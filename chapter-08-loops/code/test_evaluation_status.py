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


class EvaluationStatusTests(unittest.TestCase):
    def expression(self, source, environment=None):
        node, rest = parse_expression(tokenize(source))
        self.assertIsNone(rest[0]["tag"])
        if environment is None:
            environment = {}
        return evaluator.evaluate(node, environment)

    def test_normal_values_and_statuses(self):
        for source, value in [('42', 42), ('true', True), ('"hello"', 'hello'),
                              ('number("2")+3', 5), ('type(false)', 'boolean'),
                              ('false or true', True), ('1<2', True)]:
            with self.subTest(source=source):
                self.assertEqual(self.expression(source), (value, None))
        self.assertEqual(evaluator.evaluate_source('x=2')[0], (None, None))

    def test_exit_defaults_and_nested_exit(self):
        self.assertEqual(self.expression('exit()'), (0, 'exit'))
        self.assertEqual(self.expression('exit(7)'), (7, 'exit'))
        self.assertEqual(self.expression('exit(exit(9))'), (9, 'exit'))
        for source in ('exit(true)', 'exit(2.5)', 'exit("7")'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                self.expression(source)

    def test_unary_and_conversion_propagation(self):
        for source in ('-exit(7)', 'not exit(7)', 'number(exit(7))',
                       'string(exit(7))', 'boolean(exit(7))', 'type(exit(7))'):
            with self.subTest(source=source):
                self.assertEqual(self.expression(source), (7, 'exit'))

    def test_binary_propagation_before_later_work(self):
        for operator in ('+', '-', '*', '/', '==', '!=', '<', '<=', '>', '>=',
                         'and', 'or'):
            with self.subTest(operator=operator), patch('builtins.input') as read:
                self.assertEqual(self.expression(f'exit(7) {operator} input()'),
                                 (7, 'exit'))
                read.assert_not_called()
        # Needed right operands propagate before applying the operation or
        # checking the exit value against the operation's operand types.
        for source in ('1+exit(7)', '1-exit(7)', '1*exit(7)', '1/exit(7)',
                       '1==exit(7)', '1!=exit(7)', '1<exit(7)', '1<=exit(7)',
                       '1>exit(7)', '1>=exit(7)', 'true and exit(7)',
                       'false or exit(7)'):
            with self.subTest(source=source):
                self.assertEqual(self.expression(source), (7, 'exit'))

    def test_short_circuit_still_skips_exit(self):
        self.assertEqual(self.expression('false && exit(7)'), (False, None))
        self.assertEqual(self.expression('true || exit(7)'), (True, None))

    def test_input_prompt_exits_before_reading(self):
        env = {'__input': 'saved'}
        with patch('builtins.input') as read:
            self.assertEqual(self.expression('input(exit(7))', env), (7, 'exit'))
        read.assert_not_called()
        self.assertEqual(env['__input'], 'saved')

    def test_assignment_print_and_statement_list_stop(self):
        env = {'x': 3, '__output': 'previous', '__input': 'saved'}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input') as read:
            result, _ = evaluator.evaluate_source(
                'x=exit(7);print(input());later=2', env)
        self.assertEqual(result, (7, 'exit'))
        self.assertEqual(env, {'x': 3, '__output': 'previous', '__input': 'saved'})
        self.assertEqual(output.getvalue(), '')
        read.assert_not_called()
        with contextlib.redirect_stdout(output):
            result, _ = evaluator.evaluate_source('print(exit(8));later=2', env)
        self.assertEqual(result, (8, 'exit'))
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(env['__output'], 'previous')
        self.assertNotIn('later', env)

    def test_propagation_does_not_undo_earlier_effects(self):
        env = {'__input': 'first'}
        self.assertEqual(self.expression('input()+exit(7)', env), (7, 'exit'))
        self.assertEqual(env['__input'], '')

    def test_generic_status_is_not_limited_to_exit(self):
        # A synthetic child stands in for future break/continue/return nodes.
        # Ordinary parents must carry unfamiliar statuses without consuming them.
        original = evaluator.evaluate
        for status in ('break', 'continue', 'return'):
            for source in ('x=marker+missing', 'x=type(marker)', 'print(marker)'):
                def child(node, env):
                    if node.get('tag') == 'identifier' and node.get('value') == 'marker':
                        return 17, status
                    return original(node, env)
                with self.subTest(status=status, source=source):
                    env = {}
                    with patch.object(evaluator, 'evaluate', side_effect=child):
                        self.assertEqual(original(parse(tokenize(source)), env),
                                         (17, status))
                    self.assertNotIn('x', env)
                    self.assertEqual(env['__output'], '')

    def test_exit_keyword_and_syntax(self):
        self.assertEqual([t['tag'] for t in tokenize('exit exiting exit_code')],
                         ['exit', 'identifier', 'identifier', None])
        for source in ('exit=1', 'exit', 'exit(1,2)', 'exit(', 'exit(1);x=1+'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_runner_handles_exit(self):
        runner = Path(__file__).with_name('runner.py')
        for source, code, output in [('print(1);exit(7);print(2)', 7, '1\n'),
                                      ('exit();print(2)', 0, ''),
                                      ('print(3)', 0, '3\n')]:
            result = subprocess.run([sys.executable, str(runner), source],
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, code)
            self.assertEqual(result.stdout, output)
            self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
