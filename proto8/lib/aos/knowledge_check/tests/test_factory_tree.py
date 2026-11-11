"""The stock knowledge base (proto8/knowledge) passes knowledge_check with no errors; warnings are allowed."""
from pathlib import Path
import subprocess
import sys
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'
HOME = Path(__file__).resolve().parents[4]


class FactoryTree(unittest.TestCase):
    def test_no_errors(self):
        got = subprocess.run([sys.executable, str(ENTRY), '--home', str(HOME)], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=900)
        errors = [l for l in got.stdout.splitlines() if ': error: ' in l and 'CheckFailed' not in l]
        self.assertEqual(errors, [], '\n'.join(errors[:40]))
        self.assertEqual(got.returncode, 0, got.stdout[-2000:] + got.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
