from __future__ import annotations

import argparse
import json
from time import sleep

from synapse2action.unitree_g1 import UnitreeG1Sdk


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Unitree G1 through official SDK2 topics")
    parser.add_argument("--domain-id", type=int, default=1)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--state-timeout", type=float, default=10.0)
    parser.add_argument("--stream-seconds", type=float, default=0.0)
    parser.add_argument("--frequency-hz", type=float, default=200.0)
    args = parser.parse_args()

    sdk = UnitreeG1Sdk(domain_id=args.domain_id, interface=args.interface)
    sdk.connect()
    initial = sdk.wait_for_state(args.state_timeout)
    if args.stream_seconds < 0:
        raise ValueError("stream duration must be non-negative")
    if args.stream_seconds:
        commands = sdk.stream_neutral(args.stream_seconds, args.frequency_hz)
    else:
        commands = 0
        sleep(0.1)
    final = sdk.observation()
    print(
        json.dumps(
            {
                "transport": "unitree_sdk2_python",
                "topics": {"command": "rt/lowcmd", "state": "rt/lowstate"},
                "motor_count": len(final.joint_position_rad),
                "mode_machine": final.mode_machine,
                "state_advanced": final.captured_at_ns > initial.captured_at_ns,
                "commands_sent": commands,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
