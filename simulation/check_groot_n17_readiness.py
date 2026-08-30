#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


MODEL_FILES = (
    "config.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
    "model.safetensors.index.json",
    "processor_config.json",
    "statistics.json",
)
SONIC_FILES = ("model_encoder.onnx", "model_decoder.onnx")


def local_readiness(project: Path) -> dict[str, object]:
    vendor = project / "simulation/vendor"
    isaac = vendor / "Isaac-GR00T"
    wbc = vendor / "GR00T-WholeBodyControl"
    model = vendor / "models/GR00T-N1.7-3B"
    sonic = wbc / "gear_sonic_deploy/policy/sonic_v1_1"
    paths = {
        "isaac_source": isaac / "gr00t/eval/run_gr00t_server.py",
        "isaac_runtime": isaac / ".venv/bin/python",
        "sonic_source": wbc / "gear_sonic/scripts/run_sim_loop.py",
        "sonic_runtime": wbc / ".venv_sim/bin/python",
    }
    checks = {name: path.is_file() for name, path in paths.items()}
    checks["n17_base"] = all((model / name).is_file() for name in MODEL_FILES)
    checks["n17_base_complete"] = checks["n17_base"] and not any(model.rglob("*.incomplete"))
    checks["sonic_weights"] = all((sonic / name).is_file() for name in SONIC_FILES)
    missing = [name for name, passed in checks.items() if not passed]
    return {
        "ready_local": not missing,
        "checks": checks,
        "missing": missing,
        "model_path": str(model),
        "embodiment_tag": "UNITREE_G1_SONIC",
    }


def gated_access(hf: Path) -> dict[str, object]:
    identity = subprocess.run(
        [str(hf), "auth", "whoami"], capture_output=True, text=True, check=False
    )
    if identity.returncode:
        return {"authenticated": False, "authorized": False, "reason": "not_authenticated"}
    probe = subprocess.run(
        [str(hf), "download", "nvidia/Cosmos-Reason2-2B", "config.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    error = probe.stderr
    reason = "ok"
    if probe.returncode:
        reason = "license_not_granted" if "403 Client Error" in error else "access_probe_failed"
    return {
        "authenticated": True,
        "authorized": probe.returncode == 0,
        "reason": reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local GR00T N1.7 + GEAR-SONIC readiness")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-access", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = local_readiness(args.project.resolve())
    if args.check_access:
        hf = args.project / "simulation/vendor/Isaac-GR00T/.venv/bin/hf"
        report["huggingface"] = gated_access(hf)
        report["ready"] = report["ready_local"] and report["huggingface"]["authorized"]
    else:
        report["ready"] = report["ready_local"]
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
