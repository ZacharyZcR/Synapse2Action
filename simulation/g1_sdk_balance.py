from __future__ import annotations

import argparse
import json

from synapse2action.unitree_g1 import (
    G1FixStandController,
    G1OfficialVelocityPolicy,
    UnitreeG1Sdk,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="FixStand then run Unitree's official G1 ONNX policy")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--state-timeout", type=float, default=5.0)
    parser.add_argument("--transition-seconds", type=float, default=0.0)
    parser.add_argument("--balance-seconds", type=float, default=5.0)
    args = parser.parse_args()

    sdk = UnitreeG1Sdk(domain_id=args.domain_id, interface=args.interface)
    sdk.connect()
    sdk.wait_for_state(args.state_timeout)
    if args.transition_seconds < 0:
        raise ValueError("transition duration must be non-negative")
    stand_commands = 0
    if args.transition_seconds:
        stand_commands = G1FixStandController(sdk).run(args.transition_seconds, 0).commands_sent
    balance = G1OfficialVelocityPolicy(sdk, args.policy).run(args.balance_seconds)
    print(json.dumps({
        "controller": "unitree_rl_lab_velocity_v0",
        "transport": "unitree_sdk2_python",
        "fixstand_commands": stand_commands,
        "policy_steps": balance.policy_steps,
        "maximum_roll_rad": balance.maximum_roll_rad,
        "maximum_pitch_rad": balance.maximum_pitch_rad,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
