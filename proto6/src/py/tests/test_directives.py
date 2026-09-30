"""aos_directives 的測試：每條規則、每個錯誤代號都要有一條。

純記憶體文件用 `Document(None, root)`；要測跨檔的用暫存資料夾寫真檔。
"""
import json
import os
import shutil
import tempfile
import unittest

from aos_directives import (
    DirectiveError, Document, Context, Option,
    load_document, is_directive, is_option_object,
    resolve, resolve_located, split_option, option_names, parse_options,
)


class Base(unittest.TestCase):
    """暫存資料夾＋幾個小工具。"""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-directives-")
        self.addCleanup(shutil.rmtree, self.d, True)

    def write(self, name, obj, raw=False):
        """把 obj 寫成 JSON 檔（raw=True 就照字面寫，用來寫壞 JSON），回絕對路徑。"""
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(obj if raw else json.dumps(obj, ensure_ascii=False))
        return p

    def ctx(self, root, env=None, path=None):
        """純記憶體文件的 Context，中心路徑＝暫存資料夾。"""
        return Context(Document(path, root), base_dir=self.d, env={} if env is None else env)

    def fails(self, code, fn, *a):
        with self.assertRaises(DirectiveError) as cm:
            fn(*a)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        return cm.exception


# ---------------------------------------------------------------- 基本 ----

class TestBasics(Base):

    def test_error_shape(self):
        e = DirectiveError("Foo", "白話")
        self.assertEqual(e.code, "Foo")
        self.assertEqual(str(e), "Foo: 白話")

    def test_plain_values_untouched(self):
        ctx = self.ctx({})
        for v in ("s", 1, 1.5, True, None, [1, {"$env": "X"}], {"a": {"$env": "X"}}):
            self.assertIs(resolve(v, ctx, ["x"]), v)

    def test_is_directive(self):
        self.assertTrue(is_directive({"$env": "X"}))
        self.assertTrue(is_directive({"$opt": "a"}))
        self.assertTrue(is_directive({"$xyz": 1}))
        self.assertFalse(is_directive({"a": 1}))
        self.assertFalse(is_directive({}))
        self.assertFalse(is_directive("$env"))
        self.assertFalse(is_directive(["$env"]))

    def test_is_option_object(self):
        self.assertTrue(is_option_object({"$opt": "a"}))
        self.assertTrue(is_option_object({"$opt": None}))
        self.assertFalse(is_option_object({"$env": "X"}))
        self.assertFalse(is_option_object("x"))

    def test_unknown_directive(self):
        self.fails("UnknownDirective", resolve, {"$xyz": 1}, self.ctx({}), ["x"])
        self.fails("UnknownDirective", resolve, {"$xyz": 1, "a": 2}, self.ctx({}), [])

    def test_resolve_located_plain(self):
        ctx = self.ctx({})
        loc = resolve_located("v", ctx, ["a", "b"])
        self.assertEqual(loc.value, "v")
        self.assertIs(loc.ctx.doc, ctx.doc)
        self.assertEqual(loc.position, ["a", "b"])

    def test_load_document(self):
        p = self.write("a.json", {"x": 1})
        doc = load_document(p)
        self.assertEqual(doc.root, {"x": 1})
        self.assertEqual(doc.path, os.path.realpath(p))
        self.assertEqual(doc.ident, doc.path)

    def test_load_document_read_failed(self):
        self.fails("ReferenceReadFailed", load_document, os.path.join(self.d, "nope.json"))

    def test_load_document_json_invalid(self):
        p = self.write("bad.json", "{not json", raw=True)
        self.fails("ReferenceJsonInvalid", load_document, p)

    def test_context_defaults(self):
        p = self.write("a.json", {})
        c = Context(load_document(p))
        self.assertEqual(c.base_dir, self.d)
        self.assertIs(c.env, os.environ)
        c2 = Context(Document(None, {}))
        self.assertEqual(c2.base_dir, os.getcwd())

    def test_context_child(self):
        c = self.ctx({}, env={"A": "1"})
        other = Document(None, {"z": 1})
        c2 = c.child(doc=other)
        self.assertIs(c2.doc, other)
        self.assertEqual(c2.base_dir, self.d)
        self.assertEqual(c2.env, {"A": "1"})
        c3 = c.child(base_dir="/tmp", env={"B": "2"})
        self.assertIs(c3.doc, c.doc)
        self.assertEqual((c3.base_dir, c3.env), ("/tmp", {"B": "2"}))

    def test_memory_docs_have_distinct_identity(self):
        a, b = Document(None, {}), Document(None, {})
        self.assertNotEqual(a.ident, b.ident)


# ---------------------------------------------------------------- $env ----

