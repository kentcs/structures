import unittest
from unittest.mock import patch

import evaluator


class StringIndexingTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    # ===== Reading a character =====

    def test_index_reads_a_one_character_string(self):
        _, env = self.run_source('s="hello"; x=s[1]; y=type(s[1])')
        self.assertEqual(env['x'], 'e')
        self.assertEqual(env['y'], 'string')

    def test_first_and_last_characters(self):
        _, env = self.run_source('s="hello"; a=s[0]; b=s[length(s) - 1]')
        self.assertEqual(env['a'], 'h')
        self.assertEqual(env['b'], 'o')

    def test_string_literal_can_be_indexed_directly(self):
        _, env = self.run_source('x="hello"[1]')
        self.assertEqual(env['x'], 'e')

    def test_index_agrees_with_head_and_slice(self):
        _, env = self.run_source(
            's="hello"; a=s[0] == head(s); b=s[2] == head(slice(s, 2, 3))')
        self.assertEqual(env['a'], True)
        self.assertEqual(env['b'], True)

    def test_whole_number_float_index_accepted(self):
        _, env = self.run_source('x="hello"[1.0]')
        self.assertEqual(env['x'], 'e')

    def test_string_inside_a_list_can_be_indexed_in_a_chain(self):
        _, env = self.run_source('names=["ab", "cd"]; x=names[1][0]')
        self.assertEqual(env['x'], 'c')

    # ===== Rejected indices: the same rules as for a list =====

    def test_fractional_index_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x="hello"[1.5]')

    def test_boolean_index_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x="hello"[true]')

    def test_string_index_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x="hello"["1"]')

    def test_negative_index_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('x="hello"[-1]')

    def test_index_equal_to_the_length_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('x="hello"[5]')

    def test_every_index_of_an_empty_string_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('x=""[0]')

    def test_indexing_other_values_still_rejected(self):
        for source in ('x=5[0]', 'x=true[0]'):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    self.run_source(source)

    # ===== A string cannot be assigned into =====

    def test_assignment_into_a_string_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('s="hello"; s[0]="j"')

    def test_failed_assignment_leaves_the_string_unchanged(self):
        environment = {}
        try:
            self.run_source('s="hello"; s[0]="j"', environment)
        except TypeError:
            pass
        self.assertEqual(environment['s'], 'hello')

    def test_assignment_into_a_string_held_by_a_list_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('names=["ab"]; names[0][1]="x"')

    def test_replacing_a_list_element_with_a_new_string_still_works(self):
        _, env = self.run_source('names=["ab"]; names[0]="xy"')
        self.assertEqual(env['names'], ['xy'])

    # ===== Traversal =====

    def test_traverse_a_string_with_while_and_length(self):
        source = '''
            s="abc";
            r="";
            i=0;
            while (i < length(s)) {
                r=s[i] + r;
                i=i + 1;
            };
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['r'], 'cba')

    # ===== Status propagation =====

    def test_exit_from_the_base_or_the_index_propagates(self):
        for source in ('x=exit(7)[input()]', 'x="hello"[exit(7)]'):
            with self.subTest(source=source):
                with patch('builtins.input') as fake_input:
                    result, env = self.run_source(source)
                self.assertEqual(result, (7, 'exit'))
                self.assertNotIn('x', env)
                fake_input.assert_not_called()


if __name__ == '__main__':
    unittest.main()
