"""Run from inside python/:  python -m unittest

This example only checks the shape of the output, so it passes on the starter.
Add your own tests for the rules.
"""

import unittest

from plan import build_plan


class ShapeTest(unittest.TestCase):
    def test_empty_input_gives_empty_plan(self):
        plan = build_plan([], [], "2026-10-12")
        self.assertEqual(plan, {"today": "2026-10-12", "actions": [], "skipped": []})


if __name__ == "__main__":
    unittest.main()
