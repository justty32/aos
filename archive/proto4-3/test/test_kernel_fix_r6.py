#!/usr/bin/env python3

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

import _util  # noqa: F401
from aos_kernel import KHome
from aos_kernel_syscall import handle_syscalls


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "aos-kernel-init"
KERNEL = ROOT / "aos-kernel"


class KernelFixR6Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aos-kernel-fix-r6-")
        self.base = Path(self.tmp.name)
        self.k = self.base / "K"
        self.daemon_home = self.base / "daemon"
        self.env = os.environ | {"AOS_DAEMON_HOME": str(self.daemon_home)}
        result = subprocess.run(
            [sys.executable, str(INIT), str(self.k), "--ncpu", "1"],
            text=True, capture_output=True, check=False, env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def kernel(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(KERNEL), *map(str, args)], text=True,
            capture_output=True, check=False, env=env or self.env,
        )

    def put_json(self, path, value=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value or {"argv": ["true"], "cwd": str(self.base)}),
                        encoding="utf-8")

    def test_rm_clears_done_and_bad_records(self):
        h = KHome(self.k)
        for label, folder in (("done", Path(h.done)), ("bad", Path(h.bad))):
            with self.subTest(label=label):
                old = folder / "old.json"
                self.put_json(old)
                request = Path(h.syscalls) / f"rm-{label}.json"
                self.put_json(request, {"op": "rm", "pid": "old"})
                handle_syscalls(h, h.config(), h.state(), [])
                reply = json.loads((Path(h.syscalls_done) / request.name).read_text())
                self.assertTrue(reply["ok"])
                self.assertEqual(reply["msg"], f"清掉 {label} 裡的舊紀錄：old")
                self.assertFalse(old.exists())

    def test_add_named_proc_replaces_only_retired_record(self):
        old = self.k / "procs/done/replay.json"
        self.put_json(old)
        inst = self.base / "job.json"
        self.put_json(inst)
        result = self.kernel("add", self.k, inst, "--name", "replay")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("清掉 done 裡的舊紀錄：replay", result.stdout)
        self.assertFalse(old.exists())
        self.assertTrue((self.k / "procs/replay.json").exists())

    def test_ls_reports_missing_daemon_home(self):
        env = dict(os.environ)
        env.pop("AOS_DAEMON_HOME", None)
        result = self.kernel("ls", self.k, env=env)
        self.assertIn("找不到 daemon 的家（AOS_DAEMON_HOME 沒設？）", result.stdout)

    def test_ls_reports_normally_stopped_daemon(self):
        self.daemon_home.mkdir()
        result = self.kernel("ls", self.k)
        self.assertIn("daemon 沒在跑（正常收工過）", result.stdout)

    def test_ls_reports_dead_daemon_pid(self):
        self.daemon_home.mkdir()
        self.put_json(self.daemon_home / "state.json", {"pid": 999999999, "runs": {}})
        result = self.kernel("ls", self.k)
        self.assertIn("daemon dead（pid 999999999 不在了）", result.stdout)

    def test_ls_uses_dash_for_missing_runs_and_aligns_long_proc(self):
        name = "a-very-long-process-name"
        state = {"cpus": {"0": {"pid": name, "since": time.time() - 2,
                                  "runs_at": 0}}, "queue": [], "waiting": {}}
        (self.k / "state.json").write_text(json.dumps(state), encoding="utf-8")
        self.daemon_home.mkdir()
        self.put_json(self.daemon_home / "state.json", {"pid": os.getpid(), "runs": {}})
        lines = self.kernel("ls", self.k).stdout.splitlines()
        header = next(line for line in lines if line.startswith("CPU "))
        row = next(line for line in lines if line.startswith("0 "))
        match = re.match(r"\S+\s+(\S+)\s+(\S+)\s+(\S+)", row)
        self.assertEqual((match.group(1), match.group(3)), (name, "-"))
        self.assertEqual(match.start(2), header.index("ON"))
        self.assertNotIn("None", row)


if __name__ == "__main__":
    unittest.main()
