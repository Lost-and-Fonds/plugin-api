# Broadcast publication results

This document normatively defines publication reporting for one Broadcast `publish` invocation. Bounded selected-Item input and EOF are defined in [Broadcast collection enumeration](broadcast-collection.md); staged artifact authority and adoption are defined in [staging](staging.md).

## Invocation reporter and batches

The host creates exactly one `broadcast-host.publication-reporter` for a publication invocation and transfers its owned handle in `publish-request` alongside the `item-collection`. The reporter is invocation-scoped, non-durable, not reusable, and neither a cursor nor a continuation. Dropping its handle prevents further calls through it but does not commit prior reports.

`maximum-report-records-per-batch` MUST be greater than zero. It applies independently to each `report-files` and `report-destination-metadata` call. Each successful batch contains 1 through that maximum records. Empty batches are rejected; oversized batches return `limit-exceeded`. The ordinary RPC frame limit applies independently, including to an individual record. There is no cross-frame fragmentation or total result-cardinality limit imposed by one frame.

Each call is atomic: success accepts every record; any error accepts none from that batch. Accepted records retain call order and within-batch order. `rejected` covers semantic invalidity, including empty batches and duplicate file paths; `limit-exceeded` covers a batch exceeding the advertised maximum; `failed(string)` means the host could not record an otherwise acceptable batch. A plugin may correct and retry after an error; the error does not itself terminate or permanently poison the invocation. Failed batches are never persisted. For final `files: complete`, the plugin asserts that every record belonging to its canonical complete filesystem result was eventually accepted. It MUST NOT abandon a known file record whose omission would make that accepted sequence incomplete. A corrected later report may satisfy the complete result; the host does not scan the destination to prove this assertion.

## File result completeness

`published-file.relative-path` is relative to the destination namespace, never a Vault or host filesystem path. `item-id` and `asset-id` are optional correlation fields; the host does not interpret them as universal foreign keys.

`files: not-applicable` means this publication does not expose filesystem-relative output paths through the canonical `published-file` model. A successful result with this status MUST have zero accepted file records.

`files: complete` means the accepted report sequence is the exhaustive canonical filesystem-relative file result defined by the plugin for this successful publication. It is not advisory, a sample, or “whatever fit.” A complete empty result is valid. A plugin MUST NOT successfully claim `complete` when it knows the canonical result is only partially reported. The host transports and persists the assertion and does not scan the destination to prove it or infer provider/domain semantics.

Within one successful complete file report, each `relative-path` MUST occur at most once. If a proposed batch repeats a path accepted earlier in the invocation, the entire batch is rejected and none of its records are accepted. Different paths may correlate to the same Item or Asset; duplicate-content, hardlink, and other destination semantics remain plugin-owned.

## Destination metadata

All destination metadata is reported through `report-destination-metadata`; `publication` has no inline metadata list. The accepted sequence is the complete metadata emitted by the plugin for this publication, in successful report-call order and then record order within each batch. Duplicate facets are permitted; their meaning belongs to plugin-owned schemas.

Completeness here means the complete metadata sequence emitted by the plugin, not one facet per remote object or side effect. One item-level summary may represent many uploaded objects, or the plugin may emit many receipts or none. Facets remain opaque: Core MUST NOT interpret or normalize them to infer missing destination objects, nor infer semantic priority from ordering absent plugin-owned schema semantics.

## Final commit and failure

Report entries are provisional invocation state. Successful report calls do not independently make publication state durable. The final successful `broadcast-plugin.publish` result is the sole commit point. The host accepts the result only when existing publication conditions hold, including Item collection EOF, validity of any `publication.artifact` under [staging](staging.md), consistent file status, valid accepted report batches, and a valid final lifecycle response. It then accepts staged artifact adoption, published files, and destination metadata as one logical result. There is no reporter finish/finalize phase.

If publication returns a plugin error or the invocation fails due to protocol/channel failure, invalid staged artifact, invalid file status, or another contract violation, the host MUST discard all reporter state, including files and destination metadata. It MUST NOT expose a partial or successful publication result. Destination side effects, including uploads, filesystem writes, and destination commits, may remain; the protocol requires no rollback. Reporter errors need not appear in a final result. For file reports, final `files: complete` remains valid only when every record belonging to the asserted canonical complete file result was eventually accepted; the plugin may correct/retry failed reports but MUST NOT silently omit known records. For destination metadata, the successful result remains only the complete ordered sequence actually emitted and successfully accepted by the plugin. No receipt-per-object or receipt-per-side-effect completeness is required, failed attempted metadata need not be reconstructed, and Core keeps facets opaque. Only accepted report batches contribute if the lifecycle later succeeds.

There is no publication continuation, cursor, checkpoint, or cross-invocation report resume. Retry and reconciliation are future/plugin/application policy. A large result, including a million filesystem outputs, is reported in bounded calls during the invocation; the final `publication` contains only the optional staged artifact and small file status, never a result-sized inline list.
