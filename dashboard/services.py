"""
dashboard/services.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Analytics and aggregation service layer for Phase 4 Dashboard & Charts.
    Performs raw PyMongo aggregation pipelines across customers, orders,
    payments, credit_profiles, and risk_alerts collections.

VIVA TALKING POINTS:
    - "All summary metrics and chart series are computed in the database engine
      via MongoDB aggregation pipelines ($group, $match, $dateToString, $max, $subtract)
      rather than loading all documents into Python memory."
    - "Revenue calculations strictly filter status == 'completed' to prevent
      double-counting or inflating numbers with cancelled or returned orders."
    - "Outstanding debt uses $subtract(amount_due, amount_paid) clamped to 0,
      and overdue balances only include invoices where payment is delinquent."
    - "Chart.js datasets are structured into pure JSON-serializable dictionaries
      and injected into the DOM via Django's secure json_script tag."
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, time, timezone
from typing import Dict, Any, Tuple, Optional, List
from core.db_client import get_collection


def parse_date_range(start_date_str: Optional[str], end_date_str: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    """
    Parses and validates ISO date range strings (YYYY-MM-DD).

    Returns:
        (start_dt, end_dt, error_message)
        where start_dt and end_dt are timezone-aware UTC datetimes.
    """
    start_dt = None
    end_dt = None
    error = None

    if start_date_str and start_date_str.strip():
        try:
            d = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
            start_dt = datetime.combine(d.date(), time.min).replace(tzinfo=timezone.utc)
        except ValueError:
            error = f"Invalid start date '{start_date_str}'. Expected format YYYY-MM-DD."

    if end_date_str and end_date_str.strip():
        try:
            d = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")
            end_dt = datetime.combine(d.date(), time.max).replace(tzinfo=timezone.utc)
        except ValueError:
            error = f"Invalid end date '{end_date_str}'. Expected format YYYY-MM-DD."

    if start_dt and end_dt and start_dt > end_dt:
        error = "Start date cannot be after end date."
        start_dt = None
        end_dt = None

    return start_dt, end_dt, error


def get_customers_overview() -> Dict[str, Any]:
    """
    Aggregates customer counts, profile status distribution, and risk category breakdown.
    Handles empty collections and missing fields gracefully.
    """
    col_cust = get_collection("customers")
    col_profiles = get_collection("credit_profiles")

    total_customers = col_cust.count_documents({})
    active_customers = col_cust.count_documents({"is_active": True})
    inactive_customers = total_customers - active_customers

    # Profile Status Breakdown
    status_counts = {
        "ESTABLISHED": 0,
        "LIMITED_HISTORY": 0,
        "INSUFFICIENT_DATA": 0,
    }
    status_pipeline = [
        {"$group": {"_id": "$profile_status", "count": {"$sum": 1}}}
    ]
    for doc in col_profiles.aggregate(status_pipeline):
        key = doc.get("_id")
        if key in status_counts:
            status_counts[key] = doc.get("count", 0)

    # Risk Category Breakdown
    risk_counts = {
        "Excellent": 0,
        "Good": 0,
        "Fair": 0,
        "Poor": 0,
        "Critical": 0,
        "Insufficient Data": 0,
        "Insufficient_Data": 0,
    }
    risk_pipeline = [
        {"$group": {"_id": "$risk_category", "count": {"$sum": 1}}}
    ]
    for doc in col_profiles.aggregate(risk_pipeline):
        key = doc.get("_id")
        if key in risk_counts:
            risk_counts[key] = doc.get("count", 0)
    risk_counts["Insufficient_Data"] = risk_counts.get("Insufficient Data", 0)

    return {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "inactive_customers": inactive_customers,
        "profile_statuses": status_counts,
        "risk_categories": risk_counts,
    }


def get_financial_overview(start_dt: Optional[datetime] = None, end_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Aggregates financial KPIs:
      - Completed-order revenue (optionally filtered by order_date)
      - Completed order count
      - Total outstanding balance across all invoices
      - Total overdue balance across delinquent invoices
      - Current (non-overdue) outstanding balance
    """
    col_orders = get_collection("orders")
    col_payments = get_collection("payments")

    # 1. Revenue from completed orders only (strictly avoids double-counting cancelled/returned)
    match_orders: Dict[str, Any] = {"status": "completed"}
    if start_dt or end_dt:
        match_orders["order_date"] = {}
        if start_dt:
            match_orders["order_date"]["$gte"] = start_dt
        if end_dt:
            match_orders["order_date"]["$lte"] = end_dt

    revenue_pipeline = [
        {"$match": match_orders},
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": "$total_amount"},
                "order_count": {"$sum": 1},
            }
        }
    ]
    rev_results = list(col_orders.aggregate(revenue_pipeline))
    if rev_results:
        completed_revenue = round(rev_results[0].get("total_revenue", 0.0), 2)
        completed_orders = rev_results[0].get("order_count", 0)
    else:
        completed_revenue = 0.0
        completed_orders = 0

    # 2. Total Outstanding Balance: sum of max(amount_due - amount_paid, 0)
    outstanding_pipeline = [
        {
            "$group": {
                "_id": None,
                "total_outstanding": {
                    "$sum": {
                        "$max": [
                            0.0,
                            {"$subtract": [
                                {"$ifNull": ["$amount_due", 0.0]},
                                {"$ifNull": ["$amount_paid", 0.0]}
                            ]}
                        ]
                    }
                },
                "total_due": {"$sum": {"$ifNull": ["$amount_due", 0.0]}},
                "total_paid": {"$sum": {"$ifNull": ["$amount_paid", 0.0]}},
                "payment_count": {"$sum": 1},
            }
        }
    ]
    out_results = list(col_payments.aggregate(outstanding_pipeline))
    total_outstanding = round(out_results[0].get("total_outstanding", 0.0), 2) if out_results else 0.0
    total_due = round(out_results[0].get("total_due", 0.0), 2) if out_results else 0.0
    total_paid = round(out_results[0].get("total_paid", 0.0), 2) if out_results else 0.0
    total_invoices = out_results[0].get("payment_count", 0) if out_results else 0

    # 3. Total Overdue Balance: sum of outstanding debt on overdue invoices
    now = datetime.now(timezone.utc)
    overdue_pipeline = [
        {
            "$project": {
                "outstanding": {
                    "$max": [
                        0.0,
                        {"$subtract": [
                            {"$ifNull": ["$amount_due", 0.0]},
                            {"$ifNull": ["$amount_paid", 0.0]}
                        ]}
                    ]
                },
                "is_overdue": "$is_overdue",
                "due_date": "$due_date",
            }
        },
        {
            "$match": {
                "outstanding": {"$gt": 0.0},
                "$or": [
                    {"is_overdue": True},
                    {"due_date": {"$lt": now}}
                ]
            }
        },
        {
            "$group": {
                "_id": None,
                "total_overdue": {"$sum": "$outstanding"},
                "overdue_count": {"$sum": 1},
            }
        }
    ]
    overdue_results = list(col_payments.aggregate(overdue_pipeline))
    if overdue_results:
        total_overdue = round(overdue_results[0].get("total_overdue", 0.0), 2)
        overdue_invoices = overdue_results[0].get("overdue_count", 0)
    else:
        total_overdue = 0.0
        overdue_invoices = 0

    current_outstanding = round(max(total_outstanding - total_overdue, 0.0), 2)

    return {
        "completed_revenue": completed_revenue,
        "completed_order_count": completed_orders,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "current_outstanding": current_outstanding,
        "total_due": total_due,
        "total_paid": total_paid,
        "total_invoices": total_invoices,
        "overdue_invoice_count": overdue_invoices,
    }


