#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
M3="$ROOT/tests/contract"

python3 "$ROOT/tools/extract_wit.py" --repo-root "$ROOT" --output-dir "$ROOT/schema"
PYTHONPATH="$M3" python3 "$M3/test_m3.py" \
    --repo-root "$ROOT" \
    --schema "$ROOT/schema/wit-schema.json" \
    --goldens "$M3/goldens"
