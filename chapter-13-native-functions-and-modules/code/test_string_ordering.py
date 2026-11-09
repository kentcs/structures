import operator
import unittest
from unittest.mock import patch

from evaluator import evaluate, evaluate_source


def exit_node(value=7):
    return {"tag": "exit", "expression": {"tag": "number", "value": value}}


def evaluate_program(statements, environment=None):
    # ===== exit no longer nests inside a larger expression, so a program
    # that needs one mid-expression is built directly instead of parsed
    # from source text, the same way evaluate_source builds one from text. =====
    if environment is None:
        environment = {}
    ast = {"tag": "program", "statements": {"tag": "statement_list", "statements": statements}}
    return evaluate(ast, environment), environment


class StringOrderingTests(unittest.TestCase):
    def value(self, expression):
        return evaluate_source("result=" + expression)[1]["result"]

    def test_all_operators_and_boundaries(self):
        pairs = [("ant", "bee"), ("bee", "ant"), ("ant", "ant"),
                 ("", ""), ("", "a"), ("a", ""), ("a", "ant"),
                 ("ant", "a"), ("Z", "a"), ("10", "2"),
                 ("z", "\u00e9")]
        for symbol, compare in [("<", operator.lt), ("<=", operator.le),
                                (">", operator.gt), (">=", operator.ge)]:
            for left, right in pairs:
                expression = f'"{left}" {symbol} "{right}"'
                with self.subTest(expression=expression):
                    self.assertIs(self.value(expression), compare(left, right))

    def test_incompatible_types_remain_errors(self):
        for symbol in ("<", "<=", ">", ">="):
            for left, right in [('"1"', "1"), ("1", '"1"'),
                                ("true", '"a"'), ('"a"', "false"),
                                ("false", "true")]:
                with self.subTest(symbol=symbol, left=left, right=right):
                    with self.assertRaises(TypeError):
                        self.value(f"{left} {symbol} {right}")

    def test_exit_propagates_before_comparison_or_storage(self):
        target = {"tag": "identifier", "value": "result"}
        set_old = {"tag": "assign", "target": target, "expression": {"tag": "string", "value": "old"}}
        with patch("builtins.input") as read:
            result, env = evaluate_program([
                set_old,
                {"tag": "assign", "target": target,
                 "expression": {"tag": "<", "left": exit_node(7),
                                "right": {"tag": "input", "prompt": None}}},
            ])
        read.assert_not_called()
        self.assertEqual(result, (7, "exit"))
        self.assertEqual(env["result"], "old")
        result, env = evaluate_program([
            {"tag": "assign", "target": {"tag": "identifier", "value": "__input"},
             "expression": {"tag": "string", "value": "ant"}},
            set_old,
            {"tag": "assign", "target": target,
             "expression": {"tag": "<", "left": {"tag": "input", "prompt": None},
                            "right": exit_node(7)}},
        ])
        self.assertEqual(result, (7, "exit"))
        self.assertEqual(env["result"], "old")
        self.assertEqual(env["__input"], "")

    def test_operands_evaluated_once_left_to_right(self):
        with patch("builtins.input", side_effect=["ant", "bee"]) as read:
            self.assertIs(self.value("input() < input()"), True)
        self.assertEqual(read.call_count, 2)


if __name__ == "__main__":
    unittest.main()
