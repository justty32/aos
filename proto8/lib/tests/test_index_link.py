# index paths and $ref share one rule and one parser (aos_refpath.spot): left of # is the file system, right of # is inside the json.
# The table is the one aos-directive also runs (lib/tests/ref_path_cases.json); here only "which object is it written in" is index's own.
import json
import os
import sys
import unittest

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, LIB)
import aos_index  # noqa: E402

CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_path_cases.json")


class IndexLink(unittest.TestCase):
    def test_shared_table(self):
        with open(CASES) as f:
            cases = json.load(f)["cases"]
        n = 0
        for c in cases:
            if c["file"] is None or c["here"] is None:
                continue                                   # index always knows its file and where it is
            where = "%s#/%s" % (c["file"], "/".join(c["here"] + ["_index"]))   # an _index string in the object `here`
            with self.subTest(rule=c["rule"], text=c["text"]):
                self.assertEqual(aos_index.link(where, c["text"]), c.get("to"))
                n += 1
        self.assertGreater(n, 35)

    def test_written_in(self):
        at = "kb/v.json#/o/p/_index"                      # _index string: written in object /o/p
        for text, to in (("#./q/_index", "kb/v.json#/o/p/q/_index"), ("#../r/_index", "kb/v.json#/o/r/_index"),
                         ("#/a/_index", "kb/v.json#/a/_index"), ("w.json#/_index", "kb/w.json#/_index"),
                         ("q/_index", "kb/q/_index"), ("#../../..", None), ("w.json#../x", None), ("#a", None), ("#", "kb/v.json")):
            with self.subTest(text=text):
                self.assertEqual(aos_index.link(at, text), to)

    def test_entry_field_is_written_in_its_entry(self):
        # an entry's index field sits in the entry object _index/KEY (same rule as $ref: the object holding the value)
        self.assertEqual(aos_index.link("kb/v.json#/o/_index", "#./more", "k"), "kb/v.json#/o/_index/k/more")
        self.assertEqual(aos_index.link("kb/v.json#/o/_index", "#../../sub/_index", "k"), "kb/v.json#/o/sub/_index")
        self.assertEqual(aos_index.link("kb/_index.json", "#../x", "k"), "kb/_index.json#/x")
        self.assertEqual(aos_index.link("kb/_index.json", "sub/_index.json", "a/b"), "kb/sub/_index.json")
        self.assertEqual(aos_index.link("kb/_index.json", "#./x", "a/b~"), "kb/_index.json#/a~1b~0/x")
        self.assertIsNone(aos_index.link("kb/_index.json", "#../../x", "k"))


if __name__ == "__main__":
    unittest.main()
