# Input discovery

This document normatively defines bounded Input enumeration and its durable progress contract.

## Delivery and batch acceptance

An Input delivers discovered Items only through `input-host.commit-discovery-batch`. `discover` returns no Item list; normal success means the plugin has submitted and received acknowledgment for a terminal batch. The plugin MUST NOT use a second delivery path, accumulate the complete discovery before delivery, or commit more than `maximum-items-per-batch` Items in any batch. The host-provided maximum MUST be greater than zero. The canonical RPC message-size limit applies independently. This is a transport batch limit, not a provider page size; provider pagination is plugin-owned.

The host MUST atomically accept every Item in a batch and its progress transition, or accept neither. A successful acknowledgment means both are durable across invocation failure. If acceptance fails or acknowledgment is lost, the plugin MUST NOT assume progress advanced. The host MUST NOT durably store Items separately from the associated continuation or terminal transition.

`more(continuation)` accepts a nonterminal batch and durably stores the next run continuation. It leaves the previously completed refresh state unchanged. `complete(refresh-state)` accepts the terminal batch, marks the run complete, clears its continuation, and replaces the completed refresh state with the supplied optional value in the same atomic acceptance. A terminal batch MAY contain zero Items.

## Distinct opaque state

A `discovery-continuation` is plugin-owned opaque state for one in-progress logical run. It resumes immediately after the last durably acknowledged batch. It MUST contain or identify all plugin-specific resume information without depending on mutable plugin-local disk or process state. Core MUST store and return it unchanged and MUST NOT interpret it. It is discarded when the run completes or is abandoned and MUST NOT be treated as completed refresh state.

A `discovery-refresh-state` is plugin-owned opaque state retained only between completed runs as a possible baseline for a later `refresh`. It is optional. Core MUST NOT interpret it, and it changes only on successful atomic acceptance of a terminal batch. Inputs that do not support efficient refresh MAY always receive and return `none`.

Neither state may contain credentials or depend on secret material. Credential bindings may legitimately change between invocations.

## New and resumed runs

A new run has `continuation = none`. The host fixes its Input identity, intent, options, and prior completed refresh-state baseline when creating the run. A resumed invocation MUST preserve that context and supply the last durably acknowledged continuation. Credentials are invocation-scoped and may rotate or be revoked. If run configuration changes incompatibly, the host MAY abandon the run and start a new one; it MUST NOT resume the continuation under silently changed semantics.

For new `complete` intent, the plugin enumerates the complete logical Input without requiring a refresh baseline; the host SHOULD supply no baseline. The terminal batch MAY establish state for a later refresh. For new `refresh` intent, the host MAY supply the most recently completed refresh state. With no baseline, the plugin MUST behave coherently, for example by performing initial complete enumeration. The host does not define or interpret refresh semantics.

## Interruption and retry

After batch 861 is acknowledged and the invocation fails during batch 862, Core retains Items through batch 861, the continuation committed with that batch, and the previous completed refresh state. Retry resumes from that continuation, not batch 1. The underlying remote source may mutate and yield overlapping Items after resumption; stable `discovered-item.id` is the logical identity available to the host. The contract does not require an immutable remote snapshot or add provider-specific deduplication machinery. The continuation MUST faithfully represent the best durable next point the source permits.

For example, if completed refresh state is R10, batches A and B may commit continuations C1 and C2. A crash after B leaves R10 and C2. Only an acknowledged terminal batch `complete(R11)` atomically replaces R10 with R11. Intermediate commits MUST NOT advance the refresh baseline.

## State compatibility

Opaque state formats belong to the plugin. Plugins SHOULD keep formats backward-compatible across upgrades where useful; the protocol does not guarantee that state survives every plugin upgrade. If a newer plugin cannot understand an old continuation, the host may abandon that in-progress run and start a new one rather than guess or translate the value. The host MUST NOT rewrite or interpret either opaque state. This contract adds no universal state-version field or migration framework.

## Input sizes and examples

A small Input discovers A, B, and C, commits one batch containing those Items and `complete(none)`, then returns success. No session or resource is required.

Large structured catalogs, whole-site crawls, series/platform enumerations, social histories, and revision feeds use bounded batches and plugin-owned opaque continuation. A completed Discord history may establish D1; later `refresh(D1)` may emit changes and terminally establish D2. An interrupted refresh keeps D1 until its terminal acknowledgment. Website recrawl/change-detection state and crawl-frontier state remain plugin-owned; Core receives no URL, HTTP validator, WARC, crawl-depth, or provider-pagination fields.
