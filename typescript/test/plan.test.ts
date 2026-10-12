// Run from inside typescript/:  npm test
//
// This example only checks the shape of the output, so it passes on the starter.
// Add your own tests for the rules. If you add more test files, add them to the
// "test" script in package.json.

import assert from "node:assert/strict";
import { test } from "node:test";
import { buildPlan } from "../src/plan";

test("empty input gives an empty plan", () => {
  assert.deepEqual(buildPlan([], [], "2026-10-12"), {
    today: "2026-10-12",
    actions: [],
    skipped: [],
  });
});
