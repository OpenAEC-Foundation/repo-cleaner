#!/usr/bin/env bash
set -euo pipefail

DYNLEX="${DYNLEX:-dynlex}"
if ! command -v "$DYNLEX" >/dev/null 2>&1; then
    echo "Error: DynLex compiler not found: $DYNLEX" >&2
    exit 1
fi

mkdir -p build/tests
while IFS= read -r source; do
    name="$(basename "${source%.dl}")"
    executable="build/tests/$name"
    echo "Compiling $source"
    rm -f "$executable"
    "$DYNLEX" "$source" -O2 -o "$executable"
    if [[ ! -x "$executable" ]]; then
        echo "Error: DynLex did not produce $executable" >&2
        exit 1
    fi
    echo "Running $name"
    "$executable"
done < <(find tests -maxdepth 1 -type f -name '*_test.dl' | sort)
