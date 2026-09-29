# Input discovery

This document normatively defines bounded Input enumeration and its durable progress contract. Preservation completeness and acquisition outcomes are specified separately in [Input preservation and completeness](input-preservation.md).

## Delivery and batch acceptance

An Input delivers discovered Items only through `input-host.commit-discovery-batch`. `discover` returns no Item list; normal success means the plugin has submitted and received acknowledgment for a terminal batch. The plugin MUST NOT use a second delivery path, accumulate the complete discovery before delivery, or commit more than `maximum-items-per-batch` Items in any batch. The host-provided maximum MUST be greater than zero and is an upper bound, not a required batch size. The negotiated RPC frame maximum also applies independently. The producer MUST send fewer Items when required to fit the encoded frame; a single indivisible Item that cannot fit fails the invocation without an over-limit probe. This is a semantic count limit, not a provider page size; provider pagination is plugin-owned.

The host MUST atomically accept every Item in a batch and its progress transition, or accept neither. A successful acknowledgment means both are durable across invocation failure. The host MUST NOT durably store Items separately from the associated continuation or terminal transition. The host MUST enforce the active request's `maximum-items-per-batch`: it MUST reject a batch exceeding that count, a commit outside the active `discover` run, and any commit after that run is terminal. `discovery-commit-error.rejected` is sufficient for these cases. The negotiated RPC frame maximum remains an independent constraint; the producer may send fewer Items to fit it.

`more(continuation)` accepts a nonterminal batch and durably stores the next run continuation. It leaves the previously completed refresh state unchanged. The host's durable state is authoritative after commit, including when acknowledgment is lost or the plugin subsequently dies. If acceptance fails or acknowledgment is lost, the plugin MUST NOT assume progress advanced or retry on the assumption that it did not; the host may have durably committed the batch.

`finished(exhaustive(refresh-state))` accepts a terminal exhaustive batch, marks the run terminal, clears its continuation, and replaces the completed refresh state with the supplied optional value in the same atomic acceptance. `none` may clear a prior baseline. `finished(partial(deficiencies))` and `finished(indeterminate(diagnostic))` accept terminal coverage claims but MUST leave the previous completed refresh state unchanged. Partial and indeterminate outcomes leave it unchanged. These terminal batches MAY contain zero Items. Every terminal batch's successful acknowledgment is the durable commit point: final Items, terminal status, coverage, and diagnostics/evidence are durable together; only an exhaustive finish changes refresh state.

A `partial` finish MUST contain at least one deficiency. A partial or indeterminate finish MUST NOT carry continuation or advance/clear refresh state. The host MUST reject malformed terminal coverage, including empty deficiencies and any terminal state containing continuation. The host MUST NOT accept a terminal result as exhaustive if its coverage evidence was lost.

After acknowledgment of any `finished(...)` batch, the run is terminal: the plugin MUST NOT commit another batch and MUST return successful completion from `discover` without further discovery work. A later plugin crash, transport failure, or erroneous `discover` return MUST NOT roll back or reopen the run. If terminal acknowledgment is lost, host durable state remains authoritative; no continuation remains, and another commit MUST be rejected. Conversely, `discover` success without acknowledgment of a `finished(...)` batch is a protocol violation and MUST NOT complete the run. If execution fails before terminal acceptance, prior acknowledged `more(...)` batches remain durable and resumable.

## Coverage claims

`exhaustive(refresh-state)` means the plugin asserts that this run enumerated the logical Input exhaustively according to the request, credentials, and plugin semantics. It says nothing about whether discovered Items were fully acquired; exhaustive discovery with partial acquisition is valid.

`partial(deficiencies)` means the run intentionally terminates successfully with known gaps that prevented exhaustive enumeration. The committed Items remain valid, but there is no continuation for that logical run. `indeterminate(diagnostic)` means the run terminates without a truthful claim of either exhaustive enumeration or known definite incompleteness. Use neither terminal form for an ordinary transient interruption that should resume.

