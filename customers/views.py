"""
customers/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Controller views for Customer management.
    Handles listing, detail views, creation, updates, deletion, and CSV export.
    Protected with Django's @login_required decorator.
─────────────────────────────────────────────────────────────────────────────
"""

import csv
from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from pymongo.errors import DuplicateKeyError, WriteError

from customers import services as customer_services
from core.finance import get_customer_full_summary
from core.db_client import get_collection


@login_required
def customer_list(request):
    """
    Renders customer table with search, active status filter, and pagination.
    """
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "all")
    sort_by = request.GET.get("sort", "-account_created_at")
    page = int(request.GET.get("page", 1) or 1)

    is_active = None
    if status_filter == "active":
        is_active = True
    elif status_filter == "inactive":
        is_active = False

    data = customer_services.get_customers(
        q=q,
        is_active=is_active,
        sort_by=sort_by,
        page=page,
        per_page=10
    )

    # Attach live financial metrics to each displayed customer
    for c in data["customers"]:
        summary = get_customer_full_summary(c["customer_id"])
        c["total_orders"] = summary["total_orders"]
        c["total_spent"] = summary["total_spent"]
        c["outstanding_balance"] = summary["outstanding_balance"]
        c["overdue_count"] = summary["overdue_count"]

    context = {
        "page_title": "Customers",
        "customers": data["customers"],
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
        "page_range": data["page_range"],
        "q": q,
        "status_filter": status_filter,
        "sort_by": sort_by,
    }
    return render(request, "customers/list.html", context)


@login_required
def customer_detail(request, customer_id):
    """
    Shows full profile of a customer, including related orders, payments,
    and financial aggregations.
    """
    customer = customer_services.get_customer_by_id(customer_id)
    if not customer:
        messages.error(request, f"Customer '{customer_id}' was not found.")
        return redirect("customers:list")

    # Fetch orders and payments using raw PyMongo queries
    orders_col = get_collection("orders")
    payments_col = get_collection("payments")

    orders = list(orders_col.find({"customer_id": customer_id}).sort("order_date", -1))
    payments = list(payments_col.find({"customer_id": customer_id}).sort("due_date", -1))

    # Calculate financial aggregations
    finances = get_customer_full_summary(customer_id)

    context = {
        "page_title": f"Customer: {customer.get('full_name', customer_id)}",
        "customer": customer,
        "orders": orders,
        "payments": payments,
        "finances": finances,
    }
    return render(request, "customers/detail.html", context)


@login_required
def customer_create(request):
    """
    Creates a new customer.
    Handles MongoDB $jsonSchema validation errors and duplicate keys gracefully.
    """
    if request.method == "POST":
        post = request.POST
        form_data = {
            "full_name": post.get("full_name", "").strip(),
            "email": post.get("email", "").strip(),
            "phone": post.get("phone", "").strip(),
            "is_active": "is_active" in post,
            "kyc_verified": "kyc_verified" in post,
            "street": post.get("street", "").strip(),
            "city": post.get("city", "").strip(),
            "state": post.get("state", "").strip(),
            "pincode": post.get("pincode", "").strip(),
            "tags": post.get("tags", "").strip(),
            "date_of_birth": post.get("date_of_birth", "").strip() or None,
        }

        try:
            created = customer_services.create_customer(form_data)
            messages.success(request, f"Customer {created['customer_id']} ({created['full_name']}) created successfully!")
            return redirect("customers:detail", customer_id=created["customer_id"])
        except DuplicateKeyError:
            messages.error(request, "A customer with this email address or ID already exists.")
        except WriteError as we:
            messages.error(request, f"MongoDB validation error: {we.details.get('errmsg', str(we))}")
        except ValueError as ve:
            messages.error(request, str(ve))
        except Exception as e:
            messages.error(request, f"Failed to create customer: {str(e)}")

        return render(request, "customers/form.html", {
            "page_title": "Add New Customer",
            "form_data": form_data,
            "is_edit": False
        })

    return render(request, "customers/form.html", {
        "page_title": "Add New Customer",
        "form_data": {"is_active": True},
        "is_edit": False
    })


