# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, and compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy.

The current contract is `stashd:plugin@0.2.0`. It describes invocation-scoped
host capabilities for Input, Broadcast, and collection-export lifecycles. RPC
v1 remains the native transport: four-byte big-endian length followed by a
UTF-8 JSON object. Inline `list<u8>` values map to JSON arrays of unsigned byte
values.

The 0.2 contract makes the generic HTTP request shape and typed plugin errors
explicit. Core accepts 0.1 manifests during migration, but new plugins should
declare 0.2 and use the current SDK. Input acquisition may request a subset of
generic artifact roles; the result can report a role as temporarily or
permanently unavailable without implying that an existing Vault Asset should
be removed. Collection exporters receive generic collection metadata, entries,
and options, and return a named media artifact or a typed plugin error.

## Verify the contract

Run `./bin/verify-contract` with Python 3 and `wasm-tools` 1.225.0 available on
`PATH`. It validates the complete WIT package, checks generated artifacts for
freshness and determinism, and verifies the three lifecycle world mappings.
