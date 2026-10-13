"""
customers/urls.py
─────────────────────────────────────────────────────────────────────────────
URL configuration for the customers app.
All routes map directly to PyMongo-backed views.
─────────────────────────────────────────────────────────────────────────────
"""

from django.urls import path
from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("add/", views.customer_create, name="create"),
    path("export/csv/", views.customer_export_csv, name="export_csv"),
    path("<str:customer_id>/", views.customer_detail, name="detail"),
    path("<str:customer_id>/edit/", views.customer_update, name="update"),
    path("<str:customer_id>/delete/", views.customer_delete, name="delete"),
]
