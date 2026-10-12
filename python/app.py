"""The owner's page (part 2). Standard library only, no install needed.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date
"""

import json
import os
import sys
import urllib.parse
from datetime import date
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from plan import build_plan, parse_iso_date

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "../data")
TODAY = os.environ.get("TODAY") or date.today().isoformat()

# In-memory store for owner's decisions (persists while server runs)
# Maps invoice_id -> "approved" | "rejected"
DECISIONS = {}

PLAIN_REASONS = {
    "duplicate_id": "Duplicate invoice ID found in dataset (all occurrences skipped)",
    "invalid_amount": "Amount is missing, non-numeric, or zero / negative",
    "missing_due_date": "Due date is missing, null, or empty",
    "invalid_due_date": "Due date is not a valid date (expected YYYY-MM-DD)",
    "invalid_paid_date": "Paid date is not a valid date or is set in the future",
}


def load_plan_data(data_dir, today_str):
    """Load data from invoices.json and sent.json and build plan using rules engine."""
    inv_path = os.path.join(data_dir, "invoices.json")
    sent_path = os.path.join(data_dir, "sent.json")

    if not os.path.exists(inv_path):
        return None, f"Invoices file not found at '{inv_path}'"
    if not os.path.exists(sent_path):
        return None, f"Sent reminders file not found at '{sent_path}'"

    try:
        with open(inv_path, "r", encoding="utf-8") as f:
            invoices = json.load(f)
    except Exception as e:
        return None, f"Could not read invoices.json: {e}"

    try:
        with open(sent_path, "r", encoding="utf-8") as f:
            sent = json.load(f)
    except Exception as e:
        return None, f"Could not read sent.json: {e}"

    try:
        plan = build_plan(invoices, sent, today_str)
        # Attach customer and currency details to actions for display
        inv_map = {inv["id"]: inv for inv in invoices if isinstance(inv, dict) and "id" in inv}
        for act in plan.get("actions", []):
            inv_info = inv_map.get(act["invoice_id"], {})
            act["customer"] = inv_info.get("customer", "Unknown")
            act["amount"] = inv_info.get("amount", 0.0)
            act["currency"] = inv_info.get("currency", "")
        return plan, None
    except Exception as e:
        return None, f"Error building plan: {e}"


