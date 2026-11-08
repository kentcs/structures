"""Run the complete language-level suite without leaving generated fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class VertexSuiteTests(unittest.TestCase):
    def test_complete_suite(self):
        code = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            suite = Path(directory) / "test-suite.v"
            shutil.copyfile(code.parents[1] / "chapter-16-test-suite" / "code" / suite.name, suite)
            result = subprocess.run(
                [sys.executable, str(code / "runner.py"), str(suite)],
                cwd=directory, capture_output=True, text=True, timeout=30,
                stdin=subprocess.DEVNULL,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("PASS: 280 checks in 22 sections", result.stdout)


if __name__ == "__main__":
    unittest.main()
