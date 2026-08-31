from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"research release input must be an object: {path}")
    return payload


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _safe_pattern(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("release patterns must be non-empty strings")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"unsafe release pattern: {value}")
    return value


def _validate_source(source: Mapping[str, Any]) -> None:
    if set(source) != {
        "schema_version",
        "release_id",
        "collections",
        "unpublished_assets",
    }:
        raise ValueError("research release source has an invalid schema")
    if source.get("schema_version") != 1:
        raise ValueError("unsupported research release source version")
    if not isinstance(source.get("release_id"), str) or not source["release_id"]:
        raise ValueError("research release requires an identifier")
    collections = source.get("collections")
    if not isinstance(collections, list) or not collections:
        raise ValueError("research release requires collections")
    names = []
    for collection in collections:
        if not isinstance(collection, dict) or set(collection) != {"name", "patterns"}:
            raise ValueError("research release collection has an invalid schema")
        name = collection.get("name")
        patterns = collection.get("patterns")
        if not isinstance(name, str) or not name or not isinstance(patterns, list) or not patterns:
            raise ValueError("research release collection is incomplete")
        names.append(name)
        for pattern in patterns:
            _safe_pattern(pattern)
    if len(names) != len(set(names)):
        raise ValueError("research release collection names must be unique")
    unpublished = source.get("unpublished_assets")
    if not isinstance(unpublished, list):
        raise ValueError("research release unpublished assets must be a list")
    for item in unpublished:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "status", "reason"}
            or item.get("status") not in {"local-only", "external"}
            or not isinstance(item.get("reason"), str)
            or not item["reason"]
        ):
            raise ValueError("research release unpublished asset is invalid")
        _safe_pattern(item.get("path"))


def build_research_release(root: Path, source_path: Path) -> dict[str, Any]:
    source = _load_object(source_path)
    _validate_source(source)
    files = []
    seen: set[str] = set()
    for collection in source["collections"]:
        matched: set[Path] = set()
        for pattern in collection["patterns"]:
            matched.update(path for path in root.glob(pattern) if path.is_file())
        if not matched:
            raise ValueError(f"release collection is empty: {collection['name']}")
        for path in sorted(matched):
            if path.is_symlink():
                raise ValueError(f"release files must not be symlinks: {path}")
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                raise ValueError(f"release file belongs to multiple collections: {relative}")
            seen.add(relative)
            files.append(
                {
                    "collection": collection["name"],
                    "path": relative,
                    "sha256": _digest(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    files.sort(key=lambda item: item["path"])
    digest_payload = {
        "release_id": source["release_id"],
        "files": files,
        "unpublished_assets": source["unpublished_assets"],
    }
    release_digest = sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "release_id": source["release_id"],
        "source_catalog": source_path.relative_to(root).as_posix(),
        "source_sha256": _digest(source_path),
        "files": files,
        "unpublished_assets": source["unpublished_assets"],
        "release_digest": release_digest,
    }


def verify_research_release(
    root: Path,
    source_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    try:
        expected = build_research_release(root, source_path)
        observed = _load_object(manifest_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "schema_version": 1,
            "verification": "research_release",
            "accepted": False,
            "release_digest": None,
            "detail": str(exc),
        }
    accepted = observed == expected
    return {
        "schema_version": 1,
        "verification": "research_release",
        "accepted": accepted,
        "release_digest": expected["release_digest"],
        "detail": "release manifest matches published files"
        if accepted
        else "release manifest is stale or modified",
    }
