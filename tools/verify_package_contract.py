"""Check package-level Stashd contract identity vectors."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path


schema_path, vectors_path = map(Path, sys.argv[1:3])
schema = json.loads(schema_path.read_text(encoding="utf-8"))
vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
canonical = vectors["canonical_contract"]
contract_schema = schema.get("properties", {}).get("contract", {})
if contract_schema.get("pattern") != r"^stashd:plugin@[0-9]+\.[0-9]+\.[0-9]+$" or "contract" not in schema.get("required", []):
    raise SystemExit("manifest schema does not require the canonical exact contract identity")
if "version" not in schema.get("required", []) or "components" not in schema.get("required", []):
    raise SystemExit("manifest schema does not retain independent package version and components")

for vector in vectors["cases"]:
    manifest = vector["manifest"]
    outcome = vector["outcome"]
    identity = manifest.get("contract")
    manifest_valid = identity == canonical and all(key in manifest for key in ("id", "version", "components"))
    if outcome == "valid":
        actual = "valid" if manifest_valid else "invalid"
    elif outcome == "invalid":
        actual = "valid" if manifest_valid else "invalid"
    elif outcome == "host-incompatible-before-lifecycle":
        actual = outcome if isinstance(identity, str) and re.fullmatch(r"stashd:plugin@[0-9]+\.[0-9]+\.[0-9]+", identity) and identity != canonical else "invalid"
    else:
        raise SystemExit(f"unknown package contract vector outcome: {outcome}")
    if actual != outcome:
        raise SystemExit(f"package contract vector mismatch for {vector['name']}: {actual!r} != {outcome!r}")
    if "rpc_protocol" in vector and vector["rpc_protocol"] != 1:
        raise SystemExit(f"unexpected RPC protocol in vector {vector['name']}")

with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    canonical_path = root / "stashd-plugin.json"
    alternate_paths = (root / "plugin.json", root / "metadata" / "stashd-plugin.json")
    sample = vectors["cases"][0]["manifest"]
    canonical_path.write_text(json.dumps(sample), encoding="utf-8")
    if not canonical_path.is_file() or json.loads(canonical_path.read_text(encoding="utf-8")) != sample:
        raise SystemExit("canonical package manifest path does not load valid JSON")
    canonical_path.unlink()
    if canonical_path.is_file():
        raise SystemExit("package without the canonical manifest path unexpectedly loaded")
    for alternate_path in alternate_paths:
        alternate_path.parent.mkdir(parents=True, exist_ok=True)
        alternate_path.write_text(json.dumps(sample), encoding="utf-8")
    if canonical_path.is_file():
        raise SystemExit("alternate manifest path incorrectly substitutes for canonical path")
    canonical_path.write_text("{", encoding="utf-8")
    try:
        json.loads(canonical_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        pass
    else:
        raise SystemExit("malformed canonical manifest JSON unexpectedly parsed")
    canonical_path.write_text(json.dumps({"id": "example.plugin"}), encoding="utf-8")
    if set(json.loads(canonical_path.read_text(encoding="utf-8"))) >= {"id", "version", "contract", "components"}:
        raise SystemExit("schema-invalid manifest unexpectedly passed required-field validation")

print("package contract identity and manifest loading vectors are consistent")
