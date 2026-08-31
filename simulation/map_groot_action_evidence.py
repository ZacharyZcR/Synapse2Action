#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.g1_groot import map_groot_unitree_action
from synapse2action.unitree_g1 import G1_FIX_STAND_POSITION_RAD


def main() -> None:
    parser = argparse.ArgumentParser(description="Map captured GR00T G1 action evidence into SDK2 order")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.input.read_text())
    if evidence.get("all_modalities_finite") is not True:
        raise ValueError("GR00T evidence contains a non-finite modality")
    proposal = map_groot_unitree_action(evidence["first_action"], G1_FIX_STAND_POSITION_RAD)
    payload = {
        "schema_version": 1,
        "source": str(args.input),
        "mapped_first_action": {
            "joint_position_rad": proposal.joint_position_rad,
            "navigation_command": proposal.navigation_command,
            "base_height_command": proposal.base_height_command,
            "unsupported_hand_dimensions": proposal.unsupported_hand_dimensions,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
