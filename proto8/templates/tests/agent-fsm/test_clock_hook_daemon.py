"""Acceptance on a real root daemon (no brain needed): after_start / after_stop on start, stop, sleep, wake, kill -9 + auto_restart, rm; clock_due with the root clock; history stays empty."""
# 11-11 clock-hook：範本 loop.json 的 on_start／on_stop（aos-loop）→ lib/agent/hook_fire → hooks.json 的 after_start／after_stop；
# 每格開頭 hooks.clock_tick → clock_due。用這份 clone 的 impls／cmd（PATH 最前）、py／lib（PYTHONPATH），不碰 ~/.local/bin 指的那份。
# 跑法：python3 test_clock_hook_daemon.py [-v]；KEEP=1 留下試驗資料夾。
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

PROTO = Path(__file__).resolve().parents[3]
LOGGER = """#!%s
# test hook: append the event JSON to a log
import json, sys
with open(%r, "a") as f:
    f.write(json.dumps(json.load(sys.stdin)) + "\\n")
"""


class Daemon(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-clockhook-"))
        if not os.environ.get("KEEP"):
            self.addCleanup(shutil.rmtree, self.root, True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        bins = [str(p) for p in sorted(PROTO.glob("impls/*/bin"))] + [str(p) for p in sorted(PROTO.glob("cmd/*/bin"))]
        self.env = dict(env, AOS_HOME=str(PROTO), PATH=os.pathsep.join(bins + [env["PATH"]]),
                        PYTHONPATH=os.pathsep.join([str(PROTO / "py"), str(PROTO / "lib")]), PYTHONDONTWRITEBYTECODE="1")
        self.log = self.root / "events.jsonl"
        shutil.copytree(PROTO / "templates" / "daemon-root", self.root / "defs")
        ann = self.root / "defs" / "ann"
        shutil.copytree(PROTO / "templates" / "agent-fsm", ann, ignore=shutil.ignore_patterns("__pycache__"))
        hook = ann / "log_hook"
        hook.write_text(LOGGER % (sys.executable, str(self.log)))
        hook.chmod(0o755)
        doc = json.loads((ann / "hooks.json").read_text())
        doc["hooks"].update({"up": {"event": "after_start", "handler": "log_hook", "on_error": "continue", "timeout_ms": 5000},
                             "down": {"event": "after_stop", "handler": "log_hook", "on_error": "continue", "timeout_ms": 5000},
                             "tick": {"event": "clock_due", "every_cycles": 2, "handler": "log_hook", "on_error": "continue",
                                      "timeout_ms": 5000}})
        (ann / "hooks.json").write_text(json.dumps(doc))
        self.err = open(self.root / "root.err", "w")
        self.addCleanup(self.err.close)
        self.daemon = subprocess.Popen(["aos-exec", "--stack", "stacks/root", "defs"], cwd=self.root, env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=self.err,
                                       start_new_session=True)
        self.addCleanup(self.close)
        self.until(lambda: (self.root / "stacks" / "root" / "clock").exists(), 20)

    def close(self):
        if self.daemon.poll() is None:
            subprocess.run(["aos-daemon-ctl", "-d", "stacks/root", "shutdown"], cwd=self.root, env=self.env,
                           capture_output=True, timeout=60)
            try:
                self.daemon.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.daemon.pid, signal.SIGKILL)

    def until(self, fn, secs=20):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            got = fn()
            if got:
                return got
            time.sleep(.1)
        raise AssertionError("timed out; events: %s; root.err: %s" % (self.events(), (self.root / "root.err").read_text()[-2000:]))

    def events(self, kind=None):
        rows = [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []
        return [r for r in rows if kind is None or r["event"] == kind]

    def ctl(self, *args):
        r = subprocess.run(["aos-agent", "-d", "stacks/root", "ctl", *args], cwd=self.root, env=self.env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def starts_stops(self):
        return [(e["event"], e.get("code"), e.get("signal")) for e in self.events() if e["event"] != "clock_due"]

    def row(self):
        return json.loads((self.root / "stacks" / "root" / "procs_state.json").read_text())["procs"]["ann"]

    def test_lifecycle(self):
        self.ctl("add", "--auto-restart", "-w", ".", "defs/ann")
        stack = self.root / "stacks" / "root" / "procs" / "ann"
        self.until(lambda: self.events("after_start"))
        ticks = self.until(lambda: len(self.events("clock_due")) >= 2 and self.events("clock_due"))
        self.assertEqual(ticks[0]["clock"], str((self.root / "stacks" / "root" / "clock").resolve()))
        self.assertGreaterEqual(ticks[1]["cycle"] - ticks[1]["last_cycle"], 2)
        self.assertEqual(ticks[0]["stack"].rstrip("/"), str(stack.resolve()))
        self.assertFalse((stack / "history.jsonl").exists() and (stack / "history.jsonl").read_text().strip())
        steps = [("stop", ("after_stop", 0, None)), ("start", ("after_start", None, None)),
                 ("sleep", ("after_stop", 143, 15)), ("wake", ("after_start", None, None))]
        for cmd, want in steps:
            n = len(self.starts_stops())
            self.ctl(cmd, "ann")
            self.until(lambda: len(self.starts_stops()) > n)
            self.assertEqual(self.starts_stops()[n], want, cmd)
        n = len(self.starts_stops())
        os.kill(self.until(lambda: self.row().get("pid")), signal.SIGKILL)     # kill -9：不跑 after_stop；auto_restart 重起＝after_start
        self.until(lambda: len(self.starts_stops()) > n, 40)
        self.assertEqual(self.starts_stops()[n:], [("after_start", None, None)])
        n = len(self.starts_stops())
        self.ctl("rm", "ann")
        self.until(lambda: len(self.starts_stops()) > n)
        self.assertEqual(self.starts_stops()[n][0], "after_stop")
        history = stack / "history.jsonl"
        self.assertFalse(history.exists() and history.read_text().strip(), "history got something")


if __name__ == "__main__":
    unittest.main()
