import unittest
from unittest.mock import patch

import evaluator


class SliceHeadTailTests(unittest.TestCase):
    def run_source(self, source, environment=None):
        if environment is None:
            environment = {}
        result, environment = evaluator.evaluate_source(source, environment)
        return result, environment

    # ===== slice: lists =====

    def test_slice_of_a_list_is_half_open(self):
        _, env = self.run_source('x=slice([10, 20, 30, 40], 1, 3)')
        self.assertEqual(env['x'], [20, 30])

    def test_slice_of_the_whole_list(self):
        _, env = self.run_source('a=[1, 2, 3]; x=slice(a, 0, length(a))')
        self.assertEqual(env['x'], [1, 2, 3])

    def test_slice_with_equal_bounds_is_empty(self):
        # y: start at the length is legal too, same as end. It only marks
        # where the slice begins, not a seventh element that doesn't exist.
        _, env = self.run_source('x=slice([1, 2, 3], 1, 1); y=slice([1, 2, 3], 3, 3)')
        self.assertEqual(env['x'], [])
        self.assertEqual(env['y'], [])

    def test_slice_of_an_empty_list(self):
        _, env = self.run_source('x=slice([], 0, 0)')
        self.assertEqual(env['x'], [])

    def test_slice_builds_a_new_list(self):
        _, env = self.run_source('a=[1, 2, 3]; b=slice(a, 0, 3); b[0]=99')
        self.assertEqual(env['a'], [1, 2, 3])
        self.assertEqual(env['b'], [99, 2, 3])
        self.assertIsNot(env['a'], env['b'])

    def test_slice_shares_nested_elements_with_the_original(self):
        _, env = self.run_source('a=[[1], [2]]; b=slice(a, 0, 1); b[0][0]=99')
        self.assertEqual(env['a'], [[99], [2]])

    # ===== slice: strings =====

    def test_slice_of_a_string(self):
        _, env = self.run_source('x=slice("hello", 1, 3)')
        self.assertEqual(env['x'], 'el')

    def test_slice_of_a_string_with_equal_bounds_is_empty(self):
        _, env = self.run_source('x=slice("hello", 2, 2)')
        self.assertEqual(env['x'], '')

    def test_slice_of_a_whole_string(self):
        _, env = self.run_source('s="hello"; x=slice(s, 0, length(s))')
        self.assertEqual(env['x'], 'hello')

    # ===== slice: bounds and types =====

    def test_whole_number_float_bounds_accepted(self):
        _, env = self.run_source('x=slice([1, 2, 3], 1.0, 3.0)')
        self.assertEqual(env['x'], [2, 3])

    def test_fractional_bound_rejected(self):
        for source in ('slice([1, 2, 3], 0.5, 2)', 'slice([1, 2, 3], 0, 1.5)'):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    self.run_source('x=' + source)

    def test_boolean_bound_rejected(self):
        for source in ('slice([1, 2, 3], true, 2)', 'slice([1, 2, 3], 0, true)'):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    self.run_source('x=' + source)

    def test_string_bound_rejected(self):
        with self.assertRaises(TypeError):
            self.run_source('x=slice([1, 2, 3], "0", 2)')

    def test_negative_bound_rejected(self):
        for source in ('slice([1, 2, 3], -1, 2)', 'slice([1, 2, 3], 0, -1)'):
            with self.subTest(source=source):
                with self.assertRaises(IndexError):
                    self.run_source('x=' + source)

    def test_bound_past_the_length_rejected_not_clamped(self):
        for source in ('slice([1, 2, 3], 0, 4)', 'slice([1, 2, 3], 4, 4)',
                       'slice("abc", 0, 4)'):
            with self.subTest(source=source):
                with self.assertRaises(IndexError):
                    self.run_source('x=' + source)

    def test_start_after_end_rejected(self):
        with self.assertRaises(IndexError):
            self.run_source('x=slice([1, 2, 3], 2, 1)')

    def test_slice_requires_a_list_or_string(self):
        for source in ('slice(5, 0, 0)', 'slice(true, 0, 0)'):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    self.run_source('x=' + source)

    # ===== head =====

    def test_head_of_a_list(self):
        _, env = self.run_source('x=head([10, 20, 30])')
        self.assertEqual(env['x'], 10)

    def test_head_of_a_string(self):
        _, env = self.run_source('x=head("hello")')
        self.assertEqual(env['x'], 'h')

    def test_head_of_a_single_element(self):
        _, env = self.run_source('x=head([7]); y=head("z")')
        self.assertEqual(env['x'], 7)
        self.assertEqual(env['y'], 'z')

    def test_head_returns_the_element_itself(self):
        _, env = self.run_source('a=[[1], [2]]; h=head(a); h[0]=99')
        self.assertEqual(env['a'], [[99], [2]])

    def test_head_of_an_empty_list_or_string_rejected(self):
        for source in ('head([])', 'head("")'):
            with self.subTest(source=source):
                with self.assertRaises(IndexError):
                    self.run_source('x=' + source)

    def test_head_requires_a_list_or_string(self):
        with self.assertRaises(TypeError):
            self.run_source('x=head(5)')

    # ===== tail =====

    def test_tail_of_a_list(self):
        _, env = self.run_source('x=tail([10, 20, 30])')
        self.assertEqual(env['x'], [20, 30])

    def test_tail_of_a_string(self):
        _, env = self.run_source('x=tail("hello")')
        self.assertEqual(env['x'], 'ello')

    def test_tail_of_a_single_element_is_empty(self):
        _, env = self.run_source('x=tail([5]); y=tail("a")')
        self.assertEqual(env['x'], [])
        self.assertEqual(env['y'], '')

    def test_tail_builds_a_new_list_and_leaves_the_original(self):
        _, env = self.run_source('a=[1, 2, 3]; b=tail(a); b[0]=99')
        self.assertEqual(env['a'], [1, 2, 3])
        self.assertEqual(env['b'], [99, 3])
        self.assertIsNot(env['a'], env['b'])

    def test_tail_of_an_empty_list_or_string_is_empty(self):
        # Unlike head, tail of an empty value is not rejected: [] already
        # exists, and value[1:] agrees with Python's own slicing here.
        _, env = self.run_source('x=tail([]); y=tail("")')
        self.assertEqual(env['x'], [])
        self.assertEqual(env['y'], '')

    def test_tail_requires_a_list_or_string(self):
        with self.assertRaises(TypeError):
            self.run_source('x=tail(5)')

    # ===== length of a string =====

    def test_length_of_a_string(self):
        _, env = self.run_source('x=length("abc"); y=length("")')
        self.assertEqual(env['x'], 3)
        self.assertEqual(env['y'], 0)

    def test_length_still_rejects_other_types(self):
        for source in ('length(5)', 'length(true)'):
            with self.subTest(source=source):
                with self.assertRaises(TypeError):
                    self.run_source('x=' + source)

    # ===== Results compose =====

    def test_head_and_tail_rebuild_the_list_with_plus(self):
        _, env = self.run_source('a=[1, 2, 3]; b=[head(a)] + tail(a)')
        self.assertEqual(env['b'], [1, 2, 3])
        self.assertIsNot(env['a'], env['b'])

    def test_head_and_tail_rebuild_a_string_with_plus(self):
        _, env = self.run_source('s="hello"; t=head(s) + tail(s)')
        self.assertEqual(env['t'], 'hello')

    def test_guarded_loop_reverses_a_list(self):
        source = '''
            t=[1, 2, 3, 4];
            r=[];
            while (length(t) > 0) {
                r=[head(t)] + r;
                t=tail(t);
            };
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['r'], [4, 3, 2, 1])
        self.assertEqual(env['t'], [])

    def test_guarded_loop_reverses_a_string(self):
        source = '''
            s="abc";
            r="";
            while (length(s) > 0) {
                r=head(s) + r;
                s=tail(s);
            };
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['r'], 'cba')

    def test_slice_pieces_rejoin_with_plus(self):
        source = '''
            a=[1, 2, 3, 4, 5];
            b=slice(a, 0, 2) + slice(a, 2, length(a));
        '''
        _, env = self.run_source(source)
        self.assertEqual(env['b'], [1, 2, 3, 4, 5])

    def test_nested_slice_head_tail(self):
        _, env = self.run_source('x=head(tail(slice([1, 2, 3, 4], 1, 4)))')
        self.assertEqual(env['x'], 3)

    def test_results_can_be_indexed_and_typed(self):
        _, env = self.run_source('x=tail([1, 2, 3])[0]; y=type(head("ab")); z=type(tail([1]))')
        self.assertEqual(env['x'], 2)
        self.assertEqual(env['y'], 'string')
        self.assertEqual(env['z'], 'list')

    # ===== Keywords =====

    def test_slice_head_and_tail_are_no_longer_usable_as_names(self):
        for name in ('slice', 'head', 'tail'):
            with self.subTest(name=name):
                with self.assertRaises(SyntaxError):
                    self.run_source(f'{name}=1')
                with self.assertRaises(SyntaxError):
                    self.run_source(f'x={name}')

    def test_similar_names_remain_ordinary_identifiers(self):
        _, env = self.run_source('sliced=1; header=2; tailor=3')
        self.assertEqual(env['sliced'], 1)
        self.assertEqual(env['header'], 2)
        self.assertEqual(env['tailor'], 3)

    # ===== Status propagation and evaluation order =====

    def test_exit_from_every_position_propagates(self):
        sources = [
            'x=slice(exit(7), input(), input())',
            'x=slice([1, 2], exit(7), input())',
            'x=slice([1, 2], 0, exit(7))',
            'x=head(exit(7))',
            'x=tail(exit(7))',
        ]
        for source in sources:
            with self.subTest(source=source):
                with patch('builtins.input') as fake_input:
                    result, env = self.run_source(source)
                self.assertEqual(result, (7, 'exit'))
                self.assertNotIn('x', env)
                fake_input.assert_not_called()

    def test_slice_evaluates_sequence_then_start_then_end(self):
        with patch('builtins.input', side_effect=['hello', '1', '3']) as fake_input:
            _, env = self.run_source('x=slice(input(), number(input()), number(input()))')
        self.assertEqual(env['x'], 'el')
        self.assertEqual(fake_input.call_count, 3)

    def test_slice_evaluates_all_arguments_before_checking_types(self):
        # Every argument is evaluated, in order, before any argument is
        # checked, so an earlier type error does not hide a later exit.
        result, env = self.run_source('x=slice(5, 0, exit(4))')
        self.assertEqual(result, (4, 'exit'))
        self.assertNotIn('x', env)


if __name__ == '__main__':
    unittest.main()
