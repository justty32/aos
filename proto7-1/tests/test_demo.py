"""示範場景整合測：跑 demo/play.py（安靜模式），該發生的事全部發生、沒有殘留程序。"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
P71 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import _proc  # noqa: E402


class TestDemo(unittest.TestCase):
    def test_play(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, "root")
        # play.py 收到 SIGTERM 會走 finally 停掉自己的 daemon；逾時、assertion 失敗都先收它再刪空間（N-55）
        p = _proc.track(self, subprocess.Popen([sys.executable, os.path.join(P71, "demo", "play.py"),
                                                "--root", root, "--seconds", "6", "--quiet"],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
                        grace=15)
        out, err = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 0, out + err)
        self.assertNotIn("[--]", out)


if __name__ == "__main__":
    unittest.main()
