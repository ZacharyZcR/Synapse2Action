import unittest

from synapse2action.demo import run_demo
from synapse2action.visualization import render_demo_html


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


if __name__ == "__main__":
    unittest.main()
