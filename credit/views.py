"""
credit/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Controller views for Credit Profiles and Risk Alerts.
    All operations are protected with Django's @login_required decorator
    and state-changing actions require POST with CSRF protection.
─────────────────────────────────────────────────────────────────────────────
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import Http404

from credit import services as credit_services
from core.db_client import get_collection


@login_required
def credit_list(request):
    """
    Renders table of customer credit profiles with filters for risk category,
    profile status, search query, and sorting.
    """
    q = request.GET.get("q", "").strip()
    risk_cat = request.GET.get("risk", "all")
    status_filter = request.GET.get("status", "all")
    sort_by = request.GET.get("sort", "-score")
    page = int(request.GET.get("page", 1) or 1)

    # Check if any profiles exist; if 0, auto-calculate for all customers
    col_profiles = get_collection("credit_profiles")
    if col_profiles.count_documents({}) == 0:
        credit_services.recalculate_all_credit_profiles()

    data = credit_services.get_credit_profiles(
        q=q,
        risk_category=risk_cat,
        profile_status=status_filter,
        page=page,
        per_page=10,
        sort_by=sort_by
    )

    # Count active unresolved risk alerts for badge
    active_alerts_count = get_collection("risk_alerts").count_documents({"resolved": False})

    context = {
        "page_title": "Credit Profiles",
        "profiles": data["profiles"],
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
        "page_range": data["page_range"],
        "q": q,
        "risk_cat": risk_cat,
        "status_filter": status_filter,
        "sort_by": sort_by,
        "active_alerts_count": active_alerts_count,
    }
    return render(request, "credit/list.html", context)


@login_required
def credit_detail(request, customer_id):
    """
    Renders deep-dive credit analysis for a single customer.
    Includes score breakdown, component bars, factor explanations, and active alerts.
    """
    profile = credit_services.get_or_calculate_credit_profile(customer_id)
    if not profile:
        messages.error(request, f"Customer '{customer_id}' was not found.")
        return redirect("credit:list")

    # Fetch customer's risk alerts
    alerts = list(get_collection("risk_alerts").find({"customer_id": customer_id}).sort("created_at", -1))

    context = {
        "page_title": f"Credit Profile: {profile.get('customer_name', customer_id)}",
        "profile": profile,
        "alerts": alerts,
        "customer_id": customer_id,
    }
    return render(request, "credit/detail.html", context)


@login_required
@require_POST
def credit_recalculate(request, customer_id):
    """
    Forces recalculation of a customer's credit profile.
    Protected with POST and CSRF.
    """
    profile = credit_services.get_or_calculate_credit_profile(customer_id, force_recalculate=True)
    if not profile:
        messages.error(request, f"Could not recalculate profile for '{customer_id}'.")
        return redirect("credit:list")

    messages.success(request, f"Credit profile for {customer_id} successfully recalculated! New score: {profile['score']}/850 ({profile['risk_category']}).")
    return redirect("credit:detail", customer_id=customer_id)


@login_required
@require_POST
def credit_recalculate_all(request):
    """
    Forces recalculation of all customer profiles in bulk.
    """
    count = credit_services.recalculate_all_credit_profiles()
    messages.success(request, f"Successfully recalculated {count} customer credit profiles!")
    return redirect("credit:list")


@login_required
def risk_alerts_list(request):
    """
    Displays list of system-wide risk alerts with active/resolved toggle.
    """
    status_tab = request.GET.get("tab", "active")
    resolved = (status_tab == "resolved")
    page = int(request.GET.get("page", 1) or 1)

    data = credit_services.get_risk_alerts(resolved=resolved, page=page, per_page=15)

    # Active count for tab badge
    active_count = get_collection("risk_alerts").count_documents({"resolved": False})
    resolved_count = get_collection("risk_alerts").count_documents({"resolved": True})

    context = {
        "page_title": "Risk Alerts",
        "alerts": data["alerts"],
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
        "page_range": data["page_range"],
        "status_tab": status_tab,
        "active_count": active_count,
        "resolved_count": resolved_count,
    }
    return render(request, "credit/risk_alerts.html", context)


@login_required
@require_POST
def risk_alert_resolve(request, alert_id):
    """
    Marks an alert as resolved.
    """
    notes = request.POST.get("notes", "").strip()
    success = credit_services.resolve_risk_alert(alert_id, notes)
    if success:
        messages.success(request, "Risk alert marked as resolved.")
    else:
        messages.error(request, "Failed to resolve alert.")
    return redirect("credit:alerts")
