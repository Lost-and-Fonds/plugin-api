# Generated WIT compatibility report

This file is generated from the active WIT files; it is not a second contract.

| File | Interface | Records | Variants | Enums | Resources | Functions |
|---|---|---:|---:|---:|---:|---:|
| `wit/input.wit` | `input-host` | 8 | 3 | 1 | 2 | 5 |
| `wit/input.wit` | `input-plugin` | 7 | 2 | 1 | 0 | 3 |
| `wit/broadcast.wit` | `broadcast-host` | 6 | 3 | 1 | 2 | 4 |
| `wit/broadcast.wit` | `broadcast-plugin` | 14 | 2 | 0 | 0 | 4 |
| `wit/collection-export.wit` | `collection-export-host` | 0 | 0 | 0 | 0 | 1 |
| `wit/collection-export.wit` | `collection-export-plugin` | 5 | 2 | 0 | 0 | 1 |

## Component worlds

The plugin-package schema lists canonical WIT worlds as the available component implementations:

| World | Imports | Exports |
|---|---|---|
| `input-world` | `input-host` | `input-plugin` |
| `broadcast-world` | `broadcast-host` | `broadcast-plugin` |
| `collection-export-world` | `collection-export-host` | `collection-export-plugin` |

## Native mapping

- scalar values map to JSON scalars;
- records map to JSON objects with required fields and nullable option fields;
- lists map to JSON arrays;
- enums map to strings;
- variants map to `{"tag": string, "value": value}` when a payload exists;
- results map to exactly one of `{"ok": value}` or `{"error": value}`;
- Component resources remain opaque invocation-scoped references; no ABI object is generated.

RPC v1 represents inline list<u8> values as JSON arrays of unsigned byte values. The generated schema has no Wasmtime or Component ABI dependency.
