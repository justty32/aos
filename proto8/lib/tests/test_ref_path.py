# The shared "path string -> (file, pointer)" rule (aos_refpath.spot): left of # is the file system, right of # is inside the json.
# One row of ref_path_cases.json per rule of thinking 2026-11/13/ref-path-rules (each kind of error has its own row).
import json
import os
import sys
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB)
import aos_refpath  # noqa: E402

CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_path_cases.json")


class RefPath(unittest.TestCase):
    def test_table(self):
        with open(CASES) as f:
            cases = json.load(f)["cases"]
        self.assertGreater(len(cases), 40)
        for c in cases:
            with self.subTest(rule=c["rule"], text=c["text"]):
                if "err" in c:
                    want = aos_refpath.RefPathBad if c["err"] == "bad" else aos_refpath.RefPathUnknown
                    with self.assertRaises(want):
                        aos_refpath.spot(c["text"], c["file"], c["here"])
                else:
                    self.assertEqual(aos_refpath.shown(*aos_refpath.spot(c["text"], c["file"], c["here"])), c["to"])

    def test_return_shape(self):
        self.assertEqual(aos_refpath.spot("x.json", "kb/m.json", []), ("kb/x.json", None))   # 檔案系統那一段就是全部
        self.assertEqual(aos_refpath.spot("x.json#/", "kb/m.json", []), ("kb/x.json", []))   # 整份 json
        self.assertEqual(aos_refpath.spot("#", "kb/m.json", ["o"]), ("kb/m.json", []))
        self.assertEqual(aos_refpath.spot("#/a//b", "kb/m.json", []), ("kb/m.json", ["a", "", "b"]))

    def test_not_a_string(self):
        for v in (None, 3, ["x.json"], {"a": 1}):
            with self.subTest(v=v), self.assertRaises(aos_refpath.RefPathBad):
                aos_refpath.spot(v, "kb/m.json", [])

    def test_folder_overrides_the_file_folder(self):
        self.assertEqual(aos_refpath.spot("x.json", None, None, folder="cfg"), ("cfg/x.json", None))
        self.assertEqual(aos_refpath.spot("x.json", None, None), ("x.json", None))

    def test_errors_are_value_errors_with_the_text(self):
        for text in ("#aaa", "y.json#./k", "#../../x"):
            with self.subTest(text=text):
                try:
                    aos_refpath.spot(text, "kb/m.json", ["o"])
                except ValueError as e:
                    self.assertIn(text, str(e))
                else:
                    self.fail("no error")


if __name__ == "__main__":
    unittest.main()
