"""
credit_profile/urls.py
─────────────────────────────────────────────────────────────────────────────
Root URL configuration.

HOW DJANGO ROUTING WORKS:
    When a user visits a URL, Django checks this file top to bottom.
    The first pattern that matches is used.
    Each app has its own urls.py (included here with include()).

URL STRUCTURE:
    /                     → Redirect to /dashboard/
    /accounts/login/      → Login page (accounts app)
    /accounts/logout/     → Logout (accounts app)
    /dashboard/           → Analytics dashboard (dashboard app)
    /customers/           → Customer management (customers app)
    /orders/              → Order history (orders app)
    /payments/            → Payment records (payments app)
    /credit/              → Credit profiles (credit app)
    /mongo-demo/          → MongoDB query showcase (mongo_demo app)
    /admin/               → Django admin (uses SQLite auth)
─────────────────────────────────────────────────────────────────────────────
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # ── Root redirect → dashboard ─────────────────────────────────────────────
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),

    # ── Django admin (SQLite auth) ────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Custom apps ───────────────────────────────────────────────────────────
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("customers/", include("customers.urls")),
    path("orders/",    include("orders.urls")),
    path("payments/",  include("payments.urls")),
    path("credit/",    include("credit.urls")),
    path("mongo-demo/", include("mongo_demo.urls")),
]
