"""格式壞掉一律退出碼 125（aos-exec 自己失敗），原因印一行 `aos-exec: <代號>: <白話>`。"""
import os
import unittest

from _util import ExecCase


class TestReject(ExecCase):

    def bad(self, obj, code):
        self.inst(obj)
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-exec: %s: " % code), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_not_json(self):
        self.bad("{這不是 JSON", "JsonSyntax")

    def test_not_an_object(self):
        self.bad("[\"argv\"]", "NotAnObject")

    def test_missing_argv(self):
        self.bad({"stdout": "out.txt"}, "EmptyArgv")

    def test_empty_argv(self):
        self.bad({"argv": []}, "EmptyArgv")

    def test_empty_argv0(self):
        self.bad({"argv": [""]}, "EmptyArgv")

    def test_argv_not_a_list(self):
        self.bad({"argv": "true"}, "FieldTypeMismatch")

    def test_argv_element_is_a_number(self):
        self.bad({"argv": ["echo", 3]}, "FieldTypeMismatch")

    def test_stdout_is_a_number(self):
        self.bad({"argv": ["true"], "stdout": 3}, "FieldTypeMismatch")

    def test_env_not_an_object(self):
        self.bad({"argv": ["true"], "envs": ["A=1"]}, "FieldTypeMismatch")

    def test_env_value_is_a_number(self):
        self.bad({"argv": ["true"], "envs": {"A": 1}}, "FieldTypeMismatch")

    def test_env_key_with_equals(self):
        self.bad({"argv": ["true"], "envs": {"A=B": "x"}}, "EnvKeyInvalid")

    def test_env_key_empty(self):
        self.bad({"argv": ["true"], "envs": {"": "x"}}, "EnvKeyInvalid")

    def test_envs_clear_val_not_an_object(self):
        self.bad({"argv": ["true"], "envs": {"$opt": "clear", "$val": "x"}},
                 "FieldTypeMismatch")

    def test_env_unknown_option(self):
        self.bad({"argv": ["true"], "envs": {"$opt": "merge"}}, "UnknownOption")

    def test_unknown_directive(self):
        """有 $ 開頭的 key、但 $opt／$ref／$fmt／$env 一個都不是＝不認得的指示詞。"""
        self.bad({"argv": ["true"], "envs": {"A": {"$nope": "x"}}}, "UnknownDirective")
        self.bad({"argv": ["true"], "envs": {"A": {"$xyz": 1, "plain": "x"}}}, "UnknownDirective")

    def test_directive_value_not_a_string(self):
        self.bad({"argv": ["true"], "envs": {"A": {"$env": 3}}},
                 "DirectiveValueTypeMismatch")

    def test_opt_merge_only_on_stderr(self):
        """選項名是看位置的：stdout 沒有 merge 這個選項。"""
        self.bad({"argv": ["true"], "stdout": {"$opt": "merge"}}, "UnknownOption")

    def test_stderr_unknown_option(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": "split"}}, "UnknownOption")

    def test_metainfo_not_an_object(self):
        self.bad({"argv": ["true"], "_metainfo": "posix"}, "MetainfoInvalid")

    def test_metainfo_missing_version(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix"}}, "MetainfoInvalid")

    def test_metainfo_type_wrong(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "windows", "_version": 1}},
                 "UnsupportedInstType")

    def test_metainfo_version_2(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix", "_version": 2}},
                 "UnsupportedInstVersion")

    def test_metainfo_version_true_is_not_an_int(self):
        """`_version` 要 int；JSON 的 true／false 是 bool，不算數。"""
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix", "_version": True}},
                 "UnsupportedInstVersion")

    def test_dir_named_dot_json_is_still_a_dir(self):
        """名字剛好以 .json 結尾的**資料夾**還是照資料夾走（先看是不是資料夾）。"""
        self.write("weird.json/inside.txt", "")
        r = self.aos(self.d + "/weird.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn(".aos/inst.json", r.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root 讀得到任何檔")
    def test_unreadable_inst_json_is_125(self):
        p = self.inst({"argv": ["true"]}, "locked.json")
        os.chmod(p, 0)
        r = self.aos(p)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReadFailed", r.stderr)

if __name__ == "__main__":
    unittest.main()
