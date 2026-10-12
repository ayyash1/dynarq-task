"""Payment reminder rules engine (part 1 & 3).

Run from inside python/:

    python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, date


STEP_RANK = {
    "friendly": 1,
    "firm": 2,
    "final": 3,
}

STEP_APPROVAL = {
    "friendly": False,
    "firm": True,
    "final": True,
}


def parse_iso_date(date_str):
    """Parse a strict YYYY-MM-DD date string. Return date object or None."""
    if not isinstance(date_str, str):
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def generate_message(customer, invoice_id, due_date_str, currency, amount, days_overdue, step):
    """Generate compliant reminder message without any external figures or claims."""
    formatted_amount = f"{currency} {amount:.2f}"
    if step == "friendly":
        return (
            f"Dear {customer},\n"
            f"This is a friendly reminder that invoice {invoice_id} was due on {due_date_str} "
            f"and is now {days_overdue} days overdue. "
            f"The outstanding balance is {formatted_amount}. "
            f"Please arrange payment at your earliest convenience. Thank you."
        )
    elif step == "firm":
        return (
            f"Dear {customer},\n"
            f"We are writing to urgently request payment for invoice {invoice_id}, "
            f"which was due on {due_date_str} and is currently {days_overdue} days overdue. "
            f"The outstanding amount is {formatted_amount}. "
            f"Please settle this balance immediately."
        )
    elif step == "final":
        return (
            f"Dear {customer},\n"
            f"This is a final notice regarding overdue invoice {invoice_id}. "
            f"Payment was due on {due_date_str} and is currently {days_overdue} days overdue. "
            f"The total outstanding amount is {formatted_amount}. "
            f"Immediate settlement of this account is required."
        )
    return ""


def build_plan(invoices, sent, today_str):
    """Return the plan for `today` as a dict with keys today, actions and skipped.

    invoices: the list from invoices.json
    sent: the list from sent.json
    today_str: a date string, YYYY-MM-DD
    """
    today_date = parse_iso_date(today_str)
    if today_date is None:
        raise ValueError(f"Invalid today date: {today_str}")

    # Map sent entries by invoice_id to the highest sent step rank
    highest_sent_by_id = {}
    valid_invoice_ids = set()
    for inv in invoices:
        if isinstance(inv, dict) and "id" in inv:
            valid_invoice_ids.add(inv["id"])

    for s in sent:
        if not isinstance(s, dict):
            continue
        inv_id = s.get("invoice_id")
        step = s.get("step")
        # Ignore entries for invoice ids not in invoices.json or step not friendly/firm/final
        if inv_id in valid_invoice_ids and step in STEP_RANK:
            rank = STEP_RANK[step]
            if inv_id not in highest_sent_by_id or rank > highest_sent_by_id[inv_id]:
                highest_sent_by_id[inv_id] = rank

    # Count occurrences of invoice ids to detect duplicates
    id_counts = Counter()
    for inv in invoices:
        if isinstance(inv, dict) and "id" in inv:
            id_counts[inv["id"]] += 1

    actions = []
    skipped = []
    seen_skipped_ids = set()

    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        inv_id = inv.get("id")

        # 1. Bad data checks in strict order:
        # Check duplicate_id
        if inv_id is not None and id_counts[inv_id] > 1:
            if inv_id not in seen_skipped_ids:
                skipped.append({"invoice_id": inv_id, "reason": "duplicate_id"})
                seen_skipped_ids.add(inv_id)
            continue

        # Check invalid_amount: missing, not a JSON number (a string or true is not a number), or 0 or less
        amount = inv.get("amount")
        if (
            amount is None
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or math.isnan(amount)
            or math.isinf(amount)
            or amount <= 0
        ):
            if inv_id not in seen_skipped_ids:
                skipped.append({"invoice_id": inv_id, "reason": "invalid_amount"})
                seen_skipped_ids.add(inv_id)
            continue

        # Check missing_due_date: missing, null or an empty string
        if "due_date" not in inv or inv["due_date"] is None or inv["due_date"] == "":
            if inv_id not in seen_skipped_ids:
                skipped.append({"invoice_id": inv_id, "reason": "missing_due_date"})
                seen_skipped_ids.add(inv_id)
            continue

        # Check invalid_due_date: not a real date in the form YYYY-MM-DD
        due_date_str = inv["due_date"]
        due_date = parse_iso_date(due_date_str)
        if due_date is None:
            if inv_id not in seen_skipped_ids:
                skipped.append({"invoice_id": inv_id, "reason": "invalid_due_date"})
                seen_skipped_ids.add(inv_id)
            continue

        # Check invalid_paid_date: not null and is not a real YYYY-MM-DD date, or after today
        paid_date_raw = inv.get("paid_date")
        paid_date = None
        if paid_date_raw is not None:
            paid_date = parse_iso_date(paid_date_raw)
            if paid_date is None or paid_date > today_date:
                if inv_id not in seen_skipped_ids:
                    skipped.append({"invoice_id": inv_id, "reason": "invalid_paid_date"})
                    seen_skipped_ids.add(inv_id)
                continue

        # 2. Paid check: if paid_date is a date on or before today, plan nothing
        if paid_date is not None:
            continue

        # 3. Days overdue & "Not yet"
        days_overdue = (today_date - due_date).days
        if days_overdue < 3:
            continue

        # Determine highest step reached
        if days_overdue >= 24:
            reached_step = "final"
        elif days_overdue >= 10:
            reached_step = "firm"
        else:
            reached_step = "friendly"

        reached_rank = STEP_RANK[reached_step]
        highest_sent_rank = highest_sent_by_id.get(inv_id, 0)

        # 4. If reached step or a higher one is already sent, plan nothing
        if highest_sent_rank >= reached_rank:
            continue

        customer = inv.get("customer", "")
        currency = inv.get("currency", "")
        message = generate_message(
            customer=customer,
            invoice_id=inv_id,
            due_date_str=due_date_str,
            currency=currency,
            amount=amount,
            days_overdue=days_overdue,
            step=reached_step,
        )

        actions.append({
            "invoice_id": inv_id,
            "step": reached_step,
            "needs_approval": STEP_APPROVAL[reached_step],
            "days_overdue": days_overdue,
            "message": message,
        })

    # Sort both lists by invoice_id character by character in plain text order
    actions.sort(key=lambda x: str(x["invoice_id"]))
    skipped.sort(key=lambda x: str(x["invoice_id"]))

    return {
        "today": today_str,
        "actions": actions,
        "skipped": skipped,
    }


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        sys.stderr.write(f"Error reading JSON from '{path}': {e}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Plan today's payment reminders.")
    parser.add_argument("--invoices", required=True, help="path to invoices.json")
    parser.add_argument("--sent", required=True, help="path to sent.json")
    parser.add_argument("--today", required=True, help="date as YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="path to write the plan JSON")
    args = parser.parse_args()

    today_date = parse_iso_date(args.today)
    if today_date is None:
        sys.stderr.write(f"Error: --today '{args.today}' is not a valid date in YYYY-MM-DD format.\n")
        sys.exit(1)

    invoices = read_json(args.invoices)
    sent = read_json(args.sent)

    try:
        plan = build_plan(invoices, sent, args.today)
    except Exception as e:
        sys.stderr.write(f"Error building plan: {e}\n")
        sys.exit(1)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")
    except Exception as e:
        sys.stderr.write(f"Error writing output to '{args.out}': {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
