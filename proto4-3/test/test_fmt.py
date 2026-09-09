"""$fmt：接字串用的指示詞。寫法沿用 repo 既有那套，這裡只有 ${env:NAME} 一個變數。"""
import os
import unittest

from _util import ExecCase

OUTER = dict(os.environ, AOSTEST_OUTER="外面來的", AOSTEST_EMPTY="")


class TestFmt(ExecCase):

    def test_appends_to_an_inherited_variable(self):
        """使用者的例子：把 /opt/bin 接在繼承來的 PATH 後面，子行程真的看得到。"""
        self.inst({"argv": ["sh", "-c", "echo $PATH"], "stdout": "out.txt",
                   "envs": {"PATH": {"$fmt": "${env:PATH}:/opt/bin"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), OUTER["PATH"] + ":/opt/bin\n")

    def test_reads_aos_exec_env_not_the_insts_envs(self):
        """讀的是 aos-exec 自己的環境，不是同一份 inst.json 的 envs。"""
        self.inst({"argv": ["sh", "-c", "echo $B"], "stdout": "out.txt",
                   "envs": {"AOSTEST_OUTER": "被蓋掉的",
                            "B": {"$fmt": "[${env:AOSTEST_OUTER}]"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[外面來的]\n")

    def test_bare_dollar_and_dollar_name_are_literal(self):
        """只有 ${…} 會展開：單獨的 $ 與 $NAME 都是字面，不用跳脫。"""
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": {"$fmt": "a$b $PATH $ ${env:AOSTEST_OUTER}"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "a$b $PATH $ 外面來的\n")

    def test_expanded_once_not_rescanned(self):
        """換進來的值裡再出現 ${…} 就是字面，不會再展開一輪。"""
        env = dict(OUTER, AOSTEST_NEST="${env:AOSTEST_OUTER}")
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": {"$fmt": "<${env:AOSTEST_NEST}>"}}})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("out.txt"), "<${env:AOSTEST_OUTER}>\n")

    def test_empty_variable_is_empty_string(self):
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": {"$fmt": "[${env:AOSTEST_EMPTY}]"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[]\n")

    def test_missing_variable_is_125(self):
        self.inst({"argv": ["true"], "envs": {"X": {"$fmt": "${env:AOSTEST_NOPE}"}}})
        r = self.aos(self.d, env=OUTER)
        self.assertEqual(r.returncode, 125)
        self.assertIn("EnvironmentVariableMissing", r.stderr)

    def test_unknown_variable_is_125(self):
        """不是 env: 開頭的 ${…}＝不認得，不猜（這一版沒有 tabledb 那些路徑變數）。"""
        self.inst({"argv": ["true"], "envs": {"X": {"$fmt": "${gitRoot}/x"}}})
        r = self.aos(self.d, env=OUTER)
        self.assertEqual(r.returncode, 125)
        self.assertIn("UnknownFormatVariable", r.stderr)

    def test_fmt_in_argv(self):
        self.inst({"argv": ["echo", {"$fmt": "hi ${env:AOSTEST_OUTER}"}],
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "hi 外面來的\n")

    def test_fmt_in_a_path_field(self):
        env = dict(OUTER, AOSTEST_NAME="named")
        self.inst({"argv": ["echo", "x"], "stdout": {"$fmt": "${env:AOSTEST_NAME}.txt"}})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("named.txt"), "x\n")

    def test_fmt_in_cwd(self):
        env = dict(OUTER, AOSTEST_SUB="sub")
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt",
                   "cwd": {"$fmt": "${env:AOSTEST_SUB}"}})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_ref_returning_a_fmt_object_keeps_resolving(self):
        self.write("vals.json", '{"v": {"$fmt": "取自 ${env:AOSTEST_OUTER}"}}')
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": {"$ref": "vals.json#/v"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "取自 外面來的\n")

    def test_fmt_value_must_be_a_string(self):
        self.inst({"argv": ["true"], "envs": {"X": {"$fmt": 3}}})
        r = self.aos(self.d, env=OUTER)
        self.assertEqual(r.returncode, 125)
        self.assertIn("DirectiveValueTypeMismatch", r.stderr)


if __name__ == "__main__":
    unittest.main()
