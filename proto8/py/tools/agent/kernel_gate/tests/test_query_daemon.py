# 驗證狀態查詢經掛 hold 的真站到暫存 daemon，直接回信與代回兩路都不留給 agent 判。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest


GATE = Path(__file__).resolve().parents[1]
PROTO8 = GATE.parents[3]
KERNEL = PROTO8 / "py" / "tools" / "aos" / "kernel" / "_entry"
AGENT = PROTO8 / "bin" / "aos-agent"
BINS = [str(PROTO8 / "bin")]


class QueryDaemonTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="gate-query-", dir=os.environ.get("KERNEL_TEST_TMP"))).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.stack = self.root / "daemon"
        self.station = self.root / "station"
        self.stack.mkdir()
        self.station.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=os.pathsep.join(BINS + [self.env["PATH"]]), PYTHONDONTWRITEBYTECODE="1")
        definition = self.root / "daemon.json"
        definition.write_text(json.dumps({"interval_ms": 20, "procs": {"fixture": {"exec": {"argv": ["/bin/false"]}}}}))
        self.log = open(self.root / "daemon.log", "w")
        self.addCleanup(self.log.close)
        self.daemon = subprocess.Popen([str(PROTO8 / "bin/aos-daemon"), str(definition)],
                                       cwd=self.root, env=dict(self.env, AOS_STACK=str(self.stack)),
                                       stdout=self.log, stderr=self.log)
        self.addCleanup(self.stop_daemon)
        deadline = time.monotonic() + 10
        while True:
            try:
                row = json.loads((self.stack / "procs_state.json").read_text())["procs"].get("fixture", {})
            except (OSError, ValueError):
                row = {}
            if row.get("phase") == "stopped" and (self.stack / "procs_requests" / "new").is_dir():
                break
            self.assertIsNone(self.daemon.poll(), "fixture daemon exited")
            self.assertLess(time.monotonic(), deadline, "fixture daemon did not start")
            time.sleep(0.02)

    def stop_daemon(self):
        if self.daemon.poll() is None:
            self.assertEqual(os.readlink("/proc/%d/cwd" % self.daemon.pid), str(self.root))
            result = subprocess.run(
                [str(PROTO8 / "bin/aos-daemon-ctl"), "-d", str(self.stack), "shutdown"],
                cwd=self.root, env=self.env, text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.daemon.wait(timeout=20)

    def test_ls_through_hold_reaches_daemon_with_direct_and_relay_replies(self):
        for relay in (False, True):
            with self.subTest(reply_via_me=relay):
                cfg = self.station / "kernel.json"
                cfg.write_text(json.dumps({
                    "next": str(self.stack / "procs_requests"), "reply_via_me": relay}))
                (self.station / "interfaces.json").write_text(json.dumps({"hookeds": "kernel_hookeds.json", "kernel": {}}))
                (self.station / "kernel_hookeds.json").write_text(json.dumps(
                    {"hold": {"event": "after_verdict", "condition": "pass", "handler": str(GATE / "hold")}}))
                station_env = dict(self.env, AOS_STACK=str(self.station))
                argv = [sys.executable, str(KERNEL), str(cfg)]
                first = subprocess.run(argv, cwd=self.root, env=station_env, text=True, capture_output=True, timeout=10)
                self.assertEqual(first.returncode, 0, first.stderr)
                stop = threading.Event()
                failures = []

                def rounds():
                    try:
                        while not stop.is_set():
                            result = subprocess.run(argv, cwd=self.root, env=station_env,
                                                    text=True, capture_output=True, timeout=10)
                            if result.returncode:
                                failures.append(result.stderr)
                                return
                            stop.wait(0.01)
                    except Exception as error:
                        failures.append(str(error))

                worker = threading.Thread(target=rounds)
                worker.start()
                started = time.monotonic()
                try:
                    result = subprocess.run([sys.executable, str(AGENT), "ctl", "ls", "--json"],
                                            cwd=self.root, env=dict(self.env, AOS_KERNEL=str(self.station / "requests")),
                                            text=True, capture_output=True, timeout=10)
                    elapsed = time.monotonic() - started
                finally:
                    stop.set()
                    worker.join(timeout=15)
                self.assertFalse(worker.is_alive(), "fixture station did not stop")
                self.assertEqual(failures, [])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLess(elapsed, 3, "state query did not finish within three seconds")
                rows = json.loads(result.stdout)
                self.assertEqual([row["name"] for row in rows], ["fixture"])
                self.assertEqual(rows[0]["phase"], "stopped")
                self.assertEqual(rows[0]["stack"].rstrip("/"), str(self.stack / "procs" / "fixture"))
                held = self.station / "hold.json"
                self.assertEqual(json.loads(held.read_text())["held"] if held.exists() else [], [])
                self.assertEqual(list((self.station / "requests" / "cur").iterdir()), [])
                self.assertFalse((self.station / "decisions").exists())


if __name__ == "__main__":
    unittest.main()
