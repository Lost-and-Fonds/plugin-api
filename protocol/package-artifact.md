# Package artifact resolution

This document is normative for the `components.*.artifact` field in the plugin package manifest. It defines a portable logical package path. It does not define package extraction, component validation, or an operating system filesystem API.

## Component credential slots

Each component may declare `credential_slots`, an object keyed by stable slot names. An omitted or empty object means the component declares no credential requirements. Names use the component-ID syntax `^[a-z0-9][a-z0-9._-]*$`; names are unique by construction within the component. Slot identity is the tuple `(package id, component id, slot name)`. The same name in distinct components is independent and never implies shared configuration.

A slot descriptor requires `label` and `required`, and may include `description`. These strings are presentation metadata only and do not participate in identity. Declarations contain no credential reference, secret, credential taxonomy, provider, scopes, or protocol placement.

The package declares requirements; Core/configuration persists the user's choice of stored credential reference per slot; invocation bindings grant temporary use. A `credential-reference` is an opaque host selector, not a secret or authorization. A `credential-binding` maps the declared slot name to that reference and is supplied only when Core authorizes it for the invocation. Bindings MUST correspond to slots declared by that component; plugins MUST NOT rely on hidden or undeclared names.

`required: true` means the component cannot perform its normal configured function without a binding. `required: false` means it may work anonymously or with reduced functionality. Neither value grants permission or guarantees validity or availability. Hosts may defer invocation when a required binding is absent; every use still undergoes invocation authorization and use-time availability/revocation checks, preserving `credential-denied` versus `credential-unavailable`.

Keep a slot name when the logical requirement remains the same. Rotating/replacing the stored credential reference or changing presentation text preserves identity. Adding an optional slot is configuration-compatible; adding a required slot can leave existing installations incompletely configured. Renaming or removing a slot changes the configuration contract and MUST NOT silently transfer its binding. Hosts MUST NOT infer equivalence between differently named slots; no migration framework is implied.

For example, `input.account` and `broadcast.account` in one package are separate slots. Core may let a user select the same stored reference for both, but that is an explicit host/user decision. A website Input declaring `session` may bind a refreshed session reference without changing that slot identity. The Input invocation receives only explicitly granted bindings. HTTP and helper capabilities mediate credential use; the existing Input-only `input-host.open-credential(reference)` remains available only for protocols those capabilities cannot express. Browsertrix/Chromium/Playwright helpers receive only the invocation's explicit bindings; generic helper mediation carries opaque session material without browser-specific WIT. Broadcast and Enrichment do not gain raw-secret access.

This covers API-backed private YouTube and Internet Archive Input, Internet Archive/Broadcast and Jellyfin/Plex destinations, S3/WebDAV Broadcast, helper-backed SFTP, authenticated Enrichment APIs, and multiple independent slots on one component. Each declares only its own stable names, Core stores references by component-scoped identity, and invocation bindings carry name/reference pairs. Use host-mediated HTTP or helper execution where applicable; Input may use its existing raw-secret escape hatch only when mediation is insufficient. Optional slots permit anonymous operation. No package metadata contains secrets or references.

## Manifest path syntax

The value is a non-empty JSON string containing a portable logical path.

- `/` is the only separator.
- `\` is forbidden. It is not a separator and is not a literal package filename character.
- A leading `/` is forbidden. A path with one is absolute under this syntax.
- `:` is forbidden anywhere in the value. This rejects drive-relative and drive-absolute forms such as `C:component.wasm` and `C:/component.wasm`, and keeps drive, device, and other host-specific path forms out of the logical namespace.
- UNC-style forms are forbidden. Backslash forms fail the `\` rule, and slash forms such as `//server/share/component.wasm` fail the leading `/` rule.
- ASCII control characters, including NUL, are forbidden.
- Empty segments are allowed in the input and have no meaning. Thus repeated separators and a trailing separator are normalized lexically.
- A segment equal to `.` has no meaning and is removed.
- Other segments are package entry names, except that `..` has traversal meaning as described below.

The syntax deliberately does not use the host's native path grammar. A runtime MUST validate this syntax before passing any value to a native path API.

## Lexical normalization

To normalize an accepted path, split it on `/` and process segments from left to right:

1. Ignore empty segments and segments equal to `.`.
2. For `..`, remove the immediately preceding retained segment. If there is no retained segment, reject the path as traversal above the package root.
3. Retain every other segment in order.
4. Join the retained segments with `/`.

Reject the path if the result has no retained segments. The normalized result is always a non-empty relative logical path using `/` and contains neither `.` nor `..` segments. Normalization is lexical only; it does not inspect the unpacked package.

For example, `./components//main.wasm/` normalizes to `components/main.wasm`, and `a/../components/main.wasm` normalizes to `components/main.wasm`. `../../evil.wasm`, `a/../../../evil.wasm`, `/component.wasm`, and `a/..` are rejected.

A runtime MUST NOT silently replace a rejected path with a native-normalized path. Filesystem resolution starts only from the resulting normalized path; segments removed during lexical normalization are not looked up as filesystem entries.

## Filesystem resolution and containment

Artifact resolution takes place after the package has been completely unpacked, against that package's unpacked root. The runtime MUST:

1. Lexically normalize the manifest value and reject any lexical failure.
2. Resolve the normalized path using filesystem directory entries, following symlinks in every intermediate component and in the final component.
3. Resolve the package root to its filesystem identity for the containment comparison.
4. Require the resolved artifact to exist and be a regular file. A missing entry, resolution error, symlink loop, or directory is a package validation/load failure. Component format and declared-world validation are separate checks.
5. Require the resolved artifact identity to be the package-root identity followed by zero or more complete path components. A string prefix comparison is not sufficient: `/package-two` is not contained by `/package`.

A symlink is permitted only when following it, including all intermediate symlinks and the final symlink, resolves to an existing regular file within the unpacked package root. A symlink that resolves outside the root, cannot be resolved, or forms a loop is rejected. The same containment check applies regardless of whether a symlink target is relative or absolute in the host filesystem.

The runtime may implement these abstract steps with language- or OS-specific primitives, but those primitives MUST provide the stated behavior. In particular, a runtime MUST NOT use a host API whose treatment of backslashes, drive letters, nonexistent components, or symlinks changes the manifest meaning. The runtime MUST compare canonical filesystem identities at a component boundary, not compare untrusted strings.

Validation and loading use the same fully unpacked package snapshot. A one-time check does not protect a package directory that can be modified afterward. A runtime that accepts mutable package directories MUST either keep the accepted snapshot immutable or use filesystem operations that preserve the same root and target guarantees while opening the artifact. OCI extraction and package-manager behavior are outside this contract.

## Equivalent artifacts

Component entries may share a normalized path. They may also use different normalized paths that resolve to the same in-package regular file, including permitted in-package symlink aliases. Sharing does not by itself invalidate a package. Each component entry is independently normalized, resolved, contained, and checked for existence and type.

## Forcing vectors

The conformance vectors in [`package-artifact-vectors.json`](package-artifact-vectors.json) exercise lexical acceptance and rejection, native-platform escape forms, equivalent paths, and final and intermediate symlink escapes. Their expected outcomes are part of this contract.
