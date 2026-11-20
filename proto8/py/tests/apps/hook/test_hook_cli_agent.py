"""Test aos-hook --agent DEF_DIR through bin/aos-hook: the definition's hook_points, its hooks file with the stack copy on top, the agent's on_clock checks, after_start clearing the on_clock state, and the mistakes (real aos-exec; no daemon)."""
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


class HookCliAgent(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-agent-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.defn, self.stack = self.d / "def", self.d / "stack"
        self.defn.mkdir()
        self.stack.mkdir()
        self.interfaces({"hooks": "hooks.json", "hook_points": [{"provider": "aos-loop"}, {"provider": "agent-fsm"}]})
        self.hooks = {}
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", AOS_HOME=str(PROTO))

    def interfaces(self, decl):
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": decl}))

    def handler(self, name, body, event, **entry):
        p = self.defn / ("h_" + name)
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)
        self.hooks[name] = dict({"event": event, "handler": p.name}, **entry)
        (self.defn / "hooks.json").write_text(json.dumps({"hooks": self.hooks}))

    def run_hook(self, *args, env=None):
        return subprocess.run([sys.executable, str(HOOK)] + [str(a) for a in args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env=dict(self.env, **(env or {})), cwd=self.d, timeout=60)

    def assertError(self, r, code, part=""):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-hook: error: %s " % code), r.stderr)
        self.assertIn(part, r.stderr)

    def test_fire_after_stop_with_both_layers(self):
        self.handler("a_seen", "cat > \"$AOS_STACK/seen.json\"", "after_stop")
        self.handler("b_off", "exit 3", "after_stop")
        (self.stack / "hooks.json").write_text(json.dumps({"hooks": {"b_off": None}}))   # the stack copy turns it off
        r = self.run_hook("fire", "--agent", self.defn, "--stack", self.stack, "after_stop",
                          env={"AOS_LOOP_CODE": "3", "AOS_LOOP_CAUSE": " stop "})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(json.loads(r.stdout)["data"], {"code": 3, "signal": None, "cause": "stop"})
        seen = json.loads((self.stack / "hooks" / "a_seen" / "seen.json").read_text())
        self.assertEqual((seen["event"], seen["code"], seen["cause"]), ("after_stop", 3, "stop"))

    def test_block_and_declared_types(self):
        self.handler("deny", "echo no; exit 10", "before_tool", condition="rm")
        r = self.run_hook("fire", "--agent", self.defn, "--field", "name=rm", "before_tool", env={"AOS_STACK": str(self.stack)})
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertEqual(json.loads(r.stdout)["hook"], "deny")
        self.handler("deny", "echo '{\"content\": \"\"}'", "before_queue")
        r = self.run_hook("fire", "--agent", self.defn, "--stack", self.stack, "before_queue")
        self.assertError(r, "HookFailed", "content in stdout must be a non-empty string")

    def test_after_start_clears_the_on_clock_state(self):
        state = self.stack / "hooks" / "tick" / "on_clock.json"
        state.parent.mkdir(parents=True)
        state.write_text('{"cycle": 5}\n')
        r = self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "after_start")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertFalse(state.exists())
        state.write_text('{"cycle": 5}\n')
        self.run_hook("fire", "-q", "--agent", self.defn, "--stack", self.stack, "after_stop")
        self.assertTrue(state.exists())                        # only after_start clears it

    def test_on_clock_rules(self):
        self.handler("tick", "exit 0", "on_clock")
        self.assertError(self.run_hook("check", "--agent", self.defn), "HooksBad", "needs exactly one of every_cycles, every_ms")
        self.handler("tick", "exit 0", "on_clock", every_ms=0)
        self.assertError(self.run_hook("check", "--agent", self.defn), "HooksBad", "every_ms must be a positive integer")
        self.handler("tick", "exit 0", "after_queue", every_ms=5)
        self.assertError(self.run_hook("check", "--agent", self.defn), "HooksBad", "every_ms is only for event on_clock")
        self.handler("tick", "exit 0", "on_clock", every_ms=5)
        r = self.run_hook("check", "--agent", self.defn)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout, "ok: 11 points from 2 declarations, 1 hooks from 1 lists\n")
        r = self.run_hook("check", "--agent", self.defn, "--stack", self.stack)
        self.assertIn("from 2 lists", r.stdout)

    def test_points_and_mistakes(self):
        r = self.run_hook("points", "-j", "--agent", self.defn)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("before_run", json.loads(r.stdout))
        self.assertError(self.run_hook("fire", "--agent", self.defn, "--list", self.d / "x.json", "after_start"),
                         "ArgumentsBad", "not both")
        self.assertError(self.run_hook("check", "--agent", self.d / "nope"), "ArgumentsBad", "definition folder")
        self.assertError(self.run_hook("fire", "--agent", self.defn, "after_start"), "StackMissing")
        self.interfaces({"hooks": "hooks.json"})               # no hook_points: no points
        self.assertError(self.run_hook("fire", "--agent", self.defn, "--stack", self.stack, "after_start"),
                         "EventUnknown", "the hook_points of %s/interfaces.json (points: none)" % self.defn)
        self.interfaces({"hooks": "hooks.json", "hook_points": [{"provider": "nope"}]})
        self.assertError(self.run_hook("points", "--agent", self.defn), "PointsBad", "unknown hook point provider")


if __name__ == "__main__":
    unittest.main()
