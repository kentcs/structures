"""Assignment destinations and print effects in the released interpreter."""

import contextlib
import io
import unittest

from evaluator import evaluate
from parser import parse_assignment_statement, parse_print_statement
from tokenizer import tokenize


class AssignmentTests(unittest.TestCase):
    def test_target_is_identifier_and_creates_binding(self):
        tree, _ = parse_assignment_statement(tokenize("x = 2"))
        self.assertEqual(tree["target"], {"tag": "identifier", "value": "x"})
        environment = {}
        self.assertIsNone(evaluate(tree, environment))
        self.assertEqual(environment["x"], 2)

    def test_reassignment_reads_old_value_only_on_right(self):
        tree, _ = parse_assignment_statement(tokenize("x = x + 3"))
        environment = {"x": 2}
        self.assertIsNone(evaluate(tree, environment))
        self.assertEqual(environment["x"], 5)

    def test_non_identifier_targets_are_rejected(self):
        for source in ['"x" = 2', "2 = 3", "(x) = 2"]:
            with self.subTest(source=source):
                with self.assertRaises((SyntaxError, AssertionError)):
                    parse_assignment_statement(tokenize(source))

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
        self.assertIsNone(result)
        self.assertEqual(output.getvalue(), "3\n")


if __name__ == "__main__":
    unittest.main()
