import unittest
from unittest.mock import patch

import evaluator


def exit_node(value=7):
    return {"tag": "exit", "expression": {"tag": "number", "value": value}}


class CopyTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    # ===== x == copy(x) for every x =====

    def test_copy_of_a_number_equals_the_original(self):
        _, env = self.run_source('x=5; y=copy(x); eq=x==y')
        self.assertEqual(env['y'], 5)
        self.assertTrue(env['eq'])

    def test_copy_of_a_string_equals_the_original(self):
        _, env = self.run_source('x="hi"; y=copy(x); eq=x==y')
        self.assertEqual(env['y'], 'hi')
        self.assertTrue(env['eq'])

    def test_copy_of_a_boolean_equals_the_original(self):
        _, env = self.run_source('x=true; y=copy(x); eq=x==y')
        self.assertEqual(env['y'], True)
        self.assertTrue(env['eq'])

    def test_copy_of_an_empty_list_equals_the_original(self):
        _, env = self.run_source('x=[]; y=copy(x); eq=x==y')
        self.assertEqual(env['y'], [])
        self.assertTrue(env['eq'])

    def test_copy_of_a_nested_list_equals_the_original(self):
        _, env = self.run_source('x=[1, [2, 3], "a"]; y=copy(x); eq=x==y')
        self.assertEqual(env['y'], [1, [2, 3], 'a'])
        self.assertTrue(env['eq'])

    # ===== deep: every nested list is new, not just the outermost =====

    def test_copy_is_not_the_same_list(self):
        _, env = self.run_source('a=[1, 2]; b=copy(a)')
        self.assertIsNot(env['a'], env['b'])

    def test_mutating_the_copy_does_not_affect_the_original(self):
        _, env = self.run_source('a=[1, 2]; b=copy(a); b[0]=99')
        self.assertEqual(env['a'], [1, 2])
        self.assertEqual(env['b'], [99, 2])

    def test_mutating_a_nested_copy_does_not_affect_the_original(self):
        # The point of copy being deep rather than shallow: slice and tail
        # only copy the outermost list, so a nested list is still shared.
        # copy must not share it.
        _, env = self.run_source('a=[1, [2, 3]]; b=copy(a); b[1][0]=99')
        self.assertEqual(env['a'], [1, [2, 3]])
        self.assertEqual(env['b'], [1, [99, 3]])

    def test_mutating_the_original_nested_list_does_not_affect_the_copy(self):
        _, env = self.run_source('a=[1, [2, 3]]; b=copy(a); a[1][0]=99')
        self.assertEqual(env['a'], [1, [99, 3]])
        self.assertEqual(env['b'], [1, [2, 3]])

    def test_copy_at_three_levels_of_nesting_is_independent_throughout(self):
        _, env = self.run_source('a=[[[1]]]; b=copy(a); b[0][0][0]=99')
        self.assertEqual(env['a'], [[[1]]])
        self.assertEqual(env['b'], [[[99]]])

    # ===== cycles =====

    def test_copy_of_a_self_referential_list_is_a_separate_cycle(self):
        _, env = self.run_source('a=[0]; a[0]=a; b=copy(a)')
        self.assertIsNot(env['a'], env['b'])
        self.assertIs(env['b'][0], env['b'])
        self.assertIsNot(env['b'][0], env['a'])

    def test_copy_of_a_self_referential_list_equals_the_original(self):
        _, env = self.run_source('a=[0]; a[0]=a; b=copy(a); eq=a==b')
        self.assertTrue(env['eq'])

    def test_copy_of_an_indirect_two_list_cycle_is_a_separate_cycle(self):
        _, env = self.run_source('a=[0]; c=[a]; a[0]=c; b=copy(a)')
        self.assertIsNot(env['a'], env['b'])
        self.assertIsNot(env['a'][0], env['b'][0])
        self.assertIs(env['b'][0][0], env['b'])

    # ===== status propagation =====

    def test_exit_from_the_argument_propagates(self):
        # exit can no longer sit inside copy(...)'s argument in real source,
        # since it cannot nest inside any expression; the node is built
        # directly to check the evaluator's own propagation.
        node = {"tag": "assign", "target": {"tag": "identifier", "value": "x"},
               "expression": {"tag": "copy", "expression": exit_node(7)}}
        env = {}
        with patch('builtins.input') as fake_input:
            result = evaluator.evaluate(node, env)
        self.assertEqual(result, (7, 'exit'))
        self.assertNotIn('x', env)
        fake_input.assert_not_called()

    # ===== reserved name =====

    def test_copy_is_no_longer_usable_as_a_name(self):
        with self.assertRaises(SyntaxError):
            self.run_source('copy=1')
        with self.assertRaises(SyntaxError):
            self.run_source('x=copy')

    def test_similar_names_remain_ordinary_identifiers(self):
        _, env = self.run_source('copied=1; copy_two=2')
        self.assertEqual(env['copied'], 1)
        self.assertEqual(env['copy_two'], 2)


if __name__ == '__main__':
    unittest.main()
