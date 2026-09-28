# Input value semantics

This document normatively defines Input size estimates and identity across independent lifecycle invocations. The Input WIT shapes remain unchanged.

## Size estimate values

`resolved-input` and `discovered-item` use the same `(size-bytes, size-estimated)` invariant:

| `size-bytes` | `size-estimated` | Meaning |
| --- | --- | --- |
| `none` | `false` | No byte-size value is currently known or provided. |
| `some(N)` | `false` | N is presented as a non-estimated byte-size value under the plugin's current knowledge/source semantics. It is not a claim that the source can never change. |
| `some(N)` | `true` | N is an estimated byte size. |
| `none` | `true` | Invalid: an estimate has no numeric value. |

Zero is a valid `u64` size. A host receiving the invalid combination MUST reject the containing value as a contract/protocol violation. It MUST NOT rewrite the flag or invent a value. The same rule applies to both records; `size-estimated` is not a substitute for presence. Preserved Asset `size-bytes` is factual representation size and does not use this estimate flag.

## Identity across invocations

Process reuse is host policy. Plugin correctness MUST NOT depend on mutable process-local state surviving between lifecycle invocations, consistent with [component execution](component-execution.md).

A successful `resolve` or `resolve-delegation` returns `resolved-input.id`, which the host later supplies as `discovery-request.input-id`. The plugin MUST be able to interpret and use that ID in a later `discover` invocation without an undocumented in-memory mapping established by the earlier resolve call. The ID remains opaque to Core; it need not be a URL, provider ID, human-readable value, or reversible by Core. Any needed meaning must be recoverable from the token itself or independently available durable/external/plugin state.

`resolved-input.canonical-reference`, when present, remains an opaque plugin-owned reference, not a host-parsed URL or provider identity. Since `discover` receives `input-id`, the plugin MUST NOT require a transient process-local association between the ID and canonical reference. Any required relationship must remain usable across process/invocation boundaries.

`acquire` receives the complete `discovered-item` in a later invocation. The supplied Item values, in particular stable `id`, opaque `reference`, metadata and delegation fields, together with explicit acquisition options and credentials, MUST provide the plugin-visible information needed to attempt acquisition under its defined external/durable state model. The plugin MUST NOT require an undocumented process-local object retained from the earlier discovery invocation.

These rules do not require all state to be encoded inline. Plugins MAY consult the provider/source, package-owned immutable/static data, independently durable plugin state where available, and credentials explicitly granted to the new invocation. Correctness MUST NOT depend on an undocumented mutable process-local mapping surviving from a previous lifecycle call.

`discovery-continuation` and `discovery-refresh-state` remain the explicit opaque plugin-owned cross-invocation state defined by [Input discovery](input-discovery.md). They MUST be self-sufficient across process/invocation boundaries and contain no credential material. Plugins MUST NOT create a second hidden continuation mechanism. This document adds no persistence API or WIT fields.
