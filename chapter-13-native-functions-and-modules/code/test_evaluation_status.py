import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import evaluator
from parser import parse, parse_expression, parse_statement
from tokenizer import tokenize


def exit_node(value=7):
    return {"tag": "exit", "expression": {"tag": "number", "value": value}}


class EvaluationStatusTests(unittest.TestCase):
    def expression(self, source, environment=None):
        node, rest = parse_expression(tokenize(source))
        self.assertIsNone(rest[0]["tag"])
        if environment is None:
            environment = {}
        return evaluator.evaluate(node, environment)

    def evaluate_program(self, statements, environment=None):
        # ===== exit no longer nests inside a larger expression, so a
        # program that needs one mid-expression is built directly instead
        # of parsed from source text, the same way evaluate_source builds
        # one from text. =====
        if environment is None:
            environment = {}
        ast = {"tag": "program",
               "statements": {"tag": "statement_list", "statements": statements}}
        return evaluator.evaluate(ast, environment), environment

    def test_normal_values_and_statuses(self):
        for source, value in [('42', 42), ('true', True), ('"hello"', 'hello'),
                              ('number("2")+3', 5), ('type(false)', 'boolean'),
                              ('false or true', True), ('1<2', True)]:
            with self.subTest(source=source):
                self.assertEqual(self.expression(source), (value, None))
        self.assertEqual(evaluator.evaluate_source('x=2')[0], (None, None))

    def test_exit_defaults_and_nested_exit(self):
        # exit() and exit(7), standing alone, are still legal statements,
        # parsed the ordinary way through parse_statement; what this test
        # checks is the evaluator's own handling of the resulting node.
        statement, rest = parse_statement(tokenize('exit()'))
        self.assertIsNone(rest[0]["tag"])
        self.assertEqual(evaluator.evaluate(statement, {}), (0, 'exit'))
        statement, rest = parse_statement(tokenize('exit(7)'))
        self.assertIsNone(rest[0]["tag"])
        self.assertEqual(evaluator.evaluate(statement, {}), (7, 'exit'))
        # exit(exit(9)) is no longer legal source: exit cannot nest inside
        # another expression, including another exit's own argument. The
        # evaluator's own handling of a status produced while evaluating
        # the argument is still checked directly, on a hand-built node.
        nested = {"tag": "exit", "expression": exit_node(9)}
        self.assertEqual(evaluator.evaluate(nested, {}), (9, 'exit'))
        for source in ('exit(true)', 'exit(2.5)', 'exit("7")'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                statement, _ = parse_statement(tokenize(source))
                evaluator.evaluate(statement, {})

    def test_unary_and_conversion_propagation(self):
        # exit(7) can no longer sit inside a larger expression in real
        # source; each case here builds the surrounding node directly and
        # gives it a hand-built exit node as its operand, to check the
        # evaluator's own status handling independent of what the parser
        # currently admits as legal source text.
        cases = [
            {"tag": "unary-", "operand": exit_node()},
            {"tag": "not", "operand": exit_node()},
            {"tag": "number_conversion", "expression": exit_node()},
            {"tag": "string_conversion", "expression": exit_node()},
            {"tag": "boolean_conversion", "expression": exit_node()},
            {"tag": "type_query", "expression": exit_node()},
        ]
        for node in cases:
            with self.subTest(tag=node["tag"]):
                self.assertEqual(evaluator.evaluate(node, {}), (7, 'exit'))

    def test_binary_propagation_before_later_work(self):
        for op in ('+', '-', '*', '/', '==', '!=', '<', '<=', '>', '>=',
                  'and', 'or'):
            with self.subTest(operator=op), patch('builtins.input') as read:
                node = {"tag": op, "left": exit_node(7),
                        "right": {"tag": "input", "prompt": None}}
                self.assertEqual(evaluator.evaluate(node, {}), (7, 'exit'))
                read.assert_not_called()
        # Needed right operands propagate before applying the operation or
        # checking the exit value against the operation's operand types.
        left_operands = {'+': 1, '-': 1, '*': 1, '/': 1, '==': 1, '!=': 1,
                         '<': 1, '<=': 1, '>': 1, '>=': 1,
                         'and': True, 'or': False}
        for op, left_value in left_operands.items():
            with self.subTest(operator=op):
                left_tag = "boolean" if op in ("and", "or") else "number"
                node = {"tag": op, "left": {"tag": left_tag, "value": left_value},
                        "right": exit_node(7)}
                self.assertEqual(evaluator.evaluate(node, {}), (7, 'exit'))

    def test_short_circuit_still_skips_exit(self):
        # false && exit(7) and true || exit(7) are no longer legal source
        # either, for the same reason; built directly, these still prove
        # the right operand is never reached, since reaching it would
        # produce an "exit" status instead of the plain value returned here.
        and_node = {"tag": "and", "left": {"tag": "boolean", "value": False},
                   "right": exit_node(7)}
        self.assertEqual(evaluator.evaluate(and_node, {}), (False, None))
        or_node = {"tag": "or", "left": {"tag": "boolean", "value": True},
                  "right": exit_node(7)}
        self.assertEqual(evaluator.evaluate(or_node, {}), (True, None))

    def test_input_prompt_exits_before_reading(self):
        env = {'__input': 'saved'}
        node = {"tag": "input", "prompt": exit_node(7)}
        with patch('builtins.input') as read:
            self.assertEqual(evaluator.evaluate(node, env), (7, 'exit'))
        read.assert_not_called()
        self.assertEqual(env['__input'], 'saved')

    def test_assignment_print_and_statement_list_stop(self):
        env = {'x': 3, '__output': 'previous', '__input': 'saved'}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch('builtins.input') as read:
            result, _ = self.evaluate_program([
                {"tag": "assign", "target": {"tag": "identifier", "value": "x"},
                 "expression": exit_node(7)},
                {"tag": "print", "expression": {"tag": "input", "prompt": None}},
                {"tag": "assign", "target": {"tag": "identifier", "value": "later"},
                 "expression": {"tag": "number", "value": 2}},
            ], env)
        self.assertEqual(result, (7, 'exit'))
        self.assertEqual(env, {'x': 3, '__output': 'previous', '__input': 'saved'})
        self.assertEqual(output.getvalue(), '')
        read.assert_not_called()
        with contextlib.redirect_stdout(output):
            result, _ = self.evaluate_program([
                {"tag": "print", "expression": exit_node(8)},
                {"tag": "assign", "target": {"tag": "identifier", "value": "later"},
                 "expression": {"tag": "number", "value": 2}},
            ], env)
        self.assertEqual(result, (8, 'exit'))
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(env['__output'], 'previous')
        self.assertNotIn('later', env)

    def test_propagation_does_not_undo_earlier_effects(self):
        env = {'__input': 'first'}
        node = {"tag": "+", "left": {"tag": "input", "prompt": None},
                "right": exit_node(7)}
        self.assertEqual(evaluator.evaluate(node, env), (7, 'exit'))
        self.assertEqual(env['__input'], '')

    def test_generic_status_is_not_limited_to_exit(self):
        # A synthetic child stands in for future break/continue/return nodes.
        # Ordinary parents must carry unfamiliar statuses without consuming
        # them. This evaluates the inner statement directly, not the full
        # parsed "program" node: since Chapter 11, "program" is itself a
        # boundary that rejects a stray break or continue (see
        # test_functions.py), so reaching it here would test that
        # boundary by accident instead of the ordinary-parent pass-through
        # this test is actually about.
        original = evaluator.evaluate
        for status in ('break', 'continue', 'return'):
            for source in ('x=marker+missing', 'x=type(marker)', 'print(marker)'):
                def child(node, env):
                    if node.get('tag') == 'identifier' and node.get('value') == 'marker':
                        return 17, status
                    return original(node, env)
                with self.subTest(status=status, source=source):
                    env = {}
                    program = parse(tokenize(source))
                    statement = program['statements']['statements'][0]
                    with patch.object(evaluator, 'evaluate', side_effect=child):
                        self.assertEqual(original(statement, env),
                                         (17, status))
                    self.assertNotIn('x', env)
                    self.assertNotIn('__output', env)

    def test_exit_keyword_and_syntax(self):
        self.assertEqual([t['tag'] for t in tokenize('exit exiting exit_code')],
                         ['exit', 'identifier', 'identifier', None])
        for source in ('exit=1', 'exit', 'exit(1,2)', 'exit(', 'exit(1);x=1+'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_exit_rejected_in_expression_position(self):
        # The hand-built AST tests above pin the evaluator's own status
        # handling, but none of them pin the parser rule itself: that
        # removing exit from parse_factor is what makes exit statement-only.
        # Each of these would parse successfully if exit were still a
        # factor -- none fails for any other reason -- so each one directly
        # checks that removal, not just some unrelated syntax restriction.
        # x=exit(7) in particular would now be legal as a general expression
        # statement if exit were a factor, so it still needs its own case.
        for source in ('x=exit(7)', 'print(exit(7))', 'exit(exit(7))',
                       'numbers[exit(7)]'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))
        # The positive control: exit(7) alone, with nothing asking it to be
        # part of a larger expression, still parses and runs fine.
        statement, rest = parse_statement(tokenize('exit(7)'))
        self.assertIsNone(rest[0]["tag"])
        self.assertEqual(evaluator.evaluate(statement, {}), (7, 'exit'))

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
