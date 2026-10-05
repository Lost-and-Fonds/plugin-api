# Input source routing and lifecycle

This working contract change retains the declared package version for review; it is not a published compatibility target. Canonical WIT is authoritative. No compatibility aliases exist for the former delegation API.

## Canonical source

`input-host.source` contains exactly `reference: option<string>` and `values: list<source-value>`. `source-value` contains a plugin-defined `key` and typed `option-value` (`boolean`, `number`, or `text`). These shared types live at the discovery boundary and are reused by `input-plugin`.

A plain discovered reference MUST be representable as `{reference: some(reference), values: []}` without knowing a target plugin or its option schema. Directly configured sources MAY use that identical representation, plugin-defined values with no reference, or both. The receiving Input defines how source contents are understood, including conflicts between reference and values. An empty source is structurally valid; an Input MAY decline it. Core MUST NOT interpret plugin-defined source values or convert references into plugin-specific configuration. Secrets and credential bindings MUST NOT be embedded in sources.

`discovered-item.source: option<source>` requests that the Item be handled as another Input source. `none` makes no such request; the Item's ordinary opaque `reference` remains its independent acquisition reference. The source reference need not equal the Item reference. An upstream Input MUST NOT identify a target plugin or need its source-value schema merely to emit a discovered reference. There are no provider IDs or provider/media taxonomy fields.

## Capability probe

`can-resolve(source: source) -> bool` answers only whether this Input understands this source well enough for Core to route it here. It MUST be cheap, deterministic for the same source and immutable plugin configuration/package, and independent of mutable process-local state. It MUST NOT resolve the source, mutate host/plugin state, perform network discovery or other expensive discovery, require/access credentials, create resources, stage data, call helpers, or perform acquisition. It MUST NOT call imported host capabilities. A true result is not a guarantee of successful resolution or remote availability. False is an ordinary boolean response, not a typed lifecycle error.

The probe uses the ordinary component startup, invocation envelope, and boolean RPC encoding. Startup/transport/protocol failures remain execution failures, not false or synthesized `plugin-error` results. Core MUST NOT run normal resolution as a capability probe. `unsupported` from `resolve` is a normal selected-Input lifecycle failure, not a routing signal; Core MUST NOT use it to probe/fall through to another Input.

## Routing and one resolution lifecycle

Core MUST pass the same canonical source value unchanged to `can-resolve` and the selected Input's `resolve(source, credentials)`. Directly supplied, discovered, restored, and future workflow sources all use this one resolution lifecycle. The receiving Input MUST NOT require source provenance or a separate delegated-source path. Normal resolution may use the host capabilities permitted for Inputs and returns `resolved-input` or the normal typed `plugin-error`.

For an Input A discovering a source, Core MUST retain A's package/component identity and discovering Item identity/relationship as provenance before routing. Core asks candidate Inputs `can-resolve(source)`, selects an accepting Input B, and calls B's ordinary `resolve` with that same source and B's authorized credentials. B then uses normal independent discover/acquire invocations. Provenance MUST remain Core-owned and MUST NOT be injected into B's source or resolution request. Core MUST preserve the discovering relationship even if routing fails or the downstream Input already exists.

If no installed Input accepts, Core can report that no suitable Input is available. Selection among multiple true responses is Core policy. Cycle/repeat detection and hop limits remain Core policy using package/component/Item provenance, not receiving-plugin API state. This contract does not specify a ranking, target-plugin selector, or new persistence API.

## Forcing cases

All references below stand for the exact original source string, not a Core-parsed URL or provider-specific option key. In every accepted case the probe and resolve arguments are `{reference: some(original-reference), values: []}`.

| Source origin | Candidate acceptance | Normal lifecycle |
| --- | --- | --- |
| RSS discovers an HTTP URL | HTTP Input accepts | HTTP Input `resolve(source, credentials)` |
| RSS discovers a YouTube URL | YouTube Input accepts | YouTube Input `resolve(source, credentials)` |
| RSS discovers a magnet URI / BitTorrent reference | BitTorrent Input accepts | BitTorrent Input `resolve(source, credentials)` |
| OPDS discovers an HTTP publication | HTTP Input accepts | HTTP Input `resolve(source, credentials)` |
| Generic feed discovers an unknown source | All installed Inputs decline | No suitable Input; provenance retained |
| User directly adds the same YouTube URL | YouTube Input accepts | Exactly the same source argument as the RSS case |

The YouTube Input cannot distinguish direct and cross-Input origin from the resolution request and does not need `if delegated` behavior. Real differences in source contents may affect plugin behavior; provenance does not. Opaque values-only configured sources remain supported without Core parsing them.

## Wire shapes and rejection

RPC v1 uses `stashd:plugin/input-plugin.can-resolve` with `params: {"source": {"reference": "opaque-reference", "values": []}}` and a bare `result: true` or `result: false`. `stashd:plugin/input-plugin.resolve` uses that same `source` plus `credentials`, and its result is the ordinary WIT resolution result. The optional discovered Item field is `source`, encoded as null or that same source record.

The unknown `resolve-delegation` method, `input-delegation` type, discovered Item `delegation` field, raw-string probe/resolve arguments, and old list-only resolve source are invalid under this WIT contract and MUST be rejected before dispatch. These are incompatible working API changes, not aliases or a released version migration. Package worlds, RPC framing, and unrelated lifecycle contracts are unchanged.
