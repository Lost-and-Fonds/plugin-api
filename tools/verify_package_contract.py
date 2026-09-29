"""Check package-level Stashd contract identity vectors."""

from __future__ import annotations

import json
import re
import sys
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

print("package contract identity vectors are consistent")
