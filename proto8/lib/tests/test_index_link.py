# index paths and $ref share one "string -> place" rule after #: ".." steps out one level, stepping out of the root object
# lands in the folder of the file. The table is the one aos-directive runs (impls/aos-directive/tests/ref_spot_cases.json).
import json
import os
import sys
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB)
import aos_index  # noqa: E402

CASES = os.path.join(os.path.dirname(LIB), "impls", "aos-directive", "tests", "ref_spot_cases.json")


class IndexLink(unittest.TestCase):
    def test_shared_table(self):
        with open(CASES) as f:
            cases = json.load(f)
        self.assertGreater(len(cases), 20)
        for c in cases:
            with self.subTest(text=c["text"]):
                self.assertEqual(aos_index.link(c["at"], c["text"]), c["to"])

    def test_from_inside_an_object(self):
        at = "kb/v.json#/o/p/_index"                      # 容器＝物件 kb/v.json#/o/p
        for text, to in (("#/../other.json", "kb/other.json"), ("#/../other.json#/k", "kb/other.json#/k"),
                         ("#/a/../b", "kb/v.json#/b"), ("#/a/..", "kb/v.json"), ("#/..", "kb"),
                         ("../../../x.json#/a/../../y.json#/_index", "kb/y.json#/_index"),
                         ("../r/_index", "kb/v.json#/o/r/_index"), ("w.json#/_index", None), ("../w.json#/../x", None)):
            with self.subTest(text=text):
                self.assertEqual(aos_index.link(at, text), to)


if __name__ == "__main__":
    unittest.main()
