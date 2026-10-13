"""
credit/urls.py
─────────────────────────────────────────────────────────────────────────────
URL configuration for Credit Profiles and Risk Alerts.
─────────────────────────────────────────────────────────────────────────────
"""

from django.urls import path
from . import views

app_name = "credit"

urlpatterns = [
    path("", views.credit_list, name="list"),
    path("recalculate-all/", views.credit_recalculate_all, name="recalculate_all"),
    path("alerts/", views.risk_alerts_list, name="alerts"),
    path("alerts/<str:alert_id>/resolve/", views.risk_alert_resolve, name="alert_resolve"),
    path("<str:customer_id>/", views.credit_detail, name="detail"),
    path("<str:customer_id>/recalculate/", views.credit_recalculate, name="recalculate"),
]
