"""Test that aos-agent hook add on a loop point (before_run / after_run / after_start / after_stop) warns in one stderr line when the definition's loop.json does not wire it, still adds the hook, and is quiet when it does (no flag files since 11-21)."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件

REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"
FIRE = ["aos-hook", "fire", "-q", "--stop-on-nonzero", "--def", {"$env": "AOS_CD"}]


class HookLoopWarning(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-hook-loop-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"entry": "body.json"}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({"gate": {"event": "after_run", "handler": "gate.sh"}}))
        self.loop({"on_start": FIRE + ["after_start"], "on_stop": FIRE + ["after_stop"]})   # like the template
        (self.tmp / "h").mkdir()
        (self.tmp / "h" / "guard").write_text("#!/bin/sh\nexit 0\n")
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))

    def loop(self, wires):
        (self.defn / "loop.json").write_text(json.dumps(dict({"run": ["./run"], "interval_ms": 1000}, **wires)))

    def agent(self, *args):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "hook", "--target", "bob", *[str(a) for a in args]],
                           env=env_helper.clean_env(drop=("TC_",)), capture_output=True, text=True, timeout=60,
                           cwd=self.tmp, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def warnings(self, p):
        """the loop.json warnings (the first add also notes "created ..." on stderr)."""
        return [l for l in p.stderr.splitlines() if l.startswith("aos-agent: warning:") and "loop.json" in l]

    def own(self):
        return json.loads((self.stack / "hookeds.json").read_text())

    def test_not_wired_warns_and_still_adds(self):
        for event, key in (("before_run", "on_before_run"), ("after_run", "on_after_run")):
            with self.subTest(event=event):
                p = self.agent("add", "--event", event, "-n", "h_" + event, "h/guard")
                lines = self.warnings(p)
                self.assertEqual(len(lines), 1, p.stderr)
                self.assertIn("%s/loop.json has no %s, so nothing fires %s" % (self.defn, key, event), lines[0])
                self.assertIn("recompile", lines[0])
                self.assertEqual(self.own()["h_" + event]["event"], event)
                self.assertIn("added h_" + event, p.stdout)

    def test_wired_is_quiet(self):
        p = self.agent("add", "--event", "after_start", "-n", "up", "h/guard")      # the template wires on_start
        self.assertEqual(self.warnings(p), [])
        self.loop({"on_start": FIRE + ["after_start"], "on_before_run": FIRE + ["before_run"]})
        self.assertEqual(self.warnings(self.agent("add", "--event", "before_run", "--condition", "act", "-n", "hold", "h/guard")), [])
        self.assertEqual(self.own()["hold"]["condition"], "act")
        self.assertEqual(len(self.warnings(self.agent("add", "--event", "after_stop", "-n", "down", "h/guard"))), 1)   # on_stop gone now
        self.loop({"on_after_run": None})                                           # null = not wired
        self.assertEqual(len(self.warnings(self.agent("add", "--event", "after_run", "-n", "late", "h/guard"))), 1)

    def test_other_events_and_no_loop_json(self):
        self.assertEqual(self.warnings(self.agent("add", "--event", "after_tool", "-n", "seen", "h/guard")), [])
        (self.defn / "loop.json").unlink()                                          # no loop.json: nothing to check
        self.assertEqual(self.warnings(self.agent("add", "--event", "before_run", "-n", "b", "h/guard")), [])
        self.agent("rm", "gate")
        self.agent("reset", "-y")
        self.assertEqual(sorted(p.name for p in self.stack.iterdir()), [])          # no flag files, ever


if __name__ == "__main__":
    unittest.main()