def get_revenue_timeline(start_dt: Optional[datetime] = None, end_dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Aggregates completed-order revenue grouped by month (YYYY-MM).
    Supports optional date-range filtering.
    """
    col_orders = get_collection("orders")
    match_orders: Dict[str, Any] = {"status": "completed"}
    if start_dt or end_dt:
        match_orders["order_date"] = {}
        if start_dt:
            match_orders["order_date"]["$gte"] = start_dt
        if end_dt:
            match_orders["order_date"]["$lte"] = end_dt

    pipeline = [
        {"$match": match_orders},
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m", "date": "$order_date"}
                },
                "revenue": {"$sum": "$total_amount"},
                "order_count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}}
    ]

    results = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for doc in col_orders.aggregate(pipeline):
        key = doc.get("_id")
        if not key:
            continue
        try:
            year_part, month_part = key.split("-")
            month_idx = int(month_part) - 1
            formatted_label = f"{month_names[month_idx]} {year_part}"
        except Exception:
            formatted_label = key

        results.append({
            "month_key": key,
            "label": formatted_label,
            "revenue": round(doc.get("revenue", 0.0), 2),
            "order_count": doc.get("order_count", 0),
        })

    return results


def get_risk_alerts_overview() -> Dict[str, Any]:
    """
    Aggregates active risk alerts and their severity breakdown.
    Severities: CRITICAL, HIGH, MEDIUM, LOW.
    """
    col_alerts = get_collection("risk_alerts")

    total_active = col_alerts.count_documents({"resolved": False})
    severity_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    pipeline = [
        {"$match": {"resolved": False}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    for doc in col_alerts.aggregate(pipeline):
        key = doc.get("_id")
        if key in severity_counts:
            severity_counts[key] = doc.get("count", 0)

    return {
        "total_active": total_active,
        "severities": severity_counts,
    }


def get_dashboard_summary(start_date_str: Optional[str] = None, end_date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Main aggregator that pulls all dashboard cards and Chart.js datasets together.
    Validates date filters, builds JSON-safe payloads, and handles empty datasets.
    """
    start_dt, end_dt, filter_error = parse_date_range(start_date_str, end_date_str)

    customers = get_customers_overview()
    financials = get_financial_overview(start_dt, end_dt)
    timeline = get_revenue_timeline(start_dt, end_dt)
    alerts = get_risk_alerts_overview()

    # Build JSON-safe datasets for Chart.js
    # 1. Doughnut Chart: Risk Categories
    risk_labels = ["Excellent", "Good", "Fair", "Poor", "Critical", "Insufficient Data"]
    risk_data = [customers["risk_categories"].get(cat, 0) for cat in risk_labels]
    risk_colors = ["#10b981", "#3b82f6", "#f59e0b", "#f97316", "#ef4444", "#94a3b8"]

    # 2. Bar Chart: Profile Statuses
    status_labels = ["Established", "Limited History", "Insufficient Data"]
    status_data = [
        customers["profile_statuses"].get("ESTABLISHED", 0),
        customers["profile_statuses"].get("LIMITED_HISTORY", 0),
        customers["profile_statuses"].get("INSUFFICIENT_DATA", 0),
    ]
    status_colors = ["#4f46e5", "#818cf8", "#94a3b8"]

    # 3. Bar Chart: Outstanding vs. Overdue Balance
    balance_labels = ["Total Outstanding", "Overdue Balance"]
    balance_data = [financials["total_outstanding"], financials["total_overdue"]]
    balance_colors = ["#f59e0b", "#ef4444"]

    # 4. Line Chart: Monthly Revenue
    if timeline:
        revenue_labels = [item["label"] for item in timeline]
        revenue_data = [item["revenue"] for item in timeline]
        revenue_orders = [item["order_count"] for item in timeline]
    else:
        revenue_labels = []
        revenue_data = []
        revenue_orders = []

    # 5. Bar Chart: Active Alerts by Severity
    alert_labels = ["Critical", "High", "Medium", "Low"]
    alert_data = [
        alerts["severities"].get("CRITICAL", 0),
        alerts["severities"].get("HIGH", 0),
        alerts["severities"].get("MEDIUM", 0),
        alerts["severities"].get("LOW", 0),
    ]
    alert_colors = ["#ef4444", "#f97316", "#f59e0b", "#3b82f6"]

    charts_payload = {
        "risk_category_chart": {
            "labels": risk_labels,
            "data": risk_data,
            "colors": risk_colors,
            "total": sum(risk_data),
        },
        "profile_status_chart": {
            "labels": status_labels,
            "data": status_data,
            "colors": status_colors,
            "total": sum(status_data),
        },
        "balance_chart": {
            "labels": balance_labels,
            "data": balance_data,
            "colors": balance_colors,
        },
        "revenue_timeline_chart": {
            "labels": revenue_labels,
            "data": revenue_data,
            "orders": revenue_orders,
            "total": sum(revenue_data),
        },
        "alert_severity_chart": {
            "labels": alert_labels,
            "data": alert_data,
            "colors": alert_colors,
            "total": sum(alert_data),
        },
    }

    return {
        "customers": customers,
        "financials": financials,
        "timeline": timeline,
        "alerts": alerts,
        "charts_payload": charts_payload,
        "filter": {
            "start_date": start_date_str or "",
            "end_date": end_date_str or "",
            "is_applied": bool(start_date_str or end_date_str),
            "error": filter_error,
        },
    }
