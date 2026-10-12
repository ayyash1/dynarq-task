// Payment reminder rules engine (part 1).
//
// Run from inside typescript/ (after npm install):
//
//   npm run plan -- --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
//
// This starter only reads the files and writes an empty plan in the required shape.
// The rules are yours to build.

import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

export interface Plan {
  today: string;
  actions: unknown[];
  skipped: unknown[];
}

/**
 * Return the plan for `today`.
 * invoices: the list from invoices.json
 * sent: the list from sent.json
 * today: a date string, YYYY-MM-DD
 */
export function buildPlan(invoices: unknown[], sent: unknown[], today: string): Plan {
  // TODO: apply the rules in README.md part 1 and fill both lists,
  // sorted by invoice id. Each action also needs a message (part 3).
  void invoices;
  void sent;
  return { today, actions: [], skipped: [] };
}

export function readJson(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function main(): void {
  const { values } = parseArgs({
    options: {
      invoices: { type: "string" },
      sent: { type: "string" },
      today: { type: "string" },
      out: { type: "string" },
    },
  });
  if (!values.invoices || !values.sent || !values.today || !values.out) {
    console.error("Usage: npm run plan -- --invoices FILE --sent FILE --today YYYY-MM-DD --out FILE");
    process.exit(2);
  }
  const invoices = readJson(values.invoices) as unknown[];
  const sent = readJson(values.sent) as unknown[];
  const plan = buildPlan(invoices, sent, values.today);
  writeFileSync(values.out, JSON.stringify(plan, null, 2) + "\n", "utf-8");
}

// Run main() only when this file is started directly, not when a test imports it.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
