# Staged output authority and lifecycle

This document normatively defines the authority, validation, lifetime, and writer state of staged artifacts. It composes with [RPC v1](rpc-v1.md), which owns resource handles, resource drop, invocation lifetime, and protocol failure. The WIT value-record and resource shapes remain unchanged.

## Canonical artifact authority

`staged-artifact` is an immutable host-issued descriptor (receipt), not a resource handle. The host maintains an invocation-scoped registry keyed by each reference. Only a successful `staged-writer.finish()` creates and registers an artifact. It registers exactly one artifact and returns its canonical descriptor.

The host generates a non-empty opaque reference identifying exactly one completed artifact in the current invocation. It MUST NOT expose or encode a path, URL, storage identifier, provider identity, or secret. Plugins MUST NOT interpret it. Possession or guessing alone grants no authority. It MUST NOT resolve in another invocation or be reused for a different artifact within the invocation. The active invocation context and registry, not reference text alone, determine validity.

The host computes `size-bytes` from bytes successfully written. It is factual host-observed state and the plugin cannot author or override it. `media-type` and `metadata` originate in `staging-area.create`; the host records the exact WIT values supplied and freezes them into the canonical descriptor at successful finish. This document adds no metadata validity rules or JSON canonicalization.

A plugin MAY copy a descriptor value. Any operation accepting one MUST resolve its reference in the current invocation's completed-artifact registry and compare the entire supplied descriptor against the canonical descriptor: `reference`, `media-type`, `size-bytes`, and `metadata`. Reconstructing a record does not grant mutation semantics. Adoption uses the canonical host-recorded descriptor, never plugin-supplied replacement fields.

## Opening completed output

Before opening bytes, `open-staged-artifact` MUST look up the reference in the active invocation's completed-artifact registry. Unknown, fabricated, stale, or other-invocation references return `stream-error.missing`. A known reference with any descriptor-field mismatch returns `stream-error.denied`. Underlying staged-byte read or storage failures return `stream-error.failed(...)`. Only an exact canonical descriptor may be opened; existing offset and length rules then apply. A canonical descriptor may be reopened repeatedly in the same invocation; each call returns a new invocation-scoped canonical `byte-stream`.

## Writer state machine

Each newly created writer begins **OPEN**. Its behavioral states are **OPEN**, **POISONED**, and **FINISHED**; these are not wire fields.

In OPEN, a successful `write` appends the complete chunk and leaves the writer OPEN. Existing configured chunk limits and atomic rejection apply: an oversized or rejected chunk is not partially appended. Any `write` returning any `staging-error` transitions OPEN to POISONED. Partial physical output remains unpublished and can never be finalized. A helper or output-stream failure that existing helper semantics say makes the writer unfinalizable also transitions it to POISONED.

A POISONED writer cannot recover or produce an artifact. Subsequent `write` and `finish` calls fail deterministically with `staging-error.failed(...)`; retrying a failed chunk cannot make it finalizable.

A successful `finish` from OPEN closes/finalizes the byte sequence, computes authoritative size, freezes create-time media type and metadata, creates a fresh reference, registers exactly one artifact, returns its canonical descriptor, and transitions OPEN to FINISHED. Finish does not consume the writer resource. FINISHED is terminal: subsequent `write` and second `finish` calls fail deterministically with `staging-error.failed(...)`. They append no bytes, create no artifact, and alter no descriptor. A writer resource remains a live owned WIT resource until explicitly dropped or invocation cleanup; use after its handle is dropped is an RPC resource-lifetime violation, not a staging error.

Dropping an OPEN or POISONED writer discards partial unpublished output and creates no artifact. Dropping a FINISHED writer releases only the writer resource handle. Its completed artifact remains registered and usable for the rest of the invocation, including reopening and successful lifecycle-result adoption. Artifact lifetime is independent of writer-handle lifetime.

## Lifecycle-result adoption

For a purported successful lifecycle result, the host MUST validate every staged-artifact descriptor in every adoption-bearing result position against the current invocation's canonical registry before accepting success. Each must have been successfully finished in this invocation, exactly match its canonical descriptor, and remain eligible for adoption; a live writer handle is not required. The result identifies which already-completed outputs survive invocation cleanup and does not mutate them.

A fabricated, unknown, stale, altered, or otherwise invalid descriptor in a purported success is a contract/protocol violation, not a plugin-authored lifecycle error. The host MUST reject the entire result, adopt none of its staged artifacts, fail the invocation, and clean/discard invocation-scoped staging according to existing failure rules. It MUST NOT partially accept valid descriptors from an invalid result.

The same canonical reference MUST NOT occur more than once among adoption candidates in one successful result. A duplicate is a contract violation: reject the whole result, adopt none, and do not silently deduplicate or create multiple durable outputs. Plugins needing two distinct durable outputs create two staged outputs.

Completed staged artifacts not returned for adoption remain temporary and are discarded at invocation end, even if opened as HTTP/helper input. Finish alone does not make output durable.

## Invocation boundary

A descriptor from an earlier invocation is never resolved against that invocation, durable Vault storage, another component/process, or another artifact with coincidentally similar fields. Every staged-artifact lookup is limited to the current invocation registry. Invocation cleanup invalidates all staged references and discards all unadopted output. No cross-invocation continuation exists.
