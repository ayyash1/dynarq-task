"""Unit tests for payment reminder rules engine and message generation.

Run from inside python/:  python -m unittest
"""

import subprocess
import sys
import unittest
from plan import build_plan, parse_iso_date, generate_message


class RulesEngineTest(unittest.TestCase):
    def test_empty_input_gives_empty_plan(self):
        plan = build_plan([], [], "2026-10-12")
        self.assertEqual(plan, {"today": "2026-10-12", "actions": [], "skipped": []})

    def test_invalid_today_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_plan([], [], "not-a-date")
        with self.assertRaises(ValueError):
            build_plan([], [], "2026-02-30")

    def test_duplicate_id_skips_all_instances_and_lists_once(self):
        invoices = [
            {"id": "INV-1", "customer": "A", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-1", "customer": "A2", "currency": "EUR", "amount": 200, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-2", "customer": "B", "currency": "EUR", "amount": 300, "due_date": "2026-09-01", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        self.assertEqual(len(plan["skipped"]), 1)
        self.assertEqual(plan["skipped"][0], {"invoice_id": "INV-1", "reason": "duplicate_id"})
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["invoice_id"], "INV-2")

    def test_duplicate_id_has_highest_precedence_over_other_bad_data(self):
        # Even if one duplicate has an invalid amount, both are skipped for duplicate_id
        invoices = [
            {"id": "INV-DUP", "customer": "A", "currency": "EUR", "amount": -50, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-DUP", "customer": "A2", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        self.assertEqual(plan["skipped"], [{"invoice_id": "INV-DUP", "reason": "duplicate_id"}])

    def test_invalid_amount_variations(self):
        cases = [
            ("INV-M", None),
            ("INV-S", "100.0"),
            ("INV-B1", True),
            ("INV-B2", False),
            ("INV-Z", 0),
            ("INV-N", -10.5),
            ("INV-F", float("nan")),
            ("INV-I", float("inf")),
        ]
        for inv_id, amt in cases:
            inv = [{"id": inv_id, "customer": "C", "currency": "EUR", "amount": amt, "due_date": "2026-09-01", "paid_date": None}]
            plan = build_plan(inv, [], "2026-10-12")
            self.assertEqual(plan["skipped"], [{"invoice_id": inv_id, "reason": "invalid_amount"}], f"Failed for amount {amt}")

    def test_missing_due_date_variations(self):
        cases = [
            {"id": "INV-N", "customer": "C", "currency": "EUR", "amount": 100, "due_date": None, "paid_date": None},
            {"id": "INV-E", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "", "paid_date": None},
            {"id": "INV-M", "customer": "C", "currency": "EUR", "amount": 100, "paid_date": None},
        ]
        for inv in cases:
            plan = build_plan([inv], [], "2026-10-12")
            self.assertEqual(plan["skipped"], [{"invoice_id": inv["id"], "reason": "missing_due_date"}])

    def test_invalid_due_date_variations(self):
        bad_dates = ["2026-02-30", "30/09/2026", "2026-13-01", "2026-00-10", "invalid", 12345]
        for bad in bad_dates:
            inv = [{"id": "INV-D", "customer": "C", "currency": "EUR", "amount": 100, "due_date": bad, "paid_date": None}]
            plan = build_plan(inv, [], "2026-10-12")
            self.assertEqual(plan["skipped"], [{"invoice_id": "INV-D", "reason": "invalid_due_date"}], f"Failed for {bad}")

    def test_invalid_paid_date_variations(self):
        bad_paid = ["", "2026-02-30", "30/09/2026", "2026-10-13", "not-date", 12345]  # 2026-10-13 is after today (2026-10-12)
        for bad in bad_paid:
            inv = [{"id": "INV-P", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": bad}]
            plan = build_plan(inv, [], "2026-10-12")
            self.assertEqual(plan["skipped"], [{"invoice_id": "INV-P", "reason": "invalid_paid_date"}], f"Failed for {bad}")

    def test_bad_data_order_of_precedence(self):
        # invalid_amount before missing_due_date
        inv1 = [{"id": "INV-1", "customer": "C", "currency": "EUR", "amount": 0, "due_date": None, "paid_date": None}]
        plan1 = build_plan(inv1, [], "2026-10-12")
        self.assertEqual(plan1["skipped"][0]["reason"], "invalid_amount")

        # missing_due_date before invalid_paid_date
        inv2 = [{"id": "INV-2", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "", "paid_date": "after-today"}]
        plan2 = build_plan(inv2, [], "2026-10-12")
        self.assertEqual(plan2["skipped"][0]["reason"], "missing_due_date")

        # invalid_due_date before invalid_paid_date
        inv3 = [{"id": "INV-3", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-02-30", "paid_date": "bad"}]
        plan3 = build_plan(inv3, [], "2026-10-12")
        self.assertEqual(plan3["skipped"][0]["reason"], "invalid_due_date")

    def test_paid_invoice_plans_nothing(self):
        # Paid on or before today
        inv = [{"id": "INV-PAID", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": "2026-10-10"}]
        sent = [{"invoice_id": "INV-PAID", "step": "firm", "sent_on": "2026-09-20"}]
        plan = build_plan(inv, sent, "2026-10-12")
        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["skipped"], [])

    def test_days_overdue_and_thresholds(self):
        today = "2026-10-12"
        # Due today (0 days): plan nothing
        inv0 = [{"id": "INV-0", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-12", "paid_date": None}]
        self.assertEqual(build_plan(inv0, [], today)["actions"], [])

        # 2 days overdue (2026-10-10): plan nothing
        inv2 = [{"id": "INV-2", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-10", "paid_date": None}]
        self.assertEqual(build_plan(inv2, [], today)["actions"], [])

        # 3 days overdue (2026-10-09): friendly, needs_approval=False
        inv3 = [{"id": "INV-3", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-09", "paid_date": None}]
        plan3 = build_plan(inv3, [], today)
        self.assertEqual(plan3["actions"][0]["step"], "friendly")
        self.assertEqual(plan3["actions"][0]["needs_approval"], False)
        self.assertEqual(plan3["actions"][0]["days_overdue"], 3)

        # 9 days overdue (2026-10-03): friendly
        inv9 = [{"id": "INV-9", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-03", "paid_date": None}]
        self.assertEqual(build_plan(inv9, [], today)["actions"][0]["step"], "friendly")

        # 10 days overdue (2026-10-02): firm, needs_approval=True
        inv10 = [{"id": "INV-10", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-02", "paid_date": None}]
        plan10 = build_plan(inv10, [], today)
        self.assertEqual(plan10["actions"][0]["step"], "firm")
        self.assertEqual(plan10["actions"][0]["needs_approval"], True)
        self.assertEqual(plan10["actions"][0]["days_overdue"], 10)

        # 23 days overdue (2026-09-19): firm
        inv23 = [{"id": "INV-23", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-19", "paid_date": None}]
        self.assertEqual(build_plan(inv23, [], today)["actions"][0]["step"], "firm")

        # 24 days overdue (2026-09-18): final, needs_approval=True
        inv24 = [{"id": "INV-24", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-18", "paid_date": None}]
        plan24 = build_plan(inv24, [], today)
        self.assertEqual(plan24["actions"][0]["step"], "final")
        self.assertEqual(plan24["actions"][0]["needs_approval"], True)
        self.assertEqual(plan24["actions"][0]["days_overdue"], 24)

    def test_sent_rules(self):
        today = "2026-10-12"
        # 12 days overdue (firm reached):
        # If nothing sent -> plan firm
        inv = [{"id": "INV-1", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-30", "paid_date": None}]
        self.assertEqual(build_plan(inv, [], today)["actions"][0]["step"], "firm")

        # If friendly already sent -> plan firm
        sent_friendly = [{"invoice_id": "INV-1", "step": "friendly", "sent_on": "2026-10-03"}]
        self.assertEqual(build_plan(inv, sent_friendly, today)["actions"][0]["step"], "firm")

        # If firm already sent -> plan nothing
        sent_firm = [{"invoice_id": "INV-1", "step": "firm", "sent_on": "2026-10-05"}]
        self.assertEqual(build_plan(inv, sent_firm, today)["actions"], [])

        # If final already sent -> plan nothing
        sent_final = [{"invoice_id": "INV-1", "step": "final", "sent_on": "2026-10-05"}]
        self.assertEqual(build_plan(inv, sent_final, today)["actions"], [])

        # 25 days overdue (final reached):
        inv_final = [{"id": "INV-2", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-09-17", "paid_date": None}]
        # If friendly & firm sent -> plan final
        sent_prior = [
            {"invoice_id": "INV-2", "step": "friendly", "sent_on": "2026-09-20"},
            {"invoice_id": "INV-2", "step": "firm", "sent_on": "2026-10-01"},
        ]
        self.assertEqual(build_plan(inv_final, sent_prior, today)["actions"][0]["step"], "final")

        # If final already sent -> plan nothing
        sent_all = sent_prior + [{"invoice_id": "INV-2", "step": "final", "sent_on": "2026-10-11"}]
        self.assertEqual(build_plan(inv_final, sent_all, today)["actions"], [])

    def test_sent_ignores_unknown_ids_and_invalid_steps(self):
        today = "2026-10-12"
        inv = [{"id": "INV-1", "customer": "C", "currency": "EUR", "amount": 100, "due_date": "2026-10-05", "paid_date": None}]
        sent = [
            {"invoice_id": "INV-9999", "step": "firm", "sent_on": "2026-10-01"},
            {"invoice_id": "INV-1", "step": "unknown_step", "sent_on": "2026-10-01"},
        ]
        plan = build_plan(inv, sent, today)
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["invoice_id"], "INV-1")

    def test_sorting_by_invoice_id_plain_text(self):
        invoices = [
            {"id": "INV-99", "customer": "C99", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-100", "customer": "C100", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-2", "customer": "C2", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-10", "customer": "C10", "currency": "EUR", "amount": 100, "due_date": "2026-09-01", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        action_ids = [a["invoice_id"] for a in plan["actions"]]
        # Plain text sort: '1' < '2' < '9'
        self.assertEqual(action_ids, ["INV-10", "INV-100", "INV-2", "INV-99"])

    def test_message_content_rules(self):
        customer = "Alpha Beta Ltd"
        inv_id = "INV-777"
        due_date = "2026-09-15"
        currency = "GBP"
        amount = 1250.5
        days_overdue = 27

        for step in ["friendly", "firm", "final"]:
            msg = generate_message(customer, inv_id, due_date, currency, amount, days_overdue, step)
            self.assertIn(customer, msg)
            self.assertIn(inv_id, msg)
            self.assertIn(due_date, msg)
            self.assertIn(f"{currency} 1250.50", msg)
            self.assertIn(f"{days_overdue} days overdue", msg)


class CommandLineTest(unittest.TestCase):
    def test_cli_execution_and_exit_code(self):
        res = subprocess.run(
            [sys.executable, "plan.py", "--invoices", "../data/invoices.json", "--sent", "../data/sent.json", "--today", "2026-10-12", "--out", "../actions.json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)

    def test_cli_invalid_today_exits_nonzero(self):
        res = subprocess.run(
            [sys.executable, "plan.py", "--invoices", "../data/invoices.json", "--sent", "../data/sent.json", "--today", "2026-02-30", "--out", "../actions.json"],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0)

    def test_cli_missing_file_exits_nonzero(self):
        res = subprocess.run(
            [sys.executable, "plan.py", "--invoices", "nonexistent.json", "--sent", "../data/sent.json", "--today", "2026-10-12", "--out", "../actions.json"],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
