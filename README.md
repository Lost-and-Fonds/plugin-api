# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, and compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy.

The current contract is `stashd:plugin@0.3.0`. It describes invocation-scoped
host capabilities for Input, Broadcast, and collection-export lifecycles. RPC
v1 remains the native transport: four-byte big-endian length followed by a
UTF-8 JSON object. Inline `list<u8>` values map to JSON arrays of unsigned byte
values.

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

Run `./bin/verify-contract` with Python 3 and `wasm-tools` 1.225.0 available on
`PATH`. It validates the complete WIT package, checks generated artifacts for
freshness and determinism, and verifies the three lifecycle world mappings.
