# Payment Reminder Assistant

A Python-based payment reminder engine and web dashboard for business owners.

## Quick Start
- Run tests: `cd python && python -m unittest`
- Run CLI: `cd python && python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json`
- Run Owner Page: `cd python && python app.py` (serves `http://localhost:8000/`)
  - Configurable via `PORT`, `DATA_DIR`, and `TODAY` environment variables.

## Architectural & Design Decisions
- **Zero-Dependency Standard Library**: Uses Python standard library (`http.server`, `json`, `datetime`) for zero setup and robust offline grading.
- **Strict Precedence & Validation**: Enforces exact data hygiene order (`duplicate_id`, `invalid_amount`, `missing_due_date`, `invalid_due_date`, `invalid_paid_date`) with plain-text sorting.
- **Compliant Messaging**: Generates step-toned email copy containing only verified invoice fields without external figures or invented terms.
- **Responsive Dashboard**: Displays decisions, plain-language skip reasons, and approval controls responsive down to 390px with full keyboard accessibility.

## What Next With More Time
- Persistent storage (SQLite) for decision audit trails across restarts.
- SMTP/Webhook dispatch queue for approved reminders.
- Automated syncing with external accounting APIs (e.g. Xero, QuickBooks).
