#!/usr/bin/env python3
"""Extract WIT contracts and package role declarations deterministically."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


INTERFACE = re.compile(r"\b(interface|world)\s+([A-Za-z0-9-]+)\s*\{")


def normalize_package(resolved: dict, paths: list[Path], repo_root: Path) -> list[dict]:
    types = resolved["types"]
    interfaces = resolved["interfaces"]
    inventory = {
        "input.wit": ({"input-host", "input-plugin"}, {"input-world"}),
        "broadcast.wit": ({"broadcast-host", "broadcast-plugin"}, {"broadcast-world"}),
        "enrichment.wit": ({"enrichment-host", "enrichment-plugin"}, {"enrichment-world"}),
        "collection-export.wit": ({"collection-export-plugin"}, {"collection-export-world"}),
        "io.wit": ({"plugin-types", "progress-host", "logging-host", "http-host", "io-host"}, set()),
    }

    def unsupported(value):
        raise SystemExit(f"E_WIT_UNSUPPORTED: {value}")

    def value_type(value):
        if value is None:
            return None
        if isinstance(value, str):
            if value not in {"bool", "string", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64", "f32", "f64", "float32", "float64"}:
                unsupported(f"scalar {value}")
            return {"kind": "scalar", "name": {"float32": "f32", "float64": "f64"}.get(value, value)}
        declaration = types[value]
        if declaration["name"] is not None:
            return {"kind": "named", "name": declaration["name"]}
        kind = declaration["kind"]
        if "type" in kind:
            return value_type(kind["type"])
        for wrapper in ("list", "option"):
            if wrapper in kind:
                return {"kind": wrapper, "value": value_type(kind[wrapper])}
        if "result" in kind:
            return {"kind": "result", "ok": value_type(kind["result"]["ok"]), "error": value_type(kind["result"]["err"])}
        if "handle" in kind:
            ownership, target = next(iter(kind["handle"].items()))
            target_type = {"kind": "named", "name": types[target]["name"]}
            return target_type if ownership == "own" else {"kind": "borrow", "value": target_type}
        unsupported(kind)

    def normalize_interface(interface_id):
        source = interfaces[interface_id]
        output = {"records": {}, "variants": {}, "enums": {}, "resources": [], "functions": [], "uses": {}}
        resources = {}
        for name, type_id in source["types"].items():
            declaration = types[type_id]
            kind = declaration["kind"]
            if isinstance(kind, dict) and "type" in kind:
                target = kind["type"]
                owner = types[target].get("owner") if isinstance(target, int) else None
                if not owner or "interface" not in owner or owner["interface"] == interface_id:
                    raise SystemExit(f"E_WIT_UNSUPPORTED: type alias {name}")
                if types[target]["name"] != name:
                    unsupported(f"renamed import {name}")
                output["uses"][name] = interfaces[owner["interface"]]["name"]
            elif kind == "resource":
                resource = {"name": name, "functions": []}
                output["resources"].append(resource)
                resources[type_id] = resource
            elif "record" in kind:
                output["records"][name] = {"fields": [{"name": field["name"], "type": value_type(field["type"])} for field in kind["record"]["fields"]]}
            elif "variant" in kind:
                output["variants"][name] = {"values": [{"name": case["name"], "type": value_type(case.get("type"))} for case in kind["variant"]["cases"]]}
            elif "enum" in kind:
                output["enums"][name] = {"values": [case["name"] for case in kind["enum"]["cases"]]}
            else:
                unsupported(f"declaration {name}: {kind}")
        for function in source["functions"].values():
            kind = function["kind"]
            params = function["params"]
            name = function["name"]
            destination = output["functions"]
            if kind != "freestanding":
                if not isinstance(kind, dict) or set(kind) != {"method"}:
                    unsupported(f"function {name}: {kind}")
                destination = resources[kind["method"]]["functions"]
                params = params[1:]
                name = name.split(".", 1)[1]
            results = function["results"]
            if len(results) > 1:
                unsupported(f"multiple results: {name}")
            destination.append({"name": name, "arguments": [{"name": param["name"], "type": value_type(param["type"])} for param in params], "result": value_type(results[0]["type"]) if results else None})
        return output

    for index in range(len(interfaces)):
        normalize_interface(index)
    package = resolved["packages"]
    if len(package) != 1:
        unsupported("external packages")
    contracts = []
    seen_interfaces = set()
    seen_worlds = set()
    for path in paths:
        if path.name not in inventory:
            unsupported(f"source file {path.name}")
        interface_names, world_names = inventory[path.name]
        source = strip_comments(path.read_text())
        declared = {(match.group(1), match.group(2)) for match in INTERFACE.finditer(source)}
        expected = {("interface", name) for name in interface_names} | {("world", name) for name in world_names}
        if declared != expected:
            unsupported(f"source inventory {path.name}: {declared ^ expected}")
        contract = {"file": path.relative_to(repo_root).as_posix(), "package": package[0]["name"], "interfaces": {}, "worlds": {}}
        for match in INTERFACE.finditer(source):
            category, name = match.group(1), match.group(2)
            if category == "interface":
                contract["interfaces"][name] = normalize_interface(package[0]["interfaces"][name])
                seen_interfaces.add(name)
            else:
                world = resolved["worlds"][package[0]["worlds"][name]]
                directions = {}
                for direction in ("imports", "exports"):
                    names = []
                    for entry in world[direction].values():
                        if set(entry) != {"interface"}:
                            unsupported(f"world {name}: {entry}")
                        names.append(interfaces[entry["interface"]["id"]]["name"])
                    directions[direction] = names
                contract["worlds"][name] = directions
                seen_worlds.add(name)
        contracts.append(contract)
    if seen_interfaces != set(package[0]["interfaces"]) or seen_worlds != set(package[0]["worlds"]):
        unsupported("unattributed declarations")
    return contracts


def strip_comments(source: str) -> str:
    output = []
    index = 0
    depth = 0
    while index < len(source):
        if source.startswith("/*", index):
            depth += 1
            index += 2
        elif depth and source.startswith("*/", index):
            depth -= 1
            index += 2
        elif not depth and source.startswith("//", index):
            end = source.find("\n", index)
            index = len(source) if end < 0 else end
        else:
            output.append(source[index] if not depth else "\n" if source[index] == "\n" else " ")
            index += 1
    return "".join(output)


def report(schema: dict) -> str:
    lines = [
        "# Generated WIT compatibility report",
        "",
        "This file is generated from the active WIT files; it is not a second contract.",
        "",
        "| File | Interface | Records | Variants | Enums | Resources | Functions |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for contract in schema["contracts"]:
        for name, interface in contract["interfaces"].items():
            lines.append(
                f"| `{contract['file']}` | `{name}` | {len(interface['records'])} | "
                f"{len(interface['variants'])} | {len(interface['enums'])} | "
                f"{len(interface['resources'])} | {len(interface['functions'])} |"
            )
    lines.extend(
        [
            "",
            "## Component worlds",
            "",
            "The plugin-package schema lists canonical WIT worlds as the "
            "available component implementations:",
            "",
            "| World | Imports | Exports |",
            "|---|---|---|",
        ]
    )
    for contract in schema["contracts"]:
        for name, world in contract["worlds"].items():
            lines.append(
                f"| `{name}` | {', '.join(f'`{value}`' for value in world['imports'])} | "
                f"{', '.join(f'`{value}`' for value in world['exports'])} |"
            )
    lines.extend(
        [
            "",
            "## Native mapping",
            "",
            "The normative value and resource mapping is [RPC v1](../protocol/rpc-v1.md).",
            "This report is generated inventory, not a second wire specification.",
            "The generated schema has no Wasmtime or Component ABI dependency.",
        ]
    )
    return "\n".join(lines) + "\n"


def package_manifest_schema(package: str, worlds: dict[str, dict]) -> dict:
    component = {
        "type": "object",
        "required": ["world", "artifact"],
        "additionalProperties": False,
        "properties": {
            "world": {
                "type": "string",
                "enum": sorted(worlds),
                "description": "Canonical WIT world implemented by this component; see protocol/plugin-package.md for the normative package and component metadata contract.",
            },
            "artifact": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^[^/\\:\u0000-\u001F\u007F][^\\:\u0000-\u001F\u007F]*$",
                "description": "Portable logical package path using `/` separators; see protocol/package-artifact.md for normalization, containment, and symlink rules.",
            },
            "credential_slots": {
                "type": "object",
                "description": "Component-scoped credential requirements; each property name is a stable plugin-defined slot identity. Presentation fields do not participate in identity. See protocol/plugin-package.md for normative semantics.",
                "propertyNames": {"pattern": "^[a-z0-9][a-z0-9._-]*$"},
                "additionalProperties": {"$ref": "#/$defs/credential-slot"},
            }
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stashd.dev/schemas/plugin-package.schema.json",
        "title": "Stashd Plugin Package Manifest",
        "description": "One deployable package identity may contain one or more identified components implementing canonical WIT worlds.",
        "x-stashd-contract-package": package,
        "type": "object",
        "required": ["id", "version", "contract", "components"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "version": {"type": "string", "minLength": 1},
            "contract": {
                "type": "string",
                "pattern": r"^stashd:plugin@[0-9]+\.[0-9]+\.[0-9]+$",
                "description": "Exact Stashd WIT package identity implemented by this package; hosts determine exact-identity support before lifecycle invocation.",
            },
            "components": {
                "type": "object",
                "minProperties": 1,
                "propertyNames": {"pattern": "^[a-z0-9][a-z0-9._-]*$"},
                "additionalProperties": {"$ref": "#/$defs/component"},
            },
        },
        "$defs": {
            "component": component,
            "credential-slot": {
                "type": "object",
                "required": ["label", "required"],
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string", "minLength": 1, "description": "Presentation metadata; does not participate in slot identity."},
                    "required": {"type": "boolean", "description": "Whether the component needs this binding for its normal configured function; does not grant access or guarantee availability."},
                    "description": {"type": "string", "description": "Presentation metadata; does not participate in slot identity."},
                },
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    wit_root = args.repo_root / "wit"
    stable_file_order = ("input.wit", "broadcast.wit", "enrichment.wit", "collection-export.wit")
    paths = sorted(
        wit_root.glob("*.wit"),
        key=lambda path: (
            stable_file_order.index(path.name) if path.name in stable_file_order else len(stable_file_order),
            path.name,
        ),
    )
    resolved = json.loads(subprocess.check_output(
        ["wasm-tools", "component", "wit", str(wit_root), "--json"], text=True
    ))
    contracts = normalize_package(resolved, paths, args.repo_root)
    if not contracts:
        raise ValueError("the WIT package must contain at least one contract file")
    packages = {contract["package"] for contract in contracts}
    if None in packages or len(packages) != 1:
        raise ValueError("WIT contract files must declare the same package and version")
    worlds = {
        name: world
        for contract in contracts
        for name, world in contract["worlds"].items()
    }
    world_count = sum(len(contract["worlds"]) for contract in contracts)
    if len(worlds) != world_count:
        raise ValueError("WIT world names must be unique across the package")
    package = packages.pop()
    schema = {"schema_version": 1, "package": package, "contracts": contracts}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "wit-schema.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    (args.output_dir / "compatibility-report.md").write_text(report(schema))
    (args.output_dir / "plugin-package.schema.json").write_text(
        json.dumps(package_manifest_schema(package, worlds), indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
