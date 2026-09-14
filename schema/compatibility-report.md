# Generated M3 WIT compatibility report

This file is generated from the active WIT files; it is not a second contract.

| File | Interface | Records | Variants | Enums | Resources | Functions |
|---|---|---:|---:|---:|---:|---:|
| `wit/input.wit` | `input-host` | 7 | 3 | 2 | 2 | 5 |
| `wit/input.wit` | `input-plugin` | 8 | 2 | 2 | 0 | 3 |
| `wit/broadcast.wit` | `broadcast-host` | 6 | 3 | 1 | 2 | 4 |
| `wit/broadcast.wit` | `broadcast-plugin` | 14 | 2 | 0 | 0 | 4 |

## Native mapping

- scalar values map to JSON scalars;
- records map to JSON objects with required fields and nullable option fields;
- lists map to JSON arrays;
- enums map to strings;
- variants map to `{"tag": string, "value": value}` when a payload exists;
- results map to exactly one of `{"ok": value}` or `{"error": value}`;
- Component resources remain opaque invocation-scoped references; no ABI object is generated.

RPC v1 represents inline list<u8> values as JSON strings because the current host transports PHP byte strings directly; resource.read chunks use base64 and large response bodies use opaque resource handles. The generated schema has no Wasmtime or Component ABI dependency.
