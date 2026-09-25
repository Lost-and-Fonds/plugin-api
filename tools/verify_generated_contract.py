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
expected_package = "stashd:plugin@0.15.0"
if len(packages) != 1 or None in packages or packages != {schema["package"]} or schema["package"] != expected_package:
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

if package_schema.get("x-stashd-contract-package") != schema["package"] or package_schema.get("x-stashd-contract-package") != expected_package:
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
plugin_types = io_contract["interfaces"].get("plugin-types", {})
http_host = io_contract["interfaces"].get("http-host", {})
progress_host = io_contract["interfaces"].get("progress-host", {})
logging_host = io_contract["interfaces"].get("logging-host", {})


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
if input_host["uses"].get("plugin-metadata") != "io-host" or input_plugin["uses"].get("plugin-metadata") != "io-host":
    raise SystemExit("Input metadata facets must reuse the canonical io-host type")
if input_plugin["uses"].get("staged-artifact") != "io-host":
    raise SystemExit("Input results must return the shared canonical artifact descriptor")
acquisition_fields = fields(input_plugin, "acquisition-result")
if "artifacts" not in acquisition_fields or not contains_named_type(acquisition_fields["artifacts"], "staged-artifact"):
    raise SystemExit("Input acquisition must return completed outputs through the canonical staged-artifact descriptor")

broadcast_contract = next(contract for contract in contracts if contract["file"] == "wit/broadcast.wit")
broadcast_plugin = broadcast_contract["interfaces"]["broadcast-plugin"]
item_fields = fields(broadcast_plugin, "item")
if not {"id", "assets", "metadata"} <= item_fields.keys():
    raise SystemExit("Broadcast Items must carry stable identity, preserved Assets, and plugin metadata facets")
if item_fields["metadata"] != {"kind": "list", "value": {"kind": "named", "name": "plugin-metadata"}} or broadcast_plugin["uses"].get("plugin-metadata") != "io-host":
    raise SystemExit("Broadcast Items must use the canonical io-host.plugin-metadata facets")
if item_fields["assets"] != {"kind": "list", "value": {"kind": "named", "name": "asset"}}:
    raise SystemExit("Broadcast Items must expose a generic list of preserved Assets")
legacy_item_fields = {"source-reference", "title", "description", "published-at", "duration-seconds", "resources"}
domain_item_fields = {
    "kind", "audio", "video", "author", "artist", "season", "episode", "language", "genre",
    "duration", "thumbnail", "publication-date", "published-date",
}
if (legacy_item_fields | domain_item_fields) & item_fields.keys():
    raise SystemExit("Broadcast Items must keep source/domain fields in plugin-owned metadata facets")
asset_fields = fields(broadcast_plugin, "asset")
if not {"id", "reference", "media-type", "size-bytes", "metadata"} <= asset_fields.keys():
    raise SystemExit("Broadcast Assets must retain generic identity, opaque reference, media type, size, and metadata")
if asset_fields["id"] != {"kind": "scalar", "name": "string"} or asset_fields["reference"] != {"kind": "scalar", "name": "string"}:
    raise SystemExit("Broadcast Asset identity and host locator must remain opaque strings")
if asset_fields["media-type"] != {"kind": "option", "value": {"kind": "scalar", "name": "string"}} or asset_fields["size-bytes"] != {"kind": "scalar", "name": "u64"}:
    raise SystemExit("Broadcast Asset media type and size must remain generic representation facts")
if asset_fields["metadata"] != {"kind": "list", "value": {"kind": "named", "name": "plugin-metadata"}}:
    raise SystemExit("Broadcast Assets must use canonical plugin metadata facets")
if {"kind", "derivation-key", "url"} & asset_fields.keys():
    raise SystemExit("Broadcast Assets must not impose a kind taxonomy, derivation key, or public URL")
broadcast_functions = {function["name"]: function for function in broadcast_plugin.get("functions", [])}
if set(broadcast_functions) != {"publish", "operation"}:
    raise SystemExit("Broadcast must expose direct publish and independent operation, without prepare/finalize phases")
