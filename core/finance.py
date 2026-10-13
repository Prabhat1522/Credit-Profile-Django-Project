"""
core/finance.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Reusable financial calculation and ID-generation functions.
    Every balance, overdue check, and status derivation goes here.
    Views NEVER re-implement these — they always call this module.

VIVA POINTS:
    - "We use MongoDB aggregation pipelines to sum amounts and count records
      in a single database round-trip instead of fetching all records and
      doing arithmetic in Python."
    - "ID generation uses find_one_and_update with $inc — MongoDB guarantees
      this is atomic, so two concurrent requests cannot get the same ID."
    - "Overdue status is DERIVED from due_date vs. today — it is never a
      manually set flag, so it is always accurate."
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from pymongo import ReturnDocument
from core.db_client import get_collection


# ══════════════════════════════════════════════════════════════════════════════
#  ATOMIC ID GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _next_seq(counter_name: str) -> int:
    """
    Atomically increments a counter and returns the new value.

    Uses MongoDB's find_one_and_update with $inc — this is a single atomic
    operation. Even if two web requests run simultaneously, they will receive
    different sequence numbers.

    Args:
        counter_name: Logical name of the counter (e.g. "customer_seq")

    Returns:
        Integer sequence number (starts at 1)

    VIVA: "find_one_and_update is atomic in MongoDB. $inc increments the
    counter and ReturnDocument.AFTER returns the new value in one step.
    No two calls can return the same number."
    """
    counters_col = get_collection("counters")
    result = counters_col.find_one_and_update(
        {"_id": counter_name},           # find counter document by name
        {"$inc": {"seq": 1}},            # increment seq by 1
        upsert=True,                      # create if doesn't exist (starts at 1)
        return_document=ReturnDocument.AFTER   # return UPDATED document
    )
    return result["seq"]


def generate_customer_id() -> str:
    """Returns the next customer ID string, e.g. 'CUST-001'."""
    return f"CUST-{_next_seq('customer_seq'):03d}"


def generate_order_id() -> str:
    """Returns the next order ID string, e.g. 'ORD-001'."""
    return f"ORD-{_next_seq('order_seq'):03d}"


def generate_payment_id() -> str:
    """Returns the next payment ID string, e.g. 'PAY-001'."""
    return f"PAY-{_next_seq('payment_seq'):03d}"


def seed_counter(counter_name: str, minimum_value: int):
    """
    Ensures a counter is at least at the given minimum value.
    Used by the seed script so IDs generated after seeding don't collide.
    """
    counters_col = get_collection("counters")
    existing = counters_col.find_one({"_id": counter_name})
    if existing is None or existing.get("seq", 0) < minimum_value:
        counters_col.update_one(
            {"_id": counter_name},
            {"$set": {"seq": minimum_value}},
            upsert=True
        )


# ══════════════════════════════════════════════════════════════════════════════
#  OVERDUE & STATUS DERIVATION
# ══════════════════════════════════════════════════════════════════════════════

def _make_aware(dt):
    """Makes a naive datetime timezone-aware (UTC). Returns aware datetimes unchanged."""
    if dt is None:
        return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_overdue_status(due_date, amount_due: float, amount_paid: float) -> tuple:
    """
    Derives overdue status from the due date and outstanding balance.
    Never relies on a manually stored flag.

    Rules:
        - If outstanding <= 0: not overdue (fully paid)
        - If due_date is None: not overdue (no due date set)
        - If today > due_date AND outstanding > 0: overdue

    Returns:
        (is_overdue: bool, days_overdue: int)
    """
    outstanding = amount_due - amount_paid
    if outstanding <= 0:
        return False, 0

    if due_date is None:
        return False, 0

    now = datetime.now(timezone.utc)
    due_date = _make_aware(due_date)

    if now > due_date:
        days = (now - due_date).days
        return True, max(0, days)

    return False, 0


def derive_payment_status(amount_due: float, amount_paid: float, is_overdue: bool) -> str:
    """
    Derives the payment status string from payment amounts and overdue flag.

    Status rules (in priority order):
        paid    → amount_paid >= amount_due
        overdue → outstanding > 0 AND is_overdue
        partial → amount_paid > 0 AND outstanding > 0 AND NOT overdue
        pending → amount_paid == 0 AND NOT overdue

    VIVA: "Status is always computed — never free-text. This ensures list
    pages and detail pages always show the same status for the same record."
    """
    if amount_paid >= amount_due > 0:
        return "paid"
    if is_overdue:
        return "overdue"
    if amount_paid > 0:
        return "partial"
    return "pending"


# ══════════════════════════════════════════════════════════════════════════════
#  PER-CUSTOMER AGGREGATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_customer_order_summary(customer_id: str) -> dict:
    """
    Aggregation pipeline on the 'orders' collection for one customer.

    Pipeline:
        $match  → filter by customer_id
        $group  → count orders by status + sum total_spent (completed only)

    VIVA: "$group with $cond lets us count per-status and sum amounts in a
    single database query instead of N separate find() calls."

    Returns dict with: total_orders, completed_orders, cancelled_orders,
                       returned_orders, pending_orders, total_spent
    """
    orders_col = get_collection("orders")
    pipeline = [
        {"$match": {"customer_id": customer_id}},
        {"$group": {
            "_id": "$customer_id",
            "total_orders":     {"$sum": 1},
            "completed_orders": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "cancelled_orders": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
            "returned_orders":  {"$sum": {"$cond": [{"$eq": ["$status", "returned"]},  1, 0]}},
            "pending_orders":   {"$sum": {"$cond": [{"$eq": ["$status", "pending"]},   1, 0]}},
            # Exclude cancelled/returned from total spent — only completed orders count
            "total_spent": {
                "$sum": {
                    "$cond": [{"$eq": ["$status", "completed"]}, "$total_amount", 0]
                }
            },
        }}
    ]
    results = list(orders_col.aggregate(pipeline))
    if results:
        r = results[0]
        return {
            "total_orders":     r.get("total_orders", 0),
            "completed_orders": r.get("completed_orders", 0),
            "cancelled_orders": r.get("cancelled_orders", 0),
            "returned_orders":  r.get("returned_orders", 0),
            "pending_orders":   r.get("pending_orders", 0),
            "total_spent":      round(r.get("total_spent", 0.0), 2),
        }
    return {
        "total_orders": 0, "completed_orders": 0, "cancelled_orders": 0,
        "returned_orders": 0, "pending_orders": 0, "total_spent": 0.0,
    }


def get_customer_payment_summary(customer_id: str) -> dict:
    """
    Aggregation pipeline on the 'payments' collection for one customer.

    Pipeline:
        $match → filter by customer_id
        $group → sum amount_due, amount_paid, count overdue

    Returns dict with: total_due, total_paid, outstanding_balance,
                       payment_count, overdue_count
    """
    payments_col = get_collection("payments")
    pipeline = [
        {"$match": {"customer_id": customer_id}},
        {"$group": {
            "_id":           "$customer_id",
            "total_due":     {"$sum": "$amount_due"},
            "total_paid":    {"$sum": "$amount_paid"},
            "payment_count": {"$sum": 1},
            "overdue_count": {"$sum": {"$cond": ["$is_overdue", 1, 0]}},
        }}
    ]
    results = list(payments_col.aggregate(pipeline))
    if results:
        r = results[0]
        total_due  = round(r.get("total_due",  0.0), 2)
        total_paid = round(r.get("total_paid", 0.0), 2)
        outstanding = round(max(total_due - total_paid, 0.0), 2)
        return {
            "total_due":           total_due,
            "total_paid":          total_paid,
            "outstanding_balance": outstanding,
            "payment_count":       r.get("payment_count", 0),
            "overdue_count":       r.get("overdue_count", 0),
        }
    return {
        "total_due": 0.0, "total_paid": 0.0,
        "outstanding_balance": 0.0, "payment_count": 0, "overdue_count": 0,
    }


def get_customer_full_summary(customer_id: str) -> dict:
    """
    Combines order and payment summaries into one dict.
    Used on customer detail pages and summary cards.
    """
    order_s   = get_customer_order_summary(customer_id)
    payment_s = get_customer_payment_summary(customer_id)
    return {**order_s, **payment_s}


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD-LEVEL AGGREGATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_global_payment_summary() -> dict:
    """
    Aggregates total outstanding and overdue count across ALL customers.
    Used by the dashboard summary cards (Phase 4).

    VIVA: "$group with _id: null aggregates ALL documents into a single
    result — useful for dashboard totals."
    """
    payments_col = get_collection("payments")
    pipeline = [
        {"$group": {
            "_id":          None,
            "total_due":    {"$sum": "$amount_due"},
            "total_paid":   {"$sum": "$amount_paid"},
            "overdue_count": {"$sum": {"$cond": ["$is_overdue", 1, 0]}},
        }}
    ]
    results = list(payments_col.aggregate(pipeline))
    if results:
        r = results[0]
        total_due  = r.get("total_due", 0.0)
        total_paid = r.get("total_paid", 0.0)
        return {
            "total_outstanding":      round(max(total_due - total_paid, 0.0), 2),
            "total_overdue_payments": r.get("overdue_count", 0),
        }
    return {"total_outstanding": 0.0, "total_overdue_payments": 0}
