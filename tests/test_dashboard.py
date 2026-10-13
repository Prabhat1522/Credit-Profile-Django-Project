"""
tests/test_dashboard.py
─────────────────────────────────────────────────────────────────────────────
Phase 4 Automated Test Suite: Dashboard, Aggregations & Charts
Tests:
  1. Authentication protection (unauthenticated -> redirect to login).
  2. Authenticated dashboard view response (HTTP 200, context variables).
  3. Reusable MongoDB aggregation service results (customers, financials, alerts).
  4. Date range parsing, server-side validation, and revenue filtering.
  5. Chart.js JSON payload structures and completeness.
  6. Graceful handling of empty datasets.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from dashboard.services import (
    parse_date_range,
    get_customers_overview,
    get_financial_overview,
    get_revenue_timeline,
    get_risk_alerts_overview,
    get_dashboard_summary,
)


class DashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "test_admin"
        self.password = "Secr3t_Passw0rd!"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email="admin@creditiq.local"
        )

    def test_dashboard_requires_login(self):
        """Unauthenticated requests must redirect to the login page."""
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_dashboard_view_renders_successfully(self):
        """Authenticated requests must return HTTP 200 with complete analytics context."""
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")

        # Verify required context variables
        self.assertIn("customers", response.context)
        self.assertIn("financials", response.context)
        self.assertIn("alerts", response.context)
        self.assertIn("charts_payload", response.context)
        self.assertIn("filter", response.context)

        # Verify JSON script tag is present in the rendered HTML
        self.assertContains(response, 'id="dashboard-charts-data"')
        self.assertContains(response, 'Executive Analytics Dashboard')

    def test_db_status_json_endpoint(self):
        """db-status endpoint returns valid JSON with MongoDB status."""
        response = self.client.get(reverse("dashboard:db_status"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("collections", data)

    def test_customers_overview_aggregation(self):
        """Tests customer counts, profile status breakdown, and risk categories."""
        overview = get_customers_overview()
        self.assertGreaterEqual(overview["total_customers"], 1)
        self.assertGreaterEqual(overview["active_customers"], 0)

        # Profile status counts
        statuses = overview["profile_statuses"]
        self.assertIn("ESTABLISHED", statuses)
        self.assertIn("LIMITED_HISTORY", statuses)
        self.assertIn("INSUFFICIENT_DATA", statuses)
        self.assertEqual(
            sum(statuses.values()),
            overview["total_customers"],
            "Sum of profile status partitions should equal total customer profiles"
        )

        # Risk category counts
        cats = overview["risk_categories"]
        for expected_cat in ["Excellent", "Good", "Fair", "Poor", "Critical", "Insufficient Data"]:
            self.assertIn(expected_cat, cats)

    def test_financial_overview_aggregation(self):
        """Tests revenue calculation, outstanding balance, and overdue balance."""
        fin = get_financial_overview()
        self.assertGreaterEqual(fin["completed_revenue"], 0.0)
        self.assertGreaterEqual(fin["completed_order_count"], 0)
        self.assertGreaterEqual(fin["total_outstanding"], 0.0)
        self.assertGreaterEqual(fin["total_overdue"], 0.0)
        self.assertGreaterEqual(fin["current_outstanding"], 0.0)

        # Outstanding must be >= overdue balance
        self.assertGreaterEqual(
            fin["total_outstanding"],
            fin["total_overdue"],
            "Total outstanding balance must be greater than or equal to overdue balance."
        )

    def test_date_range_validation(self):
        """Tests date parsing, boundary validation, and error messages."""
        # Valid date range
        start, end, err = parse_date_range("2026-01-01", "2026-12-31")
        self.assertIsNone(err)
        self.assertEqual(start.year, 2026)
        self.assertEqual(end.year, 2026)

        # Inverted date range (start > end)
        start, end, err = parse_date_range("2026-12-31", "2026-01-01")
        self.assertIsNotNone(err)
        self.assertIn("cannot be after", err)

        # Invalid string format
        start, end, err = parse_date_range("invalid-date", "2026-05-01")
        self.assertIsNotNone(err)
        self.assertIn("Invalid start date", err)

        # Empty strings return None without error
        start, end, err = parse_date_range("", "")
        self.assertIsNone(err)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_revenue_timeline_with_date_filter(self):
        """Tests that date filtering isolates completed orders within the target range."""
        start_dt, end_dt, _ = parse_date_range("2026-04-01", "2026-06-30")
        filtered_timeline = get_revenue_timeline(start_dt, end_dt)

        for item in filtered_timeline:
            self.assertIn(item["month_key"], ["2026-04", "2026-05", "2026-06"])
            self.assertGreaterEqual(item["revenue"], 0.0)

    def test_risk_alerts_overview(self):
        """Tests active risk alert count and severity partition."""
        alerts = get_risk_alerts_overview()
        self.assertGreaterEqual(alerts["total_active"], 0)
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            self.assertIn(sev, alerts["severities"])
            self.assertGreaterEqual(alerts["severities"][sev], 0)

    def test_charts_payload_completeness(self):
        """Verifies all five required Chart.js visualization datasets are generated."""
        summary = get_dashboard_summary()
        payload = summary["charts_payload"]

        # 1. Doughnut: Customers by Risk Category
        self.assertIn("risk_category_chart", payload)
        self.assertEqual(len(payload["risk_category_chart"]["labels"]), 6)
        self.assertEqual(len(payload["risk_category_chart"]["data"]), 6)

        # 2. Bar: Profile Statuses
        self.assertIn("profile_status_chart", payload)
        self.assertEqual(len(payload["profile_status_chart"]["labels"]), 3)
        self.assertEqual(len(payload["profile_status_chart"]["data"]), 3)

        # 3. Bar: Outstanding vs Overdue
        self.assertIn("balance_chart", payload)
        self.assertEqual(len(payload["balance_chart"]["labels"]), 2)
        self.assertEqual(len(payload["balance_chart"]["data"]), 2)

        # 4. Line: Monthly Revenue
        self.assertIn("revenue_timeline_chart", payload)
        self.assertIsInstance(payload["revenue_timeline_chart"]["labels"], list)
        self.assertIsInstance(payload["revenue_timeline_chart"]["data"], list)

        # 5. Bar: Active Risk Alerts by Severity
        self.assertIn("alert_severity_chart", payload)
        self.assertEqual(len(payload["alert_severity_chart"]["labels"]), 4)
        self.assertEqual(len(payload["alert_severity_chart"]["data"]), 4)

    def test_empty_dataset_handling(self):
        """Verifies service functions gracefully handle empty collections without throwing exceptions."""
        empty_col_mock = MagicMock()
        empty_col_mock.count_documents.return_value = 0
        empty_col_mock.aggregate.return_value = []

        with patch("dashboard.services.get_collection", return_value=empty_col_mock):
            summary = get_dashboard_summary()
            self.assertEqual(summary["customers"]["total_customers"], 0)
            self.assertEqual(summary["financials"]["completed_revenue"], 0.0)
            self.assertEqual(summary["financials"]["total_outstanding"], 0.0)
            self.assertEqual(summary["financials"]["total_overdue"], 0.0)
            self.assertEqual(summary["alerts"]["total_active"], 0)
            self.assertEqual(len(summary["timeline"]), 0)
            self.assertEqual(summary["charts_payload"]["revenue_timeline_chart"]["total"], 0)
