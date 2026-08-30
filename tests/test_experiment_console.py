from importlib.util import module_from_spec, spec_from_file_location
from unittest.mock import patch
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
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
        self.assertIn("授权并运行", html)
        self.assertIn("Authorize run", html)
        self.assertIn('id="stop"', html)
        self.assertIn("仿真控制，不是真机急停", html)
        self.assertIn('id="language"', html)
        self.assertIn("GR00T N1.6 + MockPlanner + scripted intent", html)
        self.assertIn("GR00T N1.6 + live LLM Planner + scripted intent", html)
        self.assertIn("MuJoCo 机器人环境", html)
        self.assertIn("/api/run", html)
        self.assertIn("/api/state", html)
        self.assertIn("/api/frame", html)
        self.assertIn("/api/stop", html)
        self.assertIn("/api/history", html)
        self.assertIn("/api/video/", html)
        self.assertIn('id="replay"', html)
        self.assertIn("[hidden]{display:none!important}", html)
        self.assertIn("encodeURIComponent(token)", html)
        self.assertIn("s.log.join('\\n')", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertNotIn("https://", html)

    def test_controller_starts_with_eight_pending_stages(self) -> None:
        controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")
        state = controller.snapshot()

        self.assertFalse(state["running"])
        self.assertEqual(len(state["stages"]), 8)
        self.assertTrue(all(stage["status"] == "pending" for stage in state["stages"]))

    def test_idle_controller_rejects_stop(self) -> None:
        controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")

        self.assertFalse(controller.stop())
        self.assertFalse(controller.snapshot()["stopped"])

    def test_readiness_blocks_run_without_required_runtime(self) -> None:
        with patch.object(MODULE.shutil, "which", return_value=None), patch.dict(MODULE.os.environ, {}, clear=True):
            controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")

        self.assertFalse(controller.snapshot()["ready"])
        self.assertFalse(controller.start())

    def test_groot_local_profile_uses_installed_model_without_planner_key(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            for relative in (
                "simulation/vendor/Isaac-GR00T-N1.6/.venv/bin/python",
                "simulation/vendor/GR00T-WholeBodyControl-N1.6/.venv_eval/bin/python",
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (project / "simulation/vendor/models/GR00T-N1.6-G1-PnPAppleToPlate-CW").mkdir(
                parents=True
            )
            controller = MODULE.ExperimentController(
                project, "", "/model", "test", "groot-local"
            )

            state = controller.snapshot()
        self.assertTrue(state["ready"])
        self.assertEqual(state["profile"], "groot-local")

    def test_groot_live_planner_requires_endpoint_but_not_mock_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            for relative in (
                "simulation/vendor/Isaac-GR00T-N1.6/.venv/bin/python",
                "simulation/vendor/GR00T-WholeBodyControl-N1.6/.venv_eval/bin/python",
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (project / "simulation/vendor/models/GR00T-N1.6-G1-PnPAppleToPlate-CW").mkdir(
                parents=True
            )
            missing = MODULE.ExperimentController(
                project, "", "/model", "test", "groot-live-planner"
            )
            with patch.dict(MODULE.os.environ, {"S2A_PLANNER_API_KEY": "test-key"}):
                configured = MODULE.ExperimentController(
                    project,
                    "http://127.0.0.1:18765/v1",
                    "/model",
                    "test",
                    "groot-live-planner",
                )

        self.assertFalse(missing.snapshot()["ready"])
        self.assertTrue(configured.snapshot()["ready"])

    def test_groot_history_pairs_seeded_evidence_with_video(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            benchmark = project / "reports/simulation/groot-benchmark-phase1"
            videos = project / "reports/simulation/groot-evidence-video"
            web = project / "reports/simulation/groot-evidence-video-web"
            benchmark.mkdir(parents=True)
            videos.mkdir(parents=True)
            web.mkdir(parents=True)
            for offset, seed in enumerate((1001, 1002)):
                video = videos / f"capture-{seed}.mp4"
                video.touch()
                evidence = benchmark / f"evidence-seed-{seed}.json"
                evidence.write_text(
                    json.dumps(
                        {
                            "episodes": [
                                {
                                    "seed": seed,
                                    "stable_on_plate": seed == 1002,
                                    "lifted": seed == 1002,
                                    "remained_standing": True,
                                    "maximum_lift_m": 0.11 if seed == 1002 else 0.02,
                                }
                            ]
                        }
                    )
                )
                timestamp = 100.0 + offset * 100
                os.utime(video, (timestamp, timestamp))
                os.utime(evidence, (timestamp + 1, timestamp + 1))
            (web / "seed-1002.webm").touch()

            history = MODULE.groot_history(project)

        self.assertEqual([run["seed"] for run in history], [1001, 1002])
        self.assertTrue(all(run["video"] for run in history))
        self.assertTrue(next(run for run in history if run["seed"] == 1002)["lifted"])
        self.assertEqual(next(run for run in history if run["seed"] == 1002)["webm"], "seed-1002.webm")

    def test_video_range_supports_mp4_tail_index_requests(self) -> None:
        self.assertEqual(MODULE.parse_byte_range("bytes=-1024", 6000), (4976, 5999, True))
        self.assertEqual(MODULE.parse_byte_range("bytes=1024-", 6000), (1024, 5999, True))
        self.assertEqual(MODULE.parse_byte_range(None, 6000), (0, 5999, False))

    def test_controller_keeps_only_latest_log_for_each_stage(self) -> None:
        controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")

        controller.update("llm_planner", "running")
        controller.update("llm_planner", "running", "provider · model · … ms")
        controller.update("llm_planner", "completed", "provider · model · 42 ms")

        state = controller.snapshot()
        self.assertEqual(state["log"], ["[llm_planner] completed: provider · model · 42 ms"])

    def test_controller_does_not_log_unchanged_pending_stage(self) -> None:
        controller = MODULE.ExperimentController(ROOT, "http://127.0.0.1:18765/v1", "/model", "test")

        controller.update("vla", "pending")

        self.assertEqual(controller.snapshot()["log"], [])

    def test_mujoco_runner_writes_atomic_live_frames(self) -> None:
        source = (ROOT / "simulation" / "g1_mujoco_pick_place.py").read_text()

        self.assertIn('temporary.replace(args.visualization_directory / "live.png")', source)
        self.assertIn("render_live_frames", source)
        self.assertIn("Thread(target=render_live_frames", source)
        self.assertIn("live_qpos[:] = data.qpos", source)
        self.assertIn("height=180, width=320", source)
