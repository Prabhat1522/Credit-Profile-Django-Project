"""
accounts/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Handles admin login and logout.
    Uses Django's built-in authentication (SQLite) — NOT MongoDB.

WHY DJANGO AUTH FOR LOGIN?
    Django's auth system is battle-tested, handles password hashing,
    session management, and CSRF protection automatically.
    This keeps authentication separate and secure.

VIVA POINT:
    "Login and sessions use Django's built-in auth with SQLite.
    All business data (customers, orders, etc.) uses MongoDB via PyMongo.
    These two systems are deliberately kept separate."
─────────────────────────────────────────────────────────────────────────────
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def login_view(request):
    """
    Displays the login form on GET.
    Authenticates the user on POST using Django's auth system.
    On success: redirects to /dashboard/
    On failure: shows an error message and re-displays the form.
    """
    # If already logged in, go straight to dashboard
    if request.user.is_authenticated:
        return redirect("dashboard:index")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Django checks the username/password against SQLite auth tables
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)   # Creates a session in SQLite
            messages.success(request, f"Welcome back, {user.username}!")
            # If there was a 'next' parameter (e.g., from @login_required),
            # redirect there; otherwise go to dashboard
            next_url = request.GET.get("next", "/dashboard/")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, "accounts/login.html")


def logout_view(request):
    """
    Logs out the current user and redirects to the login page.
    Only processes POST requests to prevent accidental logout via GET.
    """
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect("accounts:login")