If a transient interruption, such as a rate limit, should be resumed, the plugin MUST retain the last acknowledged `more(continuation)` and return an execution error. It MUST NOT turn that interrupted invocation into terminal partial or indeterminate coverage merely because it cannot continue now. `plugin-error-detail.retryable` describes retry of the failed invocation; deficiency dispositions describe gaps in a coherent successful result.

## Distinct opaque state

A `discovery-continuation` is plugin-owned opaque state for one in-progress logical run. It resumes immediately after the last durably acknowledged batch. It MUST contain or identify all plugin-specific resume information without depending on mutable plugin-local disk or process state. Core MUST store and return it unchanged and MUST NOT interpret it. It is discarded when any terminal batch is accepted and MUST NOT be treated as completed refresh state.

A `discovery-refresh-state` is plugin-owned opaque state retained only between completed runs as a possible baseline for a later `refresh`. It is optional. Core MUST NOT interpret it. Only acknowledged `finished(exhaustive(...))` may replace or clear the completed refresh baseline; `more`, partial, and indeterminate outcomes leave it unchanged. Inputs that do not support efficient refresh MAY always receive and return `none` on exhaustive completion.

Neither state may contain credentials or depend on secret material. Credential bindings may legitimately change between invocations.

## New and resumed runs

A new run has `continuation = none`. The host fixes its Input identity, intent, options, and prior completed refresh-state baseline when creating the run. A resumed invocation MUST preserve that context and supply the last durably acknowledged continuation. Credentials are invocation-scoped and may rotate or be revoked. If run configuration changes incompatibly, the host MAY abandon the run and start a new one; it MUST NOT resume the continuation under silently changed semantics.

For new `complete` intent, the plugin enumerates the complete logical Input without requiring a refresh baseline; the host SHOULD supply no baseline. The terminal batch MAY establish state for a later refresh. For new `refresh` intent, the host MAY supply the most recently completed refresh state. With no baseline, the plugin MUST behave coherently, for example by performing initial complete enumeration. The host does not define or interpret refresh semantics.

## Interruption and retry

After batch 861 is acknowledged and the invocation fails during batch 862, Core retains Items through batch 861, the continuation committed with that batch, and the previous completed refresh state. Retry resumes from that continuation, not batch 1. The underlying remote source may mutate and yield overlapping Items after resumption; stable `discovered-item.id` is the logical identity available to the host. The contract does not require an immutable remote snapshot or add provider-specific deduplication machinery. The continuation MUST faithfully represent the best durable next point the source permits.

For example, if completed refresh state is R10, batches A and B may commit continuations C1 and C2. A crash after B leaves R10 and C2. If the terminal batch is `finished(partial(...))` or `finished(indeterminate(...))`, committed Items remain, the continuation is cleared, and R10 remains the baseline for a later run. Only `finished(exhaustive(R11))` atomically replaces R10 with R11; `finished(exhaustive(none))` clears it. Intermediate commits MUST NOT advance the baseline.

## State compatibility

Opaque state formats belong to the plugin. Plugins SHOULD keep formats backward-compatible across upgrades where useful; the protocol does not guarantee that state survives every plugin upgrade. If a newer plugin cannot understand an old continuation, the host may abandon that in-progress run and start a new one rather than guess or translate the value. The host MUST NOT rewrite or interpret either opaque state. This contract adds no universal state-version field or migration framework.

## Input sizes and examples

A small Input discovers A, B, and C, commits one batch containing those Items and `finished(exhaustive(none))`, then returns success. No session or resource is required. An incremental refresh with no new Items may commit a zero-Item `finished(exhaustive(R2))` batch. A source whose boundary is unknown may end with zero-Item `finished(indeterminate(...))`.

Large structured catalogs, whole-site crawls, series/platform enumerations, social histories, and revision feeds use bounded batches and plugin-owned opaque continuation. A completed Discord history may establish D1; later `refresh(D1)` may emit changes and terminally establish D2. An interrupted refresh keeps D1 until exhaustive terminal acknowledgment. Website recrawl/change-detection state and crawl-frontier state remain plugin-owned; Core receives no URL, HTTP validator, WARC, crawl-depth, or provider-pagination fields.
