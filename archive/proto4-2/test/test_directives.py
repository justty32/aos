"""指示詞：`{"$env":"NAME"}`、`{"$ref":"file.json#/pointer"}`、stderr 的 `{"$opt":"merge"}`。

`$env` 讀的是 cpu 自己的環境（測試就是這個行程），`$ref` 相對於**資料夾**讀檔。
"""
import os
import shutil
import unittest

from _util import mkinst, mktmp, read
import aos_cpu


def run(d):
    return aos_cpu.run_once(d, 1)


class DirectiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = mktmp("aos-proto4-2-dir-")
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── $env ──────────────────────────────
    def test_env_directive_in_argv_env_and_path_fields(self):
        os.environ["AOS_T_WORD"] = "喵"
        os.environ["AOS_T_OUT"] = "o.txt"
        d = mkinst(self.tmp, {"argv": ["echo", {"$env": "AOS_T_WORD"}],
                              "stdout": {"$env": "AOS_T_OUT"},
                              "env": {"X": {"$env": "AOS_T_WORD"}}})
        self.assertEqual(run(d)["exit"], 0)
        self.assertEqual(read(d, "o.txt"), "喵\n")

    def test_env_directive_missing_variable_is_error(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$env": "AOS_T_NO_SUCH_VAR"}]})
        res = run(d)
        self.assertTrue(res["error"].startswith("EnvironmentVariableMissing:"), res["error"])
        self.assertIsNone(res["exit"])                       # 這次不跑

    def test_env_directive_empty_variable_is_empty_string(self):
        os.environ["AOS_T_EMPTY"] = ""
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo [$X]"],
                              "env": {"X": {"$env": "AOS_T_EMPTY"}}})
        self.assertEqual(run(d)["stdout"].strip(), "[]")     # 存在但空＝空字串，不是錯誤

    def test_env_directive_empty_argv0_is_empty_argv(self):
        os.environ["AOS_T_EMPTY"] = ""
        d = mkinst(self.tmp, {"argv": [{"$env": "AOS_T_EMPTY"}]})
        self.assertTrue(run(d)["error"].startswith("EmptyArgv:"))

    # ── $ref ──────────────────────────────
    def test_ref_one_level_pointer(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/a/b"}]},
                   {"v.json": '{"a":{"b":"深處"}}'})
        self.assertEqual(run(d)["stdout"].strip(), "深處")

    def test_ref_whole_document_when_no_hash(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json"}]}, {"v.json": '"整份"'})
        self.assertEqual(run(d)["stdout"].strip(), "整份")

    def test_ref_pointer_escapes_and_array_index(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/a~1b/~0k/1"}]},
                   {"v.json": '{"a/b":{"~k":["零","壹"]}}'})
        self.assertEqual(run(d)["stdout"].strip(), "壹")

    def test_ref_nested_ref_and_env(self):
        os.environ["AOS_T_DEEP"] = "從環境來的"
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "a.json#/next"}]},
                   {"a.json": '{"next":{"$ref":"b.json#/last"}}',
                    "b.json": '{"last":{"$env":"AOS_T_DEEP"}}'})
        self.assertEqual(run(d)["stdout"].strip(), "從環境來的")

    def test_ref_same_file_different_pointer_is_not_a_cycle(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/x"}]},
                   {"v.json": '{"x":{"$ref":"v.json#/y"},"y":"到了"}'})
        self.assertEqual(run(d)["stdout"].strip(), "到了")

    def test_ref_cycle_is_error(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "./v.json#/x"}]},
                   {"v.json": '{"x":{"$ref":"v.json#/x"}}'})
        res = run(d)
        self.assertTrue(res["error"].startswith("ReferenceCycle:"), res["error"])
        self.assertIn("#/x", res["error"])                   # 診斷看得到繞回哪一段

    def test_ref_missing_file_and_bad_json_and_bad_pointer(self):
        d1 = mkinst(self.tmp, {"argv": ["echo", {"$ref": "沒有這個檔.json#/x"}]})
        self.assertTrue(run(d1)["error"].startswith("ReferenceReadFailed:"))
        d2 = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/x"}]}, {"v.json": "{壞"})
        self.assertTrue(run(d2)["error"].startswith("ReferenceJsonInvalid:"))
        d3 = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/x"}]}, {"v.json": '{"y":"1"}'})
        self.assertTrue(run(d3)["error"].startswith("ReferencePointerInvalid:"))

    def test_ref_to_array_or_number_is_error(self):
        d = mkinst(self.tmp, {"argv": ["echo", {"$ref": "v.json#/x"}]},
                   {"v.json": '{"x":["不能","展開"]}'})
        self.assertTrue(run(d)["error"].startswith("ReferenceValueInvalid:"))

    # ── $opt ──────────────────────────────
    def test_opt_merge_through_ref_is_allowed_at_stderr(self):
        d = mkinst(self.tmp, {"argv": ["sh", "-c", "echo 出; echo 錯 >&2"],
                              "stderr": {"$ref": "v.json#/how"}},
                   {"v.json": '{"how":{"$opt":"merge"}}'})
        res = run(d)
        self.assertIn("錯", res["stdout"])                   # 取回來的值就當成寫在那裡
        self.assertIsNone(res["stderr"])


if __name__ == "__main__":
    unittest.main()
