import unittest

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class ChapterBoundaryTests(unittest.TestCase):
    def test_logical_words_are_still_identifiers(self):
        # They become reserved words only in Logical Operators.
        _, env = evaluate_source("and=1; or=2; not=3; result=and+or+not")
        self.assertEqual(env["result"], 6)

    def test_logical_syntax_is_not_yet_available(self):
        for expression in ("true and false", "true or false", "not true",
                           "true && false", "true || false", "!true"):
            with self.subTest(expression=expression), self.assertRaises(SyntaxError):
                parse(tokenize("result=" + expression))


if __name__ == "__main__":
    unittest.main()
