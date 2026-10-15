"""proto8/lib 的自動測試：aos_cli（命令列、JSON 串流、`檔#/位置`、指示詞）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests
"""
import io
import os
import unittest
from unittest import mock

from helpers import Tmp
import aos_cli  # noqa: E402
from aos_cli import CliError, resolve, split_target, target_id  # noqa: E402


class Cli(Tmp):
    def test_parse_argv(self):
        flags = {"times", "cwd", "id"}
        self.assertEqual(aos_cli.parse_argv(["--times", "3", "x.json", "--cwd", "a b"], flags),
                         ("x.json", {"times": 3, "cwd": "a b"}, None))
        self.assertEqual(aos_cli.parse_argv(["--times", "null", "-", "--", "echo", "--times"], flags),
                         ("-", {"times": None}, ["echo", "--times"]))
        for bad, code in ((["--nope", "1"], "FlagUnknown"), (["--times"], "Usage"), (["a", "b"], "Usage")):
            with self.subTest(bad=bad), self.assertRaises(aos_cli.CliError) as c:
                aos_cli.parse_argv(bad, flags)
            self.assertEqual(c.exception.code, code)

    def test_expand(self):
        """值的雙形（C-55）：純值包成 {"val": 值}、物件照抄一份、None 照回。"""
        self.assertEqual(aos_cli.expand(3), {"val": 3})
        self.assertEqual(aos_cli.expand(False), {"val": False})
        d = {"val": "low", "deadline": 1}
        self.assertEqual(aos_cli.expand(d), d)
        self.assertIsNot(aos_cli.expand(d), d)
        self.assertIsNone(aos_cli.expand(None))

    def test_read_stream(self):
        self.assertEqual(aos_cli.read_stream('{"a": 1}\n{\n "b": 2\n} 3 {"bad'), [{"a": 1}, {"b": 2}, 3])
        self.assertEqual(aos_cli.read_stream("  \n"), [])

    def test_config_sources(self):
        path = self.write("c.json", {"times": 2, "cwd": "x", "node": {"times": 5}})
        doc, ident, piped, rest = aos_cli.config(["--times", "4", path], {"times"})
        self.assertEqual((doc["times"], ident, piped, rest), (4, os.path.realpath(path), False, None))
        self.assertEqual(aos_cli.config([path + "#/node"], set())[1], os.path.realpath(path) + "#/node")
        with mock.patch("sys.stdin", io.StringIO('{"times": 1, "id": "me"}')):
            doc, ident, piped, _ = aos_cli.config(["-"], set())
        self.assertEqual((doc, ident, piped), ({"times": 1, "id": "me"}, "me", True))
        with mock.patch("sys.stdin", io.StringIO('{"times": 1, "id": "me"} {"x": 2}')), \
                self.assertRaises(aos_cli.CliError) as c:            # 多份＝入口錯
            aos_cli.config(["-"], set())
        self.assertEqual(c.exception.code, "InputExtra")
        self.assertEqual(aos_cli.config([], set()), ({}, None, False, None))
        with self.assertRaises(aos_cli.CliError) as c:
            aos_cli.config([path + "#/times"], set())
        self.assertEqual(c.exception.code, "FieldType")


class Directives(Tmp):
    def code(self, doc):
        with self.assertRaises(CliError) as c:
            resolve(doc, self.tmp)
        return c.exception.code

    def test_ref_env(self):
        self.write("a.json", {"x": [1, {"y": "z"}], "w": {"$ref": "b.json#/k"}})
        self.write("b.json", {"k": "v"})
        os.environ["AOS_TEST_V"] = "v"
        doc = {"f": {"$ref": "a.json#/x/1/y"}, "g": {"$ref": "a.json#/x/0"}, "h": {"$env": "AOS_TEST_V"},
               "i": {"$ref": "a.json#/w"}}                           # 取回來的接著解（照 a.json 所在的檔算）
        self.assertEqual(resolve(doc, self.tmp), {"f": "z", "g": 1, "h": "v", "i": "v"})
        self.assertIn("$ref", doc["f"])

    def test_errors_one_code(self):
        # 指示詞的錯一種代號 DirectiveBad；位置走不到＝PointerBad
        self.write("bad.json", "{")
        self.write("c1.json", {"a": {"$ref": "c2.json#/b"}})
        self.write("c2.json", {"b": {"$ref": "c1.json#/a"}})
        for doc in ({"$nope": 1}, {"$env": 1}, {"$env": "AOS_TEST_NO_SUCH_VAR"}, {"$ref": "missing.json"},
                    {"$ref": "bad.json"}, {"$ref": "#/a"}, {"$ref": "c1.json#/a"}):
            with self.subTest(doc=doc):
                self.assertEqual(self.code(doc), "DirectiveBad")
        self.write("x.json", {"k": 1})
        self.assertEqual(self.code({"b": {"$ref": "x.json#/c"}}), "PointerBad")

    def test_ref_path_like_filesystem(self):
        self.write("x.json", {"k": 1})
        # # 、#/ ＝整份，結尾 / 忽略，空字串 key 指不到
        self.assertEqual(resolve({"a": {"$ref": "x.json#"}, "b": {"$ref": "x.json#/"}}, self.tmp),
                         {"a": {"k": 1}, "b": {"k": 1}})
        self.assertEqual(resolve({"a": {"$ref": "x.json#/k/"}}, self.tmp), {"a": 1})

    def test_split_target_and_window(self):
        # 檔#/位置：遇第一個 # 就切；空的或只有 / ＝整份；位置只認 / 開頭、從根算
        self.assertEqual(split_target("a.json"), ("a.json", ()))
        self.assertEqual(split_target("a.json#"), ("a.json", ()))
        self.assertEqual(split_target("a.json#/"), ("a.json", ()))
        self.assertEqual(split_target("a.json#/x/"), ("a.json", ("x",)))
        self.assertEqual(split_target("a.json#/x//y"), ("a.json", ("x", "y")))
        self.assertEqual(split_target("a#/b#c"), ("a", ("b#c",)))       # 第一個 # 之後的 # 是位置的一部分
        self.assertEqual(target_id("/r.json", ("x", "y")), "/r.json#/x/y")
        self.assertEqual(target_id("/r.json", ()), "/r.json")
        for bad in ("a.json#x", "a.json#./x", "a#b.json"):
            with self.subTest(bad=bad), self.assertRaises(CliError) as c:
                split_target(bad)
            self.assertEqual(c.exception.code, "PointerBad")
        # 視窗：只解那一格，裡面的 $ref 照自己的檔算
        self.write("c.json", {"c": 1})
        doc = {"a": {"b": {"$ref": "c.json#/c"}}, "d": {"$ref": "nope.json"}}
        self.assertEqual(resolve(doc, self.tmp, "<x>", ("a",)), {"b": 1})
        with self.assertRaises(CliError) as c:
            resolve({"a": {}}, self.tmp, "<x>", ("nope",))
        self.assertEqual(c.exception.code, "PointerBad")


if __name__ == "__main__":
    unittest.main()
