import operator
import unittest
from unittest.mock import patch

from evaluator import evaluate_source


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
        with patch("builtins.input") as read:
            result, env = evaluate_source('result="old";result=exit(7)<input()')
        read.assert_not_called()
        self.assertEqual(result, (7, "exit"))
        self.assertEqual(env["result"], "old")
        result, env = evaluate_source('__input="ant";result="old";result=input()<exit(7)')
        self.assertEqual(result, (7, "exit"))
        self.assertEqual(env["result"], "old")
        self.assertEqual(env["__input"], "")

    def test_operands_evaluated_once_left_to_right(self):
        with patch("builtins.input", side_effect=["ant", "bee"]) as read:
            self.assertIs(self.value("input() < input()"), True)
        self.assertEqual(read.call_count, 2)


if __name__ == "__main__":
    unittest.main()
