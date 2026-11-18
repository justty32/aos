"""Test that aos-agent ctl stop leaves an eca screen to the definition's after_stop hook (C′ B), while ctl rm and ctl set-def still close it themselves, on a real aos-daemon."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from env_helper import until  # noqa: E402  同夾的共用零件


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / "bin" / "aos-agent"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
ENV["PATH"] = str(PROTO / "bin") + ":" + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


class StopLinger(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="stop-linger-")))
        self.d = self.tmp / "stack"
        self.d.mkdir()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        self.closed = self.tmp / "closed.log"
        (self.tmp / "daemon.json").write_text('{"interval_ms": 20, "procs": {}}\n')
        self.old, self.new = self.definition("old"), self.definition("new")
        self.err = open(self.tmp / "daemon.err", "w")
        self.p = subprocess.Popen(["aos-daemon", str(self.tmp / "daemon.json")], cwd=self.tmp, env=dict(ENV, AOS_STACK=str(self.d)),
                                  stdout=subprocess.DEVNULL, stderr=self.err)
        until(lambda: (self.d / "state.json").exists())
        r = self.agent("ctl", "add", "-n", "ann", "-w", str(self.ws), "old")
        self.assertEqual(r.returncode, 0, r.stderr)
        until(lambda: self.row().get("phase") == "running")

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

    def definition(self, name):
        """A body that leaves when stop writes ctl.json, with a screen entry that logs "close <name>" (or refuses when the
        file busy exists, as an answering screen does)."""
        d = self.tmp / name
        (d / "screen").mkdir(parents=True)
        (d / "interfaces.json").write_text('{"aos-agent": {"screen": "screen"}}\n')
        (d / "screen" / "interfaces.json").write_text('{"aos-agent/screen": {}}\n')
        busy = self.tmp / "busy"
        for entry, text in ((d / "_entry", '#!/bin/sh\nwhile [ ! -e "$AOS_STACK/ctl.json" ]; do sleep 0.05; done\nrm -f "$AOS_STACK/ctl.json"\n'),
                            (d / "screen" / "_entry", '#!/bin/sh\nif [ -e %s ]; then echo "aos-eca-screen: error: SessionBad it is answering" >&2; exit 1; fi\n'
                                                      'echo "$1 %s" >> %s\n' % (busy, name, self.closed))):
            entry.write_text(text)
            entry.chmod(0o755)
        return d

    def closes(self):
        return self.closed.read_text().splitlines() if self.closed.exists() else []

    def row(self, n="ann"):
        try:
            return json.loads((self.d / "procs_state.json").read_text())["procs"].get(n) or {}
        except (OSError, ValueError):
            return {}

    def agent(self, *args):
        return subprocess.run([sys.executable, str(BIN), "-d", str(self.d), *args], capture_output=True, text=True,
                              env=ENV, cwd=self.tmp, timeout=90, stdin=subprocess.DEVNULL)

    def test_stop_leaves_the_screen_and_rm_closes_it(self):
        r = self.agent("ctl", "stop", "ann")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.row()["phase"], "stopped")
        self.assertEqual(self.closes(), [])                    # the after_stop hook of an eca closes it later, not ctl stop
        r = self.agent("ctl", "rm", "ann")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.closes(), ["close old"])

    def test_stop_help_says_who_closes_the_screen(self):
        r = self.agent("ctl", "stop", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("It does not close its screen: an eca closes it from its after_stop hook screen_linger_stop", r.stdout)

    def test_set_def_closes_the_screen_itself(self):
        r = self.agent("ctl", "set-def", "ann", "new")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.closes(), ["close old"])         # once, before the stop
        self.assertEqual(os.path.normpath(self.d / self.row()["def"]), str(self.new))

    def test_set_def_with_an_answering_screen_changes_nothing(self):
        (self.tmp / "busy").write_text("")
        pid = self.row()["pid"]
        r = self.agent("ctl", "set-def", "ann", "new")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("SessionBad", r.stderr)
        row = self.row()
        self.assertEqual((row["phase"], row["pid"], os.path.normpath(self.d / row["def"])), ("running", pid, str(self.old)))


if __name__ == "__main__":
    unittest.main()
