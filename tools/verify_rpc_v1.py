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
if package != "stashd:plugin@0.16.0" or vectors.get("package") != package:
    raise SystemExit("RPC v1 conformance material has a conflicting contract identity")

required = (
    "## Framing and call model",
    "## JSON values",
    "## Resource handles",
    "## Ownership, borrowing, and release",
    "## Broadcast collection resource",
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
    "Staged artifact descriptor",
    "Every `list<u8>` is a JSON array",
    "MUST NOT return `limit-exceeded`",
    "same invocation",
    "pre-1.0 package version bump from 0.15.0",
)
if any(term not in spec for term in required):
    raise SystemExit("RPC v1 normative specification is missing a required invariant")
response_rule = spec.split("## Framing and call model", 1)[1].split("## JSON values", 1)[0].lower()
response_requirements = (
    "response",
    "must contain `result`",
    "top-level `error`",
    "field is invalid",
    "typed `result<ok, error>`",
    "encoded inside it",
)
if any(term not in response_rule for term in response_requirements):
    raise SystemExit("RPC v1 response envelope must require result and forbid top-level error while retaining typed WIT errors")

by_name = {vector["name"]: vector for vector in vectors.get("vectors", [])}
expected = {
    "owned-byte-stream-handle",
    "nested-owned-http-request-body",
    "generic-http-method-tokens",
    "conditional-range-authenticated-stream",
    "redirect-under-host-policy",
    "borrowed-helper-output",
    "staged-writer-finish-canonical-descriptor",
    "reopen-exact-canonical-staged-artifact",
    "staged-writer-second-finish-failed",
    "explicit-resource-drop",
    "stream-read-chunk",
    "stream-read-eof",
    "u64-boundaries",
    "s64-boundaries",
    "host-synthesized-collection-limit",
    "broadcast-publish-collection-resource",
    "broadcast-collection-next-batch",
    "broadcast-collection-eof",
    "broadcast-collection-drop",
    "reentrant-correlation",
    "hello-first",
    "lifecycle-response-result",
}
if set(by_name) != expected:
    raise SystemExit("RPC v1 conformance vector set is incomplete or unexpected")
staged_finish = by_name["staged-writer-finish-canonical-descriptor"]
if staged_finish["response-result"]["ok"] != {
    "reference": "opaque-stage-1",
    "media-type": "application/octet-stream",
    "size-bytes": "4",
    "metadata": [{"schema": "example:v1", "json": "{}"}],
}:
    raise SystemExit("staged writer finish vector must carry the canonical host-issued descriptor")
staged_reopen = by_name["reopen-exact-canonical-staged-artifact"]
if staged_reopen["invocation"] != staged_finish["invocation"] or staged_reopen["params"]["artifact"] != staged_finish["response-result"]["ok"]:
    raise SystemExit("staged artifact reopen vector must use the exact descriptor from finish in the same invocation")
if by_name["staged-writer-second-finish-failed"]["response-result"] != {"err": {"failed": "writer already finished"}}:
    raise SystemExit("a second staged writer finish must return the existing staging-error.failed case")
method_vector = by_name["generic-http-method-tokens"]
if method_vector["methods"] != ["HEAD", "OPTIONS", "PROPFIND", "MKCOL", "MOVE", "COPY", "X-STASHD-EXT"] or any(term not in method_vector["validation"] for term in ("tchar", "rejected before dispatch")):
    raise SystemExit("RPC v1 HTTP method forcing vector is incomplete")
redirect = by_name["redirect-under-host-policy"]["policy"]
if redirect != {
    "redirects": "host-defined",
    "recheck-url-policy": True,
    "recheck-credential-grant": True,
    "forward-credential-to-new-authority": "only-if-host-policy-allows",
    "replay-streamed-body": "only-if-safely-replayable",
    "preserve-method-and-headers": "unless-documented-status-policy-says-otherwise",
}:
    raise SystemExit("RPC v1 redirect policy vector is incomplete")
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

collection_request = by_name["broadcast-publish-collection-resource"]
collection_resource = collection_request["params"]["request"]["collection"]["$resource"]
if collection_resource != {"type": "stashd:plugin/broadcast-host.item-collection", "id": "opaque-collection"} or collection_request["invocation"] != "inv-23":
    raise SystemExit("Broadcast publish vector must transfer the invocation-scoped collection resource")
collection_read = by_name["broadcast-collection-next-batch"]
if collection_read["params"]["max-items"] != 500 or collection_read["response-result"]["ok"] == []:
    raise SystemExit("Broadcast collection next vector must show bounded non-empty batches")
collection_eof = by_name["broadcast-collection-eof"]
if collection_eof["response-result"] != {"ok": None} or collection_eof["invocation"] != "inv-23":
    raise SystemExit("Broadcast collection EOF vector must use none in the same invocation")
limit = by_name["host-synthesized-collection-limit"]["lifecycle-response"]
if limit.get("result", {}).get("error", {}).get("tag") != "limit-exceeded" or "error" in limit:
    raise SystemExit("Collection Export limit vector must be a host-synthesized WIT result")
frames = by_name["reentrant-correlation"]["frames-in-order"]
if len(frames) != 4 or frames[0]["id"] == frames[1]["id"] or frames[1]["id"] != frames[2]["id"] or frames[0]["id"] != frames[3]["id"] or {frame.get("invocation") for frame in frames} != {"inv-1"}:
    raise SystemExit("RPC v1 re-entrant vector has ambiguous correlation or invocation identity")
startup = by_name["hello-first"]["frames-in-order"]
acquire_params = startup[2].get("params", {}) if len(startup) > 2 else {}
item = acquire_params.get("item", {})
options = acquire_params.get("options", {})
if len(startup) != 3 or startup[0].get("method") != "hello" or "invocation" in startup[0] or startup[1].get("result", {}).get("protocol") != 1 or startup[2].get("method") != "stashd:plugin/input-plugin.acquire" or set(acquire_params) != {"item", "options"} or set(item) != {"id", "reference", "delegation", "size-bytes", "size-estimated", "metadata"} or item.get("delegation") is not None or item.get("size-bytes") is not None or item.get("size-estimated") is not False or item.get("metadata") != [] or set(options) != {"options", "credentials"} or options != {"options": [], "credentials": []}:
    raise SystemExit("RPC v1 startup vector must gate a valid typed lifecycle invocation on invocation-free hello")
response = by_name["lifecycle-response-result"]["response"]
expected_error = {"error": {"tag": "failed", "value": {"message": "example failure", "retryable": False}}}
if "error" in response or response.get("result") != expected_error:
    raise SystemExit("RPC v1 lifecycle response must require result and nest a typed plugin-error detail")
print("RPC v1 normative specification and conformance vectors are consistent")
