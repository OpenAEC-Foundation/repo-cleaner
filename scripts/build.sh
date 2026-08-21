#!/usr/bin/env bash
set -euo pipefail

DYNLEX="${DYNLEX:-dynlex}"
if ! command -v "$DYNLEX" >/dev/null 2>&1; then
    echo "Error: DynLex compiler not found: $DYNLEX" >&2
    exit 1
fi

mkdir -p build
rm -f build/repo-conventions-enforcer
"$DYNLEX" repo_conventions_enforcer.dl -O2 -o build/repo-conventions-enforcer
if [[ ! -x build/repo-conventions-enforcer ]]; then
    echo "Error: DynLex did not produce build/repo-conventions-enforcer" >&2
    exit 1
fi
