"""aos_exec：真的跑——三種目標、退出碼、選項落地（append／mkdir／inherit／merge／clear）、逾時、

本檔：欄位、選項落地、$env（TestFieldsRun、TestOptRun、TestEnvRun）。

run_target() 的 API。案例從 proto4-3 的 test_targets／test_status／test_opts／test_env／test_api 搬來。

大多數條目透過 cli/aos-exec 開子進程（驗命令列的退出碼與 stderr），API 那群直接 import。
"""
import os
import unittest

from _util import OUTER, ExecCase


# ---------------------------------------------------------------- 欄位跑起來 ----
class TestFieldsRun(ExecCase):

    def test_argv_only_streams_are_devnull(self):
        self.inst({"argv": ["sh", "-c", "echo out; echo err >&2"]})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_stdin_default_is_devnull(self):
        self.inst({"argv": ["sh", "-c", "cat"], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, stdin="這行不該被讀到\n").returncode, 0)
        self.assertEqual(self.read("out.txt"), "")

    def test_stdin_file(self):
        self.write("in.txt", "餵進去\n")
        self.inst({"argv": ["sh", "-c", "cat"], "stdin": "in.txt", "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "餵進去\n")

    def test_stdout_file_is_truncated(self):
        self.write("out.txt", "舊的東西應該被清掉\n")
        self.inst({"argv": ["sh", "-c", "echo 新的"], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "新的\n")

    def test_stderr_file(self):
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"], "stdout": "o.txt", "stderr": "e.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual((self.read("o.txt"), self.read("e.txt")), ("o\n", "e\n"))

    def test_exit_file_normal(self):
        self.inst({"argv": ["sh", "-c", "exit 7"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 7)
        self.assertEqual(self.read("code.txt"), "7\n")

    def test_exit_file_signalled_is_128_plus_n(self):
        self.inst({"argv": ["sh", "-c", "kill -9 $$"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 137)
        self.assertEqual(self.read("code.txt"), "137\n")

    def test_no_exit_field_writes_nothing(self):
        self.inst({"argv": ["true"]})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(os.listdir(self.d), [".aos"])

    def test_cwd_field_and_relative_paths_follow(self):
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "out.txt", "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")
        self.assertEqual(self.read("sub/code.txt"), "0\n")
        self.assertFalse(self.exists("out.txt"))

    def test_cwd_itself_is_relative_to_xxx_not_to_the_json(self):
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "out.txt"})
        r = self.aos(self.d)          # proto6 改：原本用 --dir-target；inst 在 .aos/，cwd 仍從 xxx 起算
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_metainfo_does_not_reach_the_child(self):
        self.inst({"_metainfo": {"_type": "posix", "_version": 1},
                   "argv": ["sh", "-c", "env | grep -c _metainfo; echo out"], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "0\nout\n")

    def test_reject_is_125_one_line_with_code(self):
        self.bad("{這不是 JSON", "JsonSyntax")
        self.bad({"argv": []}, "EmptyArgv")
        self.bad({"argv": ["true"], "stdout": {"$opt": "merge"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdin": {"$opt": "inherit", "$val": "x"}}, "OptionConflict")
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "", "$at": "."}}}, "ReferenceCycle")

    def test_reject_does_not_run_or_write_exit(self):
        self.inst({"argv": ["sh", "-c", "echo 跑到了 > 證據.txt"], "exit": "code.txt", "envs": {"A": 1}})
        self.assertEqual(self.aos(self.d).returncode, 125)
        self.assertFalse(self.exists("證據.txt"))
        self.assertFalse(self.exists("code.txt"))

    @unittest.skipIf(os.geteuid() == 0, "root 讀得到任何檔")
    def test_unreadable_inst_json_is_125(self):
        p = self.inst({"argv": ["true"]}, "locked.json")
        os.chmod(p, 0)
        r = self.aos(p)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReadFailed", r.stderr)


# ---------------------------------------------------------------- 選項落地 ----

class TestOptRun(ExecCase):

    def test_stdout_append_keeps_previous_runs(self):
        self.inst({"argv": ["sh", "-c", "echo 又一次"], "stdout": {"$opt": "append", "$val": "log.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("log.txt"), "又一次\n又一次\n")

    def test_stdout_mkdir_creates_nested_parent(self):
        self.inst({"argv": ["sh", "-c", "echo 深"], "stdout": {"$opt": "mkdir", "$val": "a/b/c/out.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("a/b/c/out.txt"), "深\n")

    def test_stdout_append_plus_mkdir(self):
        self.inst({"argv": ["sh", "-c", "echo 一"], "stdout": {"$opt": ["append", "mkdir"], "$val": "deep/out.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("deep/out.txt"), "一\n一\n")

    def test_stdout_without_mkdir_fails_on_missing_parent(self):
        self.inst({"argv": ["sh", "-c", "echo 深"], "stdout": "a/b/out.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("開不起來", r.stderr)

    def test_stdin_open_failure_is_125(self):
        self.inst({"argv": ["true"], "stdin": "沒有這個檔.txt"})
        self.assertEqual(self.aos(self.d).returncode, 125)

    def test_stderr_append_and_mkdir(self):
        self.inst({"argv": ["sh", "-c", "echo e >&2"], "stderr": {"$opt": ["append", "mkdir"], "$val": "logs/err.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("logs/err.txt"), "e\ne\n")

    def test_stderr_open_failure_is_125(self):
        self.inst({"argv": ["true"], "stderr": "沒有這個資料夾/err.txt"})
        self.assertEqual(self.aos(self.d).returncode, 125)

    def test_exit_append_writes_one_line_per_run(self):
        self.inst({"argv": ["sh", "-c", "exit 3"], "exit": {"$opt": "append", "$val": "codes.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 3)
        self.assertEqual(self.aos(self.d).returncode, 3)
        self.assertEqual(self.read("codes.txt"), "3\n3\n")

    def test_exit_without_append_is_truncated(self):
        self.write("code.txt", "舊的\n")
        self.inst({"argv": ["sh", "-c", "exit 4"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 4)
        self.assertEqual(self.read("code.txt"), "4\n")

    def test_exit_mkdir_creates_parent(self):
        self.inst({"argv": ["sh", "-c", "exit 5"], "exit": {"$opt": "mkdir", "$val": "run/1/code.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 5)
        self.assertEqual(self.read("run/1/code.txt"), "5\n")

    def test_exit_parent_dir_missing_is_125_and_does_not_run(self):
        self.inst({"argv": ["sh", "-c", "echo 跑到了 > 證據.txt"], "exit": "沒有這個資料夾/code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("父目錄不存在", r.stderr)
        self.assertFalse(self.exists("證據.txt"))

    def test_cwd_mkdir_creates_it_and_relative_paths_follow(self):
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": {"$opt": "mkdir", "$val": "work/x"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("work/x/out.txt"), os.path.join(self.d, "work", "x") + "\n")

    def test_cwd_missing_is_125(self):
        self.inst({"argv": ["true"], "cwd": "work/x"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("cwd 不是資料夾", r.stderr)

    def test_mkdir_failure_is_125(self):
        """makedirs 做不到（路徑中間卡一個普通檔）＝aos-exec 自己失敗。"""
        self.write("blocker", "我是檔案不是資料夾")
        self.inst({"argv": ["true"], "stdout": {"$opt": "mkdir", "$val": "blocker/out.txt"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("mkdir", r.stderr)

    def test_stdin_inherit_reads_aos_exec_stdin(self):
        self.inst({"argv": ["cat"], "stdin": {"$opt": "inherit"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, stdin="從外面餵的\n").returncode, 0)
        self.assertEqual(self.read("out.txt"), "從外面餵的\n")

    def test_stdout_inherit(self):
        self.inst({"argv": ["sh", "-c", "echo 直接印"], "stdout": {"$opt": "inherit"}})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stdout), (0, "直接印\n"))

    def test_stderr_inherit(self):
        self.inst({"argv": ["sh", "-c", "echo 錯誤 >&2"], "stderr": {"$opt": "inherit"}})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stderr), (0, "錯誤\n"))

    def test_stderr_merge(self):
        """merge＝兩條走同一個 open file description，交錯不會互相蓋掉。"""
        self.inst({"argv": ["sh", "-c", "echo one; echo two >&2; echo three"],
                   "stdout": "both.txt", "stderr": {"$opt": "merge"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("both.txt"), "one\ntwo\nthree\n")

    def test_merge_without_stdout_goes_to_devnull(self):
        self.inst({"argv": ["sh", "-c", "echo e >&2"], "stderr": {"$opt": "merge"}})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_merge_follows_stdout_append(self):
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"],
                   "stdout": {"$opt": "append", "$val": "both.txt"}, "stderr": {"$opt": "merge"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("both.txt"), "o\ne\no\ne\n")

    def test_merge_follows_stdout_inherit(self):
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"],
                   "stdout": {"$opt": "inherit"}, "stderr": {"$opt": "merge"}})
        r = self.aos(self.d)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "o\ne\n", ""))


# ---------------------------------------------------------------- 環境 ----

class TestEnvRun(ExecCase):

    def test_envs_is_overlaid_on_aos_exec_env(self):
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER][$ADDED]\""],
                   "envs": {"ADDED": "加上去的"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[外面來的][加上去的]\n")

    def test_envs_overwrites_inherited(self):
        self.inst({"argv": ["sh", "-c", "echo $AOSTEST_OUTER"], "envs": {"AOSTEST_OUTER": "蓋掉"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "蓋掉\n")

    def test_clear_with_val(self):
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER][$ONLY]\""],
                   "envs": {"$opt": "clear", "$val": {"ONLY": "只有我"}}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[][只有我]\n")

    def test_clear_without_val(self):
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER][$HOME]\""], "envs": {"$opt": "clear"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[][]\n")

    def test_clear_still_finds_sh_via_defpath(self):
        self.assertIn("/bin", os.defpath)
        self.inst({"argv": ["sh", "-c", "echo 找得到"], "envs": {"$opt": "clear"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "找得到\n")

    def test_argv0_uses_the_overlaid_path(self):
        """argv[0] 走的是疊加後的 PATH：故意指到空的地方就 127。"""
        self.inst({"argv": ["sh", "-c", "true"], "envs": {"$opt": "clear", "$val": {"PATH": os.path.join(self.d, "空")}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 127)

    def test_dollar_env_reads_aos_exec_env(self):
        self.inst({"argv": ["sh", "-c", "echo $COPIED"], "envs": {"COPIED": {"$env": "AOSTEST_OUTER"}},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "外面來的\n")

    def test_dollar_env_missing_is_125(self):
        self.inst({"argv": ["true"], "envs": {"X": {"$env": "AOSTEST_NOPE"}}})
        r = self.aos(self.d, env=OUTER)
        self.assertEqual(r.returncode, 125)
        self.assertIn("EnvironmentVariableMissing", r.stderr)

    def test_fmt_appends_to_path_and_child_sees_it(self):
        self.inst({"argv": ["sh", "-c", "echo $PATH"], "stdout": "out.txt",
                   "envs": {"PATH": {"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), OUTER["PATH"] + ":/opt/bin\n")

    def test_no_aos_star_variables_are_injected(self):
        self.inst({"argv": ["sh", "-c", "env | grep '^AOS_' | wc -l"], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt").strip(), "0")


if __name__ == "__main__":
    unittest.main()
