import unittest

from synapse2action.demo import run_demo
from synapse2action.visualization import render_demo_html, render_g1_dashboard_html


class VisualizationTests(unittest.TestCase):
    def test_self_contained_demo_contains_frames_and_accessibility(self) -> None:
        html = render_demo_html(run_demo())

        self.assertIn("tabletop_frames", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('class="skip"', html)
        self.assertIn("button:disabled", html)
        self.assertIn("red_cube", html)
        self.assertIn("EXPECTED OUTCOME", html)
        self.assertNotIn("https://", html)

    def test_g1_dashboard_is_self_contained_and_exposes_evidence(self) -> None:
        html = render_g1_dashboard_html(
            {
                "harness": {
                    "accepted": True,
                    "final_state": "completed",
                    "trace": [{"event": "result", "state": "completed", "detail": "accepted"}],
                },
                "acceptance": {
                    "runtime": {
                        "maximum_round_trip_ms": 10_000,
                        "minimum_chunk_coverage_ms": 16_667,
                        "stale_fallbacks": 0,
                        "chunks_received": 3,
                    }
                },
                "simulator": {
                    "fell_at_seconds": None,
                    "grasped": True,
                    "released": True,
                    "maximum_object_height_m": 0.8,
                    "initial_object_position_xyz_m": [0.0, 0.0, 0.68],
                    "final_object_center_in_drop_zone": True,
                    "vla_authorized_frames": 100,
                },
                "eeg": {
                    "harness_replay": {
                        "decoded_examples": {"select": {"confidence": 0.98}}
                    }
                },
                "training": {"mse": 0.01, "arm_waist_mse": 0.02, "frames": 140, "finite": True},
                "frames": [{"stage": "ready", "data": "data:image/png;base64,iVBORw0KGgo="}],
            }
        )

        self.assertIn("MuJoCo Camera 01", html)
        self.assertIn("BrainFlow / LSL", html)
        self.assertIn("vla_authorized_frames", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn('class="skip"', html)
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
