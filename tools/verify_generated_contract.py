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
io_contract = next((contract for contract in contracts if contract["file"] == "wit/io.wit"), None)
if io_contract is None:
    raise SystemExit("the shared host-managed I/O contract is missing")
io_host = io_contract["interfaces"].get("io-host", {})


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


metadata_fields = fields(io_host, "plugin-metadata")
if not {"schema", "json"} <= metadata_fields.keys():
    raise SystemExit("plugin-metadata must retain its schema identifier and JSON payload")
if any(metadata_fields[name] != {"kind": "scalar", "name": "string"} for name in ("schema", "json")):
    raise SystemExit("plugin-metadata schema identifier and JSON payload must remain strings")

require_metadata_facet(input_host, "discovered-item")
require_metadata_facet(input_plugin, "resolved-input")
if input_plugin["uses"].get("staged-artifact") != "io-host":
    raise SystemExit("Input results must return the shared canonical artifact descriptor")
acquisition_fields = fields(input_plugin, "acquisition-result")
if "artifacts" not in acquisition_fields or not contains_named_type(acquisition_fields["artifacts"], "staged-artifact"):
    raise SystemExit("Input acquisition must return completed outputs through the canonical staged-artifact descriptor")

staged_fields = fields(io_host, "staged-artifact")
if not {"reference", "media-type", "size-bytes", "metadata"} <= staged_fields.keys():
    raise SystemExit("completed staged output must return the canonical generic staged-artifact descriptor")
if not contains_named_type(staged_fields["metadata"], "plugin-metadata"):
    raise SystemExit("staged artifacts must retain plugin-owned metadata")

byte_stream = next((resource for resource in io_host.get("resources", []) if resource["name"] == "byte-stream"), None)
if byte_stream is None:
    raise SystemExit("host-managed I/O must expose a bounded byte-stream resource")
stream_read = next((function for function in byte_stream["functions"] if function["name"] == "read"), None)
if stream_read is None or stream_read.get("arguments") != [] or stream_read.get("result") != {
    "kind": "result",
    "ok": {"kind": "option", "value": {"kind": "list", "value": {"kind": "scalar", "name": "u8"}}},
    "error": {"kind": "named", "name": "stream-error"},
}:
    raise SystemExit("byte-stream reads must return optional bounded chunks and typed stream errors")

writer = next((resource for resource in io_host.get("resources", []) if resource["name"] == "staged-writer"), None)
if writer is None:
    raise SystemExit("host-managed I/O must expose a staged output writer")
writer_functions = {function["name"]: function for function in writer["functions"]}
write = writer_functions.get("write")
finish = writer_functions.get("finish")
if write is None or write["arguments"] != [{"name": "bytes", "type": {"kind": "list", "value": {"kind": "scalar", "name": "u8"}}}]:
    raise SystemExit("staged output must accept explicit byte chunks")
if write.get("result") != {
    "kind": "result",
    "ok": None,
    "error": {"kind": "named", "name": "staging-error"},
}:
    raise SystemExit("staged chunk writes must report host staging errors")
if finish is None or finish.get("result") != {
    "kind": "result",
    "ok": {"kind": "named", "name": "staged-artifact"},
    "error": {"kind": "named", "name": "staging-error"},
}:
    raise SystemExit("only successful writer finalization may return a staged-artifact")
staging_area = next((resource for resource in io_host.get("resources", []) if resource["name"] == "staging-area"), None)
create = next((function for function in staging_area["functions"] if function["name"] == "create"), None) if staging_area else None
if create is None or create.get("result") != {
    "kind": "result",
    "ok": {"kind": "named", "name": "staged-writer"},
    "error": {"kind": "named", "name": "staging-error"},
}:
    raise SystemExit("the invocation staging area must explicitly create host-managed staged writers")
if create.get("arguments") != [
    {"name": "media-type", "type": {"kind": "option", "value": {"kind": "scalar", "name": "string"}}},
    {"name": "metadata", "type": {"kind": "list", "value": {"kind": "named", "name": "plugin-metadata"}}},
]:
    raise SystemExit("staged writers must be created with generic media type and metadata, without a path")
open_staging = next((function for function in io_host.get("functions", []) if function["name"] == "open-staging-area"), None)
if open_staging is None or open_staging.get("result") != {"kind": "named", "name": "staging-area"}:
    raise SystemExit("plugins must explicitly open their invocation-scoped staging area")

for filename, world_name in (("wit/input.wit", "input-world"), ("wit/enrichment.wit", "enrichment-world"), ("wit/broadcast.wit", "broadcast-world")):
    contract = next(item for item in contracts if item["file"] == filename)
    world = contract["worlds"].get(world_name, {})
    if "io-host" not in world.get("imports", []):
        raise SystemExit(f"{world_name} must import the shared host-managed I/O interface")

def require_streamed_http_response(filename: str, interface_name: str) -> None:
    contract = next(item for item in contracts if item["file"] == filename)
    interface = contract["interfaces"][interface_name]
    response_fields = fields(interface, "http-response")
    if response_fields.get("body") != {"kind": "named", "name": "byte-stream"} or interface["uses"].get("byte-stream") != "io-host":
        raise SystemExit(f"{filename} HTTP responses must expose bodies as bounded byte streams")


require_streamed_http_response("wit/input.wit", "input-host")
require_streamed_http_response("wit/broadcast.wit", "broadcast-host")

