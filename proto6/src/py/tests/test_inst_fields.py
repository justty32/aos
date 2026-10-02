"""aos_inst.load()：讀、驗、解——照 spec/inst.md。全部在這個進程裡跑，不開子進程。

本檔：七個欄位、_metainfo、選項物件形狀（TestFields、TestMetainfo、TestOptShape）。

分幾群：七個欄位與預設值、_metainfo、選項物件的形狀、$ref／$at、$fmt、$env、拒絕的代號、
指示詞優先序。案例大多從 proto4-3 的 test_fields／test_opts／test_ref／test_fmt／test_env／
test_reject 搬來改成直接驗 load() 的結果。
"""
import os
import unittest

from _util import InstCase

from aos_inst import InstError


# ---------------------------------------------------------------- 欄位與預設 ----
class TestFields(InstCase):

    def test_error_shape(self):
        e = InstError("Foo", "白話")
        self.assertEqual((e.code, e.msg, str(e)), ("Foo", "白話", "Foo: 白話"))

    def test_argv_only_defaults(self):
        """只有 argv：串流都沒寫（""＝/dev/null）、exit 不寫、cwd＝base、envs 空、不清空。"""
        r = self.load({"argv": ["true"]})
        self.assertEqual(r["argv"], ["true"])
        self.assertEqual(r["stdin"], {"path": "", "inherit": False})
        self.assertEqual(r["stdout"], {"path": "", "append": False, "mkdir": False, "inherit": False})
        self.assertEqual(r["stderr"], {"path": "", "append": False, "mkdir": False,
                                       "inherit": False, "merge": False})
        self.assertEqual(r["exit"], {"path": "", "append": False, "mkdir": False})
        self.assertEqual(r["cwd"], self.d)
        self.assertFalse(r["cwd_mkdir"])
        self.assertEqual((r["envs"], r["envs_clear"]), ({}, False))
        self.assertEqual(r["metainfo"], {"_type": "posix", "_version": 1})

    def test_paths_are_relative_to_cwd(self):
        """四個路徑欄以解出來的 cwd 為中心；cwd 自己以 base 為中心。"""
        r = self.load({"argv": ["true"], "cwd": "sub", "stdin": "in.txt", "stdout": "o.txt",
                       "stderr": "e.txt", "exit": "code.txt"})
        sub = os.path.join(self.d, "sub")
        self.assertEqual(r["cwd"], sub)
        self.assertEqual(r["stdin"]["path"], os.path.join(sub, "in.txt"))
        self.assertEqual(r["stdout"]["path"], os.path.join(sub, "o.txt"))
        self.assertEqual(r["stderr"]["path"], os.path.join(sub, "e.txt"))
        self.assertEqual(r["exit"]["path"], os.path.join(sub, "code.txt"))

    def test_absolute_paths_are_literal(self):
        r = self.load({"argv": ["true"], "cwd": "/tmp", "stdout": "/x/y.txt"})
        self.assertEqual(r["cwd"], "/tmp")
        self.assertEqual(r["stdout"]["path"], "/x/y.txt")

    def test_cwd_is_relative_to_base_not_to_the_json(self):
        """inst.json 埋在 deep/ 裡，cwd 的相對路徑還是從 base 起算。"""
        r = self.load({"argv": ["true"], "cwd": "sub"}, rel="deep/inst.json")
        self.assertEqual(r["cwd"], os.path.join(self.d, "sub"))

    def test_dot_dot_in_paths_is_normalized(self):
        r = self.load({"argv": ["true"], "cwd": "a/b", "stdout": "../o.txt"})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "a", "o.txt"))

    def test_empty_path_means_not_written(self):
        """路徑欄給空字串＝沒寫（舊意思：/dev/null／不寫 exit／cwd＝base）。"""
        r = self.load({"argv": ["true"], "stdout": "", "exit": "", "cwd": ""})
        self.assertEqual(r["stdout"]["path"], "")
        self.assertEqual(r["exit"]["path"], "")
        self.assertEqual(r["cwd"], self.d)

    def test_envs_field(self):
        r = self.load({"argv": ["true"], "envs": {"GREET": "hi", "N": "1"}})
        self.assertEqual(r["envs"], {"GREET": "hi", "N": "1"})
        self.assertFalse(r["envs_clear"])

    def test_unknown_top_level_keys_are_ignored(self):
        r = self.load({"argv": ["true"], "timeout_ms": 5, "parallel": True, "env": {"A": "1"}})
        self.assertEqual(r["argv"], ["true"])
        self.assertEqual(r["envs"], {})

    def test_argv_elements_verbatim(self):
        """沒有 shell：空字串、空白、像旗標的都原樣是一個元素。"""
        r = self.load({"argv": ["echo", "", "a b", "--flag", "$HOME"]})
        self.assertEqual(r["argv"], ["echo", "", "a b", "--flag", "$HOME"])


