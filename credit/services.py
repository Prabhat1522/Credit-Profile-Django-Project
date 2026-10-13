"""
credit/services.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Data access and persistence layer for credit profiles and risk alerts.
    Coordinates between raw PyMongo collections and credit/score_engine.py.
    Provides:
      - Upsert logic for credit profiles (avoiding duplicates).
      - Duplicate prevention and automatic resolution for risk alerts.
      - Paginated search and filtering for credit dashboard.
─────────────────────────────────────────────────────────────────────────────
"""

import math
import re
from datetime import datetime, timezone
from bson import ObjectId
from core.db_client import get_collection
from credit.score_engine import calculate_credit_profile, evaluate_invoice


def get_or_calculate_credit_profile(customer_id: str, force_recalculate: bool = False) -> dict:
    """
    Fetches the customer's credit profile from MongoDB Atlas.
    If the profile does not exist or force_recalculate is True, it calculates
    the profile using the scoring engine, upserts it, and updates risk alerts.
    """
    col_profiles = get_collection("credit_profiles")

    if not force_recalculate:
        existing = col_profiles.find_one({"customer_id": customer_id})
        if existing:
            return existing

    # Fetch fresh raw data from MongoDB collections
    col_customers = get_collection("customers")
    col_orders = get_collection("orders")
    col_payments = get_collection("payments")

    customer = col_customers.find_one({"customer_id": customer_id})
    if not customer:
        return None

    orders = list(col_orders.find({"customer_id": customer_id}))
    payments = list(col_payments.find({"customer_id": customer_id}))

    # Calculate using the pure engine
    profile_data = calculate_credit_profile(customer, orders, payments)

    # Attach customer metadata for easy display
    profile_data["customer_name"] = customer.get("full_name", "")
    profile_data["customer_email"] = customer.get("email", "")

    # Atomic upsert into credit_profiles collection
    col_profiles.update_one(
        {"customer_id": customer_id},
        {"$set": profile_data},
        upsert=True
    )

    # Synchronize risk alerts
    _sync_risk_alerts(customer_id, profile_data.get("detected_alerts", []), profile_data)

    return profile_data


def _sync_risk_alerts(customer_id: str, detected_alerts: list, profile_data: dict):
    """
    Syncs detected risk alerts with the risk_alerts collection.
    Prevents duplicate unresolved alerts and marks healed conditions as resolved.
    """
    col_alerts = get_collection("risk_alerts")
    now = datetime.now(timezone.utc)

    active_alert_types = {a["alert_type"] for a in detected_alerts}

    # 1. Upsert / Insert detected alerts
    for a in detected_alerts:
        alert_type = a["alert_type"]
        existing = col_alerts.find_one({
            "customer_id": customer_id,
            "alert_type": alert_type,
            "resolved": False
        })

        if existing:
            # Update last evaluation time and reason without duplicating
            col_alerts.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "last_evaluated_at": now,
                    "reason": a["reason"],
                    "severity": a["severity"],
                    "credit_score": profile_data.get("score"),
                }}
            )
        else:
            # Insert new unresolved alert
            doc = {
                "customer_id": customer_id,
                "alert_type": alert_type,
                "severity": a["severity"],
                "reason": a["reason"],
                "credit_score": profile_data.get("score"),
                "risk_category": profile_data.get("risk_category"),
                "created_at": now,
                "last_evaluated_at": now,
                "resolved": False,
            }
            col_alerts.insert_one(doc)

    # 2. Auto-resolve alerts whose conditions are no longer present
    # (e.g. customer had OVERDUE_PAYMENT, but now has paid their balance)
    col_alerts.update_many(
        {
            "customer_id": customer_id,
            "resolved": False,
            "alert_type": {"$nin": list(active_alert_types)}
        },
        {
            "$set": {
                "resolved": True,
                "resolved_at": now,
                "resolution_notes": "Automatically resolved: condition cleared upon score recalculation."
            }
        }
    )


def get_credit_profiles(q=None, risk_category=None, profile_status=None, page=1, per_page=10, sort_by="-score"):
    """
    Retrieves a paginated list of credit profiles with optional search & filters.
    """
    col_profiles = get_collection("credit_profiles")
    filter_query = {}

    if risk_category and risk_category != "all":
        filter_query["risk_category"] = risk_category

    if profile_status and profile_status != "all":
        filter_query["profile_status"] = profile_status

    if q and q.strip():
        safe_q = re.escape(q.strip())
        filter_query["$or"] = [
            {"customer_id": {"$regex": safe_q, "$options": "i"}},
            {"customer_name": {"$regex": safe_q, "$options": "i"}},
            {"risk_category": {"$regex": safe_q, "$options": "i"}},
        ]

    total = col_profiles.count_documents(filter_query)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    sort_dir = -1 if sort_by.startswith("-") else 1
    sort_field = sort_by.lstrip("-")
    if sort_field not in ["score", "calculated_at", "customer_id"]:
        sort_field = "score"
        sort_dir = -1

    profiles = list(col_profiles.find(filter_query).sort(sort_field, sort_dir).skip(skip).limit(per_page))

    return {
        "profiles": profiles,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "page_range": list(range(1, total_pages + 1)),
    }


def get_risk_alerts(customer_id=None, resolved=False, page=1, per_page=10):
    """
    Fetches paginated risk alerts.
    """
    col_alerts = get_collection("risk_alerts")
    filter_query = {"resolved": resolved}
    if customer_id:
        filter_query["customer_id"] = customer_id

    total = col_alerts.count_documents(filter_query)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    alerts = list(col_alerts.find(filter_query).sort("created_at", -1).skip(skip).limit(per_page))

    # Add customer full name if available and string id for templates
    col_cust = get_collection("customers")
    for a in alerts:
        a["id"] = str(a["_id"])
        cust = col_cust.find_one({"customer_id": a.get("customer_id")}, {"full_name": 1})
        a["customer_name"] = cust["full_name"] if cust else "Unknown"

    return {
        "alerts": alerts,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "page_range": list(range(1, total_pages + 1)),
    }


def resolve_risk_alert(alert_id_str: str, resolution_notes: str = ""):
    """Manually marks a risk alert as resolved."""
    col_alerts = get_collection("risk_alerts")
    try:
        oid = ObjectId(alert_id_str)
    except Exception:
        return False

    res = col_alerts.update_one(
        {"_id": oid},
        {"$set": {
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc),
            "resolution_notes": resolution_notes.strip() or "Manually marked as resolved by admin."
        }}
    )
    return res.modified_count > 0


def recalculate_all_credit_profiles():
    """
    Batch recalculates credit profiles for all customers in the database.
    Useful for initial setup and seed data sync.
    """
    col_cust = get_collection("customers")
    customers = list(col_cust.find({}, {"customer_id": 1}))
    count = 0
    for c in customers:
        cid = c.get("customer_id")
        if cid:
            get_or_calculate_credit_profile(cid, force_recalculate=True)
            count += 1
    return count
