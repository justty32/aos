"""aos_inst.load()：讀、驗、解——照 spec/inst-posix/。全部在這個進程裡跑，不開子進程。

本檔：$ref、$at、指示詞出現在哪都行（TestRef、TestDirectiveAnywhere、TestAt）。

分幾群：七個欄位與預設值、_metainfo、選項物件的形狀、$ref／$at、$fmt、$env、拒絕的代號、
指示詞優先序。案例大多從 proto4-3 的 test_fields／test_opts／test_ref／test_fmt／test_env／
test_reject 搬來改成直接驗 load() 的結果。
"""
import os
import unittest

from _util import InstCase, fmt


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


if __name__ == "__main__":
    unittest.main()
