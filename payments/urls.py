"""
payments/urls.py
─────────────────────────────────────────────────────────────────────────────
URL routing for the payments app.
─────────────────────────────────────────────────────────────────────────────
"""

from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="list"),
    path("add/", views.payment_create, name="create"),
    path("export/csv/", views.payment_export_csv, name="export_csv"),
    path("<str:payment_id>/", views.payment_detail, name="detail"),
    path("<str:payment_id>/pay/", views.payment_record_pay, name="record_pay"),
    path("<str:payment_id>/delete/", views.payment_delete, name="delete"),
]
