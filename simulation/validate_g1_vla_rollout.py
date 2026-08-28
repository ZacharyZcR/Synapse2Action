from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.task_spec import load_task_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a SmolVLA-driven G1 MuJoCo rollout")
    parser.add_argument("simulator", type=Path)
    parser.add_argument("--task-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    simulator = json.loads(args.simulator.read_text())
    task = load_task_spec(args.task_spec)
    runtime = simulator["vla_runtime"]
    functional_checks = {
        "sdk2_commands": simulator["sdk2_lowcmd_frames"] >= 1000,
        "vla_chunks": runtime["chunks_received"] >= 2,
        "vla_reached_bridge": simulator.get("vla_authorized_frames", 0) > 0,
        "vla_changed_joint_targets": simulator.get("vla_overlay_frames", 0) > 0
        and simulator.get("maximum_vla_joint_delta_rad", 0.0) > 1e-6,
        "object_grasped": simulator["grasped"],
        "object_lifted": simulator["maximum_object_height_m"] - simulator["initial_object_position_xyz_m"][2]
        >= task.verification.minimum_lift_m,
        "object_released": simulator["released"],
        "object_in_drop_zone": simulator["final_object_center_in_drop_zone"],
        "g1_remained_standing": simulator["minimum_base_height_m"]
        >= task.verification.minimum_base_height_m,
    }
    report = {
        "accepted": all(functional_checks.values()) and runtime["accepted"],
        "functional_accepted": all(functional_checks.values()),
        "realtime_accepted": runtime["accepted"],
        "functional_checks": functional_checks,
        "runtime": runtime,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["accepted"])


if __name__ == "__main__":
    main()
