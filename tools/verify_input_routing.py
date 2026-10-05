#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


root = Path(__file__).resolve().parents[1]
schema = json.loads((root / "schema/wit-schema.json").read_text(encoding="utf-8"))
contract = next(contract for contract in schema["contracts"] if contract["file"] == "wit/input.wit")
interfaces = {name: interface for component in schema["contracts"] for name, interface in component["interfaces"].items()}
plugin = interfaces["input-plugin"]
functions = {function["name"]: function for function in plugin["functions"]}


def valid_value(value: object, shape: dict, owner: str) -> bool:
    kind = shape["kind"]
    if kind == "scalar":
        if shape["name"] == "string":
            return isinstance(value, str)
        if shape["name"] == "bool":
            return type(value) is bool
        if shape["name"] == "s64":
            return isinstance(value, str) and re.fullmatch(r"0|-?[1-9][0-9]*", value) is not None and -(2**63) <= int(value) < 2**63
        return False
    if kind == "option":
        return value is None or valid_value(value, shape["value"], owner)
    if kind == "list":
        return isinstance(value, list) and all(valid_value(element, shape["value"], owner) for element in value)
    if kind != "named":
        return False
    name = shape["name"]
    owner = interfaces[owner].get("uses", {}).get(name, owner)
    interface = interfaces[owner]
    record = interface.get("records", {}).get(name)
    if record is not None:
        return isinstance(value, dict) and set(value) == {field["name"] for field in record["fields"]} and all(
            valid_value(value[field["name"]], field["type"], owner) for field in record["fields"]
        )
    variant = interface.get("variants", {}).get(name)
    if variant is not None:
        if not isinstance(value, dict) or set(value) != {"tag", "value"}:
            return False
        case = next((case for case in variant["values"] if case["name"] == value["tag"]), None)
        return case is not None and valid_value(value["value"], case["type"], owner)
    return False


def valid_request(method: str, params: dict) -> bool:
    prefix = "stashd:plugin/input-plugin."
    function = functions.get(method[len(prefix):]) if method.startswith(prefix) else None
    return function is not None and set(params) == {argument["name"] for argument in function["arguments"]} and all(
        valid_value(params[argument["name"]], argument["type"], "input-plugin") for argument in function["arguments"]
    )


source_type = {"kind": "named", "name": "source"}
probe_method = "stashd:plugin/input-plugin.can-resolve"
resolve_method = "stashd:plugin/input-plugin.resolve"
cases = (
    ("RSS HTTP URL", "HTTP URL", "http"),
    ("RSS YouTube URL", "YouTube URL", "youtube"),
    ("RSS magnet URI / BitTorrent", "magnet URI / BitTorrent", "bittorrent"),
    ("OPDS HTTP publication", "HTTP publication", "http"),
    ("generic feed unknown source", "unknown source", None),
    ("direct YouTube URL", "YouTube URL", "youtube"),
)
plugin_references = {
    "http": {"HTTP URL", "HTTP publication"},
    "youtube": {"YouTube URL"},
    "bittorrent": {"magnet URI / BitTorrent"},
}
received = {}
for label, reference, expected in cases:
    source = {"reference": reference, "values": []}
    item = {"id": label, "reference": "opaque-item-reference", "source": source, "size-bytes": None, "size-estimated": False, "metadata": []}
    assert valid_value(item, {"kind": "named", "name": "discovered-item"}, "input-host"), label
    provenance = ("discovering-package", "discovering-component", item["id"]) if label != "direct YouTube URL" else None
    retained_provenance = copy.deepcopy(provenance)
    probed = []
    accepted = []
    for candidate, understood in plugin_references.items():
        wire_params = json.loads(json.dumps({"source": source}))
        assert valid_request(probe_method, wire_params), label
        probed.append(wire_params["source"])
        answer = wire_params["source"]["reference"] in understood
        assert valid_value(answer, functions["can-resolve"]["result"], "input-plugin"), label
        if answer:
            accepted.append(candidate)
    assert accepted == ([] if expected is None else [expected]), label
    assert provenance == retained_provenance, label
    if accepted:
        params = json.loads(json.dumps({"source": source, "credentials": []}))
        assert valid_request(resolve_method, params), label
        assert all(params["source"] == value for value in probed), label
        assert set(params) == {"source", "credentials"}, label
        received[label] = params
assert received["RSS YouTube URL"] == received["direct YouTube URL"]
configured = {"reference": None, "values": [{"key": "opaque-option", "value": {"tag": "text", "value": "opaque-content"}}]}
assert valid_request(probe_method, {"source": configured})
assert valid_request(resolve_method, {"source": configured, "credentials": []})
assert valid_value({"reference": "opaque-reference", "values": configured["values"]}, source_type, "input-host")
assert valid_value(False, functions["can-resolve"]["result"], "input-plugin")
credential_fields = interfaces["io-host"]["records"]["credential-reference"]["fields"]
credential_reference = {field["name"]: "opaque-reference" for field in credential_fields}
assert valid_request(resolve_method, {"source": configured, "credentials": [{"name": "configured-slot", "reference": credential_reference}]})
for number in ("0", "1", "-1", str(-(2**63)), str(2**63 - 1)):
    assert valid_value(number, {"kind": "scalar", "name": "s64"}, "input-host")
for number in ("01", "-0", "--1", "+1", "١", str(2**63), str(-(2**63) - 1)):
    assert not valid_value(number, {"kind": "scalar", "name": "s64"}, "input-host")
for method, params in (
    ("stashd:plugin/input-plugin.resolve-delegation", {"delegation": {"reference": "opaque-reference"}, "credentials": []}),
    (resolve_method, {"source": [], "credentials": []}),
    (resolve_method, {"source": "opaque-reference", "credentials": []}),
    (resolve_method, {"source": {"reference": "opaque-reference"}, "credentials": []}),
    (probe_method, {"source": "opaque-reference"}),
    (probe_method, {"source": configured, "credentials": []}),
):
    assert not valid_request(method, params), (method, params)
legacy_item = {"id": "item", "reference": "opaque-item-reference", "delegation": {"reference": "opaque-reference"}, "size-bytes": None, "size-estimated": False, "metadata": []}
assert not valid_value(legacy_item, {"kind": "named", "name": "discovered-item"}, "input-host")
assert not valid_value({"reference": "opaque-reference", "values": [], "provider": "target"}, source_type, "input-host")
assert not valid_value({"ok": True}, functions["can-resolve"]["result"], "input-plugin")
print("Input routing: six forcing cases, identical direct/discovered resolution, opaque configuration, and obsolete wire rejection passed")
