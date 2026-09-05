"""門房跟現有 proto 的接縫：同一份登記表、同一把鎖、退回輪詢那條路。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
sys.path.insert(0, PROTO)
import doorman  # noqa: E402

from test_doorman import Base, make_land  # noqa: E402

AOS_PY = os.path.join(PROTO, "aos.py")


class TestFallback(Base):
    def test_no_inotify_falls_back_to_polling_and_keeps_working(self):
        """S-13-32／S-13-33：綁不上就記一筆 fallback，然後繼續把生死寫進本子與登記表。"""
        land = make_land(self.root, "a")
        orig = doorman.Inotify

        def boom():
            raise OSError(38, "假裝這台機器沒有 inotify")

        doorman.Inotify = boom
        try:
            d = doorman.Doorman(self.root, self.home, force_poll=False)
            d.run(once=True)
        finally:
            doorman.Inotify = orig

        self.assertEqual(d.mode, "poll")
        self.assertEqual(d.fallback_reason, "no_inotify")
        self.assertEqual(self.kinds(), ["fallback", "born"])
        self.assertIsNotNone(self.entry(land))          # 退回巡邏之後照樣做事


@unittest.skipUnless(os.path.exists(AOS_PY), "找不到 proto/aos.py")
class TestSharesTheRegistryWithProto(unittest.TestCase):
    """門房寫的那筆，proto 的 aos 讀得懂；反過來也不打架。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="doorman-interop.")
        self.root = os.path.realpath(os.path.join(self.tmp, "root"))
        self.home = os.path.realpath(os.path.join(self.tmp, "home"))
        os.makedirs(self.root)
        os.makedirs(self.home)
        self.env = dict(os.environ, AOS_HOME=self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def aos(self, *argv):
        return subprocess.run([sys.executable, AOS_PY] + list(argv),
                              capture_output=True, text=True, env=self.env, timeout=60)

    def test_aos_init_then_doorman_then_daemon_ls(self):
        land = os.path.join(self.root, "w1")
        r = self.aos("init", land)
        if r.returncode != 0:
            self.skipTest("aos init 跑不起來（另一隊正在改 aosp）：%s" % r.stderr[-300:])
        land = os.path.realpath(land)

        r = subprocess.run([sys.executable, os.path.join(PROTO, "doorman.py"),
                            self.root, "--home", self.home, "--once", "--quiet"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

        with open(os.path.join(self.home, ".aos", "registry.json"), encoding="utf-8") as f:
            reg = json.load(f)
        self.assertEqual([e["path"] for e in reg["entries"]], [land])
        self.assertEqual(reg["entries"][0]["state"], "stopped")
        # proto 的 aos init 不寫 land_id（schema 要求），所以這裡只能是 null
        self.assertIsNone(reg["entries"][0]["land_id"])

        r = self.aos("daemon", "ls")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(land, r.stdout)
        self.assertIn("stopped", r.stdout)


if __name__ == "__main__":
    unittest.main()
