#!/usr/bin/env python3
"""Prove the semantic contract verifier rejects targeted Input regressions."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


schema_path, package_schema_path = map(Path, sys.argv[1:3])
verifier = Path(__file__).with_name("verify_generated_contract.py")
schema = json.loads(schema_path.read_text(encoding="utf-8"))
package_schema = json.loads(package_schema_path.read_text(encoding="utf-8"))
staging_path = Path(__file__).resolve().parents[1] / "protocol" / "staging.md"
staging_text = staging_path.read_text(encoding="utf-8")


def package_artifact(candidate: dict) -> dict:
    return candidate["$defs"]["component"]["properties"]["artifact"]


def remove_artifact_path_syntax(candidate: dict) -> None:
    package_artifact(candidate).pop("pattern", None)


def weaken_credential_slot_schema(candidate: dict) -> None:
    slot = candidate["$defs"]["credential-slot"]
    slot["properties"]["credential_reference"] = {"type": "string"}


def make_credential_slot_global(candidate: dict) -> None:
    candidate["properties"]["credential_slots"] = candidate["$defs"]["component"]["properties"].pop("credential_slots")


def remove_slot_identity_constraints(candidate: dict) -> None:
    candidate["$defs"]["component"]["properties"]["credential_slots"]["propertyNames"].pop("pattern", None)


def remove_artifact_resolution_reference(candidate: dict) -> None:
    package_artifact(candidate)["description"] = "Package-relative path to a component artifact."


def input_interface(candidate: dict, name: str) -> dict:
    contract = next(item for item in candidate["contracts"] if item["file"] == "wit/input.wit")
    return contract["interfaces"][name]


def interface(candidate: dict, filename: str, name: str) -> dict:
    contract = next(item for item in candidate["contracts"] if item["file"] == filename)
    return contract["interfaces"][name]


def contract(candidate: dict, filename: str) -> dict:
    return next(item for item in candidate["contracts"] if item["file"] == filename)


def expect_rejected(name: str, mutate) -> None:
    candidate = copy.deepcopy(schema)
    mutate(candidate)
    with tempfile.TemporaryDirectory(prefix="stashd-contract-sensitivity-") as temp:
        candidate_path = Path(temp) / "wit-schema.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(verifier), str(candidate_path), str(package_schema_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode == 0:
        raise SystemExit(f"semantic verifier accepted the {name} regression")
    print(f"sensitivity check caught {name}")


def expect_staging_rule_rejected(name: str, weakened_rule: str) -> None:
    candidate = staging_text.replace(weakened_rule, "", 1)
    if candidate == staging_text:
        raise SystemExit(f"staging sensitivity mutation could not locate {name}")
    with tempfile.TemporaryDirectory(prefix="stashd-staging-sensitivity-") as temp:
        candidate_path = Path(temp) / "staging.md"
        candidate_path.write_text(candidate, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "STASHD_STAGING_SPEC": str(candidate_path)},
        )
    if result.returncode == 0:
        raise SystemExit(f"semantic verifier accepted the {name} regression")
    print(f"sensitivity check caught {name}")


def expect_staging_adoption_position_rejected(name: str, position: str) -> None:
    candidate = staging_text.replace(position, "", 1)
    if candidate == staging_text:
        raise SystemExit(f"staging sensitivity mutation could not locate {name}")
    with tempfile.TemporaryDirectory(prefix="stashd-staging-sensitivity-") as temp:
        candidate_path = Path(temp) / "staging.md"
        candidate_path.write_text(candidate, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "STASHD_STAGING_SPEC": str(candidate_path)},
        )
    if result.returncode == 0:
        raise SystemExit(f"semantic verifier accepted the {name} regression")
    print(f"sensitivity check caught {name}")


def expect_package_schema_rejected(name: str, mutate) -> None:
    candidate = copy.deepcopy(schema)
    package_candidate = copy.deepcopy(package_schema)
    mutate(package_candidate)
    with tempfile.TemporaryDirectory(prefix="stashd-contract-sensitivity-") as temp:
        candidate_path = Path(temp) / "wit-schema.json"
        package_candidate_path = Path(temp) / "plugin-package.schema.json"
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        package_candidate_path.write_text(json.dumps(package_candidate), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(verifier), str(candidate_path), str(package_candidate_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode == 0:
        raise SystemExit(f"semantic verifier accepted the {name} regression")
    print(f"sensitivity check caught {name}")


def add_provider_field(candidate: dict) -> None:
    interface = input_interface(candidate, "input-host")
    interface["records"]["input-delegation"]["fields"].append(
        {"name": "provider", "type": {"kind": "scalar", "name": "string"}}
    )


def remove_discovery_boundary(candidate: dict) -> None:
    interface = input_interface(candidate, "input-host")
    interface["records"]["discovered-item"]["fields"] = [
        field for field in interface["records"]["discovered-item"]["fields"] if field["name"] != "delegation"
    ]


def replace_resolver_type_with_string(candidate: dict) -> None:
    interface = input_interface(candidate, "input-plugin")
    resolver = next(function for function in interface["functions"] if function["name"] == "resolve-delegation")
    resolver["arguments"][0]["type"] = {"kind": "scalar", "name": "string"}


def inline_http_body(candidate: dict) -> None:
    request = interface(candidate, "wit/io.wit", "http-host")["records"]["http-request"]
    next(field for field in request["fields"] if field["name"] == "body")["type"] = {
        "kind": "list",
        "value": {"kind": "scalar", "name": "u8"},
    }


def inline_broadcast_http_body(candidate: dict) -> None:
    response = interface(candidate, "wit/io.wit", "http-host")["records"]["http-response"]
    next(field for field in response["fields"] if field["name"] == "body")["type"] = {
        "kind": "list",
        "value": {"kind": "scalar", "name": "u8"},
    }


def remove_staged_writer(candidate: dict) -> None:
    io = interface(candidate, "wit/io.wit", "io-host")
    io["resources"] = [resource for resource in io["resources"] if resource["name"] != "staged-writer"]


def remove_world_io_import(candidate: dict, filename: str, world_name: str) -> None:
    contract = next(item for item in candidate["contracts"] if item["file"] == filename)
    contract["worlds"][world_name]["imports"].remove("io-host")


def remove_helper_staging_capability(candidate: dict) -> None:
    helper = next(function for function in interface(candidate, "wit/io.wit", "io-host")["functions"] if function["name"] == "run-helper")
    helper["arguments"] = [argument for argument in helper["arguments"] if argument["name"] != "output"]


def remove_broadcast_asset_stream(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-host")
    owner["functions"] = [function for function in owner["functions"] if function["name"] != "open-asset"]


def remove_helper_input(candidate: dict) -> None:
    helper = next(function for function in interface(candidate, "wit/io.wit", "io-host")["functions"] if function["name"] == "run-helper")
    helper["arguments"] = [argument for argument in helper["arguments"] if argument["name"] != "input"]


def restore_broadcast_asset(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-host")
    owner["records"]["asset"] = copy.deepcopy(interface(candidate, "wit/io.wit", "io-host")["records"]["preserved-asset"])
    owner["uses"].pop("preserved-asset", None)
    next(field for field in owner["records"]["item"]["fields"] if field["name"] == "assets")["type"]["value"]["name"] = "asset"


def restore_enrichment_asset(candidate: dict) -> None:
    owner = interface(candidate, "wit/enrichment.wit", "enrichment-host")
    owner["records"]["asset"] = copy.deepcopy(interface(candidate, "wit/io.wit", "io-host")["records"]["preserved-asset"])
    owner["uses"].pop("preserved-asset", None)
    next(field for field in owner["records"]["item-context"]["fields"] if field["name"] == "assets")["type"]["value"]["name"] = "asset"


def remove_preserved_asset_id(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "io-host")
    owner["records"]["preserved-asset"]["fields"] = [field for field in owner["records"]["preserved-asset"]["fields"] if field["name"] != "id"]


def make_preserved_reference_domain_locator(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "io-host")
    reference = next(field for field in owner["records"]["preserved-asset"]["fields"] if field["name"] == "reference")
    reference["name"] = "url"


def remove_preserved_metadata(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "io-host")
    owner["records"]["preserved-asset"]["fields"] = [field for field in owner["records"]["preserved-asset"]["fields"] if field["name"] != "metadata"]


def conflate_staged_and_preserved(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "io-host")
    owner["records"].pop("staged-artifact", None)
    owner["records"]["preserved-asset"] = copy.deepcopy(owner["records"]["preserved-asset"])


def duplicate_byte_stream_for_broadcast(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-host")
    owner["uses"].pop("byte-stream", None)
    owner["resources"].append({"name": "asset-byte-stream", "functions": [{"name": "read", "arguments": [], "result": {"kind": "result", "ok": {"kind": "option", "value": {"kind": "list", "value": {"kind": "scalar", "name": "u8"}}}, "error": {"kind": "named", "name": "stream-error"}}}]})
    function = next(function for function in owner["functions"] if function["name"] == "open-asset")
    function["result"]["ok"] = {"kind": "named", "name": "asset-byte-stream"}


def expose_broadcast_vault_path(candidate: dict) -> None:
    function = next(function for function in interface(candidate, "wit/broadcast.wit", "broadcast-host")["functions"] if function["name"] == "open-asset")
    function["arguments"].append({"name": "vault-path", "type": {"kind": "scalar", "name": "string"}})


def broadcast_credentials_only_during_publish(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    function = next(function for function in owner["functions"] if function["name"] == "operation")
    function["arguments"] = [argument for argument in function["arguments"] if argument["name"] != "credentials"]


def embed_credentials_in_broadcast_settings(candidate: dict) -> None:
    record = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["setting"]
    record["fields"].append({"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}})


def embed_credentials_in_enrichment_configuration(candidate: dict) -> None:
    record = interface(candidate, "wit/enrichment.wit", "enrichment-plugin")["records"]["configuration-value"]
    record["fields"].append({"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}})


def remove_enrichment_credentials(candidate: dict) -> None:
    enrich = next(function for function in interface(candidate, "wit/enrichment.wit", "enrichment-plugin")["functions"] if function["name"] == "enrich")
    enrich["arguments"] = [argument for argument in enrich["arguments"] if argument["name"] != "credentials"]


def add_second_credential_type(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["records"]["broadcast-credential"] = {"fields": [{"name": "id", "type": {"kind": "scalar", "name": "string"}}]}


def add_raw_secret_to_enrichment_record(candidate: dict) -> None:
    record = interface(candidate, "wit/enrichment.wit", "enrichment-plugin")["records"]["capability"]
    record["fields"].append({"name": "api-key", "type": {"kind": "scalar", "name": "string"}})


def pass_reference_without_binding(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    publish = next(function for function in owner["functions"] if function["name"] == "publish")
    next(argument for argument in publish["arguments"] if argument["name"] == "credentials")["type"] = {
        "kind": "list", "value": {"kind": "named", "name": "credential-reference"}
    }


def add_prepare_phase(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["functions"].append({
        "name": "prepare",
        "arguments": [
            {"name": "request", "type": {"kind": "named", "name": "publish-request"}},
            {"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}},
        ],
        "result": {"kind": "result", "ok": {"kind": "named", "name": "preparation"}, "error": {"kind": "named", "name": "plugin-error"}},
    })


def add_finalize_phase(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["functions"].append({
        "name": "finalize",
        "arguments": [
            {"name": "request", "type": {"kind": "named", "name": "finalization-request"}},
            {"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}},
        ],
        "result": {"kind": "result", "ok": {"kind": "named", "name": "publication"}, "error": {"kind": "named", "name": "plugin-error"}},
    })


def restore_opaque_prepared_output(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["records"]["derived-artifact"] = {"fields": [
        {"name": "item-id", "type": {"kind": "scalar", "name": "string"}},
        {"name": "reference", "type": {"kind": "scalar", "name": "string"}},
        {"name": "derived-from", "type": {"kind": "list", "value": {"kind": "scalar", "name": "string"}}},
        {"name": "media-type", "type": {"kind": "option", "value": {"kind": "scalar", "name": "string"}}},
        {"name": "size-bytes", "type": {"kind": "scalar", "name": "u64"}},
        {"name": "metadata", "type": {"kind": "list", "value": {"kind": "named", "name": "plugin-metadata"}}},
    ]}
    owner["records"]["preparation"] = {"fields": [
        {"name": "artifacts", "type": {"kind": "list", "value": {"kind": "named", "name": "derived-artifact"}}},
    ]}


def remove_enrichment_shared_http(candidate: dict) -> None:
    contract(candidate, "wit/enrichment.wit")["worlds"]["enrichment-world"]["imports"].remove("http-host")


def expose_raw_credentials_through_shared_io(candidate: dict) -> None:
    interface(candidate, "wit/io.wit", "io-host")["resources"].append({
        "name": "credential-access",
        "functions": [{"name": "read", "arguments": [], "result": {"kind": "result", "ok": {"kind": "scalar", "name": "string"}, "error": {"kind": "named", "name": "credential-error"}}}],
    })


def restore_broadcast_duration(candidate: dict) -> None:
    item = interface(candidate, "wit/broadcast.wit", "broadcast-host")["records"]["item"]
    item["fields"].append({"name": "duration-seconds", "type": {"kind": "option", "value": {"kind": "scalar", "name": "u32"}}})


def remove_broadcast_item_metadata(candidate: dict) -> None:
    item = interface(candidate, "wit/broadcast.wit", "broadcast-host")["records"]["item"]
    item["fields"] = [field for field in item["fields"] if field["name"] != "metadata"]


def require_fake_artifact_for_publication(candidate: dict) -> None:
    publication = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publication"]
    next(field for field in publication["fields"] if field["name"] == "artifact")["type"] = {"kind": "named", "name": "staged-artifact"}


def require_filesystem_result_for_publication(candidate: dict) -> None:
    publication = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publication"]
    next(field for field in publication["fields"] if field["name"] == "files")["type"] = {
        "kind": "list", "value": {"kind": "named", "name": "published-file"}
    }


def add_ambiguous_broadcast_request_fields(candidate: dict) -> None:
    request = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publish-request"]
    request["fields"].append({"name": "reference", "type": {"kind": "scalar", "name": "string"}})


def add_broadcast_sources(candidate: dict) -> None:
    request = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publish-request"]
    request["fields"].append({"name": "sources", "type": {"kind": "list", "value": {"kind": "named", "name": "item"}}})


def add_mixed_source_settings(candidate: dict) -> None:
    request = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publish-request"]
    request["fields"].append({"name": "settings", "type": {"kind": "list", "value": {"kind": "named", "name": "setting"}}})


def remove_broadcast_configuration(candidate: dict) -> None:
    plugin = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    plugin["records"].pop("destination-configuration")
    publish = next(function for function in plugin["functions"] if function["name"] == "publish")
    publish["arguments"] = [argument for argument in publish["arguments"] if argument["name"] != "configuration"]


def embed_credentials_in_broadcast_configuration(candidate: dict) -> None:
    configuration = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["destination-configuration"]
    configuration["fields"].append({"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}})


def restore_asset_kind_taxonomy(candidate: dict) -> None:
    asset = interface(candidate, "wit/io.wit", "io-host")["records"]["preserved-asset"]
    asset["fields"].append({"name": "kind", "type": {"kind": "scalar", "name": "string"}})


def replace_destination_receipts_with_settings(candidate: dict) -> None:
    reporter = next(resource for resource in interface(candidate, "wit/broadcast.wit", "broadcast-host")["resources"] if resource["name"] == "publication-reporter")
    report = next(function for function in reporter["functions"] if function["name"] == "report-destination-metadata")
    report["arguments"][0]["type"] = {"kind": "list", "value": {"kind": "named", "name": "setting"}}


def restore_inline_files(candidate: dict) -> None:
    publication = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publication"]
    next(field for field in publication["fields"] if field["name"] == "files")["type"] = {"kind": "list", "value": {"kind": "named", "name": "published-file"}}


def embed_credentials_in_publication(candidate: dict) -> None:
    publication = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["publication"]
    publication["fields"].append({"name": "credential", "type": {"kind": "scalar", "name": "string"}})


def leak_host_path_into_staging(candidate: dict) -> None:
    io = interface(candidate, "wit/io.wit", "io-host")
    staging_area = next(resource for resource in io["resources"] if resource["name"] == "staging-area")
    create = next(
        function for function in staging_area["functions"]
        if function["name"] == "create"
    )
    create["arguments"].append({"name": "relative-path", "type": {"kind": "scalar", "name": "string"}})


def remove_early_credential_access(candidate: dict) -> None:
    interface = input_interface(candidate, "input-plugin")
    for function_name in ("resolve", "resolve-delegation", "discover"):
        function = next(function for function in interface["functions"] if function["name"] == function_name)
        function["arguments"] = [argument for argument in function["arguments"] if argument["name"] != "credentials"]


def remove_helper_credential_mediation(candidate: dict) -> None:
    helper = next(
        function for function in interface(candidate, "wit/io.wit", "io-host")["functions"]
        if function["name"] == "run-helper"
    )
    helper["arguments"] = [argument for argument in helper["arguments"] if argument["name"] != "credentials"]


def embed_secret_in_source(candidate: dict) -> None:
    record = input_interface(candidate, "input-plugin")["records"]["source-value"]
    record["fields"].append({"name": "password", "type": {"kind": "scalar", "name": "string"}})


def embed_secret_in_option(candidate: dict) -> None:
    record = input_interface(candidate, "input-plugin")["records"]["input-option"]
    record["fields"].append({"name": "token", "type": {"kind": "scalar", "name": "string"}})


def embed_secret_in_metadata(candidate: dict) -> None:
    record = interface(candidate, "wit/io.wit", "io-host")["records"]["plugin-metadata"]
    record["fields"].append({"name": "secret", "type": {"kind": "scalar", "name": "string"}})


def embed_secret_in_delegation(candidate: dict) -> None:
    record = input_interface(candidate, "input-host")["records"]["input-delegation"]
    record["fields"].append({"name": "credential", "type": {"kind": "scalar", "name": "string"}})


def embed_secret_in_credential_configuration(candidate: dict) -> None:
    record = interface(candidate, "wit/io.wit", "io-host")["records"]["credential-reference"]
    record["fields"].append({"name": "secret", "type": {"kind": "scalar", "name": "string"}})


def remove_enrichment_configuration(candidate: dict) -> None:
    enrichment = interface(candidate, "wit/enrichment.wit", "enrichment-plugin")
    enrich = next(function for function in enrichment["functions"] if function["name"] == "enrich")
    enrich["arguments"] = [argument for argument in enrich["arguments"] if argument["name"] != "configuration"]


def encode_enrichment_configuration_in_identity(candidate: dict) -> None:
    enrichment = interface(candidate, "wit/enrichment.wit", "enrichment-plugin")
    enrichment["records"]["capability"]["fields"] = [
        {
            "name": "id",
            "type": {"kind": "list", "value": {"kind": "named", "name": "configuration-value"}},
        }
        if field["name"] == "id" else field
        for field in enrichment["records"]["capability"]["fields"]
    ]


def change_shared_progress_precision(candidate: dict) -> None:
    progress = interface(candidate, "wit/io.wit", "progress-host")["records"]["progress"]
    next(field for field in progress["fields"] if field["name"] == "fraction")["type"] = {
        "kind": "option", "value": {"kind": "scalar", "name": "f32"}
    }


def remove_broadcast_progress_import(candidate: dict) -> None:
    contract(candidate, "wit/broadcast.wit")["worlds"]["broadcast-world"]["imports"].remove("progress-host")


def add_progress_to_collection_export(candidate: dict) -> None:
    contract(candidate, "wit/collection-export.wit")["worlds"]["collection-export-world"]["imports"].append("progress-host")


def remove_collection_logging_import(candidate: dict) -> None:
    contract(candidate, "wit/collection-export.wit")["worlds"]["collection-export-world"]["imports"].remove("logging-host")


def remove_collection_export_limit_error(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    owner["variants"]["plugin-error"]["values"] = [
        case for case in owner["variants"]["plugin-error"]["values"] if case["name"] != "limit-exceeded"
    ]


def stream_collection_export_input(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    next(field for field in owner["records"]["collection"]["fields"] if field["name"] == "entries")["type"] = {
        "kind": "named", "name": "byte-stream"
    }


def stream_collection_export_output(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    next(field for field in owner["records"]["exported-artifact"]["fields"] if field["name"] == "contents")["type"] = {
        "kind": "named", "name": "staged-artifact"
    }


def add_collection_entry_taxonomy(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    owner["records"]["collection-entry"]["fields"].append(
        {"name": "kind", "type": {"kind": "scalar", "name": "string"}}
    )


def add_duplicate_collection_entry_label(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    owner["records"]["collection-entry"]["fields"].append(
        {"name": "label", "type": {"kind": "scalar", "name": "string"}}
    )


def remove_collection_entry_reference(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    owner["records"]["collection-entry"]["fields"] = [
        field for field in owner["records"]["collection-entry"]["fields"] if field["name"] != "reference"
    ]


def make_collection_entry_reference_optional(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    field = next(field for field in owner["records"]["collection-entry"]["fields"] if field["name"] == "reference")
    field["type"] = {"kind": "option", "value": field["type"]}


def add_collection_identity(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    owner["records"]["collection"]["fields"].insert(
        0, {"name": "reference", "type": {"kind": "option", "value": {"kind": "scalar", "name": "string"}}}
    )


def require_collection_entry_title(candidate: dict) -> None:
    owner = interface(candidate, "wit/collection-export.wit", "collection-export-plugin")
    field = next(field for field in owner["records"]["collection-entry"]["fields"] if field["name"] == "title")
    field["type"] = {"kind": "scalar", "name": "string"}


def remove_input_http_import(candidate: dict) -> None:
    contract(candidate, "wit/input.wit")["worlds"]["input-world"]["imports"].remove("http-host")


def make_broadcast_http_credential_raw(candidate: dict) -> None:
    request = interface(candidate, "wit/io.wit", "http-host")["records"]["http-request"]
    next(field for field in request["fields"] if field["name"] == "credential")["type"] = {
        "kind": "option", "value": {"kind": "scalar", "name": "string"}
    }


def restore_closed_http_method_enum(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "http-host")
    owner["enums"]["http-method"] = {"values": ["get", "post", "put", "patch", "delete"]}
    next(field for field in owner["records"]["http-request"]["fields"] if field["name"] == "method")["type"] = {
        "kind": "named", "name": "http-method"
    }


def remove_http_method_token_boundary(candidate: dict) -> None:
    owner = interface(candidate, "wit/io.wit", "http-host")
    method = next(field for field in owner["records"]["http-request"]["fields"] if field["name"] == "method")
    method["type"] = {"kind": "named", "name": "http-method"}


def enrichment_interface(candidate: dict) -> dict:
    return interface(candidate, "wit/enrichment.wit", "enrichment-plugin")


def change_enrichment_discovery_result(candidate: dict) -> None:
    function = next(function for function in enrichment_interface(candidate)["functions"] if function["name"] == "capabilities")
    function["result"] = {
        "kind": "result",
        "ok": {"kind": "list", "value": {"kind": "named", "name": "capability"}},
        "error": {"kind": "named", "name": "plugin-error"},
    }


def add_enrichment_discovery_credentials(candidate: dict) -> None:
    function = next(function for function in enrichment_interface(candidate)["functions"] if function["name"] == "capabilities")
    function["arguments"].append({"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}})


def remove_enrichment_revision(candidate: dict) -> None:
    enrich = next(
        function for function in interface(candidate, "wit/enrichment.wit", "enrichment-plugin")["functions"]
        if function["name"] == "enrich"
    )
    enrich["arguments"] = [argument for argument in enrich["arguments"] if argument["name"] != "capability-revision"]


def restore_enrichment_discovery_descriptor(candidate: dict) -> None:
    enrich = next(
        function for function in interface(candidate, "wit/enrichment.wit", "enrichment-plugin")["functions"]
        if function["name"] == "enrich"
    )
    enrich["arguments"] = [
        argument for argument in enrich["arguments"]
        if argument["name"] not in {"capability-id", "capability-revision"}
    ]
    enrich["arguments"].insert(1, {"name": "capability", "type": {"kind": "named", "name": "capability"}})


def duplicate_broadcast_error_detail(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["records"]["error"] = {
        "fields": [
            {"name": "message", "type": {"kind": "scalar", "name": "string"}},
            {"name": "retryable", "type": {"kind": "scalar", "name": "bool"}},
        ]
    }
    next(case for case in owner["variants"]["plugin-error"]["values"] if case["name"] == "failed")["type"] = {
        "kind": "named", "name": "error"
    }


def duplicate_broadcast_staged_artifact(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    owner["records"]["artifact"] = {
        "fields": [
            {"name": "reference", "type": {"kind": "scalar", "name": "string"}},
            {"name": "media-type", "type": {"kind": "option", "value": {"kind": "scalar", "name": "string"}}},
            {"name": "size-bytes", "type": {"kind": "scalar", "name": "u64"}},
        ]
    }
    publication = owner["records"]["publication"]
    next(field for field in publication["fields"] if field["name"] == "artifact")["type"] = {
        "kind": "named", "name": "artifact"
    }


def restore_inline_broadcast_items(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-plugin")
    next(field for field in owner["records"]["publish-request"]["fields"] if field["name"] == "collection")["name"] = "items"
    next(field for field in owner["records"]["publish-request"]["fields"] if field["name"] == "items")["type"] = {
        "kind": "list", "value": {"kind": "named", "name": "item"}
    }


def make_unbounded_collection_read(candidate: dict) -> None:
    owner = interface(candidate, "wit/broadcast.wit", "broadcast-host")
    function = owner["resources"][0]["functions"][0]
    function["arguments"] = []
    function["result"]["ok"] = {"kind": "list", "value": {"kind": "named", "name": "item"}}


def add_collection_filter_parameter(candidate: dict) -> None:
    function = interface(candidate, "wit/broadcast.wit", "broadcast-host")["resources"][0]["functions"][0]
    function["arguments"].append({"name": "query", "type": {"kind": "scalar", "name": "string"}})


def add_provider_cursor(candidate: dict) -> None:
    function = interface(candidate, "wit/broadcast.wit", "broadcast-host")["resources"][0]["functions"][0]
    function["arguments"].append({"name": "page-token", "type": {"kind": "scalar", "name": "string"}})


def expose_collection_vault_path(candidate: dict) -> None:
    interface(candidate, "wit/broadcast.wit", "broadcast-host")["records"]["item"]["fields"].append(
        {"name": "vault-path", "type": {"kind": "scalar", "name": "string"}}
    )


def duplicate_broadcast_item(candidate: dict) -> None:
    interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["item"] = copy.deepcopy(
        interface(candidate, "wit/broadcast.wit", "broadcast-host")["records"]["item"]
    )


def add_broadcast_continuation(candidate: dict) -> None:
    interface(candidate, "wit/broadcast.wit", "broadcast-plugin")["records"]["continuation"] = {"fields": []}


def downgrade_contract_package_identity(candidate: dict) -> None:
    candidate["package"] = "stashd:plugin@0.9.0"


def restore_raw_acquisition_credentials(candidate: dict) -> None:
    interface = input_interface(candidate, "input-plugin")
    interface["records"]["acquisition-options"]["fields"] = [
        field for field in interface["records"]["acquisition-options"]["fields"] if field["name"] != "credentials"
    ]
    interface["records"]["acquisition-options"]["fields"].append(
        {"name": "credentials", "type": {"kind": "option", "value": {"kind": "list", "value": {"kind": "named", "name": "input-credential"}}}}
    )
    interface["records"]["input-credential"] = {
        "fields": [
            {"name": "key", "type": {"kind": "scalar", "name": "string"}},
            {"name": "value", "type": {"kind": "scalar", "name": "string"}},
        ]
    }


expect_staging_adoption_position_rejected("Input adoption path becomes implicit", "- Input: successful `input-plugin.acquire` adopts `acquisition-result.artifacts[]`; each entry is a `staged-artifact`.\n")
expect_staging_adoption_position_rejected("Enrichment adoption path becomes implicit", "- Enrichment: successful `enrichment-plugin.enrich` adopts `enrichment-result.assets[].artifact`; each `derived-asset.artifact` is a `staged-artifact`.\n")
expect_staging_adoption_position_rejected("Broadcast adoption path becomes implicit", "- Broadcast: successful `broadcast-plugin.publish` adopts `publication.artifact` when that optional value is `some`.\n")
expect_staging_adoption_position_rejected("Collection Export staged adoption is claimed", "- Collection Export does not use or adopt `staged-artifact`; its output transport remains separate and is outside this staging contract.\n")
expect_staging_rule_rejected("plugin-authored size becomes authoritative", "The host computes `size-bytes` from bytes successfully written. It is factual host-observed state and the plugin cannot author or override it.")
expect_staging_rule_rejected("media type mutable after finish", "`media-type` and `metadata` originate in `staging-area.create`; the host records the exact WIT values supplied and freezes them into the canonical descriptor at successful finish.")
expect_staging_rule_rejected("metadata mutable after finish", "`media-type` and `metadata` originate in `staging-area.create`; the host records the exact WIT values supplied and freezes them into the canonical descriptor at successful finish.")
expect_staging_rule_rejected("forged reference reopened", "Unknown, fabricated, stale, or other-invocation references return `stream-error.missing`.")
expect_staging_rule_rejected("old invocation reference reused", "A descriptor from an earlier invocation is never resolved against that invocation, durable Vault storage, another component/process, or another artifact with coincidentally similar fields.")
expect_staging_rule_rejected("descriptor matching ignores non-reference fields", "A plugin MAY copy a descriptor value. Any operation accepting one MUST resolve its reference in the current invocation's completed-artifact registry and compare the entire supplied descriptor against the canonical descriptor: `reference`, `media-type`, `size-bytes`, and `metadata`.")
expect_staging_rule_rejected("write errors do not poison writer", "because the write returns `staging-error`, it transitions OPEN to POISONED.")
expect_staging_rule_rejected("poisoned writer can recover", "A POISONED writer cannot recover or produce an artifact.")
expect_staging_rule_rejected("second finish creates another artifact", "FINISHED is terminal: subsequent `write` and second `finish` calls fail deterministically with `staging-error.failed(...)`.")
expect_staging_rule_rejected("write after finish allowed", "FINISHED is terminal: subsequent `write` and second `finish` calls fail deterministically with `staging-error.failed(...)`.")
expect_staging_rule_rejected("dropping finished writer deletes artifact", "Dropping a FINISHED writer releases only the writer resource handle. Its completed artifact remains registered and usable for the rest of the invocation, including reopening and successful lifecycle-result adoption.")
expect_staging_rule_rejected("lifecycle result adopts altered descriptor", "Each adoption candidate MUST have been successfully finished in this invocation, resolve to a currently registered staged artifact, and exactly match its canonical host-issued descriptor.")
expect_staging_rule_rejected("invalid result partially adopts outputs", "The host MUST reject the entire result, adopt none of its staged artifacts, fail the invocation, and clean/discard invocation-scoped staging according to existing failure rules. It MUST NOT partially accept valid descriptors from an invalid result.")
expect_staging_rule_rejected("duplicate reference silently adopted", "The same canonical reference MUST NOT occur more than once among adoption candidates in one successful result. A duplicate is a contract violation: reject the whole result, adopt none, and do not silently deduplicate or create multiple durable outputs.")
expect_staging_rule_rejected("unreturned completed output automatically durable", "Completed staged artifacts not returned for adoption remain temporary and are discarded at invocation end, even if opened as HTTP/helper input. Finish alone does not make output durable.")

expect_rejected("provider-specific delegation", add_provider_field)
expect_rejected("loss of the discovered-item delegation boundary", remove_discovery_boundary)
expect_rejected("raw-string receiving boundary", replace_resolver_type_with_string)
expect_rejected("inline-only HTTP request body", inline_http_body)
expect_rejected("inline-only HTTP response body", inline_broadcast_http_body)
expect_rejected("missing staged output writer", remove_staged_writer)
expect_rejected("helper without explicit staging capability", remove_helper_staging_capability)
expect_rejected("host path exposed by staging", leak_host_path_into_staging)
expect_rejected("Input without the shared I/O import", lambda candidate: remove_world_io_import(candidate, "wit/input.wit", "input-world"))
expect_rejected("Enrichment without the shared I/O import", lambda candidate: remove_world_io_import(candidate, "wit/enrichment.wit", "enrichment-world"))
expect_rejected("acquisition-only credential access", remove_early_credential_access)
expect_rejected("helper without host-mediated credentials", remove_helper_credential_mediation)
expect_rejected("raw password embedded in source values", embed_secret_in_source)
expect_rejected("raw token embedded in Input options", embed_secret_in_option)
expect_rejected("secret embedded in metadata", embed_secret_in_metadata)
expect_rejected("credential embedded in delegation records", embed_secret_in_delegation)
expect_rejected("secret embedded in opaque credential configuration", embed_secret_in_credential_configuration)
expect_rejected("legacy raw acquisition credential model", restore_raw_acquisition_credentials)
expect_rejected("Enrichment without explicit invocation configuration", remove_enrichment_configuration)
expect_rejected("Enrichment configuration encoded in capability identity", encode_enrichment_configuration_in_identity)
expect_rejected("split progress precision", change_shared_progress_precision)
expect_rejected("Broadcast without shared progress", remove_broadcast_progress_import)
expect_rejected("Collection Export progress added for symmetry", add_progress_to_collection_export)
expect_rejected("Collection Export without shared logging", remove_collection_logging_import)
expect_rejected("Collection Export without typed size-limit outcome", remove_collection_export_limit_error)
expect_rejected("streamed Collection Export input", stream_collection_export_input)
expect_rejected("staged Collection Export output", stream_collection_export_output)
expect_rejected("Collection Export domain taxonomy restored as kind", add_collection_entry_taxonomy)
expect_rejected("Collection Export duplicate label presentation field", add_duplicate_collection_entry_label)
expect_rejected("Collection Export entry without interchange reference", remove_collection_entry_reference)
expect_rejected("Collection Export reference made optional", make_collection_entry_reference_optional)
expect_rejected("Collection Export collection-level identity restored", add_collection_identity)
expect_rejected("Collection Export entry title made mandatory", require_collection_entry_title)
expect_rejected("Input without canonical HTTP capability", remove_input_http_import)
expect_rejected("raw Broadcast HTTP credential", make_broadcast_http_credential_raw)
expect_rejected("closed HTTP method enum", restore_closed_http_method_enum)
expect_rejected("HTTP method without token boundary", remove_http_method_token_boundary)
expect_rejected("Enrichment invocation without revision", remove_enrichment_revision)
expect_rejected("credentials added to Enrichment capability discovery", add_enrichment_discovery_credentials)
expect_rejected("fallible Enrichment capability discovery", change_enrichment_discovery_result)
expect_rejected("Enrichment invocation consuming discovery descriptor", restore_enrichment_discovery_descriptor)
expect_rejected("duplicated Broadcast error detail", duplicate_broadcast_error_detail)
expect_rejected("duplicated Broadcast staged artifact", duplicate_broadcast_staged_artifact)
expect_rejected("Broadcast without preserved Asset reads", remove_broadcast_asset_stream)
expect_rejected("duplicate Broadcast preserved Asset descriptor", restore_broadcast_asset)
expect_rejected("duplicate Enrichment preserved Asset descriptor", restore_enrichment_asset)
expect_rejected("preserved Asset without stable identity", remove_preserved_asset_id)
expect_rejected("preserved Asset reference made a URL", make_preserved_reference_domain_locator)
expect_rejected("preserved Asset without canonical metadata facets", remove_preserved_metadata)
expect_rejected("staged artifact conflated with preserved Asset", conflate_staged_and_preserved)
expect_rejected("helper without explicit streamed input", remove_helper_input)
expect_rejected("duplicated Broadcast byte-stream abstraction", duplicate_byte_stream_for_broadcast)
expect_rejected("Vault path exposed by Broadcast content boundary", expose_broadcast_vault_path)
expect_rejected("Broadcast credentials available only during publish", broadcast_credentials_only_during_publish)
expect_rejected("credentials embedded in Broadcast settings", embed_credentials_in_broadcast_settings)
expect_rejected("credentials embedded in Enrichment configuration", embed_credentials_in_enrichment_configuration)
expect_rejected("Enrichment without invocation credential bindings", remove_enrichment_credentials)
expect_rejected("unnecessary second credential type", add_second_credential_type)
expect_rejected("raw secret field in an Enrichment plugin record", add_raw_secret_to_enrichment_record)
expect_rejected("credential reference used without host-granted binding", pass_reference_without_binding)
expect_rejected("Enrichment without canonical shared HTTP", remove_enrichment_shared_http)
expect_rejected("raw credential access exposed through shared I/O", expose_raw_credentials_through_shared_io)
expect_rejected("Broadcast Item has a universal duration field", restore_broadcast_duration)
expect_rejected("Broadcast Item without canonical metadata facets", remove_broadcast_item_metadata)
expect_rejected("remote publication requires a fake staged artifact", require_fake_artifact_for_publication)
expect_rejected("publication requires filesystem paths", require_filesystem_result_for_publication)
expect_rejected("Asset kind restored as a universal taxonomy", restore_asset_kind_taxonomy)
expect_rejected("ambiguous Broadcast request reference restored", add_ambiguous_broadcast_request_fields)
expect_rejected("Broadcast source list restored", add_broadcast_sources)
expect_rejected("mixed source settings restored to Broadcast request", add_mixed_source_settings)
expect_rejected("explicit Broadcast destination configuration removed", remove_broadcast_configuration)
expect_rejected("credentials embedded in Broadcast destination configuration", embed_credentials_in_broadcast_configuration)
expect_rejected("destination receipts lose opaque plugin metadata", replace_destination_receipts_with_settings)
expect_rejected("inline publication file list restored", restore_inline_files)
expect_rejected("credentials embedded in Broadcast publication results", embed_credentials_in_publication)
expect_rejected("Broadcast preparation phase restored", add_prepare_phase)
expect_rejected("Broadcast finalization phase restored", add_finalize_phase)
expect_rejected("opaque-reference derived-artifact staging restored", restore_opaque_prepared_output)
expect_rejected("contract package identity downgraded from 0.14.0", downgrade_contract_package_identity)
expect_rejected("inline Broadcast Item list restored", restore_inline_broadcast_items)
expect_rejected("unbounded collection result", make_unbounded_collection_read)
expect_rejected("collection read maximum removed", make_unbounded_collection_read)
expect_rejected("host query/filter parameter", add_collection_filter_parameter)
expect_rejected("provider cursor added", add_provider_cursor)
expect_rejected("Vault path exposed in collection Item", expose_collection_vault_path)
expect_rejected("parallel Broadcast Item DTO", duplicate_broadcast_item)
expect_rejected("cross-invocation Broadcast continuation", add_broadcast_continuation)
expect_package_schema_rejected("package artifact path syntax removed", remove_artifact_path_syntax)
expect_package_schema_rejected("package artifact resolution rules unreferenced", remove_artifact_resolution_reference)
expect_package_schema_rejected("credential reference embedded in slot declaration", weaken_credential_slot_schema)
expect_package_schema_rejected("package-global credential slots", make_credential_slot_global)
expect_package_schema_rejected("invalid credential slot identity accepted", remove_slot_identity_constraints)


def remove_acquisition_outcome(candidate: dict) -> None:
    fields = input_interface(candidate, "input-plugin")["records"]["acquisition-result"]["fields"]
    fields[:] = [field for field in fields if field["name"] != "outcome"]


def encode_partial_as_execution_error(candidate: dict) -> None:
    errors = input_interface(candidate, "input-plugin")["variants"]["plugin-error"]["values"]
    errors.append({"name": "partial", "type": {"kind": "named", "name": "plugin-error-detail"}})


def add_overall_retryable(candidate: dict) -> None:
    input_interface(candidate, "input-plugin")["records"]["acquisition-result"]["fields"].append(
        {"name": "retryable", "type": {"kind": "scalar", "name": "bool"}}
    )


def add_domain_missing_resource_field(candidate: dict) -> None:
    input_interface(candidate, "input-host")["records"]["deficiency"]["fields"].append(
        {"name": "missing-resource-id", "type": {"kind": "scalar", "name": "string"}}
    )


def remove_indeterminate_discovery(candidate: dict) -> None:
    finish = input_interface(candidate, "input-host")["variants"]["discovery-finish"]["values"]
    finish[:] = [case for case in finish if case["name"] != "indeterminate"]


def remove_batch_commit(candidate: dict) -> None:
    owner = input_interface(candidate, "input-host")
    owner["functions"] = [function for function in owner["functions"] if function["name"] != "commit-discovery-batch"]


def restore_single_item_delivery(candidate: dict) -> None:
    owner = input_interface(candidate, "input-host")
    owner["functions"].append({"name": "report-discovered", "arguments": [{"name": "item", "type": {"kind": "named", "name": "discovered-item"}}], "result": None})


def return_discovery_items(candidate: dict) -> None:
    owner = input_interface(candidate, "input-plugin")
    discover = next(function for function in owner["functions"] if function["name"] == "discover")
    discover["result"]["ok"] = {"kind": "list", "value": {"kind": "named", "name": "discovered-item"}}


def merge_discovery_states(candidate: dict) -> None:
    owner = input_interface(candidate, "input-plugin")
    request = owner["records"]["discovery-request"]
    next(field for field in request["fields"] if field["name"] == "continuation")["type"] = {
        "kind": "option", "value": {"kind": "scalar", "name": "string"}
    }


def put_refresh_state_in_nonterminal_progress(candidate: dict) -> None:
    owner = input_interface(candidate, "input-host")
    more = next(case for case in owner["variants"]["discovery-progress"]["values"] if case["name"] == "more")
    more["type"] = {"kind": "named", "name": "discovery-refresh-state"}


def remove_batch_limit(candidate: dict) -> None:
    owner = input_interface(candidate, "input-plugin")
    request = owner["records"]["discovery-request"]
    request["fields"] = [field for field in request["fields"] if field["name"] != "maximum-items-per-batch"]


def embed_credentials_in_discovery_state(candidate: dict) -> None:
    owner = input_interface(candidate, "input-host")
    owner["records"]["discovery-continuation"]["fields"].append(
        {"name": "credentials", "type": {"kind": "list", "value": {"kind": "named", "name": "credential-binding"}}}
    )


def add_provider_pagination_field(candidate: dict) -> None:
    owner = input_interface(candidate, "input-plugin")
    owner["records"]["discovery-request"]["fields"].append(
        {"name": "page-token", "type": {"kind": "scalar", "name": "string"}}
    )


expect_rejected("acquisition artifacts without preservation outcome", remove_acquisition_outcome)
expect_rejected("partial preservation encoded as execution error", encode_partial_as_execution_error)
expect_rejected("overall retryable bit duplicating deficiencies", add_overall_retryable)
expect_rejected("provider-specific missing-resource protocol field", add_domain_missing_resource_field)
expect_rejected("terminal discovery without explicit indeterminate coverage", remove_indeterminate_discovery)
expect_rejected("missing acknowledged discovery batch", remove_batch_commit)
expect_rejected("single-item discovery delivery restored", restore_single_item_delivery)
expect_rejected("returned discovery Item list restored", return_discovery_items)
expect_rejected("undifferentiated continuation state", merge_discovery_states)
expect_rejected("refresh state in nonterminal progress", put_refresh_state_in_nonterminal_progress)
expect_rejected("unbounded discovery batch", remove_batch_limit)
expect_rejected("credentials embedded in continuation", embed_credentials_in_discovery_state)
expect_rejected("provider pagination field in request", add_provider_pagination_field)


def verify_enrichment_capability_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "enrichment-capabilities.md"
    text = document.read_text(encoding="utf-8")
    mutations = (
        ("MUST NOT require or depend on credentials or their availability", "may require credentials or their availability"),
        ("HTTP, remote calls or service health", "HTTP and remote service health are permitted"),
        ("helper execution, staging, progress callbacks, or Asset byte reads through `enrichment-host.open-asset`", "helper execution is permitted, staging and progress callbacks remain prohibited, and Asset byte reads through `enrichment-host.open-asset` remain prohibited"),
        ("Discovery determines applicability from those descriptors and metadata, not by opening or examining Asset bytes.", "Discovery determines applicability from those descriptors and metadata, and may open or examine Asset bytes."),
        ("MUST NOT perform remote service discovery, preflight execution, or an availability check", "MAY perform remote service discovery, preflight execution, and availability checks"),
        ("not guaranteed success", "guaranteed success"),
        ("MUST NOT require a live remote lookup", "MUST perform a live remote lookup"),
        ("revision MUST change when the accepted or interpreted caller configuration contract changes semantically", "revision may remain unchanged when accepted configuration semantics change"),
        ("Presentation-only changes, including wording of labels and ordering with no plugin-defined semantic meaning, do not require a revision change.", "Label-only changes MUST change the revision."),
        ("it MUST return `plugin-error.unsupported`", "it MUST return `plugin-error.invalid-configuration`"),
        ("MUST return `plugin-error.invalid-configuration`", "MUST return `plugin-error.unsupported`"),
        ("An empty list is an ordinary successful result meaning no capability applies", "An empty list means the remote service is unavailable"),
    )
    for original, replacement in mutations:
        weakened = text.replace(original, replacement, 1)
        if weakened == text:
            raise SystemExit(f"Enrichment capability sensitivity mutation did not apply: {original}")
        with tempfile.TemporaryDirectory(prefix="stashd-enrichment-sensitivity-") as temp:
            candidate_path = Path(temp) / "enrichment-capabilities.md"
            candidate_path.write_text(weakened, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
                capture_output=True, text=True, check=False,
                env={**os.environ, "STASHD_ENRICHMENT_SPEC": str(candidate_path)},
            )
        if result.returncode == 0:
            raise SystemExit(f"semantic verifier accepted weakened Enrichment capability semantics: {original}")
        print(f"sensitivity check caught weakened Enrichment capability semantics: {original}")


def expect_document_semantic_rejected(name: str, env_key: str, path: Path, mutations: tuple[tuple[str, str], ...]) -> None:
    text = path.read_text(encoding="utf-8")
    for original, replacement in mutations:
        weakened = text.replace(original, replacement, 1)
        if weakened == text:
            raise SystemExit(f"{name} sensitivity mutation did not apply: {original}")
        with tempfile.TemporaryDirectory(prefix=f"stashd-{name}-sensitivity-") as temp:
            candidate = Path(temp) / path.name
            candidate.write_text(weakened, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
                capture_output=True, text=True, check=False,
                env={**os.environ, env_key: str(candidate)},
            )
        if result.returncode == 0:
            raise SystemExit(f"semantic verifier accepted weakened {name} semantics: {original}")
        print(f"sensitivity check caught weakened {name} semantics: {original}")


def verify_shared_value_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    expect_document_semantic_rejected("shared-value", "STASHD_SHARED_VALUES_SPEC", root / "protocol" / "shared-values.md", (
        ("MUST be syntactically valid interoperable JSON", "may be arbitrary text"),
        ("parsed root is an object", "parsed root may be any JSON value"),
        ("Objects at every depth MUST NOT contain duplicate member names.", "Objects at every depth MAY contain duplicate member names."),
        ("No canonical JSON/JCS requirement applies.", "Canonical key-sorted JSON is required."),
        ("schema` MUST be non-empty", "schema` may be empty"),
        ("and versioned/revision-bearing in the plugin's own identifier scheme.", "and may be a stable but unversioned identifier even when its contract changes incompatibly under that same identifier."),
        ("Core MUST NOT infer compatibility", "Core infers compatibility"),
        ("in the inclusive range `[0.0, 1.0]`", "in a range with no lower bound and an upper bound of 1.0"),
        ("in the inclusive range `[0.0, 1.0]`", "in a range with a lower bound of 0.0 and no upper bound"),
        ("MUST contain at least one byte", "may contain zero bytes"),
        ("`ok(none)` is the only EOF representation.", "`ok(some([]))` is an alternative EOF representation."),
        ("`ok(some([]))` is invalid protocol/contract behavior.", "`ok(some([]))` is valid data."),
        ("EOF is sticky", "EOF is not sticky"),
        ("not clamp it", "clamp it"),
        ("No universal monotonicity rule applies", "A universal monotonicity rule applies"),
    ))


def verify_input_value_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    expect_document_semantic_rejected("Input-value", "STASHD_INPUT_VALUES_SPEC", root / "protocol" / "input-values.md", (
        ("| `none` | `true` | Invalid: an estimate has no numeric value.", "| `none` | `true` | Valid unknown estimate."),
        ("`some(N)` | `false` | N is presented as a non-estimated byte-size value", "`some(N)` | `false` | N remains an estimate."),
        ("`resolved-input` and `discovered-item` use the same", "`resolved-input` and `discovered-item` use different"),
        ("without an undocumented in-memory mapping established by the earlier resolve call", "using an undocumented in-memory mapping established by the earlier resolve call"),
        ("MUST NOT require an undocumented process-local object retained from the earlier discovery invocation", "MAY require a process-local object retained from the earlier discovery invocation"),
        ("Correctness MUST NOT depend on an undocumented mutable process-local mapping", "Correctness MAY depend on an undocumented mutable process-local mapping"),
        ("MUST be self-sufficient across process/invocation boundaries and contain no credential material", "may depend on hidden state and contain credentials"),
    ))


def verify_readme_current_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    expect_document_semantic_rejected("README", "STASHD_README", root / "README.md", (
        ("A `publish-request` contains the invocation-scoped `item-collection` and", "A `publish-request` contains only the preserved `items` selected"),
        ("`publication-reporter.report-destination-metadata`", "`publication.destination-metadata`"),
        ("Filesystem-relative file records are reported incrementally through\n`publication-reporter.report-files`", "Filesystem-relative file records are returned inline in `publication.files`"),
        ("`publish(request, configuration, credentials)` is the complete publication lifecycle and the\nonly publication call.", "`prepare`, `publish`, `finalize` are current lifecycle calls. `publish(request, configuration, credentials)` remains the complete publication lifecycle and the\nonly publication call."),
        ("  receipts through `publication-reporter`; no local artifact is required.", "  receipts in inline destination metadata; no local artifact is required."),
    ))


def verify_preservation_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "input-preservation.md"
    text = document.read_text(encoding="utf-8")
    mutations = (
        ("`partial` MUST contain at least one deficiency", "`partial` may contain zero deficiencies"),
        ("Only `finished(exhaustive(...))` may replace or clear completed refresh state.", "Any terminal outcome may replace completed refresh state."),
        ("MUST NOT inspect evidence to decide retry policy.", "The host parses evidence to decide retry policy."),
    )
    for original, replacement in mutations:
        weakened = text.replace(original, replacement)
        if weakened == text:
            raise SystemExit(f"preservation sensitivity mutation did not apply: {original}")
        document.write_text(weakened, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
                capture_output=True, text=True, check=False,
            )
        finally:
            document.write_text(text, encoding="utf-8")
        if result.returncode == 0:
            raise SystemExit(f"semantic verifier accepted weakened preservation semantics: {original}")
        print(f"sensitivity check caught weakened preservation semantics: {original}")


def verify_terminal_commit_authority() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "input-discovery.md"
    text = document.read_text(encoding="utf-8")
    weakened = text.replace("Every terminal batch's successful acknowledgment is the durable commit point:", "Terminal acceptance is informational:")
    if weakened == text:
        raise SystemExit("terminal commit-point sensitivity mutation did not apply")
    document.write_text(weakened, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
            capture_output=True, text=True, check=False,
        )
    finally:
        document.write_text(text, encoding="utf-8")
    if result.returncode == 0:
        raise SystemExit("semantic verifier accepted missing terminal commit-point semantics")
    print("sensitivity check caught missing terminal commit-point semantics")


def verify_broadcast_collection_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "broadcast-collection.md"
    text = document.read_text(encoding="utf-8")
    mutations = (
        ("The host MUST accept `Ok(publication)` only after the collection has\nreached EOF.", "Publication may succeed before the collection reaches EOF."),
        ("Selected Items MUST NOT silently disappear due to unrelated state changes.", "Selected Items may silently disappear due to unrelated state changes."),
        ("host MUST return every selected Item at most once", "host may return selected Items more than once"),
        ("single Item that\ncannot fit within the configured RPC response limit MUST fail", "single Item may exceed the configured RPC response limit"),
        ("There is no cross-invocation Broadcast continuation, cursor, checkpoint, or\nresume state.", "Broadcast continuation state may be reused across invocations."),
    )
    for original, replacement in mutations:
        weakened = text.replace(original, replacement)
        if weakened == text:
            raise SystemExit(f"Broadcast collection sensitivity mutation did not apply: {original}")
        document.write_text(weakened, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
                capture_output=True, text=True, check=False,
            )
        finally:
            document.write_text(text, encoding="utf-8")
        if result.returncode == 0:
            raise SystemExit(f"semantic verifier accepted weakened Broadcast collection semantics: {original}")
        print(f"sensitivity check caught weakened Broadcast collection semantics: {original}")


def verify_component_execution_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "component-execution.md"
    text = document.read_text(encoding="utf-8")
    mutations = (
        ("stdin is exclusively the host-to-plugin RPC v1 byte channel", "stdin is exclusively the plugin-to-host RPC v1 byte channel"),
        ("stderr is an ordinary diagnostic channel, not part of RPC v1", "stderr is an RPC v1 protocol channel"),
        ("Plugins MUST NOT write banners, logs, warnings, whitespace, or other diagnostic/text output there.", "Plugins MAY write arbitrary diagnostic logs there."),
        ("Every newly launched process MUST send the existing RPC v1 `hello` request as its first stdout frame.", "Every newly launched process MAY send the existing RPC v1 `hello` request after a lifecycle frame."),
        ("correctness MUST NOT depend on mutable process-local state surviving between lifecycle invocations", "correctness MAY depend on mutable process-local state surviving between lifecycle invocations"),
        ("become invalid at invocation end even if the process remains alive", "remain valid after invocation end if the process remains alive"),
        ("The protocol requires no command-line arguments.", "The protocol requires command-line arguments carrying lifecycle state."),
        ("No environment variable is guaranteed unless explicitly defined by the canonical contract.", "Ambient environment variables are guaranteed implicit inputs."),
        ("only after successful hello may it send a lifecycle request", "it may send a lifecycle request before successful hello"),
        ("is invocation transport/execution failure, never a successful lifecycle result", "is an ordinary successful lifecycle result"),
        ("A top-level `error` field is invalid in a response envelope", "A top-level `error` field is permitted in a response envelope"),
        ("MUST NOT continue processing later frames on that channel", "MAY continue processing later frames on that channel"),
    )
    for original, replacement in mutations:
        weakened = text.replace(original, replacement)
        if weakened == text:
            raise SystemExit(f"component execution sensitivity mutation did not apply: {original}")
        document.write_text(weakened, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
                capture_output=True, text=True, check=False,
            )
        finally:
            document.write_text(text, encoding="utf-8")
        if result.returncode == 0:
            raise SystemExit(f"semantic verifier accepted weakened component execution semantics: {original}")
        print(f"sensitivity check caught weakened component execution semantics: {original}")


def verify_shared_component_identity_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "plugin-package.md"
    text = document.read_text(encoding="utf-8")
    original = "Components with the same WIT world that share an artifact MUST NOT require knowledge of the selected component ID for correctness"
    replacement = "Components with the same WIT world that share an artifact MAY require knowledge of the selected component ID for correctness"
    weakened = text.replace(original, replacement)
    if weakened == text:
        raise SystemExit("shared-component identity sensitivity mutation did not apply")
    document.write_text(weakened, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(verifier), str(schema_path), str(package_schema_path)],
            capture_output=True, text=True, check=False,
        )
    finally:
        document.write_text(text, encoding="utf-8")
    if result.returncode == 0:
        raise SystemExit("semantic verifier accepted same-world dependence on implicit component identity")
    print("sensitivity check caught implicit same-world component identity")


def verify_rpc_response_envelope_semantics() -> None:
    document = Path(__file__).resolve().parents[1] / "protocol" / "rpc-v1.md"
    text = document.read_text(encoding="utf-8")
    original = "A top-level `error`\nfield is invalid."
    replacement = "A top-level `error` field is permitted."
    weakened = text.replace(original, replacement)
    if weakened == text:
        raise SystemExit("RPC response-envelope sensitivity mutation did not apply")
    document.write_text(weakened, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("verify_rpc_v1.py")), str(document), str(Path(__file__).resolve().parents[1] / "protocol" / "rpc-v1-vectors.json"), str(schema_path)],
            capture_output=True, text=True, check=False,
        )
    finally:
        document.write_text(text, encoding="utf-8")
    if result.returncode == 0:
        raise SystemExit("RPC verifier accepted a restored top-level response error")
    print("sensitivity check caught top-level RPC response error permitted")


verify_terminal_commit_authority()
verify_shared_value_semantics()
verify_input_value_semantics()
verify_readme_current_contract()
verify_enrichment_capability_semantics()
verify_preservation_semantics()
verify_broadcast_collection_semantics()
verify_component_execution_semantics()
verify_shared_component_identity_semantics()
verify_rpc_response_envelope_semantics()
