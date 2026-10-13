"""
orders/views.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Controller views for Order management.
    Handles order listing, creation with multiple items, status updating,
    detailed viewing, deletion, and CSV export.
─────────────────────────────────────────────────────────────────────────────
"""

import csv
from datetime import datetime, timezone
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from orders import services as order_services
from customers import services as customer_services
from core.db_client import get_collection


@login_required
def order_list(request):
    """
    Renders list of orders with filters for status, customer, search, and pagination.
    """
    customer_id = request.GET.get("customer_id", "").strip()
    status = request.GET.get("status", "all")
    q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "-order_date")
    page = int(request.GET.get("page", 1) or 1)

    data = order_services.get_orders(
        customer_id=customer_id or None,
        status=status,
        q=q,
        page=page,
        per_page=10,
        sort_by=sort_by
    )

    customers_dropdown = customer_services.get_all_customers_dropdown()

    context = {
        "page_title": "Orders",
        "orders": data["orders"],
        "total": data["total"],
        "page": data["page"],
        "total_pages": data["total_pages"],
        "has_next": data["has_next"],
        "has_prev": data["has_prev"],
        "page_range": data["page_range"],
        "customer_id": customer_id,
        "status": status,
        "q": q,
        "sort_by": sort_by,
        "customers_dropdown": customers_dropdown,
    }
    return render(request, "orders/list.html", context)


@login_required
def order_detail(request, order_id):
    """
    Displays single order details, purchased items, customer info, and related payments.
    """
    order = order_services.get_order_by_id(order_id)
    if not order:
        messages.error(request, f"Order '{order_id}' was not found.")
        return redirect("orders:list")

    payments = list(get_collection("payments").find({"order_id": order_id}))

    context = {
        "page_title": f"Order {order_id}",
        "order": order,
        "payments": payments,
    }
    return render(request, "orders/detail.html", context)


@login_required
def order_create(request):
    """
    Creates a new order with dynamic line items.
    """
    customers = customer_services.get_all_customers_dropdown()
    prefill_customer_id = request.GET.get("customer_id", "")

    if request.method == "POST":
        post = request.POST
        customer_id = post.get("customer_id")
        status = post.get("status", "pending")
        notes = post.get("notes", "").strip()

        # Parse item rows from post data
        # product_names[], quantities[], unit_prices[]
        product_names = post.getlist("product_name[]")
        quantities = post.getlist("quantity[]")
        unit_prices = post.getlist("unit_price[]")

        items = []
        for i in range(len(product_names)):
            pname = product_names[i].strip()
            if not pname:
                continue
            try:
                qty = int(quantities[i])
                price = float(unit_prices[i])
                items.append({
                    "product_name": pname,
                    "quantity": qty,
                    "unit_price": price,
                })
            except (ValueError, IndexError):
                continue

        try:
            order_data = {
                "customer_id": customer_id,
                "status": status,
                "notes": notes,
                "items": items,
            }
            created = order_services.create_order(order_data, create_pending_payment=True)
            messages.success(request, f"Order {created['order_id']} created successfully!")
            return redirect("orders:detail", order_id=created["order_id"])
        except Exception as e:
            messages.error(request, f"Error creating order: {str(e)}")

    context = {
        "page_title": "Create New Order",
        "customers": customers,
        "prefill_customer_id": prefill_customer_id,
    }
    return render(request, "orders/form.html", context)


@login_required
def order_update(request, order_id):
    """
    Updates order status and notes.
    """
    order = order_services.get_order_by_id(order_id)
    if not order:
        messages.error(request, f"Order '{order_id}' was not found.")
        return redirect("orders:list")

    if request.method == "POST":
        new_status = request.POST.get("status")
        notes = request.POST.get("notes", "").strip()
        try:
            order_services.update_order_status(order_id, new_status, notes)
            messages.success(request, f"Order {order_id} updated successfully.")
            return redirect("orders:detail", order_id=order_id)
        except Exception as e:
            messages.error(request, f"Failed to update order: {str(e)}")

    context = {
        "page_title": f"Update Order {order_id}",
        "order": order,
    }
    return render(request, "orders/edit.html", context)


@login_required
def order_delete(request, order_id):
    """
    Deletes an order record.
    """
    order = order_services.get_order_by_id(order_id)
    if not order:
        messages.error(request, f"Order '{order_id}' was not found.")
        return redirect("orders:list")

    if request.method == "POST":
        order_services.delete_order(order_id)
        messages.success(request, f"Order {order_id} was deleted.")
        return redirect("orders:list")

    return render(request, "orders/confirm_delete.html", {"order": order})


@login_required
def order_export_csv(request):
    """
    Exports order records to CSV.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'

    writer = csv.writer(response)
    writer.writerow(["Order ID", "Customer ID", "Order Date", "Item Count", "Total Amount", "Status", "Notes"])

    orders = list(get_collection("orders").find().sort("order_date", -1))
    for o in orders:
        odate = o.get("order_date")
        odate_str = odate.strftime("%Y-%m-%d %H:%M") if hasattr(odate, "strftime") else str(odate)
        writer.writerow([
            o.get("order_id"),
            o.get("customer_id"),
            odate_str,
            len(o.get("items", [])),
            o.get("total_amount", 0.0),
            o.get("status"),
            o.get("notes", "")
        ])

    return response
