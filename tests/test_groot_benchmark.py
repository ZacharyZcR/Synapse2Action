import unittest

from synapse2action.groot_benchmark import summarize_groot_episodes, wilson_interval


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


if __name__ == "__main__":
    unittest.main()
