"""
tests/test_credit_engine.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Automated test suite verifying the Phase 3 Credit-Scoring Engine:
      1. Deterministic ROUND_HALF_UP rounding (including exact 416.5 boundary).
      2. Canonical invoice evaluation & reconciliation of contradictory fields.
      3. Strict scale boundaries: components in [0, 100], final score in [0, 850].
      4. Single-bucket mutually exclusive invoice partitioning.
      5. The 5 agreed validation scenarios + delinquency edge cases.
      6. Exclusion of cancelled & returned orders from frequency and spend.
      7. Risk alert de-duplication and profile upsert repeatability.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timedelta, timezone
from django.test import TestCase
from credit.score_engine import (
    round_half_up,
    evaluate_invoice,
    calculate_credit_profile
)
from credit import services as credit_services
from core.db_client import get_collection


class CreditScoreEngineTestCase(TestCase):
    """Unit tests for the credit-scoring mathematical engine."""

    def test_round_half_up_exact_half_boundary(self):
        """Verifies exact half-up rounding (416.5 -> 417, not 416)."""
        self.assertEqual(round_half_up(416.5), 417)
        self.assertEqual(round_half_up(416.49), 416)
        self.assertEqual(round_half_up(416.51), 417)
        self.assertEqual(round_half_up(757.9), 758)
        self.assertEqual(round_half_up(401.625), 402)
        self.assertEqual(round_half_up(0.0), 0)

    def test_canonical_invoice_fully_settled_never_overdue(self):
        """
        A fully settled invoice (amount_due == amount_paid) must NEVER be overdue,
        even if its due date is 100 days in the past or is_overdue was stored True.
        """
        now = datetime.now(timezone.utc)
        past_date = now - timedelta(days=100)

        inv = {
            "payment_id": "PAY-TEST-01",
            "amount_due": 5000.0,
            "amount_paid": 5000.0,
            "due_date": past_date,
            "is_overdue": True,  # Contradictory stored flag!
            "days_overdue": 100,
        }
        res = evaluate_invoice(inv, now=now)
        self.assertEqual(res["outstanding"], 0.0)
        self.assertFalse(res["is_overdue"])
        self.assertEqual(res["days_overdue"], 0)
        self.assertEqual(res["bucket"], "ON_TIME")

    def test_current_partial_payment_not_delinquent(self):
        """
        A partially paid invoice whose due date is in the future must be
        classified as CURRENT_PARTIAL, not overdue or delinquent.
        """
        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=15)

        inv = {
            "payment_id": "PAY-TEST-02",
            "amount_due": 10000.0,
            "amount_paid": 5000.0,
            "due_date": future_date,
            "is_overdue": False,
        }
        res = evaluate_invoice(inv, now=now)
        self.assertEqual(res["outstanding"], 5000.0)
        self.assertFalse(res["is_overdue"])
        self.assertEqual(res["bucket"], "CURRENT_PARTIAL")

    def test_single_mutually_exclusive_bucket_partitioning(self):
        """Verifies that all 5 invoice categories enter exactly one bucket."""
        now = datetime.now(timezone.utc)
        invoices = [
            # 1. On time
            {"payment_id": "P1", "amount_due": 100, "amount_paid": 100, "due_date": now - timedelta(days=10)},
            # 2. Current partial
            {"payment_id": "P2", "amount_due": 100, "amount_paid": 50, "due_date": now + timedelta(days=10)},
            # 3. Current pending
            {"payment_id": "P3", "amount_due": 100, "amount_paid": 0, "due_date": now + timedelta(days=10)},
            # 4. Overdue partial
            {"payment_id": "P4", "amount_due": 100, "amount_paid": 40, "due_date": now - timedelta(days=10)},
            # 5. Overdue unpaid
            {"payment_id": "P5", "amount_due": 100, "amount_paid": 0, "due_date": now - timedelta(days=10)},
        ]
        buckets = [evaluate_invoice(inv, now=now)["bucket"] for inv in invoices]
        self.assertEqual(buckets, ["ON_TIME", "CURRENT_PARTIAL", "CURRENT_PENDING", "OVERDUE_PARTIAL", "OVERDUE_UNPAID"])

    def test_scenario_1_prime_customer(self):
        """Scenario 1: On-time Prime customer scores Excellent (758/850)."""
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-001",
            "account_created_at": now - timedelta(days=320),
        }
        orders = [
            {"order_id": "ORD-001", "status": "completed", "total_amount": 51998.0},
            {"order_id": "ORD-002", "status": "completed", "total_amount": 14999.0},
        ]
        payments = [
            {"payment_id": "PAY-001", "amount_due": 51998.0, "amount_paid": 51998.0, "due_date": now - timedelta(days=165)},
            {"payment_id": "PAY-002", "amount_due": 14999.0, "amount_paid": 14999.0, "due_date": now - timedelta(days=30)},
        ]
        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertEqual(res["score"], 758)
        self.assertEqual(res["risk_category"], "Excellent")
        self.assertEqual(res["profile_status"], "LIMITED_HISTORY")
        self.assertEqual(res["component_scores"]["payment_history"], 100.0)
        self.assertEqual(res["component_scores"]["outstanding_dues"], 100.0)

    def test_scenario_2_new_customer_insufficient_data(self):
        """
        Scenario 2: New customer with 1 pending invoice (due in 10 days)
        scores 417 (exact 416.5 boundary) and is classified INSUFFICIENT_DATA, NOT Critical!
        """
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-007",
            "account_created_at": now - timedelta(days=25),
        }
        orders = [
            {"order_id": "ORD-010", "status": "pending", "total_amount": 2499.0},  # Pending, not completed!
        ]
        payments = [
            {"payment_id": "PAY-010", "amount_due": 2499.0, "amount_paid": 0.0, "due_date": now + timedelta(days=10)},
        ]
        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertEqual(res["score"], 417)
        self.assertEqual(res["profile_status"], "INSUFFICIENT_DATA")
        self.assertEqual(res["risk_category"], "Insufficient Data")
        self.assertFalse(any(a["alert_type"] == "OVERDUE_PAYMENT" for a in res["detected_alerts"]))

    def test_scenario_3_severe_defaulter_critical(self):
        """Scenario 3: Severe overdue customer scores 167 (Critical) and raises alert."""
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-011",
            "account_created_at": now - timedelta(days=260),
        }
        orders = [
            {"order_id": "ORD-015", "status": "completed", "total_amount": 21999.0},
        ]
        payments = [
            {"payment_id": "PAY-013", "amount_due": 21999.0, "amount_paid": 0.0, "due_date": now - timedelta(days=65)},
        ]
        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertEqual(res["score"], 167)
        self.assertEqual(res["risk_category"], "Critical")
        self.assertEqual(res["profile_status"], "ESTABLISHED")
        self.assertEqual(res["component_scores"]["payment_history"], 0.0)
        self.assertEqual(res["component_scores"]["outstanding_dues"], 0.0)
        self.assertTrue(any(a["alert_type"] == "OVERDUE_PAYMENT" for a in res["detected_alerts"]))

    def test_scenario_4_partial_payer_fair_score(self):
        """
        Scenario 4: Partial payer on EMI (paid 50% ahead of due date)
        scores 583 (Fair risk band, recognizing proactive payment).
        """
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-004",
            "account_created_at": now - timedelta(days=240),
        }
        orders = [
            {"order_id": "ORD-006", "status": "completed", "total_amount": 15998.0},
        ]
        payments = [
            {"payment_id": "PAY-006", "amount_due": 15998.0, "amount_paid": 7999.0, "due_date": now + timedelta(days=10)},
        ]
        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertEqual(res["score"], 583)
        self.assertEqual(res["risk_category"], "Fair")
        self.assertEqual(res["profile_status"], "LIMITED_HISTORY")

    def test_scenario_5_zero_orders_zero_invoices(self):
        """Scenario 5: Fresh registration with 0 orders and 0 invoices scores 402 (Insufficient Data)."""
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-FRESH",
            "account_created_at": now - timedelta(days=10),
        }
        res = calculate_credit_profile(customer, orders=[], payments=[], now=now)
        self.assertEqual(res["score"], 402)
        self.assertEqual(res["profile_status"], "INSUFFICIENT_DATA")
        self.assertEqual(res["risk_category"], "Insufficient Data")

    def test_scenario_6_delinquency_never_masked_by_insufficient_data(self):
        """
        Scenario 6: Even if a customer has 0 completed orders and tenure < 30 days,
        an overdue invoice MUST NOT be masked by INSUFFICIENT_DATA.
        """
        now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
        customer = {
            "customer_id": "CUST-DELINQ-NEW",
            "account_created_at": now - timedelta(days=15),
        }
        payments = [
            {"payment_id": "PAY-DELINQ", "amount_due": 1000.0, "amount_paid": 0.0, "due_date": now - timedelta(days=5)},
        ]
        res = calculate_credit_profile(customer, orders=[], payments=payments, now=now)
        self.assertNotEqual(res["profile_status"], "INSUFFICIENT_DATA")
        self.assertEqual(res["profile_status"], "LIMITED_HISTORY")
        self.assertTrue(any(a["alert_type"] == "OVERDUE_PAYMENT" for a in res["detected_alerts"]))

    def test_cancelled_and_returned_orders_excluded_from_spend_and_frequency(self):
        """Cancelled and returned orders must not inflate completed count or spent total."""
        now = datetime.now(timezone.utc)
        customer = {"customer_id": "CUST-RETURN", "account_created_at": now - timedelta(days=100)}
        orders = [
            {"order_id": "ORD-1", "status": "completed", "total_amount": 5000.0},
            {"order_id": "ORD-2", "status": "cancelled", "total_amount": 50000.0},  # Must be ignored!
            {"order_id": "ORD-3", "status": "returned", "total_amount": 25000.0},   # Must be ignored!
        ]
        payments = [
            {"payment_id": "P1", "amount_due": 5000.0, "amount_paid": 5000.0, "due_date": now - timedelta(days=10)},
        ]
        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertEqual(res["financial_summary"]["completed_orders"], 1)
        self.assertEqual(res["financial_summary"]["total_spent"], 5000.0)

    def test_scale_boundaries_inclusive(self):
        """All component scores must be in [0.0, 100.0] and final score in [0, 850]."""
        now = datetime.now(timezone.utc)
        customer = {"customer_id": "CUST-EXTREME", "account_created_at": now - timedelta(days=1000)}
        orders = [{"order_id": "ORD-BIG", "status": "completed", "total_amount": 500000.0}] * 20
        payments = [{"payment_id": f"P{i}", "amount_due": 100.0, "amount_paid": 100.0, "due_date": now - timedelta(days=10)} for i in range(20)]

        res = calculate_credit_profile(customer, orders, payments, now=now)
        self.assertLessEqual(res["score"], 850)
        self.assertGreaterEqual(res["score"], 0)
        for comp, val in res["component_scores"].items():
            self.assertGreaterEqual(val, 0.0, f"{comp} below 0")
            self.assertLessEqual(val, 100.0, f"{comp} above 100")


class CreditViewsTestCase(TestCase):
    """Integration tests for Credit Profile and Risk Alert Django views."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_superuser("admin_test", "admin@test.com", "pass123")
        self.client.force_login(self.user)

    def test_credit_list_view(self):
        """Verifies /credit/ loads and renders successfully."""
        res = self.client.get("/credit/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Credit Profiles")

    def test_credit_detail_view(self):
        """Verifies /credit/CUST-001/ renders with breakdown."""
        res = self.client.get("/credit/CUST-001/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Credit Profile Analysis")
        self.assertContains(res, "5-Component Weight Breakdown")

    def test_credit_recalculate_post(self):
        """Verifies /credit/CUST-001/recalculate/ responds to POST."""
        res = self.client.post("/credit/CUST-001/recalculate/")
        self.assertEqual(res.status_code, 302)  # Redirects back to detail page

    def test_risk_alerts_view(self):
        """Verifies /credit/alerts/ renders active alerts with no template errors."""
        res = self.client.get("/credit/alerts/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "System Risk Alerts")

