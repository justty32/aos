"""Test aos-agent ctl rm keeps the stack by default and deletes it only with --purge (cli-sweep Q3), on a real aos-daemon."""
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
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = ":".join(str(p) for p in sorted((PROTO / "impls").glob("*/bin"))) + ":" + ":".join(
    str(p) for p in sorted((PROTO / "cmd").glob("*/bin"))) + ":" + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def until(cond, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("timed out")


class RmKeep(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rm-keep-"))
        self.d = self.tmp / "stack"
        self.d.mkdir()
        (self.tmp / "daemon.json").write_text('{"interval_ms": 20, "procs": {}}\n')
        body = self.tmp / "body.sh"
        body.write_text("#!/bin/sh\nexec sleep 60\n")
        body.chmod(0o755)
        self.err = open(self.tmp / "daemon.err", "w")
        self.p = subprocess.Popen(["aos-daemon", str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (self.d / "state.json").exists())
        for n in ("ann", "bob"):
            subprocess.run(["aos-daemon-ctl", "-d", str(self.d), "add", "-n", n, str(body)], env=ENV, check=True,
                           capture_output=True, cwd=self.tmp)
            until(lambda: self.row(n).get("phase") == "running")

    def tearDown(self):
        try:
            self.p.send_signal(signal.SIGTERM)
            self.p.wait(timeout=20)
        finally:
            self.err.close()
            subprocess.run(["pkill", "-f", str(self.tmp)], check=False)
            shutil.rmtree(self.tmp, ignore_errors=True)

    def row(self, n):
        try:
            return json.loads((self.d / "procs_state.json").read_text())["procs"].get(n) or {}
        except (OSError, ValueError):
            return {}

    def agent(self, *args):
        return subprocess.run([sys.executable, str(BIN), "-d", str(self.d), *args], capture_output=True, text=True,
                              env=ENV, cwd=self.tmp, timeout=60, stdin=subprocess.DEVNULL)

    def test_default_keeps_stack(self):
        r = self.agent("ctl", "rm", "ann")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stack %s kept" % (self.d / "procs" / "ann"), r.stdout)
        self.assertEqual(self.row("ann"), {})
        self.assertTrue((self.d / "procs" / "ann").is_dir())

    def test_purge_deletes_stack(self):
        r = self.agent("ctl", "rm", "--purge", "bob")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("deleted stack", r.stdout)
        self.assertFalse((self.d / "procs" / "bob").exists())

    def test_rm_and_stop_when_workspace_is_gone(self):
        """11-13: a workspace that is gone must not block rm / stop (closing the screen only needs the stack)."""
        defn = self.tmp / "defn"
        (defn / "screen").mkdir(parents=True)
        (defn / "interfaces.json").write_text('{"aos-agent": {"screen": "screen"}}\n')
        (defn / "screen" / "interfaces.json").write_text('{"aos-agent/screen": {}}\n')
        closed = self.tmp / "closed.log"
        for entry, text in ((defn / "_entry", '#!/bin/sh\nwhile [ ! -e "$AOS_STACK/ctl.json" ]; do sleep 0.1; done\n'),   # leaves when stop writes ctl.json
                            (defn / "screen" / "_entry", '#!/bin/sh\necho "$1 $AOS_STACK" >> %s\necho "no screen (already closed)"\n' % closed)):
            entry.write_text(text)
            entry.chmod(0o755)
        for n in ("cat", "dan"):
            ws = self.tmp / ("ws-" + n)
            ws.mkdir()
            r = self.agent("ctl", "add", "-n", n, "-w", str(ws), str(defn))
            self.assertEqual(r.returncode, 0, r.stderr)
            until(lambda: self.row(n).get("phase") == "running")
            ws.rmdir()
        r = self.agent("-t", "cat", "ctl", "stop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("aos-agent: warning: the workspace of cat is gone (%s); closing its screen from its stack instead" % (self.tmp / "ws-cat"), r.stderr)
        self.assertNotIn("WsMissing", r.stderr)
        self.assertEqual(self.row("cat").get("phase"), "stopped")
        r = self.agent("ctl", "rm", "dan")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("the workspace of dan is gone", r.stderr)
        self.assertIn("removed dan; stack %s kept" % (self.d / "procs" / "dan"), r.stdout)
        self.assertEqual(self.row("dan"), {})
        self.assertTrue((self.d / "procs" / "dan").is_dir())
        self.assertEqual([l.split()[0] for l in closed.read_text().splitlines()], ["close", "close"])   # the screen entry still ran
        r = self.agent("ctl", "rm", "cat")                      # stopped, workspace gone: still removable
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.row("cat"), {})

    def test_yes_needs_purge(self):
        r = self.agent("ctl", "rm", "-y", "ann")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)
        self.assertEqual(self.row("ann").get("phase"), "running")


if __name__ == "__main__":
    unittest.main()