class TestEnv(Base):

    def test_env(self):
        self.assertEqual(resolve({"$env": "A"}, self.ctx({}, {"A": "hi"}), ["x"]), "hi")

    def test_env_empty_is_empty_string(self):
        self.assertEqual(resolve({"$env": "A"}, self.ctx({}, {"A": ""}), ["x"]), "")

    def test_env_missing(self):
        self.fails("EnvironmentVariableMissing", resolve, {"$env": "A"}, self.ctx({}, {}), ["x"])

    def test_env_value_not_string(self):
        self.fails("DirectiveValueTypeMismatch", resolve, {"$env": 1}, self.ctx({}, {}), ["x"])
        self.fails("DirectiveValueTypeMismatch", resolve, {"$env": ["A"]}, self.ctx({}, {}), ["x"])

    def test_env_uses_ctx_env_not_os_environ(self):
        os.environ["AOS_DIRECTIVES_TEST_X"] = "from-os"
        self.addCleanup(os.environ.pop, "AOS_DIRECTIVES_TEST_X", None)
        self.fails("EnvironmentVariableMissing", resolve,
                   {"$env": "AOS_DIRECTIVES_TEST_X"}, self.ctx({}, {}), ["x"])
        c = Context(Document(None, {}), base_dir=self.d)     # 沒給 env ＝ os.environ
        self.assertEqual(resolve({"$env": "AOS_DIRECTIVES_TEST_X"}, c, ["x"]), "from-os")

    def test_env_extra_keys_ignored(self):
        self.assertEqual(resolve({"$env": "A", "_note": "說明", "x": 1},
                                 self.ctx({}, {"A": "hi"}), ["x"]), "hi")


# ---------------------------------------------------------------- $fmt ----

class TestFmt(Base):

    def test_fmt_basic(self):
        v = {"$fmt": {"$val": "aaa${xxx}, bbb${zzz}", "xxx": {"$env": "yyy"}, "zzz": "haha"}}
        self.assertEqual(resolve(v, self.ctx({}, {"yyy": "Y"}), ["x"]), "aaaY, bbbhaha")

    def test_fmt_no_variables(self):
        self.assertEqual(resolve({"$fmt": {"$val": "plain"}}, self.ctx({}), ["x"]), "plain")

    def test_fmt_lone_dollar_and_bare_name_are_literal(self):
        v = {"$fmt": {"$val": "a $ b $NAME c ${n}", "n": "N"}}
        self.assertEqual(resolve(v, self.ctx({}), ["x"]), "a $ b $NAME c N")

    def test_fmt_no_rescan(self):
        v = {"$fmt": {"$val": "${a}|${b}", "a": "${b}", "b": "B"}}
        self.assertEqual(resolve(v, self.ctx({}), ["x"]), "${b}|B")

    def test_fmt_unused_variable_ok(self):
        v = {"$fmt": {"$val": "x", "unused": {"$env": "A"}}}
        self.assertEqual(resolve(v, self.ctx({}, {"A": "1"}), ["x"]), "x")

    def test_fmt_unused_variable_still_resolved(self):
        """定義了沒用到也會被解（缺環境變數照樣報）。"""
        v = {"$fmt": {"$val": "x", "unused": {"$env": "NOPE"}}}
        self.fails("EnvironmentVariableMissing", resolve, v, self.ctx({}, {}), ["x"])

    def test_fmt_unknown_variable(self):
        v = {"$fmt": {"$val": "${nope}", "a": "1"}}
        self.fails("UnknownFormatVariable", resolve, v, self.ctx({}), ["x"])

    def test_fmt_empty_braces_is_unknown_variable(self):
        self.fails("UnknownFormatVariable", resolve, {"$fmt": {"$val": "${}"}}, self.ctx({}), ["x"])

    def test_fmt_value_not_object(self):
        for bad in ("${a}", 1, ["$val"], None):
            self.fails("DirectiveValueTypeMismatch", resolve, {"$fmt": bad}, self.ctx({}), ["x"])

    def test_fmt_missing_val(self):
        self.fails("DirectiveValueTypeMismatch", resolve, {"$fmt": {"a": "1"}}, self.ctx({}), ["x"])

    def test_fmt_val_resolved_not_string(self):
        v = {"$fmt": {"$val": {"$ref": "", "$at": "/n"}}}
        self.fails("DirectiveValueTypeMismatch", resolve, v, self.ctx({"n": 1}), ["x"])

    def test_fmt_variable_resolved_not_string(self):
        v = {"$fmt": {"$val": "${a}", "a": {"$ref": "", "$at": "/n"}}}
        self.fails("DirectiveValueTypeMismatch", resolve, v, self.ctx({"n": [1]}), ["x"])
        v = {"$fmt": {"$val": "${a}", "a": 1}}
        self.fails("DirectiveValueTypeMismatch", resolve, v, self.ctx({}), ["x"])

    def test_fmt_bad_variable_names(self):
        for name in ("$x", "", "a{b", "a}b", "$val2"):
            v = {"$fmt": {"$val": "x", name: "1"}}
            self.fails("FormatVariableInvalid", resolve, v, self.ctx({}), ["x"])

    def test_fmt_val_as_directive(self):
        v = {"$fmt": {"$val": {"$env": "T"}, "a": "A"}}
        self.assertEqual(resolve(v, self.ctx({}, {"T": "<${a}>"}), ["x"]), "<A>")

    def test_fmt_nested_fmt_as_variable(self):
        v = {"$fmt": {"$val": "[${a}]",
                      "a": {"$fmt": {"$val": "${b}-${c}", "b": "B", "c": {"$env": "C"}}}}}
        self.assertEqual(resolve(v, self.ctx({}, {"C": "C"}), ["x"]), "[B-C]")

    def test_fmt_ref_as_variable_from_file(self):
        self.write("v.json", {"name": "world"})
        v = {"$fmt": {"$val": "hello ${n}", "n": {"$ref": "v.json", "$at": "/name"}}}
        self.assertEqual(resolve(v, self.ctx({}), ["x"]), "hello world")

    def test_fmt_variable_positions(self):
        """變數在 <這格>/$fmt/名字、模板在 <這格>/$fmt/$val：變數之間用 ../ 互指。"""
        root = {"greet": {"$fmt": {"$val": "${a}", "a": {"$ref": "", "$at": "../b"}, "b": "sib"}}}
        self.assertEqual(resolve(root["greet"], self.ctx(root), ["greet"]), "sib")
        root = {"greet": {"$fmt": {"$val": {"$ref": "", "$at": "../t"}, "t": "tpl ${a}", "a": "A"}}}
        self.assertEqual(resolve(root["greet"], self.ctx(root), ["greet"]), "tpl A")
        # 絕對位置也走得到同一個地方
        root = {"greet": {"$fmt": {"$val": "${a}", "a": {"$ref": "", "$at": "/greet/$fmt/b"}, "b": "abs"}}}
        self.assertEqual(resolve(root["greet"], self.ctx(root), ["greet"]), "abs")

    def test_fmt_extra_keys_outside_are_ignored_but_inside_are_variables(self):
        # 外層 `_note` 忽略；內層 `_note` 是變數名（合法名字）
        v = {"$fmt": {"$val": "${_note}", "_note": "in"}, "_note": "out"}
        self.assertEqual(resolve(v, self.ctx({}), ["x"]), "in")


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


