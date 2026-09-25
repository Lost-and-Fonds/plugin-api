# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, and compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy.

The current contract is `stashd:plugin@0.9.0`. It describes invocation-scoped
host capabilities for Input, Broadcast, Enrichment, and collection-export
lifecycles. RPC v1 remains the native transport: four-byte big-endian length
followed by a UTF-8 JSON object. Large byte streams use opaque host resources;
each read returns at most a host-configured chunk as `list<u8>`, and writes
append chunks no larger than the host-configured limit. A whole large object is
never an inline byte list on these streaming paths.

The generated `schema/plugin-package.schema.json` defines one deployable
package identity (`id` and `version`) with a `components` object keyed by stable
component IDs. Each component declares a canonical WIT `world` and a
package-relative `artifact`. Multiple component IDs may declare the same world.
The allowed world values are generated from this package's WIT declarations;
the manifest selects those worlds and cannot add new ones. Package tooling can
validate each artifact against its declared world. Input, Broadcast,
Enrichment, and Collection Export keep their separate interfaces and
lifecycles. Enrichment inspects generic Item/Asset context, reports applicable
plugin-owned capabilities, and returns opaque metadata facets and/or durable
derived Assets with source Asset IDs and plugin activity/version provenance.
Capability `id` and `revision` identify the operation and its evolution. Each
capability also advertises zero or more generic configuration options. An
option has a stable plugin-owned key, a display label, a required flag, and
accepted choices represented as opaque string values with display labels. An
empty option list represents a fixed operation. Callers return selected key
and value pairs to `enrich` with the advertised capability's stable ID and
revision. Plugins validate them against that revision and report invalid
selections with `invalid-configuration`; the host
transports the descriptors and values without interpreting their meaning.
Plugins should change the capability revision when its accepted configuration
contract changes incompatibly, and callers should submit selections for the
revision they advertised. The host controls reads of existing Asset bytes and
adopts staged outputs only when an enrichment result succeeds.

This model covers optional OCR language (omit the optional selection to use
the plugin default), required subtitle target language, independent
transcription mode and model choices, artwork mode, a fixed
metadata-identification operation with no options, and capabilities with
multiple independent settings. Domain terms and values remain plugin owned;
the universal contract defines only keys, labels, required choices, and string
selections.

Contract 0.4 added this package-level component model without changing the
existing lifecycle interfaces. Consumers of the former single-role package
manifest need a downstream migration to the identified `components` object.
Contract 0.5 added the Enrichment world; contract 0.7 adds shared host-managed
streaming and staged writing. The package manifest keeps the same shape and
can select each canonical component world.

Contract 0.8 gives Input credentials one host-managed model across `resolve`,
`resolve-delegation`, `discover`, and `acquire`. Each call receives named,
plugin-defined bindings to opaque host credential references. A binding name
identifies the plugin's configured slot; Core treats both it and the reference
as opaque. References are not secrets and do not belong in source values,
options, metadata, or delegation records. The host grants only references
authorized for that invocation and checks availability when access is opened,
so a credential revoked after discovery can be unavailable during acquisition.

Contract 0.9 adds generic Enrichment configuration descriptors and a separate
caller-selection argument to `enrich`. Capability IDs and revisions remain
separate from selected values.

Inputs can select the same reference on `http-request`; the HTTP host applies
it without exposing secret material to the plugin. `run-helper` accepts the
same bindings and supplies selected credentials to the helper as named
environment variables without putting them in helper arguments or plugin
memory. For protocol clients that cannot use host-mediated HTTP or helper
access, the Input host can open an invocation-scoped `credential-access` resource.
Reading it exposes the raw secret to the plugin and should be limited to those
clients. Denial and unavailable credentials have separate host errors; HTTP
authentication rejection and the Input `authentication` error remain distinct
from those access failures.

The binding travels with each phase that may need authentication: bucket or
remote path resolution and listing use it during resolve/discover; acquisition
receives the same model again and the host can deny or report an unavailable
reference if it was revoked since discovery. HTTP sources use it on each
request, delegated references can be resolved with it, and helper-backed
discovery passes it to the helper without first acquiring content. S3, SFTP,
WebDAV, private HTTP/API, and arbitrary host-approved helpers therefore share
this boundary without a provider-specific credential schema.

Input, Broadcast, and Enrichment import the shared `io-host` interface. Its
invocation-scoped streams keep the host in control of Asset access and staging.
Plugins open staging, create a writer, append byte chunks, and call `finish` to
receive the canonical `staged-artifact` descriptor. A writer dropped before
`finish`, or whose invocation ends, is discarded. The host tracks size and
keeps output unpublished until finalization succeeds. Completed artifacts stay
invocation-scoped and are available to the host only when returned by a
successful plugin result; other output is discarded. Enrichment can open an
existing Asset at an offset with an optional length, then read bounded chunks.
Input and Broadcast HTTP responses use the same stream resource; status,
headers, and generic HTTP errors remain host mediated.

