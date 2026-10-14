import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import evaluator
from parser import parse, parse_expression
from tokenizer import tokenize


class ConditionalTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    def test_single_branch(self):
        result, env = self.run_source('if (true) { x=1 }')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['x'], 1)

        result, env = self.run_source('if (false) { x=1 }')
        self.assertEqual(result, (None, None))
        self.assertNotIn('x', env)

    def test_two_branch(self):
        for condition, expected in [('true', 1), ('false', 2)]:
            with self.subTest(condition=condition):
                _, env = self.run_source(f'if ({condition}) {{ x=1 }} else {{ x=2 }}')
                self.assertEqual(env['x'], expected)

    def test_condition_requires_boolean(self):
        for condition in ('1', '0', '"true"', '""'):
            with self.subTest(condition=condition), self.assertRaises(TypeError):
                self.run_source(f'if ({condition}) {{ x=1 }}')

    def test_empty_block_is_legal(self):
        # A block's statement_list is optional: "{}" is empty, not an error.
        result, env = self.run_source('x=1; if (true) { }; x=2')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['x'], 2)

        result, env = self.run_source('if (false) { } else { x=1 }')
        self.assertEqual(env['x'], 1)

        result, env = self.run_source('if (true) { } else { x=1 }')
        self.assertNotIn('x', env)

    def test_semicolon_only_blocks(self):
        for body in (';', ';;;', '; // comment\n ;'):
            with self.subTest(body=body):
                result, env = self.run_source(
                    f'x=1; if (true) {{ {body} }}; '
                    f'if (false) {{ x=99 }} else {{ {body} }}; x=2')
                self.assertEqual(result, (None, None))
                self.assertEqual(env['x'], 2)
        result, env = self.run_source('if (true) { ;;; x=1;;; y=2;;; }')
        self.assertEqual(result, (None, None))
        self.assertEqual((env['x'], env['y']), (1, 2))

    def test_exit_in_condition_skips_both_branches(self):
        # An exit found while evaluating the condition propagates immediately:
        # it is never checked against the boolean requirement, and neither
        # branch runs.
        result, env = self.run_source('if (exit(7)) { x=1 } else { x=2 }')
        self.assertEqual(result, (7, 'exit'))
        self.assertNotIn('x', env)

    def test_condition_evaluated_exactly_once(self):
        with patch('builtins.input', return_value='true') as fake_input:
            _, env = self.run_source('if (boolean(input())) { x=1 } else { x=2 }')
        fake_input.assert_called_once_with()
        self.assertEqual(env['x'], 1)

    def test_multi_statement_block(self):
        _, env = self.run_source('if (true) { x=1; y=2; z=x+y }')
        self.assertEqual((env['x'], env['y'], env['z']), (1, 2, 3))

    def test_nested_conditionals(self):
        source = '''
            if (true) {
                if (false) { x=1 } else { x=2 }
            } else {
                x=3
            }
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['x'], 2)

    def test_else_if_chain_via_nested_braces(self):
        # This grammar has no "else if" shortcut: a chain is an else-block
        # containing its own if_statement, written out with its own braces.
        source = '''
            grade = 85;
            if (grade >= 90) {
                letter="A"
            } else {
                if (grade >= 80) {
                    letter="B"
                } else {
                    letter="C"
                }
            }
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['letter'], 'B')

    def test_unselected_branch_is_never_evaluated(self):
        # The branch not taken must not read input, exit, or fail an assertion.
        with patch('builtins.input') as read:
            result, env = self.run_source(
                'if (false) { x=number(input()) } else { x=1 }')
        read.assert_not_called()
        self.assertEqual(env['x'], 1)

        result, env = self.run_source('if (false) { exit(9) } else { x=1 }')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['x'], 1)

        result, env = self.run_source(
            'if (true) { x=1 } else { assert false, "should not run" }')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['x'], 1)

    def test_status_escapes_nested_blocks_and_stops_later_statements(self):
        result, env = self.run_source(
            'x=1; if (true) { if (true) { exit(7) } }; x=2')
        self.assertEqual(result, (7, 'exit'))
        self.assertEqual(env['x'], 1)

        result, env = self.run_source(
            'x=1; if (true) { exit(7); x=99 }; x=2')
        self.assertEqual(result, (7, 'exit'))
        self.assertEqual(env['x'], 1)

    def test_status_escapes_the_else_branch(self):
        result, env = self.run_source(
            'x=1; if (false) { x=99 } else { exit(4); x=98 }; x=2')
        self.assertEqual(result, (4, 'exit'))
        self.assertEqual(env['x'], 1)

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result, env = self.run_source(
                'x=1; if (false) { } else { assert false, "else failed" }; x=2')
        self.assertEqual(result, (1, 'exit'))
        self.assertEqual(env['x'], 1)
        self.assertEqual(err.getvalue(), 'Assertion failed: else failed\n')

    def test_if_is_a_statement_not_an_expression(self):
        for source in ('x = if (true) { 1 }', 'print(if (true) { 1 })'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_unbraced_bodies_are_rejected(self):
        for source in ('if (true) x=1', 'if (true) { x=1 } else x=2'):
            with self.subTest(source=source):
                with self.assertRaises(SyntaxError) as raised:
                    parse(tokenize(source))
                self.assertIn("Expected '{'", str(raised.exception))

    def test_braced_single_statement_and_nested_blocks_parse(self):
        parse(tokenize('if (true) { x=1 }'))
        parse(tokenize('if (true) { x=1 } else { x=2 }'))
        parse(tokenize('if (true) { if (false) { x=1 } else { x=2 } }'))
        parse(tokenize('if (true) { }'))
        parse(tokenize('if (true) { } else { }'))

    def test_runner_handles_if(self):
        runner = Path(__file__).with_name('runner.py')
        cases = [
            ('if (true) { print(1) } else { print(2) }', 0, '1\n'),
            ('if (false) { print(1) } else { print(2) }', 0, '2\n'),
            ('if (true) { exit(3) }; print(9)', 3, ''),
        ]
        for source, code, output in cases:
            result = subprocess.run([sys.executable, str(runner), source],
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, code)
            self.assertEqual(result.stdout, output)
            self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
