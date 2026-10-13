"""
orders/urls.py
─────────────────────────────────────────────────────────────────────────────
URL routing for the orders app.
─────────────────────────────────────────────────────────────────────────────
"""

from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("add/", views.order_create, name="create"),
    path("export/csv/", views.order_export_csv, name="export_csv"),
    path("<str:order_id>/", views.order_detail, name="detail"),
    path("<str:order_id>/edit/", views.order_update, name="update"),
    path("<str:order_id>/delete/", views.order_delete, name="delete"),
]
