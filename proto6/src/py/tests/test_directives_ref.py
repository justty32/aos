"""aos_directives 的測試：每條規則、每個錯誤代號都要有一條。

本檔：$ref 與循環（TestRef、TestCycle）。

純記憶體文件用 `Document(None, root)`；要測跨檔的用暫存資料夾寫真檔。
"""
import os
import unittest

from _directives_util import Base

from aos_directives import Document, Context, resolve, resolve_located


# ---------------------------------------------------------------- $ref / $at ----
class TestRef(Base):

    def test_ref_whole_document(self):
        self.write("a.json", {"x": [1, 2]})
        self.assertEqual(resolve({"$ref": "a.json"}, self.ctx({}), ["v"]), {"x": [1, 2]})

    def test_ref_whole_document_scalar(self):
        self.write("s.json", "整份就是一個字串")
        self.assertEqual(resolve({"$ref": "s.json"}, self.ctx({}), ["v"]), "整份就是一個字串")

    def test_ref_absolute_at(self):
        self.write("a.json", {"x": {"y": ["no", "yes"]}})
        self.assertEqual(resolve({"$ref": "a.json", "$at": "/x/y/1"}, self.ctx({}), ["v"]), "yes")

    def test_ref_absolute_path_file(self):
        p = self.write("a.json", {"k": "v"})
        c = Context(Document(None, {}), base_dir="/nonexistent", env={})
        self.assertEqual(resolve({"$ref": p, "$at": "/k"}, c, ["v"]), "v")

    def test_ref_relative_file_uses_base_dir(self):
        os.mkdir(os.path.join(self.d, "sub"))
        self.write("sub/a.json", {"k": "v"})
        c = Context(Document(None, {}), base_dir=os.path.join(self.d, "sub"), env={})
        self.assertEqual(resolve({"$ref": "a.json", "$at": "/k"}, c, ["v"]), "v")
        self.fails("ReferenceReadFailed", resolve, {"$ref": "a.json"}, self.ctx({}), ["v"])

    def test_ref_self_absolute(self):
        root = {"envs": {"PATH": "/bin", "P2": {"$ref": "", "$at": "/envs/PATH"}}}
        self.assertEqual(resolve(root["envs"]["P2"], self.ctx(root), ["envs", "P2"]), "/bin")

    def test_ref_self_dot_slash_own_key(self):
        """使用者的例子：./a ＝ 這個指示詞物件自己的 key a。"""
        root = {"v": {"$ref": "", "$at": "./a", "a": "x"}}
        self.assertEqual(resolve(root["v"], self.ctx(root), ["v"]), "x")

    def test_ref_self_dotdot_sibling(self):
        root = {"envs": {"GREET": "hello", "G2": {"$ref": "", "$at": "../GREET"}}}
        self.assertEqual(resolve(root["envs"]["G2"], self.ctx(root), ["envs", "G2"]), "hello")

    def test_ref_dotdot_from_array_element(self):
        root = {"argv": ["sh", {"$ref": "", "$at": "../0"}]}
        self.assertEqual(resolve(root["argv"][1], self.ctx(root), ["argv", "1"]), "sh")

    def test_at_dot_segments_skipped(self):
        root = {"a": {"b": "B", "c": {"$ref": "", "$at": "./../b/."}}}
        self.assertEqual(resolve(root["a"]["c"], self.ctx(root), ["a", "c"]), "B")
        self.assertEqual(resolve({"$ref": "", "$at": "/a/./b"}, self.ctx(root), ["a", "c"]), "B")

    def test_at_past_root(self):
        root = {"v": {"$ref": "", "$at": "../../x"}}
        self.fails("ReferencePointerInvalid", resolve, root["v"], self.ctx(root), ["v"])
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": ".."}, self.ctx(root), [])

    def test_at_relative_with_other_file_is_from_its_root(self):
        """指別的檔時「目前位置」＝那份檔的根：./x 就是 /x，../x 爬過根。"""
        self.write("a.json", {"x": 1})
        self.assertEqual(resolve({"$ref": "a.json", "$at": "./x"}, self.ctx({}), ["v"]), 1)
        self.assertEqual(resolve({"$ref": "a.json", "$at": "."}, self.ctx({}), ["v"]), {"x": 1})
        for at in ("../x", ".."):
            self.fails("ReferencePointerInvalid", resolve, {"$ref": "a.json", "$at": at},
                       self.ctx({}), ["v"])

    def test_at_bad_start(self):
        for at in ("x/y", "x", "~1", ""):
            self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": at},
                       self.ctx({"x": {"y": 1}}), ["v"])

    def test_at_not_string(self):
        for at in (1, ["/x"], {"a": 1}):
            self.fails("DirectiveValueTypeMismatch", resolve, {"$ref": "", "$at": at},
                       self.ctx({"x": 1}), ["v"])

    def test_ref_not_string(self):
        for r in (1, None, ["a.json"], {"a": 1}):
            self.fails("DirectiveValueTypeMismatch", resolve, {"$ref": r}, self.ctx({}), ["v"])

    def test_at_escapes(self):
        root = {"a/b": {"c~d": "ok"}}
        self.assertEqual(resolve({"$ref": "", "$at": "/a~1b/c~0d"}, self.ctx(root), ["v"]), "ok")

    def test_at_array_index(self):
        root = {"arr": ["z", "o", "t"]}
        self.assertEqual(resolve({"$ref": "", "$at": "/arr/2"}, self.ctx(root), ["v"]), "t")
        for at in ("/arr/3", "/arr/-1", "/arr/x", "/arr/1.0"):
            self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": at}, self.ctx(root), ["v"])

    def test_at_missing_key_and_walk_into_scalar(self):
        root = {"a": {"b": "s"}}
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": "/a/x"}, self.ctx(root), ["v"])
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": "/a/b/c"}, self.ctx(root), ["v"])

    def test_at_empty_segment_is_empty_key(self):
        """空段照 RFC 6901 當 key ""：`/` 是根底下的 ""，`./` 是目前位置底下的 ""。"""
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "", "$at": "/"}, self.ctx({"a": 1}), ["v"])
        self.assertEqual(resolve({"$ref": "", "$at": "/"}, self.ctx({"": "empty"}), ["v"]), "empty")
        root = {"v": {"$ref": "", "$at": "./", "": "own-empty"}}
        self.assertEqual(resolve(root["v"], self.ctx(root), ["v"]), "own-empty")

    def test_hash_absolute(self):
        self.write("a.json", {"x": {"y": "hy"}})
        self.assertEqual(resolve({"$ref": "a.json#/x/y"}, self.ctx({}), ["v"]), "hy")

    def test_hash_relative_in_other_file_is_from_root(self):
        self.write("a.json", {"x": "hx"})
        self.assertEqual(resolve({"$ref": "a.json#./x"}, self.ctx({}), ["v"]), "hx")
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "a.json#../x"}, self.ctx({}), ["v"])

    def test_hash_empty_file_is_current_doc(self):
        root = {"envs": {"GREET": "hello", "G2": {"$ref": "#../GREET"}}}
        self.assertEqual(resolve(root["envs"]["G2"], self.ctx(root), ["envs", "G2"]), "hello")
        self.assertEqual(resolve({"$ref": "#/envs/GREET"}, self.ctx(root), ["v"]), "hello")

    def test_hash_split_at_first_hash(self):
        """第一個 # 之後全是位置：key 裡的 # 走得到。"""
        self.write("a.json", {"k#1": "sharp"})
        self.assertEqual(resolve({"$ref": "a.json#/k#1"}, self.ctx({}), ["v"]), "sharp")

    def test_at_wins_over_hash(self):
        self.write("a.json", {"x": "X", "y": "Y"})
        self.assertEqual(resolve({"$ref": "a.json#/x", "$at": "/y"}, self.ctx({}), ["v"]), "Y")
        self.assertEqual(resolve({"$ref": "a.json#../nope", "$at": "/y"}, self.ctx({}), ["v"]), "Y")

    def test_hash_bad_pointer(self):
        self.write("a.json", {"x": 1})
        for spec in ("a.json#x", "a.json#", "a.json#~1"):
            self.fails("ReferencePointerInvalid", resolve, {"$ref": spec}, self.ctx({}), ["v"])

    def test_filename_with_hash_cannot_be_referenced(self):
        """檔名含 # 的檔沒辦法被 $ref：# 之後一律當位置。"""
        self.write("b.json#x", {"k": "hash"})
        self.fails("ReferencePointerInvalid", resolve, {"$ref": "b.json#x"}, self.ctx({}), ["v"])
        self.fails("ReferenceReadFailed", resolve, {"$ref": "b.json#/k"}, self.ctx({}), ["v"])

    def test_ref_read_failed_and_json_invalid(self):
        self.fails("ReferenceReadFailed", resolve, {"$ref": "nope.json"}, self.ctx({}), ["v"])
        self.write("bad.json", "[1,", raw=True)
        self.fails("ReferenceJsonInvalid", resolve, {"$ref": "bad.json"}, self.ctx({}), ["v"])

    def test_ref_nested_across_files(self):
        """取回來的又是指示詞就繼續解，而且目前文件換成被引用的檔。"""
        self.write("a.json", {"next": {"$ref": "b.json", "$at": "/deep/1"}})
        self.write("b.json", {"deep": ["不是這個", {"$ref": "", "$at": "/x"}], "x": "是這個"})
        self.assertEqual(resolve({"$ref": "a.json", "$at": "/next"}, self.ctx({}), ["v"]), "是這個")

    def test_ref_nested_relative_in_referenced_file(self):
        """b.json 裡的相對 $at 是以「取到的位置」算。"""
        self.write("b.json", {"envs": {"A": "a!", "B": {"$ref": "", "$at": "../A"}}})
        self.assertEqual(resolve({"$ref": "b.json", "$at": "/envs/B"}, self.ctx({}), ["v"]), "a!")

    def test_ref_located_reports_new_doc_and_position(self):
        pb = self.write("b.json", {"envs": {"K": {"$env": "X"}}})
        loc = resolve_located({"$ref": "b.json", "$at": "/envs"}, self.ctx({}, {"X": "x"}), ["envs"])
        self.assertEqual(loc.value, {"K": {"$env": "X"}})
        self.assertEqual(loc.ctx.doc.path, os.path.realpath(pb))
        self.assertEqual(loc.position, ["envs"])
        # 宿主接著往容器裡解：位置＝b.json 的 /envs/K
        self.assertEqual(resolve(loc.value["K"], loc.ctx, loc.position + ["K"]), "x")

    def test_ref_chain_carried_into_container_values(self):
        """走進 $ref 取回來的容器後再繞回容器本身＝循環，不會無限遞迴。"""
        self.write("e.json", {"A": {"$ref": ""}})
        loc = resolve_located({"$ref": "e.json"}, self.ctx({}), ["envs"])
        self.fails("ReferenceCycle", resolve, loc.value["A"], loc.ctx, loc.position + ["A"])

    def test_ref_nested_to_third_file_chain(self):
        self.write("a.json", {"$ref": "b.json"})
        self.write("b.json", {"$ref": "c.json", "$at": "/k"})
        self.write("c.json", {"k": [1, 2, 3]})
        self.assertEqual(resolve({"$ref": "a.json"}, self.ctx({}), ["v"]), [1, 2, 3])

    def test_ref_returns_option_object_untouched(self):
        self.write("o.json", {"$opt": "append", "$val": {"$env": "P"}})
        loc = resolve_located({"$ref": "o.json"}, self.ctx({}, {"P": "out.txt"}), ["stdout"])
        self.assertEqual(loc.value, {"$opt": "append", "$val": {"$env": "P"}})
        self.assertEqual(resolve(loc.value["$val"], loc.ctx, loc.position + ["$val"]), "out.txt")

    def test_ref_extra_keys_ignored(self):
        self.write("a.json", {"k": "v"})
        self.assertEqual(resolve({"$ref": "a.json", "$at": "/k", "_note": "n", "X": "1"},
                                 self.ctx({}), ["v"]), "v")


