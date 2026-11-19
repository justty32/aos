"""aos.gdb 對真的 aos 樹（start-api 抄一份、假腦）實跑：下斷點→觸發→停→看字條→續→答完；block 那次工具不跑；工具連錯兩次才停；條件壞了 agent 不停也不掛；shell 續了又停＝why() 認得字條是舊的。"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROTO / "lib"))          # 跟 agent 用的 handler（lib/tools/agent/gdb_trigger）同一份裝好的庫
import aos.gdb as g  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV.update(AOS_HOME=str(PROTO), PATH=str(PROTO / "bin") + os.pathsep + ENV["PATH"], PYTHONDONTWRITEBYTECODE="1")


def until(cond, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.1)
    raise AssertionError("timed out")


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="gdb-live-")))
        cls.tree = cls.tmp / "tree"
        shutil.copytree(PROTO / "templates" / "start-api", cls.tree, symlinks=True)
        kj = cls.tree / "llms" / "def" / "kernel.json"
        k = json.loads(kj.read_text())
        k["endpoints"]["fake-math"] = dict(k["endpoints"]["fake"], tool="math", summary="fake brain that calls math with {} (an error)")
        kj.write_text(json.dumps(k))
        cls.logs = [open(cls.tmp / n, "w") for n in ("root.log", "llm.log")]
        cls.procs = [subprocess.Popen(["aos-exec", "root"], cwd=cls.tree, env=ENV, stdin=subprocess.DEVNULL,
                                      stdout=cls.logs[0], stderr=subprocess.STDOUT, start_new_session=True)]
        until(lambda: (cls.tree / ".stack" / "state.json").exists())
        cls.procs.append(subprocess.Popen(["aos-exec", "--stack", "stacks/llm", "def"], cwd=cls.tree / "llms", env=ENV,
                                          stdin=subprocess.DEVNULL, stdout=cls.logs[1], stderr=subprocess.STDOUT, start_new_session=True))
        until(lambda: (cls.tree / "llms" / "stacks" / "llm" / "state.json").exists())
        cls.sh("aos-agent -d .stack ctl add --auto-restart -w . agents/ann")
        os.environ.update(AOS_HOME=str(PROTO), PATH=ENV["PATH"])   # 庫在這個行程裡叫 aos-agent
        g.echo = False
        cls.a = g.attach("ann", daemon=str(cls.tree / ".stack"))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.sh("aos-daemon-ctl -d .stack shutdown", check=False)
            cls.sh("aos-daemon-ctl -d llms/stacks/llm shutdown", check=False)
            for p in cls.procs:
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)          # 只收這個測試自己起的那一群
                    p.wait()
        finally:
            for f in cls.logs:
                f.close()
            shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def sh(cls, cmd, check=True):
        r = subprocess.run(cmd, shell=True, cwd=cls.tree, env=ENV, capture_output=True, text=True, timeout=60)
        if check and r.returncode:
            raise AssertionError("%s: %s" % (cmd, r.stderr))
        return r.stdout

    def setUp(self):
        self.a.clear()
        if self.a.is_paused():
            self.a.resume()
        self.a.agent("llm", "set", "model=fake")

    def answer(self):
        return self.a.listen(timeout_s=30)

    def test_1_stop_look_resume(self):
        name = self.a.stop_before_tool("peek_now_time")
        self.a.say("one")
        self.a.wait_paused()
        why = self.a.why()
        self.assertTrue(why.paused and why.current)
        self.assertEqual(why.notes[-1]["trigger"], "gdb_" + name)
        self.assertEqual(why.notes[-1]["detail"]["name"], "peek_now_time")
        self.assertEqual(self.a.where(), "think")          # 這一格（工具）做完才停
        self.assertEqual(self.a.history(1)[0]["role"], "tool")
        self.assertIn("paused", self.a.state())
        self.a.remove(name)
        self.a.resume()
        self.assertIn("FAKE ANSWER to: one", self.answer())
        self.assertFalse(self.a.why().paused)
        self.assertEqual(self.a.why().notes, [])

    def test_2_block_once(self):
        self.a.stop_before_tool("peek_now_time", block=True, once=True)
        self.a.say("two")
        self.a.wait_paused()
        self.assertTrue(self.a.why().notes[-1]["blocked"])
        last = self.a.history(1)[0]
        self.assertEqual(last["role"], "tool")
        self.assertIn("blocked", last["content"])           # 工具沒跑：腦收到的是被擋的字樣
        self.assertTrue(self.a.triggers()[0]["spent"])
        self.a.resume()
        self.assertIn("FAKE ANSWER to: two", self.answer())
        self.a.say("two again")                             # once：不再停
        self.assertIn("FAKE ANSWER to: two again", self.answer())
        self.assertFalse(self.a.is_paused())

    def test_3_tool_error_twice_in_a_row(self):
        self.a.agent("llm", "set", "model=fake-math")
        self.a.stop_on_tool_error(times=2)
        self.a.say("three a")
        self.assertIn("FAKE ANSWER to: three a", self.answer())   # 第一次錯：還不算
        self.assertFalse(self.a.is_paused())
        self.a.say("three b")
        self.a.wait_paused()
        note = self.a.why().notes[-1]
        self.assertEqual((note["detail"]["name"], note["detail"]["code"]), ("math", 1))
        self.a.resume()
        self.assertIn("FAKE ANSWER to: three b", self.answer())

    def test_4_broken_condition_does_not_stop_or_kill(self):
        self.a.stop_when("before_tool", py=lambda ev: ev["no such key"])
        self.a.stop_when("before_tool", sh="exit 3")
        self.a.say("four")
        self.assertIn("FAKE ANSWER to: four", self.answer())
        self.assertFalse(self.a.is_paused())
        errors = [t["last_error"] for t in self.a.triggers()]
        self.assertTrue(all(errors), errors)
        row = json.loads(self.sh("aos-daemon-ctl -d .stack ls -j"))["procs"]["ann"]
        self.assertEqual((row["phase"], row["reason"]), ("running", None))

    def test_5_shell_resume_then_pause_makes_the_note_old(self):
        self.a.stop_when("before_tool", sh="grep -q peek_now_time", once=True)
        self.a.say("five")
        self.a.wait_paused()
        self.assertTrue(self.a.why().current)
        self.sh("aos-agent -d .stack ctl resume ann")         # 在 shell 續（不經 aos.gdb）
        self.assertIn("FAKE ANSWER to: five", self.answer())
        self.sh("aos-agent -d .stack ctl pause ann")          # 又在 shell 手動停
        why = self.a.why()
        self.assertTrue(why.paused)
        self.assertFalse(why.current)                        # 字條是上一次的
        self.assertIn("may be old", repr(why))

    def test_6_two_triggers_on_one_event(self):
        self.a.stop_before_tool("peek_now_time", name="first")
        self.a.stop_when("before_tool", py="ev['name'].startswith('peek')", name="second")
        self.a.say("six")
        self.a.wait_paused()
        why = self.a.why()
        self.assertEqual([n["trigger"] for n in why.notes], ["gdb_first", "gdb_second"])   # 兩張都在，不互蓋
        self.assertTrue(why.current)
        self.a.clear()
        self.a.resume()
        self.assertIn("FAKE ANSWER to: six", self.answer())


if __name__ == "__main__":
    unittest.main()
