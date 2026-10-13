"""proto8/lib 的自動測試：指示詞（aos_directives）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。
"""
import os
import unittest

from helpers import Tmp
from aos_directives import DirectiveError, resolve, split_target, target_id  # noqa: E402


class Directives(Tmp):
    def code(self, doc):
        with self.assertRaises(DirectiveError) as c:
            resolve(doc, self.tmp)
        return c.exception.code

    def test_ref_env_at(self):
        self.write("a.json", {"x": [1, {"y": "z"}]})
        os.environ["AOS_TEST_V"] = "v"
        doc = {"f": {"$ref": "a.json#/x/1/y"}, "g": {"$ref": "a.json", "$at": "/x/0"},
               "h": {"$env": "AOS_TEST_V"}, "i": {"$ref": "#/g"}, "j": {"k": {"$ref": "#../../h"}}}
        self.assertEqual(resolve(doc, self.tmp), {"f": "z", "g": 1, "h": "v", "i": 1, "j": {"k": "v"}})
        self.assertIn("$ref", doc["f"])

    def test_errors(self):
        self.write("bad.json", "{")
        self.assertEqual(self.code({"$nope": 1}), "UnknownDirective")
        self.assertEqual(self.code({"$env": 1}), "DirectiveValueTypeMismatch")
        self.assertEqual(self.code({"$env": "AOS_TEST_NO_SUCH_VAR"}), "EnvironmentVariableMissing")
        self.assertEqual(self.code({"$ref": "missing.json"}), "ReferenceReadFailed")
        self.assertEqual(self.code({"$ref": "bad.json"}), "ReferenceJsonInvalid")
        self.assertEqual(self.code({"a": 1, "b": {"$ref": "#/c"}}), "ReferencePointerInvalid")
        self.assertEqual(self.code({"a": {"$ref": "#/a"}}), "ReferenceCycle")
        self.assertEqual(self.code({"a": {"b": {"$ref": "#/a"}}}), "ReferenceCycle")

    def test_ref_path_like_filesystem(self):
        self.write("x.json", {"k": 1})
        # $ref 跟命令列同一套：# 、#/ ＝整份，結尾 / 忽略，空字串 key 指不到（10-13 使用者定甲）
        self.assertEqual(resolve({"a": {"$ref": "x.json#"}, "b": {"$ref": "x.json#/"}}, self.tmp),
                         {"a": {"k": 1}, "b": {"k": 1}})
        self.assertEqual(resolve({"a": {"$ref": "x.json#/k/"}}, self.tmp), {"a": 1})
        self.assertEqual(self.code({"": 1, "a": {"$ref": "#/"}}), "ReferenceCycle")


    def test_split_target_and_window(self):
        # 檔#/位置：遇第一個 # 就切；空的或只有 / ＝整份；位置只認 / 開頭；id 用正規化過的位置
        self.assertEqual(split_target("a.json"), ("a.json", ()))
        self.assertEqual(split_target("a.json#"), ("a.json", ()))
        self.assertEqual(split_target("a.json#/"), ("a.json", ()))
        self.assertEqual(split_target("a.json#/x/"), ("a.json", ("x",)))     # 像檔案系統：結尾 / 、空段落忽略
        self.assertEqual(split_target("a.json#/x//y"), ("a.json", ("x", "y")))
        self.assertEqual(split_target("a#/b#c"), ("a", ("b#c",)))       # 第一個 # 之後的 # 是位置的一部分
        self.assertEqual(split_target("a.json#/x~1y/0"), ("a.json", ("x/y", "0")))
        self.assertEqual(target_id("/r.json", split_target("a.json#/x/./z/../y")[1]), "/r.json#/x/y")
        self.assertEqual(target_id("/r.json", ()), "/r.json")
        for bad in ("a.json#x", "a.json#./x", "a.json#/..", "a#b.json"):
            with self.subTest(bad=bad), self.assertRaises(DirectiveError) as c:
                split_target(bad)
            self.assertEqual(c.exception.code, "ReferencePointerInvalid")
        # 視窗：裡面的 $ref 照整份檔的位置算（../ 摸到旁邊、#/ 是檔的根），不是切下來
        doc = {"a": {"b": {"$ref": "#../../c"}, "d": {"$ref": "#/c"}}, "c": 1}
        self.assertEqual(resolve(doc, self.tmp, "<x>", ("a",)), {"b": 1, "d": 1})
        self.assertEqual(self.code_at({"a": {"b": {"$ref": "#/a"}}}, ("a",)), "ReferenceCycle")
        self.assertEqual(self.code_at({"a": {}}, ("nope",)), "ReferencePointerInvalid")

    def code_at(self, doc, at):
        with self.assertRaises(DirectiveError) as c:
            resolve(doc, self.tmp, "<x>", at)
        return c.exception.code


if __name__ == "__main__":
    unittest.main()
