# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, and compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy.

The current contract is `stashd:plugin@0.5.0`. It describes invocation-scoped
host capabilities for Input, Broadcast, Enrichment, and collection-export lifecycles. RPC
v1 remains the native transport: four-byte big-endian length followed by a
UTF-8 JSON object. Inline `list<u8>` values map to JSON arrays of unsigned byte
values.

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
The host controls reads of existing Asset bytes and adopts staged outputs only
when an enrichment result succeeds.

Contract 0.4 added this package-level component model without changing the
existing lifecycle interfaces. Consumers of the former single-role package
manifest need a downstream migration to the identified `components` object.
Contract 0.5 adds the Enrichment world; the package manifest keeps the same
shape and can select `enrichment-world` as a component world.

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

Collection exporters receive generic collection metadata, entries, and options,
and return a named media artifact or a typed plugin error.

## Verify the contract

Enrichment is not acquisition: Inputs discover and acquire material into
Stashd. It is not Broadcast: Broadcasts select, transform, package, or publish
material as outputs. Enrichment operates on already preserved Item/Asset
context and may add metadata or preservation Assets to the Vault.

Run `./bin/verify-contract` with Python 3 and `wasm-tools` 1.225.0 available on
`PATH`. It parses the complete WIT package, checks generated artifacts for
freshness and determinism, verifies package/world identity, checks package
component discovery against the declared WIT worlds, and enforces generic
Input and Enrichment invariants.
