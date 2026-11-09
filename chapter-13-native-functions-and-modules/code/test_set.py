import unittest
from unittest.mock import patch

from evaluator import evaluate, evaluate_source
from parser import parse
from tokenizer import tokenize


class SetTests(unittest.TestCase):
    def test_keyword_boundary(self):
        self.assertEqual([t['tag'] for t in tokenize('set setter setting')],
                         ['set', 'identifier', 'identifier', None])

    def test_current_binding(self):
        result, env = evaluate_source('x=1; set x=5;')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['x'], 5)

    def test_nearest_binding_and_ordinary_assignment(self):
        _, env = evaluate_source('''
            x=100;
            function outer() {
                x=10;
                function middle() {
                    function inner() { set x=x+1 };
                    inner()
                };
                middle(); return x
            };
            answer=outer();
        ''')
        self.assertEqual((env['x'], env['answer']), (100, 11))

    def test_global_binding(self):
        _, env = evaluate_source('x=1; function f() { set x=5 }; f()')
        self.assertEqual(env['x'], 5)

    def test_parameter_binding(self):
        _, env = evaluate_source('function f(x) { set x=x+1; return x }; y=f(4)')
        self.assertEqual(env['y'], 5)
        self.assertNotIn('x', env)

    def test_missing_binding_rejected_before_rhs(self):
        env = {}
        with patch('builtins.input') as read:
            with self.assertRaises(NameError):
                evaluate_source('set missing=input()', env)
            read.assert_not_called()
        self.assertNotIn('missing', env)

    def test_lexical_not_caller_binding(self):
        with self.assertRaises(NameError):
            evaluate_source('''
                function f() { set callerOnly=5 };
                function g() { callerOnly=1; f() }; g()
            ''')

    def test_statement_only_and_identifier_target(self):
        for source in ('set x', 'set x 5', 'set x=', 'set 1=5',
                       'set a.x=5', 'set a[0]=5', 'y=(set x=5)'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_rhs_status_does_not_modify_binding(self):
        env = {'x': 1}
        node = {'tag': 'set', 'name': 'x', 'expression': {
            'tag': 'exit', 'expression': {'tag': 'number', 'value': 7}}}
        self.assertEqual(evaluate(node, env), (7, 'exit'))
        self.assertEqual(env['x'], 1)

    def test_counter_methods_share_state_and_instances_are_independent(self):
        _, env = evaluate_source('''
            function makeCounter() {
                count=0;
                return {
                    "increment": function() { set count=count+1; return count },
                    "value": function() { return count }
                }
            };
            a=makeCounter(); b=makeCounter();
            first=a.increment(); second=a.increment();
            av=a.value(); bv=b.value();
            detached=a.increment; third=detached(); after=a.value()
        ''')
        self.assertEqual([env[k] for k in ('first', 'second', 'av', 'bv', 'third', 'after')],
                         [1, 2, 2, 0, 3, 3])
        self.assertNotIn('count', env)


if __name__ == '__main__':
    unittest.main()
