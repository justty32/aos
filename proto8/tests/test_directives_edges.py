"""aos_directives 的測試：proto6 之後在 proto7-2 補的兩處修正（陣列索引的邊緣、`$at` 寫 null）。

原本散在 proto7-2/tests/core/test_exits.py、test_mount_dyn.py，這裡只留直接打函式庫的部分。
"""
import unittest

from aos_directives import Context, DirectiveError, Document, resolve


class TestArrayIndexEdges(unittest.TestCase):
    """`$ref` 位置裡的陣列索引：前導零照收、超長索引與非 ASCII 數字一律 ReferencePointerInvalid。"""

    def setUp(self):
        self.ctx = Context(Document(None, {"a": [7, 8]}))

    def test_leading_zero_index_resolves(self):
        self.assertEqual(resolve({"$ref": "#/a/0001"}, self.ctx, ["v"]), 8)
        self.assertEqual(resolve({"$ref": "", "$at": "/a/" + "0" * 5000 + "1"}, self.ctx, ["v"]), 8)

    def test_giant_index_is_pointer_error(self):
        for digits in (20, 4300, 5000):
            with self.subTest(digits=digits):
                with self.assertRaises(DirectiveError) as cm:
                    resolve({"$ref": "#/a/" + "9" * digits}, self.ctx, ["v"])
                self.assertEqual(cm.exception.code, "ReferencePointerInvalid")

    def test_non_ascii_digit_is_pointer_error(self):
        for digit in ("²", "١"):
            for directive in ({"$ref": "#/a/" + digit}, {"$ref": "", "$at": "/a/" + digit}):
                with self.subTest(directive=directive):
                    with self.assertRaises(DirectiveError) as cm:
                        resolve(directive, self.ctx, ["v"])
                    self.assertEqual(cm.exception.code, "ReferencePointerInvalid")


class TestAtNull(unittest.TestCase):
    """`$at` 明寫 null 要拒絕，不能當成省略而取整份文件。"""

    def test_at_null_is_type_mismatch(self):
        doc = Document(None, {"value": "whole document"})
        ctx = Context(doc)
        self.assertEqual(resolve({"$ref": ""}, ctx, ["v"]), doc.root)
        with self.assertRaises(DirectiveError) as cm:
            resolve({"$ref": "", "$at": None}, ctx, ["v"])
        self.assertEqual(cm.exception.code, "DirectiveValueTypeMismatch")


if __name__ == "__main__":
    unittest.main()
