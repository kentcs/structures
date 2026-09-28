import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from evaluator import evaluate_source
from parser import parse
from tokenizer import tokenize


class BooleanComparisonTests(unittest.TestCase):
    def value(self, expression):
        return evaluate_source("result=" + expression)[1]["result"]

    def test_token_order_and_keyword_boundaries(self):
        tokens = tokenize("== != <= >= < > = true false true_value falsehood")
        self.assertEqual([t["tag"] for t in tokens],
                         ["==", "!=", "<=", ">=", "<", ">", "=", "true",
                          "false", "identifier", "identifier", None])
        for source in ("true=1", "false=2"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_literals_and_assignment_nodes(self):
        self.assertIs(self.value("true"), True)
        self.assertIs(self.value("false"), False)
        assignment = parse(tokenize("ready=true"))["statements"]["statements"][0]
        self.assertEqual(assignment["target"], {"tag": "identifier", "value": "ready"})
        self.assertEqual(assignment["expression"], {"tag": "boolean", "value": True})

    def test_comparison_values_and_types(self):
        cases = [("1==1.0", True), ("1==2", False), ("1!=2", True),
                 ("1!=1", False), ("1<2", True), ("2<1", False),
                 ("2<=2", True), ("3<=2", False), ("3>2", True),
                 ("2>3", False), ("2>=2", True), ("2>=3", False),
                 ('"dog"=="dog"', True), ('"dog"!="cat"', True),
                 ('"dog"=="cat"', False), ("true==false", False),
                 ("true!=false", True), ("true==1", False),
                 ("false==0", False), ('"1"==1', False),
                 ("-1.5<.5", True), ("1+2*3==7", True),
                 ('"ha"*2=="haha"', True), ("(1<2)==true", True)]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                self.assertIs(self.value(expression), expected)

    def test_precedence_tree(self):
        node = parse(tokenize("x=1+2*3<8"))["statements"]["statements"][0]["expression"]
        self.assertEqual(node["tag"], "<")
        self.assertEqual(node["left"]["tag"], "+")
        self.assertEqual(node["left"]["right"]["tag"], "*")

    def test_print_capture(self):
        output = io.StringIO()
        with redirect_stdout(output):
            _, env = evaluate_source("print(true); saved=__output; print(2<1)")
        self.assertEqual(output.getvalue(), "true\nfalse\n")
        self.assertEqual(env["saved"], "true")
        self.assertEqual(env["__output"], "false")

    def test_input_and_evaluation_order(self):
        with patch("builtins.input", side_effect=["2", "3"]) as read:
            self.assertIs(self.value("number(input()) < number(input())"), True)
        self.assertEqual(read.call_count, 2)
        with patch("builtins.input") as read:
            _, env = evaluate_source('__input="2";result=number(input())==2')
        read.assert_not_called()
        self.assertIs(env["result"], True)
        self.assertEqual(env["__input"], "")

    def test_type_errors(self):
        for expression in ('"a"<"b"', '1<"2"', "true<false", "true+1",
                           "1-true", '"ha"*true', "false/2", "-true"):
            with self.subTest(expression=expression), self.assertRaises(TypeError):
                self.value(expression)

    def test_invalid_syntax(self):
        for source in ("x=1<2<3", "x=1==2==3", "x=1<", "x=<2",
                       "x=true and", "x=not", "print true"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))


if __name__ == "__main__":
    unittest.main()
