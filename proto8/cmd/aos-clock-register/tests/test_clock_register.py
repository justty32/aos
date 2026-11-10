"""Test aos-clock-register add/rm/ls, aos-clock register (the same thing), and aos-clock sending the registered letters (real aos-post; no daemon)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
REG = PROTO / "cmd" / "aos-clock-register" / "bin" / "aos-clock-register"
CLOCK = PROTO / "cmd" / "aos-clock" / "bin" / "aos-clock"


class ClockRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clock-register-"))
        (self.tmp / "st").mkdir()
        self.clock = self.tmp / "st" / "clock"
        self.box = self.tmp / "st" / "q"
        self.env = dict(os.environ, AOS_CLOCK=str(self.clock), PYTHONDONTWRITEBYTECODE="1")
        for k in ("AOS_WS", "AOS_STACK", "AOS_CF"):
            self.env.pop(k, None)
        subprocess.run(["aos-post", "init", str(self.box)], check=True, env=self.env)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reg(self, *args, stdin=""):
        return subprocess.run([sys.executable, str(REG)] + list(args), input=stdin, capture_output=True, text=True,
                              env=self.env, cwd=self.tmp, timeout=30)

    def tick(self, n=1):
        out = []
        for _ in range(n):
            r = subprocess.run([sys.executable, str(CLOCK), str(self.clock)], capture_output=True, text=True,
                               env=self.env, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "")
            out.append(r.stderr)
        return "".join(out)

    def letters(self):
        new = self.box / "new"
        return [json.loads((new / n / "letter.json").read_text()) for n in sorted(os.listdir(new))]

    def test_no_register_is_silent(self):
        self.assertEqual(self.tick(3), "")
        self.assertEqual(self.clock.read_text(), "3\n")
        self.assertFalse((self.tmp / "st" / "clock_register.json").exists())

    def test_every_aligned_and_rm(self):
        self.clock.write_text("7\n")                       # 登記在 7：仍在 10、20 寄（對齊整數倍）
        r = self.reg("add", "--every", "10", "--box", "st/q", "wake", "Look", "around.")
        self.assertEqual(r.returncode, 0, r.stderr)
        table = json.loads((self.tmp / "st" / "clock_register.json").read_text())["letters"]
        self.assertEqual(table["wake"]["box"], "q")       # 存成相對登記表資料夾
        self.assertEqual(self.tick(14), "")
        got = self.letters()
        self.assertEqual([l["body"]["cycle"] for l in got], [10, 20])
        b = got[0]["body"]
        self.assertEqual((b["role"], b["content"], b["from"], b["status"], b["what"]),
                         ("user", "Look around. (clock cycle 10)", "clock", "PROGRESS", "Look around."))
        self.assertEqual(got[0]["sent_at_cycles"], 10)
        self.assertEqual(self.reg("ls").stdout, "wake\t10\tq\tLook around.\n")
        self.assertEqual(self.reg("rm", "wake").returncode, 0)
        self.tick(10)
        self.assertEqual(len(self.letters()), 2)

    def test_clock_register_word_goes_to_register(self):
        """11-10 深夜：aos-clock register … ＝ aos-clock-register …；./register 仍是時鐘檔。"""
        run = lambda *a: subprocess.run([sys.executable, str(CLOCK)] + list(a), capture_output=True, text=True,
                                        env=self.env, cwd=self.tmp, timeout=30)
        r = run("register", "add", "--every", "5", "--box", "st/q", "w", "hi")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run("register", "ls").stdout, self.reg("ls").stdout)
        self.assertIn("aos-clock-register", run("register", "--help").stdout)
        self.assertEqual(run("./register").returncode, 0)                    # a clock file named register
        self.assertEqual((self.tmp / "register").read_text(), "1\n")

    def test_failures_only_warn(self):
        self.assertEqual(self.reg("add", "--every", "1", "--box", "st/none", "lost", "x").returncode, 0)
        err = self.tick()
        self.assertIn("aos-clock: warning: clock register entry lost: cannot send to", err)
        self.assertIn("MailboxMissing", err)
        self.assertEqual(self.clock.read_text(), "1\n")
        (self.tmp / "st" / "clock_register.json").write_text("{bad")
        self.assertIn("aos-clock: warning: clock register skipped", self.tick())
        (self.tmp / "st" / "clock_register.json").write_text('{"letters": {"a": {"every": 0, "box": "q", "text": "x"}}}')
        self.assertIn("entry 'a' skipped: every must be a positive integer", self.tick())
        self.assertEqual(self.clock.read_text(), "3\n")

    def test_errors(self):
        self.assertEqual(self.reg("add", "--every", "5", "--box", "st/q", "a", "x").returncode, 0)
        r = self.reg("add", "--every", "5", "--box", "st/q", "a", "y")
        self.assertIn("aos-clock-register: error: EntryExists", r.stderr)
        self.assertEqual(self.reg("add", "--replace", "--every", "5", "--box", "st/q", "a", "-", stdin="from stdin\n").returncode, 0)
        self.assertEqual(json.loads(self.reg("ls", "-j").stdout)["letters"]["a"]["text"], "from stdin")
        self.assertIn("ArgumentsBad", self.reg("add", "--every", "0", "--box", "st/q", "b", "x").stderr)
        self.assertIn("EntryMissing", self.reg("rm", "nope").stderr)
        self.assertIn("CommandUnknown", self.reg("set").stderr)
        env = dict(self.env)
        env.pop("AOS_CLOCK")
        r = subprocess.run([sys.executable, str(REG), "ls"], capture_output=True, text=True, env=env, timeout=30)
        self.assertIn("aos-clock-register: error: ClockMissing", r.stderr)


if __name__ == "__main__":
    unittest.main()