def render_html_page(plan, error_msg, today_str, data_dir, decisions):
    """Generate accessible, responsive, modern UI for the business owner."""
    actions = plan.get("actions", []) if plan else []
    skipped = plan.get("skipped", []) if plan else []

    # Calculate metrics
    approved_count = sum(1 for a in actions if decisions.get(a["invoice_id"]) == "approved")
    rejected_count = sum(1 for a in actions if decisions.get(a["invoice_id"]) == "rejected")
    pending_count = sum(1 for a in actions if a.get("needs_approval") and a["invoice_id"] not in decisions)

    actions_html = ""
    if actions:
        for idx, act in enumerate(actions):
            inv_id = act["invoice_id"]
            cust = escape(act.get("customer", ""))
            amt = f"{act.get('currency', '')} {act.get('amount', 0.0):,.2f}"
            days = act["days_overdue"]
            step = act["step"]
            needs_app = act.get("needs_approval", False)
            decision = decisions.get(inv_id)
            msg = escape(act.get("message", ""))

            step_badge_class = {
                "friendly": "badge-friendly",
                "firm": "badge-firm",
                "final": "badge-final"
            }.get(step, "badge-default")

            decision_controls = ""
            if needs_app:
                if decision == "approved":
                    decision_controls = f"""
                    <div class="decision-group">
                      <div class="current-status">
                        <span class="status-pill status-approved" id="status-{inv_id}">✓ Approved</span>
                      </div>
                      <div class="action-btn-row">
                        <button type="button" class="btn btn-undo"
                                onclick="recordDecision('{inv_id}', 'undo')"
                                aria-label="Undo decision for {inv_id}">
                          ↺ Undo Decision
                        </button>
                      </div>
                    </div>
                    """
                elif decision == "rejected":
                    decision_controls = f"""
                    <div class="decision-group">
                      <div class="current-status">
                        <span class="status-pill status-rejected" id="status-{inv_id}">✕ Rejected</span>
                      </div>
                      <div class="action-btn-row">
                        <button type="button" class="btn btn-undo"
                                onclick="recordDecision('{inv_id}', 'undo')"
                                aria-label="Undo decision for {inv_id}">
                          ↺ Undo Decision
                        </button>
                      </div>
                    </div>
                    """
                else:
                    decision_controls = f"""
                    <div class="decision-group">
                      <div class="current-status">
                        <span class="status-pill status-pending" id="status-{inv_id}">⏳ Awaiting Decision</span>
                      </div>
                      <div class="action-btn-row">
                        <button type="button" class="btn btn-approve"
                                onclick="recordDecision('{inv_id}', 'approved')"
                                aria-label="Approve reminder for {inv_id}">
                          Approve
                        </button>
                        <button type="button" class="btn btn-reject"
                                onclick="recordDecision('{inv_id}', 'rejected')"
                                aria-label="Reject reminder for {inv_id}">
                          Reject
                        </button>
                      </div>
                    </div>
                    """
            else:
                decision_controls = """
                <div class="decision-group">
                  <span class="status-pill status-auto">⚡ Automatic (No approval required)</span>
                </div>
                """

            actions_html += f"""
            <article class="action-card" id="card-{inv_id}" tabindex="0" aria-label="Reminder for {cust}, invoice {inv_id}">
              <div class="card-header">
                <div class="card-title-row">
                  <h3 class="customer-name">{cust}</h3>
                  <span class="badge {step_badge_class}">{step.upper()}</span>
                </div>
                <div class="invoice-id-tag">Invoice: <strong>{inv_id}</strong></div>
              </div>

              <div class="card-stats">
                <div class="stat-item">
                  <span class="stat-label">Amount</span>
                  <span class="stat-value">{amt}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Days Overdue</span>
                  <span class="stat-value overdue-tag">{days} days</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Step Policy</span>
                  <span class="stat-value">{'Needs approval' if needs_app else 'Auto-send'}</span>
                </div>
              </div>

              {decision_controls}

              <details class="message-accordion">
                <summary class="message-summary">View Email Message Content</summary>
                <div class="message-box">
                  <pre>{msg}</pre>
                </div>
              </details>
            </article>
            """
    else:
        actions_html = """
        <div class="empty-state" role="status">
          <div class="empty-icon">✓</div>
          <h3>All Caught Up</h3>
          <p>There are no payment reminders scheduled for today. All eligible invoices are either paid or up to date.</p>
        </div>
        """

    skipped_html = ""
    if skipped:
        rows = ""
        for s in skipped:
            code = s.get("reason", "unknown")
            plain_desc = PLAIN_REASONS.get(code, code.replace("_", " ").capitalize())
            rows += f"""
            <tr>
              <td><span class="mono-badge">{escape(s.get('invoice_id', ''))}</span></td>
              <td><span class="reason-pill">{escape(plain_desc)}</span></td>
              <td class="code-col"><code>{escape(code)}</code></td>
            </tr>
            """
        skipped_html = f"""
        <div class="table-responsive">
          <table class="data-table" aria-label="Skipped Invoices Table">
            <thead>
              <tr>
                <th scope="col">Invoice ID</th>
                <th scope="col">Reason (Plain Words)</th>
                <th scope="col">Internal Code</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
        """
    else:
        skipped_html = """
        <div class="empty-state-subtle">
          <p>No invoices were skipped. All entries passed data validation.</p>
        </div>
        """

    error_banner = ""
    if error_msg:
        error_banner = f"""
        <div class="alert-box alert-error" role="alert">
          <div class="alert-icon">⚠️</div>
          <div class="alert-content">
            <h4>Data Error</h4>
            <p>{escape(error_msg)}</p>
            <p class="alert-hint">Please verify that invoices.json and sent.json exist in <code>{escape(data_dir)}</code> and contain valid JSON format.</p>
          </div>
        </div>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Payment Reminders Assistant | Daily Plan</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --focus-ring: #60a5fa;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 1rem;
      min-height: 100vh;
    }}

    .container {{
      max-width: 900px;
      margin: 0 auto;
    }}

    header.main-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      padding: 1.25rem 0;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
    }}

    h1 {{
      font-size: 1.5rem;
      font-weight: 700;
      color: #fff;
    }}

    .date-badge {{
      background: #1e293b;
      border: 1px solid var(--card-border);
      padding: 0.4rem 0.8rem;
      border-radius: 9999px;
      font-size: 0.875rem;
      color: var(--text-muted);
    }}
    .date-badge strong {{ color: #60a5fa; }}

    .metrics-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 0.75rem;
      margin-bottom: 2rem;
    }}

    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 0.85rem;
      border-radius: 0.5rem;
      text-align: center;
    }}

    .metric-num {{
      font-size: 1.4rem;
      font-weight: 700;
      line-height: 1.2;
    }}
    .metric-label {{
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .alert-box {{
      display: flex;
      gap: 1rem;
      padding: 1rem;
      border-radius: 0.5rem;
      margin-bottom: 1.5rem;
    }}
    .alert-error {{
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid var(--danger);
      color: #fca5a5;
    }}
    .alert-icon {{ font-size: 1.5rem; }}
    .alert-hint {{ font-size: 0.85rem; margin-top: 0.25rem; color: var(--text-muted); }}

    section {{ margin-bottom: 2.5rem; }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }}
    h2 {{
      font-size: 1.25rem;
      font-weight: 600;
      color: #e2e8f0;
    }}

    .action-grid {{
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}

    .action-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.75rem;
      padding: 1.25rem;
      transition: border-color 0.2s;
    }}
    .action-card:focus-visible {{
      outline: 2px solid var(--focus-ring);
      outline-offset: 2px;
    }}
    .action-card:hover {{
      border-color: #475569;
    }}

    .card-header {{
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      margin-bottom: 0.85rem;
    }}
    .card-title-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }}
    .customer-name {{
      font-size: 1.15rem;
      font-weight: 600;
      color: #fff;
    }}
    .invoice-id-tag {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    .badge {{
      display: inline-block;
      padding: 0.25rem 0.65rem;
      border-radius: 0.375rem;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.05em;
    }}
    .badge-friendly {{ background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6; }}
    .badge-firm {{ background: rgba(245, 158, 11, 0.2); color: #fcd34d; border: 1px solid #f59e0b; }}
    .badge-final {{ background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }}

    .card-stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.5rem;
      background: rgba(15, 23, 42, 0.6);
      padding: 0.75rem;
      border-radius: 0.5rem;
      margin-bottom: 1rem;
    }}
    .stat-label {{
      display: block;
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
    }}
    .stat-value {{
      font-size: 0.95rem;
      font-weight: 600;
    }}
    .overdue-tag {{ color: #fbbf24; }}

    .decision-group {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      padding: 0.75rem 0;
      border-top: 1px solid #334155;
      margin-bottom: 0.75rem;
    }}
    .action-btn-row {{
      display: flex;
      gap: 0.5rem;
    }}
    .btn {{
      padding: 0.45rem 0.9rem;
      font-size: 0.85rem;
      font-weight: 600;
      border-radius: 0.375rem;
      cursor: pointer;
      border: 1px solid transparent;
      transition: background 0.15s, color 0.15s;
    }}
    .btn:focus-visible {{
      outline: 2px solid var(--focus-ring);
      outline-offset: 2px;
    }}
    .btn-approve {{
      background: #065f46;
      color: #a7f3d0;
      border-color: #059669;
    }}
    .btn-approve:hover {{ background: #047857; color: #fff; }}

    .btn-reject {{
      background: #7f1d1d;
      color: #fecaca;
      border-color: #dc2626;
    }}
    .btn-reject:hover {{ background: #991b1b; color: #fff; }}

    .btn-undo {{
      background: #1e293b;
      color: #cbd5e1;
      border: 1px solid var(--card-border);
      font-weight: 500;
    }}
    .btn-undo:hover {{
      background: #334155;
      color: #fff;
    }}

    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      font-size: 0.85rem;
      font-weight: 600;
      padding: 0.3rem 0.6rem;
      border-radius: 0.375rem;
    }}
    .status-pending {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
    .status-approved {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .status-rejected {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .status-auto {{ background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }}

    .message-accordion {{
      background: #0f172a;
      border: 1px solid var(--card-border);
      border-radius: 0.375rem;
      overflow: hidden;
    }}
    .message-summary {{
      padding: 0.6rem 0.85rem;
      font-size: 0.8rem;
      color: var(--text-muted);
      cursor: pointer;
      user-select: none;
    }}
    .message-summary:focus-visible {{
      outline: 2px solid var(--focus-ring);
    }}
    .message-box {{
      padding: 0.85rem;
      border-top: 1px solid var(--card-border);
    }}
    .message-box pre {{
      font-family: inherit;
      white-space: pre-wrap;
      font-size: 0.85rem;
      color: #e2e8f0;
      line-height: 1.45;
    }}

    .table-responsive {{
      overflow-x: auto;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.5rem;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }}
    .data-table th, .data-table td {{
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--card-border);
    }}
    .data-table th {{
      background: #111827;
      color: var(--text-muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .mono-badge {{
      font-family: monospace;
      background: #0f172a;
      padding: 0.2rem 0.4rem;
      border-radius: 0.25rem;
      font-weight: 600;
    }}
    .reason-pill {{ color: #f87171; font-weight: 500; }}
    .code-col code {{ font-size: 0.75rem; color: var(--text-muted); }}

    .empty-state {{
      background: var(--card-bg);
      border: 1px dashed var(--card-border);
      border-radius: 0.75rem;
      padding: 2.5rem 1rem;
      text-align: center;
    }}
    .empty-icon {{
      font-size: 2.5rem;
      color: var(--success);
      margin-bottom: 0.5rem;
    }}
    .empty-state h3 {{ font-size: 1.15rem; margin-bottom: 0.25rem; }}
    .empty-state p {{ color: var(--text-muted); font-size: 0.875rem; max-width: 400px; margin: 0 auto; }}

    .empty-state-subtle {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      padding: 1rem;
      border-radius: 0.5rem;
      color: var(--text-muted);
      font-size: 0.875rem;
      text-align: center;
    }}

    @media (max-width: 450px) {{
      body {{ padding: 0.5rem; }}
      h1 {{ font-size: 1.25rem; }}
      .card-stats {{ grid-template-columns: 1fr; gap: 0.35rem; }}
      .card-title-row {{ flex-direction: column; align-items: flex-start; }}
      .decision-group {{ flex-direction: column; align-items: stretch; }}
      .action-btn-row {{ width: 100%; }}
      .action-btn-row .btn {{ flex: 1; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="main-header" role="banner">
      <div>
        <h1>Payment Reminders Assistant</h1>
        <p style="font-size: 0.85rem; color: var(--text-muted);">Daily Morning Operations & Approval Dashboard</p>
      </div>
      <div class="date-badge" aria-label="Current date">
        Date: <strong>{escape(today_str)}</strong>
      </div>
    </header>

    {error_banner}

    <section aria-labelledby="metrics-heading">
      <h2 id="metrics-heading" class="sr-only" style="display:none;">Summary Metrics</h2>
      <div class="metrics-bar">
        <div class="metric-card">
          <div class="metric-num" style="color: #60a5fa;">{len(actions)}</div>
          <div class="metric-label">Reminders Today</div>
        </div>
        <div class="metric-card">
          <div class="metric-num" style="color: #fbbf24;">{pending_count}</div>
          <div class="metric-label">Pending Approval</div>
        </div>
        <div class="metric-card">
          <div class="metric-num" style="color: #34d399;">{approved_count}</div>
          <div class="metric-label">Approved</div>
        </div>
        <div class="metric-card">
          <div class="metric-num" style="color: #f87171;">{rejected_count}</div>
          <div class="metric-label">Rejected</div>
        </div>
        <div class="metric-card">
          <div class="metric-num" style="color: #cbd5e1;">{len(skipped)}</div>
          <div class="metric-label">Skipped (Bad Data)</div>
        </div>
      </div>
    </section>

    <main>
      <section aria-labelledby="actions-heading">
        <div class="section-header">
          <h2 id="actions-heading">Today's Reminders Plan</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">{len(actions)} action(s) planned</span>
        </div>
        <div class="action-grid">
          {actions_html}
        </div>
      </section>

      <section aria-labelledby="skipped-heading">
        <div class="section-header">
          <h2 id="skipped-heading">Skipped Invoices (Data Issues)</h2>
          <span style="font-size: 0.85rem; color: var(--text-muted);">{len(skipped)} issue(s) detected</span>
        </div>
        {skipped_html}
      </section>
    </main>
  </div>

  <script>
    async function recordDecision(invoiceId, decision) {{
      try {{
        const response = await fetch('/api/decide', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ invoice_id: invoiceId, decision: decision }})
        }});
        if (response.ok) {{
          window.location.reload();
        }}
      }} catch (err) {{
        console.error('Failed to submit decision:', err);
      }}
    }}
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            plan, error_msg = load_plan_data(DATA_DIR, TODAY)
            body = render_html_page(plan, error_msg, TODAY, DATA_DIR, DECISIONS)
            data = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif parsed.path == "/api/plan":
            plan, error_msg = load_plan_data(DATA_DIR, TODAY)
            payload = {
                "plan": plan,
                "error": error_msg,
                "decisions": DECISIONS,
            }
            data = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/decide":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                inv_id = data.get("invoice_id")
                decision = data.get("decision")
                if inv_id and decision in ("approved", "rejected"):
                    DECISIONS[inv_id] = decision
                    res_body = json.dumps({"ok": True, "decisions": DECISIONS}).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(res_body)))
                    self.end_headers()
                    self.wfile.write(res_body)
                    return
                elif inv_id and decision in ("undo", "reset"):
                    DECISIONS.pop(inv_id, None)
                    res_body = json.dumps({"ok": True, "decisions": DECISIONS}).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(res_body)))
                    self.end_headers()
                    self.wfile.write(res_body)
                    return
            except Exception as e:
                pass
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid decision payload")
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def main():
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/ (PORT={PORT}, DATA_DIR={DATA_DIR}, TODAY={TODAY})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


if __name__ == "__main__":
    main()