helper = next((function for function in io_host.get("functions", []) if function["name"] == "run-helper"), None)
output_argument = next((argument for argument in helper.get("arguments", []) if argument["name"] == "output"), None) if helper else None
if output_argument is None or output_argument["type"] != {
    "kind": "option",
    "value": {"kind": "borrow", "value": {"kind": "named", "name": "staged-writer"}},
}:
    raise SystemExit("helper output must have an explicit staged-writer boundary")
for filename in ("wit/io.wit", "wit/input.wit", "wit/enrichment.wit", "wit/broadcast.wit"):
    contract = next(item for item in contracts if item["file"] == filename)
    for interface in contract["interfaces"].values():
        for resource in interface.get("resources", []):
            if resource["name"] == "staging-area" and any(
                argument["name"] in {"path", "relative-path", "filesystem-path", "host-path"}
                for function in resource.get("functions", [])
                for argument in function.get("arguments", [])
            ):
                raise SystemExit("host filesystem paths must not appear in staging operations")

item_fields = fields(input_host, "discovered-item")
if not {"id", "reference"} <= item_fields.keys():
    raise SystemExit("discovered-item must retain its stable identity and opaque reference")
delegation_fields = input_host["records"].get("input-delegation", {}).get("fields", [])
if {field["name"] for field in delegation_fields} != {"reference"}:
    raise SystemExit("Input delegation must contain only one opaque reference")
if delegation_fields[0]["type"] != {"kind": "scalar", "name": "string"}:
    raise SystemExit("Input delegation reference must remain an opaque string")
delegation_type = item_fields.get("delegation")
if delegation_type != {"kind": "option", "value": {"kind": "named", "name": "input-delegation"}}:
    raise SystemExit("discovered-item must carry optional generic Input delegation context")
if input_plugin["uses"].get("discovered-item") != "input-host":
    raise SystemExit("input-plugin must reuse input-host's canonical discovered-item type")
if input_plugin["uses"].get("input-delegation") != "input-host":
    raise SystemExit("input-plugin must reuse input-host's canonical input-delegation type")
if "input-delegation" in input_plugin["records"]:
    raise SystemExit("Input delegation identity must remain in the host-owned discovery boundary")

delegation_resolver = next(
    (function for function in input_plugin["functions"] if function["name"] == "resolve-delegation"),
    None,
)
if delegation_resolver is None:
    raise SystemExit("Input must expose the generic resolve-delegation entry point")
if delegation_resolver["arguments"] != [
    {"name": "delegation", "type": delegation_type["value"]}
]:
    raise SystemExit("resolve-delegation must receive discovered-item's canonical input-delegation type")
if delegation_resolver.get("result") != {
    "kind": "result",
    "ok": {"kind": "named", "name": "resolved-input"},
    "error": {"kind": "named", "name": "plugin-error"},
}:
    raise SystemExit("resolve-delegation must use the generic Input resolution and error types")
discover_function = next(
    (function for function in input_plugin["functions"] if function["name"] == "discover"),
    None,
)
if discover_function is None or discover_function.get("result") != {
    "kind": "result",
    "ok": {"kind": "list", "value": {"kind": "named", "name": "discovered-item"}},
    "error": {"kind": "named", "name": "plugin-error"},
}:
    raise SystemExit("Input discovery must return the canonical discovered-item handoff boundary")

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
if set(enrichment_world.get("imports", [])) != {"io-host", "enrichment-host"} or enrichment_world.get("exports") != ["enrichment-plugin"]:
    raise SystemExit("enrichment-world must import shared I/O and its own host interface")


def require_fields(interface: dict, record_name: str, expected: set[str]) -> dict[str, dict]:
    if record_name not in interface.get("records", {}):
        raise SystemExit(f"Enrichment record missing: {record_name}")
    record_fields = fields(interface, record_name)
    if not expected <= record_fields.keys():
        raise SystemExit(f"Enrichment {record_name} must include {sorted(expected)!r}")
    return record_fields


asset_fields = require_fields(enrichment_host, "asset", {"id", "reference", "media-type", "size-bytes"})
if "assets" not in fields(enrichment_host, "item-context"):
    raise SystemExit("Enrichment context must include the Item's Assets")
context_fields = fields(enrichment_host, "item-context")
if not {"item-id", "assets", "metadata"} <= context_fields.keys():
    raise SystemExit("Enrichment context must expose generic Item identity, Assets, and metadata")
if not contains_named_type(context_fields["assets"], "asset"):
    raise SystemExit("Enrichment context Assets must use the canonical Asset descriptor")
open_asset = next((function for function in enrichment_host.get("functions", []) if function["name"] == "open-asset"), None)
if open_asset is None or not contains_named_type(open_asset.get("result"), "byte-stream") or enrichment_host["uses"].get("byte-stream") != "io-host":
    raise SystemExit("Enrichment must open bounded streams over existing Asset bytes")
if open_asset.get("arguments") != [
    {"name": "reference", "type": {"kind": "scalar", "name": "string"}},
    {"name": "offset", "type": {"kind": "scalar", "name": "u64"}},
    {"name": "length", "type": {"kind": "option", "value": {"kind": "scalar", "name": "u64"}}},
]:
    raise SystemExit("Enrichment Asset streams must support explicit partial reads by byte range")
if not any(function["name"] == "open-staging-area" for function in io_host.get("functions", [])):
    raise SystemExit("Enrichment must use the shared host-managed staging boundary")

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
if enrichment_plugin["uses"].get("staged-artifact") != "io-host":
    raise SystemExit("Enrichment results must return the shared canonical staged-artifact descriptor")
if not contains_named_type(derived_fields["artifact"], "staged-artifact"):
    raise SystemExit("Enrichment derived Assets must reference the completed generic staged artifact")
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
