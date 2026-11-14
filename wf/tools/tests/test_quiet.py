# 驗證清淨時段三支程式（quiet.py、quiet_hook.py、quiet_tick.py）：擋下、放行、過期、到期後合併寄出，以及被擋的 kernel_hold 請求還留在 gate。用真的 aos-post；gate 那題借 kernel_gate 自己的測試場。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]
GATE_TESTS = TOOLS.parents[1] / "proto8" / "lib" / "agent" / "kernel_gate" / "tests"
sys.path.insert(0, str(TOOLS))
import quiet  # noqa: E402

MAIL = "[aos] new_mail: %d new letter%s from %s. Look with mailbox_peek, read with mailbox_read."


class QuietTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="quiet-test-", dir=os.environ.get("QUIET_TEST_TMP")))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.stack = self.root / "stack"
        self.stack.mkdir()
        local = Path.home() / ".local" / "bin"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env["PATH"] = os.pathsep.join([str(local), self.env["PATH"]])
        self.run_cmd("aos-post", "init", self.stack / "queue")
        (self.stack / "quiet").mkdir()
        (self.stack / "quiet" / "config.json").write_text(json.dumps({"urgent_senders": ["xiaosi"]}))

    def run_cmd(self, *argv, text=None):
        r = subprocess.run([str(a) for a in argv], input=text, capture_output=True, text=True, env=self.env)
        return r

    def hook(self, content):
        r = self.run_cmd(TOOLS / "quiet_hook.py", text=json.dumps({"event": "before_queue", "stack": str(self.stack), "content": content}))
        self.assertIn(r.returncode, (0, 10), r.stderr)
        return r.returncode

    def tick(self):
        r = self.run_cmd(TOOLS / "quiet_tick.py", text=json.dumps({"event": "on_clock", "stack": str(self.stack)}))
        self.assertEqual(r.returncode, 0, r.stderr)

    def queue(self):
        new = self.stack / "queue" / "new"
        return [json.loads((p / "letter.json").read_text())["body"]["content"] for p in sorted(new.iterdir()) if not p.name.startswith(".")]

    def deferred(self):
        return quiet.read_deferred(str(self.stack / "quiet" / "deferred.jsonl"))

    def on(self, spec="30m"):
        r = self.run_cmd(TOOLS / "quiet.py", "--stack", self.stack, spec)
        self.assertEqual(r.returncode, 0, r.stderr)

    def expire(self):
        (self.stack / "quiet" / "until.json").write_text(json.dumps({"until": time.time() - 5}))

    def test_duration(self):
        self.assertEqual([quiet.parse_duration(x) for x in ("30m", "90s", "1h", "1h30m", "0m", "5x", "30", "")], [1800, 90, 3600, 5400, None, None, None, None])

    def test_not_quiet_lets_everything_through(self):
        self.assertEqual(self.hook(MAIL % (1, "", "bob")), 0)
        self.assertEqual(self.deferred(), [])

    def test_quiet_holds_mail_and_gate_notices_but_nothing_else(self):
        self.on()
        self.assertEqual(self.hook(MAIL % (2, "s", "bob, amy")), 10)
        self.assertEqual(self.hook("[aos] kernel_hold: 1 request held at your kernel station and wait for your decision.\n- letter a\n"), 10)
        for ok in (MAIL % (1, "", "xiaosi"), MAIL % (2, "s", "bob, xiaosi-digest"), "hello", "[aos] goal: go on", "[xsession] hi", "[aos] quiet_over: x"):
            self.assertEqual(self.hook(ok), 0, ok)
        self.assertEqual(len(self.deferred()), 2)

    def test_expired_does_not_hold(self):
        self.on()
        self.expire()
        self.assertEqual(self.hook(MAIL % (1, "", "bob")), 0)

    def test_tick_waits_then_merges_once_and_clears(self):
        self.on()
        self.hook(MAIL % (2, "s", "bob, amy"))
        self.hook(MAIL % (1, "", "bob"))
        self.hook("[aos] kernel_hold: 2 requests held\n- letter a\n    from: x\n- letter b\n    from: y\n")
        self.tick()
        self.assertEqual(self.queue(), [])           # still quiet
        self.expire()
        self.tick()
        out = self.queue()
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("[aos] quiet_over: 3 notices held during the quiet time: new_mail x2 (3 new letters; senders: bob, amy); kernel_hold x1 (letters: a, b)"), out[0])
        self.assertEqual(self.deferred(), [])
        self.tick()
        self.assertEqual(len(self.queue()), 1)       # nothing sent twice

    def test_off_releases_the_held_ones(self):
        self.on()
        self.hook(MAIL % (1, "", "bob"))
        self.assertEqual(self.run_cmd(TOOLS / "quiet.py", "--stack", self.stack, "off").returncode, 0)
        self.assertIn("1 notice held", self.run_cmd(TOOLS / "quiet.py", "--stack", self.stack, "status").stdout)
        self.tick()
        self.assertEqual(len(self.queue()), 1)

    def test_a_held_kernel_request_stays_at_the_gate(self):
        sys.path.insert(0, str(GATE_TESTS))
        import test_kernel_gate as kg
        gate = kg.KernelGateTest("test_02_tick_does_nothing_before_on")
        gate.setUp()
        self.addCleanup(gate.doCleanups)
        gate.ok(op="on")
        gate.send("a", procs_added={"logwatch": {"def": "/defs/x"}})
        self.assertEqual(gate.tick().returncode, 0)
        (notice,) = gate.notices()
        self.stack = gate.stack                      # run our hook against the gate's agent stack
        self.on()
        self.assertEqual(self.hook(notice["content"]), 10)      # the notice is dropped ...
        self.assertEqual(gate.tick().returncode, 0)
        self.assertIn("- letter a\n", gate.ok(op="ls"))         # ... the request is still held
        self.assertTrue((gate.cell / "requests" / "cur" / "a").is_dir())
        self.expire()
        self.tick()
        self.assertIn("kernel_hold x1 (letters: a)", gate.notices()[-1]["content"])
        self.assertIn("- letter a\n", gate.ok(op="ls"))         # and decidable after the summary
        self.assertIn("passed a", gate.ok(op="pass", letter="a"))


if __name__ == "__main__":
    unittest.main()
