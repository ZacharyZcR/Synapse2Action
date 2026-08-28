from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("experiment_console", ROOT / "simulation" / "experiment_console.py")
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExperimentConsoleTests(unittest.TestCase):
    def test_console_exposes_real_run_controls_and_live_viewer(self) -> None:
        html = MODULE.console_html()

        self.assertIn('id="start"', html)
        self.assertIn("开始真实实验", html)
        self.assertIn("Start real experiment", html)
        self.assertIn('id="language"', html)
        self.assertIn("MAMEM SSVEP Database", html)
        self.assertIn("MuJoCo 实时环境", html)
        self.assertIn("/api/run", html)
        self.assertIn("/api/state", html)
        self.assertIn("/api/frame", html)
        self.assertIn("encodeURIComponent(token)", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertNotIn("https://", html)

    def test_controller_starts_with_seven_pending_stages(self) -> None:
        controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")
        state = controller.snapshot()

        self.assertFalse(state["running"])
        self.assertEqual(len(state["stages"]), 7)
        self.assertTrue(all(stage["status"] == "pending" for stage in state["stages"]))

    def test_mujoco_runner_writes_atomic_live_frames(self) -> None:
        source = (ROOT / "simulation" / "g1_mujoco_pick_place.py").read_text()

        self.assertIn('temporary.replace(args.visualization_directory / "live.png")', source)
        self.assertIn("render_live_frames", source)
        self.assertIn("Thread(target=render_live_frames", source)
        self.assertIn("live_qpos[:] = data.qpos", source)
        self.assertIn("height=180, width=320", source)
