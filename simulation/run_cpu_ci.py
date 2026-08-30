#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
from time import monotonic
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the dependency-free Synapse2Action CPU acceptance profile"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("the CPU CI profile requires Python 3.12 or newer")

    started = monotonic()
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "schema_version": 1,
        "profile_id": "cpu-ci",
        "accepted": result.wasSuccessful(),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "tests": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
        },
        "duration_ms": round((monotonic() - started) * 1000, 3),
        "claim_boundary": [
            "hardware-free repository acceptance only",
            "no live EEG, GPU inference, vendor MuJoCo rollout, or physical robot claim",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
