"""Test that aos-agent hook add / rm / reset keep the before_run / after_run flag files in the agent's stack (hook cut 5, second half), and that ls / get leave them alone."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import env_helper  # noqa: E402  同夾的共用零件

REPO = Path(__file__).resolve().parents[5]
BIN = REPO / "proto8" / "bin" / "aos-agent"


class HookFlags(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-hook-flags-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {
            "hooks": "hooks.json", "hook_points": [{"provider": "aos-loop"}, {"provider": "agent-fsm"}]}}))
        (self.defn / "hooks.json").write_text(json.dumps({"hooks": {"gate": {"event": "after_run", "handler": "gate.sh"}}}))
        (self.tmp / "h").mkdir()
        (self.tmp / "h" / "guard").write_text("#!/bin/sh\nexit 0\n")
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": {
            "phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)}}}))

    def agent(self, *args):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "hook", "--target", "bob", *[str(a) for a in args]],
                           env=env_helper.clean_env(drop=("TC_",)), capture_output=True, text=True, timeout=60,
                           cwd=self.tmp, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def flags(self):
        return {p: (self.stack / ("hook_%s.flag" % p)).exists() for p in ("before_run", "after_run")}

    def test_add_rm_reset(self):
        self.agent("ls")
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})   # reading never sets them
        self.agent("add", "--event", "before_run", "--condition", "act", "-n", "hold", "h/guard")
        self.assertEqual(self.flags(), {"before_run": True, "after_run": True})     # the definition's after_run hook counts too
        self.assertEqual(json.loads((self.stack / "hooks.json").read_text())["hooks"]["hold"]["condition"], "act")
        self.agent("rm", "gate")                                                    # the definition's one: set to null
        self.assertEqual(self.flags(), {"before_run": True, "after_run": False})
        self.agent("rm", "hold")
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})
        self.agent("add", "--event", "before_run", "-n", "again", "h/guard")
        self.assertEqual(self.flags(), {"before_run": True, "after_run": False})
        self.agent("reset", "-y")                                                   # back to the definition's list
        self.assertEqual(self.flags(), {"before_run": False, "after_run": True})

    def test_other_events_leave_no_flag(self):
        (self.defn / "hooks.json").write_text(json.dumps({"hooks": {}}))
        self.agent("add", "--event", "after_tool", "-n", "seen", "h/guard")
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})
        self.assertEqual(sorted(p.name for p in self.stack.iterdir()), ["hooks.json"])


if __name__ == "__main__":
    unittest.main()
