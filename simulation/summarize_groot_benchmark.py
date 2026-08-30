#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.groot_benchmark import summarize_groot_episodes


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate seeded GR00T evidence reports")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    episodes = []
    for path in args.inputs:
        payload = json.loads(path.read_text())
        episodes.extend(payload.get("episodes", []))
    report = summarize_groot_episodes(episodes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
