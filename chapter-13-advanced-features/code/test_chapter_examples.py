"""Run the chapter's printed programs, with file blocks as module fixtures."""
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from native_functions import NATIVE_FUNCTIONS
from contextlib import redirect_stdout, chdir

from evaluator import evaluate_source

CHAPTER = Path(__file__).resolve().parents[1] / 'chapter-13-advanced-features.md'


class ChapterExampleTests(unittest.TestCase):
    def test_printed_programs(self):
        blocks = re.findall(r'```vertex\n(.*?)```', CHAPTER.read_text(), re.S)
        files = {}
        programs = []
        for block in blocks:
            block = '\n'.join(line[3:] if line.startswith('   ') else line for line in block.splitlines())
            match = re.match(r'// file: (.+)\n', block)
            if match:
                files[match.group(1)] = block
            else:
                programs.append(block)
        expected = ['3.0\n', '4.0\n5.0\n', '5.0\nfunction\ntrue\n', '6.0\n', '5.0\n', '7\n',
                    '2\n25\n3.0\n', '15\n', '1\n2\n0\n', '1\n1\n', '10\n9\n',
                    '10.0\n', '3.0\n', '12\n', '0\n1\n', '32.0\n']
        expected.insert(11, 'true\n')
        self.assertEqual(len(programs),len(expected))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                NATIVE_FUNCTIONS, {"combine": lambda a, b: a + b}):
            root=Path(tmp)
            for name,text in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            for index,(source,output) in enumerate(zip(programs,expected),1):
                with self.subTest(program=index):
                    out=io.StringIO()
                    with chdir(root), redirect_stdout(out):
                        result,_=evaluate_source(source,source_path=root/'main.v')
                    self.assertEqual(result,(None,None))
                    self.assertEqual(out.getvalue(),output)

    def test_five_questions_and_answers(self):
        text=CHAPTER.read_text()
        for section in (text.split('## Practice\n',1)[1].split('## Answers',1)[0],
                        text.split('## Answers to the Practice Questions\n',1)[1].split('## References',1)[0]):
            self.assertEqual(len(re.findall(r'^\d+\. ',section,re.M)),5)


if __name__=='__main__':unittest.main()

