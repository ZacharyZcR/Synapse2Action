from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "check_groot_n17_readiness", ROOT / "simulation/check_groot_n17_readiness.py"
)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def touch(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


class GrootN17ReadinessTests(unittest.TestCase):
    def test_local_readiness_requires_every_runtime_and_weight(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            required = [
                "simulation/vendor/Isaac-GR00T/gr00t/eval/run_gr00t_server.py",
                "simulation/vendor/Isaac-GR00T/.venv/bin/python",
                "simulation/vendor/GR00T-WholeBodyControl/gear_sonic/scripts/run_sim_loop.py",
                "simulation/vendor/GR00T-WholeBodyControl/.venv_sim/bin/python",
            ]
            required += [f"simulation/vendor/models/GR00T-N1.7-3B/{name}" for name in MODULE.MODEL_FILES]
            required += [
                f"simulation/vendor/GR00T-WholeBodyControl/gear_sonic_deploy/policy/sonic_v1_1/{name}"
                for name in MODULE.SONIC_FILES
            ]
            for relative in required:
                touch(project, relative)

            report = MODULE.local_readiness(project)

        self.assertTrue(report["ready_local"])
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["embodiment_tag"], "UNITREE_G1_SONIC")

    def test_incomplete_checkpoint_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            model = project / "simulation/vendor/models/GR00T-N1.7-3B"
            for name in MODULE.MODEL_FILES:
                touch(model, name)
            touch(model, "partial.safetensors.incomplete")

            report = MODULE.local_readiness(project)

        self.assertTrue(report["checks"]["n17_base"])
        self.assertFalse(report["checks"]["n17_base_complete"])

    @patch.object(MODULE.subprocess, "run")
    def test_access_probe_distinguishes_license_from_login(self, run) -> None:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "user: test", ""),
            subprocess.CompletedProcess([], 1, "", "403 Client Error"),
        ]

        report = MODULE.gated_access(Path("hf"))

        self.assertTrue(report["authenticated"])
        self.assertFalse(report["authorized"])
        self.assertEqual(report["reason"], "license_not_granted")

    def test_launchers_use_n17_sonic_contract(self) -> None:
        server = (ROOT / "simulation/run_groot_n17_server.sh").read_text()
        client = (ROOT / "simulation/run_groot_n17_sonic_client.sh").read_text()

        self.assertIn("--embodiment-tag UNITREE_G1_SONIC", server)
        self.assertIn("--port \"${S2A_GROOT_N17_PORT:-5550}\"", server)
        self.assertIn("run_vla_inference.py", client)
        self.assertIn('exec "${isaac}/.venv/bin/python"', client)


if __name__ == "__main__":
    unittest.main()
