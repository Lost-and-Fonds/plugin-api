# Preserved Asset invocation grants

This document normatively defines authority to open `preserved-asset.reference` through `broadcast-host.open-asset` and `enrichment-host.open-asset`. The reference remains an opaque string locator; it is not a path, URL, durable source identity, or bearer capability. Possession, copying, guessing, or global validity of the string grants no authority. The authority is an invocation-scoped grant table mapping a granted reference to one exact host-controlled preserved Asset representation. A grant MUST NOT be rebound to a different target during that invocation. Stable durable Asset identity remains `preserved-asset.id`.

## Grant creation

### Broadcast

A Broadcast invocation gains grants only for references in the `preserved-asset` values of an Item actually returned to the plugin by that invocation's `item-collection.next(...)`. The grant becomes active as part of successfully supplying the Item, before the plugin may make a subsequent host call, including `broadcast-host.open-asset`. Membership in the host's selected collection is not itself a grant. References for Items not yet delivered are not granted, even if guessed correctly. Grants accumulate as Items are delivered and remain active for the rest of the invocation; advancing the collection does not revoke earlier grants.

### Enrichment

For an Enrichment lifecycle invocation, the host grants every `preserved-asset.reference` present in the supplied `item-context.assets` before plugin execution may use the Asset-read host capability. A host-known Asset absent from that context is not granted. This does not weaken `capabilities(context)`: discovery remains credentialless and local, and MUST NOT open Asset bytes or perform fallible host work. The grant is usable through `enrichment-host.open-asset` during `enrich(...)` subject to the existing lifecycle restrictions.

## Lifetime and isolation

Each grant belongs to exactly one lifecycle invocation and its corresponding lifecycle host API. It remains valid until that invocation ends unless the target becomes unavailable. Invocation cleanup invalidates it. Grants do not transfer between invocations, from Broadcast to Enrichment, from Enrichment to Broadcast, or through another lifecycle API. Copying a reference within an authorized invocation preserves usability because authority is in the invocation's grant table. Copying or persisting the string creates no authority elsewhere. A later invocation may use the same textual reference only if its host explicitly grants that reference anew. Security does not require global uniqueness or unpredictability of strings.

## Opening order and errors

Both `broadcast-host.open-asset` and `enrichment-host.open-asset` MUST apply this order:

1. Look up the exact supplied reference in the current invocation's grant table for that lifecycle host. If absent, return denied immediately. The host MUST NOT first search all preserved Assets or distinguish a fabricated string from a real but ungranted Asset. A global lookup result never confers authority.
2. Resolve the granted reference to its bound host-controlled target. If that target is no longer available, return missing.
3. Only then apply the shared [byte-range model](byte-ranges.md). Thus a granted target with `offset > size` is denied under that model, and no ungranted reference can probe size or range validity.
4. After successful grant, target, and range validation, underlying storage/read failures return `failed(...)`.

The typed mapping is:

| Situation | Broadcast | Enrichment |
| --- | --- | --- |
| Granted, valid, available target and range | success | success |
| Known to Core but not granted; fabricated/guessed; prior invocation; another invocation; or another lifecycle host | `stream-error.denied` | `asset-error.denied` |
| Granted target no longer available | `stream-error.missing` | `asset-error.missing` |
| Granted target with invalid byte range | `stream-error.denied` | `asset-error.denied` |
| Underlying I/O/storage/read failure after validation | `stream-error.failed(...)` | `asset-error.failed(...)` |

Fabricated and known-but-ungranted references MUST have the same authority failure. In particular, both in-range and out-of-range requests for an ungranted reference return denied before global existence, target size, or range is evaluated.

## Conformance flows

### Broadcast delivery grants

In one invocation, `item-collection.next(...)` returns Item A containing Asset A. Asset A's reference is granted before the Item is made available to the plugin; `broadcast-host.open-asset(A, ...)` may succeed. Item B has not yet been returned, so even a known or guessed B reference is ungranted and `open-asset(B, ...)` returns `stream-error.denied`. When a later `next(...)` actually returns Item B, B's reference becomes granted and may be opened. Both A and B remain granted through the rest of the invocation. Invocation completion invalidates both.

### Enrichment context grants

In one Enrichment invocation, each reference in the host-supplied `item-context.assets` is granted before `enrich(...)` may use the Asset-read capability. A different Asset known to Core but absent from the context is denied. A reference copied from an earlier Enrichment invocation is denied unless explicitly granted again in this invocation. A grant does not authorize `enrichment-plugin.capabilities(...)` to open bytes; that lifecycle remains credentialless/local and prohibits fallible host work.

### Cross-boundary authority

A fabricated string, a globally known but ungranted reference, a reference from an earlier or other concurrent invocation, or a reference granted only through the other lifecycle host all return denied. A copied reference remains usable within the invocation whose table grants it. Invocation end removes authority. Explicitly granting the same string in a later invocation establishes only that later invocation's grant and target binding.
