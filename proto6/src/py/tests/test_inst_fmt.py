"""aos_inst.load()：讀、驗、解——照 spec/inst-posix/。全部在這個進程裡跑，不開子進程。

本檔：$fmt、$env、指示詞優先序（TestFmt、TestEnvDirective、TestDirectivePrecedence）。

分幾群：七個欄位與預設值、_metainfo、選項物件的形狀、$ref／$at、$fmt、$env、拒絕的代號、
指示詞優先序。案例大多從 proto4-3 的 test_fields／test_opts／test_ref／test_fmt／test_env／
test_reject 搬來改成直接驗 load() 的結果。
"""
import os
import unittest

from _util import OUTER, InstCase, fmt

import aos_inst


# ---------------------------------------------------------------- $fmt ----
class TestFmt(InstCase):

    def env_x(self, value, env=None):
        return self.load({"argv": ["true"], "envs": {"X": value}}, env=env)["envs"]["X"]

    def test_appends_to_an_inherited_variable(self):
        self.assertEqual(self.env_x(fmt("${p}:/opt/bin", p={"$env": "PATH"})), OUTER["PATH"] + ":/opt/bin")

    def test_env_reads_executor_env_not_the_insts_envs(self):
        r = self.load({"argv": ["true"], "envs": {"AOSTEST_OUTER": "被蓋掉的",
                                                   "B": fmt("[${o}]", o={"$env": "AOSTEST_OUTER"})}})
        self.assertEqual(r["envs"]["B"], "[外面來的]")

    def test_literal_variable_and_two_variables(self):
        self.assertEqual(self.env_x(fmt("aaa${xxx}, bbb${zzz}", xxx={"$env": "AOSTEST_OUTER"}, zzz="haha")),
                         "aaa外面來的, bbbhaha")

    def test_bare_dollar_and_dollar_name_are_literal(self):
        self.assertEqual(self.env_x(fmt("a$b $PATH $ ${o}", o={"$env": "AOSTEST_OUTER"})), "a$b $PATH $ 外面來的")

    def test_expanded_once_not_rescanned(self):
        self.assertEqual(self.env_x(fmt("<${n}>", n="${o}", o="不該被用到")), "<${o}>")

    def test_unused_variable_is_fine(self):
        self.assertEqual(self.env_x(fmt("只用 ${a}", a="a", b="沒人用")), "只用 a")

    def test_empty_env_variable_is_empty_string(self):
        self.assertEqual(self.env_x(fmt("[${e}]", e={"$env": "AOSTEST_EMPTY"})), "[]")

    def test_missing_env_variable(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("${n}", n={"$env": "AOSTEST_NOPE"})}},
                 "EnvironmentVariableMissing")

    def test_variable_not_in_table(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("${nope}/x", a="1")}}, "UnknownFormatVariable")

    def test_env_namespace_is_gone(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("${env:PATH}:/opt/bin")}}, "UnknownFormatVariable")

    def test_string_form_is_rejected(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": "${env:PATH}"}}}, "DirectiveValueTypeMismatch")

    def test_fmt_value_not_an_object(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": 3}}}, "DirectiveValueTypeMismatch")

    def test_missing_val(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$fmt": {"a": "1"}}}}, "DirectiveValueTypeMismatch")

    def test_val_resolving_to_non_string(self):
        self.write("vals.json", '{"t": ["不是字串"]}')
        self.bad({"argv": ["true"], "envs": {"X": fmt({"$ref": "vals.json", "$at": "/t"})}},
                 "DirectiveValueTypeMismatch")

    def test_variable_resolving_to_non_string(self):
        self.write("vals.json", '{"o": {"k": "v"}}')
        self.bad({"argv": ["true"], "envs": {"X": fmt("${a}", a={"$ref": "vals.json", "$at": "/o"})}},
                 "DirectiveValueTypeMismatch")
        self.bad({"argv": ["true"], "envs": {"X": fmt("${a}", a=3)}}, "DirectiveValueTypeMismatch")

    def test_bad_variable_names(self):
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"$x": "1"})}}, "FormatVariableInvalid")
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"": "1"})}}, "FormatVariableInvalid")
        self.bad({"argv": ["true"], "envs": {"X": fmt("x", **{"a{b": "1"})}}, "FormatVariableInvalid")

    def test_val_can_be_a_directive(self):
        self.write("vals.json", '{"t": "模板來自 ${who}"}')
        self.assertEqual(self.env_x(fmt({"$ref": "vals.json", "$at": "/t"}, who="別的檔")), "模板來自 別的檔")

    def test_variable_can_be_a_ref_relative_to_cwd(self):
        self.write("sub/vals.json", '{"w": "從檔案來的"}')
        r = self.load({"argv": ["true"], "cwd": "sub",
                       "envs": {"X": fmt("[${w}]", w={"$ref": "vals.json", "$at": "/w"})}})
        self.assertEqual(r["envs"]["X"], "[從檔案來的]")

    def test_variable_can_be_a_nested_fmt(self):
        self.assertEqual(self.env_x(fmt("<${inner}>", inner=fmt("${o}!", o={"$env": "AOSTEST_OUTER"}))),
                         "<外面來的!>")

    def test_fmt_in_argv_path_and_cwd(self):
        env = dict(OUTER, AOSTEST_NAME="named", AOSTEST_SUB="sub")
        r = self.load({"argv": ["echo", fmt("hi ${o}", o={"$env": "AOSTEST_OUTER"})],
                       "stdout": fmt("${n}.txt", n={"$env": "AOSTEST_NAME"}),
                       "cwd": fmt("${s}", s={"$env": "AOSTEST_SUB"})}, env=env)
        self.assertEqual(r["argv"], ["echo", "hi 外面來的"])
        self.assertEqual(r["cwd"], os.path.join(self.d, "sub"))
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "sub", "named.txt"))

    def test_ref_returning_a_fmt_object_keeps_resolving(self):
        self.write("vals.json", '{"v": {"$fmt": {"$val": "取自 ${o}", "o": {"$env": "AOSTEST_OUTER"}}}}')
        self.assertEqual(self.env_x({"$ref": "vals.json", "$at": "/v"}), "取自 外面來的")


