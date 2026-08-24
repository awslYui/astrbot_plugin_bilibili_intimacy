import unittest

from calculator import clamp_budget, plan_budget


class CalculatorTests(unittest.TestCase):
    def test_budget_is_clamped(self):
        self.assertEqual(clamp_budget("-1"), 0)
        self.assertEqual(clamp_budget("400000"), 300000)
        self.assertEqual(clamp_budget("invalid"), 0)

    def test_reference_1000_plan(self):
        plan = plan_budget(1000, daily_banner_first=True)
        self.assertEqual(plan.quality.key, "freeze")
        self.assertEqual(plan.box_count, 1)
        self.assertAlmostEqual(plan.cat_food, 46.2024)
        self.assertEqual(plan.expected_total, 12190)

    def test_reference_5639_plan(self):
        plan = plan_budget(5639, daily_banner_first=False)
        self.assertEqual(plan.quality.key, "fresh")
        self.assertEqual(plan.box_count, 4)
        self.assertEqual(plan.expected_total, 34668)

    def test_reference_38064_plan(self):
        plan = plan_budget(38064, quality="fresh", reminder_enabled=True, daily_banner_first=False)
        self.assertEqual(plan.box_count, 0)
        self.assertEqual(plan.expected_total, 195531)


if __name__ == "__main__":
    unittest.main()
