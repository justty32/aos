"""aos_inst.load()：讀、驗、解——照 spec/inst-posix/。全部在這個進程裡跑，不開子進程。

分幾群：七個欄位與預設值、_metainfo、選項物件的形狀、$ref／$at、$fmt、$env、拒絕的代號、
指示詞優先序。案例大多從 proto4-3 的 test_fields／test_opts／test_ref／test_fmt／test_env／
test_reject 搬來改成直接驗 load() 的結果。
"""
import os
import unittest

from _util import OUTER, InstCase, fmt

import aos_inst
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


# ---------------------------------------------------------------- $ref / $at ----

class TestRef(InstCase):

    def env_m(self, value, extra=None):
        """envs.M 放 value，回解出來的 M。"""
        obj = dict({"argv": ["true"], "envs": {"M": value}}, **(extra or {}))
        return self.load(obj)["envs"]["M"]

    def test_one_level(self):
        self.write("vals.json", '{"msg": "從別的檔來的"}')
        self.assertEqual(self.env_m({"$ref": "vals.json", "$at": "/msg"}), "從別的檔來的")

    def test_whole_document(self):
        self.write("plain.json", '"整份就是一個字串"')
        self.assertEqual(self.env_m({"$ref": "plain.json"}), "整份就是一個字串")

    def test_hash_form_is_the_same_as_at(self):
        """`$ref: "a.json#/x"` ＝ `$ref: "a.json", $at: "/x"`；$at 有寫就 $at 贏。"""
        self.write("vals.json", '{"msg": "有", "other": "另一個"}')
        self.assertEqual(self.env_m({"$ref": "vals.json#/msg"}), "有")
        self.assertEqual(self.env_m({"$ref": "vals.json#/msg", "$at": "/other"}), "另一個")

    def test_nested(self):
        """取回來的又是指示詞就繼續解。"""
        self.write("a.json", '{"next": {"$ref": "b.json", "$at": "/deep/1"}}')
        self.write("b.json", '{"deep": ["不是這個", "是這個"]}')
        self.assertEqual(self.env_m({"$ref": "a.json", "$at": "/next"}), "是這個")

    def test_cycle(self):
        self.write("a.json", '{"x": {"$ref": "b.json", "$at": "/y"}}')
        self.write("b.json", '{"y": {"$ref": "a.json", "$at": "/x"}}')
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": "/x"}}}, "ReferenceCycle")

    def test_self_cycle(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "", "$at": "."}}}, "ReferenceCycle")

    def test_same_target_from_two_fields_is_not_a_cycle(self):
        """鏈是每一格各自一條：兩個欄位各引用同一個目標一次完全合法。"""
        self.write("vals.json", '{"p": "same.txt"}')
        r = self.load({"argv": ["true"], "stdout": {"$ref": "vals.json#/p"}, "stderr": {"$ref": "vals.json#/p"}})
        self.assertEqual(r["stdout"]["path"], r["stderr"]["path"])

    def test_missing_file(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "nope.json", "$at": "/x"}}}, "ReferenceReadFailed")

    def test_bad_json_file(self):
        self.write("bad.json", "{不是")
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "bad.json"}}}, "ReferenceJsonInvalid")

    def test_bad_pointer(self):
        self.write("vals.json", '{"msg": "有"}')
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "vals.json", "$at": "/沒有"}}}, "ReferencePointerInvalid")

    def test_ref_not_a_string(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": 3}}}, "DirectiveValueTypeMismatch")

    def test_at_not_a_string(self):
        self.write("a.json", '{"x": "1"}')
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": 3}}}, "DirectiveValueTypeMismatch")

    def test_array_at_a_string_place(self):
        """$ref 取回來的東西當成本來寫在那裡：字串位置拿到陣列＝那個位置型別錯。"""
        self.write("vals.json", '{"msg": ["不能是陣列"]}')
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "vals.json", "$at": "/msg"}}}, "FieldTypeMismatch")

    def test_ref_is_relative_to_cwd(self):
        """cwd 設成 sub 之後，$ref 的相對路徑也跟著落在 sub 裡（不是 base）。"""
        self.write("vals.json", '{"msg": "base 底下那份（不該讀到）"}')
        self.write("sub/vals.json", '{"msg": "cwd 底下那份"}')
        self.assertEqual(self.env_m({"$ref": "vals.json", "$at": "/msg"}, {"cwd": "sub"}), "cwd 底下那份")

    def test_cwd_own_ref_is_relative_to_base(self):
        """`cwd` 自己是最先解的，它的 $ref 以 base 為中心。"""
        self.write("where.json", '{"c": "sub"}')
        r = self.load({"argv": ["true"], "cwd": {"$ref": "where.json", "$at": "/c"}})
        self.assertEqual(r["cwd"], os.path.join(self.d, "sub"))

    def test_cwd_mkdir_val_ref_is_relative_to_base(self):
        self.write("where.json", '{"c": "new/dir"}')
        r = self.load({"argv": ["true"], "cwd": {"$opt": "mkdir", "$val": {"$ref": "where.json#/c"}}})
        self.assertEqual((r["cwd"], r["cwd_mkdir"]), (os.path.join(self.d, "new", "dir"), True))

    def test_ref_in_argv_and_paths(self):
        self.write("vals.json", '{"word": "從 argv 來的", "out": "named.txt"}')
        r = self.load({"argv": ["echo", {"$ref": "vals.json", "$at": "/word"}],
                       "stdout": {"$ref": "vals.json", "$at": "/out"}})
        self.assertEqual(r["argv"], ["echo", "從 argv 來的"])
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "named.txt"))

    def test_option_val_can_be_a_ref(self):
        self.write("vals.json", '{"out": "deep/named.txt"}')
        r = self.load({"argv": ["true"], "stdout": {"$opt": "mkdir", "$val": {"$ref": "vals.json", "$at": "/out"}}})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "deep", "named.txt"))
        self.assertTrue(r["stdout"]["mkdir"])

    def test_option_val_ref_to_a_number(self):
        self.write("vals.json", '{"out": 3}')
        self.bad({"argv": ["true"], "stdout": {"$opt": "append", "$val": {"$ref": "vals.json", "$at": "/out"}}},
                 "FieldTypeMismatch")

    def test_absolute_ref_path(self):
        p = self.write("vals.json", '{"msg": "絕對"}')
        self.assertEqual(self.env_m({"$ref": p, "$at": "/msg"}, {"cwd": "/tmp"}), "絕對")


