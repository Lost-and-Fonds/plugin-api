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


def input_host(candidate: dict) -> dict:
    contract = next(item for item in candidate["contracts"] if item["file"] == "wit/input.wit")
    return contract["interfaces"]["input-host"]


def expect_rejected(name: str, mutate) -> None:
    candidate = copy.deepcopy(schema)
    mutate(input_host(candidate))
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


def add_provider_field(interface: dict) -> None:
    interface["records"]["input-delegation"]["fields"].append(
        {"name": "provider", "type": {"kind": "scalar", "name": "string"}}
    )


def remove_discovery_boundary(interface: dict) -> None:
    interface["records"]["discovered-item"]["fields"] = [
        field for field in interface["records"]["discovered-item"]["fields"] if field["name"] != "delegation"
    ]


expect_rejected("provider-specific delegation", add_provider_field)
expect_rejected("loss of the discovered-item delegation boundary", remove_discovery_boundary)
