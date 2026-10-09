# Ponytail Audit: Ultra

**What this repo does:** `plugin-api` defines the language-neutral agreement between Stashd plugins and their host: interfaces, wire messages, resource ownership, and package rules. It also generates schemas and checks contract examples. I assumed sequential plugin invocations handling large streams and long-running helpers, with independently implemented hosts and SDKs.

**Ultra assessment:** More abstraction is not needed. The priority is fixing contradictory rules and making the existing checks catch real contract mistakes. `./bin/verify-contract` passes; the targeted reproductions below expose gaps despite that. No files changed during the audit.

## Must fix

### 1. Resource ownership rules contradict ordinary method calls and drops

`protocol/rpc-v1.md:174–183`, `protocol/rpc-v1.md:197–236`

- **What this is:** A resource handle lets a plugin use a host-managed stream, writer, or collection.
- **Problem:** Transferring ownership makes the host’s handle transferred-away, which the host must reject. But the plugin then sends that same handle back to the host for borrowed method calls and destruction. Following both rules literally rejects legitimate operations.
- **Fix:** Distinguish the host’s backing resource from the endpoint currently owning its handle. Explicitly permit validated remote-owner method calls and destruction.
- **If we skip it:** Independent implementations can disagree about whether basic stream reads and cleanup are legal.

### 2. Collection Export uses the wrong directional frame limits

`wit/collection-export.wit:23–35`, `protocol/rpc-v1.md:258–260`, `tools/verify_generated_contract.py:28–37`

- **What this is:** Each endpoint advertises the largest message it can receive.
- **Problem:** Collection Export says requests must fit the **host’s** receive limit and responses the **plugin’s** limit. Those directions are reversed. The verifier also requires this incorrect wording.
- **Fix:** Requests must fit the plugin’s receive limit; responses must fit the host’s. Update the specification and its checks together.
- **If we skip it:** Different receive limits cause unnecessary rejection or messages too large for their recipient.

### 3. A blocked helper read prevents plugin-directed cancellation

`protocol/helper-process.md:3–7`, `protocol/rpc-v1.md:70–79`, `wit/io.wit:258–260`

- **What this is:** Plugins wait for helper output through `next-event` and stop helpers through `cancel`.
- **Problem:** `next-event` can wait indefinitely for a silent helper. RPC forbids issuing another capability request before that response, so the plugin cannot send `cancel` while blocked.
- **Fix:** Define a bounded wait or polling result for `next-event`, or a narrowly specified cancellation exception. Do not add general asynchronous RPC.
- **If we skip it:** Plugin-directed cancellation cannot interrupt this wait; recovery depends on host timeout or process termination.

## Should fix

### 4. The WIT extractor invents commented types and silently loses valid declarations

`tools/extract_wit.py:12–14`, `tools/extract_wit.py:139–165`

- **What this is:** The extractor turns WIT interface definitions into the committed JSON contract.
- **Problem:** An executed reproduction showed that `/* record phantom { value: string } */` becomes a real record. Another showed valid type aliases and flags disappearing entirely. `wasm-tools` accepted both inputs.
- **Fix:** Use the authoritative parser already invoked by verification, if practical. Otherwise strip comments correctly and reject unsupported declarations instead of silently omitting them.
- **If we skip it:** Generated schemas can describe an API that differs from the actual WIT, even after successful syntax validation.

### 5. Verification misses removed host interfaces and weakened manifest rules

`tools/verify_generated_contract.py:910–952`, `tools/verify_generated_contract.py:258–296`

- **What this is:** Semantic checks are meant to catch unintended contract changes.
- **Problem:** Executed mutations removing `input-host` or `broadcast-host` from their worlds both passed. Changing the package schema to allow unknown root fields also passed.
- **Fix:** Check exact canonical world imports/exports and essential manifest constraints. Add these three mutations to the existing sensitivity tests.
- **If we skip it:** Verification can approve components missing their essential host interface or manifests accepting previously forbidden fields.

### 6. Failed writer finalization has no defined next state

`protocol/staging.md:21–29`

- **What this is:** Staged writers collect temporary bytes and finalize them into adoptable artifacts.
- **Problem:** The state machine defines failed writes and successful finalization, but not a failed `finish`. After a storage error, implementations can disagree about whether retrying is allowed or whether the writer is permanently unusable.
- **Fix:** Specify the failure transition and artifact-registration guarantees. Making failed finalization poison the writer is the smallest conservative rule.
- **If we skip it:** Hosts and SDKs can implement incompatible retry behavior around the point where output becomes adoptable.

### 7. README teaches the obsolete helper API

`README.md:465–469`, `wit/io.wit:243–268`

- **What this is:** The README explains helper input and output ownership.
- **Problem:** It describes a borrowed stdout writer and a returned byte stream. Current WIT transfers an owned writer and returns a process whose events eventually return that writer on normal exit.
- **Fix:** Delete the obsolete paragraph or replace it with a short link to the canonical helper contract.
- **If we skip it:** Implementers may reuse a consumed writer or expect a return value that does not exist.

### 8. RPC integer checks accept forbidden encodings

`tools/verify_rpc_v1.py:205–211`

- **What this is:** Large integer values travel as canonical decimal strings.
- **Problem:** An executed vector mutation containing `"01"`, `"-0"`, and `"١"` passed verification. Numeric range checking does not enforce the required spelling.
- **Fix:** Check the canonical ASCII decimal grammar before conversion and retain these values as negative tests.
- **If we skip it:** Conformance fixtures can bless encodings that another compliant endpoint rejects.

### 9. Sensitivity tests mistake any failure for a correct rejection

`tools/test_contract_sensitivity.py:62–134`

- **What this is:** These tests deliberately break a contract and expect verification to reject it.
- **Problem:** Every nonzero exit counts as success, including an unrelated missing document or an unexpected Python exception. The normal command checks the baseline first, but individual mutation checks still do not establish why rejection happened.
- **Fix:** Require the expected diagnostic and reject unexpected exceptions. Merge the duplicate staging rejection helpers while touching this code.
- **If we skip it:** Broken verification can look like strong regression protection.

## Verdict

Fix resource ownership and Collection Export frame directions first, then close the helper cancellation gap. The passing suite is useful, but it is not yet reliable evidence of contract consistency.

**Lean:** About **19 lines, 0 dependencies** removable by merging the duplicate staging rejection helpers; more deletion is possible by removing obsolete README text.

**Not checked:** Downstream Core/SDK behavior, live helper processes, real filesystem races, and production load. Those remain runtime risks, not demonstrated failures in this audit.
