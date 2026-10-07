import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class AssertionTests(unittest.TestCase):
    def test_success_continues(self):
        result, env = evaluate_source('assert 1<2,"Expected increasing values";assert true,"ok";done=3')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['done'], 3)

    def test_failure_reports_once_and_prevents_later_effects(self):
        for statement, message in [('assert 1==2,"wrong value"',
                                    'Assertion failed: wrong value'),
                                   ('assert false,""', 'Assertion failed: '),
                                   ('assert false,"line\\nnext"',
                                    'Assertion failed: line\nnext')]:
            with self.subTest(statement=statement):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                        patch('builtins.input') as read:
                    result, env = evaluate_source(
                        'before=1;' + statement + ';print(input());after=2')
                self.assertEqual(result, (1, 'exit'))
                self.assertEqual(env['before'], 1)
                self.assertNotIn('after', env)
                self.assertEqual(env['__output'], '')
                self.assertEqual(out.getvalue(), '')
                self.assertEqual(err.getvalue(), message + '\n')
                read.assert_not_called()

    def test_condition_runs_once_and_propagates_exit(self):
        with patch('builtins.input', return_value='yes') as read:
            self.assertEqual(evaluate_source('assert input()=="yes","Expected yes"')[0], (None, None))
        read.assert_called_once_with()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(evaluate_source('assert exit(7),"unused"')[0], (7, 'exit'))
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(evaluate_source('assert true or exit(7),"Expected true"')[0], (None, None))

    def test_requires_boolean(self):
        for expression in ('0', '1', '"true"'):
            with self.subTest(expression=expression), self.assertRaises(TypeError):
                evaluate_source('assert ' + expression + ',"Requires boolean"')

    def test_syntax_and_keyword_boundaries(self):
        self.assertEqual([t['tag'] for t in tokenize('assert assertion assert_value')],
                         ['assert', 'identifier', 'identifier', None])
        for source in ('assert', 'assert true', 'assert false;',
                       'assert true;done=1', 'assert true,', 'assert true,42',
                       'assert true,message', 'assert true,"a","b"',
                       'assert=true', 'x=assert true', 'print(assert true)',
                       'assert true,"a"+"b"', 'assert false,"failure";x=1+'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_runner_handles_assertion_exit_without_duplicate_diagnostic(self):
        runner = Path(__file__).with_name('runner.py')
        for source, code, message in [('assert true,"Expected true"', 0, ''),
                                      ('assert false,"stopped";print(9)', 1, 'Assertion failed: stopped\n'),
                                      ('assert false,"bad value"', 1,
                                       'Assertion failed: bad value\n')]:
            result = subprocess.run([sys.executable, str(runner), source],
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, code)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, message)


if __name__ == '__main__':
    unittest.main()
