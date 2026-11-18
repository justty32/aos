"""Test aos-clock-register --after/--at/--cron and aos-clock firing them: one-time entries remove themselves, cron moves next, missed ones are sent once (real aos-post; no daemon)."""
import datetime
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
sys.path.insert(0, str(PROTO / "py"))
import aos_clock_register as reg  # noqa: E402


def iso(t):
    return t.astimezone().isoformat(timespec="seconds")


class OnceCron(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clock-once-cron-"))
        (self.tmp / "st").mkdir()
        self.clock = self.tmp / "st" / "clock"
        self.table = self.tmp / "st" / "clock_register.json"
        self.box = self.tmp / "st" / "q"
        self.env = dict(os.environ, AOS_CLOCK=str(self.clock), PYTHONDONTWRITEBYTECODE="1")
        for k in ("AOS_WS", "AOS_STACK", "AOS_CF"):
            self.env.pop(k, None)
        subprocess.run(["aos-post", "init", str(self.box)], check=True, env=self.env)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reg(self, *args):
        return subprocess.run([sys.executable, str(REG)] + list(args), capture_output=True, text=True,
                              env=self.env, cwd=self.tmp, timeout=30)

    def tick(self, n=1):
        err = ""
        for _ in range(n):
            r = subprocess.run([sys.executable, str(CLOCK), str(self.clock)], capture_output=True, text=True,
                               env=self.env, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            err += r.stderr
        return err

    def letters(self):
        new = self.box / "new"
        return [json.loads((new / n / "letter.json").read_text())["body"] for n in sorted(os.listdir(new))]

    def entries(self):
        return json.loads(self.table.read_text())["letters"]

    def edit(self, name, **kv):
        doc = json.loads(self.table.read_text())
        doc["letters"][name].update(kv)
        self.table.write_text(json.dumps(doc))

    def test_after_once_then_gone(self):
        self.clock.write_text("7\n")
        r = self.reg("add", "--after", "3", "--box", "st/q", "once", "Look", "again.")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "added once: once at cycle 10 (now 7) to %s\n" % self.box)
        self.assertEqual(self.entries()["once"]["at_cycle"], 10)
        self.assertEqual(self.reg("ls").stdout, "once\tcycle 10\tq\tLook again.\n")
        self.assertEqual(self.tick(2), "")
        self.assertEqual(self.letters(), [])
        self.assertEqual(self.tick(5), "")                    # cycle 10 寄、之後不再寄
        got = self.letters()
        self.assertEqual([(b["cycle"], b["content"]) for b in got], [(10, "[aos] clock: cycle 10. Look again.")])
        self.assertNotIn("due", got[0])
        self.assertEqual(self.entries(), {})

    def test_at_once_and_late(self):
        r = self.reg("add", "--at", "+1h", "--box", "st/q", "ping", "Call ann.")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("added ping: once at ", r.stdout)
        self.assertTrue(self.reg("ls").stdout.startswith("ping\tat 20"))
        self.tick(2)
        self.assertEqual(self.letters(), [])                  # 還沒到
        due = (datetime.datetime.now() - datetime.timedelta(hours=2, minutes=5)).replace(second=0, microsecond=0)
        self.edit("ping", at_time=iso(due))                    # 假裝樹睡過了到期時刻
        self.assertEqual(self.tick(), "")
        got = self.letters()
        self.assertEqual(len(got), 1)
        self.assertIn("due %s (late by 2h 5m). Call ann." % due.strftime("%Y-%m-%d %H:%M"), got[0]["content"])
        self.assertEqual(got[0]["due"], iso(due))
        self.assertEqual(self.entries(), {})
        self.tick(2)
        self.assertEqual(len(self.letters()), 1)

    def test_cron_missed_many_sent_once(self):
        r = self.reg("add", "--cron", "*/5  *  * * *", "--box", "st/q", "poll", "Poll.")
        self.assertEqual(r.returncode, 0, r.stderr)
        e = self.entries()["poll"]
        self.assertEqual(e["cron"], "*/5 * * * *")
        self.assertGreater(datetime.datetime.fromisoformat(e["next"]), datetime.datetime.now().astimezone())
        self.assertIn("poll\tcron */5 * * * * next ", self.reg("ls").stdout)
        self.edit("poll", next=iso(datetime.datetime.now() - datetime.timedelta(hours=1)))   # 錯過 12 次
        self.tick(3)
        self.assertEqual(len(self.letters()), 1)
        nxt = datetime.datetime.fromisoformat(self.entries()["poll"]["next"])
        self.assertGreater(nxt, datetime.datetime.now().astimezone())
        self.assertEqual(nxt.minute % 5, 0)

    def test_failed_send_still_used(self):
        self.assertEqual(self.reg("add", "--after", "1", "--box", "st/nobox", "lost", "x").returncode, 0)
        err = self.tick()
        self.assertIn("aos-clock: warning: clock register entry lost: cannot send to", err)
        self.assertEqual(self.entries(), {})                   # 同 every：寄不到只提醒一次
        self.assertEqual(self.tick(), "")

    def test_replaced_entry_not_removed(self):
        """寫回前重讀：寄時那格已被換掉＝不動它（直接呼叫 fire，模擬寄的同時別人 add --replace）。"""
        self.clock.write_text("4\n")
        self.assertEqual(self.reg("add", "--after", "1", "--box", "st/q", "w", "old").returncode, 0)
        used = {"w": self.entries()["w"]}
        self.edit("w", text="new", at_cycle=99)
        self.assertEqual(reg.write_back(str(self.table), used, datetime.datetime.now().astimezone()), [])
        self.assertEqual(self.entries()["w"]["at_cycle"], 99)

    def test_bad_hand_edited_entries_skipped(self):
        self.table.write_text(json.dumps({"letters": {
            "two": {"every": 2, "at_cycle": 3, "box": "q", "text": "x"},
            "nonext": {"cron": "* * * * *", "box": "q", "text": "x"},
            "badtime": {"at_time": "tomorrow", "box": "q", "text": "x"}}}))
        err = self.tick()
        self.assertIn("entry 'two' skipped: give only one of", err)
        self.assertIn("entry 'nonext' skipped: next:", err)
        self.assertIn("entry 'badtime' skipped: at_time:", err)
        self.assertEqual(self.letters(), [])

    def test_errors(self):
        bad = lambda *a: self.reg("add", *a, "--box", "st/q", "n", "x").stderr
        self.assertIn("ArgumentsBad give exactly one of --every, --after, --at, --cron (got none)", bad())
        self.assertIn("(got --every, --at)", bad("--every", "2", "--at", "+1m"))
        self.assertIn("ArgumentsBad --after needs a positive integer", bad("--after", "0"))
        self.assertIn("is in the past", bad("--at", "2020-01-01 00:00"))
        self.assertIn("ArgumentsBad at 'later'", bad("--at", "later"))
        self.assertIn("ArgumentsBad cron", bad("--cron", "* * *"))
        self.assertIn("never fires", bad("--cron", "0 0 31 2 *"))
        self.clock.write_text("x\n")
        self.assertIn("ClockBad", bad("--after", "2"))
        self.assertFalse(self.table.exists())


if __name__ == "__main__":
    unittest.main()
