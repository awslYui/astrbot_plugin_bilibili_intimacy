import unittest
from pathlib import Path

from calculator import clamp_budget, find_minimum_budget_for_target, plan_budget
from chart import render_benefit_curve


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
        self.assertAlmostEqual(plan.cat_food, 68.8096)
        self.assertEqual(plan.expected_total, 34668)

    def test_reference_38064_plan(self):
        plan = plan_budget(38064, quality="fresh", reminder_enabled=True, daily_banner_first=False)
        self.assertEqual(plan.box_count, 0)
        self.assertEqual(plan.expected_total, 195531)

    def test_governor_daily_first_gift(self):
        plan = plan_budget(
            220000,
            quality="normal",
            journey_mode="none",
            allocation="intimacy",
            daily_first_gift="governor",
            daily_first_multiplier=3,
        )
        self.assertEqual(plan.first_gift, "governor")
        self.assertEqual(plan.first_gift_paid, 199980)
        self.assertEqual(plan.daily_first_multiplier, 3)

    def test_admiral_highest_day_stacks_to_five_point_five_times(self):
        plan = plan_budget(22000, quality="normal", daily_first_gift="admiral", daily_first_multiplier=3)
        self.assertEqual(plan.first_gift_paid, 19980)
        self.assertGreaterEqual(plan.gift_intimacy, round(19980 * 5.5))

    def test_auto_uses_governor_for_highest_three_times_return(self):
        plan = plan_budget(
            200000, daily_first_gift="auto", daily_first_multiplier=3
        )
        self.assertEqual(plan.first_gift, "governor")
        self.assertEqual(plan.first_gift_paid, 199980)
        self.assertEqual(plan.expected_total, 1101441)

    def test_reverse_finds_the_exact_minimum_budget_and_plan(self):
        plan, maximum_plan = find_minimum_budget_for_target(
            100_000, daily_first_gift="auto", daily_first_multiplier=3
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertGreaterEqual(plan.expected_total, 100_000)
        self.assertLess(
            plan_budget(
                plan.budget - 1, daily_first_gift="auto", daily_first_multiplier=3
            ).expected_total,
            100_000,
        )
        self.assertGreaterEqual(maximum_plan.expected_total, 100_000)

    def test_curve_renderer_creates_a_png(self):
        image = render_benefit_curve(10_000, daily_first_gift="auto", daily_first_multiplier=3)
        self.assertTrue(image.is_file())
        self.assertEqual(image.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        Path(image).unlink()


if __name__ == "__main__":
    unittest.main()