# ---------------------------------------------------------------- 優先序／混寫 ----

class TestPrecedence(Base):

    def test_ref_beats_fmt(self):
        """$fmt 是壞的（不是物件）也不會被看。"""
        self.write("a.json", {"k": "from-ref"})
        v = {"$ref": "a.json", "$at": "/k", "$fmt": "bad"}
        self.assertEqual(resolve(v, self.ctx({}), ["v"]), "from-ref")

    def test_ref_beats_env(self):
        self.write("a.json", "from-ref")
        self.assertEqual(resolve({"$ref": "a.json", "$env": "NOPE"}, self.ctx({}, {}), ["v"]), "from-ref")

    def test_fmt_beats_env(self):
        v = {"$fmt": {"$val": "F"}, "$env": "NOPE"}
        self.assertEqual(resolve(v, self.ctx({}, {}), ["v"]), "F")

    def test_opt_beats_everything_returned_untouched(self):
        v = {"$opt": "x", "$ref": "nope.json", "$fmt": 1, "$env": "NOPE", "$val": {"$env": "A"}}
        self.assertIs(resolve(v, self.ctx({}, {}), ["v"]), v)

    def test_unknown_dollar_key_with_known_is_fine(self):
        self.assertEqual(resolve({"$env": "A", "$zzz": 1}, self.ctx({}, {"A": "a"}), ["v"]), "a")


# ---------------------------------------------------------------- 選項物件 ----

TABLE = {
    "append": {"val": "required"},
    "mkdir": {"val": "required"},
    "inherit": {"val": "forbidden", "alone": True},
    "clear": {"val": "optional"},
    "bare": {},
}


