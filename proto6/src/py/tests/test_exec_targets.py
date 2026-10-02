"""aos_exec：真的跑——三種目標、退出碼、選項落地（append／mkdir／inherit／merge／clear）、逾時、

本檔：三種目標與 stderr 旗標（TestTargets、TestStderrFlag）。

run_target() 的 API。案例從 proto4-3 的 test_targets／test_status／test_opts／test_env／test_api 搬來。

大多數條目透過 cli/aos-exec 開子進程（驗命令列的退出碼與 stderr），API 那群直接 import。
"""
import os
import stat
import subprocess
import unittest

from _util import EXEC, ExecCase


# ---------------------------------------------------------------- 三種目標 ----
class TestTargets(ExecCase):

    def test_plain_file_runs_and_inherits_stdio(self):
        """普通檔案：直接跑，三條串流繼承 aos-exec 的，cwd＝它所在的資料夾。"""
        p = self.write("hello.sh", "#!/bin/sh\nread x\necho \"out:$x $PWD\"\necho err >&2\n", executable=True)
        r = self.aos(p, stdin="fed\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "out:fed %s\n" % self.d)
        self.assertEqual(r.stderr, "err\n")

    def test_plain_file_gets_everything_after_separator_verbatim(self):
        p = self.write("args.sh", "#!/bin/sh\nprintf '<%s>\\n' \"$@\"\n", executable=True)
        r = self.aos(p, "--timeout-ms", "1000", "--", "a b", "", "--stderr", "-")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "<a b>\n<>\n<--stderr>\n<->\n")

    def test_plain_file_not_executable_is_126(self):
        p = self.write("noexec.sh", "#!/bin/sh\necho hi\n")
        r = self.aos(p)
        self.assertEqual(r.returncode, 126)
        self.assertIn("aos-exec:", r.stderr)

    def test_plain_file_stderr_flag(self):
        p = self.write("e.sh", "#!/bin/sh\necho oops >&2\n", executable=True)
        r = self.aos(p, "--stderr", "seen.err", cwd=self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("seen.err"), "oops\n")
        self.assertEqual(r.stderr, "")

    def test_json_target_rejects_separator_args(self):
        target = self.inst({"argv": ["sh", "-c", "printf ran > marker"]}, "one.json")
        r = self.aos(target, "--", "extra")
        self.assertEqual(r.returncode, 1)                  # proto6 改：用法錯 1（aos 結束碼慣例）
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", r.stderr)
        self.assertFalse(self.exists("marker"))

    def test_directory_target_rejects_even_empty_separator_args(self):
        self.inst({"argv": ["sh", "-c", "printf ran > marker"]})
        r = self.aos(self.d, "--")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.exists("marker"))

    def test_json_file_is_parsed_as_inst(self):
        """.json 檔＝當 inst.json 讀；base 是那個 .json 所在的資料夾。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"}, "one.json")
        r = self.aos(os.path.join(self.d, "one.json"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), self.d + "\n")

    def test_json_in_subdir_uses_that_subdir(self):
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"}, "sub/two.json")
        r = self.aos(os.path.join(self.d, "sub", "two.json"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_missing_json_is_125_not_usage(self):
        """以 .json 結尾但不存在的路徑：aos-exec 自己失敗（125、ReadFailed），不是用法錯。"""
        r = self.aos(os.path.join(self.d, "later.json"))
        self.assertEqual(r.returncode, 125)
        self.assertTrue(r.stderr.startswith("aos-exec: ReadFailed: "), r.stderr)

    def test_dir_uses_default_dir_target(self):
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), self.d + "\n")

    def test_no_target_means_current_dir(self):
        """xxx 留空＝`.`：跑呼叫時所在資料夾的 .aos/inst.json，base 就是那個資料夾。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"})
        r = self.aos(cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("out.txt"), self.d + "\n")
        r = self.aos("--timeout-ms", "1000", cwd=self.d)          # 只有旗標、沒有 xxx 也一樣
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dir_falls_back_to_inst_json(self):
        """proto6 新增：沒有 .aos/inst.json 就找 xxx/inst.json，base 還是 xxx 自己。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"}, "inst.json")
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("out.txt"), self.d + "\n")

    def test_dir_prefers_dot_aos_inst_json(self):
        """proto6 新增：兩個都有時跑 .aos/inst.json。"""
        self.inst({"argv": ["sh", "-c", "echo aos"], "stdout": "out.txt"})
        self.inst({"argv": ["sh", "-c", "echo plain"], "stdout": "out.txt"}, "inst.json")
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("out.txt"), "aos\n")

    def test_dir_name_from_env(self):
        """proto6 新增（使用者 2026-10-01）：資料夾目標的 `.aos` 照環境變數 AOS_DIRNAME；沒設＝.aos。"""
        self.inst({"argv": ["sh", "-c", "echo aos"], "stdout": "out.txt"})
        self.inst({"argv": ["sh", "-c", "echo aos2"], "stdout": "out.txt"}, ".aos2/inst.json")
        env = lambda v: dict(os.environ, AOS_DIRNAME=v)
        unset = {k: v for k, v in os.environ.items() if k != "AOS_DIRNAME"}
        self.assertEqual(self.aos(self.d, env=env(".aos2")).returncode, 0)
        self.assertEqual(self.read("out.txt"), "aos2\n")
        self.assertEqual(self.aos(self.d, env=unset).returncode, 0)
        self.assertEqual(self.read("out.txt"), "aos\n")
        r = self.aos(self.d, env=env(".aos3"))              # 名字底下沒有、頂層也沒有：用法錯 1
        self.assertEqual(r.returncode, 1)
        self.assertIn(".aos3/inst.json", r.stderr)
        self.inst({"argv": ["sh", "-c", "echo plain"], "stdout": "out.txt"}, "inst.json")
        self.assertEqual(self.aos(self.d, env=env(".aos3")).returncode, 0)   # 退回頂層 inst.json
        self.assertEqual(self.read("out.txt"), "plain\n")

    def test_empty_dir_name_means_target_itself(self):
        """proto6 新增（使用者 2026-10-01 再改）：AOS_DIRNAME 設成空字串＝不用子資料夾，只找 <目標>/inst.json；
        跟「沒設」（先 .aos/inst.json 再 inst.json）分得開。"""
        self.inst({"argv": ["sh", "-c", "echo aos"], "stdout": "out.txt"})
        empty = dict(os.environ, AOS_DIRNAME="")
        unset = {k: v for k, v in os.environ.items() if k != "AOS_DIRNAME"}
        r = self.aos(self.d, env=empty)                     # 只有 .aos/inst.json：空字串不看它，用法錯 1
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒有 inst.json", r.stderr)
        self.assertNotIn(".aos", r.stderr.replace(self.d, ""))
        self.assertFalse(self.exists("out.txt"))
        self.inst({"argv": ["sh", "-c", "echo plain"], "stdout": "out.txt"}, "inst.json")
        self.assertEqual(self.aos(self.d, env=empty).returncode, 0)
        self.assertEqual(self.read("out.txt"), "plain\n")  # 兩個都有：空字串跑頂層的
        self.assertEqual(self.aos(self.d, env=unset).returncode, 0)
        self.assertEqual(self.read("out.txt"), "aos\n")    # 沒設：跑 .aos/ 的
        self.assertEqual(self.aos(cwd=self.d, env=empty).returncode, 0)   # 留空＝. 也一樣
        self.assertEqual(self.read("out.txt"), "plain\n")

    def test_bad_dir_name_is_usage(self):
        """proto6 新增：AOS_DIRNAME 含 / 或是 . 、.. 時，資料夾目標算用法錯（使用者 2026-10-01：用法錯回 1）。"""
        self.inst({"argv": ["sh", "-c", "touch ran"]})
        for bad in ("a/b", ".", ".."):
            r = self.aos(self.d, env=dict(os.environ, AOS_DIRNAME=bad))
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("AOS_DIRNAME", r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertFalse(self.exists("ran"))
        # 只影響資料夾目標：直接給 .json 檔照跑
        r = self.aos(os.path.join(self.d, ".aos", "inst.json"), env=dict(os.environ, AOS_DIRNAME=".."))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.exists(".aos/ran"))                  # .json 目標的 base 是檔所在的資料夾

    def test_top_level_user_is_ignored(self):
        """proto6（使用者 2026-10-01）：拿掉「認得頂層 user」，回到 proto5——user 當陌生鍵忽略，照目前身分跑。"""
        self.inst({"user": "root" if os.geteuid() else "nobody", "argv": ["sh", "-c", "touch ran"]})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(self.exists("ran"))

    def test_dir_target_flag_is_gone(self):
        """proto6 改：不提供改尋找路徑的旗標，--dir-target 是用法錯。"""
        self.inst({"argv": ["true"]}, "other/place.json")
        self.assertEqual(self.aos(self.d, "--dir-target", "other/place.json").returncode, 1)

    def test_dir_named_dot_json_is_still_a_dir(self):
        self.write("weird.json/inside.txt", "")
        r = self.aos(self.d + "/weird.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn(".aos/inst.json", r.stderr)

    def test_missing_xxx_is_1(self):
        r = self.aos(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("找不到", r.stderr)

    def test_missing_dir_target_is_1(self):
        """proto6 改：.aos/inst.json 跟 inst.json 都沒有才是用法錯（1），訊息兩個都提。"""
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn(".aos/inst.json", r.stderr)
        self.assertIn("也沒有 inst.json", r.stderr)

    def test_bad_flag_is_1(self):
        """proto6 改（aos 結束碼慣例）：argparse 的用法錯也回 1，不是它預設的 2。"""
        self.assertEqual(self.aos(self.d, "--no-such-flag").returncode, 1)
        self.assertEqual(self.aos(self.d, "--timeout-ms", "abc").returncode, 1)
        self.assertEqual(self.aos(self.d, "--help").returncode, 0)

    def test_no_args_is_1(self):
        self.assertEqual(self.aos().returncode, 1)

    def test_negative_timeout_is_1(self):
        self.inst({"argv": ["true"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "-1").returncode, 1)

    def test_entry_script_is_executable(self):
        self.assertTrue(os.stat(EXEC).st_mode & stat.S_IXUSR)
        with open(EXEC, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("#!"))
        r = subprocess.run([EXEC], capture_output=True, text=True)     # 不經 python3 也跑得起來
        self.assertEqual(r.returncode, 1)


# ---------------------------------------------------------------- --stderr ----

class TestStderrFlag(ExecCase):

    def test_dash_makes_child_stderr_visible(self):
        self.inst({"argv": ["sh", "-c", "echo typo >&2"]})
        r = self.aos(self.d, "--stderr", "-")
        self.assertEqual(r.returncode, 0)
        self.assertIn("typo", r.stderr)

    def test_path_writes_from_the_callers_cwd(self):
        self.inst({"argv": ["sh", "-c", "echo typo >&2"], "cwd": "sub"})
        self.write("sub/.keep", "")
        r = self.aos(self.d, "--stderr", "seen.err", cwd=self.d)
        self.assertEqual(r.returncode, 0)
        self.assertIn("typo", self.read("seen.err"))        # 在呼叫者的 cwd，不是 inst 的 cwd

    def test_path_overrides_merge(self):
        self.inst({"argv": ["sh", "-c", "echo out; echo typo >&2"], "stdout": "out.txt",
                   "stderr": {"$opt": "merge"}})
        r = self.aos(self.d, "--stderr", "seen.err", cwd=self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), "out\n")
        self.assertIn("typo", self.read("seen.err"))

    def test_flag_overrides_inst_stderr_options_including_mkdir(self):
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"], "stdout": "o.txt",
                   "stderr": {"$opt": ["append", "mkdir"], "$val": "never/e.txt"}})
        r = self.aos(self.d, "--stderr", "-")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "e\n")
        self.assertEqual(self.read("o.txt"), "o\n")
        self.assertFalse(self.exists("never"))          # 被蓋掉的 mkdir 也不建

    def test_path_that_cannot_be_opened_is_125(self):
        self.inst({"argv": ["true"]})
        r = self.aos(self.d, "--stderr", os.path.join(self.d, "missing", "x"))
        self.assertEqual(r.returncode, 125)


if __name__ == "__main__":
    unittest.main()
