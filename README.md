# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, and compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy.

The current contract is `stashd:plugin@0.15.0`. It describes invocation-scoped
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

Contract 0.10 normalizes genuinely shared plugin protocol primitives from #8:
common progress precision, plugin error detail, invocation logging, HTTP
requests, and staged output, while retaining lifecycle-specific error and
configuration models. Enrichment execution receives capability identity and
revision separately from its advertised descriptor.

Contract 0.11 makes Broadcast content-capable. `broadcast-host.open-asset`
opens bounded reads from an opaque preserved reference as the shared
`io-host.byte-stream`; it never returns a Vault or filesystem path. The shared
HTTP request body is absent or an owned byte stream, so it can carry preserved
Asset bytes or a completed staged artifact reopened with
`io-host.open-staged-artifact`. `run-helper` can likewise take an owned stream
for helper stdin while retaining its optional staged-writer stdout. All of
these paths use the canonical byte-stream and preserve chunked transport for
large objects.

Opening a missing or unauthorized Asset fails with the existing `stream-error`;
read failures use that same typed error and terminate the stream. HTTP reports a
request-body read failure as `body-failed`; the host closes the stream when the
request completes or fails, and the remote destination may have received a
partial body if transport failed after sending began. Helpers report stdin
stream failures as `input-failed`, terminate the helper, and close the stream.
An invocation ending closes any remaining streams and discards unfinished
staged writers. Completed staged artifacts can be reopened only during their
own invocation; only artifacts returned by a successful plugin result become
available to Core.

Contract 0.12 extends the canonical `credential-binding` model to potentially
authenticated Broadcast calls (`prepare`, `publish`, `finalize`, and
`operation`) and Enrichment execution (`enrich`). Each receives a list of
bindings authorized for that invocation, separate from settings, metadata,
capability identity, and Enrichment configuration. A call that needs no
credential receives an empty list. Enrichment imports the existing `http-host`
for remote OCR, translation, transcription, and identification services; it
does not define an Enrichment-specific HTTP client. The shared helper accepts
the same binding type for approved helper-backed work.

Credential reference IDs are opaque selectors, never bearer capabilities. An
ID alone does not authorize access. The host validates each binding against the
current invocation's grants and rechecks authorization and availability when
HTTP or helper access is used. A denied or ungranted credential and a credential
that has become unavailable remain distinct host errors. HTTP authentication
rejection remains distinct from transport failure and from lifecycle plugin
errors. Credential material must not be placed in Broadcast settings,
publication metadata, Enrichment configuration, metadata facets, source or
Asset references, or capability IDs/revisions. HTTP and approved helper
mediation cover these use cases; Broadcast and Enrichment do not receive raw
secret access.

Contract 0.13 makes Broadcast Items generic: an Item contains its stable ID,
concrete Assets, and canonical `plugin-metadata` facets. Assets contain a stable
Asset ID, an opaque host reference, optional media type, byte size, and their
own metadata facets. The host opens Asset bytes only through `open-asset` and
the shared bounded `byte-stream`. Asset `kind`, derivation key, and URL were
removed: they do not have one universal Broadcast meaning, and an Asset need
not have a public URL. Media type and size describe a concrete representation
without classifying its domain. Prepared derived outputs likewise identify
their source through preserved Asset IDs and carry plugin metadata instead of
an output `kind` or provider derivation key.

Broadcast no longer requires Item `source-reference`, `title`, `description`,
`published-at`, or `duration-seconds`. Source provenance belongs to the
preservation model; titles, descriptions, dates, durations, and domain fields
remain available in plugin-owned metadata facets rather than fixed protocol
columns. This includes video/audio, books, wiki revisions, archive items, and
future domains without adding a normalized media schema. Facet schemas can
identify data such as `youtube.video@…`, `podcast.episode@…`,
`books.publication@…`, `mediawiki.revision@…`, or
`internet-archive.item@…`; Core transports their JSON without interpreting it.

A `publication` has an optional staged `artifact`, optional filesystem
`files`, and a list of canonical `destination-metadata` facets. Remote-only
success returns no artifact and can put one or more receipts—such as remote
object IDs, URLs, ETags, infohashes, or destination revisions—in opaque
plugin-owned metadata. Filesystem-relative paths appear only inside the
optional `files` result; no empty path stands for a non-filesystem result.
`published-file` keeps optional Item and Asset IDs for correlation and a
relative path, while removing the provider-specific source reference.

