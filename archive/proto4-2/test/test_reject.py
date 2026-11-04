"""拒絕表（凍結分支 SPEC §C-6）每一條都要有看得懂的錯誤字串。

拒絕＝last.json 多一個 `error`（開頭是代號）、這次不跑、cpu 照活。
"""
import shutil
import unittest

from _util import mkinst, mktmp
import aos_cpu


class RejectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-rej-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rejected(self, code, inst, files=None):
        """跑一次，斷言被拒、代號對得上、而且真的沒跑。"""
        d = mkinst(self.tmp, inst, files)
        res = aos_cpu.run_once(d, 1)
        self.assertIn("error", res, "這筆居然跑起來了：%r" % (inst,))
        self.assertTrue(res["error"].startswith(code + ":"),
                        "要 %s，拿到 %s" % (code, res["error"]))
        self.assertIsNone(res["exit"])
        self.assertIsNone(res["signal"])
        return res["error"]

    def test_json_syntax(self):
        self.rejected("JsonSyntax", '{"argv": ["echo"')

    def test_not_an_object(self):
        self.rejected("NotAnObject", "[1, 2, 3]")
        self.rejected("NotAnObject", '"我是字串"')

    def test_unknown_key_is_rejected_not_ignored(self):
        e = self.rejected("UnknownKey", {"argv": ["echo"], "stdou": "o.txt"})
        self.assertIn("stdou", e)                       # 拼錯的欄位要指名道姓
        self.rejected("UnknownKey", {"argv": ["echo"], "parallel": True})   # 這版沒有 parallel
        self.rejected("UnknownKey", {"argv": ["echo"], "id": "a"})          # 也沒有 id

    def test_empty_argv(self):
        self.rejected("EmptyArgv", {"env": {"A": "b"}})          # 根本沒寫 argv
        self.rejected("EmptyArgv", {"argv": []})
        self.rejected("EmptyArgv", {"argv": [""]})

    def test_field_type_mismatch(self):
        self.rejected("FieldTypeMismatch", {"argv": "echo"})              # argv 不是陣列
        self.rejected("FieldTypeMismatch", {"argv": ["echo", 7]})         # 引數不是字串
        self.rejected("FieldTypeMismatch", {"argv": ["echo"], "env": ["A"]})
        self.rejected("FieldTypeMismatch", {"argv": ["echo"], "env": {"A": 7}})
        self.rejected("FieldTypeMismatch", {"argv": ["echo"], "stdout": 7})
        self.rejected("FieldTypeMismatch", {"argv": ["echo"], "timeout_ms": "300"})
        self.rejected("FieldTypeMismatch", {"argv": ["echo"], "timeout_ms": -1})
        self.rejected("FieldTypeMismatch",                                # timeout_ms 不吃指示詞
                      {"argv": ["echo"], "timeout_ms": {"$env": "HOME"}})

    def test_env_key_invalid(self):
        self.rejected("EnvKeyInvalid", {"argv": ["echo"], "env": {"": "x"}})
        self.rejected("EnvKeyInvalid", {"argv": ["echo"], "env": {"A=B": "x"}})

    def test_directive_key_count(self):
        self.rejected("DirectiveKeyCountInvalid",
                      {"argv": ["echo", {"$env": "HOME", "$ref": "v.json"}]})
        self.rejected("DirectiveKeyCountInvalid", {"argv": ["echo", {}]})

    def test_unknown_directive(self):
        self.rejected("UnknownDirective", {"argv": ["echo", {"$foo": "x"}]})
        e = self.rejected("UnknownDirective",           # $opt 只有 stderr 能用
                          {"argv": ["echo"], "stdout": {"$opt": "merge"}})
        self.assertIn("stderr", e)

    def test_directive_value_type(self):
        self.rejected("DirectiveValueTypeMismatch", {"argv": ["echo", {"$env": 7}]})
        self.rejected("DirectiveValueTypeMismatch",
                      {"argv": ["echo"], "stderr": {"$opt": ["merge"]}})

    def test_unknown_option(self):
        self.rejected("UnknownOption", {"argv": ["echo"], "stderr": {"$opt": "append"}})

    def test_missing_inst_file(self):
        d = mkinst(self.tmp, {"argv": ["echo"]})
        res = aos_cpu.run_once(d, 1, "沒有這份/inst.json")
        self.assertTrue(res["error"].startswith("ReadFailed:"), res["error"])


if __name__ == "__main__":
    unittest.main()
