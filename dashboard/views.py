"""
dashboard/views.py
─────────────────────────────────────────────────────────────────────────────
Phase 1: Setup-status dashboard and MongoDB connection test.
Phase 4: Full analytics dashboard with KPIs, date filtering, and Chart.js charts.
─────────────────────────────────────────────────────────────────────────────
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from dashboard.services import get_dashboard_summary


@login_required
def index(request):
    """
    Main analytics dashboard view (Phase 4).
    Displays KPI summary cards, date-range filters, and 5 interactive Chart.js charts.
    """
    start_date_str = request.GET.get("start_date", "").strip()
    end_date_str = request.GET.get("end_date", "").strip()

    # Query MongoDB analytics via service layer
    try:
        summary = get_dashboard_summary(start_date_str, end_date_str)
        mongo_status = _check_mongo_connection()
    except Exception as e:
        messages.error(request, f"Unable to aggregate analytics from MongoDB: {str(e)}")
        summary = {
            "customers": {"total_customers": 0, "active_customers": 0, "inactive_customers": 0, "profile_statuses": {}, "risk_categories": {}},
            "financials": {"completed_revenue": 0.0, "completed_order_count": 0, "total_outstanding": 0.0, "total_overdue": 0.0, "current_outstanding": 0.0},
            "timeline": [],
            "alerts": {"total_active": 0, "severities": {}},
            "charts_payload": {
                "risk_category_chart": {"labels": [], "data": [], "colors": [], "total": 0},
                "profile_status_chart": {"labels": [], "data": [], "colors": [], "total": 0},
                "balance_chart": {"labels": [], "data": [], "colors": []},
                "revenue_timeline_chart": {"labels": [], "data": [], "orders": [], "total": 0},
                "alert_severity_chart": {"labels": [], "data": [], "colors": [], "total": 0},
            },
            "filter": {"start_date": start_date_str, "end_date": end_date_str, "is_applied": False, "error": str(e)},
        }
        mongo_status = {"status": "error", "message": str(e), "collections": []}

    # Warn if date filter was invalid
    if summary["filter"].get("error"):
        messages.warning(request, summary["filter"]["error"])

    phases = [
        {"number": 1, "name": "Setup & Foundation",  "status": "completed"},
        {"number": 2, "name": "Customer CRUD & Data", "status": "completed"},
        {"number": 3, "name": "Credit Engine",        "status": "completed"},
        {"number": 4, "name": "Dashboard & Charts",   "status": "completed"},
        {"number": 5, "name": "Demo & Reports",       "status": "active"},
    ]

    context = {
        "page_title": "Executive Dashboard",
        "mongo_status": mongo_status,
        "current_year": timezone.now().year,
        "phases": phases,
        "customers": summary["customers"],
        "financials": summary["financials"],
        "alerts": summary["alerts"],
        "timeline": summary["timeline"],
        "filter": summary["filter"],
        "charts_payload": summary["charts_payload"],
    }
    return render(request, "dashboard/index.html", context)


def db_status(request):
    """
    JSON endpoint to check MongoDB connection status.
    Preserved for debugging and status polling.

    Visit: http://127.0.0.1:8000/dashboard/db-status/
    """
    result = _check_mongo_connection()
    return JsonResponse(result)


def _check_mongo_connection() -> dict:
    """
    Internal helper: attempts to connect to MongoDB and lists collections.
    Returns a dict describing the connection state.
    """
    try:
        from core.db_client import get_db
        db = get_db()

        collections = db.list_collection_names()
        return {
            "status": "ok",
            "message": "Connected to MongoDB Atlas successfully.",
            "db_name": db.name,
            "collections": collections,
        }
    except EnvironmentError as e:
        return {
            "status": "error",
            "message": "MONGODB_URI is not set in .env",
            "detail": str(e),
            "collections": [],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Cannot connect to MongoDB.",
            "detail": str(e),
            "collections": [],
        }
