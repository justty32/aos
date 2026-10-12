"""aos_directives 的測試：每條規則、每個錯誤代號都要有一條。

本檔：基本、$env、$fmt、優先序（TestBasics、TestEnv、TestFmt、TestPrecedence）。

純記憶體文件用 `Document(None, root)`；要測跨檔的用暫存資料夾寫真檔。
"""
import os
import unittest

from _directives_util import Base

from aos_directives import (
    DirectiveError, Document, Context, load_document, is_directive, is_option_object, resolve,
    resolve_located,
)


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


if __name__ == "__main__":
    unittest.main()
