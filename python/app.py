"""The owner's page (part 2). Standard library only, no install needed.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date
"""

import os
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "../data")
TODAY = os.environ.get("TODAY") or date.today().isoformat()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        # TODO: use build_plan from plan.py and show today's plan (README part 2).
        body = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Payment reminders</title></head><body>"
            "<h1>Payment reminders</h1>"
            f"<p>Placeholder page. Today is {escape(TODAY)}. Data folder: {escape(DATA_DIR)}.</p>"
            "</body></html>"
        )
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