class TestCycle(Base):

    def test_self_cycle(self):
        root = {"v": {"$ref": "", "$at": "."}}
        self.fails("ReferenceCycle", resolve, root["v"], self.ctx(root), ["v"])

    def test_self_cycle_absolute(self):
        root = {"v": {"$ref": "", "$at": "/v"}}
        self.fails("ReferenceCycle", resolve, root["v"], self.ctx(root), ["v"])

    def test_two_file_cycle(self):
        self.write("a.json", {"$ref": "b.json"})
        self.write("b.json", {"$ref": "a.json"})
        self.fails("ReferenceCycle", resolve, {"$ref": "a.json"}, self.ctx({}), ["v"])

    def test_file_refers_back_to_itself_by_name(self):
        self.write("a.json", {"k": {"$ref": "a.json", "$at": "/k"}})
        self.fails("ReferenceCycle", resolve, {"$ref": "a.json", "$at": "/k"}, self.ctx({}), ["v"])

    def test_fmt_variable_refers_to_fmt_itself(self):
        """變數在 /v/$fmt/a，../.. 回到 /v＝這個 $fmt 物件自己＝循環。"""
        root = {"v": {"$fmt": {"$val": "${a}", "a": {"$ref": "", "$at": "../.."}}}}
        self.fails("ReferenceCycle", resolve, root["v"], self.ctx(root), ["v"])

    def test_same_target_twice_not_cycle(self):
        """同一個目標被兩個變數各引用一次、或兩格各引用一次，不是循環。"""
        self.write("a.json", {"k": "v"})
        v = {"$fmt": {"$val": "${a}${b}", "a": {"$ref": "a.json", "$at": "/k"},
                      "b": {"$ref": "a.json", "$at": "/k"}}}
        self.assertEqual(resolve(v, self.ctx({}), ["x"]), "vv")
        c = self.ctx({})
        self.assertEqual(resolve({"$ref": "a.json"}, c, ["p"]), {"k": "v"})
        self.assertEqual(resolve({"$ref": "a.json"}, c, ["q"]), {"k": "v"})

    def test_cycle_checked_before_reading(self):
        """繞回自己的檔即使讀不到也先報循環（鏈上已經有它）。"""
        self.write("a.json", {"$ref": "a.json"})
        self.fails("ReferenceCycle", resolve, {"$ref": "a.json"}, self.ctx({}), ["v"])


if __name__ == "__main__":
    unittest.main()
