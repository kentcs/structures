"""Assignment destinations and print effects in the released interpreter."""

import contextlib
import io
import unittest

from evaluator import evaluate, evaluate_source
from parser import parse_expression, parse_print_statement
from tokenizer import tokenize


class AssignmentTests(unittest.TestCase):
    def test_target_is_identifier_and_creates_binding(self):
        tree, _ = parse_expression(tokenize("x = 2"))
        self.assertEqual(tree["target"], {"tag": "identifier", "value": "x"})
        environment = {}
        # ===== CHAPTER 11: assignment evaluates to the assigned value =====
        self.assertEqual(evaluate(tree, environment), (2, None))
        self.assertEqual(environment["x"], 2)

    def test_reassignment_reads_old_value_only_on_right(self):
        tree, _ = parse_expression(tokenize("x = x + 3"))
        environment = {"x": 2}
        self.assertEqual(evaluate(tree, environment), (5, None))
        self.assertEqual(environment["x"], 5)

    def test_non_identifier_targets_parse_but_are_rejected_at_evaluation(self):
        # ===== CHAPTER 11: the parser no longer restricts what can appear
        # to the left of "=" -- any expression may; evaluation decides
        # whether that expression is actually assignable. =====
        for source in ['"x" = 2', "2 = 3"]:
            with self.subTest(source=source):
                tree, _ = parse_expression(tokenize(source))
                self.assertEqual(tree["tag"], "assign")
                with self.assertRaises(ValueError):
                    evaluate(tree, {})

    def test_parentheses_around_a_target_are_transparent(self):
        # Parentheses only group; they build no AST node of their own, so
        # (x) = 2 parses to the exact same target as x = 2 and is just as
        # assignable.
        tree, _ = parse_expression(tokenize("(x) = 2"))
        self.assertEqual(tree, {
            "tag": "assign",
            "target": {"tag": "identifier", "value": "x"},
            "expression": {"tag": "number", "value": 2},
        })
        environment = {}
        self.assertEqual(evaluate(tree, environment), (2, None))
        self.assertEqual(environment["x"], 2)

    def test_assignment_chains_right_associatively(self):
        # ===== CHAPTER 11: assignment is a right-associative expression =====
        # x = y = 1 parses as x = (y = 1): y is assigned first, that
        # assignment evaluates to 1, and x is assigned that same 1.
        _, environment = evaluate_source("x = y = 1;")
        self.assertEqual(environment["x"], 1)
        self.assertEqual(environment["y"], 1)

    def test_string_node_is_not_an_assignment_destination(self):
        tree = {"tag": "assign", "target": {"tag": "string", "value": "x"},
                "expression": {"tag": "number", "value": 2}}
        environment = {}
        with self.assertRaises(ValueError):
            evaluate(tree, environment)
        self.assertEqual(environment, {})

    def test_print_returns_none_and_writes_output(self):
        tree, _ = parse_print_statement(tokenize("print(3)"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = evaluate(tree, {})
        self.assertEqual(result, (None, None))
        self.assertEqual(output.getvalue(), "3\n")


if __name__ == "__main__":
    unittest.main()
