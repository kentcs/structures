from pathlib import Path
import subprocess
import sys
import unittest

from evaluator import evaluate_source
from tokenizer import tokenize

PRELUDE = 'items=[1, 2, 3]; empty=[]; word="abc"; '
RUNNER = Path(__file__).with_name('runner.py')
SUBPROCESS_TIMEOUT = 5


class ForEachTests(unittest.TestCase):
    def test_keyword_boundary(self):
        self.assertEqual([t['tag'] for t in tokenize('for in format inside')],
                         ['for', 'in', 'identifier', 'identifier', None])

    def test_results(self):
        cases = [
            ('out=[]; for (x in items) { out=out+[x] }', 'out', [1, 2, 3]),
            ('out=""; for (c in word) { out=c+out }', 'out', 'cba'),
            ('n=0; for (x in empty) { n=n+1 }', 'n', 0),
            ('n=0; for (c in "") { n=n+1 }', 'n', 0),
            ('out=[]; for (x in items) { for (c in word) { out=out+[string(x)+c] } }',
             'out', ['1a', '1b', '1c', '2a', '2b', '2c', '3a', '3b', '3c']),
            ('fs=[]; for (x in items) { fs=fs+[function() { return x }] }; out=fs[0]()',
             'out', 3),
            ('out=[]; for (x in items) { items[2]=99; out=out+[x] }', 'out', [1, 2, 3]),
            ('out=[]; for (x in items) { if (x == 1) { continue }; if (x == 3) { break }; out=out+[x] }',
             'out', [2]),
            ('function f() { for (x in items) { if (x == 2) { return x } }; return 0 }; out=f()',
             'out', 2),
        ]
        for source, name, expected in cases:
            with self.subTest(source=source):
                result, env = evaluate_source(PRELUDE + source)
                self.assertEqual(result, (None, None))
                self.assertEqual(env[name], expected)

    def test_empty_collection_leaves_variable_unbound(self):
        _, env = evaluate_source(PRELUDE + 'for (x in empty) { }')
        self.assertNotIn('x', env)

    def test_exit_propagates(self):
        result, env = evaluate_source(PRELUDE + 'for (x in items) { if (x == 2) { exit(x) }; last=x }')
        self.assertEqual(result, (2, 'exit'))
        self.assertEqual(env['last'], 1)

    def test_errors(self):
        for source, error in [('for (x in 5) { }', TypeError),
                              ('for (x in {}) { }', TypeError),
                              ('for x in items { }', SyntaxError),
                              ('for (x in items) x=1', SyntaxError),
                              ('for (1 in items) { }', SyntaxError),
                              ('for (x items) { }', SyntaxError)]:
            with self.subTest(source=source), self.assertRaises(error):
                evaluate_source(PRELUDE + source)

    def test_runner_output_and_status(self):
        for source, code, output, message in [
                ('for (item in ["a", "b"]) { print(item) }', 0, 'a\nb\n', ''),
                ('for (x in [1, 2, 3]) { if (x == 2) { exit(x) }; print(x) }', 2, '1\n', ''),
                ('for (x in 5) { print(x) }', 1, '', 'TypeError: for collection must be a list or string')]:
            with self.subTest(source=source):
                result = subprocess.run([sys.executable, str(RUNNER), source],
                                        capture_output=True, text=True,
                                        stdin=subprocess.DEVNULL,
                                        timeout=SUBPROCESS_TIMEOUT)
                self.assertEqual(result.returncode, code)
                self.assertEqual(result.stdout, output)
                self.assertIn(message, result.stderr)


if __name__ == '__main__':
    unittest.main()
