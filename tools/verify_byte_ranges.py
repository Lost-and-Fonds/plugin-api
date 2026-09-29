"""Verify shared byte-range requirements and conformance vectors for each API."""

from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = (root / "protocol" / "byte-ranges.md").read_text(encoding="utf-8")
required = (
    "the open MUST fail with the operation's `denied` error case",
    "`stream-error.denied`",
    "`asset-error.denied`",
    "if `O > S`",
    "`remaining = S - O`",
    "`extent = remaining`",
    "`extent = min(L, remaining)`",
    "MUST NOT depend on evaluating `O + L`",
    "`O == S` is valid",
    "`some(0)` at any valid offset",
    "clamped to available bytes, not rejected",
    "Reference/authority validation MUST precede range calculation",
    "`u64::MAX`",
    "RPC receive-frame maximum",
)
for phrase in required:
    if phrase.casefold() not in spec.casefold():
        raise SystemExit(f"shared byte-range specification is missing: {phrase}")

operations = (
    ("wit/io.wit", "open-staged-artifact", "protocol/byte-ranges.md"),
    ("wit/broadcast.wit", "open-asset", "protocol/byte-ranges.md"),
    ("wit/enrichment.wit", "open-asset", "protocol/byte-ranges.md"),
)
for filename, operation, link in operations:
    source = (root / filename).read_text(encoding="utf-8")
    start = source.find(f"{operation}: func")
    if start < 0:
        raise SystemExit(f"{filename} is missing {operation}")
    preceding = source[:start].splitlines()
    comments = []
    for line in reversed(preceding):
        if line.lstrip().startswith("///"):
            comments.append(line)
        elif comments:
            break
    if not comments or link not in "\n".join(reversed(comments)):
        raise SystemExit(f"{filename}:{operation} must reference {link}")

vectors = {
    "| 100 | 0 | none | success | 100 |",
    "| 100 | 25 | none | success | 75 |",
    "| 100 | 20 | some(10) | success | 10 |",
    "| 100 | 90 | some(20) | success, clamped at EOF | 10 |",
    "| 100 | 99 | some(MAX) | success, clamped at EOF | 1 |",
    "| 100 | 100 | none | success, immediate EOF | 0 |",
    "| 100 | 100 | some(0) | success, immediate EOF | 0 |",
    "| 100 | 100 | some(50) | success, immediate EOF | 0 |",
    "| 100 | 101 | none | denied | — |",
    "| 100 | 101 | some(0) | denied | — |",
    "| 100 | 50 | some(0) | success, immediate EOF | 0 |",
    "| 0 | 0 | none | success, immediate EOF | 0 |",
    "| 0 | 0 | some(MAX) | success, immediate EOF | 0 |",
    "| 0 | 1 | some(0) | denied | — |",
    "| 100 | 50 | some(MAX) | success, clamped at EOF | 50 |",
}
for vector in vectors:
    if vector not in spec:
        raise SystemExit(f"byte-range conformance vector is missing: {vector}")
print("byte-range semantics and all three operation references verified")