publish = broadcast_functions["publish"]
if publish.get("arguments") != [
    {"name": "request", "type": {"kind": "named", "name": "publish-request"}},
    {"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}},
] or publish.get("result") != {
    "kind": "result",
    "ok": {"kind": "named", "name": "publication"},
    "error": {"kind": "named", "name": "plugin-error"},
}:
    raise SystemExit("Broadcast publish must accept one request and invocation credentials and return a publication directly")
operation = broadcast_functions["operation"]
if operation.get("arguments") != [
    {"name": "request", "type": {"kind": "named", "name": "operation-request"}},
    {"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}},
] or operation.get("result") != {
    "kind": "result",
    "ok": {"kind": "named", "name": "operation-result"},
    "error": {"kind": "named", "name": "plugin-error"},
}:
    raise SystemExit("Broadcast operation must remain a separate interactive operation with its own request and result")
if {"preparation", "derived-artifact", "finalization-request"} & broadcast_plugin.get("records", {}).keys():
    raise SystemExit("Broadcast must not define cross-invocation preparation or finalization records")

publication_fields = fields(broadcast_plugin, "publication")
publication_artifact = publication_fields.get("artifact")
if publication_artifact != {"kind": "option", "value": {"kind": "named", "name": "staged-artifact"}} or broadcast_plugin["uses"].get("staged-artifact") != "io-host":
    raise SystemExit("Broadcast publication must allow no local artifact or the canonical staged artifact")
if publication_fields.get("files") != {"kind": "option", "value": {"kind": "list", "value": {"kind": "named", "name": "published-file"}}}:
    raise SystemExit("filesystem-specific published files must be optional and scoped")
if publication_fields.get("destination-metadata") != {"kind": "list", "value": {"kind": "named", "name": "plugin-metadata"}}:
    raise SystemExit("destination receipts must use canonical opaque plugin metadata facets")
if broadcast_plugin["uses"].get("plugin-metadata") != "io-host":
    raise SystemExit("Broadcast results must reuse canonical io-host.plugin-metadata")
published_file_fields = fields(next(contract for contract in contracts if contract["file"] == "wit/broadcast.wit")["interfaces"]["broadcast-host"], "published-file")
if published_file_fields.get("relative-path") != {"kind": "scalar", "name": "string"} or "source-reference" in published_file_fields:
    raise SystemExit("filesystem result paths must stay inside published-file without provider source references")
for value_interface in (broadcast_plugin, broadcast_contract["interfaces"].get("broadcast-host", {})):
    for record_name, record in value_interface.get("records", {}).items():
        if record_name != "published-file" and "relative-path" in {field["name"] for field in record["fields"]}:
            raise SystemExit("filesystem paths must remain scoped to optional published-file results")
if "artifact" in broadcast_plugin.get("records", {}):
    raise SystemExit("Broadcast must not duplicate the shared staged-artifact descriptor")

staged_fields = fields(io_host, "staged-artifact")
if not {"reference", "media-type", "size-bytes", "metadata"} <= staged_fields.keys():
    raise SystemExit("completed staged output must return the canonical generic staged-artifact descriptor")
if not contains_named_type(staged_fields["metadata"], "plugin-metadata"):
    raise SystemExit("staged artifacts must retain plugin-owned metadata")

# Inputs receive configured opaque credential bindings on every lifecycle call.
# The host owns the references and grants access only to the active invocation.
credential_reference = {"kind": "named", "name": "credential-reference"}
credential_binding = {"kind": "named", "name": "credential-binding"}
credential_refs = fields(io_host, "credential-reference")
if set(credential_refs) != {"id"} or credential_refs["id"] != {"kind": "scalar", "name": "string"}:
    raise SystemExit("credential references must remain opaque, language-neutral host identities")
credential_bindings = fields(io_host, "credential-binding")
if set(credential_bindings) != {"name", "reference"} or credential_bindings["name"] != {"kind": "scalar", "name": "string"} or credential_bindings["reference"] != credential_reference:
    raise SystemExit("credential bindings must map a plugin-defined slot to an opaque host reference")

allowed_credential_records = {("io-host", "credential-reference"), ("io-host", "credential-binding")}
for interface_name, interface in interfaces.items():
    for record_name in interface.get("records", {}):
        if "credential" in record_name and (interface_name, record_name) not in allowed_credential_records:
            raise SystemExit("credential selectors and bindings must use the existing canonical io-host records")

secret_field_names = {
    "credential", "credentials", "password", "secret", "token", "access-token",
    "refresh-token", "api-key", "private-key", "bearer",
}

def require_no_embedded_credentials(owner: str, record_set: dict) -> None:
    for record_name, record in record_set.items():
        for field in record["fields"]:
            if field["name"] in secret_field_names:
                raise SystemExit(f"{owner}.{record_name} must not carry credentials or raw secret fields")
            if any(contains_named_type(field["type"], name) for name in ("credential-reference", "credential-binding", "credential-access", "input-credential")):
                raise SystemExit(f"{owner}.{record_name} must keep credentials separate from generic data")

require_no_embedded_credentials("Input", input_host["records"])
require_no_embedded_credentials("plugin metadata", {"plugin-metadata": io_host["records"]["plugin-metadata"]})
credential_error = {"kind": "named", "name": "credential-error"}
credential_access = next((resource for resource in input_host.get("resources", []) if resource["name"] == "credential-access"), None)
credential_read = next((function for function in credential_access.get("functions", []) if function["name"] == "read"), None) if credential_access else None
if credential_read is None or credential_read.get("result") != {
    "kind": "result", "ok": {"kind": "scalar", "name": "string"}, "error": credential_error,
}:
    raise SystemExit("raw credential access must be an explicit, typed, invocation-scoped escape hatch")
open_credential = next((function for function in input_host.get("functions", []) if function["name"] == "open-credential"), None)
if open_credential is None or open_credential.get("arguments") != [
    {"name": "reference", "type": credential_reference},
] or open_credential.get("result") != {
    "kind": "result", "ok": {"kind": "named", "name": "credential-access"}, "error": credential_error,
}:
    raise SystemExit("credential access must resolve an opaque reference through the shared host boundary")
credential_errors = input_host["variants"].get("credential-error", {}).get("values", [])
if {value["name"] for value in credential_errors} != {"denied", "unavailable"}:
    raise SystemExit("credential denial and unavailability must remain distinguishable")
if any(resource["name"] == "credential-access" for resource in io_host.get("resources", [])):
    raise SystemExit("raw credential access must not become a shared host capability")

input_http_credential = fields(http_host, "http-request").get("credential")
if input_http_credential != {"kind": "option", "value": credential_reference}:
    raise SystemExit("shared HTTP must select credentials through the opaque reference model")
http_errors = {value["name"] for value in http_host["variants"].get("http-error", {}).get("values", [])}
if not {"denied", "credential-unavailable", "authentication-rejected"} <= http_errors:
    raise SystemExit("shared HTTP must distinguish access denial, unavailable credentials, and authentication rejection")
source_value_fields = fields(input_plugin, "source-value")
option_fields = fields(input_plugin, "input-option")
for record_name, record_fields in (("source-value", source_value_fields), ("input-option", option_fields)):
    if any(contains_named_type(value, "input-credential") or contains_named_type(value, "credential-access") for value in record_fields.values()):
        raise SystemExit(f"{record_name} must not carry raw or access-handle credential material")
    credentialish = {"credential", "credentials", "password", "secret", "token", "api-key", "private-key"}
    if credentialish & record_fields.keys():
        raise SystemExit(f"{record_name} must not grow direct credential or secret fields")
metadata_record = io_contract["interfaces"]["io-host"]["records"]["plugin-metadata"]
delegation_record = input_host["records"]["input-delegation"]
for record_name, record in (("plugin-metadata", metadata_record), ("input-delegation", delegation_record)):
    record_names = {field["name"] for field in record["fields"]}
    if credentialish & record_names:
        raise SystemExit(f"{record_name} must not become a credential transport")
if "input-credential" in input_plugin["records"]:
    raise SystemExit("the acquisition-only raw Input credential model must be removed")

def require_credential_bindings(function_name: str, interface: dict = input_plugin) -> None:
    function = next((function for function in interface["functions"] if function["name"] == function_name), None)
    if function is None or not any(
        argument["name"] == "credentials"
        and argument["type"] == {"kind": "list", "value": credential_binding}
        for argument in function["arguments"]
    ):
        raise SystemExit(f"Input {function_name} must receive host-authorized credential bindings")

for lifecycle_phase in ("resolve", "resolve-delegation", "discover"):
    require_credential_bindings(lifecycle_phase)
acquisition_credentials = fields(input_plugin, "acquisition-options").get("credentials")
if acquisition_credentials != {"kind": "list", "value": credential_binding}:
    raise SystemExit("Input acquisition must use the same host-managed credential bindings as other phases")
if input_plugin["variants"].get("plugin-error", {}).get("values") is None:
    raise SystemExit("Input must retain typed lifecycle errors")
error_cases = {value["name"] for value in input_plugin["variants"]["plugin-error"]["values"]}
if not {"credential-denied", "credential-unavailable", "authentication"} <= error_cases:
    raise SystemExit("Input must preserve credential denial, unavailability, and authentication failure distinctions")

broadcast_contract = next(contract for contract in contracts if contract["file"] == "wit/broadcast.wit")
broadcast_plugin = broadcast_contract["interfaces"].get("broadcast-plugin", {})
if broadcast_plugin.get("uses", {}).get("credential-binding") != "io-host":
    raise SystemExit("Broadcast must reuse io-host.credential-binding")
for phase in ("publish", "operation"):
    require_credential_bindings(phase, broadcast_plugin)
require_no_embedded_credentials("Broadcast", broadcast_plugin.get("records", {}))
require_no_embedded_credentials("Broadcast host", broadcast_contract["interfaces"].get("broadcast-host", {}).get("records", {}))
if not {"authentication", "unavailable", "failed"} <= {
    value["name"] for value in broadcast_plugin.get("variants", {}).get("plugin-error", {}).get("values", [])
}:
    raise SystemExit("Broadcast must retain authentication and ordinary service failure outcomes")

helper = next((function for function in io_host.get("functions", []) if function["name"] == "run-helper"), None)
helper_credentials = next((argument for argument in helper["arguments"] if argument["name"] == "credentials"), None) if helper else None
if helper_credentials is None or helper_credentials["type"] != {"kind": "list", "value": credential_binding}:
    raise SystemExit("helpers must be able to consume the same credentials through host mediation")
helper_errors = {value["name"] for value in io_host["variants"].get("helper-error", {}).get("values", [])}
if not {"credential-denied", "credential-unavailable"} <= helper_errors:
    raise SystemExit("helper credential denial and unavailability must remain distinguishable")
helper_input = next((argument for argument in helper.get("arguments", []) if argument["name"] == "input"), None) if helper else None
if helper_input is None or helper_input["type"] != {"kind": "option", "value": {"kind": "named", "name": "byte-stream"}}:
    raise SystemExit("helpers must accept explicit streamed stdin through the canonical byte-stream")
if "input-failed" not in helper_errors:
    raise SystemExit("helper stdin read failures must have an explicit typed outcome")

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
open_staged = next((function for function in io_host.get("functions", []) if function["name"] == "open-staged-artifact"), None)
if open_staged is None or open_staged.get("result") != {
    "kind": "result", "ok": {"kind": "named", "name": "byte-stream"}, "error": {"kind": "named", "name": "stream-error"},
} or not any(argument["type"] == {"kind": "named", "name": "staged-artifact"} for argument in open_staged["arguments"]):
    raise SystemExit("completed staged artifacts must reopen through the canonical byte-stream")

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

broadcast_contract = next(contract for contract in contracts if contract["file"] == "wit/broadcast.wit")
broadcast_host = broadcast_contract["interfaces"].get("broadcast-host", {})
open_broadcast_asset = next((function for function in broadcast_host.get("functions", []) if function["name"] == "open-asset"), None)
if open_broadcast_asset is None or broadcast_host.get("uses", {}).get("byte-stream") != "io-host" or open_broadcast_asset.get("result") != {
    "kind": "result", "ok": {"kind": "named", "name": "byte-stream"}, "error": {"kind": "named", "name": "stream-error"},
}:
    raise SystemExit("Broadcast must open preserved content as the canonical host-managed byte-stream")
if open_broadcast_asset.get("arguments") != [
    {"name": "reference", "type": {"kind": "scalar", "name": "string"}},
    {"name": "offset", "type": {"kind": "scalar", "name": "u64"}},
    {"name": "length", "type": {"kind": "option", "value": {"kind": "scalar", "name": "u64"}}},
]:
    raise SystemExit("Broadcast Asset reads must use opaque references and explicit bounded ranges")
path_names = {"filesystem-path", "host-path", "vault-path", "filesystem-location", "vault-location"}
for interface in (broadcast_host, http_host, io_host):
    for record in interface.get("records", {}).values():
        if path_names & {field["name"] for field in record["fields"]}:
            raise SystemExit("filesystem and Vault paths must not appear in content transport boundaries")
    for function in interface.get("functions", []):
        if path_names & {argument["name"] for argument in function["arguments"]}:
            raise SystemExit("filesystem and Vault paths must not appear in content transport boundaries")
if any(resource["name"] == "credential-access" for resource in broadcast_host.get("resources", [])):
    raise SystemExit("Broadcast must use mediated credentials rather than raw-secret access")

if fields(http_host, "http-response").get("body") != {"kind": "named", "name": "byte-stream"}:
    raise SystemExit("shared HTTP responses must expose bodies as bounded byte streams")
if fields(http_host, "http-request").get("body") != {"kind": "option", "value": {"kind": "named", "name": "byte-stream"}}:
    raise SystemExit("shared HTTP request bodies must be absent or streamed through the canonical byte-stream")
if http_host.get("uses", {}).get("byte-stream") != "io-host":
    raise SystemExit("shared HTTP request and response bodies must use the canonical host byte stream")
if "body-failed" not in {value["name"] for value in http_host.get("variants", {}).get("http-error", {}).get("values", [])}:
    raise SystemExit("HTTP request-body stream failures must have an explicit typed outcome")
for filename, world_name in (("wit/input.wit", "input-world"), ("wit/broadcast.wit", "broadcast-world")):
    contract = next(item for item in contracts if item["file"] == filename)
    world = contract["worlds"].get(world_name, {})
    if "http-host" not in world.get("imports", []):
        raise SystemExit(f"{world_name} must import the canonical HTTP capability")
    host_interface = contract["interfaces"]["input-host" if world_name == "input-world" else "broadcast-host"]
    if any(name in host_interface.get("records", {}) for name in ("http-request", "http-response", "http-header")):
        raise SystemExit(f"{world_name} must not redeclare shared HTTP value types")
if "http-host" not in worlds["enrichment-world"]["imports"]:
    raise SystemExit("Enrichment must use the canonical shared HTTP capability for authenticated remote services")
if "http-host" in worlds["collection-export-world"]["imports"]:
    raise SystemExit("Collection Export must not gain HTTP solely for symmetry")

# The same invocation progress contract applies to Input, Broadcast, and
# Enrichment. Collection Export intentionally has no progress lifecycle.
progress_fields = fields(progress_host, "progress")
if progress_fields != {
    "stage": {"kind": "scalar", "name": "string"},
    "fraction": {"kind": "option", "value": {"kind": "scalar", "name": "f64"}},
}:
    raise SystemExit("shared progress must use a stage and optional f64 fraction")
if progress_host.get("functions") != [{
    "name": "report-progress",
    "arguments": [{"name": "progress", "type": {"kind": "named", "name": "progress"}}],
    "result": None,
}]:
    raise SystemExit("progress reporting must use the canonical invocation progress value")
for world_name in ("input-world", "broadcast-world", "enrichment-world"):
    if "progress-host" not in worlds[world_name]["imports"]:
        raise SystemExit(f"{world_name} must import the shared progress capability")
if "progress-host" in worlds["collection-export-world"]["imports"]:
    raise SystemExit("Collection Export must not gain progress solely for symmetry")

# Collection Export is deliberately inline and bounded by host RPC message
# limits; large catalogue publication belongs to Broadcast's streaming path.
collection_export = interfaces["collection-export-plugin"]
collection_fields = fields(collection_export, "collection")
if collection_fields.get("entries") != {
    "kind": "list", "value": {"kind": "named", "name": "collection-entry"}
}:
    raise SystemExit("Collection Export input must remain an inline entry list")
artifact_fields = fields(collection_export, "exported-artifact")
if artifact_fields.get("contents") != {
    "kind": "list", "value": {"kind": "scalar", "name": "u8"}
}:
    raise SystemExit("Collection Export output must remain an inline byte list")
limit_error = next(
    (case for case in collection_export["variants"]["plugin-error"]["values"] if case["name"] == "limit-exceeded"),
    None,
)
if limit_error is None or limit_error.get("type") != {"kind": "named", "name": "plugin-error-detail"}:
    raise SystemExit("Collection Export must expose a typed host-enforced limit outcome")
collection_world_imports = set(worlds["collection-export-world"]["imports"])
if collection_world_imports != {"plugin-types", "logging-host"}:
    raise SystemExit("bounded Collection Export must not import streaming, progress, or remote-publication capabilities")

if logging_host.get("functions") != [{
    "name": "log",
    "arguments": [{"name": "message", "type": {"kind": "scalar", "name": "string"}}],
    "result": None,
}]:
    raise SystemExit("plugin diagnostic logging must use one canonical message callback")
for world_name in ("input-world", "broadcast-world", "enrichment-world", "collection-export-world"):
    if "logging-host" not in worlds[world_name]["imports"]:
        raise SystemExit(f"{world_name} must import shared invocation logging")
for interface_name in ("input-host", "broadcast-host", "enrichment-host"):
    if any(function["name"] == "log" for function in interfaces[interface_name].get("functions", [])):
        raise SystemExit(f"{interface_name} must not redeclare shared logging")

# Plugin outcome detail is shared; error variant taxonomies stay with each
# lifecycle and may evolve independently.
error_detail_fields = fields(plugin_types, "plugin-error-detail")
if error_detail_fields != {
    "message": {"kind": "scalar", "name": "string"},
    "retryable": {"kind": "scalar", "name": "bool"},
}:
    raise SystemExit("shared plugin error detail must preserve message and retryability")
for interface_name in ("input-plugin", "broadcast-plugin", "enrichment-plugin", "collection-export-plugin"):
    owner = interfaces[interface_name]
    cases = owner.get("variants", {}).get("plugin-error", {}).get("values", [])
    if not cases or any(case.get("type") != {"kind": "named", "name": "plugin-error-detail"} for case in cases):
        raise SystemExit(f"{interface_name} must use shared detail while owning its plugin-error cases")
    if "error" in owner.get("records", {}):
        raise SystemExit(f"{interface_name} must not duplicate the shared error detail record")
    owning_world = next(world for world, value in worlds.items() if interface_name in value["exports"])
    if "plugin-types" not in worlds[owning_world]["imports"]:
        raise SystemExit(f"{owning_world} must import the shared plugin value types")

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
if not delegation_resolver["arguments"] or delegation_resolver["arguments"][0] != {
    "name": "delegation", "type": delegation_type["value"]
}:
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
if set(enrichment_world.get("imports", [])) != {"io-host", "enrichment-host", "http-host", "progress-host", "plugin-types", "logging-host"} or enrichment_world.get("exports") != ["enrichment-plugin"]:
    raise SystemExit("enrichment-world must import only its own host and the applicable shared interfaces")
if enrichment_plugin.get("uses", {}).get("credential-binding") != "io-host":
    raise SystemExit("Enrichment must reuse io-host.credential-binding")
require_no_embedded_credentials("Enrichment", enrichment_plugin.get("records", {}))
require_no_embedded_credentials("Enrichment context", enrichment_host.get("records", {}))
if any(resource["name"] == "credential-access" for resource in enrichment_host.get("resources", [])):
    raise SystemExit("Enrichment must use mediated credentials rather than raw-secret access")


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
if enrichment_host["uses"].get("plugin-metadata") != "io-host" or enrichment_plugin["uses"].get("plugin-metadata") != "io-host":
    raise SystemExit("Enrichment metadata facets must reuse the canonical io-host type")
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
if (
    capability_fields["id"] != {"kind": "scalar", "name": "string"}
    or capability_fields["revision"] != {"kind": "scalar", "name": "string"}
):
    raise SystemExit("Enrichment capability identity and revision must remain opaque strings")
if capability_fields.get("options") != {
    "kind": "list",
    "value": {"kind": "named", "name": "configuration-option"},
}:
    raise SystemExit("Enrichment capabilities must describe accepted generic configuration options")
option_fields = require_fields(enrichment_plugin, "configuration-option", {"key", "label", "required", "choices"})
if option_fields["choices"] != {
    "kind": "list",
    "value": {"kind": "named", "name": "configuration-choice"},
}:
    raise SystemExit("Enrichment options must describe accepted choices")
choice_fields = require_fields(enrichment_plugin, "configuration-choice", {"value", "label"})
selection_fields = require_fields(enrichment_plugin, "configuration-value", {"key", "value"})
if any(
    field_type != {"kind": "scalar", "name": "string"}
    for field_type in (
        option_fields["key"], option_fields["label"], choice_fields["value"],
        choice_fields["label"], selection_fields["key"], selection_fields["value"],
    )
):
    raise SystemExit("Enrichment configuration keys, labels, and values must be generic strings")
if option_fields["required"] != {"kind": "scalar", "name": "bool"}:
    raise SystemExit("Enrichment options must express whether a selection is required")
if not any(function["name"] == "capabilities" for function in enrichment_plugin.get("functions", [])):
    raise SystemExit("Enrichment must let a plugin declare applicable capabilities for Item/Asset context")
enrich_function = next(
    (function for function in enrichment_plugin.get("functions", []) if function["name"] == "enrich"),
    None,
)
if enrich_function is None or not contains_named_type(enrich_function.get("result"), "enrichment-result"):
    raise SystemExit("Enrichment must run a declared capability and return an enrichment-result")
enrich_arguments = {argument["name"]: argument["type"] for argument in enrich_function.get("arguments", [])}
if enrich_arguments.get("capability-id") != {"kind": "scalar", "name": "string"} or enrich_arguments.get(
    "capability-revision"
) != {"kind": "scalar", "name": "string"}:
    raise SystemExit("Enrichment invocation must receive stable capability identity and revision, not its discovery descriptor")
if "capability" in enrich_arguments:
    raise SystemExit("Enrichment invocation must not receive the discovery-only capability descriptor")
if enrich_arguments.get("configuration") != {
    "kind": "list",
    "value": {"kind": "named", "name": "configuration-value"},
}:
    raise SystemExit("Enrichment invocation must receive caller configuration explicitly")
if enrich_arguments.get("credentials") != {"kind": "list", "value": credential_binding}:
    raise SystemExit("Enrichment execution must receive explicit host-granted credential bindings")
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
plugin_errors = enrichment_plugin.get("variants", {}).get("plugin-error", {}).get("values", [])
if not any(case.get("name") == "invalid-configuration" for case in plugin_errors):
    raise SystemExit("Enrichment must report invalid caller selections explicitly")
if not {"authentication", "unavailable", "failed"} <= {case["name"] for case in plugin_errors}:
    raise SystemExit("Enrichment must retain authentication and ordinary service failure outcomes")

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
