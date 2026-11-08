import unittest
from unittest.mock import patch

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class ConversionAndTypeTests(unittest.TestCase):
    def value(self, expression):
        return evaluate_source("result=" + expression)[1]["result"]

    def test_conversion_matrix(self):
        cases = [('number(2)', 2), ('number(2.5)', 2.5),
                 ('number(" .5 ")', .5), ('number(true)', 1), ('number(false)', 0),
                 ('string(2)', '2'), ('string(2.5)', '2.5'), ('string("abc")', 'abc'),
                 ('string(true)', 'true'), ('string(false)', 'false'),
                 ('boolean(true)', True), ('boolean(false)', False),
                 ('boolean(0)', False), ('boolean(-0.0)', False),
                 ('boolean(-2)', True), ('boolean(.5)', True),
                 ('boolean(" TrUe ")', True), ('boolean(" FALSE ")', False)]
        for source, expected in cases:
            with self.subTest(source=source):
                result = self.value(source)
                self.assertEqual(result, expected)
                self.assertIs(type(result), type(expected))

    def test_invalid_text(self):
        for source in ('boolean("")', 'boolean("yes")', 'boolean("0")',
                       'boolean("1")', 'number("true")', 'number("2+3")'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.value(source)

    def test_type_names(self):
        for expression, expected in [('42', 'number'), ('2.5', 'number'),
                                     ('"42"', 'string'), ('true', 'boolean'),
                                     ('1<2', 'boolean'), ('type(false)', 'string')]:
            with self.subTest(expression=expression):
                self.assertEqual(self.value(f'type({expression})'), expected)

    def test_argument_evaluated_once(self):
        for name, supplied, expected in [('type', 'false', 'string'),
                                         ('boolean', 'false', False),
                                         ('string', 'text', 'text'),
                                         ('number', '42', 42)]:
            with self.subTest(name=name), patch('builtins.input', return_value=supplied) as read:
                self.assertEqual(self.value(f'{name}(input())'), expected)
                read.assert_called_once_with()
        _, env = evaluate_source('__input="true"; result=type(input())')
        self.assertEqual(env['result'], 'string')
        self.assertEqual(env['__input'], '')
        with self.assertRaises(ValueError):
            self.value('type(missing)')

    def test_keyword_boundaries_and_syntax(self):
        self.assertEqual([t['tag'] for t in tokenize('boolean type boolean_value typewriter')],
                         ['boolean_conversion', 'type_query', 'identifier', 'identifier', None])
        for name in ('number', 'string', 'boolean', 'type'):
            for source in (f'x={name}()', f'x={name}(1,2)', f'x={name}(1', f'{name}=1'):
                with self.subTest(source=source), self.assertRaises(SyntaxError):
                    parse(tokenize(source))

    def test_explicit_conversion_does_not_change_implicit_rules(self):
        self.assertEqual(self.value('number(true)+2'), 3)
        self.assertIs(self.value('boolean(1) and true'), True)
        self.assertIs(self.value('true==1'), False)
        for source in ('true+2', '1 and true'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                self.value(source)


if __name__ == '__main__':
    unittest.main()
