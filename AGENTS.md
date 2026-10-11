# Plugin API repository instructions

The API repository owns only the language-neutral contract. Do not add provider
semantics, PHP SDK implementation, or core runtime code here.

Verification: run `./bin/verify-contract`. Focused audit regressions run with
`python3 tools/test_audit_regressions.py`. Regenerate artifacts with
`python3 tools/extract_wit.py --repo-root "$PWD" --output-dir schema`.
WIT extraction uses the CI-pinned `wasm-tools` parser and rejects unsupported
valid declarations rather than producing partial schemas.
