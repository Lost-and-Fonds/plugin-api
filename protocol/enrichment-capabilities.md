# Enrichment capability discovery

This document normatively defines capability discovery by `enrichment-plugin.capabilities`.

## Local declarative discovery

`capabilities(context)` is deterministic, local, credentialless discovery for the installed component and supplied `item-context`. It describes operations that the component can attempt for that context; it MUST NOT perform remote service discovery, preflight execution, or an availability check. The same installed component version and context value MUST produce the same capability contract meaning. Results MUST NOT depend on network conditions, authentication, clock, randomness, process reuse, mutable state from earlier calls, or earlier enrichment outcomes. Correctness MUST NOT depend on process-local state surviving between lifecycle invocations. An empty list is an ordinary successful result meaning no capability applies; it does not signal service failure or an error. Even though the supplied Asset references are granted for the invocation under [preserved Asset invocation grants](preserved-asset-grants.md), this grant does not permit `capabilities` to open Asset bytes or perform fallible host work.

Discovery MAY depend on the component implementation/version, package-owned static data, and values supplied in context, including Item metadata facets and Asset descriptors (such as media type, size, identity, count, and understood plugin-owned metadata). The host does not interpret plugin-owned applicability rules. Discovery determines applicability from those descriptors and metadata, not by opening or examining Asset bytes.

Discovery MUST be computable from the supplied value context plus local installed component/package state. It MUST NOT require or depend on credentials or their availability, HTTP, remote calls or service health, current account permissions, rate limits, external mutable state, helper execution, staging, progress callbacks, or Asset byte reads through `enrichment-host.open-asset`. It MUST NOT perform a host callback whose ordinary failure materially determines the answer. Logging is not required for correctness and MUST NOT affect the returned set. These restrictions follow from discovery having no typed error result: it is declarative and MUST NOT conceal fallible execution.

## Meaning and execution boundary

An advertised capability means that, given this supplied Item/Asset context, the installed component knows how to attempt that plugin-defined operation if asked to execute it. It does not guarantee valid credentials, a configured account, a live service, an existing remote resource, successful execution, a known result, or completed caller selections. The host/UI may present it as an available operation. Capability discovery expresses applicability and attemptability, not guaranteed success.

Remote/authenticated operations MAY be advertised based on context without credentials or service probes. Execution-time authentication failures, rate limits, service outages, and ordinary failures are reported by `enrich` using its existing typed errors (such as `authentication`, `rate-limited`, `unavailable`, or `failed`). A credential unavailable or revoked through the host boundary uses the existing canonical execution path/error. Local operations likewise may be advertised from context without network access. If execution must inspect bytes and discovers malformed or unsupported content, `enrich` reports the appropriate existing typed result; this does not invalidate discovery.

## Options and multiplicity

Capability options follow the same local, deterministic discovery model. Choices MAY be compiled into the component, derived from package-owned static data, or derived locally from supplied context. Options MUST NOT require a live remote lookup. A component with a dynamic remote catalogue MUST expose a locally defined stable contract suitable for execution, or change its contract in a later component version or capability revision. This protocol does not define remote option discovery.

WIT retains list-shaped descriptors and selections; list ordering is preserved in transport but MUST NOT resolve identity or multiplicity conflicts. Identity comparisons use exact transported string equality: implementations MUST NOT trim, case-fold, Unicode-normalize, parse domain syntax, or interpret labels. No additional non-empty string requirement is introduced here.

Within one `capabilities(context)` result, each `capability.id` MUST occur at most once, regardless of revision or other descriptor fields. `capability.id` is the stable logical-operation identity; `revision` does not permit simultaneous descriptors for one ID. A duplicate ID is invalid plugin-produced contract/protocol output. The host MUST reject/fail that discovery invocation under the existing contract/protocol failure model; it MUST NOT choose first, last, or highest revision, discard, or rewrite descriptors. `capabilities` has no typed error result, so this is not `plugin-error.invalid-configuration`. An empty result is valid and means no operation applies.

Within one capability, every `configuration-option.key` MUST be unique. Within each option, `configuration-choice.value` MUST be unique. These scopes are independent: different capabilities may reuse keys, and different options may reuse values. Duplicate identities invalidate descriptor output even when entries otherwise match. Labels are presentation text, are not identity, and MAY duplicate. An advertised option MUST have at least one choice; zero choices are invalid descriptor output. A capability with no settings uses `options = []`. Each option offers one value from its explicitly advertised opaque choices; this contract defines no free-text, boolean, remote-catalogue, or implicit multi-select behavior.

For caller configuration, each option key may occur at most once. A required option has exactly one selection; an optional option has zero or one. Omission of an optional key is valid; any default behavior is defined by that capability's own semantics, and the universal contract does not select `choices[0]` automatically.

## Identity and revision

`capability.id` is the stable, opaque, plugin-owned identity of the logical operation. A presentation or options change alone does not create a new operation identity unless the plugin intentionally defines a different operation. Human-readable labels are not identity.

`capability.revision` identifies the advertised configuration and execution contract for that ID. For one ID, the revision MUST change when the accepted or interpreted caller configuration contract changes semantically, including adding/removing/changing an option key, changing requiredness, adding/removing an accepted choice when that changes accepted configuration, changing an accepted opaque choice's semantic meaning, or changing validation/interpretation. Presentation-only label changes are presentation-only changes and do not require a revision change. Do not advertise multiple descriptors for the same ID to expose old and new revisions; discovery returns at most one current descriptor per applicable ID.

For a given component version and context, the same `(capability-id, capability-revision)` MUST represent one coherent configuration contract. Accepted choice semantics MUST NOT vary with remote state, credentials, account tier, rate limits, or process history. Such execution conditions are reported by `enrich`, not encoded in the revision.

A host/UI MAY cache a descriptor to present choices and later call `enrich` with `capability-id`, `capability-revision`, and selections. The host need not resend the descriptor. `enrich` continues to receive the ID and revision independently, not the complete capability record.

## Execution validation

When `enrich` receives an unknown capability ID, an ID that does not apply to the supplied context, or an unsupported/stale revision, it MUST return `plugin-error.unsupported`. A stale revision is not invalid caller configuration. First validate capability identity and revision.

For a supported ID/revision, validate caller selections in full. Reject any duplicate `configuration-value.key` even when values are identical; do not choose first/last, deduplicate, or treat repeated keys as multi-select. Reject unknown keys. Require exactly one selection for each required option and zero or one for each optional option. Every supplied value MUST exactly equal one advertised choice value for its option. Caller selection order has no effect. Any failure, with no partial acceptance or ignored entries, MUST return `plugin-error.invalid-configuration`; duplicate selections, unknown keys, missing required keys, and unsupported values are ordinary caller errors, not RPC/protocol failures.

Invalid capability discovery output is distinct: duplicate IDs, duplicate option keys, zero-choice options, and duplicate choice values violate the plugin contract/protocol. The host MUST reject/fail the discovery invocation and MUST NOT discard, select, rewrite, or convert these producer violations to `plugin-error.invalid-configuration`. `capabilities` has no typed plugin-error return.
