from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import unittest

import evaluator
from evaluator import is_function
from parser import parse
from tokenizer import tokenize

SUBPROCESS_TIMEOUT = 5


class FunctionTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    # ===== Function literals and the named-definition sugar =====

    def test_function_literal_is_a_value(self):
        result, env = self.run_source('f = function(x) { return x }')
        self.assertEqual(result, (None, None))
        self.assertTrue(is_function(env['f']))
        self.assertEqual(env['f']['parameters'], ['x'])

    def test_named_definition_is_sugar_for_assignment(self):
        sugar = parse(tokenize('function double(x) { return x+x }'))
        resolved = parse(tokenize('double = function(x) { return x+x }'))
        self.assertEqual(sugar, resolved)

    def test_named_definition_binds_in_the_current_environment(self):
        result, env = self.run_source('function f(x) { return x }')
        self.assertTrue(is_function(env['f']))

    # ===== A function value is a dict, but not Vertex data =====

    def test_two_functions_with_identical_source_are_not_equal(self):
        # FUNCTION_KEY's value counts up by one per function literal
        # evaluated, so two separately built functions disagree on it even
        # when their parameters and body are textually identical -- the
        # same outcome Python's default identity comparison gave for free
        # back when Function was its own class.
        result, env = self.run_source('''
            a = function(x) { return x };
            b = function(x) { return x };
            same = a == b;
        ''')
        self.assertFalse(env['same'])

    def test_a_function_equals_itself(self):
        result, env = self.run_source('a = function(x) { return x }; same = a == a;')
        self.assertTrue(env['same'])

    def test_copy_of_a_function_is_itself_not_a_deep_copy(self):
        # copy() must satisfy x == copy(x) for every x, including a
        # function -- but a function's body is an AST, not Vertex data,
        # so copying one has to hand back the same value rather than
        # deep-copying its internals the way copy() does for a list or
        # object.
        result, env = self.run_source('''
            a = function(x) { return x };
            b = copy(a);
            same = b == a;
            kind = type(b);
        ''')
        self.assertTrue(env['same'])
        self.assertEqual(env['kind'], 'function')
        self.assertIs(env['b'], env['a'])

    def test_indexing_or_writing_through_a_function_value_rejected(self):
        for source in ('a = function(x) { return x }; a["parameters"];',
                       'a = function(x) { return x }; a["parameters"] = [];'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                self.run_source(source)

    # ===== Calling: arity, parameters, locals =====

    def test_call_with_no_parameters(self):
        result, env = self.run_source(
            'function greet() { return "hi" }; print(greet())')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['__output'], 'hi')

    def test_call_with_several_parameters(self):
        result, env = self.run_source(
            'function add3(a, b, c) { return a+b+c }; print(add3(1, 2, 3))')
        self.assertEqual(env['__output'], '6')

    def test_too_few_arguments_rejected(self):
        with self.assertRaises(TypeError) as raised:
            self.run_source('function add(a, b) { return a+b }; add(1)')
        self.assertIn('expects 2 argument', str(raised.exception))

    def test_too_many_arguments_rejected(self):
        with self.assertRaises(TypeError) as raised:
            self.run_source('function add(a, b) { return a+b }; add(1, 2, 3)')
        self.assertIn('expects 2 argument', str(raised.exception))

    def test_calling_a_non_function_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x=5; x()')

    def test_local_variables_do_not_leak_into_the_caller(self):
        result, env = self.run_source(
            'function f(x) { y = x*2; return y+1 }; print(f(5))')
        self.assertEqual(env['__output'], '11')
        self.assertNotIn('y', env)

    def test_each_call_gets_its_own_locals(self):
        # Calling f twice must not let the second call see the first
        # call's own local, even though both are named the same.
        result, env = self.run_source('''
            function f(x) { doubled = x*2; return doubled };
            a = f(3);
            b = f(100);
        ''')
        self.assertEqual((env['a'], env['b']), (6, 200))
        self.assertNotIn('doubled', env)

    # ===== return, and falling off the end =====

    def test_return_stops_the_function_immediately(self):
        result, env = self.run_source('''
            function f(x) {
                if (x < 0) { return "negative" };
                return "non-negative"
            };
            print(f(-1)); print(f(1))
        ''')
        # Only the second print's output survives in __output, but both
        # ran: check by tracing through a list instead.
        self.assertEqual(result, (None, None))

    def test_return_value_reaches_the_caller(self):
        result, env = self.run_source(
            'function f(x) { return x < 0 }; y = f(-3)')
        self.assertEqual(env['y'], True)

    def test_falling_off_the_end_yields_null(self):
        result, env = self.run_source('function f() { x=1 }; y=f()')
        self.assertIsNone(env['y'])

    def test_bare_return_yields_null(self):
        result, env = self.run_source('function f() { return }; y=f()')
        self.assertIsNone(env['y'])

    def test_return_inside_nested_blocks_still_escapes_the_function(self):
        result, env = self.run_source('''
            function f(x) {
                if (true) {
                    if (x > 0) { return "positive" }
                };
                return "other"
            };
            y = f(5)
        ''')
        self.assertEqual(env['y'], 'positive')

    # ===== Calls inside larger expressions =====

    def test_call_inside_arithmetic(self):
        result, env = self.run_source(
            'function square(x) { return x*x }; y = 1 + square(3) + 1')
        self.assertEqual(env['y'], 11)

    def test_call_inside_a_condition(self):
        result, env = self.run_source('''
            function isPositive(x) { return x > 0 };
            if (isPositive(5)) { y=1 } else { y=2 }
        ''')
        self.assertEqual(env['y'], 1)

    def test_nested_calls(self):
        result, env = self.run_source('''
            function square(x) { return x*x };
            function sumSquares(a, b) { return square(a) + square(b) };
            y = sumSquares(3, 4)
        ''')
        self.assertEqual(env['y'], 25)

    def test_call_chained_with_index_and_field_suffixes(self):
        result, env = self.run_source('''
            function makeList() { return [1, 2, 3] };
            function makeRecord() { return {"value": 42} };
            a = makeList()[1];
            b = makeRecord().value;
        ''')
        self.assertEqual((env['a'], env['b']), (2, 42))

    def test_a_calls_result_can_be_called_again(self):
        # make()'s result is a function; calling that result with (3, 4)
        # is a second, immediate call, chained the same way funcs[0](x)
        # chains an index suffix with a call suffix.
        result, env = self.run_source('''
            function make() { return function(a, b) { return a + b } };
            y = make()(3, 4)
        ''')
        self.assertEqual(env['y'], 7)

    def test_dynamic_scoping_cannot_see_a_defining_calls_own_locals(self):
        # This is the limitation the next chapter exists to fix. a lives
        # only inside makeAdder's own call frame; the function returned
        # from it does not retain that frame, so when it is later called,
        # its new call environment chains to wherever *that* call
        # happened, not back to makeAdder's. a is unreachable there.
        with self.assertRaises(ValueError) as raised:
            self.run_source('''
                function makeAdder(a) { return function(b) { return a + b } };
                y = makeAdder(1)(2)
            ''')
        self.assertEqual(str(raised.exception), 'Unknown identifier: a')

    def test_bare_call_statement_discards_its_result(self):
        result, env = self.run_source(
            'function sideEffect() { print("ran"); return 99 }; sideEffect()')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['__output'], 'ran')
        self.assertNotIn('99', env)

    def test_exit_from_an_embedded_function_call_propagates(self):
        # exit itself still cannot nest inside a larger expression, but a
        # call can, and a call whose body exits carries that status out
        # through whatever expression the call sits inside -- the same way
        # any other status already propagates. This is what fulfills
        # Chapter 6's promise that a later chapter's function calls would
        # give a real way to exit from something nested.
        result, env = self.run_source('''
            numbers = [10, 20, 30];
            function stopAt(code) { exit(code); };
            x = numbers[stopAt(5)];
        ''')
        self.assertEqual(result, (5, 'exit'))
        self.assertNotIn('x', env)

    def test_any_expression_may_be_a_statement(self):
        # ===== CHAPTER 11: expression_statement ::= expression =====
        # A bare expression statement is legal even when it has no effect
        # at all -- the grammar does not try to rule out useless statements.
        result, env = self.run_source('1 + 1;')
        self.assertEqual(result, (None, None))
        self.assertEqual(env, {'__input': '', '__output': ''})

    def test_a_suffix_chain_ending_in_a_call_is_a_legal_bare_statement(self):
        # Any mix of indexing and calls is legal as a bare statement, not
        # just a single trailing call, as long as the chain ends in one.
        result, env = self.run_source('''
            record = [0, 0, 0, 0, {"sam": function(x) { print(x); return x }}];
            record[4]["sam"](2);
        ''')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['__output'], '2')

    def test_an_anonymous_function_called_immediately_is_a_legal_bare_statement(self):
        # An identifier right after "function" means the named-definition
        # sugar; anything else, most commonly "(", means an ordinary
        # anonymous function expression -- an immediately invoked one here,
        # used as a statement with its result discarded. Parenthesizing it
        # is not required.
        result, env = self.run_source('function(a) { print(a * 2) }(5);')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['__output'], '10')

    # ===== Dynamic scoping =====

    def test_call_sees_the_callers_environment_not_the_definers(self):
        # showX is defined once, at the top level, where x does not exist
        # at all. Each caller supplies its own x, and showX sees whichever
        # one was active where it was actually called from.
        result, env = self.run_source('''
            function showX() { return x };
            function callWith5() { x=5; return showX() };
            function callWith9() { x=9; return showX() };
            a = callWith5();
            b = callWith9();
        ''')
        self.assertEqual((env['a'], env['b']), (5, 9))
        self.assertNotIn('x', env)

    def test_recursion_works_through_the_same_dynamic_chain(self):
        # Each recursive call's $PARENT is the previous call's own
        # environment, which chains all the way back to wherever
        # factorial was originally bound -- no special-casing needed for
        # a function to call itself.
        result, env = self.run_source('''
            function factorial(n) {
                if (n == 0) { return 1 };
                return n * factorial(n-1)
            };
            y = factorial(5)
        ''')
        self.assertEqual(env['y'], 120)

    def test_mutual_recursion(self):
        result, env = self.run_source('''
            function isEven(n) {
                if (n == 0) { return true };
                return isOdd(n-1)
            };
            function isOdd(n) {
                if (n == 0) { return false };
                return isEven(n-1)
            };
            a = isEven(10);
            b = isOdd(10);
        ''')
        self.assertEqual((env['a'], env['b']), (True, False))

    # ===== break and continue cannot escape a function =====

    def test_break_inside_own_loop_still_works_normally(self):
        result, env = self.run_source('''
            function firstOver(items, limit) {
                i = 0;
                while (true) {
                    if (items[i] > limit) { break };
                    i = i+1
                };
                return items[i]
            };
            y = firstOver([1, 5, 9, 2], 8)
        ''')
        self.assertEqual(env['y'], 9)

    def test_break_outside_any_loop_in_the_function_body_rejected(self):
        with self.assertRaises(ValueError) as raised:
            self.run_source('function f() { break }; f()')
        self.assertEqual(str(raised.exception), "'break' used outside a loop")

    def test_continue_outside_any_loop_in_the_function_body_rejected(self):
        with self.assertRaises(ValueError) as raised:
            self.run_source('function f() { continue }; f()')
        self.assertEqual(str(raised.exception), "'continue' used outside a loop")

    def test_break_does_not_leak_through_a_call_into_the_callers_loop(self):
        # Without the function-boundary check, this break would otherwise
        # look like it belongs to the while loop that made the call.
        with self.assertRaises(ValueError):
            self.run_source('''
                function f() { break };
                while (true) { f() }
            ''')

    # ===== return cannot escape the program itself =====

    def test_return_outside_any_function_rejected(self):
        with self.assertRaises(ValueError) as raised:
            self.run_source('return 5;')
        self.assertEqual(str(raised.exception), "'return' used outside a function")

    def test_return_outside_any_function_rejected_from_inside_a_loop(self):
        # A loop passes an unfamiliar status straight through, the same
        # way it already does for exit -- the program boundary is still
        # what rejects it, same as a bare return would.
        with self.assertRaises(ValueError) as raised:
            self.run_source('while (true) { return 5; }')
        self.assertEqual(str(raised.exception), "'return' used outside a function")

    def test_runner_rejects_return_outside_any_function(self):
        runner = Path(__file__).with_name('runner.py')
        result = subprocess.run(
            [sys.executable, str(runner), 'return 5;'],
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=SUBPROCESS_TIMEOUT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'return' used outside a function", result.stderr)

    # ===== exit passes through a call unconsumed =====

    def test_exit_inside_a_function_propagates_through_the_call(self):
        result, env = self.run_source(
            'function f() { exit(7) }; print(f()); print("never")')
        self.assertEqual(result, (7, 'exit'))
        # print never got far enough to evaluate its own argument, let
        # alone run: __output is still its program-start default, never
        # overwritten with "never".
        self.assertEqual(env['__output'], '')

    # ===== Assigning to a call result =====

    def test_assigning_directly_to_a_call_result_rejected(self):
        # ===== CHAPTER 11: assignability is checked at evaluation, not parsing =====
        # 'f() = 5' now parses fine; evaluating it is what rejects a call
        # result as an assignment target, since a call's result has nowhere
        # to be written back to.
        parse(tokenize('function f() { return 1 }; f() = 5'))
        with self.assertRaises(ValueError):
            self.run_source('function f() { return 1 }; f() = 5;')

    def test_assigning_into_a_list_a_call_returned_is_allowed(self):
        result, env = self.run_source('''
            function makeList() { return [1, 2, 3] };
            items = makeList();
            makeList()[0] = 99;
        ''')
        # makeList()[0] = 99 writes into a brand new list the second call
        # produced, not into the one already saved as items.
        self.assertEqual(env['items'], [1, 2, 3])

    # ===== null =====

    def test_null_as_a_literal(self):
        result, env = self.run_source('x = null')
        self.assertIsNone(env['x'])

    def test_null_equals_itself(self):
        result, env = self.run_source('y = (null == null)')
        self.assertTrue(env['y'])

    def test_null_does_not_equal_other_values(self):
        for other in ('0', 'false', '""', '[]'):
            with self.subTest(other=other):
                result, env = self.run_source(f'y = (null == {other})')
                self.assertFalse(env['y'])

    def test_type_of_null(self):
        result, env = self.run_source('y = type(null)')
        self.assertEqual(env['y'], 'null')

    def test_type_of_a_function(self):
        result, env = self.run_source('y = type(function(x) { return x })')
        self.assertEqual(env['y'], 'function')

    def test_printing_null(self):
        result, env = self.run_source('print(null)')
        self.assertEqual(env['__output'], 'null')

    def test_printing_a_function(self):
        result, env = self.run_source('print(function(x) { return x })')
        self.assertEqual(env['__output'], '<function>')

    def test_string_of_null_and_function(self):
        result, env = self.run_source('a = string(null); b = string(function(){ })')
        self.assertEqual(env['a'], 'null')
        self.assertEqual(env['b'], '<function>')

    def test_null_inside_a_list_displays_correctly(self):
        result, env = self.run_source('print([1, null, 3])')
        self.assertEqual(env['__output'], '[1, null, 3]')

    def test_arithmetic_with_null_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x = 1 + null')

    def test_arithmetic_with_a_function_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x = 1 + function(y) { return y }')

    def test_comparison_with_null_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x = null < 1')

    def test_indexing_null_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x = null[0]')

    # ===== runner-level end-to-end checks =====

    def test_runner_handles_recursion(self):
        runner = Path(__file__).with_name('runner.py')
        source = (
            'function factorial(n) { '
            'if (n == 0) { return 1 }; return n * factorial(n-1) }; '
            'print(factorial(6))'
        )
        result = subprocess.run([sys.executable, str(runner), source],
                                capture_output=True, text=True,
                                stdin=subprocess.DEVNULL,
                                timeout=SUBPROCESS_TIMEOUT)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '720\n')
        self.assertEqual(result.stderr, '')

    def test_runnable_functions_example(self):
        out = io.StringIO()
        with redirect_stdout(out):
            result, env = evaluator.evaluate_source(
                Path(__file__).with_name('functions.v').read_text())
        self.assertEqual(result, (5, 'exit'))
        self.assertEqual(out.getvalue(), (
            '42\n21\n10\n5.0\nran with no return value\nnull\n720\n11\n'
            '5 is positive\n20\n99\n7\nHello\nBonjour\n5\n5\nnull\ntrue\n'
            'null\nfunction\n'
        ))

    def test_runner_rejects_break_outside_a_loop_inside_a_function(self):
        runner = Path(__file__).with_name('runner.py')
        result = subprocess.run(
            [sys.executable, str(runner), 'function f() { break }; f()'],
            capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=SUBPROCESS_TIMEOUT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'break' used outside a loop", result.stderr)


if __name__ == '__main__':
    unittest.main()
