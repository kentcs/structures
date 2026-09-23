import io
import unittest
from contextlib import redirect_stdout

from evaluator import evaluate
from parser import parse
from tokenizer import tokenize


class Chapter2CompatibilityTests(unittest.TestCase):
    def test_numeric_programs(self):
        cases = [
            ("x=2; print(x); y=x+3*4; print(y)", "2\n14\n"),
            (";;;x=-1.5+.5*5.;;;print(x);;;", "1.0\n"),
            ("x=--3; x=x+1; print(-(x+2))", "-6\n"),
            ("x=20/2/2; print(x); print(10-3-2)", "5.0\n5\n"),
            ("// start\nx=8; // assignment\nprint(x/2)// end", "4.0\n"),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertIsNone(evaluate(parse(tokenize(source)), {}))
                self.assertEqual(output.getvalue(), expected)

    def test_comment_tokens_and_positions(self):
        for ending in ("\n", "\r\n", "\r"):
            tokens = tokenize("8// ignored @ ; /" + ending + "/2")
            self.assertEqual([t["tag"] for t in tokens], ["number", "/", "number", None])
        for source in ("//", "// at end", "8 // trailing"):
            tokens = tokenize(source)
            self.assertEqual([t["tag"] for t in tokens],
                             ["number", None] if source.startswith("8") else [None])
            self.assertEqual(tokens[-1]["column"], len(source) + 1)
        tokens = tokenize("// first\n  8// second\r\n /2")
        self.assertEqual((tokens[0]["line"], tokens[0]["column"]), (2, 3))
        self.assertEqual((tokens[1]["line"], tokens[1]["column"]), (3, 2))
        self.assertEqual([t["tag"] for t in tokenize("/ /")], ["/", "/", None])

    def test_comments_and_strings(self):
        tokens = tokenize('"https://example.org" // "unterminated \\q\n"//"')
        self.assertEqual([t["tag"] for t in tokens], ["string", "string", None])
        self.assertEqual(tokens[0]["value"], "https://example.org")
        self.assertEqual(tokens[1]["value"], "//")

    def test_rejected_programs(self):
        for source in ("", ";;;", "// only a comment", "x=2 print(x)",
                       "x=2 // ;\nprint(x)", "3=2", "print 2"):
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                parse(tokenize(source))

    def test_evaluation_errors(self):
        for source, error in (("print(missing)", ValueError),
                              ("x=3/0", ZeroDivisionError)):
            with self.subTest(source=source), self.assertRaises(error):
                evaluate(parse(tokenize(source)), {})


if __name__ == "__main__":
    unittest.main()