# ---------------------------------------------------------------- _metainfo ----

class TestMetainfo(InstCase):

    def test_absent_is_posix_v1(self):
        self.assertEqual(self.load({"argv": ["true"]})["metainfo"], {"_type": "posix", "_version": 1})

    def test_valid(self):
        r = self.load({"_metainfo": {"_type": "posix", "_version": 1}, "argv": ["true"]})
        self.assertEqual(r["metainfo"], {"_type": "posix", "_version": 1})

    def test_extra_keys_ignored(self):
        r = self.load({"_metainfo": {"_type": "posix", "_version": 1, "note": "隨便"}, "argv": ["true"]})
        self.assertEqual(r["metainfo"], {"_type": "posix", "_version": 1})

    def test_not_an_object(self):
        self.bad({"argv": ["true"], "_metainfo": "posix"}, "MetainfoInvalid")
        self.bad({"argv": ["true"], "_metainfo": ["posix", 1]}, "MetainfoInvalid")

    def test_missing_keys(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix"}}, "MetainfoInvalid")
        self.bad({"argv": ["true"], "_metainfo": {"_version": 1}}, "MetainfoInvalid")
        self.bad({"argv": ["true"], "_metainfo": {}}, "MetainfoInvalid")

    def test_metainfo_is_not_resolved_as_a_directive(self):
        """規範 1.5：`{"_metainfo": {"$ref": …}}` 的 $ref 不是 _type／_version，被忽略＝缺欄位。"""
        self.write("m.json", '{"_type": "posix", "_version": 1}')
        self.bad({"argv": ["true"], "_metainfo": {"$ref": "m.json"}}, "MetainfoInvalid")

    def test_type_wrong(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "windows", "_version": 1}}, "UnsupportedInstType")
        self.bad({"argv": ["true"], "_metainfo": {"_type": 1, "_version": 1}}, "UnsupportedInstType")

    def test_version_wrong(self):
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix", "_version": 2}}, "UnsupportedInstVersion")
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix", "_version": "1"}}, "UnsupportedInstVersion")

    def test_version_true_is_not_an_int(self):
        """`_version` 要 int；JSON 的 true／false 是 bool，不算數。"""
        self.bad({"argv": ["true"], "_metainfo": {"_type": "posix", "_version": True}}, "UnsupportedInstVersion")

    def test_metainfo_checked_before_argv(self):
        """_metainfo 先驗：壞的 _metainfo 配上壞的 argv，報的是 _metainfo。"""
        self.bad({"_metainfo": 3}, "MetainfoInvalid")


# ---------------------------------------------------------------- 選項物件的形狀 ----

