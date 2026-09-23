#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 tokenizer.py
python3 parser.py
python3 evaluator.py
python3 -m unittest discover -v

actual_output="$(./vertex example.v < /dev/null)"
expected_output='Chapter 4: Booleans and Comparisons
true
false
true
false
true
true
true
false
true
true
true
Captured: true
Input cleared: []
Answer: 42
true
1
false
false
number
string
boolean
Accepted: true'

if [[ "$actual_output" != "$expected_output" ]]; then
    echo "example.v output did not match" >&2
    diff -u <(printf '%s\n' "$expected_output") <(printf '%s\n' "$actual_output")
    exit 1
fi

echo "All Chapter 4 tests passed."
