import unittest
from unittest.mock import patch

import evaluator
from parser import parse
from tokenizer import tokenize


class ListTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    # ===== Literals =====

    def test_empty_list(self):
        result, env = self.run_source('a=[]')
        self.assertEqual(result, (None, None))
        self.assertEqual(env['a'], [])

    def test_nonempty_mixed_list(self):
        _, env = self.run_source('a=[1, "two", true]')
        self.assertEqual(env['a'], [1, 'two', True])

    def test_elements_evaluated_in_source_order(self):
        with patch('builtins.input', side_effect=['first', 'second']) as fake_input:
            _, env = self.run_source('a=[input(), input()]')
        self.assertEqual(env['a'], ['first', 'second'])
        self.assertEqual(fake_input.call_count, 2)

    def test_nested_list_literal(self):
        _, env = self.run_source('a=[[1, 2], [3, 4]]')
        self.assertEqual(env['a'], [[1, 2], [3, 4]])

    # ===== Indexing (read) =====

    def test_index_read(self):
        _, env = self.run_source('a=[10, 20, 30]; x=a[1]')
        self.assertEqual(env['x'], 20)

    def test_nested_indexing(self):
        _, env = self.run_source('m=[[1, 2], [3, 4]]; x=m[1][0]')
        self.assertEqual(env['x'], 3)

    def test_whole_number_float_index_accepted(self):
        _, env = self.run_source('a=[1, 2, 3]; x=a[1.0]')
        self.assertEqual(env['x'], 2)

    def test_fractional_index_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('a=[1, 2, 3]; x=a[1.5]')

    def test_boolean_index_rejected(self):
        # bool is an int subclass in Python; Vertex must not let that leak in.
        with self.assertRaises(TypeError):
            self.run_source('a=[1, 2, 3]; x=a[true]')

    def test_string_index_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('a=[1, 2, 3]; x=a["0"]')

    def test_negative_index_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('a=[1, 2, 3]; x=a[-1]')

    def test_out_of_range_index_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('a=[1, 2, 3]; x=a[3]')

    def test_indexing_a_non_list_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('a=5; x=a[0]')

    # ===== Indexed assignment (write) =====

    def test_indexed_assignment(self):
        _, env = self.run_source('a=[1, 2, 3]; a[0]=99')
        self.assertEqual(env['a'], [99, 2, 3])

    def test_nested_indexed_assignment(self):
        _, env = self.run_source('m=[[1, 2], [3, 4]]; m[1][0]=99')
        self.assertEqual(env['m'], [[1, 2], [99, 4]])

    def test_indexed_assignment_out_of_range_does_not_grow(self):
        with self.assertRaises(IndexError):
            self.run_source('a=[1, 2, 3]; a[5]=1')

    def test_indexed_assignment_requires_a_list_base(self):
        with self.assertRaises(TypeError):
            self.run_source('a=5; a[0]=1')

    # ===== Mutation vs. rebinding =====

    def test_indexed_assignment_mutates_through_every_alias(self):
        _, env = self.run_source('a=[1, 2]; b=a; b[0]=99')
        self.assertEqual(env['a'], [99, 2])
        self.assertIs(env['a'], env['b'])

    def test_rebinding_does_not_affect_the_alias(self):
        _, env = self.run_source('a=[1, 2]; b=a; a=[9, 9]')
        self.assertEqual(env['a'], [9, 9])
        self.assertEqual(env['b'], [1, 2])
        self.assertIsNot(env['a'], env['b'])

    def test_concatenation_produces_an_independent_list(self):
        _, env = self.run_source('a=[1, 2]; b=[3, 4]; c=a+b; c[0]=99')
        self.assertEqual(env['a'], [1, 2])
        self.assertEqual(env['b'], [3, 4])
        self.assertEqual(env['c'], [99, 2, 3, 4])

    def test_arithmetic_other_than_plus_rejects_lists(self):
        for operator in ('-', '*', '/'):
            with self.subTest(operator=operator):
                with self.assertRaises(TypeError):
                    self.run_source(f'a=[1, 2] {operator} [3, 4]')

    def test_plus_requires_both_operands_to_be_lists(self):
        with self.assertRaises(TypeError):
            self.run_source('a=[1, 2] + 3')

    # ===== Equality =====

    def test_structural_equality(self):
        result, _ = self.run_source('x=[1, 2] == [1, 2]')
        self.assertEqual(result, (None, None))

    def test_equality_checks_length(self):
        _, env = self.run_source('x=[1, 2] == [1, 2, 3]')
        self.assertEqual(env['x'], False)

    def test_equality_preserves_true_is_not_one_when_nested(self):
        _, env = self.run_source('x=[true] == [1]; y=[1] == [true]')
        self.assertEqual(env['x'], False)
        self.assertEqual(env['y'], False)

    def test_nested_list_equality(self):
        _, env = self.run_source('x=[1, [2, 3]] == [1, [2, 3]]; y=[1, [2, 3]] == [1, [2, 4]]')
        self.assertEqual(env['x'], True)
        self.assertEqual(env['y'], False)

    def test_equality_does_not_use_python_list_equality_directly(self):
        # A regression guard: Python's [True] == [1] is True, which Vertex
        # must not expose.
        _, env = self.run_source('x=[true, false] == [1, 0]')
        self.assertEqual(env['x'], False)

    def test_ordering_comparisons_reject_lists(self):
        for operator in ('<', '<=', '>', '>='):
            with self.subTest(operator=operator):
                with self.assertRaises(TypeError):
                    self.run_source(f'x=[1] {operator} [2]')

    # ===== length() =====

    def test_length_of_a_list(self):
        _, env = self.run_source('x=length([1, 2, 3])')
        self.assertEqual(env['x'], 3)

    def test_length_of_empty_list(self):
        _, env = self.run_source('x=length([])')
        self.assertEqual(env['x'], 0)

    def test_length_rejects_non_list(self):
        with self.assertRaises(TypeError):
            self.run_source('x=length(5)')

    # ===== type(), print(), string() =====

    def test_type_of_a_list(self):
        _, env = self.run_source('x=type([1, 2])')
        self.assertEqual(env['x'], 'list')

    def test_print_quotes_strings_inside_a_list(self):
        import contextlib
        import io
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_source('print([1, "hi", true, [2, 3]])')
        self.assertEqual(output.getvalue(), '[1, "hi", true, [2, 3]]\n')

    def test_print_of_a_bare_string_is_still_unquoted(self):
        import contextlib
        import io
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.run_source('print("hi")')
        self.assertEqual(output.getvalue(), 'hi\n')

    def test_string_conversion_of_a_list(self):
        _, env = self.run_source('x=string([1, "hi"])')
        self.assertEqual(env['x'], '[1, "hi"]')

    def test_number_and_boolean_conversion_reject_lists(self):
        with self.assertRaises(TypeError):
            self.run_source('x=number([1])')
        with self.assertRaises(TypeError):
            self.run_source('x=boolean([1])')

    # ===== Traversal =====

    def test_traverse_with_while_and_length(self):
        source = '''
            a=[3, 1, 4, 1, 5];
            total=0;
            i=0;
            while (i < length(a)) {
                total=total+a[i];
                i=i+1;
            };
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['total'], 14)

    # ===== Status propagation: exit injected at every position =====

    def test_exit_from_a_list_element_stops_later_elements(self):
        with patch('builtins.input') as fake_input:
            result, _ = self.run_source('a=[1, exit(7), input()]')
        self.assertEqual(result, (7, 'exit'))
        fake_input.assert_not_called()

    def test_exit_from_the_index_base_propagates(self):
        with patch('builtins.input') as fake_input:
            result, env = self.run_source('x = exit(7)[input()]')
        self.assertEqual(result, (7, 'exit'))
        self.assertNotIn('x', env)
        fake_input.assert_not_called()

    def test_exit_from_an_index_expression_propagates(self):
        with patch('builtins.input') as fake_input:
            result, env = self.run_source('a=[1, 2, 3]; x=a[exit(7)]')
        self.assertEqual(result, (7, 'exit'))
        self.assertNotIn('x', env)
        fake_input.assert_not_called()

    def test_exit_from_indexed_assignment_index_wins_over_the_value(self):
        # The target's index is resolved before the right-hand value, so an
        # exit from the index must win even if the value also exits.
        result, env = self.run_source('a=[1, 2, 3]; a[exit(6)]=exit(999)')
        self.assertEqual(result, (6, 'exit'))
        self.assertEqual(env['a'], [1, 2, 3])

    def test_exit_from_a_chained_assignment_base_wins_over_the_value(self):
        result, env = self.run_source('m=[[1, 2], [3, 4]]; m[exit(7)][0]=exit(999)')
        self.assertEqual(result, (7, 'exit'))
        self.assertEqual(env['m'], [[1, 2], [3, 4]])

    def test_exit_from_the_right_hand_value_leaves_the_list_unmutated(self):
        result, env = self.run_source('a=[1, 2, 3]; a[0]=exit(9)')
        self.assertEqual(result, (9, 'exit'))
        # No pending mutation happens after a special status.
        self.assertEqual(env['a'], [1, 2, 3])

    def test_exit_from_plain_assignment_value_leaves_target_unset(self):
        result, env = self.run_source('x=exit(9)')
        self.assertEqual(result, (9, 'exit'))
        self.assertNotIn('x', env)


if __name__ == '__main__':
    unittest.main()
