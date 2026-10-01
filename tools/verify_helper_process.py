"""Verify helper process event semantics and conformance vectors."""

from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
vectors = json.loads((root / "protocol/helper-process-vectors.json").read_text(encoding="utf-8"))
if vectors.get("contract") != "stashd:plugin@0.18.0":
    raise SystemExit("helper process vectors refer to the wrong contract")

required_cases = {
    "stdout-only-live",
    "stderr-only-live",
    "interleaved-streams",
    "arbitrary-cr-progress-bytes",
    "zero-exit-after-output",
    "nonzero-normal-exit",
    "cancel-retains-pending-output",
    "timeout-retains-output",
    "runtime-failure-retains-output",
    "child-crash-retains-output",
    "stdout-only-live",
    "stderr-only-live",
    "interleaved-streams",
    "single-large-write-split-to-fit-frame",
    "natural-exit-before-cancel",
    "cancel-before-natural-exit",
    "arbitrary-cr-progress-bytes",
    "zero-exit-after-output",
    "nonzero-normal-exit",
    "cancel-retains-pending-output",
    "timeout-retains-output",
    "runtime-failure-retains-output",
    "child-crash-retains-output",
}
cases = {case["name"]: case for case in vectors.get("event_order", [])}
if set(cases) != required_cases:
    raise SystemExit("helper process event-order vectors are incomplete")
for case in cases.values():
    if "events" not in case:
        continue
    events = case["events"]
    terminal_indexes = [index for index, event in enumerate(events) if "terminal" in event]
    if len(terminal_indexes) != 1 or terminal_indexes[0] != len(events) - 1:
        raise SystemExit(f"{case['name']} must end with exactly one terminal event")
    if any(not event.get("output", {}).get("bytes_hex") for event in events if "output" in event):
        raise SystemExit(f"{case['name']} contains an empty output event")
    if any("stdout-activity" in event for event in events):
        raise SystemExit(f"{case['name']} must not contain staged stdout activity in unstaged mode")
cr_bytes = bytes.fromhex(cases["arbitrary-cr-progress-bytes"]["events"][0]["output"]["bytes_hex"].replace(" ", ""))
if b"\r" not in cr_bytes:
    raise SystemExit("carriage-return progress bytes were not preserved")
interleaved = [event["output"]["channel"] for event in cases["interleaved-streams"]["events"] if "output" in event]
if interleaved != ["stdout", "stderr", "stdout"]:
    raise SystemExit("interleaved stdout/stderr delivery order is incorrect")
large = cases["single-large-write-split-to-fit-frame"]
logical_bytes = bytes.fromhex(large["logical_write_bytes_hex"])
chunks = [bytes.fromhex(event["output"]["bytes_hex"]) for event in large["events"] if "output" in event]
if b"".join(chunks) != logical_bytes or len(chunks) < 2 or max(map(len, chunks)) >= len(logical_bytes):
    raise SystemExit("large helper writes must be split without loss or reordering")
if any(event["output"].get("encoded_response_bytes", 0) > large["frame_max_bytes"] for event in large["events"] if "output" in event):
    raise SystemExit("helper event response exceeds the negotiated frame size")
if cases["natural-exit-before-cancel"].get("terminal") != {"exited": 0} or cases["natural-exit-before-cancel"].get("cancel_result") != "no-op":
    raise SystemExit("cancellation after terminal determination must not rewrite natural exit")
if cases["cancel-before-natural-exit"].get("terminal") != "cancelled":
    raise SystemExit("accepted cancellation before natural exit must determine cancelled")
lifecycle = vectors.get("lifecycle", {})
for requirement in (
    "eof_after_terminal_consumed",
    "dropping_live_resource_terminates_and_reaps_child",
    "invocation_end_terminates_and_reaps_child",
):
    if lifecycle.get(requirement) is not True:
        raise SystemExit(f"helper process lifecycle vector missing {requirement}")
if lifecycle.get("terminal_event_count") != 1 or lifecycle.get("events_after_terminal") != 0:
    raise SystemExit("helper process terminal/EOF ordering is invalid")
if lifecycle.get("start_failure", {}).get("child_exit") is not False:
    raise SystemExit("failure to start must not invent a child exit")
slow = vectors.get("slow_consumer", {})
for requirement in (
    "stdout_and_stderr_drained_independently_of_consumer",
    "bounded_buffering_or_spooling_required",
    "accepted_bytes_delivered_before_terminal",
):
    if slow.get(requirement) is not True:
        raise SystemExit(f"high-volume helper vector missing {requirement}")
if slow.get("os_pipe_may_block_child") is not False or slow.get("silent_truncation_allowed") is not False:
    raise SystemExit("slow helper consumer may not block pipes or lose output")
staged = vectors.get("staged_stdout", {})
if staged.get("writer_receives_all_stdout_payload_bytes") is not True or staged.get("stdout_payload_bytes_in_output_events") is not False:
    raise SystemExit("staged stdout payload must not be duplicated into helper output events")
if staged.get("activity_counts_monotonic_cumulative") is not True or staged.get("stderr_diagnostic_events_retained") is not True:
    raise SystemExit("staged stdout activity and stderr diagnostics must remain observable")
activity = staged.get("activity_counts", [])
if not activity or activity != sorted(activity) or activity[-1] != staged.get("stdout_activity_event", {}).get("stdout-activity"):
    raise SystemExit("staged stdout activity counts must be cumulative and monotonic")
staged_events = staged.get("events", [])
if any(event.get("output", {}).get("channel") == "stdout" for event in staged_events):
    raise SystemExit("staged stdout payload must not appear as output(stdout, bytes)")
if [event["stdout-activity"] for event in staged_events if "stdout-activity" in event] != activity:
    raise SystemExit("staged stdout activity events do not match cumulative count vectors")
if staged.get("final_activity_before_terminal_catches_writer_accepted_bytes") is not True or staged.get("activity_may_be_coalesced") is not True:
    raise SystemExit("staged stdout activity must catch up before terminal and may be coalesced")
unstaged = vectors.get("unstaged_stdout", {})
if unstaged.get("stdout_as_live_byte_output_events") is not True or unstaged.get("stdout_activity_must_not_appear") is not True:
    raise SystemExit("unstaged stdout must use output events and exclude activity events")
ownership = vectors.get("ownership", {})
for key in ("start-helper-output", "while-running", "normal-exit", "abnormal-or-drop", "start-failure-after-request-acceptance"):
    if not ownership.get(key):
        raise SystemExit(f"helper writer ownership vector is missing {key}")

schema = json.loads((root / "schema/wit-schema.json").read_text(encoding="utf-8"))
io_host = next(contract["interfaces"]["io-host"] for contract in schema["contracts"] if contract["file"] == "wit/io.wit")
events = {item["name"]: item.get("type") for item in io_host["variants"]["helper-event"]["values"]}
if events != {
    "output": {"kind": "named", "name": "helper-output"},
    "stdout-activity": {"kind": "scalar", "name": "u64"},
    "terminal": {"kind": "named", "name": "helper-terminal"},
}:
    raise SystemExit("helper process WIT events do not match the conformance vectors")
exit_payload = next(value for value in io_host["variants"]["helper-terminal"]["values"] if value["name"] == "exited")["type"]
if exit_payload != {"kind": "named", "name": "helper-exit"}:
    raise SystemExit("normal exit must transfer the staged writer back in its terminal payload")
print("helper process event, lifetime, backpressure, and staged stdout vectors verified")
