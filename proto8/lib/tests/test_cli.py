"""proto8/lib 的自動測試：aos_cli（命令列、JSON 串流）。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests
"""
import io
import os
import unittest
from unittest import mock

from helpers import Tmp
import aos_cli  # noqa: E402


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
        """值的雙形（C-55）：純值包成 {"val": 值}、物件照抄一份、None 照回；key 可換。"""
        self.assertEqual(aos_cli.expand(3), {"val": 3})
        self.assertEqual(aos_cli.expand(False), {"val": False})
        d = {"val": "low", "deadline": 1}
        self.assertEqual(aos_cli.expand(d), d)
        self.assertIsNot(aos_cli.expand(d), d)
        self.assertIsNone(aos_cli.expand(None))
        self.assertEqual(aos_cli.expand("x", key="k"), {"k": "x"})

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
                self.assertRaises(aos_cli.CliError) as c:            # 多份＝入口錯（10-15 使用者「都按照推薦。」）
            aos_cli.config(["-"], set())
        self.assertEqual(c.exception.code, "InputExtra")
        self.assertEqual(aos_cli.config([], set()), ({}, None, False, None))
        with self.assertRaises(aos_cli.CliError) as c:
            aos_cli.config([path + "#/times"], set())
        self.assertEqual(c.exception.code, "FieldType")


if __name__ == "__main__":
    unittest.main()
