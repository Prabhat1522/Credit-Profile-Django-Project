"""
orders/services.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Data access layer for the 'orders' MongoDB collection using raw PyMongo.
    Enforces $jsonSchema validator compliance:
      - required: order_id, customer_id, order_date, items, total_amount, status
      - items: array of objects with product_name, quantity (int >= 1),
               unit_price (double >= 0), subtotal (double >= 0)
      - status: 'pending', 'completed', 'cancelled', 'returned'
─────────────────────────────────────────────────────────────────────────────
"""

import math
import re
from datetime import datetime, timezone
from core.db_client import get_collection
from core.finance import generate_order_id, generate_payment_id


def get_orders(customer_id=None, status=None, q=None, page=1, per_page=10, sort_by="-order_date"):
    """
    Retrieves paginated orders with filters for customer, status, or search text.
    """
    col = get_collection("orders")
    filter_query = {}

    if customer_id:
        filter_query["customer_id"] = customer_id

    if status and status != "all":
        filter_query["status"] = status

    if q and q.strip():
        safe_q = re.escape(q.strip())
        filter_query["$or"] = [
            {"order_id": {"$regex": safe_q, "$options": "i"}},
            {"customer_id": {"$regex": safe_q, "$options": "i"}},
            {"items.product_name": {"$regex": safe_q, "$options": "i"}},
        ]

    total = col.count_documents(filter_query)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    sort_dir = -1 if sort_by.startswith("-") else 1
    sort_field = sort_by.lstrip("-")
    if sort_field not in ["order_date", "total_amount", "order_id"]:
        sort_field = "order_date"
        sort_dir = -1

    orders = list(col.find(filter_query).sort(sort_field, sort_dir).skip(skip).limit(per_page))

    # Also lookup customer full name for each order for display convenience
    customers_col = get_collection("customers")
    for o in orders:
        cust = customers_col.find_one({"customer_id": o.get("customer_id")}, {"full_name": 1})
        o["customer_name"] = cust["full_name"] if cust else "Unknown Customer"

    return {
        "orders": orders,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "page_range": list(range(1, total_pages + 1)),
    }


def get_order_by_id(order_id):
    """Fetches single order by order_id."""
    col = get_collection("orders")
    order = col.find_one({"order_id": order_id})
    if order:
        cust = get_collection("customers").find_one({"customer_id": order.get("customer_id")})
        order["customer"] = cust
    return order


def create_order(data, create_pending_payment=True, due_days=15):
    """
    Creates an order document and inserts it into MongoDB.
    Optionally creates an associated pending payment invoice.

    Args:
        data: Dict containing customer_id, items, status, optional notes, optional order_date
        create_pending_payment: If True, creates matching payment document
        due_days: Number of days until payment is due (default 15)
    """
    col = get_collection("orders")

    order_id = data.get("order_id") or generate_order_id()
    customer_id = data.get("customer_id")
    if not customer_id:
        raise ValueError("Customer ID is required.")

    # Validate customer exists
    cust = get_collection("customers").find_one({"customer_id": customer_id})
    if not cust:
        raise ValueError(f"Customer '{customer_id}' does not exist.")

    items_raw = data.get("items", [])
    if not items_raw or len(items_raw) < 1:
        raise ValueError("At least one line item is required in the order.")

    items = []
    total_amount = 0.0

    for it in items_raw:
        pname = (it.get("product_name") or "").strip()
        if not pname:
            continue
        qty = int(it.get("quantity", 1))
        unit_p = float(it.get("unit_price", 0.0))
        subtotal = round(qty * unit_p, 2)
        items.append({
            "product_name": pname,
            "quantity": int(qty),
            "unit_price": float(unit_p),
            "subtotal": float(subtotal),
        })
        total_amount += subtotal

    if not items:
        raise ValueError("Order must contain at least one valid product.")

    total_amount = round(total_amount, 2)
    order_date = data.get("order_date") or datetime.now(timezone.utc)
    if hasattr(order_date, "tzinfo") and order_date.tzinfo is None:
        order_date = order_date.replace(tzinfo=timezone.utc)

    status = data.get("status", "pending")
    if status not in ["pending", "completed", "cancelled", "returned"]:
        status = "pending"

    order_doc = {
        "order_id": order_id,
        "customer_id": customer_id,
        "order_date": order_date,
        "items": items,
        "total_amount": float(total_amount),
        "status": status,
    }

    if data.get("notes"):
        order_doc["notes"] = str(data["notes"]).strip()

    col.insert_one(order_doc)

    # Automatically generate corresponding payment record if order is not cancelled
    if create_pending_payment and status in ["pending", "completed"]:
        from datetime import timedelta
        due_date = order_date + timedelta(days=due_days)
        payment_doc = {
            "payment_id": generate_payment_id(),
            "order_id": order_id,
            "customer_id": customer_id,
            "amount_due": float(total_amount),
            "amount_paid": 0.0,
            "status": "pending",
            "is_overdue": False,
            "days_overdue": 0,
            "due_date": due_date,
            "payment_mode": "UPI",
        }
        get_collection("payments").insert_one(payment_doc)

    return order_doc


def update_order_status(order_id, new_status, notes=None):
    """Updates order status and optional notes."""
    if new_status not in ["pending", "completed", "cancelled", "returned"]:
        raise ValueError("Invalid order status.")

    col = get_collection("orders")
    update_data = {"status": new_status}
    if notes is not None:
        update_data["notes"] = notes

    col.update_one({"order_id": order_id}, {"$set": update_data})
    return True


def delete_order(order_id):
    """Deletes order document."""
    col = get_collection("orders")
    res = col.delete_one({"order_id": order_id})
    return res.deleted_count > 0