# ---------------------------------------------------------------- $env ----

class TestEnvDirective(InstCase):

    def test_value_can_be_dollar_env(self):
        r = self.load({"argv": ["true"], "envs": {"COPIED": {"$env": "AOSTEST_OUTER"}}})
        self.assertEqual(r["envs"]["COPIED"], "外面來的")

    def test_clear_val_can_use_dollar_env(self):
        r = self.load({"argv": ["true"], "envs": {"$opt": "clear", "$val": {"COPIED": {"$env": "AOSTEST_OUTER"}}}})
        self.assertEqual((r["envs"], r["envs_clear"]), ({"COPIED": "外面來的"}, True))

    def test_missing_variable(self):
        self.bad({"argv": ["true"], "envs": {"X": {"$env": "AOSTEST_NOPE"}}}, "EnvironmentVariableMissing")

    def test_empty_string_is_ok(self):
        self.assertEqual(self.load({"argv": ["true"], "envs": {"X": {"$env": "AOSTEST_EMPTY"}}})["envs"]["X"], "")

    def test_env_not_a_string(self):
        self.bad({"argv": ["true"], "envs": {"A": {"$env": 3}}}, "DirectiveValueTypeMismatch")

    def test_env_in_cwd_and_argv(self):
        env = dict(OUTER, AOSTEST_SUB="sub", AOSTEST_PROG="true")
        r = self.load({"argv": [{"$env": "AOSTEST_PROG"}], "cwd": {"$env": "AOSTEST_SUB"}}, env=env)
        self.assertEqual((r["argv"], r["cwd"]), (["true"], os.path.join(self.d, "sub")))

    def test_default_env_is_os_environ(self):
        """load() 沒給 env 就查 os.environ。"""
        p = self.inst({"argv": ["true"], "envs": {"H": {"$env": "HOME"}}})
        self.assertEqual(aos_inst.load(p, self.d)["envs"]["H"], os.environ["HOME"])


# ---------------------------------------------------------------- 優先序 ----
class TestDirectivePrecedence(InstCase):
    """一個指示詞物件裡好幾個 $ key：只跑優先序最高的（$opt > $ref > $fmt > $env），其餘不看。"""

    def env_x(self, value):
        return self.load({"argv": ["true"], "envs": {"X": value}})["envs"]["X"]

    def test_unknown_keys_beside_a_directive_are_ignored(self):
        self.write("a.json", '"從 a 來的"')
        self.assertEqual(self.env_x({"$ref": "a.json", "_note": "說明", "x": 1}), "從 a 來的")

    def test_ref_beats_fmt(self):
        self.write("a.json", '"從 a 來的"')
        self.assertEqual(self.env_x({"$ref": "a.json", "$fmt": "壞的"}), "從 a 來的")

    def test_fmt_beats_env(self):
        self.assertEqual(self.env_x({"$fmt": {"$val": "fmt 贏"}, "$env": "AOSTEST_NOPE"}), "fmt 贏")

    def test_opt_beats_ref_at_an_option_position(self):
        r = self.load({"argv": ["true"], "stdout": {"$opt": "append", "$val": "f.txt", "$ref": "nope.json"}})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "f.txt"))

    def test_opt_at_a_no_option_position_is_still_unknown_option(self):
        self.write("a.json", '"x"')
        self.bad({"argv": ["true"], "envs": {"X": {"$opt": "clear", "$ref": "a.json"}}}, "UnknownOption")


if __name__ == "__main__":
    unittest.main()
