from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any

from synapse2action.visualization import render_g1_dashboard_html


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the self-contained G1 simulation evidence dashboard")
    parser.add_argument("--harness", type=Path, default=Path("reports/simulation/harness-live-eeg-smolvla-g1.json"))
    parser.add_argument("--eeg", type=Path, default=Path("reports/eeg/live-eeg-lsl.json"))
    parser.add_argument("--training", type=Path, default=Path("reports/training/smolvla-g1-suite-heldout.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/simulation/synapse2action-dashboard.html"))
    args = parser.parse_args()

    harness = load_json(args.harness)
    simulator = harness["unitree_simulator"]
    if not harness["accepted"] or not simulator.get("visualization_frames"):
        parser.error("the harness report must be accepted and contain visualization frames")

    frames = []
    for frame in simulator["visualization_frames"]:
        image_path = args.harness.parent / frame["file"]
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        frames.append({"stage": frame["stage"], "data": f"data:image/png;base64,{encoded}"})

    dashboard = {
        "harness": {
            "accepted": harness["accepted"],
            "final_state": harness["final_state"],
            "trace": harness["trace"],
        },
        "acceptance": harness["unitree_acceptance"],
        "simulator": simulator,
        "eeg": load_json(args.eeg),
        "training": load_json(args.training),
        "frames": frames,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_g1_dashboard_html(dashboard))
    print(json.dumps({"accepted": True, "frames": len(frames), "output": str(args.output)}))


if __name__ == "__main__":
    main()
