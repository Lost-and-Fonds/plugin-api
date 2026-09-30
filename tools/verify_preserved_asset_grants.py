"""Verify preserved Asset grant semantics, vectors, and API references."""

from __future__ import annotations

import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]

spec_path = Path(os.environ.get("STASHD_PRESERVED_ASSET_GRANTS_SPEC", root / "protocol" / "preserved-asset-grants.md"))
spec = spec_path.read_text(encoding="utf-8").casefold()
required = (
    "invocation-scoped grant table",
    "| granted, valid, available target and range | success | success |",
    "| known to core but not granted; fabricated/guessed; prior invocation; another invocation; or another lifecycle host | `stream-error.denied` | `asset-error.denied` |",
    "| granted target no longer available | `stream-error.missing` | `asset-error.missing` |",
    "| granted target with invalid byte range | `stream-error.denied` | `asset-error.denied` |",
    "| underlying i/o/storage/read failure after validation | `stream-error.failed(...)` | `asset-error.failed(...)` |",
    "invocation cleanup invalidates it",
    "possession, copying, guessing, or global validity of the string grants no authority",
    "references in the `preserved-asset` values of an item actually returned",
    "references for items not yet delivered are not granted",
    "grants accumulate as items are delivered",
    "every `preserved-asset.reference` present in the supplied `item-context.assets`",
    "`capabilities(context)`",
    "grants do not transfer between invocations, from broadcast to enrichment",
    "look up the exact supplied reference in the current invocation's grant table",
    "the host must NOT first search all preserved Assets".casefold(),
    "if absent, return denied immediately",
    "if that target is no longer available, return missing",
    "only then apply the shared",
    "underlying storage/read failures return `failed(...)`",
    "Fabricated and known-but-ungranted references MUST have the same authority failure".casefold(),
    "both in-range and out-of-range requests for an ungranted reference return denied before global existence, target size, or range is evaluated",
    "invocation completion invalidates both",
    "different asset known to core but absent from the context is denied",
    "explicitly granted again in this invocation",
    "item a containing asset a",
    "item b has not yet been returned",
    "when a later `next(...)` actually returns item b",
    "both a and b remain granted through the rest of the invocation",
    "reference copied from an earlier enrichment invocation is denied",
    "does not authorize `enrichment-plugin.capabilities(...)`",
    "a copied reference remains usable within the invocation",
    "explicitly granting the same string in a later invocation",
)
for phrase in required:
    if phrase not in spec:
        raise SystemExit(f"preserved Asset grant specification is missing: {phrase}")

for filename, operation in (
    ("wit/broadcast.wit", "open-asset"),
    ("wit/enrichment.wit", "open-asset"),
):
    source = (root / filename).read_text(encoding="utf-8")
    start = source.find(f"{operation}: func")
    preceding = source[:start].splitlines()
    comments = []
    for line in reversed(preceding):
        if line.lstrip().startswith("///"):
            comments.append(line)
        elif comments:
            break
    comment = "\n".join(reversed(comments))
    if "protocol/preserved-asset-grants.md" not in comment or "denied" not in comment or "missing" not in comment:
        raise SystemExit(f"{filename}:{operation} must reference shared grants and typed errors")

io_wit = (root / "wit" / "io.wit").read_text(encoding="utf-8")
record_start = io_wit.find("record preserved-asset {")
start = io_wit.rfind("    /// An already-preserved", 0, record_start)
asset_record = "\n".join(line.removeprefix("    /// ") for line in io_wit[start:record_start].splitlines())
for phrase in ("defined input mechanism", "string alone grants nothing", "only for that invocation", "corresponding", "protocol/preserved-asset-grants.md"):
    if phrase.casefold() not in asset_record.casefold():
        raise SystemExit(f"preserved-asset.reference WIT documentation is missing: {phrase}")
print("preserved Asset grant authority, ordering, and lifecycle verified")
