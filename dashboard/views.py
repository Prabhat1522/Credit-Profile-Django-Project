"""
dashboard/views.py
─────────────────────────────────────────────────────────────────────────────
Phase 1: Provides a setup-status dashboard and a MongoDB connection test.
Phase 4: Will be extended with full analytics and Chart.js charts.
─────────────────────────────────────────────────────────────────────────────
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone


def index(request):
    """
    Main dashboard view.

    Phase 1: Shows system setup status — confirms Django is running,
    MongoDB connection state, and which collections exist.

    Phase 4: Will display summary cards and Chart.js analytics.
    """
    # Try to get MongoDB connection status
    mongo_status = _check_mongo_connection()

    phases = [
        {"number": 1, "name": "Setup & Foundation",  "status": "completed"},
        {"number": 2, "name": "Customer CRUD & Data", "status": "completed"},
        {"number": 3, "name": "Credit Engine",        "status": "active"},
        {"number": 4, "name": "Dashboard & Charts",   "status": "pending"},
        {"number": 5, "name": "Demo & Reports",       "status": "pending"},
    ]

    context = {
        "page_title": "Dashboard",
        "mongo_status": mongo_status,
        "current_year": timezone.now().year,
        "phases": phases,
        "expected_collections": [
            "customers", "orders", "payments", "credit_profiles", "risk_alerts"
        ],
    }
    return render(request, "dashboard/index.html", context)


def db_status(request):
    """
    JSON endpoint to check MongoDB connection status.
    Useful for manual testing during Phase 1 setup.

    Visit: http://127.0.0.1:8000/dashboard/db-status/
    Returns JSON like: {"status": "ok", "db_name": "credit_profile", "collections": [...]}
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
