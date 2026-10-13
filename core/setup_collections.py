"""
core/setup_collections.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    One-time (but idempotent) setup script that:
    1. Creates all MongoDB collections if they don't already exist
    2. Applies $jsonSchema validators to customers, payments, and orders
    3. Creates indexes for performance and uniqueness
    4. Creates the 'counters' collection for atomic ID generation

HOW TO RUN:
    python core/setup_collections.py

IDEMPOTENT = SAFE TO RUN MULTIPLE TIMES:
    - Collections that already exist are NOT recreated or cleared
    - Validators are applied via collMod — updates existing collections
    - Indexes are created with create_index — skipped if already exist

VIVA POINTS:
    - "We apply $jsonSchema at the database level. MongoDB enforces these
      rules even if our Python code has a bug."
    - "Indexes on customer_id, order_id, and payment_id speed up lookups.
      Unique indexes on customer_id and email enforce data integrity."
    - "The counters collection provides atomic ID sequences. Each counter
      document has a name (_id) and a seq (integer)."
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os

# Allow running as a standalone script from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.db_client import get_db, close_connection
from core.validators import CUSTOMERS_VALIDATOR, PAYMENTS_VALIDATOR, ORDERS_VALIDATOR
from pymongo.errors import CollectionInvalid, OperationFailure


# ── Collection definitions ────────────────────────────────────────────────────
# Maps collection name → validator (None = no $jsonSchema validator)
COLLECTIONS = {
    "customers":       CUSTOMERS_VALIDATOR,
    "orders":          ORDERS_VALIDATOR,      # Phase 2: added orders validator
    "payments":        PAYMENTS_VALIDATOR,
    "credit_profiles": None,
    "risk_alerts":     None,
    "counters":        None,                  # Phase 2: atomic ID counters
}


def create_collection_if_not_exists(db, name: str) -> bool:
    existing = db.list_collection_names()
    if name in existing:
        print(f"  ℹ️  Collection '{name}' already exists — skipping creation.")
        return False
    db.create_collection(name)
    print(f"  ✅ Created collection '{name}'.")
    return True


def apply_validator(db, name: str, validator: dict):
    """
    Applies a $jsonSchema validator to an existing collection via collMod.

    validationLevel: "moderate" — only validates new inserts and updates
                     to documents that already match the schema.
    validationAction: "error" — rejects the write if validation fails.
    """
    try:
        db.command({
            "collMod": name,
            "validator": validator,
            "validationLevel": "moderate",
            "validationAction": "error"
        })
        print(f"  ✅ Applied $jsonSchema validator to '{name}'.")
    except OperationFailure as e:
        print(f"  ❌ Failed to apply validator to '{name}': {e}")


def _safe_index(collection, keys, **kwargs):
    """Creates an index, skipping gracefully if it already exists with a different name."""
    from pymongo.errors import OperationFailure as OpFail
    try:
        collection.create_index(keys, **kwargs)
    except OpFail as e:
        if "already exists" in str(e):
            print(f"    (index on {keys} already exists — skipping)")
        else:
            raise


def create_indexes(db):
    """
    Creates all indexes. Idempotent — existing indexes are not recreated.

    VIVA: "unique=True means MongoDB rejects duplicate values for that field.
    This is a second layer of protection beyond Python-level checks."
    """
    print("\n[Step 3] Creating indexes...")

    # ── customers ────────────────────────────────────────────────────────────
    _safe_index(db["customers"], "customer_id",        unique=True,  name="idx_customer_id_unique")
    _safe_index(db["customers"], "email",              unique=True,  name="idx_customer_email_unique")
    _safe_index(db["customers"], "is_active",                        name="idx_customer_is_active")
    _safe_index(db["customers"], "account_created_at",               name="idx_customer_created_at")
    print("  [OK] customers: unique(customer_id), unique(email), is_active, account_created_at")

    # ── orders ───────────────────────────────────────────────────────────────
    _safe_index(db["orders"], "order_id",    unique=True, name="idx_order_id_unique")
    _safe_index(db["orders"], "customer_id",              name="idx_order_customer_id")
    _safe_index(db["orders"], "status",                   name="idx_order_status")
    _safe_index(db["orders"], "order_date",               name="idx_order_date")
    print("  [OK] orders: unique(order_id), customer_id, status, order_date")

    # ── payments ─────────────────────────────────────────────────────────────
    _safe_index(db["payments"], "payment_id",  unique=True, name="idx_payment_id_unique")
    _safe_index(db["payments"], "customer_id",              name="idx_payment_customer_id")
    _safe_index(db["payments"], "order_id",                 name="idx_payment_order_id")
    _safe_index(db["payments"], "is_overdue",               name="idx_payment_is_overdue")
    _safe_index(db["payments"], "due_date",                 name="idx_payment_due_date")
    print("  [OK] payments: unique(payment_id), customer_id, order_id, is_overdue, due_date")

    # ── credit_profiles ───────────────────────────────────────────────────────
    _safe_index(db["credit_profiles"], "customer_id", unique=True, name="idx_credit_customer_id")
    print("  [OK] credit_profiles: unique(customer_id)")

    # ── risk_alerts ───────────────────────────────────────────────────────────
    _safe_index(db["risk_alerts"], "customer_id", name="idx_alerts_customer_id")
    _safe_index(db["risk_alerts"], "resolved",    name="idx_alerts_resolved")
    print("  [OK] risk_alerts: customer_id, resolved")


def run_setup():
    print("=" * 60)
    print("  Credit Profile System — MongoDB Collection Setup")
    print("=" * 60)

    try:
        db = get_db()
        print(f"\n[Connected] Database: '{db.name}'\n")

        print("[Step 1] Creating collections...")
        for col_name in COLLECTIONS:
            create_collection_if_not_exists(db, col_name)

        print("\n[Step 2] Applying $jsonSchema validators...")
        for col_name, validator in COLLECTIONS.items():
            if validator is not None:
                apply_validator(db, col_name, validator)
            else:
                print(f"  ℹ️  No validator for '{col_name}' — skipping.")

        create_indexes(db)

        print("\n" + "=" * 60)
        print("  ✅ Setup complete! All collections, validators, and indexes ready.")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Setup failed:\n{e}")
        sys.exit(1)
    finally:
        close_connection()


if __name__ == "__main__":
    run_setup()
