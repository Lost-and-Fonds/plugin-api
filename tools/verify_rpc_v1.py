#!/usr/bin/env python3
"""Check canonical RPC v1 identity, conformance vectors, and key invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path


class DuplicateMemberError(ValueError):
    pass


def reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMemberError(f"duplicate JSON object member: {key!r}")
        result[key] = value
    return result


def parse_rpc_frame(raw: str) -> object:
    return json.loads(raw, object_pairs_hook=reject_duplicate_members)


spec_path, vectors_path, schema_path = map(Path, sys.argv[1:4])
spec = spec_path.read_text(encoding="utf-8")
vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
schema = json.loads(schema_path.read_text(encoding="utf-8"))
package = schema.get("package")
if package != "stashd:plugin@0.17.0" or vectors.get("package") != package:
    raise SystemExit("RPC v1 conformance material has a conflicting contract identity")

required = (
    "## Framing and call model",
    "reject unsupported identities before launching a process or sending lifecycle messages",
    "The `hello` exchange below negotiates RPC framing/protocol only",
    "max-frame-bytes",
    "4096 bytes",
    "unsigned 32-bit integers from 4096 through 4294967295",
    "actual encoded UTF-8 JSON payload size",
    "smaller private encoded-message",
    "MUST NOT impose a smaller private encoded-message\nlimit",
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
    "least one byte",
    "sticky",
    "`some([])` is invalid protocol",
    "MUST NOT return `limit-exceeded`",
    "same invocation",
    "pre-1.0 package version bump from 0.15.0",
)
if any(term not in spec for term in required):
    raise SystemExit("RPC v1 normative specification is missing a required invariant")
duplicate_rule = spec.split("## Framing and call model", 1)[1].split("## JSON values", 1)[0]
if "host MUST NOT send a payload exceeding `N`" not in duplicate_rule or "plugin MUST NOT send a\npayload exceeding `M`" not in duplicate_rule or "Each\nadvertises the sender's own maximum receive payload" not in duplicate_rule or "MUST be no more than\n4096 bytes" not in duplicate_rule:
    raise SystemExit("RPC v1 hello must define independent directional frame maxima")
if any(term not in duplicate_rule for term in (
    "Every JSON\nobject anywhere", "MUST contain unique member names",
    "exact JSON string", "at any nesting depth",
    "before envelope validation", "MUST NOT choose first-wins or last-wins semantics",
)):
    raise SystemExit("RPC v1 must reject duplicate JSON object members before dispatch")
raw_duplicate_cases = vectors.get("raw-duplicate-member-frames", [])
expected_duplicate_cases = {
    "duplicate top-level method",
    "duplicate top-level id",
    "duplicate hello params",
    "duplicate resource handle member",
    "duplicate nested WIT member",
}
if {case.get("name") for case in raw_duplicate_cases} != expected_duplicate_cases:
    raise SystemExit("RPC v1 raw duplicate-member fixture set is incomplete or unexpected")
for case in raw_duplicate_cases:
    name = case["name"]
    raw_frame = case["raw-frame"]
    try:
        parse_rpc_frame(raw_frame)
    except DuplicateMemberError:
        continue
    raise SystemExit(f"RPC v1 parser accepted {name}")
print("RPC v1 raw duplicate-member frame cases rejected")
if parse_rpc_frame('{"id":"a","ID":"b"}') != {"id": "a", "ID": "b"}:
    raise SystemExit("RPC v1 duplicate detection must use exact member-name equality")
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
    "broadcast-publication-report-files",
    "broadcast-publication-report-metadata",
    "broadcast-publication-limit-exceeded",
    "broadcast-publication-complete",
    "broadcast-publication-not-applicable",
    "reentrant-correlation",
    "hello-first",
    "lifecycle-response-result",
    "enrichment-capabilities-local-discovery",
    "shared-value-semantics",
    "input-size-estimate-states",
    "rpc-frame-size-boundaries",
    "rpc-frame-invalid-advertisements",
    "rpc-batch-fits-frame",
    "staged-writer-frame-sizing",
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
if by_name["staged-writer-second-finish-failed"]["response-result"] != {
    "error": {"tag": "failed", "value": "writer already finished"}
}:
    raise SystemExit("a second staged writer finish must use the canonical RPC result and payload-bearing variant encoding")
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
request_params = collection_request["params"]["request"]
if request_params.get("collection", {}).get("$resource") != {"type": "stashd:plugin/broadcast-host.item-collection", "id": "opaque-collection"} or request_params.get("reporter", {}).get("$resource") != {"type": "stashd:plugin/broadcast-host.publication-reporter", "id": "opaque-reporter"} or request_params.get("maximum-report-records-per-batch") != 2 or collection_request["invocation"] != "inv-23":
    raise SystemExit("Broadcast publish vector must transfer both invocation resources and the explicit batch maximum")
for name in ("broadcast-publication-report-files", "broadcast-publication-report-metadata"):
    report = by_name[name]
    batches = next(value for key, value in report["params"].items() if key in {"files", "metadata"})
    if not batches or report["response-result"] != {"ok": None}:
        raise SystemExit("publication report vectors must show non-empty bounded successful batches")
oversized = by_name["broadcast-publication-limit-exceeded"]
if oversized["response-result"] != {"error": "limit-exceeded"} or len(oversized["params"]["files"]) != 3 or len(oversized["params"]["files"]) <= request_params["maximum-report-records-per-batch"] or "zero records" not in oversized["acceptance"]:
    raise SystemExit("publication batch limit vector must use canonical payloadless encoding and reject the entire batch over the advertised maximum")
if by_name["broadcast-publication-complete"]["response-result"] != {"ok": {"artifact": None, "files": "complete"}} or by_name["broadcast-publication-not-applicable"]["response-result"] != {"ok": {"artifact": None, "files": "not-applicable"}}:
    raise SystemExit("final Broadcast vectors must carry status only, not inline file or metadata lists")
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
if len(startup) != 3 or startup[0].get("method") != "hello" or "invocation" in startup[0] or startup[0].get("params", {}).get("max-frame-bytes") != 2097152 or startup[1].get("result", {}).get("max-frame-bytes") != 1048576 or startup[1].get("result", {}).get("protocol") != 1 or startup[2].get("method") != "stashd:plugin/input-plugin.acquire" or set(acquire_params) != {"item", "options"} or set(item) != {"id", "reference", "delegation", "size-bytes", "size-estimated", "metadata"} or item.get("delegation") is not None or item.get("size-bytes") is not None or item.get("size-estimated") is not False or item.get("metadata") != [] or set(options) != {"options", "credentials"} or options != {"options": [], "credentials": []}:
    raise SystemExit("RPC v1 startup vector must gate a valid typed lifecycle invocation on invocation-free hello")
size_states = by_name["input-size-estimate-states"]
if size_states["valid"] != [
    {"size-bytes": None, "size-estimated": False},
    {"size-bytes": "0", "size-estimated": False},
    {"size-bytes": "0", "size-estimated": True},
] or size_states["invalid"] != [{"size-bytes": None, "size-estimated": True}]:
    raise SystemExit("Input size-estimate vector must distinguish the three valid states and reject absent estimated size")
shared_values = by_name["shared-value-semantics"]
frame_bounds = by_name["rpc-frame-size-boundaries"]
invalid_ads = by_name["rpc-frame-invalid-advertisements"]
utf8_example = frame_bounds["utf8-example"]
raw_json = utf8_example["raw-json"]
if frame_bounds["bootstrap-bytes"] != 4096 or frame_bounds["advertisements"] != {"plugin": 8192, "host": 16384} or frame_bounds["sender-rules"] != {"plugin-to-host": "16384", "host-to-plugin": "8192"} or frame_bounds["acceptance"] != "payload exactly equal to peer maximum accepted; one byte over rejected before dispatch":
    raise SystemExit("RPC frame vector must establish asymmetric peer-direction limits")
if json.loads(raw_json) != {"x": "é"} or len(raw_json.encode("utf-8")) != utf8_example["encoded-utf8-bytes"] or len(raw_json) != utf8_example["character-count"] or utf8_example["encoded-utf8-bytes"] <= utf8_example["character-count"] or "complete JSON payload" not in utf8_example["meaning"]:
    raise SystemExit("RPC frame vector must measure the complete non-ASCII JSON payload in encoded UTF-8 bytes")
if invalid_ads["hello-payload-over-4096"] != "protocol failure" or any(case.get("valid") for case in invalid_ads["cases"]):
    raise SystemExit("RPC frame vector must reject missing and invalid size advertisements and oversized hello")
if by_name["rpc-batch-fits-frame"]["records-sent"] >= by_name["rpc-batch-fits-frame"]["maximum-items-per-batch"]:
    raise SystemExit("batch vector must permit fewer records than the semantic count maximum")
if "no private chunk ceiling" not in by_name["staged-writer-frame-sizing"]["rule"]:
    raise SystemExit("staged writer vector must rule out a private chunk ceiling")
metadata_vector = shared_values["plugin-metadata"]
if metadata_vector.get("valid-schema-values") != ["example", " ", "example@1"]:
    raise SystemExit("plugin metadata vector must accept opaque, whitespace-only, and revision-looking non-empty schema strings")
if metadata_vector.get("invalid-schema-values") != [""]:
    raise SystemExit("plugin metadata vector must reject the empty schema string")
if metadata_vector.get("valid-json-example") != {"schema": "example", "json": "{\"a\":1}"}:
    raise SystemExit("plugin metadata vector must show that schema=example is receiver-valid")
if metadata_vector.get("invalid-json-cases") != ["malformed-json", "root-array", "duplicate-member-at-any-depth"]:
    raise SystemExit("plugin metadata vector must retain malformed JSON, non-object root, and recursive duplicate-member failures")
if metadata_vector.get("receiver-validity-proves-producer-conformance") is not False or metadata_vector.get("producer-conformance-inferable-from-schema") is not False:
    raise SystemExit("plugin metadata vector must distinguish receiver validity from producer conformance")
if metadata_vector.get("canonicalization-required") is not False or metadata_vector.get("core-interprets-domain-fields") is not False:
    raise SystemExit("plugin metadata vector must retain exact opaque transport semantics")


def validate_capability_result(capabilities: list[dict[str, object]]) -> str:
    capability_ids: set[str] = set()
    for capability in capabilities:
        capability_id = capability.get("id")
        if not isinstance(capability_id, str) or capability_id in capability_ids:
            return "contract/protocol violation"
        capability_ids.add(capability_id)
        options = capability.get("options")
        if not isinstance(options, list):
            return "contract/protocol violation"
        option_keys: set[str] = set()
        for option in options:
            if not isinstance(option, dict):
                return "contract/protocol violation"
            key = option.get("key")
            choices = option.get("choices")
            if not isinstance(key, str) or key in option_keys or not isinstance(choices, list) or not choices:
                return "contract/protocol violation"
            option_keys.add(key)
            choice_values: set[str] = set()
            for choice in choices:
                if not isinstance(choice, dict):
                    return "contract/protocol violation"
                value = choice.get("value")
                if not isinstance(value, str) or value in choice_values:
                    return "contract/protocol violation"
                choice_values.add(value)
    return "valid"


def validate_configuration(options: list[dict[str, object]], selections: list[dict[str, object]]) -> str:
    options_by_key: dict[str, dict[str, object]] = {}
    for option in options:
        key = option.get("key")
        if not isinstance(key, str) or key in options_by_key:
            return "invalid-configuration"
        options_by_key[key] = option
    selections_by_key: dict[str, str] = {}
    for selection in selections:
        key = selection.get("key")
        value = selection.get("value")
        if not isinstance(key, str) or not isinstance(value, str) or key in selections_by_key or key not in options_by_key:
            return "invalid-configuration"
        selections_by_key[key] = value
    for key, option in options_by_key.items():
        selected = selections_by_key.get(key)
        if selected is None:
            if option.get("required") is True:
                return "invalid-configuration"
            continue
        choices = option.get("choices")
        if not isinstance(choices, list) or not any(isinstance(choice, dict) and choice.get("value") == selected for choice in choices):
            return "invalid-configuration"
    return "valid"


if shared_values["byte-stream"] != {
    "valid-data": {"ok": [0]}, "eof": {"ok": None}, "invalid-empty-data": {"ok": []}, "eof-sticky": True,
} or shared_values["progress"] != {
    "valid": [None, 0.0, 1.0], "invalid": [-0.1, 1.0001], "monotonicity-required": False,
}:
    raise SystemExit("shared value semantic conformance vector is incomplete or inconsistent")
enrichment_discovery = by_name["enrichment-capabilities-local-discovery"]
capabilities = enrichment_discovery["response-result"]
if set(enrichment_discovery["params"]) != {"context"} or len(capabilities) != 2 or "direct list WIT return" not in enrichment_discovery["meaning"] or "no typed lifecycle error wrapper" not in enrichment_discovery["meaning"] or enrichment_discovery["discovery-boundary"] != {
    "credentials": False, "configuration": False, "host-callbacks": False
}:
    raise SystemExit("Enrichment capability discovery vector must show context-only direct-list discovery without credentials, configuration, or callbacks")
if validate_capability_result(capabilities) != "valid":
    raise SystemExit("Enrichment representative discovery result must be a valid descriptor list")
fixed_capability = next((capability for capability in capabilities if capability.get("id") == "example.fixed"), None)
representative = next((capability for capability in capabilities if capability.get("id") == "example.operation"), None)
if fixed_capability is None or fixed_capability.get("options") != [] or representative is None:
    raise SystemExit("Enrichment valid discovery must include a fixed capability and representative configurable capability")
uniqueness = enrichment_discovery.get("uniqueness-vectors", {})
invalid_descriptor_cases = uniqueness.get("invalid-descriptors", [])
expected_descriptor_names = {"duplicate-capability-id", "duplicate-option-key", "empty-option-choices", "duplicate-choice-value"}
if {case.get("name") for case in invalid_descriptor_cases} != expected_descriptor_names:
    raise SystemExit("Enrichment invalid descriptor fixture set is incomplete")
for case in invalid_descriptor_cases:
    descriptor_result = case.get("discovery-result")
    if descriptor_result is None:
        descriptor = case.get("capability")
        descriptor_result = [descriptor] if isinstance(descriptor, dict) else []
    computed = validate_capability_result(descriptor_result) if isinstance(descriptor_result, list) else "valid"
    if computed != case.get("expected") or computed != "contract/protocol violation":
        raise SystemExit(f"Enrichment descriptor fixture {case.get('name')} does not compute to its declared producer violation")
valid_configuration_cases = uniqueness.get("valid-configurations", [])
invalid_configuration_cases = uniqueness.get("invalid-configurations", [])
if {case.get("name") for case in valid_configuration_cases} != {"required-mode-only-optional-language-omitted", "required-and-optional-selected", "optional-only-empty", "fixed-capability-empty"}:
    raise SystemExit("Enrichment valid caller configuration fixture set is incomplete")
if {case.get("name") for case in invalid_configuration_cases} != {"duplicate-identical", "duplicate-different", "unknown-option", "missing-required", "unsupported-choice", "extra-on-fixed-capability"}:
    raise SystemExit("Enrichment invalid caller configuration fixture set is incomplete")
for case in valid_configuration_cases + invalid_configuration_cases:
    selected_options = case.get("options", representative["options"])
    computed = validate_configuration(selected_options, case.get("configuration", []))
    if computed != case.get("expected"):
        raise SystemExit(f"Enrichment configuration fixture {case.get('name')} computes {computed!r}, expected {case.get('expected')!r}")
if any(case.get("expected") != "valid" for case in valid_configuration_cases) or any(case.get("expected") != "invalid-configuration" for case in invalid_configuration_cases):
    raise SystemExit("Enrichment configuration fixtures must declare the normative valid and invalid outcomes")
if uniqueness.get("failure-boundary") != {"invalid-discovered-descriptor": "contract/protocol violation", "invalid-caller-selection": "plugin-error.invalid-configuration", "unknown-inapplicable-or-stale-identity": "plugin-error.unsupported"}:
    raise SystemExit("Enrichment vectors must distinguish descriptor, caller, and capability identity failures")
response = by_name["lifecycle-response-result"]["response"]
expected_error = {"error": {"tag": "failed", "value": {"message": "example failure", "retryable": False}}}
if "error" in response or response.get("result") != expected_error:
    raise SystemExit("RPC v1 lifecycle response must require result and nest a typed plugin-error detail")
print("RPC v1 normative specification and conformance vectors are consistent")
