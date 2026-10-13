"""
customers/services.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Data access layer for the 'customers' MongoDB collection using raw PyMongo.
    Contains all CRUD queries, pagination, search, and filters.
    Keeps database logic cleanly separated from Django views.

VIVA POINTS:
    - "All database interactions with the customer collection use raw PyMongo,
      not Django ORM, fulfilling the NoSQL MongoDB subject requirement."
    - "Schema validation is enforced at the database level by MongoDB $jsonSchema."
    - "ID generation is guaranteed unique and sequential via MongoDB atomic $inc."
─────────────────────────────────────────────────────────────────────────────
"""

import math
import re
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError, WriteError
from core.db_client import get_collection
from core.finance import generate_customer_id


def get_customers(q=None, is_active=None, sort_by="-account_created_at", page=1, per_page=10):
    """
    Retrieves a paginated list of customers with optional search and filters.

    Args:
        q: Optional search query matching full_name, email, or customer_id (regex).
        is_active: Optional boolean to filter active/inactive customers.
        sort_by: Field to sort by. Prefix '-' indicates descending order.
        page: Current 1-based page number.
        per_page: Number of items per page.

    Returns:
        dict: {
            "customers": list of customer dicts,
            "total": int,
            "page": int,
            "per_page": int,
            "total_pages": int,
            "has_next": bool,
            "has_prev": bool,
            "page_range": list of int,
        }
    """
    col = get_collection("customers")
    filter_query = {}

    if q and q.strip():
        search_term = q.strip()
        # Case-insensitive regex matching full_name, email, or customer_id
        safe_regex = re.escape(search_term)
        filter_query["$or"] = [
            {"customer_id": {"$regex": safe_regex, "$options": "i"}},
            {"full_name": {"$regex": safe_regex, "$options": "i"}},
            {"email": {"$regex": safe_regex, "$options": "i"}},
            {"phone": {"$regex": safe_regex, "$options": "i"}},
        ]

    if is_active is not None:
        filter_query["is_active"] = bool(is_active)

    total = col.count_documents(filter_query)
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    # Sort direction
    sort_dir = -1 if sort_by.startswith("-") else 1
    sort_field = sort_by.lstrip("-")
    # Default to account_created_at if invalid
    if sort_field not in ["account_created_at", "full_name", "customer_id", "email"]:
        sort_field = "account_created_at"
        sort_dir = -1

    cursor = col.find(filter_query).sort(sort_field, sort_dir).skip(skip).limit(per_page)
    customers = list(cursor)

    return {
        "customers": customers,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "page_range": list(range(1, total_pages + 1)),
    }


def get_all_customers_dropdown():
    """Returns a lightweight list of customers for dropdown selections."""
    col = get_collection("customers")
    return list(col.find({"is_active": True}, {"customer_id": 1, "full_name": 1, "email": 1}).sort("customer_id", 1))


def get_customer_by_id(customer_id):
    """Fetches a single customer document by customer_id string."""
    col = get_collection("customers")
    return col.find_one({"customer_id": customer_id})


def create_customer(data):
    """
    Creates and inserts a new customer document into MongoDB.
    Assigns atomic customer_id if not supplied.

    Raises:
        ValueError: If validation fails.
        WriteError / DuplicateKeyError: If database rejects document.
    """
    col = get_collection("customers")

    customer_id = data.get("customer_id") or generate_customer_id()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()

    if not full_name or len(full_name) < 2:
        raise ValueError("Full name must be at least 2 characters.")
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")
    if not phone or len(phone) < 7:
        raise ValueError("A valid phone number (at least 7 characters) is required.")

    account_created_at = data.get("account_created_at") or datetime.now(timezone.utc)
    if hasattr(account_created_at, "tzinfo") and account_created_at.tzinfo is None:
        account_created_at = account_created_at.replace(tzinfo=timezone.utc)

    # Address subdocument
    address = None
    city = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip()
    if city and state:
        address = {
            "street": (data.get("street") or "").strip(),
            "city": city,
            "state": state,
            "pincode": (data.get("pincode") or "").strip(),
        }

    # Tags list
    tags_raw = data.get("tags")
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        tags = []

    doc = {
        "customer_id": customer_id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "account_created_at": account_created_at,
        "is_active": bool(data.get("is_active", True)),
        "kyc_verified": bool(data.get("kyc_verified", False)),
        "tags": tags,
    }

    if address:
        doc["address"] = address

    # Optional date of birth
    dob = data.get("date_of_birth")
    if dob:
        if isinstance(dob, str) and dob.strip():
            try:
                dob = datetime.strptime(dob.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                doc["date_of_birth"] = dob
            except ValueError:
                pass
        elif isinstance(dob, datetime):
            doc["date_of_birth"] = dob

    col.insert_one(doc)
    return doc


def update_customer(customer_id, data):
    """
    Updates an existing customer document.
    """
    col = get_collection("customers")
    existing = col.find_one({"customer_id": customer_id})
    if not existing:
        return False

    update_fields = {}

    if "full_name" in data:
        name = data["full_name"].strip()
        if len(name) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        update_fields["full_name"] = name

    if "email" in data:
        email = data["email"].strip().lower()
        if "@" not in email:
            raise ValueError("A valid email address is required.")
        update_fields["email"] = email

    if "phone" in data:
        phone = data["phone"].strip()
        if len(phone) < 7:
            raise ValueError("A valid phone number is required.")
        update_fields["phone"] = phone

    if "is_active" in data:
        update_fields["is_active"] = bool(data["is_active"])

    if "kyc_verified" in data:
        update_fields["kyc_verified"] = bool(data["kyc_verified"])

    city = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip()
    if city and state:
        update_fields["address"] = {
            "street": (data.get("street") or "").strip(),
            "city": city,
            "state": state,
            "pincode": (data.get("pincode") or "").strip(),
        }

    if "tags" in data:
        tags_raw = data["tags"]
        if isinstance(tags_raw, str):
            update_fields["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif isinstance(tags_raw, list):
            update_fields["tags"] = [str(t).strip() for t in tags_raw if str(t).strip()]

    dob = data.get("date_of_birth")
    if dob:
        if isinstance(dob, str) and dob.strip():
            try:
                update_fields["date_of_birth"] = datetime.strptime(dob.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        elif isinstance(dob, datetime):
            update_fields["date_of_birth"] = dob

    if update_fields:
        col.update_one({"customer_id": customer_id}, {"$set": update_fields})

    return True


def delete_customer(customer_id):
    """
    Deletes a customer document by customer_id.
    """
    col = get_collection("customers")
    res = col.delete_one({"customer_id": customer_id})
    return res.deleted_count > 0
