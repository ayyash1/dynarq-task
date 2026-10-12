// The owner's page (part 2). Uses only node:http, no framework needed.
//
// Run from inside typescript/:  npm run app
//
// Environment variables:
//   PORT      port to listen on, default 8000
//   DATA_DIR  folder with invoices.json and sent.json, default ../data
//   TODAY     date as YYYY-MM-DD, default the real date

import { createServer } from "node:http";

const PORT = Number(process.env.PORT || "8000");
const DATA_DIR = process.env.DATA_DIR || "../data";
const TODAY = process.env.TODAY || localToday();

function localToday(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const server = createServer((req, res) => {
  if (req.method !== "GET" || req.url !== "/") {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }
  // TODO: use buildPlan from plan.ts and show today's plan (README part 2).
  const body =
    '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    "<title>Payment reminders</title></head><body>" +
    "<h1>Payment reminders</h1>" +
    `<p>Placeholder page. Today is ${escapeHtml(TODAY)}. Data folder: ${escapeHtml(DATA_DIR)}.</p>` +
    "</body></html>";
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
});

server.listen(PORT, () => {
  console.log(`Serving on http://localhost:${PORT}/`);
});
