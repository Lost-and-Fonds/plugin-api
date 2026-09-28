# Input preservation and completeness

This document normatively defines successful-but-incomplete Input discovery and acquisition. It is distinct from bounded delivery and run continuation in [Input discovery](input-discovery.md).

## Execution and preservation outcomes

Input lifecycle functions retain `result<T, plugin-error>`. `Err(plugin-error)` means the invocation did not produce a coherent preservation result the host may safely adopt. Invocation-scoped staged output is not adopted merely because bytes were written before execution failed. `plugin-error-detail.retryable` describes whether the failed invocation itself should be tried again.

`Ok(result)` means the plugin completed coherently and the host may persist/adopt the result. It may report incomplete enumeration or preservation. Execution outcome, preservation/completeness outcome, and retry disposition are separate concerns.

## Deficiencies and diagnostics

`deficiency-disposition` is `retryable`, `terminal`, or `unknown`. `retryable` means a later attempt may plausibly improve the gap after transient conditions change. `terminal` means the plugin has positive reason to believe the same logical operation under materially unchanged conditions will not resolve it, not that the bytes can never exist under changed credentials, source state, configuration, plugin version, or manual intervention. `unknown` means the plugin cannot make a useful generic prediction and MUST NOT be forced into `terminal`.

A `deficiency` combines one disposition with an `outcome-diagnostic`. A diagnostic contains human-readable plugin-supplied text and zero or more canonical `plugin-metadata` evidence facets. The host MAY display/store the message and MUST treat evidence as opaque: it MUST NOT parse plugin-owned evidence for provider or domain semantics. Provider-specific identifiers, status details, resource categories, counts, and retry evidence belong in those facets, never universal protocol fields.

The host derives generic retry policy only from dispositions: any `retryable` deficiency means a later retry may improve the outcome; all `terminal` deficiencies do not indicate unchanged automatic retry; `unknown` deficiencies without any retryable one leave the decision to host/user policy. Mixed dispositions remain partial and potentially improvable when any one is retryable. The host MUST NOT inspect evidence to decide retry policy.

## Acquisition result and adoption

`acquisition-result` contains returned `artifacts` and a `preservation-outcome`:

- `complete` asserts that the intended acquisition scope for this discovered Item and invocation was satisfied. It makes no claim about the entire provider/account/site, discovery exhaustiveness, alternative representations, or anything beyond that scope.
- `partial(deficiencies)` means execution succeeded and returned artifacts are valid/adoptable, but the plugin knows the intended acquisition scope was not fully satisfied. `partial` MUST contain at least one deficiency. If the plugin knows the result is incomplete but cannot identify a precise cause, it may report an `unknown` deficiency with a useful generic diagnostic.

For every successful acquisition, the host MUST treat returned artifacts, preservation outcome, and all deficiency diagnostics/evidence as one logical durable preservation fact. It MUST NOT adopt artifacts while losing or omitting the partial claim. If adoption/persistence cannot complete coherently, the newly adopted Assets MUST NOT appear as an unqualified complete acquisition. Existing staging remains invocation-scoped: only artifacts returned by `Ok(acquisition-result)` are candidates for adoption. An `Err(plugin-error)` does not turn staged data into partial output.

A partial result retains all returned valid concrete artifacts even if sibling material failed. The plugin MUST NOT return half-written or corrupt temporary files. A partial result MAY contain zero artifacts when the plugin coherently establishes gaps but captures no valid output. A complete result with zero artifacts is not prohibited by this contract. The host MUST reject malformed output, including an empty deficiency list in a partial outcome.

A later retry is a new acquisition attempt. Earlier adopted valid Assets remain historical preservation evidence unless a host provenance/version model explicitly supersedes them. A failed retry MUST NOT erase an earlier partial capture. This contract does not define host version-history machinery.

## Discovery coverage

Terminal discovery coverage is represented independently from acquisition completeness:

- `finished(exhaustive(refresh-state))` asserts that the run exhaustively enumerated the logical Input according to request, credentials, and plugin semantics. It may replace the completed refresh baseline with the optional state, including clearing it with `none`. It does not assert acquisition completeness of any Item.
- `finished(partial(deficiencies))` ends the run successfully with known gaps preventing exhaustive enumeration. It MUST have at least one deficiency.
- `finished(indeterminate(diagnostic))` ends the run without a truthful claim of either exhaustive enumeration or known definite incompleteness.

Partial and indeterminate terminal discovery retain all successfully committed Items, persist coverage and diagnostic/evidence state, clear the run continuation, and leave the previous completed refresh baseline unchanged. They do not permit continuation or refresh-state advancement. The host MUST reject an empty partial deficiency list and malformed terminal state. A zero-Item terminal batch is valid, including partial or indeterminate discovery.

Only `finished(exhaustive(...))` may replace or clear completed refresh state. Acceptance of any `finished(...)` batch atomically commits final Items, terminal status, coverage claim, evidence, and the refresh transition only when exhaustive. This is the #21 terminal acknowledgment commit point: later plugin failure cannot reopen or roll back the run, and no further batch may be committed. Successful `discover` completion without an acknowledged terminal batch is a protocol violation. If acknowledgment is lost, host durable state is authoritative.

A resumable interruption is not terminal partial discovery. If a transient issue such as rate limiting occurs after acknowledged `more(C42)`, the plugin SHOULD return an execution error and let the host resume at C42. It MUST NOT report terminal partial merely because this invocation stopped. A terminal partial/indeterminate claim means the logical run intentionally ends and has no continuation. `plugin-error-detail.retryable` answers whether a failed invocation should be retried; deficiency disposition answers whether a known gap in a coherent successful outcome may plausibly improve. These are different questions.

## Examples

- A browser capture with a valid main WARC and failed embeds returns `Ok` with the valid artifact and a partial retryable/unknown deficiency with browser-owned evidence; the artifact is adopted with its incomplete claim.
- Thirty-eight captured resources and one definitively missing CDN object return a partial outcome with 38 valid artifacts and a terminal deficiency. Two temporary failures plus one known missing object may return retryable, retryable, and terminal deficiencies together.
- Three coherently identified unavailable resources may return `Ok(artifacts = [], partial([...]))`; this is not necessarily an execution error.
- A plugin crash midway returns `Err(plugin-error)`; staging is not adopted.
- A forum crawl with a known inaccessible region ends at `finished(partial([...]))`; prior committed Items remain and the old refresh baseline is preserved. An uncertain history boundary ends at `finished(indeterminate(...))` and likewise preserves the old baseline.
- A resumable rate limit after `more(C42)` returns an execution error, not terminal partial discovery; retry uses C42.
- Exhaustive discovery and partial acquisition are independently valid: the plugin can know exactly which Items exist while failing to preserve every representation.
