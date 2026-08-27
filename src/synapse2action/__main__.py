from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiments import run_suite
from .monte_carlo import run_monte_carlo
from .synthetic_intent import run_intent_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic hardware-free experiments")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("experiments/scenarios"))
    parser.add_argument("--intent-directory", type=Path)
    parser.add_argument("--monte-carlo-config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.monte_carlo_config:
        report = run_monte_carlo(args.monte_carlo_config)
    elif args.intent_directory:
        report = run_intent_suite(args.intent_directory)
    else:
        report = run_suite(args.directory)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return int(report.get("failed", 0) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
