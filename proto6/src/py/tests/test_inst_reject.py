"""aos_inst.load()：讀、驗、解——照 spec/inst-posix/。全部在這個進程裡跑，不開子進程。

本檔：拒絕的代號（TestReject）。

分幾群：七個欄位與預設值、_metainfo、選項物件的形狀、$ref／$at、$fmt、$env、拒絕的代號、
指示詞優先序。案例大多從 proto4-3 的 test_fields／test_opts／test_ref／test_fmt／test_env／
test_reject 搬來改成直接驗 load() 的結果。
"""
import os
import unittest

from _util import InstCase

import aos_inst
from aos_inst import InstError


# ---------------------------------------------------------------- 拒絕 ----
class TestReject(InstCase):

    def test_read_failed(self):
        with self.assertRaises(InstError) as cm:
            aos_inst.load(os.path.join(self.d, "nope.json"), self.d)
        self.assertEqual(cm.exception.code, "ReadFailed")

    def test_not_json(self):
        self.bad("{這不是 JSON", "JsonSyntax")

    def test_not_an_object(self):
        self.bad('["argv"]', "NotAnObject")
        self.bad('"字串"', "NotAnObject")
        self.bad("null", "NotAnObject")

    def test_missing_argv(self):
        self.bad({"stdout": "out.txt"}, "EmptyArgv")

    def test_empty_argv(self):
        self.bad({"argv": []}, "EmptyArgv")
        self.write("a.json", '{"argv": []}')
        self.bad({"argv": {"$ref": "a.json#/argv"}}, "EmptyArgv")

    def test_empty_argv0(self):
        self.bad({"argv": [""]}, "EmptyArgv")
        self.bad({"argv": ["", "x"]}, "EmptyArgv")

    def test_argv_not_a_list(self):
        self.bad({"argv": "true"}, "FieldTypeMismatch")
        self.bad({"argv": {"a": 1}}, "FieldTypeMismatch")

    def test_argv_element_not_a_string(self):
        self.bad({"argv": ["echo", 3]}, "FieldTypeMismatch")
        self.bad({"argv": ["echo", None]}, "FieldTypeMismatch")
        self.bad({"argv": ["echo", ["x"]]}, "FieldTypeMismatch")

    def test_path_field_not_a_string(self):
        for name in ("stdin", "stdout", "stderr", "exit", "cwd"):
            self.bad({"argv": ["true"], name: 3}, "FieldTypeMismatch")
            self.bad({"argv": ["true"], name: ["x"]}, "FieldTypeMismatch")

    def test_envs_not_an_object(self):
        self.bad({"argv": ["true"], "envs": ["A=1"]}, "FieldTypeMismatch")
        self.bad({"argv": ["true"], "envs": "A=1"}, "FieldTypeMismatch")

    def test_envs_value_not_a_string(self):
        self.bad({"argv": ["true"], "envs": {"A": 1}}, "FieldTypeMismatch")
        self.bad({"argv": ["true"], "envs": {"A": {"k": "v"}}}, "FieldTypeMismatch")

    def test_env_key_invalid(self):
        self.bad({"argv": ["true"], "envs": {"A=B": "x"}}, "EnvKeyInvalid")
        self.bad({"argv": ["true"], "envs": {"": "x"}}, "EnvKeyInvalid")

    def test_env_key_invalid_inside_clear_val(self):
        self.bad({"argv": ["true"], "envs": {"$opt": "clear", "$val": {"A=B": "x"}}}, "EnvKeyInvalid")

    def test_unknown_directive(self):
        self.bad({"argv": ["true"], "envs": {"A": {"$nope": "x"}}}, "UnknownDirective")
        self.bad({"argv": ["true"], "envs": {"A": {"$xyz": 1, "plain": "x"}}}, "UnknownDirective")
        self.bad({"argv": ["true"], "envs": {"$xyz": "x"}}, "UnknownDirective")

    def test_metainfo_checked_after_top_level_ref(self):
        """頂層從別的檔拿，_metainfo 也是那份檔的。"""
        self.write("b.json", '{"_metainfo": {"_type": "posix", "_version": 9}, "argv": ["true"]}')
        self.bad({"$ref": "b.json"}, "UnsupportedInstVersion")


if __name__ == "__main__":
    unittest.main()