class TestDirectiveAnywhere(InstCase):
    """先解、再驗：頂層、argv 整包、envs 整包都能是指示詞，解出來才照那個位置驗型別。"""

    def test_whole_inst_from_a_ref(self):
        self.write("base.json", '{"argv": ["sh", "-c", "echo 整份都是別人的"], "stdout": "out.txt"}')
        r = self.load({"$ref": "base.json"})
        self.assertEqual(r["argv"], ["sh", "-c", "echo 整份都是別人的"])
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "out.txt"))

    def test_whole_inst_ref_then_relative_at_uses_that_file(self):
        """頂層 $ref 之後，「目前文件」是被引用的檔：裡面的 $ref:"" 指的是它自己。"""
        self.write("base.json", '{"argv": ["echo", {"$ref": "", "$at": "/name"}], "name": "b 的"}')
        r = self.load({"$ref": "base.json", "name": "inst 的（被忽略）"})
        self.assertEqual(r["argv"], ["echo", "b 的"])

    def test_top_level_ref_to_itself_is_a_cycle(self):
        self.bad({"$ref": ".aos/inst.json"}, "ReferenceCycle")

    def test_top_level_ref_to_a_non_object(self):
        self.write("s.json", '"字串"')
        self.bad({"$ref": "s.json"}, "NotAnObject")

    def test_argv_can_be_a_ref_to_an_array(self):
        self.write("a.json", '{"argv": ["sh", "-c", "echo argv 也是"]}')
        r = self.load({"argv": {"$ref": "a.json", "$at": "/argv"}})
        self.assertEqual(r["argv"], ["sh", "-c", "echo argv 也是"])

    def test_argv_ref_to_a_string(self):
        self.write("a.json", '{"argv": "sh"}')
        self.bad({"argv": {"$ref": "a.json", "$at": "/argv"}}, "FieldTypeMismatch")

    def test_argv_elements_inside_a_referenced_array_keep_resolving(self):
        """argv 整包從別的檔拿，裡面的元素還是指示詞就用那份檔當目前文件繼續解。"""
        self.write("a.json", '{"argv": ["echo", {"$ref": "", "$at": "/w"}], "w": "a 的 w"}')
        r = self.load({"argv": {"$ref": "a.json#/argv"}, "w": "inst 的 w"})
        self.assertEqual(r["argv"], ["echo", "a 的 w"])

    def test_envs_whole_object_from_a_ref(self):
        self.write("e.json", '{"A": "一", "B": "二"}')
        self.assertEqual(self.load({"argv": ["true"], "envs": {"$ref": "e.json"}})["envs"], {"A": "一", "B": "二"})

    def test_envs_values_inside_a_referenced_object_keep_resolving(self):
        self.write("e.json", '{"A": {"$ref": "", "$at": "../B"}, "B": "e 的 B"}')
        self.assertEqual(self.load({"argv": ["true"], "envs": {"$ref": "e.json"}})["envs"],
                         {"A": "e 的 B", "B": "e 的 B"})

    def test_envs_ref_to_a_string(self):
        self.write("e.json", '"不是物件"')
        self.bad({"argv": ["true"], "envs": {"$ref": "e.json"}}, "FieldTypeMismatch")

    def test_envs_fmt_is_type_mismatch(self):
        self.bad({"argv": ["true"], "envs": fmt("x")}, "FieldTypeMismatch")

    def test_envs_ref_mixed_with_a_plain_key_runs_the_ref(self):
        """有 $ 開頭的 key 就整包當指示詞物件看：混著的普通 key 忽略、不會變成環境變數。"""
        self.write("e.json", '{"A": "1"}')
        self.assertEqual(self.load({"argv": ["true"], "envs": {"$ref": "e.json", "X": "1"}})["envs"], {"A": "1"})


