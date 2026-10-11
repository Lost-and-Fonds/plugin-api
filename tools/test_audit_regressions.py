#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV = {key: value for key, value in os.environ.items() if not key.startswith("STASHD_")}


def run_script(name, *arguments, env=None):
    return subprocess.run([sys.executable, str(ROOT / "tools" / name), *map(str, arguments)], capture_output=True, text=True, env=env or ENV)


class AuditRegressions(unittest.TestCase):
    def test_rejection_harness(self):
        tree = ast.parse((ROOT / "tools" / "test_contract_sensitivity.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check_rejection")
        namespace: dict[str, Any] = {"expected_diagnostics": {"test": "E_EXPECTED"}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "harness", "exec"), namespace)
        for status, diagnostic in ((0, ""), (1, "missing document"), (1, "Traceback"), (-9, "E_EXPECTED"), (1, "E_OTHER")):
            with self.assertRaises(SystemExit):
                namespace["check_rejection"](subprocess.CompletedProcess([], status, "", diagnostic), "test")
        namespace["check_rejection"](subprocess.CompletedProcess([], 1, "", "E_EXPECTED\n"), "test")

    def test_valid_unsupported_wit(self):
        declarations = (
            "type alternate = string;",
            "flags switches { active, }",
            "resource extra { constructor(); }",
            "resource extra { make: static func() -> extra; }",
            "type coordinates = tuple<u32, u32>;",
            "character: func(value: char);",
            "type renamed = plugin-error-detail;",
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "wit", root / "wit")
                source = root / "wit" / "io.wit"
                source.write_text(source.read_text().replace("interface plugin-types {", "interface plugin-types {\n    " + declaration, 1))
                parser = subprocess.run(["wasm-tools", "component", "wit", str(root / "wit"), "--json"], capture_output=True, text=True)
                self.assertEqual(parser.returncode, 0, parser.stderr)
                result = run_script("extract_wit.py", "--repo-root", root, "--output-dir", root / "schema")
                self.assertEqual(result.returncode, 1)
                self.assertIn("E_WIT_UNSUPPORTED:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((root / "schema").exists())

    def test_duplicate_wit_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "wit", root / "wit")
            source = root / "wit" / "io.wit"
            source.write_text(source.read_text().replace("interface plugin-types {", "interface plugin-types {\nrecord plugin-error-detail { value: string }", 1))
            result = run_script("extract_wit.py", "--repo-root", root, "--output-dir", root / "schema")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "schema").exists())

    def test_comments_and_determinism(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "wit", root / "wit")
            source = root / "wit" / "io.wit"
            source.write_text(source.read_text().replace("interface plugin-types {", "interface plugin-types {\n/* record phantom { value: string } /* nested } */ */", 1))
            for output in ("first", "second"):
                result = run_script("extract_wit.py", "--repo-root", root, "--output-dir", root / output)
                self.assertEqual(result.returncode, 0, result.stderr)
            for artifact in ("wit-schema.json", "plugin-package.schema.json", "compatibility-report.md"):
                self.assertEqual((root / "first" / artifact).read_bytes(), (ROOT / "schema" / artifact).read_bytes())
                self.assertEqual((root / "first" / artifact).read_bytes(), (root / "second" / artifact).read_bytes())

    def test_world_and_manifest_mutations(self):
        schema = json.loads((ROOT / "schema" / "wit-schema.json").read_text())
        manifest = json.loads((ROOT / "schema" / "plugin-package.schema.json").read_text())
        mutations = []
        for world_name in ("input-world", "broadcast-world", "enrichment-world", "collection-export-world"):
            for direction in ("imports", "exports"):
                for change in ("remove", "add", "duplicate"):
                    candidate = copy.deepcopy(schema)
                    world = next(contract["worlds"][world_name] for contract in candidate["contracts"] if world_name in contract["worlds"])
                    if change == "remove":
                        world[direction].pop(1 if direction == "imports" and world_name != "collection-export-world" else 0)
                    else:
                        world[direction].append("logging-host" if change == "add" else world[direction][0])
                    mutations.append((candidate, manifest, f"E_WORLD_MEMBERS: {world_name}.{direction}"))
        for field, value, diagnostic in (("additionalProperties", True, "E_MANIFEST_ROOT"), ("type", "array", "E_MANIFEST_ROOT"), ("required", ["id"], "plugin package schema must declare")):
            candidate = copy.deepcopy(manifest)
            candidate[field] = value
            mutations.append((schema, candidate, diagnostic))
        for field in ("id", "version"):
            candidate = copy.deepcopy(manifest)
            candidate["properties"][field]["minLength"] = 0
            mutations.append((schema, candidate, "E_MANIFEST_STRING"))
        for definition, field, value, diagnostic in (("component", "type", "array", "E_MANIFEST_COMPONENT"), ("component", "required", ["world"], "each identified component"), ("credential-slot", "type", "array", "E_MANIFEST_SLOT")):
            candidate = copy.deepcopy(manifest)
            candidate["$defs"][definition][field] = value
            mutations.append((schema, candidate, diagnostic))
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            manifest_path = Path(directory) / "manifest.json"
            for candidate_schema, candidate_manifest, diagnostic in mutations:
                with self.subTest(diagnostic=diagnostic):
                    schema_path.write_text(json.dumps(candidate_schema))
                    manifest_path.write_text(json.dumps(candidate_manifest))
                    result = run_script("verify_generated_contract.py", schema_path, manifest_path)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_audit_rule_sensitivity(self):
        mutations = (
            ("protocol/helper-process.md", "MUST wake the event wait", "MAY wait for output"),
            ("protocol/helper-process.md", "MUST NOT set the invocation flag", "MUST set the invocation flag"),
            ("protocol/helper-process.md", "flag remains true for the invocation", "flag may reset"),
            ("protocol/helper-process.md", "Notification MUST NOT consume, reorder, or discard queued events", "Notification discards output"),
            ("protocol/staging.md", "registers no completed artifact", "registers a partial artifact"),
            ("protocol/staging.md", "Registration is atomic with successful finalization", "Registration may precede finalization"),
            ("protocol/rpc-v1.md", "ownership does not revert", "ownership reverts"),
            ("protocol/rpc-v1.md", "complete frame was not accepted, no transfer was committed", "incomplete frames transfer ownership"),
            ("protocol/rpc-v1.md", "MUST accept remote-owner method calls, borrows, and", "MUST reject remote-owner method calls, borrows, and"),
            ("protocol/rpc-v1.md", "request cannot fit the plugin's advertised receive", "request cannot fit the host's advertised receive"),
            ("README.md", "Normal exit\nreturns the valid writer", "Normal exit returns a byte stream"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "protocol", root / "protocol")
            shutil.copytree(ROOT / "schema", root / "schema")
            (root / "tools").mkdir()
            shutil.copy(ROOT / "tools" / "verify_audit_contract.py", root / "tools")
            shutil.copy(ROOT / "README.md", root / "README.md")
            for filename, original, replacement in mutations:
                path = root / filename
                text = path.read_text()
                self.assertIn(original, text)
                path.write_text(text.replace(original, replacement, 1))
                result = subprocess.run([sys.executable, str(root / "tools" / "verify_audit_contract.py")], capture_output=True, text=True)
                path.write_text(text)
                self.assertEqual(result.returncode, 1, filename)
                self.assertIn("E_AUDIT_SPEC:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_integer_mutations(self):
        vectors = json.loads((ROOT / "protocol" / "rpc-v1-vectors.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vectors.json"
            for name in ("u64-boundaries", "s64-boundaries"):
                for value in ("01", "-0", "١", "+1", " 1", "1 ", "1.0", "1e2", "--1", 1, True, str(2**64), str(-(2**63)-1)):
                    candidate = copy.deepcopy(vectors)
                    candidate_cases = next(items for items in candidate.values() if isinstance(items, list) and any(isinstance(item, dict) and item.get("name") == name for item in items))
                    next(item for item in candidate_cases if item.get("name") == name)["values"] = [value]
                    path.write_text(json.dumps(candidate))
                    result = run_script("verify_rpc_v1.py", ROOT / "protocol" / "rpc-v1.md", path, ROOT / "schema" / "wit-schema.json")
                    self.assertEqual(result.returncode, 1, (name, value))
                    self.assertIn(f"RPC v1 {name} must use in-range decimal strings", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