@login_required
def customer_update(request, customer_id):
    """
    Updates an existing customer profile.
    """
    customer = customer_services.get_customer_by_id(customer_id)
    if not customer:
        messages.error(request, f"Customer '{customer_id}' was not found.")
        return redirect("customers:list")

    if request.method == "POST":
        post = request.POST
        form_data = {
            "full_name": post.get("full_name", "").strip(),
            "email": post.get("email", "").strip(),
            "phone": post.get("phone", "").strip(),
            "is_active": "is_active" in post,
            "kyc_verified": "kyc_verified" in post,
            "street": post.get("street", "").strip(),
            "city": post.get("city", "").strip(),
            "state": post.get("state", "").strip(),
            "pincode": post.get("pincode", "").strip(),
            "tags": post.get("tags", "").strip(),
            "date_of_birth": post.get("date_of_birth", "").strip() or None,
        }

        try:
            customer_services.update_customer(customer_id, form_data)
            messages.success(request, f"Customer {customer_id} updated successfully!")
            return redirect("customers:detail", customer_id=customer_id)
        except DuplicateKeyError:
            messages.error(request, "Email address is already in use by another customer.")
        except WriteError as we:
            messages.error(request, f"MongoDB validation error: {we.details.get('errmsg', str(we))}")
        except ValueError as ve:
            messages.error(request, str(ve))
        except Exception as e:
            messages.error(request, f"Failed to update customer: {str(e)}")

    address = customer.get("address") or {}
    tags_str = ", ".join(customer.get("tags") or [])
    dob_str = ""
    if customer.get("date_of_birth"):
        dob_str = customer["date_of_birth"].strftime("%Y-%m-%d")

    form_data = {
        "customer_id": customer.get("customer_id"),
        "full_name": customer.get("full_name"),
        "email": customer.get("email"),
        "phone": customer.get("phone"),
        "is_active": customer.get("is_active", True),
        "kyc_verified": customer.get("kyc_verified", False),
        "street": address.get("street", ""),
        "city": address.get("city", ""),
        "state": address.get("state", ""),
        "pincode": address.get("pincode", ""),
        "tags": tags_str,
        "date_of_birth": dob_str,
    }

    return render(request, "customers/form.html", {
        "page_title": f"Edit Customer {customer_id}",
        "form_data": form_data,
        "customer_id": customer_id,
        "is_edit": True,
    })


@login_required
def customer_delete(request, customer_id):
    """
    Deletes customer document after confirmation.
    """
    customer = customer_services.get_customer_by_id(customer_id)
    if not customer:
        messages.error(request, f"Customer '{customer_id}' was not found.")
        return redirect("customers:list")

    if request.method == "POST":
        customer_services.delete_customer(customer_id)
        messages.success(request, f"Customer {customer_id} ({customer.get('full_name')}) was deleted.")
        return redirect("customers:list")

    # Calculate linked counts for safety warning
    orders_count = get_collection("orders").count_documents({"customer_id": customer_id})
    payments_count = get_collection("payments").count_documents({"customer_id": customer_id})

    context = {
        "page_title": f"Delete Customer {customer_id}",
        "customer": customer,
        "orders_count": orders_count,
        "payments_count": payments_count,
    }
    return render(request, "customers/confirm_delete.html", context)


@login_required
def customer_export_csv(request):
    """
    Exports customer list to a downloadable CSV file.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="customers_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Customer ID", "Full Name", "Email", "Phone",
        "Active", "KYC Verified", "City", "State",
        "Total Orders", "Total Spent", "Outstanding Balance", "Overdue Count"
    ])

    col = get_collection("customers")
    customers = list(col.find().sort("customer_id", 1))

    for c in customers:
        cid = c.get("customer_id")
        summary = get_customer_full_summary(cid)
        addr = c.get("address") or {}
        writer.writerow([
            cid,
            c.get("full_name", ""),
            c.get("email", ""),
            c.get("phone", ""),
            "Yes" if c.get("is_active") else "No",
            "Yes" if c.get("kyc_verified") else "No",
            addr.get("city", ""),
            addr.get("state", ""),
            summary["total_orders"],
            summary["total_spent"],
            summary["outstanding_balance"],
            summary["overdue_count"],
        ])

    return response
