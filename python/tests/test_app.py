"""Unit tests for the owner's web application (part 2).

Run from inside python/:  python -m unittest
"""

import json
import os
import unittest
from app import load_plan_data, render_html_page, PLAIN_REASONS, DECISIONS


class AppTest(unittest.TestCase):
    def setUp(self):
        DECISIONS.clear()

    def test_load_plan_data_success(self):
        plan, err = load_plan_data("../data", "2026-10-12")
        self.assertIsNone(err)
        self.assertIsNotNone(plan)
        self.assertIn("actions", plan)
        self.assertIn("skipped", plan)
        # Check customer names and currencies attached
        for act in plan["actions"]:
            self.assertIn("customer", act)
            self.assertIn("amount", act)

    def test_load_plan_data_missing_dir(self):
        plan, err = load_plan_data("nonexistent_dir", "2026-10-12")
        self.assertIsNone(plan)
        self.assertIsNotNone(err)
        self.assertIn("not found", err.lower())

    def test_plain_reasons_contain_all_bad_data_codes(self):
        expected_codes = ["duplicate_id", "invalid_amount", "missing_due_date", "invalid_due_date", "invalid_paid_date"]
        for code in expected_codes:
            self.assertIn(code, PLAIN_REASONS)
            self.assertNotIn("_", PLAIN_REASONS[code])  # Plain words, not code identifiers

    def test_render_html_page_contains_required_elements(self):
        plan, _ = load_plan_data("../data", "2026-10-12")
        html = render_html_page(plan, None, "2026-10-12", "../data", {"INV-1001": "approved"})
        self.assertIn("Payment Reminders Assistant", html)
        self.assertIn("INV-1001", html)
        self.assertIn("Approved", html)
        self.assertIn("Undo Decision", html)
        self.assertIn("Skipped Invoices", html)
        self.assertIn("viewport", html)

    def test_render_decision_states_and_undo(self):
        plan, _ = load_plan_data("../data", "2026-10-12")
        # When unapproved, shows Approve and Reject buttons
        html_pending = render_html_page(plan, None, "2026-10-12", "../data", {})
        self.assertIn("Approve", html_pending)
        self.assertIn("Reject", html_pending)
        self.assertIn("Awaiting Decision", html_pending)

        # When rejected, shows Rejected status and Undo button
        html_rejected = render_html_page(plan, None, "2026-10-12", "../data", {"INV-1001": "rejected"})
        self.assertIn("Rejected", html_rejected)
        self.assertIn("Undo Decision", html_rejected)

    def test_render_empty_state(self):
        empty_plan = {"today": "2026-10-12", "actions": [], "skipped": []}
        html = render_html_page(empty_plan, None, "2026-10-12", "../data", {})
        self.assertIn("All Caught Up", html)

    def test_render_error_state(self):
        html = render_html_page(None, "Failed to read data files", "2026-10-12", "../data", {})
        self.assertIn("Data Error", html)
        self.assertIn("Failed to read data files", html)


if __name__ == "__main__":
    unittest.main()
