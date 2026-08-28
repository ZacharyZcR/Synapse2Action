from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an official Unitree SDK2 simulation run")
    parser.add_argument("report_directory", type=Path)
    parser.add_argument(
        "--scenario",
        choices=("balance", "locomotion", "obstacle", "dynamic-obstacle"),
        default="balance",
    )
    args = parser.parse_args()
    simulator = load_json(args.report_directory / "g1-mujoco.json")
    controller_log = (args.report_directory / "g1-controller.log").read_text()
    quaternion = simulator.get("base_quaternion_wxyz", [])
    upright_quaternion = (
        isinstance(quaternion, list)
        and len(quaternion) == 4
        and abs(float(quaternion[0])) >= 0.95
    )

    checks = {
        "official_simulator": simulator.get("simulator") == "unitreerobotics/unitree_mujoco",
        "official_controller_loaded_policy": "config/policy/velocity/v0" in controller_log,
        "official_velocity_policy": "FSM: Start Velocity" in controller_log,
        "g1_29dof": simulator.get("model") == "g1_29dof" and simulator.get("motor_count") == 29,
        "physics_command_barrier": simulator.get("physics_started_after_lowcmd") is True,
        "controller_prerolled": int(simulator.get("lowcmd_frames_before_physics", 0)) >= 100,
        "odometry_feedback_published": int(simulator.get("odometry_frames_published", 0)) >= 1000,
        "simulation_advanced": float(simulator.get("simulated_seconds", 0)) >= 13.9,
        "no_external_support": simulator.get("external_support") is False,
        "unsupported_standing": float(simulator.get("unsupported_seconds", 0)) >= 13.9,
        "minimum_height": float(simulator.get("minimum_base_height_m", 0)) >= 0.65,
        "final_height": float(simulator.get("base_height_m", 0)) >= 0.65,
        "upright_quaternion": upright_quaternion,
    }
    if args.scenario in ("locomotion", "obstacle", "dynamic-obstacle"):
        final_velocity = simulator.get("final_base_linear_velocity_xyz_mps", [])
        checks["closed_loop_position_reached"] = float(simulator.get("final_position_error_m", 99)) <= 0.1
        checks["closed_loop_yaw_reached"] = abs(float(simulator.get("final_yaw_error_rad", 99))) <= 0.15
        checks["stopped_after_locomotion"] = (
            isinstance(final_velocity, list)
            and len(final_velocity) == 3
            and abs(float(final_velocity[0])) < 0.2
            and abs(float(final_velocity[1])) < 0.2
            and abs(float(simulator.get("final_yaw_rate_rad_s", 99))) < 0.15
        )
    if args.scenario in ("obstacle", "dynamic-obstacle"):
        obstacle_radius = float(simulator.get("obstacle_radius_m", 0))
        checks["obstacle_has_collision_geometry"] = obstacle_radius > 0
        checks["navigation_replanned"] = (
            "Navigation replan:" in controller_log
            and controller_log.count("Navigation waypoint ") >= 2
        )
        checks["obstacle_clearance"] = (
            float(simulator.get("minimum_obstacle_center_distance_m", 0))
            >= obstacle_radius + 0.25
        )
        checks["detour_executed"] = float(simulator.get("maximum_abs_lateral_position_m", 0)) >= 0.3
    if args.scenario == "dynamic-obstacle":
        checks["dynamic_obstacle_appeared"] = simulator.get("dynamic_obstacle") is True
        checks["online_detection_triggered"] = "Dynamic obstacle detected" in controller_log
    report = {"accepted": all(checks.values()), "checks": checks}
    output = args.report_directory / "acceptance.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
