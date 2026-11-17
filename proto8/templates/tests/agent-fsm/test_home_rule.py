"""Path rule one (11-17): template programs copied out of the home find lib only through AOS_HOME, and say HomeMissing when it is unset."""
# 重現 1（thinking/2026-11/17/路徑規則/02）當驗收：範本抄到 proto8 外的暫存夾，關掉 user site、不給 PYTHONPATH：
#   給 AOS_HOME＝這份 proto8 → --help 退 0；不給 → 一行 HomeMissing、退 1。agent-fsm 四格、tool-python、judge-llm 各一次。
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
CASES = (("agent-fsm", "idle.py"), ("agent-fsm", "brain.py"), ("agent-fsm", "wait.py"), ("agent-fsm", "act.py"),
         ("tool-python", "tool.py"), ("judge-llm", "_entry"))


class HomeRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="home-rule-"))
        for name in {c[0] for c in CASES}:
            shutil.copytree(PROTO / "templates" / name, cls.tmp / name, ignore=shutil.ignore_patterns("__pycache__", "tests"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_copy(self, folder, program, home):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and k != "PYTHONPATH"}
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        if home:
            env["AOS_HOME"] = str(PROTO)
        return subprocess.run([sys.executable, str(self.tmp / folder / program), "--help"], cwd=str(self.tmp),
                              env=env, capture_output=True, text=True, timeout=60)

    def test_with_home_runs(self):
        for folder, program in CASES:
            with self.subTest(program=folder + "/" + program):
                r = self.run_copy(folder, program, True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("usage", r.stdout.lower())

    def test_without_home_says_so(self):
        for folder, program in CASES:
            with self.subTest(program=folder + "/" + program):
                r = self.run_copy(folder, program, False)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                lines = r.stderr.strip().splitlines()
                self.assertEqual(len(lines), 1, r.stderr)
                self.assertIn(": error: HomeMissing ", lines[0])


if __name__ == "__main__":
    unittest.main()
