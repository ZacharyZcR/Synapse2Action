import unittest

from synapse2action.groot_benchmark import (
    compare_groot_counterfactuals,
    summarize_groot_episodes,
    wilson_interval,
)


def episode(seed: int, *, grasped: bool, lifted: bool) -> dict[str, object]:
    return {
        "seed": seed,
        "gripper_contact": True,
        "grasped": grasped,
        "lifted": lifted,
        "contacted_plate": False,
        "released_after_contact": False,
        "stable_on_plate": False,
        "remained_standing": True,
        "maximum_lift_m": 0.12 if lifted else 0.04,
        "apple_plate_progress_m": 0.3,
        "minimum_apple_plate_xy_distance_m": 0.5,
    }


class GrootBenchmarkTests(unittest.TestCase):
    def test_summarizes_stage_rates_and_motion_metrics(self) -> None:
        report = summarize_groot_episodes(
            [episode(10, grasped=True, lifted=True), episode(11, grasped=False, lifted=False)]
        )
        self.assertEqual(report["episodes"], 2)
        self.assertEqual(report["stage_success_rate"]["grasped"], 0.5)
        self.assertEqual(report["stage_success_rate"]["remained_standing"], 1.0)
        self.assertEqual(report["strict_success_rate"], 0.0)
        self.assertLess(report["stage_success_95ci"]["grasped"][0], 0.5)
        self.assertGreater(report["stage_success_95ci"]["grasped"][1], 0.5)
        self.assertAlmostEqual(report["mean_maximum_lift_m"], 0.08)

    def test_wilson_interval_is_bounded_for_extreme_rates(self) -> None:
        self.assertEqual(wilson_interval(0, 20)[0], 0.0)
        self.assertEqual(wilson_interval(20, 20)[1], 1.0)

    def test_rejects_duplicate_seeds(self) -> None:
        with self.assertRaises(ValueError):
            summarize_groot_episodes(
                [episode(7, grasped=True, lifted=True), episode(7, grasped=True, lifted=True)]
            )

    def test_rejects_empty_benchmark(self) -> None:
        with self.assertRaises(ValueError):
            summarize_groot_episodes([])

    def test_compares_seed_paired_lift_counterfactuals(self) -> None:
        baseline = [
            episode(10, grasped=True, lifted=False),
            episode(11, grasped=True, lifted=False),
        ]
        shorter_horizon = [
            episode(10, grasped=True, lifted=True),
            episode(11, grasped=True, lifted=False),
        ]

        report = compare_groot_counterfactuals(
            {"baseline": baseline, "short_horizon": shorter_horizon}
        )

        effect = report["effects_vs_baseline"]["short_horizon"]
        self.assertEqual(effect["lift_rate_delta"], 0.5)
        self.assertAlmostEqual(effect["mean_maximum_lift_m_delta"], 0.04)
        self.assertTrue(effect["paired_results"][0]["lifted_changed"])
        self.assertAlmostEqual(
            effect["paired_results"][0]["maximum_lift_m_delta"], 0.08
        )
        self.assertEqual(report["paired_seeds"], [10, 11])

    def test_counterfactuals_require_identical_seed_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "same order"):
            compare_groot_counterfactuals(
                {
                    "baseline": [episode(10, grasped=True, lifted=False)],
                    "changed": [episode(11, grasped=True, lifted=True)],
                }
            )


if __name__ == "__main__":
    unittest.main()
