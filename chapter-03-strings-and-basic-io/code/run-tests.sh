#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 tokenizer.py
python3 parser.py
python3 evaluator.py
python3 -m unittest discover -v

actual_output="$(./vertex example.v < /dev/null)"
expected_output='Chapter 3: Strings and Basic I/O
Hello, Ada!
Captured output: Hello, Ada!
Input after use: []
hahaha!
You entered: testing
42
Captured number: 42
As text: 42
With a decimal: 42.5'

if [[ "$actual_output" != "$expected_output" ]]; then
    echo "example.v output did not match" >&2
    diff -u <(printf '%s\n' "$expected_output") <(printf '%s\n' "$actual_output")
    exit 1
fi

echo "All Chapter 3 tests passed."
