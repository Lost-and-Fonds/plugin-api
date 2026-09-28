# Enrichment capability discovery

This document normatively defines capability discovery by `enrichment-plugin.capabilities`.

## Local declarative discovery

`capabilities(context)` is deterministic, local, credentialless discovery for the installed component and supplied `item-context`. It describes operations that the component can attempt for that context; it MUST NOT perform remote service discovery, preflight execution, or an availability check. The same installed component version and context value MUST produce the same capability contract meaning. Results MUST NOT depend on network conditions, authentication, clock, randomness, process reuse, mutable state from earlier calls, or earlier enrichment outcomes. Correctness MUST NOT depend on process-local state surviving between lifecycle invocations. An empty list is an ordinary successful result meaning no capability applies; it does not signal service failure or an error.

Discovery MAY depend on the component implementation/version, package-owned static data, and values supplied in context, including Item metadata facets and Asset descriptors (such as media type, size, identity, count, and understood plugin-owned metadata). The host does not interpret plugin-owned applicability rules. Discovery determines applicability from those descriptors and metadata, not by opening or examining Asset bytes.

Discovery MUST be computable from the supplied value context plus local installed component/package state. It MUST NOT require or depend on credentials or their availability, HTTP, remote calls or service health, current account permissions, rate limits, external mutable state, helper execution, staging, progress callbacks, or Asset byte reads through `enrichment-host.open-asset`. It MUST NOT perform a host callback whose ordinary failure materially determines the answer. Logging is not required for correctness and MUST NOT affect the returned set. These restrictions follow from discovery having no typed error result: it is declarative and MUST NOT conceal fallible execution.

## Meaning and execution boundary

An advertised capability means that, given this supplied Item/Asset context, the installed component knows how to attempt that plugin-defined operation if asked to execute it. It does not guarantee valid credentials, a configured account, a live service, an existing remote resource, successful execution, a known result, or completed caller selections. The host/UI may present it as an available operation. Capability discovery expresses applicability and attemptability, not guaranteed success.

Remote/authenticated operations MAY be advertised based on context without credentials or service probes. Execution-time authentication failures, rate limits, service outages, and ordinary failures are reported by `enrich` using its existing typed errors (such as `authentication`, `rate-limited`, `unavailable`, or `failed`). A credential unavailable or revoked through the host boundary uses the existing canonical execution path/error. Local operations likewise may be advertised from context without network access. If execution must inspect bytes and discovers malformed or unsupported content, `enrich` reports the appropriate existing typed result; this does not invalidate discovery.

## Options

Capability options follow the same local, deterministic discovery model. Choices MAY be compiled into the component, derived from package-owned static data, or derived locally from supplied context. Options MUST NOT require a live remote lookup. A component with a dynamic remote catalogue MUST expose a locally defined stable contract suitable for execution, or change its contract in a later component version or capability revision. This protocol does not define remote option discovery.

## Identity and revision

`capability.id` is the stable, opaque, plugin-owned identity of the logical operation. A presentation or options change alone does not create a new operation identity unless the plugin intentionally defines a different operation. Human-readable labels are not identity.

`capability.revision` identifies the advertised configuration and execution contract for that ID. For one ID, the revision MUST change when the accepted or interpreted caller configuration contract changes semantically, including adding/removing an option key, changing requiredness, changing accepted choice values, changing the meaning of an accepted opaque choice value, or incompatibly changing validation/interpretation such that a descriptor/selection pairing becomes ambiguous. Presentation-only changes, including wording of labels and ordering with no plugin-defined semantic meaning, do not require a revision change.

For a given component version and context, the same `(capability-id, capability-revision)` MUST represent one coherent configuration contract. Accepted choice semantics MUST NOT vary with remote state, credentials, account tier, rate limits, or process history. Such execution conditions are reported by `enrich`, not encoded in the revision.

A host/UI MAY cache a descriptor to present choices and later call `enrich` with `capability-id`, `capability-revision`, and selections. The host need not resend the descriptor. `enrich` continues to receive the ID and revision independently, not the complete capability record.

## Execution validation

When `enrich` receives an unknown capability ID, an ID that does not apply to the supplied context, or an unsupported/stale revision, it MUST return `plugin-error.unsupported`. It MUST NOT use `not-found` for protocol capability identity. For a supported ID/revision, structurally invalid caller selections, including an unknown option key, missing required selection, disallowed duplicate, or unsupported choice value, MUST return `plugin-error.invalid-configuration`. A stale revision is not caller configuration failure. These cases do not introduce a new error variant.
