"""$fmt：接字串用的指示詞。值是物件：$val 是模板、其餘 key 是本地變數表，${name} 只查那張表。"""
import os
import unittest

from _util import ExecCase

OUTER = dict(os.environ, AOSTEST_OUTER="外面來的", AOSTEST_EMPTY="")


def fmt(template, **variables):
    """寫測試用的縮寫：fmt("${p}:/x", p={"$env": "PATH"}) → 完整的 $fmt 物件。"""
    return {"$fmt": dict({"$val": template}, **variables)}


class TestFmt(ExecCase):

    def bad(self, obj, code, env=OUTER):
        self.inst(obj)
        r = self.aos(self.d, env=env)
        self.assertEqual(r.returncode, 125, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-exec: %s: " % code), r.stderr)
        return r

    def test_appends_to_an_inherited_variable(self):
        """使用者的例子：把 /opt/bin 接在繼承來的 PATH 後面，子行程真的看得到。"""
        self.inst({"argv": ["sh", "-c", "echo $PATH"], "stdout": "out.txt",
                   "envs": {"PATH": fmt("${p}:/opt/bin", p={"$env": "PATH"})}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), OUTER["PATH"] + ":/opt/bin\n")

    def test_env_variable_reads_aos_exec_env_not_the_insts_envs(self):
        """變數是 $env 的話讀的是 aos-exec 自己的環境，不是同一份 inst.json 的 envs。"""
        self.inst({"argv": ["sh", "-c", "echo $B"], "stdout": "out.txt",
                   "envs": {"AOSTEST_OUTER": "被蓋掉的",
                            "B": fmt("[${o}]", o={"$env": "AOSTEST_OUTER"})}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[外面來的]\n")

    def test_literal_variable_and_two_variables(self):
        """使用者的例子：一個變數是 $env、一個是字面。"""
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("aaa${xxx}, bbb${zzz}", xxx={"$env": "AOSTEST_OUTER"},
                                     zzz="haha")}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "aaa外面來的, bbbhaha\n")

    def test_bare_dollar_and_dollar_name_are_literal(self):
        """只有 ${…} 會展開：單獨的 $ 與 $NAME 都是字面，不用跳脫。"""
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("a$b $PATH $ ${o}", o={"$env": "AOSTEST_OUTER"})}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "a$b $PATH $ 外面來的\n")

    def test_expanded_once_not_rescanned(self):
        """變數值裡再出現 ${…} 就是字面，不會再展開一輪。"""
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("<${n}>", n="${o}", o="不該被用到")}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "<${o}>\n")

    def test_unused_variable_is_fine(self):
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("只用 ${a}", a="a", b="沒人用")}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "只用 a\n")

    def test_empty_env_variable_is_empty_string(self):
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("[${e}]", e={"$env": "AOSTEST_EMPTY"})}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[]\n")

    def test_missing_env_variable_is_125(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("${n}", n={"$env": "AOSTEST_NOPE"})}},
                 "EnvironmentVariableMissing")

    def test_variable_not_in_table_is_125(self):
        """模板裡的 ${name} 只查本地表：沒定義＝UnknownFormatVariable，不猜。"""
        self.bad({"argv": ["true"], "envs": {"X": fmt("${nope}/x", a="1")}},
                 "UnknownFormatVariable")

    def test_env_namespace_is_gone(self):
        """舊的 ${env:NAME} 沒有特例了：env:PATH 就只是一個沒定義的變數名。"""
        self.bad({"argv": ["true"], "envs": {"X": fmt("${env:PATH}:/opt/bin")}},
                 "UnknownFormatVariable")

    def test_string_form_is_rejected(self):
        """舊的字串寫法 {"$fmt": "…"} 不再認得。"""
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": "${env:PATH}:/opt/bin"}}},
                 "DirectiveValueTypeMismatch")

    def test_fmt_value_not_an_object(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": 3}}}, "DirectiveValueTypeMismatch")

    def test_missing_val_is_125(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": {"a": "1"}}}},
                 "DirectiveValueTypeMismatch")

    def test_val_resolving_to_non_string_is_125(self):
        self.write("vals.json", '{"t": ["不是字串"]}')
        self.bad({"argv": ["true"], "envs": {"X": fmt({"$ref": "vals.json#/t"})}},
                 "DirectiveValueTypeMismatch")

    def test_variable_resolving_to_non_string_is_125(self):
        """變數是 $ref 拿到一個物件＝解完不是字串。"""
        self.write("vals.json", '{"o": {"k": "v"}}')
        self.bad({"argv": ["true"], "envs": {"X": fmt("${a}", a={"$ref": "vals.json#/o"})}},
                 "DirectiveValueTypeMismatch")

    def test_variable_literal_non_string_is_125(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("${a}", a=3)}},
                 "DirectiveValueTypeMismatch")

    def test_bad_variable_names(self):
        """變數名不能 $ 開頭、不能空、不能含大括號。"""
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"$x": "1"})}},
                 "FormatVariableInvalid")
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"": "1"})}},
                 "FormatVariableInvalid")
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"a{b": "1"})}},
                 "FormatVariableInvalid")

    def test_val_can_be_a_directive(self):
        """模板自己也能是指示詞：從別的檔 $ref 一個模板進來。"""
        self.write("vals.json", '{"t": "模板來自 ${who}"}')
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt({"$ref": "vals.json#/t"}, who="別的檔")}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "模板來自 別的檔\n")

    def test_variable_can_be_a_ref(self):
        """$ref 的相對路徑跟 $fmt 用同一個中心（cwd）。"""
        self.write("vals.json", '{"w": "從檔案來的"}')
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("[${w}]", w={"$ref": "vals.json#/w"})}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[從檔案來的]\n")

    def test_variable_can_be_a_nested_fmt(self):
        """變數值再是 $fmt：內層先展開成字串，外層當字面接進去（不再掃）。"""
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": fmt("<${inner}>",
                                     inner=fmt("${o}!", o={"$env": "AOSTEST_OUTER"}))}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "<外面來的!>\n")

    def test_fmt_in_argv(self):
        self.inst({"argv": ["echo", fmt("hi ${o}", o={"$env": "AOSTEST_OUTER"})],
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "hi 外面來的\n")

    def test_fmt_in_a_path_field(self):
        env = dict(OUTER, AOSTEST_NAME="named")
        self.inst({"argv": ["echo", "x"],
                   "stdout": fmt("${n}.txt", n={"$env": "AOSTEST_NAME"})})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("named.txt"), "x\n")

    def test_fmt_in_cwd(self):
        env = dict(OUTER, AOSTEST_SUB="sub")
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "stdout": "out.txt",
                   "cwd": fmt("${s}", s={"$env": "AOSTEST_SUB"})})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_ref_returning_a_fmt_object_keeps_resolving(self):
        self.write("vals.json",
                   '{"v": {"$fmt": {"$val": "取自 ${o}", "o": {"$env": "AOSTEST_OUTER"}}}}')
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt",
                   "envs": {"X": {"$ref": "vals.json#/v"}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "取自 外面來的\n")

    def test_fmt_at_an_object_position_is_field_type_mismatch(self):
        """$fmt 解出來一定是字串，放在 envs 這種要物件的位置就是型別錯。"""
        self.bad({"argv": ["true"], "envs": fmt("x")}, "FieldTypeMismatch")


if __name__ == "__main__":
    unittest.main()
