"""選項物件 `{"$opt": …, "$val": …}`：形狀怎麼驗（UnknownOption／OptionConflict），
以及每個選項真的跑起來是什麼樣（append／mkdir／inherit／merge）。"""
import os
import unittest

from _util import ExecCase


class TestOptShape(ExecCase):
    """讀／驗階段就被擋下來的：退出碼 125、stderr 一行、開頭是代號。"""

    def bad(self, obj, code):
        self.inst(obj)
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-exec: %s: " % code), r.stderr)

    def test_opt_array_is_accepted(self):
        """$opt 可以是陣列：append＋mkdir 一起開。"""
        self.inst({"argv": ["sh", "-c", "echo 一"],
                   "stdout": {"$opt": ["append", "mkdir"], "$val": "deep/out.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("deep/out.txt"), "一\n")

    def test_opt_not_a_string_or_array(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": 3, "$val": "x"}},
                 "DirectiveValueTypeMismatch")

    def test_opt_empty_array(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": [], "$val": "x"}},
                 "DirectiveValueTypeMismatch")

    def test_opt_array_with_non_string(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": ["append", 1], "$val": "x"}},
                 "DirectiveValueTypeMismatch")

    def test_duplicate_option_is_unknown_option(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": ["append", "append"], "$val": "x"}},
                 "UnknownOption")

    def test_option_not_for_this_position(self):
        """clear 是 envs 的、mkdir 不是 stdin 的、大寫不算。"""
        self.bad({"argv": ["true"], "stdout": {"$opt": "clear"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdin": {"$opt": "mkdir", "$val": "x"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdin": {"$opt": "Inherit"}}, "UnknownOption")

    def test_option_in_a_position_with_no_options(self):
        """argv 的元素、envs 的值都不吃選項。"""
        self.bad({"argv": [{"$opt": "inherit"}]}, "UnknownOption")
        self.bad({"argv": ["true"], "envs": {"A": {"$opt": "clear"}}}, "UnknownOption")

    def test_inherit_with_val_conflicts(self):
        self.bad({"argv": ["true"], "stdin": {"$opt": "inherit", "$val": "in.txt"}},
                 "OptionConflict")

    def test_merge_with_val_conflicts(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": "merge", "$val": "e.txt"}},
                 "OptionConflict")

    def test_inherit_plus_append_conflicts(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": ["inherit", "append"], "$val": "x"}},
                 "OptionConflict")

    def test_merge_plus_inherit_conflicts(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": ["merge", "inherit"]}},
                 "OptionConflict")

    def test_merge_plus_mkdir_conflicts(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": ["mkdir", "merge"], "$val": "d/e"}},
                 "OptionConflict")

    def test_append_without_val_conflicts(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": "append"}}, "OptionConflict")
        self.bad({"argv": ["true"], "exit": {"$opt": ["append", "mkdir"]}}, "OptionConflict")
        self.bad({"argv": ["true"], "cwd": {"$opt": "mkdir"}}, "OptionConflict")

    def test_append_with_empty_val_conflicts(self):
        """空字串在路徑欄的意思是「沒寫」，跟 append／mkdir 兜不起來。"""
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": ""}},
                 "OptionConflict")

    def test_extra_key_beside_opt_and_val(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": "x", "$mode": 1}},
                 "DirectiveKeyCountInvalid")

    def test_val_type_is_checked_per_position(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": 3}},
                 "FieldTypeMismatch")


class TestOptRun(ExecCase):
    """真的跑：每個選項的行為。"""

    def test_stdout_append_keeps_previous_runs(self):
        self.inst({"argv": ["sh", "-c", "echo 又一次"],
                   "stdout": {"$opt": "append", "$val": "log.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("log.txt"), "又一次\n又一次\n")

    def test_stdout_mkdir_creates_nested_parent(self):
        self.inst({"argv": ["sh", "-c", "echo 深"],
                   "stdout": {"$opt": "mkdir", "$val": "a/b/c/out.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("a/b/c/out.txt"), "深\n")

    def test_stdout_without_mkdir_still_fails_on_missing_parent(self):
        """沒開 mkdir 就照舊：父目錄不在＝重導向開不起來＝125。"""
        self.inst({"argv": ["sh", "-c", "echo 深"], "stdout": "a/b/out.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("開不起來", r.stderr)

    def test_stderr_append_and_mkdir(self):
        self.inst({"argv": ["sh", "-c", "echo e >&2"],
                   "stderr": {"$opt": ["append", "mkdir"], "$val": "logs/err.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("logs/err.txt"), "e\ne\n")

    def test_exit_append_writes_one_line_per_run(self):
        self.inst({"argv": ["sh", "-c", "exit 3"],
                   "exit": {"$opt": "append", "$val": "codes.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 3)
        self.assertEqual(self.aos(self.d).returncode, 3)
        self.assertEqual(self.read("codes.txt"), "3\n3\n")

    def test_exit_without_append_is_truncated(self):
        self.write("code.txt", "舊的\n")
        self.inst({"argv": ["sh", "-c", "exit 4"], "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 4)
        self.assertEqual(self.read("code.txt"), "4\n")

    def test_exit_mkdir_creates_parent(self):
        self.inst({"argv": ["sh", "-c", "exit 5"],
                   "exit": {"$opt": "mkdir", "$val": "run/1/code.txt"}})
        self.assertEqual(self.aos(self.d).returncode, 5)
        self.assertEqual(self.read("run/1/code.txt"), "5\n")

    def test_exit_without_mkdir_still_fails_on_missing_parent(self):
        self.inst({"argv": ["true"], "exit": "run/1/code.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("父目錄不存在", r.stderr)

    def test_cwd_mkdir_creates_it_and_relative_paths_follow(self):
        """cwd 先建、再當其他相對路徑的中心：stdout 落在新建的 cwd 裡。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": {"$opt": "mkdir", "$val": "work/x"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("work/x/out.txt"), os.path.join(self.d, "work", "x") + "\n")

    def test_cwd_without_mkdir_still_fails(self):
        self.inst({"argv": ["true"], "cwd": "work/x"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("cwd 不是資料夾", r.stderr)

    def test_mkdir_failure_is_aos_failure(self):
        """makedirs 做不到（路徑中間卡一個普通檔）＝aos-exec 自己失敗，125。"""
        self.write("blocker", "我是檔案不是資料夾")
        self.inst({"argv": ["true"], "stdout": {"$opt": "mkdir", "$val": "blocker/out.txt"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("mkdir", r.stderr)

    def test_stdin_inherit_reads_aos_exec_stdin(self):
        self.inst({"argv": ["cat"], "stdin": {"$opt": "inherit"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, stdin="從外面餵的\n").returncode, 0)
        self.assertEqual(self.read("out.txt"), "從外面餵的\n")

    def test_stdout_inherit_shows_on_aos_exec_stdout(self):
        self.inst({"argv": ["sh", "-c", "echo 直接印"], "stdout": {"$opt": "inherit"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "直接印\n")

    def test_stderr_inherit_shows_on_aos_exec_stderr(self):
        self.inst({"argv": ["sh", "-c", "echo 錯誤 >&2"], "stderr": {"$opt": "inherit"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "錯誤\n")

    def test_merge_follows_stdout_append(self):
        """merge 照 stdout 的設定走：stdout 是 append，兩條就一起接在檔尾。"""
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"],
                   "stdout": {"$opt": "append", "$val": "both.txt"},
                   "stderr": {"$opt": "merge"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("both.txt"), "o\ne\no\ne\n")

    def test_merge_follows_stdout_inherit(self):
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"],
                   "stdout": {"$opt": "inherit"}, "stderr": {"$opt": "merge"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "o\ne\n")
        self.assertEqual(r.stderr, "")

    def test_cli_stderr_flag_overrides_inst_stderr_options(self):
        """--stderr - 蓋過 inst.json 的 stderr 設定，包括 merge／append。"""
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"], "stdout": "o.txt",
                   "stderr": {"$opt": ["append", "mkdir"], "$val": "never/e.txt"}})
        r = self.aos(self.d, "--stderr", "-")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "e\n")
        self.assertEqual(self.read("o.txt"), "o\n")
        self.assertFalse(self.exists("never"))          # mkdir 也一起被蓋掉，不建

    def test_envs_clear_with_val(self):
        self.inst({"argv": ["sh", "-c", "echo \"[$HOME][$ONLY]\""],
                   "envs": {"$opt": "clear", "$val": {"ONLY": "只有我"}},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[][只有我]\n")


if __name__ == "__main__":
    unittest.main()
