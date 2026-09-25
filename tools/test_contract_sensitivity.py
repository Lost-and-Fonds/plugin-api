#!/usr/bin/env python3
"""Prove the semantic contract verifier rejects targeted Input regressions."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path


schema_path, package_schema_path = map(Path, sys.argv[1:3])
verifier = Path(__file__).with_name("verify_generated_contract.py")
schema = json.loads(schema_path.read_text(encoding="utf-8"))


def input_interface(candidate: dict, name: str) -> dict:
    contract = next(item for item in candidate["contracts"] if item["file"] == "wit/input.wit")
    return contract["interfaces"][name]


def interface(candidate: dict, filename: str, name: str) -> dict:
    contract = next(item for item in candidate["contracts"] if item["file"] == filename)
    return contract["interfaces"][name]


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
    response = input_interface(candidate, "input-host")["records"]["http-response"]
    next(field for field in response["fields"] if field["name"] == "body")["type"] = {
        "kind": "list",
        "value": {"kind": "scalar", "name": "u8"},
    }


def inline_broadcast_http_body(candidate: dict) -> None:
    response = interface(candidate, "wit/broadcast.wit", "broadcast-host")["records"]["http-response"]
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


expect_rejected("provider-specific delegation", add_provider_field)
expect_rejected("loss of the discovered-item delegation boundary", remove_discovery_boundary)
expect_rejected("raw-string receiving boundary", replace_resolver_type_with_string)
expect_rejected("inline-only HTTP response body", inline_http_body)
expect_rejected("inline-only Broadcast HTTP response body", inline_broadcast_http_body)
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
