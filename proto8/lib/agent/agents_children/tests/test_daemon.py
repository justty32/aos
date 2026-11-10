"""Test agents_children and agents_ctl on a real aos-daemon: tools/llm changes land on the child (not the parent), and a child removed with agents_ctl is forgotten and frees the quota."""
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

sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[1] / "_entry"
AGENT = TOOL.parents[1]
CTL_TOOL = AGENT / "agents_ctl" / "_entry"
PROTO = AGENT.parents[1]
TEMPLATE = PROTO / "templates" / "agent-fsm"
DAEMON_BIN = PROTO / "impls" / "aos-daemon" / "bin" / "aos-daemon"


@unittest.skipUnless(DAEMON_BIN.exists() and CTL_TOOL.exists(), "needs a built aos-daemon (proto8/impls) and agents_ctl")
class RealDaemon(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agents-children-real-"))
        self.ws = self.tmp / "ws"
        self.dstack = self.ws / ".stack"
        self.dstack.mkdir(parents=True)
        (self.tmp / "daemon.json").write_text('{"interval_ms": 200}')
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(p) for p in sorted((PROTO / "impls").glob("*/bin"))] + [str(p) for p in sorted((PROTO / "cmd").glob("*/bin"))]
        env.update(PATH=os.pathsep.join(bins + [env["PATH"]]), AOS_HOME=str(PROTO), PYTHONDONTWRITEBYTECODE="1")
        self.log = open(self.tmp / "d.log", "w")
        self.daemon = subprocess.Popen(["aos-daemon", "daemon.json"], cwd=self.tmp, env=dict(env, AOS_STACK=str(self.dstack)),
                                       stdout=self.log, stderr=self.log, start_new_session=True)
        self.addCleanup(self.stop_daemon)
        self.env = dict(env, AOS_DAEMON=str(self.dstack), AOS_WS=str(self.ws))
        deadline = time.monotonic() + 10
        while True:
            r = self.agent("ctl", "add", "--name", "mom", str(TEMPLATE), check=False)
            if r.returncode == 0 or time.monotonic() > deadline:
                break
            time.sleep(0.2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.mom = r.stdout.strip().splitlines()[-1]
        self.env["AOS_STACK"] = os.path.join(self.mom, "tools", TOOL.parent.name)

    def stop_daemon(self):
        try:
            os.killpg(self.daemon.pid, signal.SIGTERM)
            self.daemon.wait(15)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(self.daemon.pid, signal.SIGKILL)
            except OSError:
                pass
            self.daemon.wait()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, *argv, check=True):
        r = subprocess.run(["aos-agent"] + list(argv), cwd=self.ws, env=self.env, capture_output=True, text=True, timeout=60)
        if check:
            self.assertEqual(r.returncode, 0, (argv, r.stderr))
        return r

    def tool(self, path, args):
        return subprocess.run([str(path)], input=json.dumps(args), cwd=self.ws, env=self.env, capture_output=True, text=True, timeout=120)

    def ok(self, path, args):
        r = self.tool(path, args)
        self.assertEqual(r.returncode, 0, (args, r.stdout, r.stderr))
        return r.stdout

    def test_children_on_a_real_daemon(self):
        self.ok(TOOL, {"op": "add", "def": str(TEMPLATE), "name": "kid", "ws": "kid"})
        self.assertEqual([c["name"] for c in json.loads(self.ok(TOOL, {"op": "ls", "long": True}))["children"]], ["kid"])
        short = self.ok(TOOL, {"op": "ls"}).splitlines()
        self.assertEqual((len(short), short[0].split("\t")[0], short[-1]), (2, "kid", "children 1/4"))
        self.assertLess(len(short[0]), 200)
        out = self.ok(TOOL, {"op": "tools", "name": "kid", "args": {"op": "add", "path": str(PROTO / "lib" / "base" / "math")}})
        self.assertIn("kid's next turn", out)
        kid_tools = [t["name"] for t in json.loads(self.agent("tools", "--target", "kid", "ls", "--json").stdout)]
        mom_tools = [t["name"] for t in json.loads(self.agent("tools", "--target", "mom", "ls", "--json").stdout)]
        self.assertIn("math", kid_tools)
        self.assertNotIn("math", mom_tools)
        self.ok(TOOL, {"op": "llm", "name": "kid", "args": {"op": "set", "settings": {"model": "fake"}}})
        self.assertIn("model=fake", self.agent("llm", "--target", "kid", "ls").stdout)
        self.assertNotIn("model=fake", self.agent("llm", "--target", "mom", "ls", check=False).stdout)
        self.assertIn("messages", self.ok(TOOL, {"op": "history", "name": "kid", "args": {"op": "ls"}}))
        self.ok(TOOL, {"op": "hook", "name": "kid", "args": {"op": "ls"}})
        r = self.tool(TOOL, {"op": "tools", "name": "mom", "args": {"op": "ls"}})
        self.assertIn("error: ChildUnknown mom", r.stdout)
        # someone removes kid with agents_ctl: agents_children forgets it and the slot is free again
        self.ok(CTL_TOOL, {"op": "rm", "name": "kid"})
        self.assertNotIn('"kid"', self.ok(CTL_TOOL, {"op": "ls", "json": True}))
        self.assertNotIn("kid\t", self.ok(CTL_TOOL, {"op": "ls"}))
        self.assertEqual(self.ok(TOOL, {"op": "ls"}), "children 0/4\n")
        self.assertIn("error: ChildUnknown kid", self.tool(TOOL, {"op": "state", "name": "kid"}).stdout)
        self.assertIn("children 1/4", self.ok(TOOL, {"op": "add", "def": str(TEMPLATE), "name": "kid2"}))
        self.ok(TOOL, {"op": "rm", "name": "kid2", "purge": True})


if __name__ == "__main__":
    unittest.main()
