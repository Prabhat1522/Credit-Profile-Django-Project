"""
mongo_demo/urls.py
─────────────────────────────────────────────────────────────────────────────
Routing for MongoDB Showcase and viva demo.
─────────────────────────────────────────────────────────────────────────────
"""

from django.urls import path
from . import views

app_name = "mongo_demo"

urlpatterns = [
    path("", views.index, name="index"),
]
