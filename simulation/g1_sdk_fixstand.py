from __future__ import annotations

import argparse
import json

from synapse2action.unitree_g1 import G1FixStandController, UnitreeG1Sdk


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Unitree G1 FixStand over official SDK2")
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--state-timeout", type=float, default=10.0)
    parser.add_argument("--transition-seconds", type=float, default=3.0)
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--frequency-hz", type=float, default=200.0)
    args = parser.parse_args()

    sdk = UnitreeG1Sdk(domain_id=args.domain_id, interface=args.interface)
    sdk.connect()
    sdk.wait_for_state(args.state_timeout)
    result = G1FixStandController(sdk, frequency_hz=args.frequency_hz).run(
        args.transition_seconds,
        args.hold_seconds,
    )
    print(
        json.dumps(
            {
                "controller": "unitree_rl_lab_fixstand",
                "transport": "unitree_sdk2_python",
                "commands_sent": result.commands_sent,
                "maximum_roll_rad": result.maximum_roll_rad,
                "maximum_pitch_rad": result.maximum_pitch_rad,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
