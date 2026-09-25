#!/usr/bin/env python3
"""Check semantic invariants in the generated WIT and package schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path


schema_path, package_schema_path = map(Path, sys.argv[1:3])
schema = json.loads(schema_path.read_text(encoding="utf-8"))
package_schema = json.loads(package_schema_path.read_text(encoding="utf-8"))

contracts = schema["contracts"]
packages = {contract["package"] for contract in contracts}
if len(packages) != 1 or None in packages or packages != {schema["package"]}:
    raise SystemExit("WIT package identity mismatch")

interfaces = {
    name: interface
    for contract in contracts
    for name, interface in contract["interfaces"].items()
}
worlds = {
    name: world
    for contract in contracts
    for name, world in contract["worlds"].items()
}
world_count = sum(len(contract["worlds"]) for contract in contracts)
if len(worlds) != world_count:
    raise SystemExit("WIT world names must be unique across the package")
if not worlds:
    raise SystemExit("the WIT package must declare at least one component world")

for name, world in worlds.items():
    imports = world["imports"]
    exports = world["exports"]
    if not imports or not exports:
        raise SystemExit(f"component world {name!r} must keep its own host imports and plugin exports")
    if any(interface not in interfaces for interface in imports + exports):
        raise SystemExit(f"component world {name!r} references an interface outside the WIT package")

if package_schema.get("x-stashd-contract-package") != schema["package"]:
    raise SystemExit("plugin package schema refers to a different WIT package identity")
package_required = set(package_schema.get("required", []))
if not {"id", "version", "components"} <= package_required:
    raise SystemExit("plugin package schema must declare one package id/version and its components")
package_properties = package_schema.get("properties", {})
if {"role", "kind"} & package_properties.keys():
    raise SystemExit("plugin package schema must not encode a singular role or kind")
components_schema = package_properties.get("components", {})
if components_schema.get("type") != "object":
    raise SystemExit("plugin package components must be an explicit world-keyed object")
if components_schema.get("maxProperties") is not None:
    raise SystemExit("plugin package schema must permit multiple component worlds")
component_worlds = components_schema.get("properties", {})
if set(component_worlds) != set(worlds):
    raise SystemExit("package role discovery does not match the WIT package's declared worlds")
if len(component_worlds) < 2:
    raise SystemExit("the package model must permit a multi-role package")
component_definition = package_schema.get("$defs", {}).get("component", {})
if not {"artifact"} <= set(component_definition.get("required", [])):
    raise SystemExit("each declared world must identify its component artifact")
if component_definition.get("properties", {}).keys() != {"artifact"}:
    raise SystemExit("component declarations must not duplicate package identity or role")
if any(value.get("$ref") != "#/$defs/component" for value in component_worlds.values()):
    raise SystemExit("every package component role must reference the common component declaration")

package_schema_text = json.dumps(package_schema, sort_keys=True).lower()
implementation_terms = ("php", "composer", "class-name", "entrypoint", "implementation-language")
if any(term in package_schema_text for term in implementation_terms):
    raise SystemExit("plugin package schema must remain language-independent")

input_contract = next(contract for contract in contracts if contract["file"] == "wit/input.wit")
input_host = input_contract["interfaces"]["input-host"]
input_plugin = input_contract["interfaces"]["input-plugin"]


def fields(interface: dict, record_name: str) -> dict[str, dict]:
    return {field["name"]: field["type"] for field in interface["records"][record_name]["fields"]}


def contains_named_type(value: object, name: str) -> bool:
    if isinstance(value, dict):
        return (value.get("kind") == "named" and value.get("name") == name) or any(
            contains_named_type(child, name) for child in value.values()
        )
    return isinstance(value, list) and any(contains_named_type(child, name) for child in value)


def require_metadata_facet(interface: dict, record_name: str) -> None:
    if record_name not in interface["records"]:
        raise SystemExit(f"Input record missing: {record_name}")
    record_fields = fields(interface, record_name)
    if "metadata" not in record_fields or not contains_named_type(record_fields["metadata"], "plugin-metadata"):
        raise SystemExit(f"{record_name} must retain extensible plugin metadata")


metadata_fields = {
    field["name"]: field["type"]
    for field in input_host["records"].get("plugin-metadata", {}).get("fields", [])
}
if not {"schema", "json"} <= metadata_fields.keys():
    raise SystemExit("plugin-metadata must retain its schema identifier and JSON payload")
if any(metadata_fields[name] != {"kind": "scalar", "name": "string"} for name in ("schema", "json")):
    raise SystemExit("plugin-metadata schema identifier and JSON payload must remain strings")

require_metadata_facet(input_host, "discovered-item")
require_metadata_facet(input_host, "staged-artifact")
require_metadata_facet(input_plugin, "resolved-input")

item_fields = fields(input_host, "discovered-item")
if not {"id", "reference"} <= item_fields.keys():
    raise SystemExit("discovered-item must retain its stable identity and opaque reference")
if input_plugin["uses"].get("discovered-item") != "input-host":
    raise SystemExit("input-plugin must reuse input-host's canonical discovered-item type")

for interface in (input_host, input_plugin):
    symbols = set(interface["records"]) | set(interface["variants"]) | set(interface["enums"])
    for record in interface["records"].values():
        symbols.update(field["name"] for field in record["fields"])
    for enum in interface["enums"].values():
        symbols.update(enum["values"])
    for variant in interface["variants"].values():
        symbols.update(value["name"] for value in variant["values"])
    for function in interface["functions"]:
        symbols.add(function["name"])
        symbols.update(argument["name"] for argument in function["arguments"])
    symbols = {symbol.lower() for symbol in symbols}
    forbidden = {
        "video", "audio", "media-kind", "artifact-role", "role", "requested-roles",
        "unavailable-artifact", "primary", "captions", "caption", "subtitles", "subtitle",
        "artwork", "artwork-reference", "thumbnail", "duration", "duration-seconds",
        "creator", "title", "description", "published-at", "kind", "upstream-state",
    } & symbols
    if forbidden:
        raise SystemExit(f"domain-specific Input concepts returned to the universal contract: {sorted(forbidden)!r}")
