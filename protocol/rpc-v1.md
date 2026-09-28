# RPC v1

This document is the normative native wire mapping for the WIT package in this
repository. WIT defines operations and ownership; RPC v1 only transports them.
This is not a Component Model ABI and does not add operations to WIT. Process
launch and stdin/stdout/stderr binding are normatively defined in
[Component execution](component-execution.md).

## Framing and call model

Each frame is a four-byte unsigned big-endian byte length followed by exactly
that many bytes of UTF-8 JSON. The JSON text MUST decode to one object. The
length counts encoded JSON bytes, not characters. Endpoints MUST enforce a
configured maximum frame size before allocating or decoding the payload. A
truncated header or payload, invalid UTF-8/JSON, non-object JSON, zero/oversize
length, or invalid envelope is a protocol failure. The four-byte length itself
is the transport frame limit; an endpoint MUST also reject an otherwise valid
JSON message that exceeds the WIT operation's configured byte or output limit.

After startup, every lifecycle frame has `protocol: 1`, a non-empty string
`id`, `kind`, and the active string `invocation`. A request has
`kind: "request"`, a canonical WIT `method`, and an object `params`; a response
has `kind: "response"` and MUST contain `result`. `id` is an opaque
correlation token that MUST NOT be reused during the invocation. A response
MUST echo both `id` and `invocation`. `result` is the WIT return value, including
ordinary typed `result<ok, error>` values encoded inside it. A top-level `error`
field is invalid. Envelope fields not defined for the frame kind are invalid.

For every newly launched process, the plugin's first stdout frame MUST be a
`hello` request with `protocol: 1`, `kind: "request"`, `method: "hello"`, and
`params: {"min":1,"max":1}`; it has no invocation. The host responds to the
same ID with `result: {"protocol":1,"min":1,"max":1}`. Only after successful
hello validation and response may the host start one exported lifecycle call. Its `method` is the
package-qualified WIT interface and function, for example
`stashd:plugin/input-plugin.acquire`; `params` is the record of named WIT
arguments. Imported functions and resource methods use the same method form,
for example `stashd:plugin/http-host.open-http-client` and
`stashd:plugin/io-host.byte-stream.read`. A resource method carries its
receiver in `params.self` and uses interface, resource, then method in the
qualified name, for example
`stashd:plugin/http-host.http-client.request`.

There is one active lifecycle invocation per plugin process and no pipelined
calls. While waiting for the lifecycle response, the host MUST continue
receiving and servicing plugin-originated imported-function/resource requests.
The plugin waits for each such response before issuing its next request. The
host's lifecycle request and the plugin's capability request can therefore be
outstanding together, with distinct IDs. Each endpoint returns the response
that matches the request ID it is servicing; neither endpoint may treat the
next frame as necessarily answering its own most recent request. This bounded
re-entrant request/response model is sufficient for callbacks and resource
operations and does not permit arbitrary concurrent asynchronous calls.

Calls and responses for one invocation preserve stream order. A receiver MUST
reject duplicate live IDs, unmatched/duplicate responses, out-of-order or
wrong-invocation responses, and requests from the wrong direction as protocol
failures. On protocol failure, the failing endpoint MUST treat the channel and
process as unusable, fail the active lifecycle if one exists, and invalidate
invocation-scoped resources. It MUST NOT continue with later frames or translate
the failure into a lifecycle `plugin-error`. Unknown WIT functions/methods, invalid resource operations,
unknown/stale handles, wrong resource types, ownership violations, malformed
typed values, and over-limit messages are protocol failures. A valid WIT
`result<ok,error>` is instead returned in `result` and is not a protocol error.

## JSON values

WIT values have these JSON encodings:

