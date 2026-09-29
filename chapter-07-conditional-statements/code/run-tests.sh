#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 tokenizer.py
python3 parser.py
python3 evaluator.py
python3 -m unittest discover -v

actual_output="$(./vertex example.v < /dev/null 2>/dev/null || true)"
expected_output='Chapter 7: Conditional Statements
single branch runs
B or lower
C
3
unselected branch never touched exit or input'

if [[ "$actual_output" != "$expected_output" ]]; then
    echo "example.v output did not match" >&2
    diff -u <(printf '%s\n' "$expected_output") <(printf '%s\n' "$actual_output")
    exit 1
fi

echo "All Chapter 7 tests passed."
