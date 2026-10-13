"""
mongo_demo/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Interactive MongoDB Showcase & Viva Demonstration View.
    Demonstrates live PyMongo operations:
      - Aggregation pipelines ($group, $cond, $dateToString)
      - Schema validators ($jsonSchema)
      - Atomic sequence counters ($inc with find_one_and_update)
      - Compound and unique indexes
    Protected by @login_required.
─────────────────────────────────────────────────────────────────────────────
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.db_client import get_db, get_collection
from core.validators import CUSTOMERS_VALIDATOR, PAYMENTS_VALIDATOR, ORDERS_VALIDATOR


@login_required
def index(request):
    """
    Renders live MongoDB demonstration and viva reference dashboard.
    """
    db = get_db()
    collections_names = db.list_collection_names()

    # 1. Collection Statistics
    collection_stats = []
    for name in ["customers", "orders", "payments", "credit_profiles", "risk_alerts", "counters"]:
        col = db[name]
        count = col.count_documents({})
        collection_stats.append({
            "name": name,
            "count": count,
            "exists": name in collections_names,
        })

    # 2. Live Aggregation Demo 1: Order breakdown by status
    pipeline_orders = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$total_amount"},
            }
        },
        {"$sort": {"total_value": -1}}
    ]
    orders_agg = [
        {"status": o["_id"], "count": o["count"], "total_value": o.get("total_value", 0.0)}
        for o in db.orders.aggregate(pipeline_orders)
    ]

    # 3. Live Aggregation Demo 2: Payment Dues and Overdue
    pipeline_payments = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_due": {"$sum": "$amount_due"},
                "total_paid": {"$sum": "$amount_paid"},
            }
        },
        {"$sort": {"count": -1}}
    ]
    payments_agg = [
        {"status": p["_id"], "count": p["count"], "total_due": p.get("total_due", 0.0), "total_paid": p.get("total_paid", 0.0)}
        for p in db.payments.aggregate(pipeline_payments)
    ]

    # 4. Atomic Counter State
    counters = [
        {"name": c["_id"], "seq": c.get("seq", 0)}
        for c in db.counters.find()
    ]

    # 5. Active Indexes
    indexes = {}
    for name in ["customers", "orders", "payments", "credit_profiles", "risk_alerts"]:
        indexes[name] = list(db[name].list_indexes())

    context = {
        "page_title": "MongoDB Architecture & Viva Demo",
        "collection_stats": collection_stats,
        "orders_agg": orders_agg,
        "payments_agg": payments_agg,
        "counters": counters,
        "indexes": indexes,
        "customers_validator": CUSTOMERS_VALIDATOR,
        "payments_validator": PAYMENTS_VALIDATOR,
        "orders_validator": ORDERS_VALIDATOR,
    }
    return render(request, "mongo_demo/index.html", context)
