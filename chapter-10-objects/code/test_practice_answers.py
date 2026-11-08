"""Execute the answers as written in the chapter, including inline examples."""
import io
from pathlib import Path
import re
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import evaluator

CHAPTER = Path(__file__).resolve().parents[1] / 'chapter-10-objects.md'


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

    def test_add_passed_field_from_inline_answer(self):
        source = re.findall(r'`([^`]+)`', self.answers[0])[0]
        _, env, _ = self.run_source('student={"score":87};' + source)
        self.assertIs(env['student']['passed'], True)
        _, env, _ = self.run_source('student={"score":59};' + source)
        self.assertIs(env['student']['passed'], False)

    def test_alias_and_rebinding_from_question(self):
        _, env, _ = self.run_source(code_blocks(self.questions[1])[0])
        self.assertEqual((env['a']['score'], env['b']['score']), (90, 70))

    def test_deep_copy_answer_and_printed_output(self):
        _, env, out = self.run_source(code_blocks(self.answers[2])[0])
        self.assertEqual(out, '[80, 90]\n[100, 90]\n')
        self.assertIsNot(env['original']['scores'], env['mycopy']['scores'])

    def test_duplicate_key_question_never_reads_input(self):
        expression = re.findall(r'`([^`]+)`', self.questions[3])[0]
        with patch('builtins.input') as read:
            with self.assertRaises(ValueError):
                self.run_source('value=' + expression)
            read.assert_not_called()

    def test_self_cycle_from_inline_answer(self):
        source = re.findall(r'`([^`]+)`', self.answers[4])[0]
        _, env, _ = self.run_source(source)
        self.assertIsNot(env['a'], env['b'])
        self.assertIs(env['b']['self'], env['b'])
