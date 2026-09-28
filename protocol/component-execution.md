# Component execution and RPC transport

This document normatively defines how a resolved package component becomes a process speaking native RPC v1. [Package artifact resolution](package-artifact.md) governs artifact path normalization, containment, and regular-file validation. [RPC v1](rpc-v1.md) governs framing, WIT encoding, invocation correlation, and resource ownership.

## Artifact and launch environment

A component's resolved `artifact` is the program implementing that component. After resolving and validating it under the package-artifact rules, the host launches that file as a program. The artifact may use an ordinary platform launcher mechanism where its packaging environment requires one. The protocol does not prescribe a language, interpreter, runtime taxonomy, or universal executable-bit rule. Execution failure is a component startup/load failure, not a lifecycle `plugin-error`.

The process working directory MUST denote the unpacked package root, so package-owned resources are accessible by package-relative paths. A sandbox MAY map the root to another internal absolute location while preserving these semantics. Plugins MUST NOT need to know, persist, emit, or depend on the host's absolute package path; no host package or Vault path is exposed through WIT.

The protocol requires no command-line arguments. A component MUST NOT require Core-specific positional arguments or flags to implement the contract. The selected component and world are host/package state; the canonical lifecycle method identifies the operation after handshake. Launch implementations MUST NOT use arguments to expose package IDs, credentials, Vault paths, component state, or lifecycle inputs.

The host MAY sanitize or minimize the process environment. No environment variable is guaranteed unless explicitly defined by the canonical contract. Component correctness MUST NOT depend on inherited host environment. Credentials MUST NOT be injected into the process environment merely because helper credential injection exists; invocation credentials use the canonical WIT credential model.

## Process RPC channels

For native RPC v1 process components:

- stdin is exclusively the host-to-plugin RPC v1 byte channel. It carries the existing four-byte big-endian length-prefixed UTF-8 JSON frames. Plugins MUST NOT expect interactive user input on stdin.
- stdout is exclusively the plugin-to-host RPC v1 byte channel and carries only valid RPC v1 framed messages. Plugins MUST NOT write banners, logs, warnings, whitespace, or other diagnostic/text output there. Any stdout bytes not forming canonical framing are a protocol failure.
- stderr is an ordinary diagnostic channel, not part of RPC v1. The host MAY capture, display, truncate, persist as diagnostics, or discard it. stderr MUST NOT affect framing or typed lifecycle results, and plugins MUST NOT require it to carry protocol state. Once an invocation is active, structured invocation-aware diagnostics should use the canonical `logging-host` capability where appropriate. No framed protocol is defined on stderr.

## Startup and hello

Every newly launched process MUST send the existing RPC v1 `hello` request as its first stdout frame. Hello has no lifecycle invocation ID. The host validates protocol compatibility and responds to hello; only after successful hello may it send a lifecycle request. No lifecycle request or imported capability/resource request may precede successful hello. Malformed frames or any other stdout bytes before or during hello fail startup. Process exit or stdout closure before hello completes also fails startup. Startup failures are not lifecycle `plugin-error` results.

## Lifetime and reuse

Process reuse across sequential lifecycle invocations is host/runtime policy. A host MAY retain a successfully handshaken process or terminate it after an invocation and launch a fresh one later. Each new process performs hello once; a reused process does not repeat hello for each invocation. At most one lifecycle invocation is active per process, as specified by RPC v1.

Plugin correctness MUST NOT depend on mutable process-local state surviving between lifecycle invocations. Process-local caches are permitted as optimizations, but correctness-required information comes from the current lifecycle request, canonical durable plugin/Core state represented by the contract, host capabilities, package contents, or external systems. Invocation-scoped resources, grants, streams, staged outputs, and references become invalid at invocation end even if the process remains alive.

## Exit, termination, and channel failure

Before hello completes, process exit is startup failure. During an active lifecycle, process exit or a broken RPC channel before a valid lifecycle response is accepted is invocation transport/execution failure, never a successful lifecycle result; unadopted invocation-scoped resources are cleaned up under their existing rules. After a complete valid lifecycle response has been accepted, that result remains authoritative and a later process exit MUST NOT retroactively change it. A later invocation may launch a new process.

Timeout and cancellation remain host/runtime policy; this contract defines no cancellation protocol or signal semantics. The host MAY terminate a process out of band under timeout, invalid-channel, unresponsive-process, or sandbox/runtime policy. Termination before lifecycle response acceptance fails that invocation and cleans up its invocation-scoped resources.

On framing or protocol failure, the failing endpoint MUST treat the channel/process as unusable. The active lifecycle fails if one exists, invocation-scoped resources are invalidated/cleaned up, and no lifecycle `plugin-error` is synthesized. The endpoint MUST NOT continue processing later frames on that channel. The host MAY terminate the process. Any replacement process performs hello from the beginning. A top-level `error` field is invalid in a response envelope; typed WIT failures remain values inside the required `result` field.
