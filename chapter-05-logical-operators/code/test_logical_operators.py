import unittest
from unittest.mock import patch

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class LogicalOperatorTests(unittest.TestCase):
    def value(self, source):
        return evaluate_source("result=" + source)[1]["result"]

    def test_normalized_tokens(self):
        tags = [t["tag"] for t in tokenize("and && or || not ! != android origin notable")]
        self.assertEqual(tags, ["and", "and", "or", "or", "not", "not", "!=",
                                "identifier", "identifier", "identifier", None])
        for source in ("and=1", "or=1", "not=1"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_same_tree_for_both_spellings(self):
        words = parse(tokenize("x=not false and true or false"))
        symbols = parse(tokenize("x=!false && true || false"))
        self.assertEqual(words, symbols)
        node = words["statements"]["statements"][0]["expression"]
        self.assertEqual(node["tag"], "or")
        self.assertEqual(node["left"]["tag"], "and")
        self.assertEqual(node["left"]["left"]["tag"], "not")

    def test_truth_tables(self):
        for left in (False, True):
            for right in (False, True):
                for operator in ("and", "&&", "or", "||"):
                    expected = (left and right) if operator in ("and", "&&") else (left or right)
                    source = f"{str(left).lower()} {operator} {str(right).lower()}"
                    with self.subTest(source=source):
                        self.assertIs(self.value(source), expected)
            for operator in ("not ", "!"):
                self.assertIs(self.value(operator + str(left).lower()), not left)

    def test_precedence_and_repeated_negation(self):
        for source, expected in [("true or false and false", True),
                                 ("(true or false) and false", False),
                                 ("not 1+2*3==7", False),
                                 ("!1!=2", False), ("!!true", True),
                                 ("not !false", False),
                                 ("1<2 && 3>=3 or false", True)]:
            with self.subTest(source=source):
                self.assertIs(self.value(source), expected)

    def test_short_circuit_skips_errors_and_input(self):
        # A skipped child is never evaluated, including its runtime type checks.
        for source, expected in [("false and missing", False),
                                 ("true or 1/0==0", True),
                                 ("false && input()", False),
                                 ("true || input()", True)]:
            with self.subTest(source=source), patch("builtins.input") as read:
                self.assertIs(self.value(source), expected)
                read.assert_not_called()
        _, env = evaluate_source('__input="ready";x=false and input()=="ready"')
        self.assertEqual(env["__input"], "ready")

    def test_needed_right_operand_runs_once(self):
        for source in ('true and input()=="yes"', 'false || input()=="yes"'):
            with self.subTest(source=source), patch("builtins.input", return_value="yes") as read:
                self.assertIs(self.value(source), True)
                read.assert_called_once_with()

    def test_boolean_operands_required(self):
        for source in ("not 1", '!"text"', "1 and true", "0 or false",
                       "true and 2", 'false || "text"'):
            with self.subTest(source=source), self.assertRaises(TypeError):
                self.value(source)

    def test_incomplete_operators(self):
        for source in ("x=true &&", "x=false or", "x=!", "x=and true",
                       "x=true & false", "x=true | false"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))


if __name__ == "__main__":
    unittest.main()
