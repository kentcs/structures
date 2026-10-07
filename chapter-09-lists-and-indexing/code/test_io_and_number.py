import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class InputOutputAndNumberTests(unittest.TestCase):
    def test_globals_exist_before_first_use(self):
        _, env = evaluate_source('saved_input=__input;saved_output=__output')
        self.assertEqual(env, {
            '__input': '', '__output': '', 'saved_input': '', 'saved_output': '',
        })

    def test_print_captures_latest_text(self):
        output = io.StringIO()
        with redirect_stdout(output):
            _, env = evaluate_source('print(42);first=__output;print("a\\nb")')
        self.assertEqual(output.getvalue(), '42\na\nb\n')
        self.assertEqual(env['first'], '42')
        self.assertEqual(env['__output'], 'a\nb')

    def test_supplied_input_is_consumed_once(self):
        output = io.StringIO()
        with patch('builtins.input', return_value='keyboard') as read:
            with redirect_stdout(output):
                _, env = evaluate_source(
                    '__input="Ada";a=input("Name? ");cleared=__input;'
                    'b=input("Next? ");__input="Grace";c=input()'
                )
        self.assertEqual([env[key] for key in ('a', 'b', 'c')], ['Ada', 'keyboard', 'Grace'])
        self.assertEqual(env['cleared'], '')
        self.assertEqual(env['__input'], '')
        read.assert_called_once_with('Next? ')
        self.assertEqual(output.getvalue(), '')

    def test_external_input_and_global_assignment(self):
        root = {'__input': '21', '__output': 'previous'}
        local = {'$PARENT': root}
        with patch('builtins.input') as read, redirect_stdout(io.StringIO()):
            _, env = evaluate_source(
                'previous=__output;print(number(input())*2);__input="next"', local
            )
        read.assert_not_called()
        self.assertEqual(env['previous'], 'previous')
        self.assertEqual(root['__output'], '42')
        self.assertEqual(root['__input'], 'next')
        self.assertNotIn('__output', local)
        self.assertNotIn('__input', local)

    def test_prompt_and_supplied_input_types(self):
        for source in ('__input="ready";x=input(42)', '__input=42;x=input()'):
            with self.subTest(source=source), patch('builtins.input') as read:
                with self.assertRaises(TypeError):
                    evaluate_source(source)
                read.assert_not_called()

    def test_number_values_and_types(self):
        for text, expected in [('42', 42), ('-3', -3), ('+3', 3),
                               (' 2.5 ', 2.5), ('.5', .5), ('5.', 5.0)]:
            with self.subTest(text=text):
                _, env = evaluate_source('value=number(text)', {'text': text})
                self.assertEqual(env['value'], expected)
                self.assertIs(type(env['value']), type(expected))
        _, env = evaluate_source('value="ha"*number("3");numbered=number("1"+"2")')
        self.assertEqual(env['value'], 'hahaha')
        self.assertEqual(env['numbered'], 12)

    def test_invalid_number_arguments(self):
        for text in ('', ' ', 'abc', '1.2.3', '2+3', '1e3', 'nan', 'inf'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                evaluate_source('x=number(text)', {'text': text})
        self.assertEqual(evaluate_source('x=number(42)')[1]['x'], 42)

    def test_number_syntax(self):
        for source in ('x=number', 'x=number()', 'x=number("1"', 'x=number("1","2")'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))
        tokens = tokenize('number numbered number_value')
        self.assertEqual([t['tag'] for t in tokens],
                         ['number_conversion', 'identifier', 'identifier', None])

    def test_string_conversion(self):
        for expression, expected in [('42', '42'), ('-3', '-3'), ('2.5', '2.5'),
                                     ('5.', '5.0'), ('1+2*3', '7')]:
            with self.subTest(expression=expression):
                _, env = evaluate_source(f'value=string({expression})')
                self.assertEqual(env['value'], expected)
        _, env = evaluate_source('value="Answer: "+string(number("21")*2)')
        self.assertEqual(env['value'], 'Answer: 42')
        for source in ('x=string("42")', 'x=string(input())'):
            with self.subTest(source=source):
                self.assertEqual(evaluate_source(source, {'__input': '42'})[1]['x'], '42')

    def test_string_syntax(self):
        for source in ('x=string', 'x=string()', 'x=string(1', 'x=string(1,2)'):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))
        tokens = tokenize('string stringed string_value')
        self.assertEqual([t['tag'] for t in tokens],
                         ['string_conversion', 'identifier', 'identifier', None])


if __name__ == '__main__':
    unittest.main()
