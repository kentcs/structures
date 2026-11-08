"""Execute the answers as written in the chapter, including inline examples."""
import io
from pathlib import Path
import re
import unittest
from contextlib import redirect_stdout

import evaluator

CHAPTER = Path(__file__).resolve().parents[1] / 'chapter-11-functions.md'


def numbered(section):
    return re.split(r'(?m)^(?=\d+\. )', section)[1:]


def code_blocks(text):
    blocks = re.findall(r'```vertex\n(.*?)```', text, re.S)
    return ['\n'.join(line[3:] if line.startswith('   ') else line
                      for line in block.splitlines()) for block in blocks]


class PracticeAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = CHAPTER.read_text()
        cls.questions = numbered(text.split('## Practice\n', 1)[1].split('## Answers', 1)[0])
        cls.answers = numbered(text.split('## Answers to the Practice Questions\n', 1)[1].split('## References', 1)[0])

    def run_source(self, source):
        out = io.StringIO()
        with redirect_stdout(out):
            result, env = evaluator.evaluate_source(source)
        return result, env, out.getvalue()

    def test_all_five_answers_present(self):
        self.assertEqual(len(self.questions), 5)
        self.assertEqual(len(self.answers), 5)

    def test_max_of_answer_picks_the_larger_argument(self):
        source = code_blocks(self.answers[0])[0]
        _, env, _ = self.run_source(source + 'x = maxOf(3, 9); y = maxOf(9, 3);')
        self.assertEqual(env['x'], 9)
        self.assertEqual(env['y'], 9)

    def test_count_down_answer_prints_descending_lines(self):
        source = code_blocks(self.answers[1])[0]
        _, _, out = self.run_source(source + 'countDown(4);')
        self.assertEqual(out, '4\n3\n2\n1\n')

    def test_sum_to_answer_and_base_case_from_inline_text(self):
        source = code_blocks(self.answers[2])[0]
        _, env, _ = self.run_source(source + 'x = sumTo(5); z = sumTo(0);')
        self.assertEqual(env['x'], 15)
        self.assertEqual(env['z'], 0)
        self.assertIn('`sumTo(0)` returns `0`', self.answers[2])

    def test_show_greeting_question_predicts_the_unbound_identifier_error(self):
        source = '''function showGreeting() { print(greeting) };
showGreeting();
'''
        with self.assertRaises(ValueError) as caught:
            self.run_source(source)
        self.assertEqual(str(caught.exception), 'Unknown identifier: greeting')
        self.assertIn('Unknown identifier: greeting', self.answers[3])

    def test_is_empty_answer_from_code_block(self):
        source = code_blocks(self.answers[4])[0]
        _, _, out = self.run_source(source)
        self.assertEqual(out, 'nothing here\n')


if __name__ == '__main__':
    unittest.main()
