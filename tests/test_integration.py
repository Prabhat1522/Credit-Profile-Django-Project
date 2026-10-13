"""
tests/test_integration.py
─────────────────────────────────────────────────────────────────────────────
Phase 5 Comprehensive Integration Test Suite:
Covers end-to-end workflows:
  1. Customer creation, profile inspection, and cleanup.
  2. Order creation with automated invoice generation and partial payments.
  3. Credit profile recalculation idempotency (no duplicate profiles).
  4. Risk alert generation, inspection, and manual resolution.
  5. Dashboard metrics integrity and live updates.
  6. Security enforcement: unauthenticated and invalid state-changing requests.
  7. Date-filter boundary conditions and malformed input handling.
  8. CSV export endpoints for customers, orders, and payments.
  9. MongoDB demo showcase view authentication and rendering.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.db_client import get_collection
from core.finance import compute_overdue_status, derive_payment_status
from customers import services as customer_services
from orders import services as order_services
from payments import services as payment_services
from credit import services as credit_services
from dashboard import services as dashboard_services


class FullApplicationIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "integration_admin"
        self.password = "Int3grati0n_S3cure!"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email="admin@integration.local"
        )
        self.created_customer_ids = []
        self.created_order_ids = []
        self.created_payment_ids = []

    def tearDown(self):
        # Strict cleanup of any test-generated records to prevent polluting MongoDB Atlas
        col_cust = get_collection("customers")
        col_orders = get_collection("orders")
        col_payments = get_collection("payments")
        col_profiles = get_collection("credit_profiles")
        col_alerts = get_collection("risk_alerts")

        for cid in self.created_customer_ids:
            col_cust.delete_one({"customer_id": cid})
            col_profiles.delete_one({"customer_id": cid})
            col_alerts.delete_many({"customer_id": cid})

        for oid in self.created_order_ids:
            col_orders.delete_one({"order_id": oid})

        for pid in self.created_payment_ids:
            col_payments.delete_one({"payment_id": pid})

    def test_customer_creation_and_detail_view(self):
        """Workflow 1: Admin creates customer through POST and views the customer detail page."""
        self.client.login(username=self.username, password=self.password)

        post_data = {
            "full_name": "Rohan Gupta",
            "email": "rohan.gupta.integration.test@example.com",
            "phone": "+91 98765 43210",
            "is_active": "on",
            "kyc_verified": "on",
            "street": "12 Residency Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560025",
            "tags": "VIP, Tech",
        }

        response = self.client.post(reverse("customers:create"), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Locate created customer
        col_cust = get_collection("customers")
        created = col_cust.find_one({"email": post_data["email"]})
        self.assertIsNotNone(created)
        cid = created["customer_id"]
        self.created_customer_ids.append(cid)

        # Verify customer detail view
        detail_response = self.client.get(reverse("customers:detail", kwargs={"customer_id": cid}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Rohan Gupta")
        self.assertContains(detail_response, "Bengaluru")

    def test_order_creation_with_invoice_and_partial_payment(self):
        """Workflow 2: Order creation creates linked invoice; partial payment updates outstanding debt."""
        # 1. Create a customer
        cust = customer_services.create_customer({
            "full_name": "Neha Sharma",
            "email": "neha.sharma.test@example.com",
            "phone": "+91 98111 22233",
            "is_active": True,
        })
        cid = cust["customer_id"]
        self.created_customer_ids.append(cid)

        # 2. Create an order with items
        order_data = {
            "customer_id": cid,
            "status": "pending",
            "notes": "Integration test purchase",
            "items": [
                {"product_name": "Noise Cancelling Headphones", "quantity": 1, "unit_price": 5000.0},
                {"product_name": "USB-C Fast Cable", "quantity": 2, "unit_price": 500.0},
            ]
        }
        order = order_services.create_order(order_data, create_pending_payment=True)
        oid = order["order_id"]
        self.created_order_ids.append(oid)
        self.assertEqual(order["total_amount"], 6000.0)

        # 3. Verify linked payment invoice was created
        col_pay = get_collection("payments")
        inv = col_pay.find_one({"order_id": oid})
        self.assertIsNotNone(inv)
        pid = inv["payment_id"]
        self.created_payment_ids.append(pid)
        self.assertEqual(inv["amount_due"], 6000.0)
        self.assertEqual(inv["amount_paid"], 0.0)
        self.assertEqual(inv["status"], "pending")

        # 4. Record a partial payment of ₹2500
        payment_services.record_transaction(pid, payment_amount=2500.0, payment_mode="UPI")

        updated_inv = col_pay.find_one({"payment_id": pid})
        self.assertEqual(updated_inv["amount_paid"], 2500.0)
        self.assertEqual(updated_inv["status"], "partial")

        # Outstanding balance calculation
        outstanding = max(updated_inv["amount_due"] - updated_inv["amount_paid"], 0.0)
        self.assertEqual(outstanding, 3500.0)

    def test_credit_profile_recalculation_idempotency(self):
        """Workflow 3: Repeated profile calculations update in place without duplicate documents."""
        col_profiles = get_collection("credit_profiles")
        existing_profile = col_profiles.find_one({"customer_id": "CUST-001"})
        self.assertIsNotNone(existing_profile, "Seeded customer CUST-001 must exist")

        count_before = col_profiles.count_documents({"customer_id": "CUST-001"})
        self.assertEqual(count_before, 1)

        # Force recalculation twice
        p1 = credit_services.get_or_calculate_credit_profile("CUST-001", force_recalculate=True)
        p2 = credit_services.get_or_calculate_credit_profile("CUST-001", force_recalculate=True)

        count_after = col_profiles.count_documents({"customer_id": "CUST-001"})
        self.assertEqual(count_after, 1, "Credit profile must be upserted atomically; no duplicates allowed.")
        self.assertEqual(p1["score"], p2["score"])
        self.assertEqual(p1["profile_status"], p2["profile_status"])

    def test_risk_alert_generation_and_resolution(self):
        """Workflow 4: Admin resolves an active risk alert and verifies status update."""
        col_alerts = get_collection("risk_alerts")
        alert = col_alerts.find_one({"resolved": False})
        if alert is None:
            # Create a test alert if none currently active
            now = datetime.now(timezone.utc)
            res = col_alerts.insert_one({
                "customer_id": "CUST-005",
                "alert_type": "OVERDUE_PAYMENT",
                "severity": "CRITICAL",
                "reason": "Test generated delinquency alert",
                "created_at": now,
                "last_evaluated_at": now,
                "resolved": False,
            })
            alert_id_str = str(res.inserted_id)
        else:
            alert_id_str = str(alert["_id"])

        self.client.login(username=self.username, password=self.password)
        resolve_url = reverse("credit:alert_resolve", kwargs={"alert_id": alert_id_str})
        response = self.client.post(resolve_url, data={"notes": "Resolved via integration test"}, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify alert document is resolved in database
        from bson import ObjectId
        updated = col_alerts.find_one({"_id": ObjectId(alert_id_str)})
        self.assertTrue(updated["resolved"])
        self.assertIn("resolved_at", updated)

    def test_unauthenticated_state_changing_requests_rejected(self):
        """Workflow 5: Unauthenticated state-changing POST requests must be redirected."""
        unauth_client = Client()

        # Customer create
        r1 = unauth_client.post(reverse("customers:create"), data={"full_name": "Hacker"})
        self.assertEqual(r1.status_code, 302)
        self.assertIn("/accounts/login/", r1.url)

        # Order create
        r2 = unauth_client.post(reverse("orders:create"), data={"customer_id": "CUST-001"})
        self.assertEqual(r2.status_code, 302)
        self.assertIn("/accounts/login/", r2.url)

        # Recalculate credit
        r3 = unauth_client.post(reverse("credit:recalculate", kwargs={"customer_id": "CUST-001"}))
        self.assertEqual(r3.status_code, 302)
        self.assertIn("/accounts/login/", r3.url)

        # Resolve alert
        from bson import ObjectId
        dummy_id = str(ObjectId())
        r4 = unauth_client.post(reverse("credit:alert_resolve", kwargs={"alert_id": dummy_id}))
        self.assertEqual(r4.status_code, 302)
        self.assertIn("/accounts/login/", r4.url)

    def test_date_filter_boundary_and_malformed_handling(self):
        """Workflow 6: Dashboard handles valid, malformed, and inverted date ranges gracefully."""
        self.client.login(username=self.username, password=self.password)

        # Valid date range
        r_valid = self.client.get(reverse("dashboard:index"), {"start_date": "2026-04-01", "end_date": "2026-06-30"})
        self.assertEqual(r_valid.status_code, 200)
        self.assertTrue(r_valid.context["filter"]["is_applied"])

        # Inverted date range (start > end)
        r_inverted = self.client.get(reverse("dashboard:index"), {"start_date": "2026-12-31", "end_date": "2026-01-01"})
        self.assertEqual(r_inverted.status_code, 200)
        self.assertIsNotNone(r_inverted.context["filter"]["error"])

        # Malformed date strings
        r_bad = self.client.get(reverse("dashboard:index"), {"start_date": "garbage-date", "end_date": "not-valid"})
        self.assertEqual(r_bad.status_code, 200)
        self.assertIsNotNone(r_bad.context["filter"]["error"])

    def test_csv_exports_functionality(self):
        """Workflow 7: All CSV export endpoints return valid CSV files with attachment headers."""
        self.client.login(username=self.username, password=self.password)

        endpoints = [
            reverse("customers:export_csv"),
            reverse("orders:export_csv"),
            reverse("payments:export_csv"),
        ]

        for url in endpoints:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res["Content-Type"], "text/csv")
            self.assertIn("attachment;", res["Content-Disposition"])
            self.assertGreater(len(res.content), 20)

    def test_mongo_demo_showcase_page(self):
        """Workflow 8: MongoDB showcase view is protected by login and renders database architecture."""
        unauth = Client()
        r_unauth = unauth.get(reverse("mongo_demo:index"))
        self.assertEqual(r_unauth.status_code, 302)

        self.client.login(username=self.username, password=self.password)
        r_auth = self.client.get(reverse("mongo_demo:index"))
        self.assertEqual(r_auth.status_code, 200)
        self.assertContains(r_auth, "MongoDB Architecture")
        self.assertContains(r_auth, "customers")
        self.assertContains(r_auth, "orders")
        self.assertContains(r_auth, "payments")