| WIT type | JSON |
|---|---|
| `bool`, `string` | JSON boolean, string |
| `u8`, `u16`, `u32`, `s8`, `s16`, `s32` | JSON integer number in the exact WIT range |
| `u64`, `s64` | Canonical base-10 JSON string: `0` or an optional `-` followed by a non-zero digit and digits; no `+`, leading zero, decimal point, or exponent. The value MUST be in the WIT range. |
| `f32`, `f64` | Finite JSON number in range; NaN and infinities are invalid |
| unit (`()`, WIT `_`) | JSON `null` |
| record | Object with every declared field exactly once; unknown fields are invalid |
| list | JSON array in WIT order |
| `option<T>` | `null` for `none`, otherwise the encoding of `T` |
| enum | The exact kebab-case WIT case name as a JSON string |
| payloadless variant case | The exact kebab-case case name as a JSON string |
| payload-bearing variant | `{"tag":"case","value":VALUE}` with exactly those two fields |
| `result<T,E>` | Exactly `{"ok":VALUE}` or `{"error":VALUE}` |
| resource | The resource-handle object defined below |

JSON object key order is insignificant. Strings are Unicode scalar sequences
encoded as UTF-8; lone surrogate values are invalid. Integers MUST be range
checked, not rounded or routed through IEEE-754 binary64. In particular, the
string representation for `u64` and `s64` is required even when a particular
runtime has exact JSON integer support.

Every `list<u8>` is a JSON array of integer numbers from 0 through 255,
inclusive. This applies equally to inline values and each bounded stream chunk.
Base64, byte strings, and implementation-specific binary values are not RPC v1
encodings. A stream read returns `{"ok":null}` at EOF or
`{"ok":[byte,...]}` for a chunk. Empty arrays are not EOF. A write receives an
array and validates every byte before appending any of them.