The shared helper capability receives an optional borrowed staged writer
explicitly. The host can stream helper stdout into that writer without exposing
a mount or path. A plugin can call a helper once for each output stream when a
helper produces multiple files, or copy a returned byte stream through the
same writer API.

## Shared primitive decisions

`plugin-metadata` and `staged-artifact` remain canonical in `io-host`. Input
acquisition, Broadcast publication, and Enrichment derived Assets return the
same staged output descriptor. Collection Export's named inline file result
has a different transport and stays separate. The `progress-host` interface
owns the shared `progress` value (`stage` plus an optional `f64` fraction) and
callback. Input, Broadcast, and Enrichment report the same kind of invocation
progress, so they use the same precision and callback. Collection Export is a
one-shot collection-to-artifact contract with no progress lifecycle; it does
not import `progress-host`.

The `plugin-types` interface owns shared `plugin-error-detail` (`message` and
`retryable`) without merging the separate lifecycle error variants. Every world
uses one `logging-host` message callback for invocation diagnostics.

Input and Broadcast use the same generic outbound HTTP capability, request,
response stream, transport errors, and opaque credential reference through
`http-host`. Enrichment and Collection Export do not import HTTP. Input,
Broadcast, Enrichment, and Collection Export share only plugin error detail;
each retains its own `plugin-error` cases because unsupported operations,
configuration validation, credential outcomes, and lifecycle failures differ.

The repeated option/value shapes remain separate. Input source values and
acquisition options configure a source or plugin; Broadcast settings and
operation choices configure interactive runtime work and publication; Enrichment
advertises capability-specific caller selections using string values and
revisions. Collection Export settings configure one export. Their similar
field layouts do not give them one semantic contract or one future SDK type.
Likewise Broadcast's `choice` and Enrichment's `configuration-choice` are
separate because one describes an interactive operation result and the other
describes accepted invocation configuration.

Enrichment discovery returns the full capability descriptor for host and UI
use. Invocation receives only `capability-id`, `capability-revision`, and the
caller's selections alongside Item/Asset context. This preserves
revision-aware execution without making presentation labels and advertised
option descriptors part of the plugin's execution input.

The Input contract describes opaque plugin-owned source and Item references,
generic byte sizes, and staged artifact descriptors (reference, media type, and
byte size). It does not require a URL, audiovisual media kind, title, duration,
artwork, or fixed Asset role. Provider and domain fields belong in
plugin-owned metadata facets: each facet carries a stable versioned schema
identifier and a JSON object, which Core treats as opaque. The HTTP capability
is available to Inputs that need it; it is not part of every Input's identity.
Core uses opaque IDs and references to connect lifecycle records, byte estimates
for storage decisions, and staged descriptors to ingest content and calculate
fixity. It does not infer domain meaning from plugin metadata.

An Input can attach an optional `input-delegation` to a discovered item. It
contains only the opaque reference another Input should resolve; keeping it on
the discovered item preserves the discovering Input and item as provenance.
Core routes the reference by probing installed Inputs through
`resolve-delegation`. A receiving Input returns its normal `resolved-input` or
the typed `unsupported` error. Core does not parse references or need a
provider taxonomy. Package and component IDs identify each Input in a
delegation chain, while discovered item IDs retain the handoff context, so
Core can detect repeats or bound a chain later.

Core routing and cycle bounds, SDK support for the new field and resolver,
and provider implementations such as Generic Feeds remain downstream work.

Collection exporters receive generic collection metadata, entries, and options,
and return a named media artifact or a typed plugin error. Their lifecycle does
not define progress reporting.

## Verify the contract

Enrichment is not acquisition: Inputs discover and acquire material into
Stashd. It is not Broadcast: Broadcasts select, transform, package, or publish
material as outputs. Enrichment operates on already preserved Item/Asset
context and may add metadata or preservation Assets to the Vault.

Run `./bin/verify-contract` with Python 3 and `wasm-tools` 1.225.0 available on
`PATH`. It parses the complete WIT package, checks generated artifacts for
freshness and determinism, verifies package/world identity, checks package
component discovery against the declared WIT worlds, and enforces generic
Input credential lifecycle access, explicit generic Enrichment configuration,
shared progress precision, shared Input/Broadcast HTTP types, shared plugin
error detail, shared logging, revision-aware Enrichment invocation, HTTP
streaming, and staging invariants. It also proves that the semantic checks
reject acquisition-only credentials, raw credentials in generic Input records,
inline-only HTTP bodies, missing staged writers, implicit helper staging,
filesystem paths in staging, Input delegation regressions, configuration
encoded into capability identity, split shared progress precision, a raw HTTP
credential, missing capability revision, the discovery descriptor passed to
Enrichment execution, duplicated plugin error detail, and removal of the
Enrichment invocation configuration boundary, plus missing shared logging.
