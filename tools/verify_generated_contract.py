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
    raise SystemExit("plugin package components must be an object keyed by component identity")
if components_schema.get("minProperties", 0) < 1:
    raise SystemExit("plugin package must contain at least one component")
if components_schema.get("maxProperties") is not None:
    raise SystemExit("plugin package schema must permit multiple components")
if "properties" in components_schema or components_schema.get("additionalProperties") != {"$ref": "#/$defs/component"}:
    raise SystemExit("plugin package components must be independently identified by object key")
if components_schema.get("propertyNames", {}).get("pattern") != "^[a-z0-9][a-z0-9._-]*$":
    raise SystemExit("component identities must use the stable component-ID pattern")
component_definition = package_schema.get("$defs", {}).get("component", {})
if not {"world", "artifact"} <= set(component_definition.get("required", [])):
    raise SystemExit("each identified component must declare its WIT world and artifact")
component_properties = component_definition.get("properties", {})
if set(component_properties) != {"world", "artifact"}:
    raise SystemExit("component declarations must contain only world and artifact")
if component_properties["world"].get("enum") != sorted(worlds):
    raise SystemExit("component world choices must match the canonical WIT worlds exactly")
if component_definition.get("additionalProperties") is not False:
    raise SystemExit("component declarations must reject unspecified fields")

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

enrichment_contract = next(
    (contract for contract in contracts if contract["file"] == "wit/enrichment.wit"),
    None,
)
if enrichment_contract is None:
    raise SystemExit("the canonical Enrichment contract is missing")
enrichment_host = enrichment_contract["interfaces"].get("enrichment-host", {})
enrichment_plugin = enrichment_contract["interfaces"].get("enrichment-plugin", {})
enrichment_world = enrichment_contract["worlds"].get("enrichment-world", {})
if enrichment_world != {"imports": ["enrichment-host"], "exports": ["enrichment-plugin"]}:
    raise SystemExit("enrichment-world must have its own enrichment-host import and enrichment-plugin export")


def require_fields(interface: dict, record_name: str, expected: set[str]) -> dict[str, dict]:
    if record_name not in interface.get("records", {}):
        raise SystemExit(f"Enrichment record missing: {record_name}")
    record_fields = fields(interface, record_name)
    if not expected <= record_fields.keys():
        raise SystemExit(f"Enrichment {record_name} must include {sorted(expected)!r}")
    return record_fields


metadata_fields = require_fields(enrichment_host, "plugin-metadata", {"schema", "json"})
if any(metadata_fields[name] != {"kind": "scalar", "name": "string"} for name in ("schema", "json")):
    raise SystemExit("Enrichment metadata must retain its opaque schema identifier and JSON payload")

asset_fields = require_fields(enrichment_host, "asset", {"id", "reference", "media-type", "size-bytes"})
if "assets" not in fields(enrichment_host, "item-context"):
    raise SystemExit("Enrichment context must include the Item's Assets")
context_fields = fields(enrichment_host, "item-context")
if not {"item-id", "assets", "metadata"} <= context_fields.keys():
    raise SystemExit("Enrichment context must expose generic Item identity, Assets, and metadata")
if not contains_named_type(context_fields["assets"], "asset"):
    raise SystemExit("Enrichment context Assets must use the canonical Asset descriptor")
asset_reader = next(
    (resource for resource in enrichment_host.get("resources", []) if resource["name"] == "asset-reader"),
    None,
)
if asset_reader is None or not any(function["name"] == "read" for function in asset_reader["functions"]):
    raise SystemExit("Enrichment host must expose controlled reads of existing Asset bytes")
if not any(function["name"] == "open-asset" for function in enrichment_host.get("functions", [])):
    raise SystemExit("Enrichment host must open an existing Asset for reading")
if not any(resource["name"] == "staging-area" for resource in enrichment_host.get("resources", [])):
    raise SystemExit("Enrichment host must stage candidate output Assets")

capability_fields = require_fields(enrichment_plugin, "capability", {"id", "revision"})
if not any(function["name"] == "capabilities" for function in enrichment_plugin.get("functions", [])):
    raise SystemExit("Enrichment must let a plugin declare applicable capabilities for Item/Asset context")
enrich_function = next(
    (function for function in enrichment_plugin.get("functions", []) if function["name"] == "enrich"),
    None,
)
if enrich_function is None or not contains_named_type(enrich_function.get("result"), "enrichment-result"):
    raise SystemExit("Enrichment must run a declared capability and return an enrichment-result")
result_fields = require_fields(enrichment_plugin, "enrichment-result", {"metadata", "assets"})
derived_fields = require_fields(
    enrichment_plugin,
    "derived-asset",
    {"artifact", "derived-from", "activity", "activity-version"},
)
if not contains_named_type(result_fields["metadata"], "plugin-metadata"):
    raise SystemExit("Enrichment results must support plugin-owned metadata facets")
if not contains_named_type(result_fields["assets"], "derived-asset"):
    raise SystemExit("Enrichment results must support durable derived Assets")
if not any(
    function["name"] == "enrich" and contains_named_type(function.get("result"), "plugin-error")
    for function in enrichment_plugin.get("functions", [])
):
    raise SystemExit("Enrichment execution must return typed plugin errors")

# Keep the universal Enrichment symbols domain-neutral. Examples belong in
# architecture and issue documentation, not in the canonical wire contract.
enrichment_symbols = set(enrichment_host.get("records", {})) | set(enrichment_plugin.get("records", {}))
enrichment_symbols |= set(enrichment_host.get("variants", {})) | set(enrichment_plugin.get("variants", {}))
for interface in (enrichment_host, enrichment_plugin):
    for record in interface.get("records", {}).values():
        enrichment_symbols.update(field["name"] for field in record["fields"])
    for function in interface.get("functions", []):
        enrichment_symbols.add(function["name"])
        enrichment_symbols.update(argument["name"] for argument in function["arguments"])
enrichment_symbols = {symbol.lower() for symbol in enrichment_symbols}
enrichment_specific = {
    "transcription", "transcript", "ocr", "translation", "subtitle", "subtitles",
    "chapter", "chapters", "artwork", "cover-art", "identification",
}
if enrichment_specific & enrichment_symbols:
    raise SystemExit(
        f"domain-specific Enrichment concepts returned to the universal contract: {sorted(enrichment_specific & enrichment_symbols)!r}"
    )
