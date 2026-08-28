#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time

from synapse2action.task_spec import load_task_spec


PROJECT = Path(__file__).resolve().parents[1]
VENDOR = PROJECT / "simulation" / "vendor"
ISAAC = Path(os.getenv("S2A_GROOT_ISAAC_DIR", VENDOR / "Isaac-GR00T-N1.6"))
WBC = Path(os.getenv("S2A_GROOT_WBC_DIR", VENDOR / "GR00T-WholeBodyControl-N1.6"))
MODEL = Path(
    os.getenv(
        "S2A_GROOT_MODEL_DIR",
        VENDOR / "models" / "GR00T-N1.6-G1-PnPAppleToPlate-CW",
    )
)
REPORT_DIR = PROJECT / "reports" / "simulation"
STEM = "g1-groot-closed-loop"


def wait_until_ready(process: subprocess.Popen[str], log_path: Path, timeout_s: float = 120) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            text = log_path.read_text(errors="replace") if log_path.exists() else ""
            raise RuntimeError(text.strip() or "GR00T server exited during startup")
        try:
            with socket.create_connection(("127.0.0.1", 5555), timeout=1):
                return
        except OSError:
            pass
        time.sleep(1)
    raise TimeoutError("GR00T server startup timed out")


def terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] != "planner_action":
        raise SystemExit("usage: run_groot_g1_pick_place.py TASK_SPEC planner_action")
    task = load_task_spec(Path(sys.argv[1]))
    if (task.target, task.destination) != ("apple", "plate"):
        raise ValueError("public GR00T checkpoint only supports apple -> plate")
    for path in (ISAAC, WBC, MODEL):
        if not path.exists():
            raise FileNotFoundError(path)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    env.setdefault("MUJOCO_GL", "egl")
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(PROJECT / "src"), env.get("PYTHONPATH")))
    )
    evidence_path = REPORT_DIR / f"{STEM}-evidence.json"
    for path in (
        evidence_path,
        REPORT_DIR / f"{STEM}.json",
        REPORT_DIR / f"{STEM}-acceptance.json",
    ):
        path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="s2a-groot-") as temporary:
        log_path = Path(temporary) / "server.log"
        with log_path.open("w") as server_log:
            server = subprocess.Popen(
                (
                    str(ISAAC / ".venv" / "bin" / "python"),
                    "gr00t/eval/run_gr00t_server.py",
                    "--model-path",
                    str(MODEL),
                    "--embodiment-tag",
                    "UNITREE_G1",
                    "--use-sim-policy-wrapper",
                    "--host",
                    "127.0.0.1",
                ),
                cwd=ISAAC,
                env=env,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                wait_until_ready(server, log_path)
                completed = subprocess.run(
                    (
                        str(WBC / ".venv_eval" / "bin" / "python"),
                        str(PROJECT / "simulation" / "run_groot_evidence_rollout.py"),
                        "--output",
                        str(evidence_path),
                        "--max-episode-steps",
                        "1440",
                        "--minimum-lift-m",
                        str(task.verification.minimum_lift_m),
                        "--policy-client-host",
                        "127.0.0.1",
                        "--policy-client-port",
                        "5555",
                    ),
                    cwd=WBC,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            finally:
                terminate(server)

    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        print(output, file=sys.stderr)
        return 1
    match = re.search(r"results:.*\[(True|False)\]", output)
    official_success = bool(match and match.group(1) == "True")
    evidence_payload = json.loads(evidence_path.read_text())
    episodes = evidence_payload.get("episodes", [])
    evidence = episodes[0] if episodes and isinstance(episodes[0], dict) else {}
    strictly_verified = bool(
        official_success
        and evidence.get("grasped") is True
        and evidence.get("lifted") is True
        and evidence.get("released_after_contact") is True
        and evidence.get("stable_on_plate") is True
        and evidence.get("remained_standing") is True
    )
    report = {
        "schema_version": 1,
        "task_id": task.task_id,
        "model": "cloudwalk-research/GR00T-N1.6-G1-PnPAppleToPlate",
        "instruction": task.instruction,
        "official_contact_success": official_success,
        "gripper_contact": evidence.get("gripper_contact"),
        "maximum_consecutive_grasp_steps": evidence.get("maximum_consecutive_grasp_steps"),
        "grasped": evidence.get("grasped"),
        "maximum_lift_m": evidence.get("maximum_lift_m"),
        "lifted": evidence.get("lifted"),
        "released": evidence.get("released_after_contact"),
        "stable_on_target": evidence.get("stable_on_plate"),
        "remained_standing": evidence.get("remained_standing"),
        "evidence_steps": evidence.get("steps"),
        "video_directory": str(REPORT_DIR / "groot-evidence-video"),
        "limitation": "Strict evidence is measured from MuJoCo state; the upstream success flag remains contact-only.",
        "returncode": completed.returncode,
    }
    acceptance = {
        "accepted": official_success,
        "criterion": "upstream apple-plate contact",
        "strictly_verified": strictly_verified,
    }
    (REPORT_DIR / f"{STEM}.json").write_text(json.dumps(report, indent=2) + "\n")
    (REPORT_DIR / f"{STEM}-acceptance.json").write_text(json.dumps(acceptance, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
