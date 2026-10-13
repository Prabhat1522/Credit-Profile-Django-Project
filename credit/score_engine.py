"""
credit/score_engine.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Core Explainable Credit-Scoring Engine for E-Commerce Customers.
    Pure calculation module: completely decoupled from database queries.
    Implements:
      - 0–850 project credit score scale.
      - 5 weighted components:
          1. Payment History (35%)
          2. Outstanding Dues (25%)
          3. Order Frequency (15%)
          4. Order Value / Spend (15%)
          5. Account Age (10%)
      - Deterministic ROUND_HALF_UP rounding.
      - Canonical invoice evaluation reconciling contradictory fields.
      - Mutually exclusive profile-status decision tree.
      - Detailed positive & negative factor explanations for viva.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


def round_half_up(value: float) -> int:
    """
    Rounds a floating-point number to the nearest integer using ROUND_HALF_UP.
    Guarantees:
        416.5 -> 417
        416.49 -> 416
        757.9 -> 758
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _make_aware(dt):
    """Ensures a datetime object is timezone-aware in UTC."""
    if dt is None:
        return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_invoice(inv: dict, now: datetime = None) -> dict:
    """
    Canonical shared helper for analyzing an invoice/payment record.
    Reconciles contradictory stored fields:
      - Outstanding balance is always max(amount_due - amount_paid, 0.0).
      - If outstanding balance is 0.0, the invoice is 100% SETTLED and
        NEVER marked overdue, regardless of stored flags or past due dates.
      - If outstanding balance > 0.0, overdue status is derived from due_date vs now.

    Partitions every invoice into EXACTLY ONE of 5 mutually exclusive buckets:
      - ON_TIME: Not overdue, outstanding == 0.
      - CURRENT_PARTIAL: Not overdue, amount_paid > 0, outstanding > 0.
      - CURRENT_PENDING: Not overdue, amount_paid == 0, outstanding > 0.
      - OVERDUE_PARTIAL: Overdue, amount_paid > 0, outstanding > 0.
      - OVERDUE_UNPAID: Overdue, amount_paid == 0, outstanding > 0.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now = _make_aware(now)

    try:
        amount_due = float(inv.get("amount_due", 0.0))
    except (ValueError, TypeError):
        amount_due = 0.0

    try:
        amount_paid = float(inv.get("amount_paid", 0.0))
    except (ValueError, TypeError):
        amount_paid = 0.0

    amount_due = max(0.0, round(amount_due, 2))
    amount_paid = max(0.0, round(amount_paid, 2))
    outstanding = max(0.0, round(amount_due - amount_paid, 2))

    due_date = _make_aware(inv.get("due_date"))

    # Determine derived overdue state
    if outstanding <= 0.0:
        # Fully settled invoice — cannot be overdue under any circumstances
        is_overdue = False
        days_overdue = 0
    else:
        # Outstanding debt exists — evaluate due date
        if due_date is not None and now > due_date:
            is_overdue = True
            days_overdue = max(0, (now - due_date).days)
        else:
            # Fallback if due_date is missing: check explicit is_overdue flag
            is_overdue = bool(inv.get("is_overdue", False)) and (inv.get("status") == "overdue")
            days_overdue = int(inv.get("days_overdue", 0)) if is_overdue else 0

    # Bucket classification (Mutually exclusive)
    if is_overdue:
        if amount_paid > 0.0:
            bucket = "OVERDUE_PARTIAL"
        else:
            bucket = "OVERDUE_UNPAID"
    else:
        if outstanding <= 0.0:
            bucket = "ON_TIME"
        elif amount_paid > 0.0:
            bucket = "CURRENT_PARTIAL"
        else:
            bucket = "CURRENT_PENDING"

    return {
        "payment_id": inv.get("payment_id", ""),
        "order_id": inv.get("order_id", ""),
        "amount_due": amount_due,
        "amount_paid": amount_paid,
        "outstanding": outstanding,
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "bucket": bucket,
    }


def calculate_credit_profile(customer: dict, orders: list, payments: list, now: datetime = None) -> dict:
    """
    Calculates the 5-component explainable credit profile for a customer.

    Args:
        customer: Customer document dict
        orders: List of customer order documents
        payments: List of customer payment/invoice documents
        now: Optional evaluation timestamp (defaults to current UTC datetime)

    Returns:
        dict: Complete credit profile document ready for MongoDB storage & UI display.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now = _make_aware(now)

    customer_id = customer.get("customer_id", "UNKNOWN")

    # ─────────────────────────────────────────────────────────────────────────
    # 1. EVALUATE INVOICES & REPAYMENTS (Shared canonical helper)
    # ─────────────────────────────────────────────────────────────────────────
    evaluated_invoices = [evaluate_invoice(p, now=now) for p in payments]

    n_ontime = 0
    n_curr_part = 0
    n_curr_pend = 0
    n_over_part = 0
    n_over_unpaid = 0

    total_billed = 0.0
    total_paid = 0.0
    balance_current = 0.0
    balance_overdue = 0.0
    max_days_late = 0

    for ev in evaluated_invoices:
        b = ev["bucket"]
        total_billed += ev["amount_due"]
        total_paid += ev["amount_paid"]

        if b == "ON_TIME":
            n_ontime += 1
        elif b == "CURRENT_PARTIAL":
            n_curr_part += 1
            balance_current += ev["outstanding"]
        elif b == "CURRENT_PENDING":
            n_curr_pend += 1
            balance_current += ev["outstanding"]
        elif b == "OVERDUE_PARTIAL":
            n_over_part += 1
            balance_overdue += ev["outstanding"]
            max_days_late = max(max_days_late, ev["days_overdue"])
        elif b == "OVERDUE_UNPAID":
            n_over_unpaid += 1
            balance_overdue += ev["outstanding"]
            max_days_late = max(max_days_late, ev["days_overdue"])

    n_total_invoices = len(evaluated_invoices)
    n_overdue = n_over_part + n_over_unpaid
    total_outstanding = round(balance_current + balance_overdue, 2)
    total_billed = round(total_billed, 2)
    total_paid = round(total_paid, 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. EVALUATE ORDERS (Completed orders only)
    # ─────────────────────────────────────────────────────────────────────────
    completed_orders = [o for o in orders if o.get("status") == "completed"]
    n_completed_orders = len(completed_orders)
    total_spent = round(sum(float(o.get("total_amount", 0.0)) for o in completed_orders), 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. EVALUATE TENURE
    # ─────────────────────────────────────────────────────────────────────────
    created_at = _make_aware(customer.get("account_created_at"))
    if created_at:
        tenure_days = max(0, (now - created_at).days)
    else:
        tenure_days = 0

    # ─────────────────────────────────────────────────────────────────────────
    # 4. COMPONENT CALCULATIONS (Strictly [0.0, 100.0])
    # ─────────────────────────────────────────────────────────────────────────

    # --- Component 1: Payment History (35%) ---
    if n_total_invoices == 0:
        c_pay = 65.0  # Neutral baseline for new account
    else:
        repayment_base = (
            (n_ontime * 100.0)
            + (n_curr_part * 85.0)
            + (n_curr_pend * 70.0)
            + (n_over_part * 40.0)
            + (n_over_unpaid * 0.0)
        ) / n_total_invoices

        if n_overdue > 0:
            penalty = min(50.0, (max_days_late * 0.5) + (n_overdue * 10.0))
            c_pay = max(0.0, min(100.0, round(repayment_base - penalty, 2)))
        else:
            c_pay = max(0.0, min(100.0, round(repayment_base, 2)))

    # --- Component 2: Outstanding Dues (25%) ---
    if total_billed <= 0.0:
        c_dues = 70.0  # Clean baseline; no debt record
    elif total_outstanding <= 0.0:
        c_dues = 100.0  # Flawless debt settlement
    else:
        u_curr = balance_current / total_billed
        u_overdue = balance_overdue / total_billed
        base_dues = 100.0 - (30.0 * u_curr) - (70.0 * u_overdue)

        if balance_overdue > 0.0:
            overdue_pen = min(30.0, (balance_overdue / 1000.0) * 2.0)
            c_dues = max(0.0, min(100.0, round(base_dues - overdue_pen, 2)))
        else:
            c_dues = max(0.0, min(100.0, round(base_dues, 2)))

    # --- Component 3: Order Frequency (15%) ---
    if n_completed_orders == 0:
        c_freq = 20.0
    else:
        c_freq = min(100.0, round(20.0 + (n_completed_orders * 8.0), 2))

    # --- Component 4: Order Value / Total Spend (15%) ---
    if total_spent <= 0.0:
        c_val = 20.0
    else:
        c_val = min(100.0, round(20.0 + ((total_spent / 50000.0) * 80.0), 2))

    # --- Component 5: Account Age (10%) ---
    c_age = min(100.0, max(10.0, round((tenure_days / 365.0) * 100.0, 2)))

    # ─────────────────────────────────────────────────────────────────────────
    # 5. COMPOSITE SCORE CALCULATION & ROUND_HALF_UP SCALING
    # ─────────────────────────────────────────────────────────────────────────
    weights = {
        "payment_history": 0.35,
        "outstanding_dues": 0.25,
        "order_frequency": 0.15,
        "order_value": 0.15,
        "account_age": 0.10,
    }

    s_norm = (
        (weights["payment_history"] * c_pay)
        + (weights["outstanding_dues"] * c_dues)
        + (weights["order_frequency"] * c_freq)
        + (weights["order_value"] * c_val)
        + (weights["account_age"] * c_age)
    )
    s_norm = round(s_norm, 4)

    raw_scaled = s_norm * 8.5
    final_score = max(0, min(850, round_half_up(raw_scaled)))

    # ─────────────────────────────────────────────────────────────────────────
    # 6. MUTUALLY EXCLUSIVE & EXHAUSTIVE PROFILE-STATUS DECISION TREE
    # ─────────────────────────────────────────────────────────────────────────
    has_delinquency = (n_overdue > 0) or (balance_overdue > 0.0)

    if has_delinquency:
        # Delinquency priority: Demonstrated delinquency is NEVER masked by INSUFFICIENT_DATA
        if tenure_days >= 30 or n_completed_orders >= 1:
            profile_status = "ESTABLISHED"
        else:
            profile_status = "LIMITED_HISTORY"
    elif n_completed_orders == 0 and n_ontime == 0 and n_curr_part == 0:
        # Zero completed purchases, zero repayments made, zero delinquency
        profile_status = "INSUFFICIENT_DATA"
    elif n_completed_orders >= 3 and tenure_days >= 30:
        # Established purchasing and tenure record
        profile_status = "ESTABLISHED"
    else:
        # Early activity (1-2 orders or tenure < 30 days)
        profile_status = "LIMITED_HISTORY"

    # ─────────────────────────────────────────────────────────────────────────
    # 7. RISK CATEGORY CLASSIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    if profile_status == "INSUFFICIENT_DATA":
        risk_category = "Insufficient Data"
    else:
        if final_score >= 750:
            risk_category = "Excellent"
        elif final_score >= 650:
            risk_category = "Good"
        elif final_score >= 550:
            risk_category = "Fair"
        elif final_score >= 400:
            risk_category = "Poor"
        else:
            risk_category = "Critical"

    # ─────────────────────────────────────────────────────────────────────────
    # 8. FACTOR EXPLANATIONS (Viva & Academic Requirement)
    # ─────────────────────────────────────────────────────────────────────────
    positive_factors = []
    negative_factors = []

    # Payment History explanations
    if n_ontime > 0 and n_overdue == 0:
        positive_factors.append(f"Flawless payment track record with {n_ontime} on-time payment{'' if n_ontime == 1 else 's'}.")
    if n_curr_part > 0 and n_overdue == 0:
        positive_factors.append(f"Proactive installment repayment: partially paid {n_curr_part} invoice{'' if n_curr_part == 1 else 's'} ahead of due date.")
    if n_overdue > 0:
        negative_factors.append(f"Payment delinquency: {n_overdue} invoice{'' if n_overdue == 1 else 's'} overdue (maximum {max_days_late} days late).")

    # Dues explanations
    if total_outstanding == 0.0 and total_billed > 0.0:
        positive_factors.append("Zero outstanding debt: all billed invoices are 100% settled.")
    elif balance_overdue > 0.0:
        negative_factors.append(f"Overdue debt burden of ₹{balance_overdue:.2f} requires immediate clearance.")
    elif balance_current > 0.0:
        positive_factors.append(f"Healthy credit utilization: ₹{balance_current:.2f} in current billing term (not overdue).")

    # Order Frequency & Spend explanations
    if n_completed_orders >= 5:
        positive_factors.append(f"High engagement: {n_completed_orders} completed purchases.")
    elif n_completed_orders >= 2:
        positive_factors.append(f"Regular customer with {n_completed_orders} completed orders.")
    elif n_completed_orders == 0:
        negative_factors.append("No completed purchases recorded yet.")

    if total_spent >= 50000.0:
        positive_factors.append(f"Top-tier lifetime spending volume of ₹{total_spent:.2f}.")
    elif total_spent >= 15000.0:
        positive_factors.append(f"Substantial lifetime spend of ₹{total_spent:.2f}.")

    # Tenure explanations
    if tenure_days >= 300:
        positive_factors.append(f"Long-standing account age of {tenure_days} days.")
    elif tenure_days < 30:
        negative_factors.append(f"New account onboarding ({tenure_days} days active).")

    # ─────────────────────────────────────────────────────────────────────────
    # 9. RISK ALERTS IDENTIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    detected_alerts = []
    if n_overdue > 0:
        detected_alerts.append({
            "alert_type": "OVERDUE_PAYMENT",
            "severity": "CRITICAL" if max_days_late >= 30 else "HIGH",
            "reason": f"Customer has {n_overdue} overdue invoice(s) with ₹{balance_overdue:.2f} unpaid ({max_days_late} days late).",
        })

    if balance_overdue >= 15000.0:
        detected_alerts.append({
            "alert_type": "HIGH_OUTSTANDING",
            "severity": "HIGH",
            "reason": f"High overdue balance of ₹{balance_overdue:.2f} exceeds risk threshold.",
        })

    if risk_category == "Critical":
        detected_alerts.append({
            "alert_type": "CRITICAL_SCORE",
            "severity": "CRITICAL",
            "reason": f"Credit score ({final_score}/850) has entered the Critical risk band.",
        })

    return {
        "customer_id": customer_id,
        "score": final_score,
        "profile_status": profile_status,
        "risk_category": risk_category,
        "raw_composite_score": s_norm,
        "component_scores": {
            "payment_history": c_pay,
            "outstanding_dues": c_dues,
            "order_frequency": c_freq,
            "order_value": c_val,
            "account_age": c_age,
        },
        "weights": weights,
        "scale": "0-850",
        "financial_summary": {
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "balance_current": round(balance_current, 2),
            "balance_overdue": round(balance_overdue, 2),
            "overdue_count": n_overdue,
            "max_days_late": max_days_late,
            "completed_orders": n_completed_orders,
            "total_spent": total_spent,
            "tenure_days": tenure_days,
        },
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
        "detected_alerts": detected_alerts,
        "calculated_at": now,
    }
