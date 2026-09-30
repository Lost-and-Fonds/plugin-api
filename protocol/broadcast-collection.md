# Broadcast collection enumeration

This document normatively defines the selected Item collection supplied to one
Broadcast `publish` invocation. Asset contents remain a separate path: plugins
read them only through the existing `broadcast-host.open-asset` byte stream.

## Resource and membership

The host supplies an opaque `broadcast-host.item-collection` resource in
`publish-request`. It is owned by the plugin under RPC v1 resource-transfer
rules, is valid only for that invocation, may be explicitly dropped, and is
unconditionally invalidated at invocation end. It MUST NOT be persisted or
reused in another invocation. No database identity/query, Vault path,
filesystem handle, or provider cursor is exposed. Preserved Asset read authority
is granted only as each Item is successfully returned by `next(...)`, not by
membership in the selected collection; see [preserved Asset invocation grants](preserved-asset-grants.md).

The resource represents the caller-selected logical collection as fixed for
the invocation. New Items arriving in Core during publication MUST NOT be added.
Selected Items MUST NOT silently disappear due to unrelated state changes. The
host MUST return every selected Item at most once, in a coherent forward
sequence whose order is host-defined and has no provider/domain meaning. If a
selected Item cannot be presented, the host MUST return a collection-read error
rather than silently skip it. The host need not materialize the collection in
memory to establish this behavior.

## Bounded reads and EOF

`next(max-items)` requires `max-items > 0`. The requested value is an upper
bound, not provider pagination. The host MAY return fewer Items and MUST enforce
its explicit semantic count maximum; a request larger than that maximum SHOULD
return a smaller batch rather than fail. Each response is independently subject
to the peer-advertised RPC frame maximum, measured on encoded UTF-8 JSON. The
producer MUST return fewer Items as needed to fit; no hidden smaller encoded-byte
limit applies.

`some(non-empty-list)` returns a batch. `none` means EOF. An empty successful
batch is invalid and MUST NOT be used as another EOF spelling. Once reached,
EOF SHOULD remain sticky. An empty selected collection therefore reads as
`none` immediately. A final partial batch is valid. A valid single Item that
cannot fit within the peer-advertised receive maximum MUST fail at the
appropriate boundary using an existing typed error where available, never by
sending an oversized frame.

`rejected` covers invalid operations such as a zero maximum; `limit-exceeded`
means even one next Item cannot fit; `unavailable` means backing state/service
is currently unavailable; `failed` covers other host-side enumeration errors.
These errors do not expose provider or storage internals.

## Publication completion and failure

A plugin MAY apply destination-specific filtering using streamed Item metadata,
but filtering belongs to the plugin and does not permit stopping enumeration
early. The host MUST accept `Ok(publication)` only after the collection has
reached EOF. A successful response before EOF is a protocol/contract violation
and MUST NOT be accepted as complete publication. A plugin that encounters a
collection error, including one after remote work has started, MUST return an
existing Broadcast `plugin-error`; it MUST NOT report success for a prefix.

Remote side effects already performed may remain after a failed publication;
the protocol promises no remote rollback. Existing staging semantics are
unchanged: on error staged outputs are not adopted, unfinished writers are
discarded, and completed artifacts not returned by a successful result are
discarded at invocation end. Asset read failures continue to use existing
Asset stream errors, not collection errors. Dropping before EOF followed by an
error is valid; dropping before EOF followed by success is not.

There is no cross-invocation Broadcast continuation, cursor, checkpoint, or
resume state. A retry is a new invocation with a new collection resource and
starts a new publication attempt. Destination-specific retry/idempotency remains
plugin-owned. This mechanism does not change Collection Export, which remains a
bounded inline one-shot interchange lifecycle.
