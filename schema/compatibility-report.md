# Generated WIT compatibility report

This file is generated from the active WIT files; it is not a second contract.

| File | Interface | Records | Variants | Enums | Resources | Functions |
|---|---|---:|---:|---:|---:|---:|
| `wit/input.wit` | `input-host` | 6 | 1 | 1 | 1 | 4 |
| `wit/input.wit` | `input-plugin` | 7 | 2 | 1 | 0 | 4 |
| `wit/broadcast.wit` | `broadcast-host` | 4 | 1 | 1 | 1 | 3 |
| `wit/broadcast.wit` | `broadcast-plugin` | 14 | 2 | 0 | 0 | 4 |
| `wit/enrichment.wit` | `enrichment-host` | 2 | 1 | 0 | 0 | 3 |
| `wit/enrichment.wit` | `enrichment-plugin` | 4 | 1 | 0 | 0 | 2 |
| `wit/collection-export.wit` | `collection-export-host` | 0 | 0 | 0 | 0 | 1 |
| `wit/collection-export.wit` | `collection-export-plugin` | 5 | 2 | 0 | 0 | 1 |
| `wit/io.wit` | `io-host` | 3 | 3 | 0 | 3 | 2 |

## Component worlds

The plugin-package schema lists canonical WIT worlds as the available component implementations:

| World | Imports | Exports |
|---|---|---|
| `input-world` | `io-host`, `input-host` | `input-plugin` |
| `broadcast-world` | `io-host`, `broadcast-host` | `broadcast-plugin` |
| `enrichment-world` | `io-host`, `enrichment-host` | `enrichment-plugin` |
| `collection-export-world` | `collection-export-host` | `collection-export-plugin` |

## Native mapping

- scalar values map to JSON scalars;
- records map to JSON objects with required fields and nullable option fields;
- lists map to JSON arrays;
- enums map to strings;
- variants map to `{"tag": string, "value": value}` when a payload exists;
- results map to exactly one of `{"ok": value}` or `{"error": value}`;
- Component resources remain opaque invocation-scoped references; no ABI object is generated.

RPC v1 represents resource handles as opaque invocation-scoped references and byte chunks as JSON arrays of unsigned byte values. Large input and output objects using io-host are transported as bounded chunks, never in one RPC object. The generated schema has no Wasmtime or Component ABI dependency.
