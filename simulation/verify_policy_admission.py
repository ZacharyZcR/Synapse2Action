#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.policy_admission import verify_policy_admission


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a policy evidence bundle")
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--language-manifest", type=Path, required=True)
    parser.add_argument("--language-evaluation", type=Path, required=True)
    parser.add_argument("--required-seeds", nargs="+", type=int, required=True)
    parser.add_argument("--minimum-outcome-success-rate", type=float, default=0.9)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_policy_admission(
        args.runs,
        args.language_manifest,
        args.language_evaluation,
        required_seeds=args.required_seeds,
        minimum_outcome_success_rate=args.minimum_outcome_success_rate,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return int(not report["accepted"])


if __name__ == "__main__":
    raise SystemExit(main())
