#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tokenizer.py
python3 parser.py
python3 evaluator.py
python3 -m unittest discover -v
python3 runner.py example.v
python3 runner.py native.v
python3 runner.py modules.v
python3 runner.py ../chapter-test-suite.t
echo "All Chapter 13 tests passed."