class TestOptShape(InstCase):

    def test_single_option(self):
        r = self.load({"argv": ["true"], "stdout": {"$opt": "append", "$val": "log.txt"}})
        self.assertEqual(r["stdout"], {"path": os.path.join(self.d, "log.txt"), "append": True,
                                       "mkdir": False, "inherit": False})

    def test_option_array(self):
        r = self.load({"argv": ["true"], "stdout": {"$opt": ["append", "mkdir"], "$val": "deep/out.txt"}})
        self.assertTrue(r["stdout"]["append"] and r["stdout"]["mkdir"])
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "deep", "out.txt"))

    def test_all_no_val_options(self):
        r = self.load({"argv": ["true"], "stdin": {"$opt": "inherit"}, "stdout": {"$opt": "inherit"},
                       "stderr": {"$opt": "merge"}})
        self.assertEqual(r["stdin"], {"path": "", "inherit": True})
        self.assertTrue(r["stdout"]["inherit"])
        self.assertTrue(r["stderr"]["merge"])
        self.assertFalse(r["stderr"]["inherit"])

    def test_stderr_inherit(self):
        r = self.load({"argv": ["true"], "stderr": {"$opt": "inherit"}})
        self.assertTrue(r["stderr"]["inherit"])

    def test_exit_options(self):
        r = self.load({"argv": ["true"], "exit": {"$opt": ["mkdir", "append"], "$val": "run/1/code.txt"}})
        self.assertEqual(r["exit"], {"path": os.path.join(self.d, "run", "1", "code.txt"),
                                     "append": True, "mkdir": True})

    def test_cwd_mkdir(self):
        r = self.load({"argv": ["true"], "cwd": {"$opt": "mkdir", "$val": "work/x"}, "stdout": "o.txt"})
        self.assertTrue(r["cwd_mkdir"])
        self.assertEqual(r["cwd"], os.path.join(self.d, "work", "x"))
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "work", "x", "o.txt"))

    def test_envs_clear_with_and_without_val(self):
        r = self.load({"argv": ["true"], "envs": {"$opt": "clear", "$val": {"ONLY": "我"}}})
        self.assertEqual((r["envs"], r["envs_clear"]), ({"ONLY": "我"}, True))
        r = self.load({"argv": ["true"], "envs": {"$opt": "clear"}})
        self.assertEqual((r["envs"], r["envs_clear"]), ({}, True))

    def test_opt_not_a_string_or_array(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": 3, "$val": "x"}}, "DirectiveValueTypeMismatch")
        self.bad({"argv": ["true"], "stdout": {"$opt": None}}, "DirectiveValueTypeMismatch")
        self.bad({"argv": ["true"], "stdout": {"$opt": {"a": 1}}}, "DirectiveValueTypeMismatch")

    def test_opt_empty_array(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": [], "$val": "x"}}, "DirectiveValueTypeMismatch")

    def test_opt_array_with_non_string(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": ["append", 1], "$val": "x"}}, "DirectiveValueTypeMismatch")

    def test_duplicate_option_is_unknown_option(self):
        e = self.bad({"argv": ["true"], "stdout": {"$opt": ["append", "append"], "$val": "x"}}, "UnknownOption")
        self.assertIn("重複", e.msg)

    def test_option_not_for_this_position(self):
        """clear 是 envs 的、mkdir 不是 stdin 的、merge 只有 stderr 有、大寫不算。"""
        self.bad({"argv": ["true"], "stdout": {"$opt": "clear"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdin": {"$opt": "mkdir", "$val": "x"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdout": {"$opt": "merge"}}, "UnknownOption")
        self.bad({"argv": ["true"], "exit": {"$opt": "inherit"}}, "UnknownOption")
        self.bad({"argv": ["true"], "cwd": {"$opt": "append", "$val": "x"}}, "UnknownOption")
        self.bad({"argv": ["true"], "envs": {"$opt": "merge"}}, "UnknownOption")
        self.bad({"argv": ["true"], "stdin": {"$opt": "Inherit"}}, "UnknownOption")

    def test_option_in_a_position_with_no_options(self):
        """argv 的元素、envs 的值、argv 整包、頂層、$val 裡面都不吃選項。"""
        self.bad({"argv": [{"$opt": "inherit"}]}, "UnknownOption")
        self.bad({"argv": ["true"], "envs": {"A": {"$opt": "clear"}}}, "UnknownOption")
        self.bad({"argv": {"$opt": "inherit"}}, "UnknownOption")
        self.bad({"$opt": "inherit"}, "UnknownOption")
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": {"$opt": "mkdir", "$val": "x"}}},
                 "UnknownOption")
        self.bad({"argv": ["true"], "envs": {"$opt": "clear", "$val": {"$opt": "clear"}}}, "UnknownOption")

    def test_inherit_with_val_conflicts(self):
        self.bad({"argv": ["true"], "stdin": {"$opt": "inherit", "$val": "in.txt"}}, "OptionConflict")
        self.bad({"argv": ["true"], "stdout": {"$opt": "inherit", "$val": "x"}}, "OptionConflict")

    def test_merge_with_val_conflicts(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": "merge", "$val": "e.txt"}}, "OptionConflict")

    def test_inherit_plus_others_conflicts(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": ["inherit", "append"], "$val": "x"}}, "OptionConflict")
        self.bad({"argv": ["true"], "stderr": {"$opt": ["mkdir", "inherit"], "$val": "x"}}, "OptionConflict")

    def test_merge_plus_others_conflicts(self):
        self.bad({"argv": ["true"], "stderr": {"$opt": ["merge", "inherit"]}}, "OptionConflict")
        self.bad({"argv": ["true"], "stderr": {"$opt": ["mkdir", "merge"], "$val": "d/e"}}, "OptionConflict")
        self.bad({"argv": ["true"], "stderr": {"$opt": ["append", "merge"], "$val": "e"}}, "OptionConflict")

    def test_required_val_missing_conflicts(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": "append"}}, "OptionConflict")
        self.bad({"argv": ["true"], "stderr": {"$opt": "mkdir"}}, "OptionConflict")
        self.bad({"argv": ["true"], "exit": {"$opt": ["append", "mkdir"]}}, "OptionConflict")
        self.bad({"argv": ["true"], "cwd": {"$opt": "mkdir"}}, "OptionConflict")

    def test_required_val_empty_string_conflicts(self):
        """空字串在路徑欄的意思是「沒寫」，跟 append／mkdir 兜不起來。"""
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": ""}}, "OptionConflict")
        self.bad({"argv": ["true"], "cwd": {"$opt": "mkdir", "$val": ""}}, "OptionConflict")
        self.bad({"argv": ["true"], "exit": {"$opt": "mkdir", "$val": ""}}, "OptionConflict")

    def test_extra_keys_beside_opt_and_val_are_ignored(self):
        """選項物件只認 $opt／$val：別的 key（連 $ref 也是）一律忽略。"""
        r = self.load({"argv": ["true"], "stdout": {"$opt": "append", "$val": "f.txt", "$ref": "nope.json",
                                                    "$mode": 1, "_note": "說明"}})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "f.txt"))

    def test_old_dollar_envs_key_is_silently_ignored(self):
        """舊寫法 {"$opt":"clear","$envs":{…}}：不報錯，但 $envs 沒人看＝清成空環境。"""
        r = self.load({"argv": ["true"], "envs": {"$opt": "clear", "$envs": {"A": "1"}}})
        self.assertEqual((r["envs"], r["envs_clear"]), ({}, True))

    def test_val_type_is_checked_per_position(self):
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": 3}}, "FieldTypeMismatch")
        self.bad({"argv": ["true"], "envs": {"$opt": "clear", "$val": "x"}}, "FieldTypeMismatch")
        self.bad({"argv": ["true"], "envs": {"$opt": "clear", "$val": ["A=1"]}}, "FieldTypeMismatch")

    def test_val_can_be_a_directive(self):
        r = self.load({"argv": ["true"], "stdout": {"$opt": "append", "$val": {"$env": "AOSTEST_OUTER"}}})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "外面來的"))
        self.write("e.json", '{"ONLY": "只有這個"}')
        r = self.load({"argv": ["true"], "envs": {"$opt": "clear", "$val": {"$ref": "e.json"}}})
        self.assertEqual((r["envs"], r["envs_clear"]), ({"ONLY": "只有這個"}, True))


if __name__ == "__main__":
    unittest.main()
