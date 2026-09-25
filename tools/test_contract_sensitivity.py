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
