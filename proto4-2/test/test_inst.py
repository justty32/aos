"""執行一次 inst.json（＝aos 的「一個指令」）。"""
import json
import os
import shutil
import subprocess
import unittest

from _util import PY, CPU, copy_fx, mktmp
import aos_cpu


def last(d):
    with open(os.path.join(d, ".aos", "last.json")) as f:
        return json.load(f)


def runs(d):
    with open(os.path.join(d, ".aos", "runs.jsonl")) as f:
        return [json.loads(x) for x in f if x.strip()]


class InstTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-inst-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_argv_env_cwd_stdin_all_taken(self):
        d = copy_fx("hello", self.tmp)
        res = aos_cpu.run_once(d, 7)
        self.assertEqual(res["exit"], 3)                       # exit status 拿得到
        self.assertIsNone(res["signal"])
        out = res["stdout"].splitlines()
        self.assertEqual(out[0], os.path.join(d, "sub"))       # cwd 相對於資料夾
        self.assertEqual(out[1], "env=hi")                     # env 疊上去了
        self.assertEqual(out[2], "tick=7")                     # AOS_TICK
        self.assertEqual(out[3], "dir=" + d)                   # AOS_DIR
        self.assertEqual(out[4], "來自 stdin")                  # stdin 餵進去了
        self.assertIn("oops", res["stderr"])
        for k in ("tick", "exit", "signal", "stdout", "stderr", "started_at", "ended_at"):
            self.assertIn(k, res)
        self.assertIsNotNone(res["started_at"])
        self.assertIsNotNone(res["ended_at"])
        self.assertEqual(last(d), res)                          # last.json 就是它
        self.assertEqual(len(runs(d)), 1)                       # runs.jsonl 一行

    def test_not_an_object_is_one_error_and_cpu_survives(self):
        d = copy_fx("badinst", self.tmp)
        p = subprocess.run([PY, CPU, d, "--max-runs", "1", "--interval", "0"],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0)                       # cpu 不炸
        r = last(d)
        self.assertIn("error", r)
        self.assertIn("物件", r["error"])
        self.assertIsNone(r["exit"])

    def test_inst_path_is_configurable(self):
        d = copy_fx("alt", self.tmp)
        res = aos_cpu.run_once(d, 1, "my/inst.json")
        self.assertEqual(res["exit"], 0)
        self.assertIn("我在 my/inst.json", res["stdout"])
        p = subprocess.run([PY, CPU, d, "--max-runs", "1", "--inst", "my/inst.json"],
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertIn("我在 my/inst.json", last(d)["stdout"])

    def test_timeout_kills_and_records_signal_9(self):
        d = copy_fx("slow", self.tmp)
        res = aos_cpu.run_once(d, 1)
        self.assertEqual(res["signal"], 9)
        self.assertIsNone(res["exit"])


if __name__ == "__main__":
    unittest.main()
