#!/usr/bin/env python3
"""Check the language-neutral package artifact rules and forcing vectors."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


schema_path, vectors_path = map(Path, sys.argv[1:3])


def reject_reason(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return "artifact must be a non-empty string"
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        return "artifact contains an ASCII control character"
    if "\\" in value:
        return "artifact contains a backslash"
    if ":" in value:
        return "artifact contains a colon"
    if value.startswith("/"):
        return "artifact is absolute"

    retained: list[str] = []
    for segment in value.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not retained:
                return "artifact traverses above the package root"
            retained.pop()
            continue
        retained.append(segment)
    if not retained:
        return "artifact normalizes to an empty path"
    return None


def normalize(value: str) -> str:
    reason = reject_reason(value)
    if reason is not None:
        raise ValueError(reason)
    return "/".join(
        segment
        for segment in value.split("/")
        if segment not in ("", ".")
    ) if ".." not in value.split("/") else _normalize_with_parents(value)


def _normalize_with_parents(value: str) -> str:
    retained: list[str] = []
    for segment in value.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            retained.pop()
        else:
            retained.append(segment)
    return "/".join(retained)


def resolve_filesystem(artifact: str, entries: dict[str, dict[str, str]]) -> bool:
    try:
        normalized = normalize(artifact)
    except ValueError:
        return False

    package_root = "/package"

    def resolve(path: str, link_count: int) -> str | None:
        if link_count > 40:
            return None
        components = [part for part in path.split("/") if part not in ("", ".")]
        resolved: list[str] = []
        for index, component in enumerate(components):
            if component == "..":
                if not resolved:
                    return "/outside"
                resolved.pop()
                continue
            candidate = "/" + "/".join(resolved + [component])
            if candidate == package_root:
                resolved.append(component)
                continue
            entry = entries.get(candidate[len(package_root) + 1 :]) if candidate.startswith(package_root + "/") else entries.get(candidate)
            if entry is None:
                return None
            kind = entry.get("type")
            if kind == "symlink":
                target = entry.get("target")
                if not isinstance(target, str) or not target:
                    return None
                target_path = target if target.startswith("/") else "/".join(resolved + [target])
                suffix = components[index + 1 :]
                if suffix:
                    target_path = target_path.rstrip("/") + "/" + "/".join(suffix)
                return resolve(target_path, link_count + 1)
            if kind == "directory":
                if index == len(components) - 1:
                    return None
                resolved.append(component)
                continue
            if kind == "file":
                return candidate if index == len(components) - 1 else None
            return None
        return None

    resolved = resolve(package_root + "/" + normalized, 0)
    return resolved is not None and resolved.startswith(package_root + "/")







def check_lexical_vectors(vectors: dict[str, Any]) -> None:
    for vector in vectors["lexical"]:
        value = vector["artifact"]
        try:
            normalized = normalize(value)
            actual = {"outcome": "accepted", "normalized": normalized}
        except ValueError:
            actual = {"outcome": "rejected"}
        expected = {key: vector[key] for key in ("outcome", "normalized") if key in vector}
        if actual != expected:
            raise SystemExit(f"artifact vector mismatch for {vector['name']}: {actual!r} != {expected!r}")


def check_equivalent_vectors(vectors: dict[str, Any]) -> None:
    for vector in vectors["equivalent"]:
        normalized = {normalize(artifact) for artifact in vector["artifacts"]}
        expected = {vector["normalized"]}
        if normalized != expected:
            raise SystemExit(f"equivalent artifact vector mismatch for {vector['name']}: {normalized!r} != {expected!r}")


def check_filesystem_vectors(vectors: dict[str, Any]) -> None:
    for vector in vectors["filesystem"]:
        actual = "accepted" if resolve_filesystem(vector["artifact"], vector["entries"]) else "rejected"
        if actual != vector["outcome"]:
            raise SystemExit(f"filesystem vector mismatch for {vector['name']}: {actual!r} != {vector['outcome']!r}")


schema = json.loads(schema_path.read_text(encoding="utf-8"))
vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
if vectors.get("package") != "stashd:plugin@0.18.0":
    raise SystemExit("package artifact vectors refer to the wrong contract")
contract_schema = schema.get("properties", {}).get("contract", {})
if contract_schema.get("pattern") != r"^stashd:plugin@[0-9]+\.[0-9]+\.[0-9]+$":
    raise SystemExit("package manifest contract identity must use the canonical exact-identity syntax")
artifact_schema = schema["$defs"]["component"]["properties"]["artifact"]
if artifact_schema.get("pattern") != r"^[^/\\:\u0000-\u001F\u007F][^\\:\u0000-\u001F\u007F]*$":
    raise SystemExit("artifact schema does not enforce the canonical portable path syntax")
if "package-artifact.md" not in artifact_schema.get("description", ""):
    raise SystemExit("artifact schema must point to the normative resolution rules")
check_lexical_vectors(vectors)
check_equivalent_vectors(vectors)
check_filesystem_vectors(vectors)
print("package artifact resolution rules and forcing vectors are consistent")
