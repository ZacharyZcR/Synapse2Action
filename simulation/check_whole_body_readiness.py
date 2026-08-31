#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import subprocess


REQUIRED_PATHS = {
    "open_wbt_mujoco": "simulation/vendor/OpenWBT/deploy/run_teleoperation_mujoco.py",
    "open_wbt_real": "simulation/vendor/OpenWBT/deploy/run_teleoperation_real.py",
    "open_track_training": "simulation/vendor/OpenTrack/track_mj/learning/train/train_ppo_track.py",
    "open_track_deployment": "simulation/vendor/OpenTrack/deploy/state_machine/main.cpp",
    "open_track_simulator": "simulation/vendor/OpenTrack/deploy/sim_interface/main.py",
    "open_track_limits": "simulation/vendor/OpenTrack/deploy/storage/g1_tracking_constant.yaml",
    "unitree_locomotion_policy": "simulation/vendor/unitree_rl_gym/deploy/pre_train/g1/motion.pt",
    "unitree_locomotion_config": "simulation/vendor/unitree_rl_gym/deploy/deploy_mujoco/configs/g1.yaml",
    "unitree_locomotion_model": "simulation/vendor/unitree_rl_gym/resources/robots/g1_description/scene.xml",
}


def _head(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def local_readiness(project: Path, system: str | None = None) -> dict[str, object]:
    lock = json.loads((project / "simulation/whole_body.lock.json").read_text())
    checks = {name: (project / relative).is_file() for name, relative in REQUIRED_PATHS.items()}
    vendor = project / "simulation/vendor"
    commits = {
        "open_wbt": _head(vendor / "OpenWBT"),
        "open_track": _head(vendor / "OpenTrack"),
        "unitree_rl_gym": _head(vendor / "unitree_rl_gym"),
    }
    checks["open_wbt_commit"] = commits["open_wbt"] == lock["open_wbt"]["commit"]
    checks["open_track_commit"] = commits["open_track"] == lock["open_track"]["commit"]
    checks["unitree_rl_gym_commit"] = commits["unitree_rl_gym"] == lock["unitree_rl_gym"]["commit"]
    checks["linux"] = (system or platform.system()) == "Linux"
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "ready": not missing,
        "checks": checks,
        "missing": missing,
        "commits": commits,
        "scope": "source-and-deployment-readiness-only",
        "validated_capability": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check pinned OpenWBT/OpenTrack source readiness")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = local_readiness(args.project.resolve())
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
