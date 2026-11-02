"""Execute the Chapter 12 examples and practice answers as printed."""
import io
from pathlib import Path
import re
import unittest
from contextlib import redirect_stdout

from evaluator import evaluate_source

CHAPTER = Path(__file__).resolve().parents[1] / 'chapter-12-scope-and-closures.md'


class PracticeAnswerTests(unittest.TestCase):
    def test_all_chapter_examples(self):
        blocks = re.findall(r'```vertex\n(.*?)```', CHAPTER.read_text(), re.S)
        outputs = ['3\n', 'Hello\n', '6\n15\n21\n', '7\n100\n',
                   '11\n11\n10\n', '9\n', '11\n12\n12\n', '11\n100\n',
                   '1\n2\n11\n', '1\n2\n11\n', '25\n25\n', '1\n2\n2\n0\n',
                   '25\n25\n100\n', '720\n', '23\n', '2\n5\n',
                   '14\n21\n', '13\n16\n', '1\n2\n1\n']
        self.assertEqual(len(blocks), len(outputs))
        for index, (block, expected) in enumerate(zip(blocks, outputs), 1):
            with self.subTest(example=index):
                source = '\n'.join(line[3:] if line.startswith('   ') else line
                                   for line in block.splitlines())
                out = io.StringIO()
                with redirect_stdout(out):
                    result, _ = evaluate_source(source)
                self.assertEqual(result, (None, None))
                self.assertEqual(out.getvalue(), expected)

    def test_five_questions_and_answers(self):
        text = CHAPTER.read_text()
        practice = text.split('## Practice\n', 1)[1].split('## Answers', 1)[0]
        answers = text.split('## Answers to the Practice Questions\n', 1)[1].split('## References', 1)[0]
        for section in (practice, answers):
            self.assertEqual(len(re.findall(r'^\d+\. ', section, re.M)), 5)


if __name__ == '__main__':
    unittest.main()