This shape covers generated Podcast feed artifacts with enclosure Assets and
metadata-provided titles/dates; Jellyfin/Plex Asset publication with optional
filesystem or destination records; Internet Archive and S3/WebDAV remote-only
receipts; BitTorrent publication that returns both a local torrent artifact
and destination metadata; OPDS catalogue artifacts built from document
metadata; and arbitrary document/binary Assets without audiovisual fields.

## Broadcast lifecycle (contract 0.14)

`publish(request, credentials)` is the complete publication lifecycle and the
only publication call. A caller may invoke it directly; there is no preceding
`prepare` call and no following `finalize` call. The plugin may select,
transform, package, upload, commit, and perform destination work needed for the
publication before it returns. These are implementation steps within one
invocation, not separate protocol phases. Work that does not need a separate
call is not represented as a fake phase.

If `publish` creates bytes, it uses the shared `io-host` staging area and
`staged-artifact`; Broadcast defines no second prepared-output handle. A
completed staged artifact can be reopened with `open-staged-artifact` only
during the invocation that created it. The plugin can consume it in that call
(for example as an HTTP request body) and return it as `publication.artifact`.
On a successful result the host adopts a returned artifact; an artifact not
returned is discarded when the invocation ends. If the call fails, its staged
outputs are not adopted and are discarded. No later invocation may rely on a
byte-stream, staged-writer, or staged-artifact handle from an earlier call.
Durable destination state is reported separately in
`publication.destination-metadata`, and filesystem-relative paths are only
reported through `publication.files`.

The optional publication fields are independent: local generated output is
`artifact`, filesystem-oriented results may include `files`, and remote-only
publication may return neither while recording receipts in
`destination-metadata`. An empty local artifact or an empty path is not a
placeholder for a remote result.

The former `prepare`, `preparation`, `derived-artifact`, `finalize`, and
`finalization-request` contract is removed. In particular, prepared bytes are
not described by a Broadcast-specific opaque `reference`: that would either
invent a second staging system or require an invocation-only resource to
survive across calls. A plugin that needs intermediate generated bytes stages
and consumes them within `publish`; durable derived Assets belong to the
preservation/Enrichment model, not to a temporary Broadcast preparation
result.

`operation` is an independent, explicitly requested plugin-defined
interactive destination operation. It can inspect or update destination
configuration/state and return choices or values for a caller, but it does not
publish the `publish-request` Items and its result is not publication state.
Operation names and payload meanings are defined by the plugin. Core invokes
it only when a caller requests that named operation; it is not an automatic
publication hook, a discovery method, or a generic substitute for a missing
publication capability. A publication that needs a destination-side commit or
refresh to count as successful performs that work inside `publish`.

Credentials are grants for each individual invocation. A later call must
receive its own authorized credential bindings; destination metadata may
describe durable remote state, but it does not retain credentials or grant
access to an earlier call's streams or staged outputs.

The protocol makes no exactly-once, automatic-retry, or idempotency guarantee.
A failed call can have produced partial external effects, such as a remote
server accepting some uploaded bytes before a transport error. Plugins should
use destination-supported idempotency mechanisms when available and report
retryable errors accurately. Callers own retry policy and must not assume that
repeating a failed call has no duplicate effects.

### Forcing cases

- **Podcast feed:** build the feed and return its staged document from one
  `publish` call; no fake preparation or finalization is needed.
- **Jellyfin/Plex:** read preserved Assets, transform or package them, publish
  files, and perform any required library refresh before `publish` returns.
  Report filesystem paths or destination receipts as applicable.
- **Internet Archive:** stream the authenticated upload and return remote
  receipts in destination metadata; no local artifact is required.
- **BitTorrent:** generate torrent metadata in invocation staging, consume or
  return it, seed/publish as needed, then return the optional artifact and
  destination receipt together.
- **S3/WebDAV:** upload directly from an Asset stream (or a staged stream) and
  return remote object receipts; no preliminary call is required.
- **OPDS:** generate and return a staged catalogue artifact from Item and
  Asset metadata in `publish`.
- **Arbitrary remote API:** perform the API publication and return destination
  metadata only; no filesystem or local artifact is implied.

