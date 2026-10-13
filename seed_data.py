"""
seed_data.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Populates MongoDB Atlas with 15 realistic e-commerce customer profiles,
    diverse orders, and payment records demonstrating all required business
    scenarios for academic evaluation and viva demonstration:
      1. Perfect on-time payers (CUST-001, CUST-002, CUST-006, CUST-013)
      2. Partial payers (CUST-004, CUST-010)
      3. Overdue / Defaulters (CUST-005, CUST-011, CUST-015)
      4. Cancelled & Returned orders (CUST-008, CUST-009)
      5. New accounts with pending dues (CUST-007)
      6. Varied payment methods: UPI, Card, COD, EMI, Wallet

VIVA DEMONSTRATION POINTS:
    - "Schema compliance: Every seeded document strictly conforms to the
      MongoDB $jsonSchema validators."
    - "ID Generation counters: The counters collection is seeded to avoid
      ID collisions when users create records in the web UI."
    - "Idempotent: Can be run multiple times safely."
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.db_client import get_collection
from core.finance import seed_counter, compute_overdue_status, derive_payment_status


def seed_database():
    print("=" * 60)
    print("  Credit Profile System — Seeding Phase 2 Demonstration Data")
    print("=" * 60)

    now = datetime.now(timezone.utc)

    # 1. Customers Dataset (15 diverse customers)
    customers_data = [
        {
            "customer_id": "CUST-001",
            "full_name": "Rajesh Kumar",
            "email": "rajesh.kumar@example.com",
            "phone": "+91 9820112233",
            "account_created_at": now - timedelta(days=320),
            "date_of_birth": datetime(1988, 5, 14, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "42 Marine Drive", "city": "Mumbai", "state": "Maharashtra", "pincode": "400020"},
            "tags": ["premium", "electronics", "prompt-payer"],
        },
        {
            "customer_id": "CUST-002",
            "full_name": "Priya Sharma",
            "email": "priya.sharma@example.com",
            "phone": "+91 9811223344",
            "account_created_at": now - timedelta(days=280),
            "date_of_birth": datetime(1993, 11, 23, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "15 Connaught Place", "city": "New Delhi", "state": "Delhi", "pincode": "110001"},
            "tags": ["fashion", "frequent", "verified"],
        },
        {
            "customer_id": "CUST-003",
            "full_name": "Amit Patel",
            "email": "amit.patel@example.com",
            "phone": "+91 9879112233",
            "account_created_at": now - timedelta(days=190),
            "date_of_birth": datetime(1985, 2, 8, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "88 CG Road", "city": "Ahmedabad", "state": "Gujarat", "pincode": "380009"},
            "tags": ["appliances", "standard"],
        },
        {
            "customer_id": "CUST-004",
            "full_name": "Sneha Reddy",
            "email": "sneha.reddy@example.com",
            "phone": "+91 9848112233",
            "account_created_at": now - timedelta(days=240),
            "date_of_birth": datetime(1996, 7, 19, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": False,
            "address": {"street": "24 Jubilee Hills", "city": "Hyderabad", "state": "Telangana", "pincode": "500033"},
            "tags": ["books", "partial-payer"],
        },
        {
            "customer_id": "CUST-005",
            "full_name": "Vikram Singh",
            "email": "vikram.singh@example.com",
            "phone": "+91 9829112233",
            "account_created_at": now - timedelta(days=150),
            "date_of_birth": datetime(1990, 9, 30, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "12 MI Road", "city": "Jaipur", "state": "Rajasthan", "pincode": "302001"},
            "tags": ["furniture", "overdue-risk"],
        },
        {
            "customer_id": "CUST-006",
            "full_name": "Ananya Iyer",
            "email": "ananya.iyer@example.com",
            "phone": "+91 9880112233",
            "account_created_at": now - timedelta(days=365),
            "date_of_birth": datetime(1994, 4, 12, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "57 Indiranagar 100ft Rd", "city": "Bengaluru", "state": "Karnataka", "pincode": "560038"},
            "tags": ["premium", "electronics", "vip"],
        },
        {
            "customer_id": "CUST-007",
            "full_name": "Rohit Verma",
            "email": "rohit.verma@example.com",
            "phone": "+91 9415112233",
            "account_created_at": now - timedelta(days=25),
            "date_of_birth": datetime(1998, 1, 15, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": False,
            "address": {"street": "10 Hazratganj", "city": "Lucknow", "state": "Uttar Pradesh", "pincode": "226001"},
            "tags": ["new-user", "pending-first-payment"],
        },
        {
            "customer_id": "CUST-008",
            "full_name": "Pooja Nair",
            "email": "pooja.nair@example.com",
            "phone": "+91 9447112233",
            "account_created_at": now - timedelta(days=210),
            "date_of_birth": datetime(1992, 12, 5, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "7 MG Road", "city": "Kochi", "state": "Kerala", "pincode": "682016"},
            "tags": ["fashion", "returns-history"],
        },
        {
            "customer_id": "CUST-009",
            "full_name": "Manish Gupta",
            "email": "manish.gupta@example.com",
            "phone": "+91 9830112233",
            "account_created_at": now - timedelta(days=120),
            "date_of_birth": datetime(1989, 8, 18, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": False,
            "address": {"street": "33 Park Street", "city": "Kolkata", "state": "West Bengal", "pincode": "700016"},
            "tags": ["cancelled-orders"],
        },
        {
            "customer_id": "CUST-010",
            "full_name": "Kavita Joshi",
            "email": "kavita.joshi@example.com",
            "phone": "+91 9850112233",
            "account_created_at": now - timedelta(days=175),
            "date_of_birth": datetime(1995, 3, 27, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "9 FC Road", "city": "Pune", "state": "Maharashtra", "pincode": "411004"},
            "tags": ["emi-shopper"],
        },
        {
            "customer_id": "CUST-011",
            "full_name": "Suresh Raina",
            "email": "suresh.raina@example.com",
            "phone": "+91 9840112233",
            "account_created_at": now - timedelta(days=260),
            "date_of_birth": datetime(1986, 11, 27, tzinfo=timezone.utc),
            "is_active": False,
            "kyc_verified": False,
            "address": {"street": "14 Anna Salai", "city": "Chennai", "state": "Tamil Nadu", "pincode": "600002"},
            "tags": ["high-risk", "severe-default"],
        },
        {
            "customer_id": "CUST-012",
            "full_name": "Deepa Menon",
            "email": "deepa.menon@example.com",
            "phone": "+91 9446112233",
            "account_created_at": now - timedelta(days=90),
            "date_of_birth": datetime(1991, 6, 10, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "21 Statue Junction", "city": "Thiruvananthapuram", "state": "Kerala", "pincode": "695001"},
            "tags": ["cod-buyer"],
        },
        {
            "customer_id": "CUST-013",
            "full_name": "Arjun Mehta",
            "email": "arjun.mehta@example.com",
            "phone": "+91 9825112233",
            "account_created_at": now - timedelta(days=310),
            "date_of_birth": datetime(1984, 10, 14, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "77 Ring Road", "city": "Surat", "state": "Gujarat", "pincode": "395002"},
            "tags": ["bulk-buyer", "high-credit"],
        },
        {
            "customer_id": "CUST-014",
            "full_name": "Ritu Agarwal",
            "email": "ritu.agarwal@example.com",
            "phone": "+91 9425112233",
            "account_created_at": now - timedelta(days=140),
            "date_of_birth": datetime(1997, 8, 22, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": True,
            "address": {"street": "18 AB Road", "city": "Indore", "state": "Madhya Pradesh", "pincode": "452001"},
            "tags": ["wallet-user", "active"],
        },
        {
            "customer_id": "CUST-015",
            "full_name": "Tarun Malhotra",
            "email": "tarun.malhotra@example.com",
            "phone": "+91 9814112233",
            "account_created_at": now - timedelta(days=200),
            "date_of_birth": datetime(1990, 7, 3, tzinfo=timezone.utc),
            "is_active": True,
            "kyc_verified": False,
            "address": {"street": "5 Sector 17", "city": "Chandigarh", "state": "Punjab", "pincode": "160017"},
            "tags": ["late-payer"],
        },
    ]

    # Insert / Upsert Customers
    cust_col = get_collection("customers")
    print("\n[Step 1] Upserting 15 customers...")
    for c in customers_data:
        cust_col.update_one({"customer_id": c["customer_id"]}, {"$set": c}, upsert=True)
    print(f"  ✅ Successfully seeded {len(customers_data)} customers.")

    # 2. Orders Dataset
    orders_data = [
        # CUST-001 (High spender, completed)
        {
            "order_id": "ORD-001",
            "customer_id": "CUST-001",
            "order_date": now - timedelta(days=180),
            "items": [
                {"product_name": "Smart 4K LED TV 55-inch", "quantity": 1, "unit_price": 42999.0, "subtotal": 42999.0},
                {"product_name": "Soundbar with Subwoofer", "quantity": 1, "unit_price": 8999.0, "subtotal": 8999.0},
            ],
            "total_amount": 51998.0,
            "status": "completed",
            "notes": "Delivered on schedule",
        },
        {
            "order_id": "ORD-002",
            "customer_id": "CUST-001",
            "order_date": now - timedelta(days=45),
            "items": [
                {"product_name": "Wireless Noise Cancelling Headphones", "quantity": 1, "unit_price": 14999.0, "subtotal": 14999.0},
            ],
            "total_amount": 14999.0,
            "status": "completed",
            "notes": "Express delivery",
        },
        # CUST-002 (Frequent buyer)
        {
            "order_id": "ORD-003",
            "customer_id": "CUST-002",
            "order_date": now - timedelta(days=120),
            "items": [
                {"product_name": "Designer Leather Handbag", "quantity": 1, "unit_price": 6499.0, "subtotal": 6499.0},
                {"product_name": "Silk Scarf", "quantity": 2, "unit_price": 1299.0, "subtotal": 2598.0},
            ],
            "total_amount": 9097.0,
            "status": "completed",
        },
        {
            "order_id": "ORD-004",
            "customer_id": "CUST-002",
            "order_date": now - timedelta(days=30),
            "items": [
                {"product_name": "Fitness Smartwatch Band 7", "quantity": 1, "unit_price": 3499.0, "subtotal": 3499.0},
            ],
            "total_amount": 3499.0,
            "status": "completed",
        },
        # CUST-003 (Appliances)
        {
            "order_id": "ORD-005",
            "customer_id": "CUST-003",
            "order_date": now - timedelta(days=95),
            "items": [
                {"product_name": "Microwave Oven 28L Convection", "quantity": 1, "unit_price": 11490.0, "subtotal": 11490.0},
            ],
            "total_amount": 11490.0,
            "status": "completed",
        },
        # CUST-004 (Partial payer)
        {
            "order_id": "ORD-006",
            "customer_id": "CUST-004",
            "order_date": now - timedelta(days=60),
            "items": [
                {"product_name": "E-Reader Paperwhite 16GB", "quantity": 1, "unit_price": 13999.0, "subtotal": 13999.0},
                {"product_name": "Leather Folio Cover", "quantity": 1, "unit_price": 1999.0, "subtotal": 1999.0},
            ],
            "total_amount": 15998.0,
            "status": "completed",
        },
        # CUST-005 (Overdue payment)
        {
            "order_id": "ORD-007",
            "customer_id": "CUST-005",
            "order_date": now - timedelta(days=70),
            "items": [
                {"product_name": "Ergonomic Office Chair", "quantity": 1, "unit_price": 12500.0, "subtotal": 12500.0},
                {"product_name": "Footrest Cushion", "quantity": 1, "unit_price": 1200.0, "subtotal": 1200.0},
            ],
            "total_amount": 13700.0,
            "status": "completed",
            "notes": "Payment outstanding past due date",
        },
        # CUST-006 (VIP electronics)
        {
            "order_id": "ORD-008",
            "customer_id": "CUST-006",
            "order_date": now - timedelta(days=220),
            "items": [
                {"product_name": "Gaming Laptop 16GB RTX 4060", "quantity": 1, "unit_price": 89999.0, "subtotal": 89999.0},
            ],
            "total_amount": 89999.0,
            "status": "completed",
        },
        {
            "order_id": "ORD-009",
            "customer_id": "CUST-006",
            "order_date": now - timedelta(days=110),
            "items": [
                {"product_name": "Mechanical Gaming Keyboard RGB", "quantity": 1, "unit_price": 4500.0, "subtotal": 4500.0},
                {"product_name": "Wireless Gaming Mouse", "quantity": 1, "unit_price": 2999.0, "subtotal": 2999.0},
            ],
            "total_amount": 7499.0,
            "status": "completed",
        },
        # CUST-007 (New customer, pending)
        {
            "order_id": "ORD-010",
            "customer_id": "CUST-007",
            "order_date": now - timedelta(days=5),
            "items": [
                {"product_name": "Bluetooth Portable Speaker", "quantity": 1, "unit_price": 2499.0, "subtotal": 2499.0},
            ],
            "total_amount": 2499.0,
            "status": "pending",
            "notes": "Awaiting shipment and payment",
        },
        # CUST-008 (Returned order demo)
        {
            "order_id": "ORD-011",
            "customer_id": "CUST-008",
            "order_date": now - timedelta(days=80),
            "items": [
                {"product_name": "Embroidered Anarkali Kurta Set", "quantity": 1, "unit_price": 4999.0, "subtotal": 4999.0},
            ],
            "total_amount": 4999.0,
            "status": "returned",
            "notes": "Returned due to size mismatch; refund completed",
        },
        {
            "order_id": "ORD-012",
            "customer_id": "CUST-008",
            "order_date": now - timedelta(days=25),
            "items": [
                {"product_name": "Cotton Casual Dress", "quantity": 1, "unit_price": 2199.0, "subtotal": 2199.0},
            ],
            "total_amount": 2199.0,
            "status": "completed",
        },
        # CUST-009 (Cancelled order demo)
        {
            "order_id": "ORD-013",
            "customer_id": "CUST-009",
            "order_date": now - timedelta(days=65),
            "items": [
                {"product_name": "Air Purifier HEPA Filter H13", "quantity": 1, "unit_price": 9999.0, "subtotal": 9999.0},
            ],
            "total_amount": 9999.0,
            "status": "cancelled",
            "notes": "Customer cancelled before dispatch",
        },
        # CUST-010 (EMI partially paid)
        {
            "order_id": "ORD-014",
            "customer_id": "CUST-010",
            "order_date": now - timedelta(days=50),
            "items": [
                {"product_name": "Front Load Washing Machine 7kg", "quantity": 1, "unit_price": 28490.0, "subtotal": 28490.0},
            ],
            "total_amount": 28490.0,
            "status": "completed",
        },
        # CUST-011 (Defaulter)
        {
            "order_id": "ORD-015",
            "customer_id": "CUST-011",
            "order_date": now - timedelta(days=110),
            "items": [
                {"product_name": "Smartphone 5G 128GB", "quantity": 1, "unit_price": 21999.0, "subtotal": 21999.0},
            ],
            "total_amount": 21999.0,
            "status": "completed",
            "notes": "Delivered COD credit; default on payment",
        },
        # CUST-012 (COD single order)
        {
            "order_id": "ORD-016",
            "customer_id": "CUST-012",
            "order_date": now - timedelta(days=40),
            "items": [
                {"product_name": "Induction Cooktop 2000W", "quantity": 1, "unit_price": 2699.0, "subtotal": 2699.0},
            ],
            "total_amount": 2699.0,
            "status": "completed",
        },
        # CUST-013 (Bulk buyer)
        {
            "order_id": "ORD-017",
            "customer_id": "CUST-013",
            "order_date": now - timedelta(days=150),
            "items": [
                {"product_name": "Stainless Steel Cookware Set 5pc", "quantity": 5, "unit_price": 3999.0, "subtotal": 19995.0},
                {"product_name": "Kitchen Knife Set with Block", "quantity": 5, "unit_price": 1499.0, "subtotal": 7495.0},
            ],
            "total_amount": 27490.0,
            "status": "completed",
        },
        # CUST-014 (Wallet user)
        {
            "order_id": "ORD-018",
            "customer_id": "CUST-014",
            "order_date": now - timedelta(days=35),
            "items": [
                {"product_name": "Organic Skincare Gift Hamper", "quantity": 1, "unit_price": 3200.0, "subtotal": 3200.0},
            ],
            "total_amount": 3200.0,
            "status": "completed",
        },
        # CUST-015 (Late payer)
        {
            "order_id": "ORD-019",
            "customer_id": "CUST-015",
            "order_date": now - timedelta(days=45),
            "items": [
                {"product_name": "Smart Security Camera 360", "quantity": 2, "unit_price": 2499.0, "subtotal": 4998.0},
            ],
            "total_amount": 4998.0,
            "status": "completed",
        },
    ]

    orders_col = get_collection("orders")
    print("\n[Step 2] Upserting 19 orders...")
    for o in orders_data:
        orders_col.update_one({"order_id": o["order_id"]}, {"$set": o}, upsert=True)
    print(f"  ✅ Successfully seeded {len(orders_data)} orders.")

    # 3. Payments Dataset
    payments_data = [
        # PAY-001 (for ORD-001): Paid in full on time
        {
            "payment_id": "PAY-001",
            "order_id": "ORD-001",
            "customer_id": "CUST-001",
            "amount_due": 51998.0,
            "amount_paid": 51998.0,
            "payment_date": now - timedelta(days=175),
            "due_date": now - timedelta(days=165),
            "payment_mode": "Card",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-002 (for ORD-002): Paid in full on time
        {
            "payment_id": "PAY-002",
            "order_id": "ORD-002",
            "customer_id": "CUST-001",
            "amount_due": 14999.0,
            "amount_paid": 14999.0,
            "payment_date": now - timedelta(days=40),
            "due_date": now - timedelta(days=30),
            "payment_mode": "UPI",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-003 (for ORD-003): Paid on time
        {
            "payment_id": "PAY-003",
            "order_id": "ORD-003",
            "customer_id": "CUST-002",
            "amount_due": 9097.0,
            "amount_paid": 9097.0,
            "payment_date": now - timedelta(days=118),
            "due_date": now - timedelta(days=105),
            "payment_mode": "UPI",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-004 (for ORD-004): Paid on time
        {
            "payment_id": "PAY-004",
            "order_id": "ORD-004",
            "customer_id": "CUST-002",
            "amount_due": 3499.0,
            "amount_paid": 3499.0,
            "payment_date": now - timedelta(days=28),
            "due_date": now - timedelta(days=15),
            "payment_mode": "Card",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-005 (for ORD-005): Paid on time
        {
            "payment_id": "PAY-005",
            "order_id": "ORD-005",
            "customer_id": "CUST-003",
            "amount_due": 11490.0,
            "amount_paid": 11490.0,
            "payment_date": now - timedelta(days=90),
            "due_date": now - timedelta(days=80),
            "payment_mode": "Card",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-006 (for ORD-006, CUST-004): Partial payment (due: 15998, paid: 7999), due date in future
        {
            "payment_id": "PAY-006",
            "order_id": "ORD-006",
            "customer_id": "CUST-004",
            "amount_due": 15998.0,
            "amount_paid": 7999.0,
            "payment_date": now - timedelta(days=50),
            "due_date": now + timedelta(days=10),
            "payment_mode": "EMI",
            "status": "partial",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-007 (for ORD-007, CUST-005): Overdue payment (due: 13700, paid: 0, due date 35 days ago)
        {
            "payment_id": "PAY-007",
            "order_id": "ORD-007",
            "customer_id": "CUST-005",
            "amount_due": 13700.0,
            "amount_paid": 0.0,
            "payment_date": None,
            "due_date": now - timedelta(days=35),
            "payment_mode": "Card",
            "status": "overdue",
            "is_overdue": True,
            "days_overdue": 35,
        },
        # PAY-008 (for ORD-008, CUST-006): High value paid
        {
            "payment_id": "PAY-008",
            "order_id": "ORD-008",
            "customer_id": "CUST-006",
            "amount_due": 89999.0,
            "amount_paid": 89999.0,
            "payment_date": now - timedelta(days=218),
            "due_date": now - timedelta(days=205),
            "payment_mode": "Card",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-009 (for ORD-009, CUST-006): Paid
        {
            "payment_id": "PAY-009",
            "order_id": "ORD-009",
            "customer_id": "CUST-006",
            "amount_due": 7499.0,
            "amount_paid": 7499.0,
            "payment_date": now - timedelta(days=108),
            "due_date": now - timedelta(days=95),
            "payment_mode": "UPI",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-010 (for ORD-010, CUST-007): Pending payment, due in 10 days
        {
            "payment_id": "PAY-010",
            "order_id": "ORD-010",
            "customer_id": "CUST-007",
            "amount_due": 2499.0,
            "amount_paid": 0.0,
            "payment_date": None,
            "due_date": now + timedelta(days=10),
            "payment_mode": "COD",
            "status": "pending",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-011 (for ORD-012, CUST-008): Paid
        {
            "payment_id": "PAY-011",
            "order_id": "ORD-012",
            "customer_id": "CUST-008",
            "amount_due": 2199.0,
            "amount_paid": 2199.0,
            "payment_date": now - timedelta(days=23),
            "due_date": now - timedelta(days=10),
            "payment_mode": "UPI",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-012 (for ORD-014, CUST-010): Partial EMI
        {
            "payment_id": "PAY-012",
            "order_id": "ORD-014",
            "customer_id": "CUST-010",
            "amount_due": 28490.0,
            "amount_paid": 14245.0,
            "payment_date": now - timedelta(days=35),
            "due_date": now + timedelta(days=20),
            "payment_mode": "EMI",
            "status": "partial",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-013 (for ORD-015, CUST-011): Critical default, 65 days overdue
        {
            "payment_id": "PAY-013",
            "order_id": "ORD-015",
            "customer_id": "CUST-011",
            "amount_due": 21999.0,
            "amount_paid": 0.0,
            "payment_date": None,
            "due_date": now - timedelta(days=65),
            "payment_mode": "COD",
            "status": "overdue",
            "is_overdue": True,
            "days_overdue": 65,
        },
        # PAY-014 (for ORD-016, CUST-012): COD Paid
        {
            "payment_id": "PAY-014",
            "order_id": "ORD-016",
            "customer_id": "CUST-012",
            "amount_due": 2699.0,
            "amount_paid": 2699.0,
            "payment_date": now - timedelta(days=37),
            "due_date": now - timedelta(days=25),
            "payment_mode": "COD",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-015 (for ORD-017, CUST-013): High bulk payment, UPI
        {
            "payment_id": "PAY-015",
            "order_id": "ORD-017",
            "customer_id": "CUST-013",
            "amount_due": 27490.0,
            "amount_paid": 27490.0,
            "payment_date": now - timedelta(days=148),
            "due_date": now - timedelta(days=135),
            "payment_mode": "UPI",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-016 (for ORD-018, CUST-014): Wallet Paid
        {
            "payment_id": "PAY-016",
            "order_id": "ORD-018",
            "customer_id": "CUST-014",
            "amount_due": 3200.0,
            "amount_paid": 3200.0,
            "payment_date": now - timedelta(days=34),
            "due_date": now - timedelta(days=20),
            "payment_mode": "Wallet",
            "status": "paid",
            "is_overdue": False,
            "days_overdue": 0,
        },
        # PAY-017 (for ORD-019, CUST-015): 15 days overdue
        {
            "payment_id": "PAY-017",
            "order_id": "ORD-019",
            "customer_id": "CUST-015",
            "amount_due": 4998.0,
            "amount_paid": 0.0,
            "payment_date": None,
            "due_date": now - timedelta(days=15),
            "payment_mode": "UPI",
            "status": "overdue",
            "is_overdue": True,
            "days_overdue": 15,
        },
    ]

    payments_col = get_collection("payments")
    print("\n[Step 3] Upserting 17 payment records...")
    for p in payments_data:
        payments_col.update_one({"payment_id": p["payment_id"]}, {"$set": p}, upsert=True)
    print(f"  ✅ Successfully seeded {len(payments_data)} payments.")

    # 4. Seed Atomic Sequence Counters
    print("\n[Step 4] Initializing atomic sequence counters...")
    seed_counter("customer_seq", 15)
    seed_counter("order_seq", 19)
    seed_counter("payment_seq", 17)
    print("  ✅ Counters set (CUST: 15, ORD: 19, PAY: 17). Next generated IDs will be CUST-016, ORD-020, PAY-018.")

    print("\n" + "=" * 60)
    print("  🎉 SEEDING COMPLETE! Phase 2 data is live in MongoDB Atlas.")
    print("=" * 60)


if __name__ == "__main__":
    seed_database()
