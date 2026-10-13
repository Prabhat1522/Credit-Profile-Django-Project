"""dashboard/urls.py"""
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    # MongoDB connection test endpoint — useful during setup
    path("db-status/", views.db_status, name="db_status"),
]
