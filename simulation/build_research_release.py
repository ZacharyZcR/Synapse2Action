#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synapse2action.research_release import (
    build_research_release,
    verify_research_release,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify research release assets")
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("research/release-source.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("research/release-v1.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    source = (root / args.source).resolve() if not args.source.is_absolute() else args.source
    manifest = (
        (root / args.manifest).resolve()
        if not args.manifest.is_absolute()
        else args.manifest
    )
    if args.command == "build":
        payload = build_research_release(root, source)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        return 0
    report = verify_research_release(root, source, manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(not report["accepted"])


if __name__ == "__main__":
    raise SystemExit(main())
