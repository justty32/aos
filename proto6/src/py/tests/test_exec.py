"""aos_exec：真的跑——三種目標、退出碼、選項落地（append／mkdir／inherit／merge／clear）、逾時、
run_target() 的 API。案例從 proto4-3 的 test_targets／test_status／test_opts／test_env／test_api 搬來。

大多數條目透過 cli/aos-exec 開子進程（驗命令列的退出碼與 stderr），API 那群直接 import。
"""
import io
import os
import stat
import subprocess
import sys
import time
import unittest

from _util import EXEC, OUTER, ExecCase

import aos_exec
import aos_inst

# 一個攔下 SIGTERM 不理的程式：只有 SIGKILL 弄得死它。
IGNORE_TERM = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"


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
        self.assertEqual(r.returncode, 2)
        self.assertIn("inst 目標的參數寫在 inst.json 的 argv 裡", r.stderr)
        self.assertFalse(self.exists("marker"))

    def test_directory_target_rejects_even_empty_separator_args(self):
        self.inst({"argv": ["sh", "-c", "printf ran > marker"]})
        r = self.aos(self.d, "--")
        self.assertEqual(r.returncode, 2)
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

    def test_dir_target_flag(self):
        self.inst({"argv": ["sh", "-c", "echo other"], "stdout": "out.txt"}, "other/place.json")
        r = self.aos(self.d, "--dir-target", "other/place.json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), "other\n")     # base 還是 xxx，不是 other/

    def test_dir_named_dot_json_is_still_a_dir(self):
        self.write("weird.json/inside.txt", "")
        r = self.aos(self.d + "/weird.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn(".aos/inst.json", r.stderr)

    def test_missing_xxx_is_2(self):
        r = self.aos(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("找不到", r.stderr)

    def test_missing_dir_target_is_2(self):
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 2)
        self.assertIn(".aos/inst.json", r.stderr)

    def test_bad_flag_is_2(self):
        self.assertEqual(self.aos(self.d, "--no-such-flag").returncode, 2)

    def test_no_args_is_2(self):
        self.assertEqual(self.aos().returncode, 2)

    def test_negative_timeout_is_2(self):
        self.inst({"argv": ["true"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "-1").returncode, 2)

    def test_entry_script_is_executable(self):
        self.assertTrue(os.stat(EXEC).st_mode & stat.S_IXUSR)
        with open(EXEC, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("#!"))
        r = subprocess.run([EXEC], capture_output=True, text=True)     # 不經 python3 也跑得起來
        self.assertEqual(r.returncode, 2)


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
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "out.txt"}, "deep/inst.json")
        r = self.aos(self.d, "--dir-target", "deep/inst.json")
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


# ---------------------------------------------------------------- 退出碼與逾時 ----

class TestStatus(ExecCase):

    def test_exit_code_passthrough(self):
        self.inst({"argv": ["sh", "-c", "exit 42"]})
        self.assertEqual(self.aos(self.d).returncode, 42)
        self.inst({"argv": ["sh", "-c", "exit 1"]})
        self.assertEqual(self.aos(self.d).returncode, 1)     # 子程式自己回 1 就是 1，不會跟 125 混

    def test_signalled_is_128_plus_n(self):
        self.inst({"argv": ["sh", "-c", "kill -TERM $$"]})
        self.assertEqual(self.aos(self.d).returncode, 143)

    def test_command_not_found_is_127_and_writes_exit(self):
        self.inst({"argv": ["aos-definitely-no-such-program"], "exit": "code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 127)
        self.assertIn("找不到程式", r.stderr)
        self.assertEqual(self.read("code.txt"), "127\n")

    def test_not_executable_is_126_and_writes_exit(self):
        self.write("noexec.sh", "#!/bin/sh\necho hi\n")
        self.inst({"argv": ["./noexec.sh"], "exit": "code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 126)
        self.assertIn("沒有執行權", r.stderr)
        self.assertEqual(self.read("code.txt"), "126\n")

    def test_timeout_sigterm_is_143(self):
        self.inst({"argv": ["sleep", "30"]})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 143)
        self.assertLess(time.monotonic() - t0, 5)      # SIGTERM 就死，不用等寬限期

    def test_timeout_sigkill_is_137(self):
        """攔下 SIGTERM 不理的：給 2 秒寬限期，還活著就 SIGKILL＝137。"""
        self.inst({"argv": [sys.executable, "-c", IGNORE_TERM], "exit": "code.txt"})
        t0 = time.monotonic()
        r = self.aos(self.d, "--timeout-ms", "200")
        self.assertEqual(r.returncode, 137)
        self.assertGreater(time.monotonic() - t0, 1.5)
        self.assertEqual(self.read("code.txt"), "137\n")

    def test_timeout_writes_exit_file(self):
        self.inst({"argv": ["sleep", "30"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "200").returncode, 143)
        self.assertEqual(self.read("code.txt"), "143\n")

    def test_timeout_kills_the_whole_group(self):
        """砍的是整個 process group，孫行程要跟著走。"""
        self.inst({"argv": ["sh", "-c", "sleep 30 & echo $! > pid.txt; wait"]})
        self.assertIn(self.aos(self.d, "--timeout-ms", "300").returncode, (137, 143))
        pid = int(self.read("pid.txt").strip())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and os.path.exists("/proc/%d" % pid):
            time.sleep(0.05)
        self.assertFalse(os.path.exists("/proc/%d" % pid))

    def test_timeout_zero_means_no_limit(self):
        self.inst({"argv": ["sh", "-c", "sleep 0.3; exit 5"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "0").returncode, 5)

    def test_timeout_applies_to_plain_file_and_json_mode(self):
        p = self.write("slow.sh", "#!/bin/sh\nsleep 30\n", executable=True)
        self.assertEqual(self.aos(p, "--timeout-ms", "200").returncode, 143)
        self.inst({"argv": ["sleep", "30"]}, "one.json")
        self.assertEqual(self.aos(os.path.join(self.d, "one.json"), "--timeout-ms", "200").returncode, 143)

    def test_not_timed_out_returns_normally(self):
        self.inst({"argv": ["sh", "-c", "exit 3"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "10000").returncode, 3)


# ---------------------------------------------------------------- API ----

class TestApi(ExecCase):
    """核心是一個函式：aos-run 就是 import 這個模組反覆叫 run_target()，拿 (code, kind)。"""

    def call(self, *args, **kw):
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            code, kind = aos_exec.run_target(*args, **kw)
        finally:
            sys.stderr = old
        return code, kind, buf.getvalue()

    def test_returns_exit_code(self):
        self.inst({"argv": ["sh", "-c", "exit 9"]})
        self.assertEqual(self.call(self.d)[:2], (9, "child"))

    def test_can_be_called_again_and_again(self):
        self.inst({"argv": ["sh", "-c", "echo x >> tally.txt"]})
        for _ in range(3):
            self.assertEqual(self.call(self.d)[:2], (0, "child"))
        self.assertEqual(self.read("tally.txt"), "x\nx\nx\n")

    def test_takes_dir_target_and_timeout(self):
        self.inst({"argv": ["sleep", "30"]}, "other.json")
        self.assertEqual(self.call(self.d, dir_target="other.json", timeout_ms=200)[:2], (143, "child"))

    def test_reports_the_reason_on_stderr(self):
        self.inst({"argv": "true"})
        code, kind, err = self.call(self.d)
        self.assertEqual((code, kind), (1, "aos"))
        self.assertTrue(err.startswith("aos-exec: FieldTypeMismatch: "), err)

    def test_kind_says_whose_code_it_is(self):
        self.assertEqual(self.call(os.path.join(self.d, "沒這個"))[:2], (2, "usage"))
        self.assertEqual(self.call(self.d, args=[])[:2], (2, "usage"))     # 資料夾目標給了 --
        self.inst("{ 這不是 JSON")
        self.assertEqual(self.call(self.d)[:2], (1, "aos"))
        self.inst({"argv": ["aos-definitely-no-such-program"]})
        self.assertEqual(self.call(self.d)[:2], (127, "child"))

    def test_missing_json_is_aos_not_usage(self):
        self.assertEqual(self.call(os.path.join(self.d, "later.json"))[:2], (1, "aos"))

    def test_on_spawn_gets_the_popen_then_none(self):
        seen = []
        self.inst({"argv": ["sh", "-c", "exit 4"]})
        code, kind, _ = self.call(self.d, on_spawn=seen.append)
        self.assertEqual((code, kind), (4, "child"))
        self.assertEqual(len(seen), 2)
        self.assertIsInstance(seen[0], subprocess.Popen)
        self.assertIsNone(seen[1])

    def test_stderr_and_args_kwargs(self):
        p = self.write("args.sh", "#!/bin/sh\nprintf '<%s>' \"$@\" > got.txt; echo err >&2\n", executable=True)
        errp = os.path.join(self.d, "seen.err")
        code, kind, _ = self.call(p, stderr=errp, args=["a", "b c"])
        self.assertEqual((code, kind), (0, "child"))
        self.assertEqual(self.read("got.txt"), "<a><b c>")
        self.assertEqual(self.read("seen.err"), "err\n")

    def test_main_turns_kinds_into_exit_codes(self):
        """命令列才換算：usage→2、aos→125、child→原樣。"""
        buf = io.StringIO()
        old, sys.stderr = sys.stderr, buf
        try:
            self.inst("{ 這不是 JSON")
            self.assertEqual(aos_exec.main([self.d]), 125)
            self.assertEqual(aos_exec.main([os.path.join(self.d, "沒這個")]), 2)
            self.inst({"argv": ["sh", "-c", "exit 1"]})
            self.assertEqual(aos_exec.main([self.d]), 1)
        finally:
            sys.stderr = old


class TestRunInstTimeout(ExecCase):
    """期限真的到才標記，不能拿 143／137 猜；stdout 仍保留已收的部分。"""

    def run_memory(self, script, timeout_ms=1000):
        inst = aos_inst.load_obj({"argv": [sys.executable, "-c", script]}, self.d)
        return aos_exec.run_inst(inst, "", timeout_ms=timeout_ms)

    def test_normal_exit_143_is_not_timeout_and_tuple_compatible(self):
        r = self.run_memory("print('正常'); raise SystemExit(143)")
        code, kind, out = r
        self.assertEqual(r, (143, "child", "正常\n"))
        self.assertEqual((code, kind, out), r)
        self.assertFalse(r.timed_out)

    def test_sigterm_timeout_keeps_output(self):
        r = self.run_memory("import time; print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (143, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_sigkill_timeout_keeps_output(self):
        r = self.run_memory("import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                            "print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (137, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_graceful_zero_exit_after_deadline_is_still_timeout(self):
        r = self.run_memory("import signal, sys, time; "
                            "signal.signal(signal.SIGTERM, lambda *args: sys.exit(0)); "
                            "print('已開始', flush=True); time.sleep(30)", 200)
        self.assertEqual(r, (0, "child", "已開始\n"))
        self.assertTrue(r.timed_out)

    def test_spawn_failure_is_not_timeout(self):
        inst = aos_inst.load_obj({"argv": ["aos-no-such-tool"]}, self.d)
        r = aos_exec.run_inst(inst, "", timeout_ms=1)
        self.assertEqual(r, (127, "child", ""))
        self.assertFalse(r.timed_out)


if __name__ == "__main__":
    unittest.main()