class TestAt(InstCase):
    """`$at`：絕對／相對位置、`$ref:""`＝目前文件、escape、陣列索引、位置＝實體路徑。"""

    def env_m(self, envs, extra=None):
        obj = dict({"argv": ["true"], "envs": envs}, **(extra or {}))
        return self.load(obj)["envs"]["M"]

    def test_absolute_in_another_file(self):
        self.write("a.json", '{"x": {"y": ["零", "壹"]}}')
        self.assertEqual(self.env_m({"M": {"$ref": "a.json", "$at": "/x/y/1"}}), "壹")

    def test_empty_ref_absolute_is_this_document(self):
        r = self.load({"argv": ["echo", {"$ref": "", "$at": "/envs/GREET"}], "envs": {"GREET": "哈囉"}})
        self.assertEqual(r["argv"], ["echo", "哈囉"])

    def test_dot_slash_is_the_directive_objects_own_position(self):
        r = self.load({"argv": ["echo", {"$ref": "", "$at": "./a", "a": "x"}]})
        self.assertEqual(r["argv"], ["echo", "x"])

    def test_dot_dot_is_the_sibling_key(self):
        self.assertEqual(self.env_m({"GREET": "兄弟", "M": {"$ref": "", "$at": "../GREET"}}), "兄弟")
        self.assertEqual(self.env_m({"GREET": "兄弟", "M": {"$ref": "#../GREET"}}), "兄弟")

    def test_two_dot_dots_from_a_nested_spot(self):
        """envs/M 往上兩層＝根，再走 /argv/2。"""
        self.assertEqual(self.env_m({"M": {"$ref": "", "$at": "../../argv/2"}},
                                    {"argv": ["sh", "-c", "第二個"]}), "第二個")

    def test_dot_dot_past_root(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "", "$at": "../../../x"}}}, "ReferencePointerInvalid")

    def test_relative_at_with_another_file_is_from_its_root(self):
        """指別的檔時「目前位置」＝那份檔的根：x.json#./a ＝ /a；再往上就爬過根。"""
        self.write("a.json", '{"x": "1"}')
        self.assertEqual(self.env_m({"M": {"$ref": "a.json", "$at": "./x"}}), "1")
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": "../x"}}}, "ReferencePointerInvalid")

    def test_at_with_bad_prefix(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "", "$at": "envs/GREET"}, "GREET": "1"}},
                 "ReferencePointerInvalid")

    def test_at_omitted_is_the_whole_document(self):
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": ""}}}, "FieldTypeMismatch")

    def test_tilde_escapes(self):
        self.write("a.json", '{"a/b": {"c~d": "逃"}}')
        self.assertEqual(self.env_m({"M": {"$ref": "a.json", "$at": "/a~1b/c~0d"}}), "逃")

    def test_array_index(self):
        self.write("a.json", '["零", "壹", "貳"]')
        self.assertEqual(self.env_m({"M": {"$ref": "a.json", "$at": "/2"}}), "貳")
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": "/x"}}}, "ReferencePointerInvalid")
        self.bad({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": "/3"}}}, "ReferencePointerInvalid")

    def test_nested_directive_uses_the_referenced_file_as_its_document(self):
        self.write("b.json", '{"v": {"$ref": "", "$at": "../w"}, "w": "b 的 w"}')
        self.assertEqual(self.env_m({"M": {"$ref": "b.json", "$at": "/v"}, "w": "inst 的 w"}), "b 的 w")

    def test_nested_absolute_in_referenced_file(self):
        self.write("b.json", '{"deep": {"v": {"$ref": "", "$at": "/top"}}, "top": "b 的頂"}')
        self.assertEqual(self.env_m({"M": {"$ref": "b.json", "$at": "/deep/v"}, "top": "不是"}), "b 的頂")

    def test_relative_at_inside_an_option_val(self):
        """選項物件的 $val 位置是 <那格>/$val，所以 ../ 回到那格、../../ 回到根。"""
        r = self.load({"argv": ["true"], "name": "named.txt",
                       "stdout": {"$opt": "mkdir", "$val": {"$ref": "", "$at": "../../name"}}})
        self.assertEqual(r["stdout"]["path"], os.path.join(self.d, "named.txt"))

    def test_fmt_variables_can_point_at_each_other(self):
        """$fmt 的變數位置是 <那格>/$fmt/名字：b 用 ../a 拿到兄弟變數 a。"""
        self.assertEqual(self.env_m({"M": fmt("${a}+${b}", a="甲", b={"$ref": "", "$at": "../a"})}), "甲+甲")

    def test_position_inside_argv_is_the_index(self):
        """argv 元素的位置是 /argv/N：從第 2 個往上一層再走 0 拿到 argv[0]。"""
        r = self.load({"argv": ["echo", {"$ref": "", "$at": "../0"}]})
        self.assertEqual(r["argv"], ["echo", "echo"])


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
