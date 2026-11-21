"""Test aos-hook fire --stop-on-nonzero and -q through bin/aos-hook: stop at the first non-zero handler and exit with its code (10 quietly, others with a HookFailed line, a timeout with 1), without the flag always 0 (real aos-exec; no daemon)."""
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


class HookCliFlags(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aos-hook-flags-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.stack = self.d / "stack"
        self.list = self.d / "hookeds.json"
        self.hooks = {}
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", AOS_HOME=str(PROTO))

    def handler(self, name, body, **entry):
        """hook NAME runs `body` (sh) and leaves a mark STACK/ran_NAME."""
        p = self.d / ("h_" + name)
        p.write_text('#!/bin/sh\ntouch "$AOS_STACK/../../ran_%s"\n%s\n' % (name, body))
        p.chmod(0o755)
        self.hooks[name] = dict({"event": "before_run", "handler": p.name}, **entry)
        self.list.write_text(json.dumps(self.hooks))

    def ran(self):
        return sorted(p.name[4:] for p in self.stack.glob("ran_*"))

    def fire(self, *args):
        return subprocess.run([sys.executable, str(HOOK), "fire", "--list", str(self.list), "--stack", str(self.stack)]
                              + [str(a) for a in args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              env=self.env, cwd=self.d, timeout=60)

    def test_without_the_flag_always_0(self):
        self.handler("a", "exit 10")
        self.handler("b", "exit 3")
        self.handler("c", "echo hi")
        r = self.fire("before_run")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual([(h["hook"], h["code"]) for h in json.loads(r.stdout)["hooks"]], [("a", 10), ("b", 3), ("c", 0)])
        self.assertEqual(self.ran(), ["a", "b", "c"])

    def test_stop_on_10_exits_10_quietly(self):
        self.handler("a", "echo ok")
        self.handler("b", "echo skip; exit 10")
        self.handler("c", "true")
        r = self.fire("--stop-on-nonzero", "before_run")
        self.assertEqual((r.returncode, r.stderr), (10, ""))
        self.assertEqual([(h["hook"], h["code"], h["stdout"]) for h in json.loads(r.stdout)["hooks"]],
                         [("a", 0, "ok\n"), ("b", 10, "skip\n")])
        self.assertEqual(self.ran(), ["a", "b"])                           # c never ran

    def test_stop_on_other_code_exits_with_it(self):
        self.handler("a", "exit 3")
        self.handler("b", "true")
        r = self.fire("--stop-on-nonzero", "before_run")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(r.stderr, "aos-hook: error: HookFailed hook a (event before_run) exited 3\n")
        self.assertEqual(len(json.loads(r.stdout)["hooks"]), 1)
        self.assertEqual(self.ran(), ["a"])

    def test_stop_on_timeout_exits_1(self):
        self.handler("a", "sleep 5", timeout_ms=200)
        self.handler("b", "true")
        r = self.fire("--stop-on-nonzero", "-q", "before_run")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("aos-hook: warning: hook a (event before_run): did not finish in 200 ms", r.stderr)
        self.assertIn("aos-hook: error: HookFailed hook a (event before_run) did not finish in 200 ms", r.stderr)
        self.assertEqual(self.ran(), ["a"])

    def test_all_zero_and_nobody(self):
        self.handler("a", "true")
        self.handler("b", "true")
        r = self.fire("--stop-on-nonzero", "-q", "before_run")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.ran(), ["a", "b"])
        r = self.fire("--stop-on-nonzero", "after_run")
        self.assertEqual((r.returncode, json.loads(r.stdout)), (0, {"event": "after_run", "hooks": []}))

    def test_quiet_keeps_the_exit_code(self):
        self.handler("a", "echo loud; exit 10")
        r = self.fire("-q", "--stop-on-nonzero", "before_run")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (10, "", ""))
        r = self.fire("--quiet", "before_run")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
