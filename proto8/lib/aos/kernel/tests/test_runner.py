# 用真的 aos-daemon 與假的端點函數驗「自己跑」零件：掛上、收成品、逾時、重掛一次、放棄。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KERNEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KERNEL))
import runner  # noqa: E402

FUNCTION = '''#!/usr/bin/env python3
# Fake endpoint function: sleep and exit as stdin says; with "once", only the first run sleeps.
import json, os, sys, time
ask = json.load(sys.stdin)
marker = os.path.join(os.environ["AOS_STACK"], "ran_before")
again = os.path.exists(marker)
open(marker, "w").close()
if not (ask.get("once") and again):
    time.sleep(ask.get("sleep", 0))
print(json.dumps({"said": ask.get("say")}))
sys.exit(ask.get("code", 0))
'''


class ZeroTimeout(unittest.TestCase):
    def test_mount_omits_zero_timeout_and_exit_is_not_late(self):
        from unittest.mock import patch
        with patch.object(runner, 'send', return_value='letter') as send, patch.object(runner, 'write_json'):
            runner.mount('/job', 'job', '/tool', {}, '/box', '/daemon', timeout_ms=0)
            spec = send.call_args.args[1]['procs_added']['job']['exec']
            self.assertNotIn('timeout_ms', spec)
        with patch.object(runner, 'read_json', return_value={'phase': 'done', 'code': 137}):
            result = runner.settle('/job', {'mounted_at': 0}, ({}, ''), '/box', '/daemon', timeout_ms=0)
            self.assertEqual(result, {'kind': 'exit', 'code': 137, 'timed_out': False})


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="runner-test-", dir=os.environ.get("KERNEL_TEST_TMP")))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.stack = self.root / "stack"
        self.stack.mkdir()
        self.function = self.root / "function"
        self.function.mkdir()
        (self.function / "_entry").write_text(FUNCTION)
        (self.function / "_entry").chmod(0o755)
        (self.root / "daemon.json").write_text(json.dumps({"interval_ms": 20, "procs": {}}))
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("AOS_")}
        self.log = open(self.root / "daemon.log", "a")
        self.addCleanup(self.log.close)
        self.daemon = subprocess.Popen(["aos-daemon", "--enable-logs", "daemon.json"], cwd=self.root,
                                       env=dict(self.env, AOS_STACK=str(self.stack)),
                                       stdout=self.log, stderr=self.log)
        self.addCleanup(self.stop_daemon)
        self.until(lambda: (runner.read_json(self.stack / "procs_state.json") or {}).get("pid") == self.daemon.pid)
        self.home = str(self.stack) + "/"
        self.box = str(self.stack / (runner.read_json(self.stack / "procs_state.json")["procs_requests"]))
        self.until(lambda: os.path.isdir(os.path.join(self.box, "new")))

    def stop_daemon(self):
        # 只收自己起的那一個：送訊號前核對它的 cwd 還在這個暫存夾。
        if self.daemon.poll() is None and os.readlink("/proc/%d/cwd" % self.daemon.pid) == str(self.root):
            self.daemon.terminate()
            self.daemon.wait(timeout=20)

    def until(self, probe, timeout=15):
        end = time.monotonic() + timeout
        while True:
            got = probe()
            if got:
                return got
            self.assertLess(time.monotonic(), end, "timed out waiting for the fixture")
            time.sleep(0.03)

    def ctl(self, *args):
        result = subprocess.run(["aos-daemon-ctl", "-d", str(self.stack), *args], env=self.env, cwd=self.root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def job(self, name, **ask):
        folder = self.root / "jobs" / name
        folder.mkdir(parents=True)
        (folder / "request.json").write_text(json.dumps(ask))
        return folder

    def mount(self, folder, timeout_ms=None, box=None):
        return runner.mount(str(folder), "job_" + folder.name, str(self.function), {"note": "kept"},
                            box or self.box, self.home, timeout_ms=timeout_ms)

    def settle(self, folder, **options):
        proc = runner.read_json(folder / "proc.json")
        return runner.settle(str(folder), proc, runner.read_table(self.home), self.box, self.home, **options)

    def row(self, folder):
        return runner.read_table(self.home)[0].get("job_" + folder.name)

    def phase(self, folder, phase):
        self.until(lambda: (self.row(folder) or {}).get("phase") == phase)

    def test_mount_adds_a_row_and_records_the_job(self):
        folder = self.job("mounted", sleep=5)
        proc = self.mount(folder)
        self.assertEqual(proc, runner.read_json(folder / "proc.json"))
        self.assertEqual((proc["name"], proc["exec"], proc["retries"], proc["note"]),
                         ("job_mounted", str(self.function), 0, "kept"))
        self.assertTrue(proc["mount_letter"])
        self.assertIsNone(self.settle(folder))               # 掛信還沒套、或正在跑：都算在飛
        self.phase(folder, "running")
        self.assertIsNone(self.settle(folder))

    def test_finished_job_hands_back_its_stdout_and_the_row_is_removed(self):
        folder = self.job("done", say="hello", code=3)
        self.mount(folder)
        result = self.until(lambda: self.settle(folder))
        self.assertEqual(result, {"kind": "exit", "code": 3, "timed_out": False})
        self.assertEqual(json.loads((folder / "reply.json").read_text()), {"said": "hello"})
        self.until(lambda: self.row(folder) is None)         # 收成品時順手寄了 procs_removed

    def test_timeout_is_reported_as_timed_out(self):
        folder = self.job("slow", sleep=30)
        self.mount(folder, timeout_ms=300)
        result = self.until(lambda: self.settle(folder, timeout_ms=300))
        self.assertEqual((result["kind"], result["timed_out"]), ("exit", True))
        self.assertIn(result["code"], (143, 137))

    def test_job_removed_midway_is_mounted_once_more(self):
        folder = self.job("again", sleep=30, once=True, say="second run")
        first = self.mount(folder)
        self.phase(folder, "running")
        self.ctl("rm", "job_again")
        self.until(lambda: self.row(folder) is None)
        self.assertIsNone(self.settle(folder))
        second = runner.read_json(folder / "proc.json")
        self.assertEqual(second["retries"], 1)
        self.assertNotEqual(second["mount_letter"], first["mount_letter"])
        self.assertGreater(second["mounted_at"], first["mounted_at"])
        result = self.until(lambda: self.settle(folder))
        self.assertEqual(result, {"kind": "exit", "code": 0, "timed_out": False})
        self.assertEqual(json.loads((folder / "reply.json").read_text()), {"said": "second run"})

    def test_second_loss_gives_up(self):
        folder = self.job("lost", sleep=30)
        self.mount(folder)
        for expected in (None, {"kind": "twice"}):
            self.phase(folder, "running")
            self.ctl("rm", "job_lost")
            self.until(lambda: self.row(folder) is None)
            self.assertEqual(self.settle(folder), expected)

    def test_unsendable_mount_letter_fails(self):
        folder = self.job("nowhere")
        with self.assertRaises(runner.Failed) as raised:
            self.mount(folder, box=str(self.root / "no_such_mailbox"))
        self.assertEqual(raised.exception.code, "MailboxMissing")
        self.assertFalse((folder / "proc.json").exists())

    def test_stopped_row_waits_then_gives_up_and_sleeping_row_keeps_flying(self):
        folder = self.job("held", sleep=30)
        self.mount(folder)
        self.phase(folder, "running")
        self.ctl("sleep", "job_held")
        self.phase(folder, "sleeping")
        self.assertIsNone(self.settle(folder))               # 睡著的照算在飛，不起算
        self.assertNotIn("stopped_seen_at", runner.read_json(folder / "proc.json"))
        self.ctl("wake", "job_held")
        self.phase(folder, "running")
        # stop 要等這一圈跑完；趁它在 stopping 時叫它睡，列就停在 stopped（沒寫原因、沒跑完）。
        stopping = subprocess.Popen(["aos-daemon-ctl", "-d", str(self.stack), "stop", "job_held"], env=self.env,
                                    cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(stopping.wait)
        self.phase(folder, "stopping")
        self.ctl("sleep", "job_held")
        self.phase(folder, "stopped")
        self.assertIsNone(self.settle(folder))               # 被人停著：先等，記下第一次看到的時間
        seen = runner.read_json(folder / "proc.json")["stopped_seen_at"]
        self.assertIsNone(self.settle(folder))
        self.assertEqual(runner.read_json(folder / "proc.json")["stopped_seen_at"], seen)
        self.assertEqual(self.settle(folder, give_up_s=0),
                         {"kind": "stopped", "name": "job_held", "seconds": 0})
        self.until(lambda: self.row(folder) is None)


if __name__ == "__main__":
    unittest.main()
