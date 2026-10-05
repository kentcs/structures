from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import evaluator
from parser import parse
from tokenizer import tokenize

# A regression that breaks loop termination must fail fast, not hang the suite.
SUBPROCESS_TIMEOUT = 5


class LoopTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    def test_zero_iterations(self):
        result, env = self.run_source('while (false) { x=1 }')
        self.assertEqual(result, (None, None))
        self.assertNotIn('x', env)

    def test_one_iteration(self):
        result, env = self.run_source('i=0; while (i < 1) { i=i+1 }')
        self.assertEqual(env['i'], 1)

    def test_repeated_state_changes(self):
        result, env = self.run_source(
            'i=0; total=0; while (i < 5) { i=i+1; total=total+i }')
        self.assertEqual((env['i'], env['total']), (5, 15))

    def test_condition_requires_boolean(self):
        with self.assertRaises(TypeError):
            self.run_source('while (1) { x=1 }')

    def test_unbraced_body_and_missing_parens_rejected(self):
        for source in ('while (true) x=1', 'while true { x=1 }',
                       'while (true { x=1 }'):
            with self.subTest(source=source):
                with self.assertRaises(SyntaxError):
                    parse(tokenize(source))

    def test_break_stops_loop_and_skips_later_body_statements(self):
        result, env = self.run_source(
            'i=0; while (true) { i=i+1; if (i == 3) { break }; last=i }')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['i'], 3)
        # last=i never runs on the iteration where break fires.
        self.assertEqual(env['last'], 2)

    def test_continue_skips_later_body_statements(self):
        result, env = self.run_source(
            'i=0; skipped=0; while (i < 5) { i=i+1; '
            'if (i == 3) { continue }; skipped=skipped+1 }')
        self.assertEqual(env['i'], 5)
        # skipped=skipped+1 runs for every i except 3.
        self.assertEqual(env['skipped'], 4)

    def test_continue_reevaluates_condition_exactly_once(self):
        # boolean(input()) ties each condition check to one input() call.
        with patch('builtins.input',
                   side_effect=['true', 'true', 'true', 'false']) as fake_input:
            result, env = self.run_source(
                'i=0; last=0; while (boolean(input())) { '
                'i=i+1; if (i == 2) { continue }; last=i }')
        self.assertEqual(fake_input.call_count, 4)
        self.assertEqual(env['i'], 3)
        self.assertEqual(env['last'], 3)

    def test_continue_does_not_perform_an_implicit_update(self):
        # The state update happens before the skipped statements, not as a
        # side effect of continue itself.
        result, env = self.run_source(
            'i=0; while (i < 3) { i=i+1; if (true) { continue }; i=i+100 }')
        self.assertEqual(env['i'], 3)

    def test_exit_propagates_instead_of_being_consumed(self):
        result, env = self.run_source('i=0; while (true) { i=i+1; exit(i) }')
        self.assertEqual(result, (1, 'exit'))
        self.assertEqual(env['i'], 1)

    def test_exit_from_condition_propagates(self):
        result, env = self.run_source('while (boolean(exit(9))) { x=1 }')
        self.assertEqual(result, (9, 'exit'))
        self.assertNotIn('x', env)

    def test_failed_assertion_inside_loop_body_propagates(self):
        result, env = self.run_source(
            'i=0; while (i < 5) { i=i+1; assert i < 3, "too far" }')
        self.assertEqual(result, (1, 'exit'))
        self.assertEqual(env['i'], 3)

    def test_nested_loops_inner_break_then_more_outer_work(self):
        source = '''
            outer=0; total=0;
            while (outer < 3) {
                outer=outer+1;
                inner=0;
                while (true) {
                    inner=inner+1;
                    if (inner == 2) { break };
                    total=total+1;
                };
                total=total+100;
            };
        '''
        result, env = self.run_source(source)
        self.assertEqual(result, (None, None))
        self.assertEqual(env['outer'], 3)
        # Each inner loop contributes one total+1 before its break, plus the
        # outer loop's own total+100 after the inner loop finishes.
        self.assertEqual(env['total'], 3 + 300)

    def test_break_and_continue_require_an_enclosing_loop(self):
        # Neither is rejected during parsing: both are ordinary statuses
        # that propagate like any other, so misuse surfaces at evaluation.
        for keyword in ('break', 'continue'):
            with self.subTest(keyword=keyword):
                result, env = self.run_source(keyword)
                self.assertEqual(result, (None, keyword))

    def test_runner_rejects_break_and_continue_outside_a_loop(self):
        runner = Path(__file__).with_name('runner.py')
        for keyword in ('break', 'continue'):
            with self.subTest(keyword=keyword):
                result = subprocess.run([sys.executable, str(runner), keyword],
                                        capture_output=True, text=True,
                                        stdin=subprocess.DEVNULL,
                                        timeout=SUBPROCESS_TIMEOUT)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'Unhandled evaluation status: {keyword}',
                              result.stderr)

    def test_runner_handles_while(self):
        runner = Path(__file__).with_name('runner.py')
        cases = [
            ('i=0; while (i < 3) { print(i); i=i+1 }', 0, '0\n1\n2\n'),
            ('while (false) { print(1) }; print(2)', 0, '2\n'),
            ('i=0; while (true) { i=i+1; if (i == 4) { exit(i) } }', 4, ''),
        ]
        for source, code, output in cases:
            result = subprocess.run([sys.executable, str(runner), source],
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL,
                                    timeout=SUBPROCESS_TIMEOUT)
            self.assertEqual(result.returncode, code)
            self.assertEqual(result.stdout, output)
            self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
