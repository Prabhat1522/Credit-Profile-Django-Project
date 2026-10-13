"""
tests/test_finance.py
─────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Automated test suite verifying the business logic in core/finance.py:
      1. Overdue status derivation
      2. Payment status derivation (paid, pending, partial, overdue)
      3. Edge cases: zero dues, partial payments, past due dates
      4. Customer aggregations (cancelled/returned orders excluded from spent)
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timedelta, timezone
from django.test import TestCase
from core.finance import (
    compute_overdue_status,
    derive_payment_status,
    get_customer_order_summary,
    get_customer_payment_summary,
    get_customer_full_summary,
)


class FinanceCalculationsTestCase(TestCase):
    """Unit tests for financial calculations and status rules."""

    def test_overdue_when_past_due_date_with_balance(self):
        """Payments past their due date with an outstanding balance must be marked overdue."""
        now = datetime.now(timezone.utc)
        past_date = now - timedelta(days=10)

        is_overdue, days = compute_overdue_status(past_date, amount_due=1000.0, amount_paid=0.0)
        self.assertTrue(is_overdue)
        self.assertGreaterEqual(days, 9)

    def test_not_overdue_when_fully_paid_even_if_past_due(self):
        """Even if the due date is long past, a fully paid invoice must never be overdue."""
        past_date = datetime.now(timezone.utc) - timedelta(days=60)

        is_overdue, days = compute_overdue_status(past_date, amount_due=1000.0, amount_paid=1000.0)
        self.assertFalse(is_overdue)
        self.assertEqual(days, 0)

    def test_not_overdue_when_due_date_is_future(self):
        """Invoices with a future due date must not be overdue."""
        future_date = datetime.now(timezone.utc) + timedelta(days=15)

        is_overdue, days = compute_overdue_status(future_date, amount_due=1000.0, amount_paid=200.0)
        self.assertFalse(is_overdue)
        self.assertEqual(days, 0)

    def test_derive_payment_status_paid(self):
        """Paid status when amount_paid >= amount_due."""
        status = derive_payment_status(amount_due=500.0, amount_paid=500.0, is_overdue=False)
        self.assertEqual(status, "paid")

    def test_derive_payment_status_partial(self):
        """Partial status when 0 < amount_paid < amount_due and not overdue."""
        status = derive_payment_status(amount_due=500.0, amount_paid=250.0, is_overdue=False)
        self.assertEqual(status, "partial")

    def test_derive_payment_status_pending(self):
        """Pending status when amount_paid == 0 and not overdue."""
        status = derive_payment_status(amount_due=500.0, amount_paid=0.0, is_overdue=False)
        self.assertEqual(status, "pending")

    def test_derive_payment_status_overdue(self):
        """Overdue status when is_overdue is True."""
        status = derive_payment_status(amount_due=500.0, amount_paid=100.0, is_overdue=True)
        self.assertEqual(status, "overdue")

    def test_customer_summary_aggregation(self):
        """Verify customer financial summary aggregation on seeded customer CUST-001."""
        summary = get_customer_full_summary("CUST-001")
        # CUST-001 has 2 completed orders: 51998 + 14999 = 66997
        self.assertEqual(summary["total_orders"], 2)
        self.assertEqual(summary["completed_orders"], 2)
        self.assertAlmostEqual(summary["total_spent"], 66997.0, places=1)
        self.assertEqual(summary["outstanding_balance"], 0.0)
        self.assertEqual(summary["overdue_count"], 0)

    def test_customer_summary_overdue_flag(self):
        """Verify customer financial summary identifies overdue payments on CUST-005."""
        summary = get_customer_full_summary("CUST-005")
        self.assertGreater(summary["outstanding_balance"], 0.0)
        self.assertGreaterEqual(summary["overdue_count"], 1)
