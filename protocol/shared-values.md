# Shared value semantics

This document defines semantics shared by canonical plugin value types. Core validates and transports these values without interpreting plugin-owned domain meaning.

## Plugin metadata

`io-host.plugin-metadata` retains its WIT shape: `schema: string` and `json: string`. Every metadata facet transported anywhere under this contract, including Input, Broadcast, Enrichment, staged artifacts, diagnostics/evidence, and destination-metadata reports, is governed by the receiver-enforceable checks and producer obligations below. A facet that passes structural validation is receiver-valid; that does not prove producer conformance.

### Receiver-enforceable validation

Every canonical receiver MUST mechanically validate only universal properties that do not require interpreting plugin-owned schema or domain meaning. `schema` MUST have a string length greater than zero. This is exactly a non-zero length check: receivers MUST NOT trim whitespace, normalize Unicode, parse separators, or require `@`, digits, semver, reverse-domain notation, MIME syntax, a registry prefix, or a recognizable revision token. Thus `example`, `example@1`, `youtube.video@3`, `org.example/foo/v2`, `urn:example:metadata:alpha`, `x`, and ` ` all pass this check; the empty string fails. Passing this check says nothing about the quality or producer conformance of the identifier.

`json` MUST be syntactically valid interoperable JSON whose parsed root is an object. Objects at every depth MUST NOT contain duplicate member names. Malformed JSON, arrays, scalars, null, and duplicates are invalid. Receivers MUST NOT accept malformed JSON as opaque text, apply first-wins or last-wins duplicate handling, normalize or reconstruct JSON, or interpret plugin-owned domain fields as canonical shared validation. An endpoint receiving any structurally invalid facet MUST reject the containing protocol value as a contract/protocol violation. It MUST NOT silently drop only the bad facet, convert the violation to a lifecycle `plugin-error`, fix or normalize it, or choose a duplicate-member winner. A receiver MUST NOT reject structurally valid metadata merely because it cannot prove a producer semantic obligation.

After successful structural validation, the host transports/stores the exact WIT string values. JSON key ordering, whitespace, number spelling where accepted by interoperable JSON, Unicode normalization, and schema spelling are not canonicalized. Semantically equivalent serialized objects may remain distinct WIT string values. No canonical JSON/JCS requirement applies. Equality of metadata inside canonical staged-artifact descriptors compares the actual WIT metadata values.

### Producer obligations

The producing plugin MUST use a schema identifier it owns/defines for the facet contract, treat that identifier as stable for one defined facet interpretation, and make it versioned or revision-bearing according to its own identifier scheme. Reusing the exact identifier asserts the same defined facet contract/interpretation under the producer's compatibility policy. An incompatible change to structural or field semantics MUST use a different schema identity/revision. The producer MUST define its compatible-extension policy.

These are producer obligations, not generic receiver checks. Core maintains no universal schema ownership registry and MUST NOT infer ownership from naming syntax or reject a structurally valid identifier because it does not match a package ID, reverse domain, provider name, or other convention. The canonical host does not maintain schema histories to prove reuse claims. It does not compare old/new JSON structures to infer compatibility, parse version components, order revisions, or infer compatibility from similar names. Schema-aware consumers may assess producer claims using producer-defined context; the generic Core/host validator MUST NOT infer them by parsing opaque schema names or arbitrary domain JSON. For example, `example` is receiver-valid despite lacking a recognizable version marker, while `foo@99` is not thereby proven producer-conforming merely because it resembles a version.

The producing plugin MUST NOT put credential references/selectors or secret material in metadata. Since metadata domain JSON is intentionally opaque, generic Core validation MUST NOT enforce this by scanning names such as `password`, `token`, `credential`, or `secret`, comparing arbitrary values with known credential IDs, parsing provider-specific fields, guessing from value formats, or rejecting fields that merely look sensitive. Structurally valid metadata remains receiver-valid even if its producer violates this obligation; this validator is not expected to discover that violation. This clarification does not remove separate architectural safeguards that keep credentials out of metadata-producing APIs/configuration paths.

### Opaque transport and evolution

Receiver-validity and producer conformance are complementary: canonical accept/reject decisions for metadata transport are based on receiver-enforceable structure, while producer obligations govern what a conforming plugin may emit. For example, `schema: "example"` and `json: {"credential":"opaque-looking-value"}` are structurally valid; producer conformance may be violated if that value is actually credential or secret material, but Core MUST NOT infer this from the domain key/value. This example contains no actual credential. Equivalent domain meaning does not imply byte/string equality, and the host MUST NOT interpret the domain JSON.

## Byte streams

For `io-host.byte-stream.read`, `ok(none)` is the only EOF representation. A successful non-EOF result `ok(some(bytes))` MUST contain at least one byte and MUST be chosen so the complete encoded response fits within the plugin's advertised receive-frame maximum; no separate hidden stream chunk byte ceiling applies. `ok(some([]))` is invalid protocol/contract behavior. A receiver MUST reject it and fail the active invocation/channel under the existing protocol-failure model; it MUST NOT treat it as EOF, retry/spin, skip it, or convert it to `none`. RPC v1 continues to encode `list<u8>` as a JSON array of byte integers.

EOF is sticky: after a stream returns `none`, all later successful reads while the resource remains live MUST return `none`; no later bytes may appear. The owner may drop the stream after EOF. No rewind/reset operation is defined. These rules do not define a universal chunk size.

## Progress

`progress.fraction = none` means indeterminate or stage-only progress; the host/UI MUST NOT derive a percentage from it. A present fraction MUST be finite and in the inclusive range `[0.0, 1.0]`; zero means zero fractional completion and one means complete for the work described. RPC v1 already rejects non-finite `f64`; this contract additionally rejects values outside the range.

Because `report-progress` returns unit, an invalid fraction is a contract/protocol failure for the active invocation. The host MUST reject it, not clamp it, convert it to `none`, ignore it and continue, or reinterpret percentages. No universal monotonicity rule applies across callbacks; lifecycle stages may restart or describe independent work. `stage` is plugin-defined diagnostic/presentation text, and the host MUST NOT parse semantic state from it.
