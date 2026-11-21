"""Run the shared table py/tests/md_path_cases.json against aos.mdpath (reading markdown as JSON: headings, _, lists, tables, json fences). The C++ side (aos-directive) runs the same table."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from aos import mdpath  # noqa: E402

TABLE = json.loads((HERE / "md_path_cases.json").read_text(encoding="utf-8"))


class Cases(unittest.TestCase):
    def test_cases(self):
        for c in TABLE["cases"]:
            text, toks = TABLE["docs"][c["doc"]], mdpath.split("x.md#" + c["ptr"])[1] if c["ptr"] else []
            with self.subTest(rule=c["rule"], ptr=c["ptr"]):
                if "ls" in c:
                    self.assertEqual(mdpath.ls(text, toks), c["ls"])
                elif c.get("missing"):
                    with self.assertRaises(mdpath.Missing):
                        mdpath.get(text, toks)
                else:
                    got = mdpath.get(text, toks)
                    self.assertEqual(got, c["get"])
                    self.assertIs(type(got), type(c["get"]))

    def test_trees(self):
        for c in TABLE["trees"]:
            with self.subTest(rule=c["rule"]):
                self.assertEqual(mdpath.tree(TABLE["docs"][c["doc"]]), c["tree"])

    def test_missing_names_what_is_there(self):
        with self.assertRaises(mdpath.Missing) as e:
            mdpath.get("# A\n\n## B\n", ["A", "C"])
        self.assertIn("/A has no C", e.exception.reason)
        self.assertIn("B", e.exception.reason)

    def test_split(self):
        self.assertEqual(mdpath.split("a/x.md"), ("a/x.md", []))
        self.assertEqual(mdpath.split("x.md#/a~1b/c~0"), ("x.md", ["a/b", "c~"]))
        with self.assertRaises(ValueError):
            mdpath.split("x.md#abc")


if __name__ == "__main__":
    unittest.main()
