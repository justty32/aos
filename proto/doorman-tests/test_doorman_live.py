"""門房第一級：真的把 doorman.py 當一支程式起起來跑（inotify 與輪詢兩條路都測）。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
sys.path.insert(0, PROTO)
import doorman  # noqa: E402

from test_doorman import LAND_ID, make_land  # noqa: E402

SCRIPT = os.path.join(PROTO, "doorman.py")
TIMEOUT_S = 10.0


def wait_for(fn, timeout=TIMEOUT_S, step=0.05):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(step)
    return last


class LiveBase(unittest.TestCase):
    poll = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="doorman-live.")
        self.root = os.path.realpath(os.path.join(self.tmp, "root"))
        self.home = os.path.realpath(os.path.join(self.tmp, "home"))
        os.makedirs(self.root)
        os.makedirs(self.home)
        self.registry = os.path.join(self.home, ".aos", "registry.json")
        self.log = os.path.join(self.home, ".aos", "doorman.jsonl")
        self.proc = None

    def tearDown(self):
        self.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, *extra):
        argv = [sys.executable, SCRIPT, self.root, "--home", self.home,
                "--poll-ms", "150", "--for-ms", "20000"]
        if self.poll:
            argv.append("--poll")
        argv += list(extra)
        self.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, env=dict(os.environ, AOS_HOME=self.home))
        # 等它把開場那一輪掃完（印出「門房起來了」）
        line = self.proc.stdout.readline()
        self.assertIn("門房起來了", line, line)
        self.mode_line = line
        return self.proc

    def stop(self):
        if self.proc is None:
            return None
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            out = self.proc.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out = self.proc.communicate()[0]
        self.proc = None
        return out

    def lines(self):
        if not os.path.exists(self.log):
            return []
        try:
            with open(self.log, encoding="utf-8") as f:
                return [json.loads(ln) for ln in f if ln.strip()]
        except ValueError:
            return []

    def entries(self):
        reg = doorman.read_json(self.registry, {"entries": []}) or {"entries": []}
        return reg.get("entries", [])

    def entry(self, path):
        for e in self.entries():
            if e.get("path") == path:
                return e
        return None

    def expect(self, fn, what, timeout=TIMEOUT_S):
        """等 fn() 變真；等不到才把門房的輸出撈出來當錯誤訊息（別急著 stop）。"""
        got = wait_for(fn, timeout=timeout)
        if not got:
            self.fail("%s\n門房輸出：%s" % (what, self.stop()))
        return got

    # ---- 實際的測試 ----
    def test_live_birth_then_death(self):
        self.start()
        land = make_land(self.root, "alpha")

        e = self.expect(lambda: self.entry(land), "沒等到出生被登記")
        self.assertEqual(e["state"], "stopped")
        self.assertIsNone(e["clock"])
        self.expect(lambda: any(ln["kind"] == "born" and ln["path"] == land
                                for ln in self.lines()), "本子沒有 born")

        shutil.rmtree(land)
        self.expect(lambda: (self.entry(land) or {}).get("ext", {}).get("died_at"),
                    "沒等到死亡被標記")
        self.assertEqual(self.entry(land)["state"], "stopped")
        self.assertTrue(any(ln["kind"] == "gone" and ln["path"] == land for ln in self.lines()))

    def test_live_repeated_life_and_death_keeps_one_entry(self):
        self.start()
        for i in range(3):
            land = make_land(self.root, "beta")
            self.expect(lambda: self.entry(land) and not self.entry(land)["ext"].get("died_at"),
                        "第 %d 次出生沒登記到" % (i + 1))
            shutil.rmtree(land)
            self.expect(lambda: (self.entry(land) or {}).get("ext", {}).get("died_at"),
                        "第 %d 次死亡沒標到" % (i + 1))
        self.assertEqual(len(self.entries()), 1, self.entries())

    def test_land_created_by_plain_write_is_seen(self):
        """不是原子改名（一般 open+write）建出來的地也看得見——S-13-47 只認改名，
        預設不照那條走，理由記在 DOORMAN.md。"""
        self.start()
        land = make_land(self.root, "plain", atomic=False)
        self.expect(lambda: self.entry(land), "非原子建的地沒被看見")


class TestLiveInotify(LiveBase):
    poll = False

    def test_it_really_used_inotify(self):
        self.start()
        self.assertIn("方式 inotify", self.mode_line)
        self.assertEqual([], [ln for ln in self.lines() if ln["kind"] == "fallback"])

    def test_strict_birth_sees_the_rename_when_the_watch_is_already_there(self):
        """--strict-birth 照 S-13-47：只有 layout.json 原子改名那次才算出生。
        前提是 `.aos/` 的 watch 已經裝好了。"""
        self.start("--strict-birth")
        land = os.path.realpath(os.path.join(self.root, "atomic"))
        os.makedirs(os.path.join(land, ".aos"))
        time.sleep(0.8)                       # 等門房把 <地>/.aos 的 watch 裝上
        make_land(self.root, "atomic")        # 這一下才是原子改名
        self.expect(lambda: self.entry(land), "原子改名建的地該被看見")

        plain = os.path.realpath(os.path.join(self.root, "plain"))
        os.makedirs(os.path.join(plain, ".aos"))
        time.sleep(0.8)
        make_land(self.root, "plain", atomic=False)
        time.sleep(1.0)
        self.assertIsNone(self.entry(plain), "S-13-47 之下，非改名建的地不該登記")

    def test_strict_birth_misses_a_land_created_in_one_shot(self):
        """S-13-47 的漏洞（DOORMAN.md 第 2 條）：整塊地一口氣建出來時，
        `.aos/` 的 watch 還沒裝好，那個 IN_MOVED_TO 沒人收得到，就永遠不算出生。"""
        self.start("--strict-birth")
        land = make_land(self.root, "oneshot")     # mkdir + mkdir + rename 一氣呵成
        time.sleep(2.0)
        self.assertIsNone(self.entry(land),
                          "這一題會過反而代表 S-13-47 的競態消失了，記得回頭改 DOORMAN.md")


class TestLivePoll(LiveBase):
    poll = True

    def test_it_really_used_polling(self):
        self.start()
        self.assertIn("方式 poll", self.mode_line)


class TestCli(unittest.TestCase):
    def run_it(self, *argv):
        return subprocess.run([sys.executable, SCRIPT] + list(argv),
                              capture_output=True, text=True, timeout=30)

    def test_tmpfs_note_prints_one_measured_line(self):
        r = self.run_it("--tmpfs-note", "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout.strip().splitlines()
        self.assertEqual(len(out), 1, out)
        self.assertIn("tmpfs", out[0])
        self.assertTrue("有效" in out[0] or "無效" in out[0], out[0])

    def test_missing_root_says_what_to_do_next(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 2)
        self.assertIn("下一步", r.stderr)

    def test_root_that_is_not_a_dir_says_what_to_do_next(self):
        r = self.run_it("/definitely/not/here", "--home", tempfile.mkdtemp())
        self.assertEqual(r.returncode, 2)
        self.assertIn("下一步", r.stderr)

    def test_once_mode_exits_by_itself(self):
        tmp = tempfile.mkdtemp(prefix="doorman-once.")
        self.addCleanup(shutil.rmtree, tmp, True)
        root = os.path.join(tmp, "root")
        home = os.path.join(tmp, "home")
        os.makedirs(root)
        os.makedirs(home)
        land = make_land(root, "a")
        r = self.run_it(root, "--home", home, "--once")
        self.assertEqual(r.returncode, 0, r.stderr)
        reg = doorman.read_json(os.path.join(home, ".aos", "registry.json"))
        self.assertEqual([e["path"] for e in reg["entries"]], [land])


# LiveBase 自己是共用的殼，不要被 discover 當成一組測試跑兩遍
del LiveBase


if __name__ == "__main__":
    unittest.main()
