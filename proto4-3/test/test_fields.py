"""七個欄位各一條、串流沒寫＝/dev/null、exit 檔的內容，還有相對路徑以誰為中心。"""
import os
import unittest

from _util import ExecCase


class TestFields(ExecCase):

    def test_argv_only(self):
        """只有 argv：三條串流都是 /dev/null，什麼都不留下。"""
        self.inst({"argv": ["sh", "-c", "echo out; echo err >&2"]})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")          # 沒寫＝/dev/null，不是繼承
        self.assertEqual(r.stderr, "")

    def test_stdin_default_is_devnull(self):
        """沒寫 stdin＝子行程一讀就 EOF，餵給 aos-exec 的東西不會流下去。"""
        self.inst({"argv": ["sh", "-c", "cat"], "stdout": "out.txt"})
        r = self.aos(self.d, stdin="這行不該被讀到\n")
        self.assertEqual(r.returncode, 0)
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
        self.inst({"argv": ["sh", "-c", "echo o; echo e >&2"],
                   "stdout": "o.txt", "stderr": "e.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("o.txt"), "o\n")
        self.assertEqual(self.read("e.txt"), "e\n")

    def test_stderr_merge(self):
        """{"$opt":"merge"}＝兩條走同一個 open file description，交錯不會互相蓋掉。"""
        self.inst({"argv": ["sh", "-c", "echo one; echo two >&2; echo three"],
                   "stdout": "both.txt", "stderr": {"$opt": "merge"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("both.txt"), "one\ntwo\nthree\n")

    def test_stderr_merge_without_stdout_goes_to_devnull(self):
        self.inst({"argv": ["sh", "-c", "echo e >&2"], "stderr": {"$opt": "merge"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")

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

    def test_cwd_field(self):
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        # stdout 的相對路徑以**解析完的 cwd**為中心，所以檔案落在 sub/ 裡
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")
        self.assertFalse(self.exists("out.txt"))

    def test_exit_relative_to_cwd(self):
        self.write("sub/.keep", "")
        self.inst({"argv": ["true"], "cwd": "sub", "exit": "code.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/code.txt"), "0\n")

    def test_absolute_paths_are_literal(self):
        out = os.path.join(self.d, "abs.txt")
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "echo abs"], "cwd": "sub", "stdout": out})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("abs.txt"), "abs\n")

    def test_cwd_itself_is_relative_to_xxx_not_to_the_json(self):
        """`cwd` 自己的相對路徑從 `xxx` 起算——inst.json 埋在 deep/ 裡也一樣。"""
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": "sub", "stdout": "out.txt"},
                  "deep/inst.json")
        r = self.aos(self.d, "--dir-target", "deep/inst.json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_envs_field(self):
        self.inst({"argv": ["sh", "-c", "echo $GREET"], "envs": {"GREET": "hi"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "hi\n")


if __name__ == "__main__":
    unittest.main()