Contract 0.14 removes Broadcast prepare/finalize wire methods and their
prepared-output records. This is an incompatible WIT shape change and advances
the pre-1.0 contract from 0.13.0 to 0.14.0; it does not change RPC framing,
credential bindings, generic publication results, or shared staging.

Contract 0.15 defines Collection Export as bounded, one-shot interchange. The
collection entries and exported artifact bytes remain inline. Each host MUST
configure and enforce a maximum serialized input-message size, maximum artifact
`contents` byte size, and maximum serialized result-message size that fits its
RPC transport. Message limits include all values and encoding overhead. This
bounds entry count by encoded size without imposing an arbitrary universal
count. The host rejects oversized input before plugin invocation and refuses
oversized output, reporting either as the typed `limit-exceeded` outcome.
Plugins cannot assume arbitrarily large inline lists. `limit-exceeded` is
reserved for the host runtime; plugins must not use it for plugin failures.

Small OPML and similarly sized JSON/XML interchange documents fit this
one-shot contract. Large podcast subscription catalogues, book/document
inventories, and catalogues with tens or hundreds of thousands of entries are
not Collection Export just because they can be encoded as a file: when the goal
is to generate or publish a large catalogue, use Broadcast and its canonical
host-managed streaming/staging primitives. Collection Export adds no progress,
credentials, HTTP, or publication behavior. Adding `limit-exceeded` changes the
WIT variant shape, so the pre-1.0 package identity advances from 0.14.0 to
0.15.0; RPC framing is unchanged.

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
invocation-scoped: plugins may reopen them as streams during that invocation,
and Core adopts them only when returned by a successful plugin result.
Enrichment and Broadcast each open an existing Asset at an offset with an
optional length, then read bounded chunks using the same canonical stream.
Input and Broadcast HTTP responses use the same stream resource; HTTP request
bodies may also consume it. Status, headers, credentials, and generic HTTP
errors remain host mediated.

The shared helper capability receives an optional owned byte stream for stdin
and an optional borrowed staged writer for stdout. The host streams helper
input and output without exposing a mount or path. A plugin can call a helper
once for each output stream when a helper produces multiple files, or copy a
returned byte stream through the same writer API.

## Shared primitive decisions

`plugin-metadata` and `staged-artifact` remain canonical in `io-host`. Input
acquisition and Enrichment derived Assets return the shared staged output
descriptor; Broadcast may return one as an optional local publication
artifact. Collection Export's named inline file result
has a different transport and stays separate. The `progress-host` interface
owns the shared `progress` value (`stage` plus an optional `f64` fraction) and
callback. Input, Broadcast, and Enrichment report the same kind of invocation
progress, so they use the same precision and callback. Collection Export is a
one-shot collection-to-artifact contract with no progress lifecycle; it does
not import `progress-host`.

The `plugin-types` interface owns shared `plugin-error-detail` (`message` and
`retryable`) without merging the separate lifecycle error variants. Every world
uses one `logging-host` message callback for invocation diagnostics.

Input, Broadcast, and Enrichment use the same generic outbound HTTP capability,
request, response stream, transport errors, and opaque credential reference
through `http-host`. Collection Export does not import HTTP. Input,
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
shared progress precision, shared Input/Broadcast/Enrichment HTTP types, shared
plugin error detail, shared logging, revision-aware Enrichment invocation, HTTP
request and response streaming, Broadcast Item/Asset metadata, optional staged
and filesystem publication results, opaque destination receipts, Broadcast
Asset reads, staged-artifact reads, helper stdin, host-granted
Broadcast/Enrichment credentials, Enrichment's shared HTTP import, and staging
invariants. It also proves that the semantic checks reject acquisition-only
credentials, raw credentials in generic Input records, inline-only HTTP request
or response bodies, missing Broadcast Asset streaming, missing helper stdin,
duplicate stream abstractions, missing staged writers, implicit helper staging,
filesystem or Vault paths in content boundaries, credentials outside explicit
lifecycle bindings, an unnecessary second credential type, raw-secret fields
in plugin records, universal Broadcast duration/kind fields, missing Item
metadata facets, mandatory local artifacts or filesystem paths, and receipts
that lose the canonical plugin-metadata representation. It also checks Input
delegation, configuration identity, shared progress precision, HTTP
credentials and errors, Enrichment revision-aware execution, shared plugin
error detail, and logging.