class TestSplitOption(Base):

    def test_not_option_object(self):
        for v in ("s", 1, None, [1], {"a": 1}, {"$env": "X"}):
            self.assertEqual(split_option(v), Option(False, None, v, True))

    def test_opt_any_json_passes_through(self):
        for raw in ("name", 1, 1.5, True, None, ["a", "b"], {"k": {"$env": "X"}}, [], ""):
            o = split_option({"$opt": raw})
            self.assertEqual(o, Option(True, raw, None, False))
            self.assertIs(o.opt, raw) if not isinstance(raw, (int, float, str)) else None

    def test_val_present_and_untouched(self):
        val = {"$env": "P"}
        o = split_option({"$opt": "x", "$val": val})
        self.assertTrue(o.has_val)
        self.assertIs(o.val, val)

    def test_val_null_counts_as_present(self):
        self.assertEqual(split_option({"$opt": "x", "$val": None}), Option(True, "x", None, True))

    def test_extra_keys_ignored(self):
        o = split_option({"$opt": "x", "$envs": {"A": "1"}, "$ref": "nope", "_note": "n"})
        self.assertEqual(o, Option(True, "x", None, False))


class TestOptionNames(Base):

    def test_single_and_array(self):
        self.assertEqual(option_names("bare", False, ["p"], TABLE), frozenset({"bare"}))
        self.assertEqual(option_names(["append", "mkdir"], True, ["p"], TABLE),
                         frozenset({"append", "mkdir"}))

    def test_type_mismatch(self):
        for raw in (1, None, [], ["a", 1], [1], {"a": 1}, True):
            self.fails("DirectiveValueTypeMismatch", option_names, raw, False, ["p"], TABLE)

    def test_unknown(self):
        self.fails("UnknownOption", option_names, "nope", False, ["p"], TABLE)
        self.fails("UnknownOption", option_names, "Append", False, ["p"], TABLE)   # 區分大小寫

    def test_duplicate(self):
        e = self.fails("UnknownOption", option_names, ["append", "append"], True, ["p"], TABLE)
        self.assertIn("重複", str(e))

    def test_empty_table(self):
        e = self.fails("UnknownOption", option_names, "append", True, ["argv", "0"], {})
        self.assertIn("沒有任何選項", str(e))

    def test_val_required(self):
        self.fails("OptionConflict", option_names, "append", False, ["p"], TABLE)
        self.assertEqual(option_names("append", True, ["p"], TABLE), frozenset({"append"}))

    def test_val_forbidden(self):
        self.fails("OptionConflict", option_names, "inherit", True, ["p"], TABLE)
        self.assertEqual(option_names("inherit", False, ["p"], TABLE), frozenset({"inherit"}))

    def test_val_optional(self):
        self.assertEqual(option_names("clear", False, ["p"], TABLE), frozenset({"clear"}))
        self.assertEqual(option_names("clear", True, ["p"], TABLE), frozenset({"clear"}))

    def test_alone(self):
        self.fails("OptionConflict", option_names, ["inherit", "append"], True, ["p"], TABLE)
        self.fails("OptionConflict", option_names, ["append", "inherit"], True, ["p"], TABLE)

    def test_bad_table_is_programming_error(self):
        with self.assertRaises(ValueError):
            option_names("x", False, ["p"], {"x": {"val": "require"}})


class TestParseOptions(Base):

    def test_passthrough(self):
        for v in ("s", 1, None, {"a": 1}, {"$env": "X"}):
            self.assertEqual(parse_options(v, ["p"], TABLE), (frozenset(), v, True))

    def test_compose(self):
        val = {"$env": "P"}
        self.assertEqual(parse_options({"$opt": ["append", "mkdir"], "$val": val}, ["p"], TABLE),
                         (frozenset({"append", "mkdir"}), val, True))
        self.assertEqual(parse_options({"$opt": "inherit"}, ["p"], TABLE),
                         (frozenset({"inherit"}), None, False))

    def test_errors_propagate(self):
        self.fails("UnknownOption", parse_options, {"$opt": "nope"}, ["p"], TABLE)
        self.fails("OptionConflict", parse_options, {"$opt": "append"}, ["p"], TABLE)
        self.fails("DirectiveValueTypeMismatch", parse_options, {"$opt": 1}, ["p"], TABLE)

    def test_host_flow(self):
        """宿主的典型流程：解這格 → 拆選項 → 再解 $val。"""
        self.write("o.json", {"$opt": ["append", "mkdir"], "$val": {"$fmt": {"$val": "${d}/out.txt", "d": {"$env": "D"}}}})
        c = self.ctx({}, {"D": "/tmp/x"})
        loc = resolve_located({"$ref": "o.json"}, c, ["stdout"])
        names, val, has_val = parse_options(loc.value, loc.position, TABLE)
        self.assertEqual(names, frozenset({"append", "mkdir"}))
        self.assertTrue(has_val)
        self.assertEqual(resolve(val, loc.ctx, loc.position + ["$val"]), "/tmp/x/out.txt")


if __name__ == "__main__":
    unittest.main()
