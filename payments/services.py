"""
payments/services.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Data access layer for the 'payments' MongoDB collection using raw PyMongo.
    Adheres strictly to the PAYMENTS_VALIDATOR $jsonSchema:
      - required: payment_id, order_id, customer_id, amount_due, amount_paid,
                  status, is_overdue
      - payment_mode: "COD" | "UPI" | "Card" | "EMI" | "Wallet"
      - status: "paid" | "pending" | "overdue" | "partial" | "waived"
      - status and overdue are ALWAYS derived using core.finance functions.
─────────────────────────────────────────────────────────────────────────────
"""

import math
import re
from datetime import datetime, timezone
from core.db_client import get_collection
from core.finance import (
    generate_payment_id,
    compute_overdue_status,
    derive_payment_status
)


def get_payments(customer_id=None, status=None, is_overdue=None, q=None, page=1, per_page=10, sort_by="-due_date"):
    """
    Retrieves paginated payments matching filters.
    """
    col = get_collection("payments")
    filter_query = {}

    if customer_id:
        filter_query["customer_id"] = customer_id

    if status and status != "all":
        filter_query["status"] = status

    if is_overdue is not None:
        filter_query["is_overdue"] = bool(is_overdue)

    if q and q.strip():
        safe_q = re.escape(q.strip())
        filter_query["$or"] = [
            {"payment_id": {"$regex": safe_q, "$options": "i"}},
            {"order_id": {"$regex": safe_q, "$options": "i"}},
            {"customer_id": {"$regex": safe_q, "$options": "i"}},
        ]

    total = col.count_documents(filter_query)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    sort_dir = -1 if sort_by.startswith("-") else 1
    sort_field = sort_by.lstrip("-")
    if sort_field not in ["due_date", "payment_date", "amount_due", "payment_id"]:
        sort_field = "due_date"
        sort_dir = -1

    payments = list(col.find(filter_query).sort(sort_field, sort_dir).skip(skip).limit(per_page))

    # Enhance payments with customer names
    cust_col = get_collection("customers")
    for p in payments:
        cust = cust_col.find_one({"customer_id": p.get("customer_id")}, {"full_name": 1})
        p["customer_name"] = cust["full_name"] if cust else "Unknown Customer"
        p["outstanding"] = round(max(p.get("amount_due", 0.0) - p.get("amount_paid", 0.0), 0.0), 2)

    return {
        "payments": payments,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "page_range": list(range(1, total_pages + 1)),
    }


def get_payment_by_id(payment_id):
    """Fetches payment with customer and order lookups."""
    col = get_collection("payments")
    payment = col.find_one({"payment_id": payment_id})
    if payment:
        payment["customer"] = get_collection("customers").find_one({"customer_id": payment.get("customer_id")})
        payment["order"] = get_collection("orders").find_one({"order_id": payment.get("order_id")})
        payment["outstanding"] = round(max(payment.get("amount_due", 0.0) - payment.get("amount_paid", 0.0), 0.0), 2)
    return payment


def create_payment(data):
    """
    Creates a new payment record, computing overdue status and derived payment status.
    """
    col = get_collection("payments")

    payment_id = data.get("payment_id") or generate_payment_id()
    order_id = (data.get("order_id") or "").strip()
    customer_id = (data.get("customer_id") or "").strip()
    amount_due = float(data.get("amount_due", 0.0))
    amount_paid = float(data.get("amount_paid", 0.0))

    if not order_id:
        raise ValueError("Order ID is required.")
    if not customer_id:
        raise ValueError("Customer ID is required.")
    if amount_due < 0 or amount_paid < 0:
        raise ValueError("Amounts cannot be negative.")

    due_date = data.get("due_date")
    if due_date and isinstance(due_date, str):
        try:
            due_date = datetime.strptime(due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            due_date = None

    # Compute overdue and status
    is_overdue, days_overdue = compute_overdue_status(due_date, amount_due, amount_paid)
    status = derive_payment_status(amount_due, amount_paid, is_overdue)

    payment_mode = data.get("payment_mode", "UPI")
    if payment_mode not in ["COD", "UPI", "Card", "EMI", "Wallet"]:
        payment_mode = "UPI"

    doc = {
        "payment_id": payment_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "amount_due": float(amount_due),
        "amount_paid": float(amount_paid),
        "status": status,
        "is_overdue": bool(is_overdue),
        "days_overdue": int(days_overdue),
        "payment_mode": payment_mode,
    }

    if due_date:
        doc["due_date"] = due_date

    payment_date = data.get("payment_date")
    if payment_date:
        if isinstance(payment_date, str):
            try:
                payment_date = datetime.strptime(payment_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                payment_date = None
        if payment_date:
            doc["payment_date"] = payment_date

    col.insert_one(doc)
    return doc


def record_transaction(payment_id, payment_amount, payment_mode=None, transaction_date=None):
    """
    Records a payment transaction against an existing payment record.
    Increases amount_paid, updates payment_mode, recalculates overdue & status.
    """
    col = get_collection("payments")
    payment = col.find_one({"payment_id": payment_id})
    if not payment:
        raise ValueError(f"Payment '{payment_id}' does not exist.")

    amount_to_add = float(payment_amount)
    if amount_to_add <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    new_amount_paid = round(float(payment.get("amount_paid", 0.0)) + amount_to_add, 2)
    amount_due = float(payment.get("amount_due", 0.0))
    due_date = payment.get("due_date")

    is_overdue, days_overdue = compute_overdue_status(due_date, amount_due, new_amount_paid)
    new_status = derive_payment_status(amount_due, new_amount_paid, is_overdue)

    tdate = transaction_date or datetime.now(timezone.utc)
    if hasattr(tdate, "tzinfo") and tdate.tzinfo is None:
        tdate = tdate.replace(tzinfo=timezone.utc)

    update_fields = {
        "amount_paid": float(new_amount_paid),
        "status": new_status,
        "is_overdue": bool(is_overdue),
        "days_overdue": int(days_overdue),
        "payment_date": tdate,
    }

    if payment_mode:
        update_fields["payment_mode"] = payment_mode

    col.update_one({"payment_id": payment_id}, {"$set": update_fields})
    return True


def delete_payment(payment_id):
    """Deletes payment document."""
    col = get_collection("payments")
    res = col.delete_one({"payment_id": payment_id})
    return res.deleted_count > 0
