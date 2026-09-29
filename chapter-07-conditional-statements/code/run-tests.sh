#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 tokenizer.py
python3 parser.py
python3 evaluator.py
python3 -m unittest discover -v

stderr_capture="$(mktemp)"
actual_output="$(./vertex example.v < /dev/null 2>"$stderr_capture")" && actual_status=0 || actual_status=$?
actual_stderr="$(cat "$stderr_capture")"
rm -f "$stderr_capture"

expected_output='Chapter 7: Conditional Statements
single branch runs
B or lower
C
3
unselected branch never touched exit or input'
expected_status=1
expected_stderr='Assertion failed: grade should exceed 100'

failed=0
if [[ "$actual_output" != "$expected_output" ]]; then
    echo "example.v stdout did not match" >&2
    diff -u <(printf '%s\n' "$expected_output") <(printf '%s\n' "$actual_output")
    failed=1
fi
if [[ "$actual_status" != "$expected_status" ]]; then
    echo "example.v exit code was $actual_status, expected $expected_status" >&2
    failed=1
fi
if [[ "$actual_stderr" != "$expected_stderr" ]]; then
    echo "example.v stderr did not match" >&2
    diff -u <(printf '%s\n' "$expected_stderr") <(printf '%s\n' "$actual_stderr")
    failed=1
fi
if [[ "$failed" -ne 0 ]]; then
    exit 1
fi

echo "All Chapter 7 tests passed."
