"""$ref：一層、巢狀、循環，還有「相對路徑以 cwd 為中心」這件事。"""
import os
import unittest

from _util import ExecCase


class TestRef(ExecCase):

    def test_ref_one_level(self):
        self.write("vals.json", '{"msg": "從別的檔來的"}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "vals.json#/msg"}}})
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
        self.write("a.json", '{"next": {"$ref": "b.json#/deep/1"}}')
        self.write("b.json", '{"deep": ["不是這個", "是這個"]}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "stdout": "out.txt",
                   "envs": {"M": {"$ref": "a.json#/next"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("out.txt"), "是這個\n")

    def test_ref_cycle_is_1(self):
        self.write("a.json", '{"x": {"$ref": "b.json#/y"}}')
        self.write("b.json", '{"y": {"$ref": "a.json#/x"}}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "a.json#/x"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferenceCycle", r.stderr)

    def test_ref_missing_file_is_1(self):
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "nope.json#/x"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferenceReadFailed", r.stderr)

    def test_ref_bad_pointer_is_1(self):
        self.write("vals.json", '{"msg": "有"}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "vals.json#/沒有"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferencePointerInvalid", r.stderr)

    def test_ref_to_array_is_1(self):
        self.write("vals.json", '{"msg": ["不能是陣列"]}')
        self.inst({"argv": ["true"], "envs": {"M": {"$ref": "vals.json#/msg"}}})
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ReferenceValueInvalid", r.stderr)

    def test_ref_is_relative_to_cwd(self):
        """cwd 設成 sub 之後，$ref 的相對路徑也跟著落在 sub 裡（不是 xxx）。"""
        self.write("vals.json", '{"msg": "xxx 底下那份（不該讀到）"}')
        self.write("sub/vals.json", '{"msg": "cwd 底下那份"}')
        self.inst({"argv": ["sh", "-c", "echo $M"], "cwd": "sub", "stdout": "out.txt",
                   "envs": {"M": {"$ref": "vals.json#/msg"}}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), "cwd 底下那份\n")

    def test_cwd_own_ref_is_relative_to_xxx(self):
        """`cwd` 自己是最先解的，它的 $ref 只能以 xxx 為中心。"""
        self.write("where.json", '{"c": "sub"}')
        self.write("sub/.keep", "")
        self.inst({"argv": ["sh", "-c", "pwd"], "cwd": {"$ref": "where.json#/c"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("sub/out.txt"), os.path.join(self.d, "sub") + "\n")

    def test_ref_in_argv_and_paths(self):
        self.write("vals.json", '{"word": "從 argv 來的", "out": "named.txt"}')
        self.inst({"argv": ["echo", {"$ref": "vals.json#/word"}],
                   "stdout": {"$ref": "vals.json#/out"}})
        self.assertEqual(self.aos(self.d).returncode, 0)
        self.assertEqual(self.read("named.txt"), "從 argv 來的\n")


if __name__ == "__main__":
    unittest.main()
