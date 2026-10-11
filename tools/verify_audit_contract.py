#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(document, phrases):
    text = (ROOT / document).read_text()
    for phrase in phrases:
        if phrase not in text:
            raise SystemExit(f"E_AUDIT_SPEC: {document}: {phrase}")


require("protocol/rpc-v1.md", (
    "implementing endpoint retains the backing resource",
    "MUST accept remote-owner method calls, borrows, and",
    "It MUST NOT require local ownership",
    "Duplicate owned occurrences of one handle",
    "even if the WIT operation returns a valid error result",
    "ownership does not revert",
    "complete frame was not accepted, no transfer was committed",
    "each backing resource exactly once",
    "request cannot fit the plugin's advertised receive",
))
require("protocol/helper-process.md", (
    "min(wait-ms, 1000)", "zero polls immediately",
    "`end` is sticky after terminal consumption",
    "Every poll response MUST report `invocation-cancel-requested`",
    "Cancellation during a blocked poll MUST wake the event wait",
    "flag is sampled at response construction",
    "Notification MUST NOT consume, reorder, or discard queued events",
    "flag remains true for the invocation",
    "MUST NOT set the invocation flag",
    "does not cancel a helper, synthesize a helper terminal, or transfer ownership",
    "Core may terminate the invocation before a plugin observes the flag",
))
require("protocol/staging.md", (
    "Any typed `finish` failure from OPEN transitions OPEN to POISONED",
    "returns no descriptor", "registers no completed artifact",
    "Registration is atomic with successful finalization",
    "Retrying finish cannot recover",
))
require("README.md", ("stashd:plugin@0.19.0", "### 0.19.0 downstream handoff", "Normal exit\nreturns the valid writer"))
if "optional borrowed staged writer for stdout" in (ROOT / "README.md").read_text():
    raise SystemExit("E_AUDIT_SPEC: obsolete helper ownership guidance")
schema = json.loads((ROOT / "schema" / "wit-schema.json").read_text())
io = next(contract["interfaces"]["io-host"] for contract in schema["contracts"] if "io-host" in contract["interfaces"])
expected_fields = [
    {"name": "invocation-cancel-requested", "type": {"kind": "scalar", "name": "bool"}},
    {"name": "state", "type": {"kind": "named", "name": "helper-poll-state"}},
]
if io["records"].get("helper-poll-result", {}).get("fields") != expected_fields:
    raise SystemExit("E_AUDIT_WIT: helper-poll-result")
if io["variants"].get("helper-poll-state", {}).get("values") != [
    {"name": "pending", "type": None},
    {"name": "event", "type": {"kind": "named", "name": "helper-event"}},
    {"name": "end", "type": None},
]:
    raise SystemExit("E_AUDIT_WIT: helper-poll-state")
vectors = json.loads((ROOT / "protocol" / "audit-vectors.json").read_text())
if vectors["contract"] != schema["package"]:
    raise SystemExit("E_AUDIT_VECTORS: contract identity")
for case in vectors["ownership"]:
    owner, live, releases = "host", True, 0
    for step in case["steps"]:
        operation = step["op"]
        if operation == "cleanup":
            releases += int(live)
            live = False
            continue
        permitted = live and step["from"] == owner
        if step.get("rejected", False) != (not permitted):
            raise SystemExit(f"E_AUDIT_OWNERSHIP: {case['name']}")
        if not permitted:
            continue
        if operation == "transfer" and step["accepted"]:
            if step.get("duplicate-owned"):
                raise SystemExit("E_AUDIT_OWNERSHIP: duplicate transfer accepted")
            owner = step["to"]
        elif operation == "drop":
            live = False
            releases += 1
    if (owner, live, releases) != (case["owner"], case["live"], case["releases"]):
        raise SystemExit(f"E_AUDIT_OWNERSHIP: {case['name']} final state")
for case in vectors["polling"]:
    events = list(case["events"])
    cancelled = False
    ended = False
    first_elapsed = 0
    for index, expected in enumerate(case["expected"]):
        wait = min(case["wait-ms"], 1000)
        cancellation = case["cancel-at-ms"]
        if case.get("cancel-before-poll") == index or cancellation is not None and cancellation <= wait:
            cancelled = True
        if events:
            event = events.pop(0)
            state = {"tag": "event", "value": event}
            ended = event == "terminal"
            elapsed = 0
        elif ended:
            state, elapsed = "end", 0
        else:
            state = "pending"
            elapsed = 0 if cancelled else wait
            if index == 0 and cancellation is not None and cancellation <= wait:
                elapsed = cancellation
        if index == 0:
            first_elapsed = elapsed
        if {"invocation-cancel-requested": cancelled, "state": state} != expected:
            raise SystemExit(f"E_AUDIT_POLLING: {case['name']} poll {index}")
    if first_elapsed != case["elapsed-ms"]:
        raise SystemExit(f"E_AUDIT_POLLING: {case['name']} wait")
for case in vectors["finalization"]:
    state, registered, errors = "OPEN", 0, 0
    for operation in case["steps"]:
        if operation == "drop":
            continue
        if state != "OPEN":
            errors += 1
        elif operation.endswith("-error"):
            state = "POISONED"
            errors += 1
        elif operation == "finish":
            state = "FINISHED"
            registered += 1
    if (state, registered, errors) != (case["state"], case["registered"], case["errors"]):
        raise SystemExit(f"E_AUDIT_FINALIZATION: {case['name']}")
limits = vectors["collection-export"]
if (limits["request-bytes"] <= limits["plugin-receive"]) != limits["request-fits"] or (limits["response-bytes"] <= limits["host-receive"]) != limits["response-fits"]:
    raise SystemExit("E_AUDIT_FRAME: directional limits")
print("audit ownership, polling, finalization, and handoff invariants verified")
