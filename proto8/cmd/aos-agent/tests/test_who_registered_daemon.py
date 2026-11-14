"""ctl who reads parent / notify_box of a row attached with --envs on a real isolated daemon (ok-devt-1114 05 定稿 1.3, ok-limits 11-14).

The daemon records such a row's launch as a pointer into the cell (exec.json#/exec or loop.json#/_entry); the envs live in that file.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / "cmd" / "aos-agent" / "bin" / "aos-agent"
ENV = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
ENV["PATH"] = os.pathsep.join(str(path) for path in sorted((PROTO / "impls").glob("*/bin"))) + os.pathsep + os.pathsep.join(
    str(path) for path in sorted((PROTO / "cmd").glob("*/bin"))) + os.pathsep + ENV["PATH"]
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def until(condition, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = condition()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out")


@unittest.skipUnless(shutil.which("aos-daemon", path=ENV["PATH"]) and shutil.which("aos-post", path=ENV["PATH"]),
                     "aos-daemon and aos-post are required")
class WhoRegisteredDaemon(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="who-registered-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.daemon = self.root / "stack"
        self.daemon.mkdir()
        body = '#!/bin/sh\necho up > "$AOS_WS/up.txt"\nexec sleep 60\n'
        self.exec_def = self.root / "def-exec"
        self.exec_def.mkdir()
        (self.exec_def / "interfaces.json").write_text('{"aos-agent": {}}\n')
        (self.exec_def / "_entry").write_text(body)
        (self.exec_def / "_entry").chmod(0o755)
        script = self.root / "body.sh"
        script.write_text(body)
        script.chmod(0o755)
        self.loop_def = self.root / "def-loop"
        self.loop_def.mkdir()
        (self.loop_def / "interfaces.json").write_text('{"aos-agent": {"entry": "body.json"}}\n')
        (self.loop_def / "body.json").write_text(json.dumps({"exec": str(script), "interval_ms": 100000}))
        config = self.root / "daemon.json"
        config.write_text('{"interval_ms": 20, "procs": {}}\n')
        self.err = open(self.root / "daemon.err", "w")
        self.addCleanup(self.err.close)
        self.process = subprocess.Popen(["aos-daemon", str(config)], cwd=self.root, env=dict(ENV, AOS_STACK=str(self.daemon)),
                                        stdout=subprocess.DEVNULL, stderr=self.err)
        self.addCleanup(self.stop_daemon)
        until(lambda: (self.daemon / "state.json").exists())

    def stop_daemon(self):
        if self.process.poll() is None:
            subprocess.run(["aos-daemon-ctl", "-d", str(self.daemon), "shutdown", "--timeout-s", "20"],
                           cwd=self.root, env=ENV, capture_output=True, text=True, timeout=25)
        self.process.wait(timeout=25)

    def ctl(self, *args, env=None):
        p = subprocess.run([sys.executable, str(BIN), "-d", str(self.daemon), "ctl", *args], cwd=self.root,
                           env=dict(ENV, **(env or {})), capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("secret-value-1114", p.stdout + p.stderr)
        return p.stdout

    def attach(self, name, definition, *envs):
        ws = self.root / ("ws-" + name)
        ws.mkdir()
        flags = [x for e in envs for x in ("--envs", e)]
        self.ctl("add", "-n", name, "-w", str(ws), *flags, str(definition))
        until(lambda: (ws / "up.txt").exists())
        return str(self.daemon / "procs" / name)

    def test_exec_and_loop_rows_with_envs(self):
        for name, definition in (("ex", self.exec_def), ("lp", self.loop_def)):
            with self.subTest(name=name):
                stack = self.attach(name, definition, "AOS_PARENT_STACK=/x/mom", "AOS_NOTIFY_BOX=/x/mom/mailbox",
                                    "FAKE_TOKEN=secret-value-1114")
                j = json.loads(self.ctl("who", "--json", "--stack", stack))      # 別隻在問：只靠表與小格
                self.assertEqual((j["name"], j["parent"], j["notify_box"]), (name, "/x/mom", "/x/mom/mailbox"))
                j = json.loads(self.ctl("state", "--target", name, "-j", "who"))["who"]
                self.assertEqual((j["parent"], j["notify_box"]), ("/x/mom", "/x/mom/mailbox"))

    def test_row_without_envs_is_null_unless_it_is_you(self):
        stack = self.attach("plain", self.exec_def)
        j = json.loads(self.ctl("who", "--json", "--stack", stack))
        self.assertEqual((j["parent"], j["notify_box"]), (None, None))
        j = json.loads(self.ctl("who", "--json", env={"AOS_STACK": stack, "AOS_NOTIFY_BOX": "/x/box"}))
        self.assertEqual((j["name"], j["notify_box"]), ("plain", "/x/box"))

    def test_explicit_empty_value_wins_over_own_environment(self):
        stack = self.attach("blank", self.exec_def, "AOS_NOTIFY_BOX=")
        j = json.loads(self.ctl("who", "--json", env={"AOS_STACK": stack, "AOS_NOTIFY_BOX": "/x/box"}))
        self.assertEqual((j["name"], j["notify_box"]), ("blank", None))


if __name__ == "__main__":
    unittest.main()
