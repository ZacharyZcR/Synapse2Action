#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.language_qualification import build_language_qualification
from synapse2action.task_spec import load_task_spec


PROJECT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the language-to-work qualification suite")
    parser.add_argument(
        "--tasks",
        nargs="+",
        type=Path,
        default=sorted((PROJECT / "experiments" / "tasks").glob("*.json")),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT / "reports" / "language" / "qualification.json",
    )
    args = parser.parse_args()
    report = build_language_qualification(load_task_spec(path) for path in args.tasks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