For the shared `http-host` request record, `method` is a non-empty HTTP method
token. It MUST consist only of ASCII `tchar` characters:
`!#$%&'*+-.^_`|~`, digits, and letters. The host MUST reject whitespace,
control characters, non-ASCII characters, an empty token, and any other value
as a protocol failure before making a request; it MUST NOT dispatch the request
or translate invalid syntax into a plugin-authored `http-error` result. The rule is open-ended
and therefore covers standard methods, WebDAV methods such as `PROPFIND`,
`MKCOL`, `MOVE`, and `COPY`, and extension methods without a WIT enum update.
HTTP header names and values continue to use the existing `http-header` list;
conditional and range headers do not acquire method- or provider-specific
fields, and the host applies normal HTTP header validation.

Redirect following is host/runtime policy, not a language SDK default and not a
plugin-controlled URL/security bypass. A host MUST document whether it follows
redirects, its hop limit and URL policy, and what happens on a disallowed or
invalid target. For every followed hop it MUST re-evaluate URL policy and the
invocation's credential grant. It MUST NOT forward an opaque credential
reference to a new authority unless that policy explicitly permits it. A
request body may be replayed on a redirect only when the host can safely
replay the invocation-scoped stream; otherwise the host returns a typed
`body-failed` or `failed` HTTP error rather than silently dropping or replaying
it. The host's redirect choice and policy outcome are not inferred from a
client-library default. A host that follows a redirect MUST preserve the
request method and headers unless its documented policy explicitly changes
those values for the redirect status; such a policy MUST not silently remove
credential or conditional/range semantics.

## Resource handles

A resource value is exactly:

```json
{"$resource":{"type":"stashd:plugin/io-host.byte-stream","id":"opaque-id"}}
```

The outer object MUST contain only `$resource`; the nested object MUST contain
only `type` and `id`, both strings. `type` is the package-qualified WIT
interface and resource name, not a host language class name. `id` is an opaque,
non-empty string. `$resource` is a reserved single-key marker, so a resource
cannot be confused with an application string or ordinary record. This object
may occur wherever the WIT type admits a resource, including inside options,
lists, results, variants, and nested records. Its actual type MUST match the
WIT position.

The endpoint that creates a resource allocates its ID. IDs MUST be unique
across every resource in that invocation, MUST NOT be reused during the
invocation, and MUST be tracked with the declared WIT resource type. The
current owner keeps the active entry. When an owned WIT value is transferred,
the sender atomically marks its entry transferred and the receiver installs the
same ID and type as its active entry; only the receiver can then use or drop
that handle. A receiver MUST NOT resolve a transferred handle before installing
that entry, and an endpoint MUST reject a handle that is not in its current
owner table. Resource creation and ownership transfer are therefore explicit
state changes, not shared object identity.

IDs SHOULD be unpredictable, but are not bearer authority: possession or
guessing never bypasses the invocation, direction, grant, type, liveness, and
ownership checks. IDs reveal no address, path, secret, object identity, or
storage detail. For current WIT imports, the host creates the capability
resources and their IDs; a future resource is allocated by whichever endpoint
implements its WIT resource constructor.

The host assigns a fresh, opaque `invocation` ID to each lifecycle call. Every
call, response, resource handle and callback for that call uses that same ID.
The host MUST reject a handle used with any other invocation, even if its text
matches an active ID there. At invocation end, all IDs become stale and no
cleanup request is required or permitted after the lifecycle channel closes.
An endpoint MUST reject a stale, replayed, unknown, dropped, or
transferred-away handle deterministically; it MUST never resolve it against
another invocation or host object.

## Ownership, borrowing, and release

Ownership is determined only by the WIT signature. There is no second ownership
flag in JSON:

- An owned `resource T` value is encoded as the handle object above. Returning
  it gives ownership to the receiving endpoint. Passing it to an owned WIT
  parameter transfers ownership and consumes the sender's usable handle.
- `borrow<T>` uses the same handle shape at a WIT position whose signature says
  `borrow<T>`. It grants access only for that call. The receiver MUST NOT retain
  it, return it as owned, transfer it onward as owned, or release it. After the
  call's response, the borrow is invalid; the original owner retains its handle.
- A resource method receiver is an implicit borrow of `self`. A method does not
  consume its receiver unless the WIT signature explicitly says otherwise.
- Ownership rules apply recursively to resource values nested in records,
  variants, options, results, and lists. An owned nested value transfers just
  as an owned top-level argument does; a nested borrow remains call-scoped.

The receiver validates all resource positions and ownership before dispatch.
Once it has received and validated the complete request frame, owned arguments
are consumed by the sender and installed at the receiver before dispatch,
even if the WIT operation returns a valid error result. A successful dispatch
may return ownership in its WIT result. If transport or dispatch fails after
the complete frame was accepted, ownership does not revert: the sender MUST
NOT retry or reuse those handles. The endpoint MUST fail the invocation and
clean up all of its remaining resources when the outcome is uncertain. If the
complete frame was not accepted, no transfer was committed; a broken channel
still ends the invocation, so no handle can be reused in a later invocation.

WIT resource destruction is explicit on RPC v1. The owner sends a normal
correlated request with `method: "stashd:plugin/rpc.resource-drop"` and
`params: {"resource": HANDLE}`; the receiver responds with `result: null` after
releasing it. The receiver invalidates the ID before performing cleanup, so a
cleanup failure cannot make the resource usable again. Duplicate drop, drop of
a borrowed/transferred handle, and drop of an unknown, wrong-type, or stale
handle are protocol failures. A borrowed handle is never separately dropped.
Invocation end is unconditional cleanup: each endpoint releases every owned
resource it created or accepted, invalidates every handle, closes streams,
discards unfinished staged writers, and discards unadopted invocation output.
Garbage collection is not a release mechanism. Staged artifact descriptor
authority, writer finalization, and all-or-nothing successful-result adoption
are specified in [Staged artifact descriptor authority](staging.md).

## Broadcast collection resource

`broadcast-plugin.publish` receives the host-created owned
`broadcast-host.item-collection` handle in its request. The resource method
`item-collection.next` uses the normal correlated method call with an implicit
borrowed `self`; ownership is not consumed by reads. Its `max-items` argument
bounds each `some(non-empty Item list)` result. `none` is collection EOF. The
handle is valid only in that publication's invocation, may be explicitly
released with `rpc.resource-drop`, and is invalidated and cleaned up at
invocation end. The Broadcast collection contract specifies membership,
read-error, and successful-exhaustion requirements.

## Collection Export host result

Collection Export's WIT `plugin-error.limit-exceeded` is reserved for the host.
If the serialized request exceeds the host's configured request limit, the host
does not invoke the plugin and returns the ordinary lifecycle response whose
WIT `result` is `{"error":{"tag":"limit-exceeded","value":DETAIL}}`.
If the plugin returns artifact bytes or a serialized result exceeding the
configured artifact/result limit, the host rejects that output and returns the
same synthesized WIT result instead. `DETAIL` is the canonical
`plugin-error-detail` record. Thus the lifecycle result is a valid WIT outcome;
it is not the response envelope's top-level RPC `error`.

A plugin MUST NOT return `limit-exceeded`. If it does, the host rejects the
plugin's lifecycle response as a contract violation, fails the invocation, and
reports a protocol/contract failure out of band; it MUST NOT accept or relay the
reserved case as a plugin-authored lifecycle result. The host-synthesized case
is permitted only when the host itself rejected the request or output for the
configured limit, and the host MUST NOT synthesize it for a plugin-authored
failure. SDKs can consequently distinguish host synthesis from a plugin
outcome without guessing from error text or direction.

## Conformance flows

The companion `rpc-v1-vectors.json` contains language-neutral value and message
examples. These sequences show the required call/lifetime behavior; symbolic
IDs are examples only.

### HTTP response stream

The plugin calls `http-host.open-http-client` and receives an owned
`http-client` handle. It calls `http-client.request` with that handle as
`self`. The host returns an `http-response` record whose `body` is an owned
`byte-stream` handle. The plugin calls `byte-stream.read` repeatedly; each
response is a bounded `list<u8>` or `null` at EOF. It then sends explicit drop
for the stream and client. Each callback is correlated independently while the
host lifecycle request remains outstanding.

### HTTP request body ownership

The host returns an owned `byte-stream` from `broadcast-host.open-asset` (or an
equivalent WIT constructor). The plugin nests that handle at
`http-request.body`, then passes the request to `http-client.request`. The
owned option transfers the stream to the host and invalidates the plugin's
handle as soon as that complete call frame is accepted. The host reads until
EOF or request failure, then releases it. A `none` body has no handle.

### Staging

The plugin calls `io-host.open-staging-area`, then `staging-area.create` to
receive an owned `staged-writer`. It makes two `staged-writer.write` calls with
bounded unsigned-byte arrays and calls `finish`. The result contains a
`staged-artifact` record (not a resource handle). It drops the writer and
staging-area handles. Invocation end discards any unfinished writer and any
completed artifact not accepted from a successful lifecycle result.

### Borrowed helper output

The plugin owns a `staged-writer` and passes its handle at the
`option<borrow<staged-writer>>` position in `run-helper`. The host uses it only
for that helper call. When the response arrives, the borrow expires and the
plugin still owns the writer and can call `finish`; the host cannot retain or
drop the borrowed writer.

### Raw Input credential

The plugin calls `input-host.open-credential` with an invocation-granted
`credential-reference`, receives an owned `credential-access` resource, and
calls `credential-access.read`. The raw secret is returned only as the WIT
result. The plugin explicitly drops the handle; invocation end also invalidates
and closes it. A retained ID grants no access in a later invocation.

### Re-entrant lifecycle callback

The host sends the lifecycle request with ID `host-1` and invocation `inv-1`.
While handling it, the plugin sends an imported function or resource request
with ID `plugin-1` and the same invocation. The host services that request and
responds to `plugin-1`; the plugin resumes and returns its lifecycle result in
response to `host-1`. Distinct IDs and the echoed invocation disambiguate both
responses; the host MUST read capability requests instead of blocking solely
for `host-1`'s response. The same sequence applies to `acquire`, `publish`, and
`enrich`.

## Downstream compatibility note

Core and the PHP SDK are non-normative implementations. Their inspected docs
describe inline bytes as JSON strings and stream reads as base64; those
representations conflict with this contract's required JSON arrays of unsigned
bytes. Their existing RPC resource/capability calls also do not implement this
canonical WIT-qualified method, tagged handle, invocation-ID, ownership, borrow,
drop, or exact typed-value mapping. These layers require migration to this
document; this contract does not preserve those implementation details.

## Version decision

The WIT types and already-normative `list<u8>` array mapping are unchanged.
RPC v1 previously specified length-prefixed UTF-8 JSON and described resources
as opaque invocation-scoped references, but left their actual representation,
correlation, ownership and lifecycle unspecified. This document makes those
unspecified semantics precise without changing a previously specified wire
value or WIT shape. Therefore `stashd:plugin@0.16.0` remains the canonical
package identity for the HTTP method model; this WIT shape change requires the
pre-1.0 package version bump from 0.15.0.
