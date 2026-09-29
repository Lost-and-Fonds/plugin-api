# Shared value semantics

This document defines semantics shared by canonical plugin value types. Core validates and transports these values without interpreting plugin-owned domain meaning.

## Plugin metadata

`io-host.plugin-metadata` retains its WIT shape: `schema: string` and `json: string`. Every metadata facet transported anywhere under this contract, including Input, Broadcast, Enrichment, staged artifacts, diagnostics/evidence, and destination-metadata reports, MUST satisfy these rules. An endpoint receiving an invalid facet MUST reject the containing protocol value as a contract/protocol violation. It MUST NOT accept malformed JSON as text, choose a duplicate member value, normalize JSON, convert the violation to a lifecycle `plugin-error`, or drop only the invalid facet from a purported successful value.

`schema` MUST be non-empty, plugin-owned, stable for one defined facet contract, and versioned/revision-bearing in the plugin's own identifier scheme. No universal URI, MIME, reverse-domain, provider, or registry syntax is imposed. Reusing an identifier asserts the same facet contract and interpretation. An incompatible change to field semantics or structural contract requires a different schema identifier/version. Compatible extension policy remains plugin-schema-owned. Core MUST NOT infer compatibility from the identifier or inspect it to derive provider/domain taxonomy.

`json` MUST be syntactically valid interoperable JSON whose parsed root is an object. Objects at every depth MUST NOT contain duplicate member names. Other root types, malformed text, and duplicates are invalid. JSON key ordering, whitespace, number spelling, and Unicode normalization are not canonicalized: semantically equivalent serialized objects may remain distinct WIT string values. No canonical JSON/JCS requirement applies. The host transports the exact validated string opaquely and MUST NOT reconstruct, normalize, or interpret its domain fields. Equality of metadata inside canonical staged-artifact descriptors therefore compares the actual WIT metadata values.

## Byte streams

For `io-host.byte-stream.read`, `ok(none)` is the only EOF representation. A successful non-EOF result `ok(some(bytes))` MUST contain at least one byte and MUST be chosen so the complete encoded response fits within the plugin's advertised receive-frame maximum; no separate hidden stream chunk byte ceiling applies. `ok(some([]))` is invalid protocol/contract behavior. A receiver MUST reject it and fail the active invocation/channel under the existing protocol-failure model; it MUST NOT treat it as EOF, retry/spin, skip it, or convert it to `none`. RPC v1 continues to encode `list<u8>` as a JSON array of byte integers.

EOF is sticky: after a stream returns `none`, all later successful reads while the resource remains live MUST return `none`; no later bytes may appear. The owner may drop the stream after EOF. No rewind/reset operation is defined. These rules do not define a universal chunk size.

## Progress

`progress.fraction = none` means indeterminate or stage-only progress; the host/UI MUST NOT derive a percentage from it. A present fraction MUST be finite and in the inclusive range `[0.0, 1.0]`; zero means zero fractional completion and one means complete for the work described. RPC v1 already rejects non-finite `f64`; this contract additionally rejects values outside the range.

Because `report-progress` returns unit, an invalid fraction is a contract/protocol failure for the active invocation. The host MUST reject it, not clamp it, convert it to `none`, ignore it and continue, or reinterpret percentages. No universal monotonicity rule applies across callbacks; lifecycle stages may restart or describe independent work. `stage` is plugin-defined diagnostic/presentation text, and the host MUST NOT parse semantic state from it.
