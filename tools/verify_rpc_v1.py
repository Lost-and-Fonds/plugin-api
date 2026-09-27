#!/usr/bin/env python3
"""Check canonical RPC v1 identity, conformance vectors, and key invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path


spec_path, vectors_path, schema_path = map(Path, sys.argv[1:4])
spec = spec_path.read_text(encoding="utf-8")
vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
schema = json.loads(schema_path.read_text(encoding="utf-8"))
package = schema.get("package")
if package != "stashd:plugin@0.15.0" or vectors.get("package") != package:
    raise SystemExit("RPC v1 conformance material has a conflicting contract identity")

required = (
    "## Framing and call model",
    "## JSON values",
    "## Resource handles",
    "## Ownership, borrowing, and release",
    "## Collection Export host result",
    "## Conformance flows",
    "four-byte unsigned big-endian",
    "one active lifecycle invocation",
    "distinct IDs",
    "\"$resource\"",
    "borrow<T>",
    "receiver MUST NOT",
    "resource-drop",
    "Duplicate drop",
    "Invocation end is unconditional cleanup",
    "Every `list<u8>` is a JSON array",
    "MUST NOT return `limit-exceeded`",
    "same invocation",
    "package identity; no package version bump is warranted",
)
if any(term not in spec for term in required):
    raise SystemExit("RPC v1 normative specification is missing a required invariant")

by_name = {vector["name"]: vector for vector in vectors.get("vectors", [])}
expected = {
    "owned-byte-stream-handle",
    "nested-owned-http-request-body",
    "borrowed-helper-output",
    "explicit-resource-drop",
    "stream-read-chunk",
    "stream-read-eof",
    "u64-boundaries",
    "s64-boundaries",
    "host-synthesized-collection-limit",
    "reentrant-correlation",
}
if set(by_name) != expected:
    raise SystemExit("RPC v1 conformance vector set is incomplete or unexpected")
handle = by_name["owned-byte-stream-handle"]["value"]
if set(handle) != {"$resource"} or handle["$resource"] != {
    "type": "stashd:plugin/io-host.byte-stream", "id": "opaque-1"
}:
    raise SystemExit("RPC v1 resource handle vector does not match the canonical shape")
chunk = by_name["stream-read-chunk"]["response-result"]["ok"]
if chunk != [0, 1, 127, 255] or any(type(byte) is not int or not 0 <= byte <= 255 for byte in chunk):
    raise SystemExit("RPC v1 byte vector is not a list of unsigned JSON integers")
for name, low, high in (
    ("u64-boundaries", 0, 2**64 - 1),
    ("s64-boundaries", -(2**63), 2**63 - 1),
):
    values = by_name[name]["values"]
    if any(type(value) is not str or not value.lstrip("-").isdigit() or not low <= int(value) <= high for value in values):
        raise SystemExit(f"RPC v1 {name} must use in-range decimal strings")

limit = by_name["host-synthesized-collection-limit"]["lifecycle-response"]
if limit.get("result", {}).get("error", {}).get("tag") != "limit-exceeded" or "error" in limit:
    raise SystemExit("Collection Export limit vector must be a host-synthesized WIT result")
frames = by_name["reentrant-correlation"]["frames-in-order"]
if len(frames) != 4 or frames[0]["id"] == frames[1]["id"] or frames[1]["id"] != frames[2]["id"] or frames[0]["id"] != frames[3]["id"] or {frame.get("invocation") for frame in frames} != {"inv-1"}:
    raise SystemExit("RPC v1 re-entrant vector has ambiguous correlation or invocation identity")
print("RPC v1 normative specification and conformance vectors are consistent")
