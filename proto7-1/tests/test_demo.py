"""示範場景整合測：跑 demo/play.py（安靜模式），該發生的事全部發生、沒有殘留程序。"""
import os
import subprocess
import sys
import tempfile
import unittest

P71 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDemo(unittest.TestCase):
    def test_play(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            p = subprocess.run([sys.executable, os.path.join(P71, "demo", "play.py"),
                                "--root", root, "--seconds", "6", "--quiet"],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertNotIn("[--]", p.stdout)


if __name__ == "__main__":
    unittest.main()
