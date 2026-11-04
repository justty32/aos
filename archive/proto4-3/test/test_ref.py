"""$ref：一層、巢狀、循環，「相對路徑以 cwd 為中心」，還有**任何位置都能放**。"""
import os
import unittest

from _util import ExecCase


class TestRef(ExecCase):

    def test_ref_one_level(self):
        self.write("vals.json", '{"msg": "從別的檔來的"}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "vals.json", "$at": "/msg"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "從別的檔來的\n")

    def test_ref_whole_document(self):
        self.write("plain.json", '"整份就是一個字串"')
        self.inst({"argv": ["sh", "-c", "echo $M"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "plain.json"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "整份就是一個字串\n")

    def test_ref_nested(self):
        """取回來的又是指示詞就繼續解。"""
        self.write("a.json", '{"next": {"$ref": "b.json", "$at": "/deep/1"}}')
        self.write("b.json", '{"deep": ["不是這個", "是這個"]}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "a.json", "$at": "/next"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "是這個\n")

    def test_ref_cycle_is_125(self):
        self.write("a.json", '{"x": {"$ref": "b.json", "$at": "/y"}}')
        self.write("b.json", '{"y": {"$ref": "a.json", "$at": "/x"}}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "a.json", "$at": "/x"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReferenceCycle", r.stderr)

    def test_old_hash_pointer_form_is_now_a_filename(self):
        """舊的 file#/pointer 寫法拿掉了：# 只是檔名的一部分，所以是讀不到檔。"""
        self.write("vals.json", '{"msg": "有"}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "vals.json#/msg"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReferenceReadFailed", r.stderr)

    def test_ref_missing_file_is_125(self):
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "nope.json", "$at": "/x"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReferenceReadFailed", r.stderr)

    def test_ref_bad_pointer_is_125(self):
        self.write("vals.json", '{"msg": "有"}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "vals.json", "$at": "/沒有"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReferencePointerInvalid", r.stderr)

    def test_ref_to_array_at_a_string_place_is_125(self):
        """$ref 取回來的東西當成本來寫在那裡：字串位置拿到陣列＝那個位置型別錯。"""
        self.write("vals.json", '{"msg": ["不能是陣列"]}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "vals.json", "$at": "/msg"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("FieldTypeMismatch", r.stderr)

    def test_ref_is_relative_to_cwd(self):
        """cwd 設成 sub 之後，$ref 的相對路徑也跟著落在 sub 裡（不是 xxx）。"""
        self.write("vals.json", '{"msg": "xxx 底下那份（不該讀到）"}')
        self.write("sub/vals.json", '{"msg": "cwd 底下那份"}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "cwd": "sub", "stdout": "out.txt",
                   "envs": {"M": {"$ref": "vals.json", "$at": "/msg"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), "cwd 底下那份\n")

    def test_cwd_own_ref_is_relative_to_xxx(self):
        """`cwd` 自己是最先解的，它的 $ref 只能以 xxx 為中心。"""
        self.write("where.json", '{"c": "sub"}')
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": {"$ref": "where.json", "$at": "/c"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_ref_in_argv_and_paths(self):
        self.write("vals.json", '{"word": "從 argv 來的", "out": "named.txt"}')
        self.inst({"argv": ["echo", {"$ref": "vals.json", "$at": "/word"}],
                   "stdout": {"$ref": "vals.json", "$at": "/out"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("named.txt"), "從 argv 來的\n")

    def test_option_val_can_be_a_ref(self):
        """路徑欄的選項物件：$val 是 $ref，解出來的字串當那一格的路徑（相對於 cwd）。"""
        self.write("vals.json", '{"out": "deep/named.txt"}')
        self.inst({"argv": ["echo", "來了"],
                   "stdout": {"$opt": "mkdir", "$val": {"$ref": "vals.json", "$at": "/out"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("deep/named.txt"), "來了\n")

    def test_option_val_ref_to_a_number_is_125(self):
        """$val 解出來還是照那一格的型別驗：路徑欄拿到數字＝型別錯。"""
        self.write("vals.json", '{"out": 3}')
        self.inst({"argv": ["true"],
                   "stdout": {"$opt": "append", "$val": {"$ref": "vals.json", "$at": "/out"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("FieldTypeMismatch", r.stderr)


class TestDirectiveAnywhere(ExecCase):
    """先解、再驗：頂層、argv 整包、envs 整包都能是指示詞，解出來才照那個位置驗型別。"""

    def test_whole_inst_can_come_from_a_ref(self):
        self.write("base.json", '{"argv": ["sh", "-c", "echo 整份都是別人的"],'
                                ' "stdout": "out.txt"}')
        self.inst({"$ref": "base.json"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "整份都是別人的\n")

    def test_top_level_ref_to_itself_is_a_cycle(self):
        """頂層指回自己也擋得到——鏈是從頂層就開始記的。"""
        self.inst({"$ref": ".aos/inst.json"})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("ReferenceCycle", r.stderr)

    def test_argv_can_be_a_ref_to_an_array(self):
        self.write("a.json", '{"argv": ["sh", "-c", "echo argv 也是"]}')
        self.inst({"argv": {"$ref": "a.json", "$at": "/argv"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "argv 也是\n")

    def test_argv_ref_to_a_string_is_125(self):
        """argv 這個位置要的是陣列；$ref 解出來是字串就是型別錯。"""
        self.write("a.json", '{"argv": "sh"}')
        self.inst({"argv": {"$ref": "a.json", "$at": "/argv"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("FieldTypeMismatch", r.stderr)

    def test_envs_whole_object_from_a_ref(self):
        self.write("e.json", '{"A": "一", "B": "二"}')
        self.inst({"argv": ["sh", "-c", "echo $A$B"], "stdout": "out.txt",
                   "envs": {"$ref": "e.json"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "一二\n")

    def test_envs_ref_to_a_string_is_125(self):
        self.write("e.json", '"不是物件"')
        self.inst({"argv": ["true"], "envs": {"$ref": "e.json"}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125)
        self.assertIn("FieldTypeMismatch", r.stderr)

    def test_envs_fmt_is_125(self):
        """$fmt 解出來一定是字串，envs 要的是物件。"""
        r = self.bad_inst({"argv": ["true"], "envs": {"$fmt": {"$val": "x"}}})
        self.assertIn("FieldTypeMismatch", r.stderr)

    def test_envs_clear_form_can_ref_its_val(self):
        """選項物件的 $val 自己還能再是指示詞：清空型式的 $val 用 $ref 從別的檔拿。"""
        self.write("e.json", '{"ONLY": "只有這個"}')
        self.inst({"argv": ["sh", "-c", "echo [$ONLY][$AOSTEST_OUTER]"],
                   "stdout": "out.txt",
                   "envs": {"$opt": "clear", "$val": {"$ref": "e.json"}}})
        env = dict(os.environ, AOSTEST_OUTER="外面來的")
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[只有這個][]\n")   # 清空了，外面的看不到

    def test_envs_ref_mixed_with_a_plain_key_runs_the_ref(self):
        """有 $ 開頭的 key 就整包當指示詞物件看：混著的普通 key 忽略、不會變成環境變數。"""
        self.write("e.json", '{"A": "1"}')
        self.inst({"argv": ["sh", "-c", "echo \"[$A][$X]\""], "stdout": "out.txt",
                   "envs": {"$ref": "e.json", "X": "1"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[1][]\n")

    def bad_inst(self, obj):
        self.inst(obj)
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125, r.stderr)
        return r


class TestAt(ExecCase):
    """`$at`：絕對／相對位置、`$ref:""`＝目前文件、escape、陣列索引，還有走錯的幾種。"""

    def run_env(self, envs, extra=None):
        """envs 裡的 M 印出來；回 (returncode, stdout 內容或 stderr)。"""
        obj = dict({"argv": ["printenv", "M"], "stdout": "out.txt", "envs": envs}, **(extra or {}))
        self.inst(obj)
        r = self.aos(self.d)
        return r.returncode, (self.read("out.txt") if r.returncode == 0 else r.stderr)

    def bad(self, envs, code, extra=None):
        rc, err = self.run_env(envs, extra)
        self.assertEqual(rc, 125, err)
        self.assertIn(code, err)

    def test_whole_file(self):
        self.write("plain.json", '"整份"')
        self.assertEqual(self.run_env({"M": {"$ref": "plain.json"}}), (0, "整份\n"))

    def test_absolute_at_in_another_file(self):
        self.write("a.json", '{"x": {"y": ["零", "壹"]}}')
        self.assertEqual(self.run_env({"M": {"$ref": "a.json", "$at": "/x/y/1"}}), (0, "壹\n"))

    def test_empty_ref_absolute_is_this_document(self):
        """$ref:"" ＝這份 inst.json 自己：argv 裡拿 /envs/GREET。"""
        self.inst({"argv": ["echo", {"$ref": "", "$at": "/envs/GREET"}], "stdout": "out.txt",
                   "envs": {"GREET": "哈囉"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "哈囉\n")

    def test_dot_slash_is_the_directive_objects_own_position(self):
        """使用者的例子：./a ＝這個指示詞物件自己的 key a。"""
        self.inst({"argv": ["echo", {"$ref": "", "$at": "./a", "a": "x"}], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "x\n")

    def test_dot_dot_is_the_sibling_key(self):
        self.assertEqual(self.run_env({"GREET": "兄弟", "M": {"$ref": "", "$at": "../GREET"}}),
                         (0, "兄弟\n"))

    def test_two_dot_dots_from_a_nested_spot(self):
        """envs/M 往上兩層＝根，再走 /argv/4。"""
        self.inst({"argv": ["sh", "-c", "echo $M", "-", "第二個"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "", "$at": "../../argv/4"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "第二個\n")

    def test_dot_dot_past_root_is_125(self):
        self.bad({"M": {"$ref": "", "$at": "../../../x"}}, "ReferencePointerInvalid")

    def test_relative_at_with_another_file_is_125(self):
        self.write("a.json", '{"x": "1"}')
        self.bad({"M": {"$ref": "a.json", "$at": "./x"}}, "ReferencePointerInvalid")

    def test_at_with_bad_prefix_is_125(self):
        self.bad({"M": {"$ref": "", "$at": "envs/GREET"}, "GREET": "1"}, "ReferencePointerInvalid")

    def test_at_not_a_string_is_125(self):
        self.write("a.json", '{"x": "1"}')
        self.bad({"M": {"$ref": "a.json", "$at": 3}}, "DirectiveValueTypeMismatch")

    def test_at_omitted_is_the_whole_document(self):
        """$ref:"" 沒 $at ＝整份 inst.json，放在要字串的位置就是型別錯。"""
        self.bad({"M": {"$ref": ""}}, "FieldTypeMismatch")

    def test_tilde_escapes(self):
        self.write("a.json", '{"a/b": {"c~d": "逃"}}')
        self.assertEqual(self.run_env({"M": {"$ref": "a.json", "$at": "/a~1b/c~0d"}}),
                         (0, "逃\n"))

    def test_array_index(self):
        self.write("a.json", '["零", "壹", "貳"]')
        self.assertEqual(self.run_env({"M": {"$ref": "a.json", "$at": "/2"}}), (0, "貳\n"))
        self.bad({"M": {"$ref": "a.json", "$at": "/x"}}, "ReferencePointerInvalid")
        self.bad({"M": {"$ref": "a.json", "$at": "/3"}}, "ReferencePointerInvalid")

    def test_nested_directive_uses_the_referenced_file_as_its_document(self):
        """b.json 裡的 $ref:"" 指的是 b.json（不是 inst.json）、位置是取到的那個位置。"""
        self.write("b.json", '{"v": {"$ref": "", "$at": "../w"}, "w": "b 的 w"}')
        self.assertEqual(self.run_env({"M": {"$ref": "b.json", "$at": "/v"}, "w": "inst 的 w"}),
                         (0, "b 的 w\n"))

    def test_nested_absolute_in_referenced_file(self):
        self.write("b.json", '{"deep": {"v": {"$ref": "", "$at": "/top"}}, "top": "b 的頂"}')
        self.assertEqual(self.run_env({"M": {"$ref": "b.json", "$at": "/deep/v"}, "top": "不是"}),
                         (0, "b 的頂\n"))

    def test_self_cycle_is_125(self):
        self.bad({"M": {"$ref": "", "$at": "."}}, "ReferenceCycle")

    def test_two_file_cycle_is_125(self):
        self.write("a.json", '{"x": {"$ref": "b.json", "$at": "/y"}}')
        self.write("b.json", '{"y": {"$ref": "a.json", "$at": "/x"}}')
        self.bad({"M": {"$ref": "a.json", "$at": "/x"}}, "ReferenceCycle")

    def test_relative_at_inside_an_option_val(self):
        """選項物件的 $val 位置是 <那格>/$val，所以 ../ 回到那格、../../ 回到根。"""
        self.inst({"argv": ["sh", "-c", "echo 一"], "name": "named.txt",
                   "stdout": {"$opt": "mkdir", "$val": {"$ref": "", "$at": "../../name"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("named.txt"), "一\n")


class TestDirectivePrecedence(ExecCase):
    """一個指示詞物件裡好幾個 $ key：只跑優先序最高的（$opt > $ref > $fmt > $env），其餘不看。"""

    def run_envs(self, value):
        self.inst({"argv": ["printenv", "X"], "stdout": "out.txt", "envs": {"X": value}})
        r = self.aos(self.d, env=dict(os.environ, AOSTEST_OUTER="外面來的"))
        return r, self.read("out.txt") if r.returncode == 0 else r.stderr

    def test_unknown_keys_beside_a_directive_are_ignored(self):
        self.write("a.json", '"從 a 來的"')
        r, out = self.run_envs({"$ref": "a.json", "_note": "說明", "x": 1})
        self.assertEqual(r.returncode, 0, out)
        self.assertEqual(out, "從 a 來的\n")

    def test_ref_beats_fmt(self):
        """$fmt 故意寫壞（值是字串）來證明它根本沒被看。"""
        self.write("a.json", '"從 a 來的"')
        r, out = self.run_envs({"$ref": "a.json", "$fmt": "壞的"})
        self.assertEqual(r.returncode, 0, out)
        self.assertEqual(out, "從 a 來的\n")

    def test_fmt_beats_env(self):
        r, out = self.run_envs({"$fmt": {"$val": "fmt 贏"}, "$env": "AOSTEST_NOPE"})
        self.assertEqual(r.returncode, 0, out)
        self.assertEqual(out, "fmt 贏\n")

    def test_opt_beats_ref_at_an_option_position(self):
        """有 $opt 就是選項物件：$ref 被忽略（指到不存在的檔也沒事）。"""
        self.inst({"argv": ["sh", "-c", "echo 一"],
                   "stdout": {"$opt": "append", "$val": "f.txt", "$ref": "nope.json"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("f.txt"), "一\n")

    def test_opt_at_a_no_option_position_is_still_unknown_option(self):
        """不吃選項的位置放了 $opt：優先序一樣是 $opt 先，所以是 UnknownOption，不會退去跑 $ref。"""
        self.write("a.json", '"x"')
        r, out = self.run_envs({"$opt": "clear", "$ref": "a.json"})
        self.assertEqual(r.returncode, 125)
        self.assertIn("UnknownOption", out)

    def test_only_unknown_dollar_keys_is_unknown_directive(self):
        r, out = self.run_envs({"$xyz": 1})
        self.assertEqual(r.returncode, 125)
        self.assertIn("UnknownDirective", out)


if __name__ == "__main__":
    unittest.main()
