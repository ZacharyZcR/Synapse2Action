from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "check_whole_body_readiness", ROOT / "simulation/check_whole_body_readiness.py"
)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WholeBodyReadinessTests(unittest.TestCase):
    @patch.object(MODULE.subprocess, "run")
    def test_requires_locked_sources_and_linux(self, run) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            lock = {
                "open_wbt": {"commit": "wbt"},
                "open_track": {"commit": "track"},
                "unitree_rl_gym": {"commit": "unitree"},
                "unitree_rl_lab": {"commit": "lab"},
                "unitree_mujoco": {"commit": "mujoco"},
            }
            lock_path = project / "simulation/whole_body.lock.json"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(json.dumps(lock))
            for relative in MODULE.REQUIRED_PATHS.values():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            run.side_effect = [
                subprocess.CompletedProcess([], 0, "wbt\n", ""),
                subprocess.CompletedProcess([], 0, "track\n", ""),
                subprocess.CompletedProcess([], 0, "unitree\n", ""),
                subprocess.CompletedProcess([], 0, "lab\n", ""),
                subprocess.CompletedProcess([], 0, "mujoco\n", ""),
            ]

            report = MODULE.local_readiness(project, system="Linux")

        self.assertTrue(report["ready"])
        self.assertIsNone(report["validated_capability"])

    @patch.object(MODULE.subprocess, "run")
    def test_rejects_wrong_platform_or_commit(self, run) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            lock_path = project / "simulation/whole_body.lock.json"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(json.dumps({
                "open_wbt": {"commit": "a"},
                "open_track": {"commit": "b"},
                "unitree_rl_gym": {"commit": "c"},
                "unitree_rl_lab": {"commit": "d"},
                "unitree_mujoco": {"commit": "e"},
            }))
            run.side_effect = [
                subprocess.CompletedProcess([], 0, "wrong\n", ""),
                subprocess.CompletedProcess([], 0, "b\n", ""),
                subprocess.CompletedProcess([], 0, "c\n", ""),
                subprocess.CompletedProcess([], 0, "d\n", ""),
                subprocess.CompletedProcess([], 0, "e\n", ""),
            ]

            report = MODULE.local_readiness(project, system="Darwin")

        self.assertFalse(report["ready"])
        self.assertIn("open_wbt_commit", report["missing"])
        self.assertIn("linux", report["missing"])


if __name__ == "__main__":
    unittest.main()
