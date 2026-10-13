"""Runs the code in the chapter's "Answers to the Practice Questions".

The tests read the chapter text, so the printed answers cannot drift from
what the evaluator actually does.
"""
import contextlib
import io
import os
import re
import unittest

import evaluator
from parser import parse
from tokenizer import tokenize

CHAPTER = os.path.join(os.path.dirname(__file__), "..",
                       "chapter-09-lists-and-indexing.md")


def answer_blocks():
    """Return the vertex code blocks of each numbered answer, in order."""
    with open(CHAPTER) as chapter_file:
        text = chapter_file.read()
    section = text.split("## Answers to the Practice Questions", 1)[1]
    answers = re.split(r"(?m)^(?=\d+\. )", section)[1:]
    return [re.findall(r"```vertex\n(.*?)```", a, re.S) for a in answers]


def run(source):
    """Run source; return (printed lines, final environment)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        _, environment = evaluator.evaluate_source(source, {})
    return out.getvalue().split("\n")[:-1], environment


class PracticeAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks = answer_blocks()

    def test_six_answers_found(self):
        self.assertEqual([len(b) for b in self.blocks], [1, 1, 0, 2, 1, 1])

    def test_1_largest_value(self):
        printed, _ = run(self.blocks[0][0])
        self.assertEqual(printed, ["9"])

    def test_1_largest_value_with_negatives(self):
        source = self.blocks[0][0].replace(
            "[3, 1, 4, 1, 5, 9, 2, 6]", "[-5, -2, -9]")
        printed, _ = run(source)
        self.assertEqual(printed, ["-2"])

    def test_1_empty_list_is_index_error(self):
        source = self.blocks[0][0].replace(
            "[3, 1, 4, 1, 5, 9, 2, 6]", "[]")
        with self.assertRaises(IndexError):
            run(source)

    def test_2_alias_sees_every_update(self):
        printed, _ = run(self.blocks[1][0])
        self.assertEqual(printed, ["[75, 85, 95]"])

    def test_3_exit_after_index_check_leaves_grid_unchanged(self):
        environment = {}
        ast = parse(tokenize(
            "grid = [[1, 2], [3, 4]]; grid[0][1] = exit(4);"))
        result, status = evaluator.evaluate(ast, environment)
        self.assertEqual((result, status), (4, "exit"))
        self.assertEqual(environment["grid"], [[1, 2], [3, 4]])

    def test_3_bad_index_raises_before_exit_runs(self):
        with self.assertRaises(IndexError):
            run("a = [1]; a[5] = exit(4);")

    def test_4_list_copy_is_new(self):
        printed, _ = run(self.blocks[3][0] +
                         "\ncopy[0] = 99;\nprint(original);\nprint(copy);")
        self.assertEqual(printed, ["[1, 2, 3]", "[1, 2, 3]", "[99, 2, 3]"])

    def test_4_string_copy(self):
        printed, _ = run(self.blocks[3][1])
        self.assertEqual(printed, ["hello"])

    def test_5_even_length_joins_back(self):
        printed, _ = run(self.blocks[4][0])
        self.assertEqual(printed, ["[1, 2, 3, 4]"])

    def test_5_odd_length_is_type_error(self):
        source = self.blocks[4][0].replace("[1, 2, 3, 4]", "[1, 2, 3, 4, 5]")
        with self.assertRaises(TypeError):
            run(source)

    def test_6_reversal(self):
        printed, _ = run(self.blocks[5][0])
        self.assertEqual(printed, ["desserts"])

    def test_6_assignment_into_string_is_type_error(self):
        with self.assertRaises(TypeError):
            run('word = "stressed"; word[0] = "S";')

    def test_6_rebuild_gives_stressed(self):
        printed, _ = run('word = "stressed"; word = "S" + tail(word); '
                         'print(word);')
        self.assertEqual(printed, ["Stressed"])


if __name__ == "__main__":
    unittest.main()
