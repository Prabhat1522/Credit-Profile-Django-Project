"""
core/db_client.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Central MongoDB connection module. All other apps import collection
    references from here — no app creates its own MongoClient.

WHY A SINGLETON?
    Creating a MongoClient on every web request is slow and wastes connections.
    A singleton creates the connection once when the server starts and reuses it.

VIVA POINT:
    "PyMongo's MongoClient manages a connection pool. We import db_client
    in every app's services.py to get the correct collection and run queries."

USAGE (in any services.py):
    from core.db_client import get_collection
    customers_col = get_collection("customers")
    result = customers_col.find_one({"customer_id": "CUST-001"})
─────────────────────────────────────────────────────────────────────────────
"""

import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from dotenv import load_dotenv

# Load environment variables from .env file
# This must be called before os.environ.get() reads MONGODB_URI
load_dotenv()

# ── Module-level variables (the singleton) ────────────────────────────────────
_client = None   # MongoClient instance (created once)
_db = None       # Database handle (created once)


def get_client() -> MongoClient:
    """
    Returns the MongoClient singleton.
    Creates it on the first call; returns the existing one on all subsequent calls.

    Raises:
        EnvironmentError: If MONGODB_URI is not set in .env
        ConnectionFailure: If MongoDB Atlas cannot be reached
    """
    global _client

    if _client is None:
        # Read URI from environment — NEVER hardcode credentials here
        uri = os.environ.get("MONGODB_URI")

        if not uri:
            raise EnvironmentError(
                "\n\n[DB ERROR] MONGODB_URI is not set.\n"
                "Steps to fix:\n"
                "  1. Copy .env.example to .env\n"
                "  2. Fill in your MongoDB Atlas connection string\n"
                "  3. Restart the Django server\n"
            )

        try:
            # serverSelectionTimeoutMS: how long to wait before giving up
            # (5 seconds is enough for Atlas; increase if on slow internet)
            _client = MongoClient(uri, serverSelectionTimeoutMS=5000)

            # Force a connection attempt now — don't wait for the first query
            # This surfaces connection errors at startup, not mid-request
            _client.admin.command("ping")
            print("[DB] [OK] Connected to MongoDB Atlas successfully.")

        except ConnectionFailure as e:
            _client = None  # Reset so the next request tries again
            raise ConnectionFailure(
                f"\n\n[DB ERROR] Cannot connect to MongoDB Atlas.\n"
                f"Check:\n"
                f"  1. Your MONGODB_URI in .env is correct\n"
                f"  2. Your IP is whitelisted in Atlas Network Access\n"
                f"  3. Your username and password are correct\n"
                f"  4. Your internet connection is active\n\n"
                f"Original error: {e}"
            )
        except ConfigurationError as e:
            _client = None
            raise ConfigurationError(
                f"\n\n[DB ERROR] Invalid MongoDB URI format.\n"
                f"Your URI should look like:\n"
                f"  mongodb+srv://username:password@cluster.mongodb.net/credit_profile\n\n"
                f"Original error: {e}"
            )

    return _client


def get_db():
    """
    Returns the database handle.
    The database name is read from MONGODB_DB_NAME in .env
    (defaults to 'credit_profile' if not set).
    """
    global _db

    if _db is None:
        db_name = os.environ.get("MONGODB_DB_NAME", "credit_profile")
        _db = get_client()[db_name]

    return _db


def get_collection(collection_name: str):
    """
    Returns a reference to a specific MongoDB collection.

    This is the main function used throughout the project.
    Every app's services.py calls this to get a collection handle.

    Args:
        collection_name: Name of the MongoDB collection
                         e.g. "customers", "orders", "payments"

    Returns:
        pymongo.collection.Collection

    Example:
        col = get_collection("customers")
        doc = col.find_one({"customer_id": "CUST-001"})
    """
    return get_db()[collection_name]


def close_connection():
    """
    Closes the MongoDB connection.
    Useful in management commands and scripts that run and exit.
    Django's web server keeps it open for the lifetime of the process.
    """
    global _client, _db

    if _client is not None:
        _client.close()
        _client = None
        _db = None
        print("[DB] MongoDB connection closed.")
