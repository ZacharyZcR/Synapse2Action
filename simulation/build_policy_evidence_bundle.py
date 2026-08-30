#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.policy_evidence import (
    build_policy_evidence_bundle,
    verify_policy_evidence_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify a policy evidence bundle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output-directory", type=Path, required=True)
    build.add_argument("--runs", nargs="+", type=Path, required=True)
    build.add_argument("--language-manifest", type=Path, required=True)
    build.add_argument("--language-evaluation", type=Path, required=True)
    build.add_argument("--admission-report", type=Path, required=True)
    build.add_argument("--release-metadata", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--baseline", type=Path)
    args = parser.parse_args()

    if args.command == "build":
        report = build_policy_evidence_bundle(
            args.output_directory,
            run_paths=args.runs,
            language_manifest_path=args.language_manifest,
            language_evaluation_path=args.language_evaluation,
            admission_report_path=args.admission_report,
            release_metadata_path=args.release_metadata,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    report = verify_policy_evidence_bundle(
        args.bundle,
        baseline_directory=args.baseline,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(not report["accepted"])


if __name__ == "__main__":
    raise SystemExit(main())
