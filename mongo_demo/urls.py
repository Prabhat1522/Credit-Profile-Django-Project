"""mongo_demo/urls.py — Placeholder for Phase 5."""
from django.urls import path
from . import views

app_name = "mongo_demo"

urlpatterns = [
    path("", views.placeholder, name="index"),
]
