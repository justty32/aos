"""Test the before_run / after_run flag files through bin/aos-hook: fire after_start and check with a stack set them from the lists (with --agent and with --points / --list, like the procs-kernel template), other events never touch them."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
HOOK = PROTO / "bin" / "aos-hook"
LOOP_POINTS = PROTO / "lib" / "aos" / "apps" / "hook" / "loop_points.json"


class HookCliFlags(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-flags-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.defn, self.stack = self.d / "def", self.d / "stack"
        self.defn.mkdir()
        self.stack.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {
            "hooks": "hooks.json", "hook_points": [{"provider": "aos-loop"}, {"provider": "agent-fsm"}]}}))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", AOS_HOME=str(PROTO))

    def write_hooks(self, path, hooks):
        path.write_text(json.dumps({"hooks": hooks}))

    def run_hook(self, *args, env=None):
        return subprocess.run([sys.executable, str(HOOK)] + [str(a) for a in args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env=dict(self.env, **(env or {})), cwd=self.d, timeout=60)

    def flags(self):
        return {p: (self.stack / ("hook_%s.flag" % p)).exists() for p in ("before_run", "after_run")}

    def test_agent_after_start_sets_them(self):
        self.write_hooks(self.defn / "hooks.json", {"b": {"event": "before_run", "handler": "/bin/true"}})
        self.write_hooks(self.stack / "hooks.json", {"a": {"event": "after_run", "handler": "/bin/true"}})
        r = self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "after_start")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.flags(), {"before_run": True, "after_run": True})
        self.write_hooks(self.stack / "hooks.json", {"b": None})            # hand edit: nothing follows until a start or a check
        self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "after_stop")
        self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "before_run")
        self.assertEqual(self.flags(), {"before_run": True, "after_run": True})
        r = self.run_hook("check", "--agent", self.defn, "--stack", self.stack)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.splitlines()[1], "flags: %s off, %s off" % (self.stack / "hook_before_run.flag", self.stack / "hook_after_run.flag"))
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})

    def test_check_without_a_stack_sets_nothing(self):
        self.write_hooks(self.defn / "hooks.json", {"b": {"event": "before_run", "handler": "/bin/true"}})
        r = self.run_hook("check", "--agent", self.defn)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(len(r.stdout.splitlines()), 1, r.stdout)
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})

    def test_points_and_list_like_the_kernel(self):
        hooks = self.d / "loop_hooks.json"
        args = ["--points", LOOP_POINTS, "--list", hooks, "--stack", self.stack]
        r = self.run_hook("fire", "-q", *args, "after_start")                # no list file = no hooks
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.flags(), {"before_run": False, "after_run": False})
        self.write_hooks(hooks, {"round": {"event": "before_run", "handler": "/bin/true"}})
        r = self.run_hook("fire", "-q", *args, "after_start")
        self.assertEqual(self.flags(), {"before_run": True, "after_run": False})
        (self.stack / "hook_after_run.flag").write_text("stale\n")
        r = self.run_hook("check", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.flags(), {"before_run": True, "after_run": False})

    def test_points_without_the_loop_ones(self):
        mine = self.d / "points.json"
        mine.write_text(json.dumps({"description": "x", "provider": "mine", "points": {
            "after_start": {"when": "never", "phase": "after", "fields": {}}}}))
        (self.stack / "hook_before_run.flag").write_text("stale\n")
        r = self.run_hook("fire", "-q", "--points", mine, "--stack", self.stack, "after_start")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue((self.stack / "hook_before_run.flag").exists())     # not declared here: left alone

    def test_cannot_write_the_flag(self):
        self.write_hooks(self.defn / "hooks.json", {"b": {"event": "before_run", "handler": "/bin/true"}})
        self.stack.chmod(0o500)
        self.addCleanup(self.stack.chmod, 0o700)
        r = self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "after_start")
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-hook: error: WriteFailed "), r.stderr)


if __name__ == "__main__":
    unittest.main()
