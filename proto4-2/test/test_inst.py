"""執行一次 inst.json（＝aos 的「一個指令」）：八個欄位、127／126、逾時怎麼砍。"""
import json
import os
import shutil
import subprocess
import unittest

from _util import PY, CPU, copy_fx, last, mkinst, mktmp, read
import aos_cpu


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
        self.assertFalse(res["timed_out"])
        out = res["stdout"].splitlines()
        self.assertEqual(out[0], os.path.join(d, "sub"))       # cwd 相對於資料夾
        self.assertEqual(out[1], "env=hi")                     # env 疊上去了
        self.assertEqual(out[2], "tick=7")                     # AOS_TICK
        self.assertEqual(out[3], "dir=" + d)                   # AOS_DIR
        self.assertEqual(out[4], "來自 stdin")                  # stdin 那個**檔案**餵進去了
        self.assertIn("oops", res["stderr"])
        for k in ("tick", "exit", "signal", "stdout", "stderr", "timed_out",
                  "started_at", "ended_at"):
            self.assertIn(k, res)
        self.assertEqual(last(d), res)                          # last.json 就是它
        self.assertEqual(len(runs(d)), 1)                       # runs.jsonl 一行

    def test_stdin_empty_means_devnull(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "wc -c"]})
        self.assertEqual(aos_cpu.run_once(d, 1)["stdout"].strip(), "0")

    def test_stdout_stderr_to_files_last_json_null(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo 出; echo 錯 >&2"],
                              "stdout": "o.txt", "stderr": "e.txt"})
        res = aos_cpu.run_once(d, 1)
        self.assertEqual(read(d, "o.txt"), "出\n")
        self.assertEqual(read(d, "e.txt"), "錯\n")
        self.assertIsNone(res["stdout"])                        # 有寫＝last.json 記 null
        self.assertIsNone(res["stderr"])

    def test_stdout_file_is_truncated(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo 新"], "stdout": "o.txt"},
                   {"o.txt": "舊舊舊舊舊\n"})
        aos_cpu.run_once(d, 1)
        self.assertEqual(read(d, "o.txt"), "新\n")

    def test_stderr_merge_into_captured_stdout(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo 出; echo 錯 >&2"],
                              "stderr": {"$opt": "merge"}})
        res = aos_cpu.run_once(d, 1)
        self.assertIn("出", res["stdout"])
        self.assertIn("錯", res["stdout"])                      # 併進同一條
        self.assertIsNone(res["stderr"])

    def test_stderr_merge_into_stdout_file(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo 出; echo 錯 >&2"],
                              "stdout": "o.txt", "stderr": {"$opt": "merge"}})
        aos_cpu.run_once(d, 1)
        self.assertEqual(sorted(read(d, "o.txt").split()), ["出", "錯"])

    def test_exit_file_gets_status_and_128_plus_signal(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "exit 7"], "exit": "code.txt"})
        aos_cpu.run_once(d, 1)
        self.assertEqual(read(d, "code.txt"), "7\n")
        d2 = mkinst(self.tmp, {"argv": ["sh", "-c", "kill -TERM $$"], "exit": "code.txt"})
        res = aos_cpu.run_once(d2, 1)
        self.assertEqual(res["signal"], 15)
        self.assertEqual(read(d2, "code.txt"), "143\n")          # 128+15
        self.assertFalse(res["timed_out"])                       # 別人砍的不算逾時

    def test_redirect_target_dir_missing_is_126(self):
        """重導向的檔案開不起來＝設定階段失敗，exit 126；不會替你 mkdir。"""
        d = mkinst(self.tmp, {"argv": ["echo", "hi"], "stdout": "沒這個資料夾/o.txt"})
        res = aos_cpu.run_once(d, 1)
        self.assertEqual(res["exit"], 126)
        self.assertIn("開不起來", res["stderr"])

    def test_cwd_and_timeout_ms_defaults(self):
        d = mkinst(self.tmp, {"argv": ["pwd"]})
        self.assertEqual(aos_cpu.run_once(d, 1)["stdout"].strip(), d)   # cwd 空＝資料夾本身

    def test_command_not_found_is_127_not_error(self):
        d = mkinst(self.tmp, {"argv": ["這個程式不存在-zzz"]})
        res = aos_cpu.run_once(d, 1)
        self.assertEqual(res["exit"], 127)
        self.assertNotIn("error", res)                           # 算「跑完了一次」
        self.assertIn("找不到程式", res["stderr"])

    def test_not_executable_is_126(self):
        d = mkinst(self.tmp, {"argv": ["./noexec.sh"]},
                   {"noexec.sh": "#!/bin/sh\necho hi\n"})
        os.chmod(os.path.join(d, "noexec.sh"), 0o644)
        res = aos_cpu.run_once(d, 1)
        self.assertEqual(res["exit"], 126)
        self.assertIn("沒有執行權", res["stderr"])

    def test_path_lookup_uses_overlaid_env(self):
        d = mkinst(self.tmp, {"argv": ["mytool"], "env": {"PATH": "bin"}},
                   {"bin/mytool": "#!/bin/sh\necho 我是 mytool\n"})
        os.chmod(os.path.join(d, "bin", "mytool"), 0o755)
        res = aos_cpu.run_once(d, 1)                             # PATH 只有相對的 bin
        self.assertEqual(res["exit"], 0)
        self.assertIn("我是 mytool", res["stdout"])

    def test_timeout_sigterm_path_signal_15(self):
        d = copy_fx("slow", self.tmp)                            # sleep 5，timeout_ms 300
        res = aos_cpu.run_once(d, 1)
        self.assertTrue(res["timed_out"])
        self.assertEqual(res["signal"], 15)                      # 乖乖接 SIGTERM
        self.assertIsNone(res["exit"])

    def test_timeout_sigkill_path_signal_9(self):
        d = copy_fx("stubborn", self.tmp)                        # trap '' TERM，撐過寬限期
        res = aos_cpu.run_once(d, 1)
        self.assertTrue(res["timed_out"])
        self.assertEqual(res["signal"], 9)

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


if __name__ == "__main__":
    unittest.main()
