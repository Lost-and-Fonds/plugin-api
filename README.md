# Stashd plugin API

This repository is the canonical, language-neutral contract for Stashd
plugins: WIT definitions, generated schema, contract fixtures, and
compatibility rules.

The contract is normative. `stashd/php-sdk` provides the PHP authoring API;
`Lost-and-Fonds/stashd` owns the host/runtime and application integration.
Provider repositories own provider behavior.

Version changes must preserve the documented compatibility policy and pass the
contract test suite:

```sh
./tests/contract/run.sh
```
