#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
python3 -m pyflakes --version >/dev/null 2>&1 || python3 -m pip install --quiet pyflakes

report=$(mktemp)
find bot -name '*.py' -print0 | xargs -0 python3 -m pyflakes > "$report" 2>&1 || true

echo "----- pyflakes report -----"
cat "$report"
echo "---------------------------"

if grep -qE "undefined name|invalid syntax|SyntaxError" "$report"; then
    echo "FAIL: crash-risk issues found:"
    grep -E "undefined name|invalid syntax|SyntaxError" "$report"
    rm -f "$report"
    exit 1
fi

echo "OK: no undefined names, no syntax errors."
rm -f "$report"
