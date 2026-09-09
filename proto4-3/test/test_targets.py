"""三種目標（普通檔案／.json／資料夾）、--dir-target，還有找不到東西的退出碼 2。"""
import os
import stat
import unittest

from _util import EXEC, ExecCase


class TestTargets(ExecCase):

    def test_plain_file_runs_and_inherits_stdio(self):
        """普通檔案＝最陽春的指令集：直接跑，三條串流繼承 aos-exec 的。"""
        p = self.write("hello.sh", "#!/bin/sh\nread x\necho \"out:$x $PWD\"\necho err >&2\n",
                       executable=True)
        r = self.aos(p, stdin="fed\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "out:fed %s\n" % self.d)   # cwd＝它所在的資料夾
        self.assertEqual(r.stderr, "err\n")

    def test_plain_file_not_executable_is_126(self):
        p = self.write("noexec.sh", "#!/bin/sh\necho hi\n")
        r = self.aos(p)
        self.assertEqual(r.returncode, 126)
        self.assertIn("aos-exec:", r.stderr)

    def test_json_file_is_parsed_as_inst(self):
        """.json 檔＝當 inst.json 讀；cwd 預設是那個 .json 所在的資料夾。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"}, "one.json")
        r = self.aos(os.path.join(self.d, "one.json"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), self.d + "\n")

    def test_json_in_subdir_uses_that_subdir(self):
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"}, "sub/two.json")
        r = self.aos(os.path.join(self.d, "sub", "two.json"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_dir_uses_default_dir_target(self):
        """資料夾＝跑 xxx/.aos/inst.json，cwd 預設是 xxx 自己。"""
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), self.d + "\n")

    def test_dir_target_flag(self):
        self.inst({"argv": ["sh", "-c", "echo other"], "stdout": "out.txt"},
                  "other/place.json")
        r = self.aos(self.d, "--dir-target", "other/place.json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read("out.txt"), "other\n")     # cwd 還是 xxx，不是 other/

    def test_missing_xxx_is_2(self):
        r = self.aos(os.path.join(self.d, "nope"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("找不到", r.stderr)

    def test_missing_dir_target_is_2(self):
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 2)
        self.assertIn(".aos/inst.json", r.stderr)

    def test_bad_flag_is_2(self):
        r = self.aos(self.d, "--no-such-flag")
        self.assertEqual(r.returncode, 2)

    def test_no_args_is_2(self):
        self.assertEqual(self.aos().returncode, 2)

    def test_negative_timeout_is_2(self):
        self.inst({"argv": ["true"]})
        self.assertEqual(self.aos(self.d, "--timeout-ms", "-1").returncode, 2)

    def test_entry_script_is_executable(self):
        """aos-exec 本身要能直接執行（有 +x、有 shebang）。"""
        self.assertTrue(os.stat(EXEC).st_mode & stat.S_IXUSR)
        with open(EXEC, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("#!"))


if __name__ == "__main__":
    unittest.main()
