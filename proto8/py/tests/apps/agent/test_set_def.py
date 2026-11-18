"""Test aos-agent ctl set-def on a real aos-daemon: stop, detach and attach again on the same stack; workspace and auto_restart stay, the table shows the new definition at once."""
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
from env_helper import until  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-agent"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = str(PROTO / "bin") + ":" + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


class SetDef(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="set-def-")))
        self.d = self.tmp / "stack"
        self.d.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.tmp / "daemon.json").write_text('{"interval_ms": 20, "procs": {}}\n')
        self.old, self.new = self.definition("old"), self.definition("new")
        self.err = open(self.tmp / "daemon.err", "w")
        self.p = subprocess.Popen(["aos-daemon", str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (self.d / "state.json").exists())
        r = self.agent("ctl", "add", "-n", "ann", "--auto-restart", "-w", str(self.ws), "old")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.stack = self.d / "procs" / "ann"
        until(lambda: self.ran() == ["old"])

    def tearDown(self):
        try:
            self.p.send_signal(signal.SIGTERM)                 # only the daemon this test started
            self.p.wait(timeout=20)
        finally:
            self.err.close()
            root = str(self.tmp)
            for pid in (int(n) for n in os.listdir("/proc") if n.isdigit()):   # leftovers: only by cwd inside this test's folder
                try:
                    cwd = os.readlink("/proc/%d/cwd" % pid)
                except OSError:
                    continue
                if pid != os.getpid() and (cwd == root or cwd.startswith(root + os.sep)):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
            shutil.rmtree(self.tmp, ignore_errors=True)

    def definition(self, name, tools=False):
        """A body that writes its name into $AOS_STACK/ran.txt and leaves (taking ctl.json with it) when stop writes ctl.json."""
        d = self.tmp / name
        d.mkdir()
        (d / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json"} if tools else {}}))
        if tools:
            (d / "tools.json").write_text('{"tools": {}}\n')
        (d / "_entry").write_text('#!/bin/sh\necho %s >> "$AOS_STACK/ran.txt"\n'
                                  'while [ ! -e "$AOS_STACK/ctl.json" ]; do sleep 0.05; done\nrm -f "$AOS_STACK/ctl.json"\n' % name)
        (d / "_entry").chmod(0o755)
        return d

    def ran(self):
        p = self.d / "procs" / "ann" / "ran.txt"
        return p.read_text().split() if p.exists() else []

    def row(self, n="ann"):
        try:
            return json.loads((self.d / "procs_state.json").read_text())["procs"].get(n) or {}
        except (OSError, ValueError):
            return {}

    def agent(self, *args, **env):
        return subprocess.run([sys.executable, str(BIN), "-d", str(self.d), *args], capture_output=True, text=True,
                              env=dict(ENV, **env), cwd=self.tmp, timeout=90, stdin=subprocess.DEVNULL)

    def test_set_def_on_a_running_agent_restarts_it_with_the_new_one(self):
        """fx-1: stop, detach, attach again on the same stack: a new pid runs the new definition, history stays."""
        (self.stack / "history.jsonl").write_text('{"role": "user", "content": "kept"}\n')
        before = self.row()
        r = self.agent("ctl", "set-def", "ann", "new")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "definition of ann is now %s; it runs it now (stack %s kept)\n" % (self.new, self.stack))
        until(lambda: self.ran() == ["old", "new"])
        row = until(lambda: self.row().get("phase") == "running" and self.row())
        self.assertNotEqual(row.get("pid"), before["pid"])
        self.assertEqual(os.path.normpath(self.d / row["def"]), str(self.new))
        for key in ("stack", "ws", "auto_restart", "as_written"):             # everything else as it was
            self.assertEqual(row.get(key), before.get(key), key)
        self.assertEqual(before["as_written"], {"ws": str(self.ws)})
        self.assertEqual((self.stack / "history.jsonl").read_text(), '{"role": "user", "content": "kept"}\n')

    def test_set_def_keeps_stack_and_queue(self):
        """Stopped: the row stays stopped, the next start runs the new definition on the same stack."""
        self.assertEqual(self.agent("ctl", "stop", "ann").returncode, 0)
        (self.stack / "queue").mkdir(exist_ok=True)
        (self.stack / "queue" / "waiting.json").write_text("{}\n")
        r = self.agent("ctl", "set-def", "ann", str(self.new))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "definition of ann is now %s; it stays stopped; ctl start runs it (stack %s kept)\n" % (self.new, self.stack))
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.row()["phase"], "stopped")
        self.assertEqual(os.path.normpath(self.d / self.row()["def"]), str(self.new))   # the table shows it at once
        self.assertEqual(self.ran(), ["old"])
        self.assertEqual(self.agent("ctl", "start", "ann").returncode, 0)
        until(lambda: self.ran() == ["old", "new"])
        row = self.row()
        self.assertEqual(row["as_written"], {"ws": str(self.ws), "def": str(self.new), "exec": str(self.new)})   # typed absolute this time
        self.assertTrue((self.stack / "queue" / "waiting.json").exists())

    def restart_daemon(self):
        r = subprocess.run(["aos-daemon-ctl", "-d", str(self.d), "shutdown"], env=ENV, capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.p.wait(timeout=20)
        self.p = subprocess.Popen(["aos-daemon", str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)

    def test_set_def_survives_a_daemon_restart(self):
        """The row carries the new definition, so a daemon restart (running rows sleep, then wake) keeps it."""
        self.assertEqual(self.agent("ctl", "set-def", "ann", "new").returncode, 0)
        until(lambda: self.ran() == ["old", "new"])
        self.restart_daemon()
        until(lambda: len(self.ran()) == 3, timeout=20)
        self.assertEqual(self.ran(), ["old", "new", "new"])

    def test_set_def_on_a_stopped_agent_survives_a_daemon_restart(self):
        """The same for a stopped agent: set-def, daemon restart, ctl start runs the new definition."""
        self.assertEqual(self.agent("ctl", "stop", "ann").returncode, 0)
        self.assertEqual(self.agent("ctl", "set-def", "ann", "new").returncode, 0)
        self.restart_daemon()
        until(lambda: self.row().get("phase") == "stopped")
        self.assertEqual(self.agent("ctl", "start", "ann").returncode, 0)
        until(lambda: len(self.ran()) == 2)
        self.assertEqual(self.ran(), ["old", "new"])

    def test_set_def_on_a_sleeping_agent_keeps_it_asleep(self):
        """Attached again together with procs_slept: on the table asleep, not started; ctl wake runs the new definition."""
        self.assertEqual(self.agent("ctl", "sleep", "ann").returncode, 0)
        r = self.agent("ctl", "set-def", "ann", "new")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("it stays asleep", r.stdout)
        self.assertEqual(self.row()["phase"], "sleeping")
        time.sleep(0.5)
        self.assertEqual(self.ran(), ["old"])
        self.assertEqual(self.agent("ctl", "wake", "ann").returncode, 0)
        until(lambda: self.ran() == ["old", "new"])

    def test_a_stop_that_times_out_changes_nothing(self):
        stubborn = self.tmp / "stubborn"
        stubborn.mkdir()
        (stubborn / "interfaces.json").write_text('{"aos-agent": {}}\n')
        (stubborn / "_entry").write_text("#!/bin/sh\nexec sleep 60\n")            # never leaves on stop
        (stubborn / "_entry").chmod(0o755)
        self.assertEqual(self.agent("ctl", "add", "-n", "bob", "-w", str(self.ws), "stubborn").returncode, 0)
        until(lambda: self.row("bob").get("phase") == "running")
        r = self.agent("ctl", "set-def", "--timeout-s", "1", "bob", "new")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("aos-agent: error: WaitFailed ", r.stderr)
        self.assertEqual(os.path.normpath(self.d / self.row("bob")["def"]), str(stubborn))   # still on the table, old definition

    def test_set_def_warns_about_tools_override_of_old_def(self):
        with_tools = self.definition("tooled", tools=True)
        r = self.agent("ctl", "set-def", "ann", "tooled")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("tools.json", r.stderr)               # no own copy yet
        (self.stack / "tools.json").write_text(json.dumps({"$override": str(with_tools / "tools.json"), "tools": {}}))
        r = self.agent("ctl", "set-def", "ann", "new")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning: ann has its own tools.json in its stack, which still overrides the old definition's (%s)" % with_tools, r.stderr)
        self.assertTrue((self.stack / "tools.json").exists())  # warned, not rewritten

    def test_errors_change_nothing(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        for args, code in ((("ghost", "new"), "InstanceMissing"), (("ann", "plain"), "InterfaceMissing"),
                           (("ann", "nowhere"), "PathMissing"), (("ann",), "ArgumentsBad")):
            with self.subTest(args=args):
                r = self.agent("ctl", "set-def", *args)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("aos-agent: error: %s " % code, r.stderr)
        r = self.agent("ctl", "set-def", "ann", "new", AOS_STACK=str(self.stack))   # an agent on itself
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad set-def cannot be used by ann on itself", r.stderr)
        r = self.agent("ctl", "set-def", "--restart", "ann", "new")         # gone: every set-def restarts now
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-agent: error: FlagUnknown ", r.stderr)
        r = self.agent("ctl", "add", "-n", "eve", "--envs", "K=V", "-w", str(self.ws), "old")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.agent("ctl", "set-def", "eve", "new")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad eve was attached with --envs", r.stderr)
        self.agent("ctl", "stop", "ann")
        self.agent("ctl", "start", "ann")
        until(lambda: self.ran() == ["old", "old"])            # none of the refused calls changed the definition


if __name__ == "__main__":
    unittest.main()
