"""
credit_profile/settings.py
─────────────────────────────────────────────────────────────────────────────
Django settings for the Credit Profile System.

DUAL DATABASE DESIGN:
─────────────────────────────────────────────────────────────────────────────
  SQLite  ──► Django's own tables only: auth_user, sessions, admin log, etc.
              Django manages this automatically. You never write to it directly.

  MongoDB ──► All application data: customers, orders, payments, credit
              profiles, risk_alerts.
              Accessed only through PyMongo in core/db_client.py.
              Django has NO knowledge of MongoDB — it is managed separately.

This is a standard pattern when using Django with a NoSQL database.
─────────────────────────────────────────────────────────────────────────────
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file FIRST before reading any os.environ values ─────────────────
# python-dotenv reads .env and puts values into os.environ
# This must happen before any os.environ.get() calls below
load_dotenv()

# ── Base directory ─────────────────────────────────────────────────────────────
# Path(__file__) = .../credit_profile/settings.py
# .parent        = .../credit_profile/
# .parent.parent = .../ (project root, where manage.py lives)
BASE_DIR = Path(__file__).resolve().parent.parent


# ════════════════════════════════════════════════════════════════════════════════
#  SECURITY SETTINGS  (read from .env — never hardcoded)
# ════════════════════════════════════════════════════════════════════════════════

# Django's secret key — used for signing cookies, CSRF tokens, sessions
# MUST be kept secret. Read from .env.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-fallback-key-change-this-in-production"
)

# Debug mode — shows detailed errors in the browser
# MUST be False in production. Read from .env.
DEBUG = os.environ.get("DEBUG", "True") == "True"

# Hosts that are allowed to serve this application
# Read as comma-separated string from .env, split into a list
_allowed = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]


# ════════════════════════════════════════════════════════════════════════════════
#  INSTALLED APPS
# ════════════════════════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    # ── Django built-in apps ──────────────────────────────────────────────────
    "django.contrib.admin",         # Django admin site (uses SQLite auth)
    "django.contrib.auth",          # Authentication framework (SQLite)
    "django.contrib.contenttypes",  # Content type system (SQLite)
    "django.contrib.sessions",      # Session framework (SQLite)
    "django.contrib.messages",      # Messaging framework (flash messages)
    "django.contrib.staticfiles",   # Static file serving

    # ── Our custom Django apps ────────────────────────────────────────────────
    # Each app handles one area of the application.
    # Their views.py use PyMongo (core.db_client) for all MongoDB operations.
    "accounts",     # Admin login/logout — uses Django auth (SQLite)
    "customers",    # Customer profile management — data in MongoDB
    "orders",       # Order and purchase history — data in MongoDB
    "payments",     # Payment history and dues — data in MongoDB
    "credit",       # Credit profile generation and scoring — data in MongoDB
    "dashboard",    # Analytics dashboard with charts — reads from MongoDB
    "mongo_demo",   # MongoDB query showcase page — for viva demonstration
]


# ════════════════════════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ════════════════════════════════════════════════════════════════════════════════

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ════════════════════════════════════════════════════════════════════════════════
#  URL CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

ROOT_URLCONF = "credit_profile.urls"


# ════════════════════════════════════════════════════════════════════════════════
#  TEMPLATES
# ════════════════════════════════════════════════════════════════════════════════

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Global templates directory — shared base layouts live here
        "DIRS": [BASE_DIR / "templates"],
        # Also look inside each app's templates/ folder
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "credit_profile.wsgi.application"


# ════════════════════════════════════════════════════════════════════════════════
#  DATABASES — DUAL SETUP
# ════════════════════════════════════════════════════════════════════════════════

# SQLite is used ONLY for Django's internal tables (auth, sessions, admin).
# ALL application data goes to MongoDB via PyMongo (core/db_client.py).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# MongoDB connection settings are consumed by core/db_client.py
# They are NOT used here — this is just documentation for settings.py readers.
# MONGODB_URI     → read in core/db_client.py from os.environ
# MONGODB_DB_NAME → read in core/db_client.py from os.environ


# ════════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION
# ════════════════════════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Where to redirect after login/logout
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"


# ════════════════════════════════════════════════════════════════════════════════
#  INTERNATIONALIZATION
# ════════════════════════════════════════════════════════════════════════════════

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"   # IST — appropriate for Indian e-commerce context
USE_I18N = True
USE_TZ = True


# ════════════════════════════════════════════════════════════════════════════════
#  STATIC FILES (CSS, JavaScript)
# ════════════════════════════════════════════════════════════════════════════════

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # Our custom static files
# STATIC_ROOT is used when running collectstatic for production — not needed now

# Default primary key type for Django models (SQLite auth tables only)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
