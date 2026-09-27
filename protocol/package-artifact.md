# Package artifact resolution

This document is normative for the `components.*.artifact` field in the plugin package manifest. It defines a portable logical package path. It does not define package extraction, component validation, or an operating system filesystem API.

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
