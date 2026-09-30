# Host-mediated byte ranges

This document normatively defines the byte range used by `io-host.open-staged-artifact`, `broadcast-host.open-asset`, and `enrichment-host.open-asset`. All three operations MUST apply this identical model to the host's authoritative known representation size, after validating the reference and authority under the operation's existing rules.

Let `S` be that authoritative size, `O` the requested offset, and `L` the optional requested length. All are unsigned `u64`. First, if `O > S`, the range is invalid and the open MUST fail with the operation's `denied` error case. For `io-host.open-staged-artifact` and `broadcast-host.open-asset`, this is `stream-error.denied`; for `enrichment-host.open-asset`, it is `asset-error.denied`. This ordinary caller-invalid range is not `missing` or `failed(...)`. `missing` remains for unknown, stale, or nonexistent references under the existing rules; `failed(...)` remains for underlying host, storage, or read failures.

For `O <= S`, calculate `remaining = S - O` and `extent = remaining` when `L` is `none`, otherwise `extent = min(L, remaining)`. The stream begins at `O` and exposes exactly `extent` bytes in forward order. A requested length extending beyond EOF is clamped to available bytes, not rejected. The calculation MUST NOT depend on evaluating `O + L`; it works for `L = u64::MAX` without overflow. A valid request MUST NOT fail because such addition would overflow.

`O == S` is valid for every length value and has extent zero. `some(0)` at any valid offset is also a successful zero-byte range; it does not make `O > S` valid. A successful zero-byte stream returns `ok(none)` on its first read. Every successful stream is a fresh invocation-scoped `byte-stream`, returns no bytes outside its range, and returns `ok(none)` after exactly its extent is exhausted. EOF is sticky under [shared byte-stream semantics](shared-values.md#byte-streams), and `some([])` is never EOF. Range extent is the logical total bytes of the stream, not an RPC frame or chunk size; reads remain subject to the peer-advertised RPC receive-frame maximum in [RPC v1](rpc-v1.md).

Reference/authority validation MUST precede range calculation, so an invalid or unauthorized reference does not reveal size or produce a different result based on offset. For staged artifacts, the host first resolves the reference in the current invocation registry: unknown, fabricated, stale, or other-invocation references return `stream-error.missing`; a known reference with descriptor mismatch returns `stream-error.denied`; only an exact canonical descriptor proceeds to range validation using canonical host-recorded `size-bytes`. For preserved Assets, the applicable lifecycle host first validates the invocation grant and resolves its bound target under [preserved Asset invocation grants](preserved-asset-grants.md); only then does it apply range validation using the target's authoritative host-known representation size. This document does not define or alter Asset grants or authority.

## Conformance vectors

The table uses `S = 100` unless otherwise specified. `MAX` is `18446744073709551615` (`u64::MAX`). A denied result means the reference has already been validated successfully.

| Size | Offset | Length | Result | Extent |
| ---: | ---: | --- | --- | ---: |
| 100 | 0 | none | success | 100 |
| 100 | 25 | none | success | 75 |
| 100 | 20 | some(10) | success | 10 |
| 100 | 90 | some(20) | success, clamped at EOF | 10 |
| 100 | 99 | some(MAX) | success, clamped at EOF | 1 |
| 100 | 100 | none | success, immediate EOF | 0 |
| 100 | 100 | some(0) | success, immediate EOF | 0 |
| 100 | 100 | some(50) | success, immediate EOF | 0 |
| 100 | 101 | none | denied | — |
| 100 | 101 | some(0) | denied | — |
| 100 | 50 | some(0) | success, immediate EOF | 0 |
| 0 | 0 | none | success, immediate EOF | 0 |
| 0 | 0 | some(MAX) | success, immediate EOF | 0 |
| 0 | 1 | some(0) | denied | — |
| 100 | 50 | some(MAX) | success, clamped at EOF | 50 |

Each operation MUST conform to every vector and mapping above. The open is not a random-access storage API and MUST NOT expose a path or require a size lookup operation.
