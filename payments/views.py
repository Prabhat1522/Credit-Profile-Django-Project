"""
payments/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Controller views for Payment Management.
    Handles listing, detailed breakdown, adding invoices, recording payments
    (partial or full), deletion, and CSV export.
─────────────────────────────────────────────────────────────────────────────
"""

import csv
from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from payments import services as payment_services
from customers import services as customer_services
from core.db_client import get_collection


@login_required
def payment_list(request):
    """
    Renders table of payments with filters for status, overdue, customer, and search.
    """
    customer_id = request.GET.get("customer_id", "").strip()
    status = request.GET.get("status", "all")
    is_overdue = None
    if request.GET.get("overdue") == "true":
        is_overdue = True

    q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "-due_date")
    page = int(request.GET.get("page", 1) or 1)

    data = payment_services.get_payments(
        customer_id=customer_id or None,
        status=status,
        is_overdue=is_overdue,
        q=q,
        page=page,
        per_page=10,
        sort_by=sort_by
    )

    customers_dropdown = customer_services.get_all_customers_dropdown()

    context = {
        "page_title": "Payments",
        "payments": data["payments"],
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
        "page_range": data["page_range"],
        "customer_id": customer_id,
        "status": status,
        "is_overdue": request.GET.get("overdue", ""),
        "q": q,
        "sort_by": sort_by,
        "customers_dropdown": customers_dropdown,
    }
    return render(request, "payments/list.html", context)


@login_required
def payment_detail(request, payment_id):
    """
    Shows single payment record details, linked customer, order, and payment history.
    """
    payment = payment_services.get_payment_by_id(payment_id)
    if not payment:
        messages.error(request, f"Payment '{payment_id}' was not found.")
        return redirect("payments:list")

    context = {
        "page_title": f"Payment {payment_id}",
        "payment": payment,
    }
    return render(request, "payments/detail.html", context)


@login_required
def payment_create(request):
    """
    Creates a new payment invoice record.
    """
    customers = customer_services.get_all_customers_dropdown()
    prefill_customer_id = request.GET.get("customer_id", "")
    prefill_order_id = request.GET.get("order_id", "")
    prefill_amount = request.GET.get("amount", "")

    if request.method == "POST":
        post = request.POST
        try:
            form_data = {
                "customer_id": post.get("customer_id", "").strip(),
                "order_id": post.get("order_id", "").strip(),
                "amount_due": float(post.get("amount_due", 0.0)),
                "amount_paid": float(post.get("amount_paid", 0.0)),
                "payment_mode": post.get("payment_mode", "UPI"),
                "due_date": post.get("due_date", "").strip() or None,
            }
            created = payment_services.create_payment(form_data)
            messages.success(request, f"Payment record {created['payment_id']} created successfully!")
            return redirect("payments:detail", payment_id=created["payment_id"])
        except Exception as e:
            messages.error(request, f"Error creating payment: {str(e)}")

    context = {
        "page_title": "Create Payment Record",
        "customers": customers,
        "prefill_customer_id": prefill_customer_id,
        "prefill_order_id": prefill_order_id,
        "prefill_amount": prefill_amount,
    }
    return render(request, "payments/form.html", context)


@login_required
def payment_record_pay(request, payment_id):
    """
    Processes a payment transaction against an outstanding payment (partial or full).
    """
    payment = payment_services.get_payment_by_id(payment_id)
    if not payment:
        messages.error(request, f"Payment '{payment_id}' was not found.")
        return redirect("payments:list")

    if request.method == "POST":
        try:
            amount = float(request.POST.get("amount", 0.0))
            mode = request.POST.get("payment_mode", "UPI")
            payment_services.record_transaction(payment_id, amount, mode)
            messages.success(request, f"Successfully recorded payment of ₹{amount:.2f} for {payment_id}!")
            return redirect("payments:detail", payment_id=payment_id)
        except Exception as e:
            messages.error(request, f"Failed to record transaction: {str(e)}")

    context = {
        "page_title": f"Record Payment for {payment_id}",
        "payment": payment,
    }
    return render(request, "payments/record_pay.html", context)


@login_required
def payment_delete(request, payment_id):
    """
    Deletes payment record.
    """
    payment = payment_services.get_payment_by_id(payment_id)
    if not payment:
        messages.error(request, f"Payment '{payment_id}' was not found.")
        return redirect("payments:list")

    if request.method == "POST":
        payment_services.delete_payment(payment_id)
        messages.success(request, f"Payment {payment_id} was deleted.")
        return redirect("payments:list")

    return render(request, "payments/confirm_delete.html", {"payment": payment})


@login_required
def payment_export_csv(request):
    """
    Exports payment records to CSV.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payments_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Payment ID", "Order ID", "Customer ID", "Due Date",
        "Amount Due", "Amount Paid", "Status", "Overdue", "Days Overdue", "Payment Mode"
    ])

    payments = list(get_collection("payments").find().sort("due_date", -1))
    for p in payments:
        ddate = p.get("due_date")
        ddate_str = ddate.strftime("%Y-%m-%d") if hasattr(ddate, "strftime") else str(ddate or "")
        writer.writerow([
            p.get("payment_id"),
            p.get("order_id"),
            p.get("customer_id"),
            ddate_str,
            p.get("amount_due", 0.0),
            p.get("amount_paid", 0.0),
            p.get("status"),
            "Yes" if p.get("is_overdue") else "No",
            p.get("days_overdue", 0),
            p.get("payment_mode", "")
        ])

    return response
