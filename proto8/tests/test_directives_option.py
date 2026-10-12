"""aos_directives 的測試：每條規則、每個錯誤代號都要有一條。

本檔：選項物件（TestSplitOption、TestOptionNames、TestParseOptions）。

純記憶體文件用 `Document(None, root)`；要測跨檔的用暫存資料夾寫真檔。
"""
import unittest

from _directives_util import Base

from aos_directives import Option, resolve, resolve_located, split_option, option_names, parse_options


# ---------------------------------------------------------------- 選項物件 ----
TABLE = {
    "append": {"val": "required"},
    "mkdir": {"val": "required"},
    "inherit": {"val": "forbidden", "alone": True},
    "clear": {"val": "optional"},
    "bare": {},
}


class TestSplitOption(Base):

    def test_not_option_object(self):
        for v in ("s", 1, None, [1], {"a": 1}, {"$env": "X"}):
            self.assertEqual(split_option(v), Option(False, None, v, True))

    def test_opt_any_json_passes_through(self):
        for raw in ("name", 1, 1.5, True, None, ["a", "b"], {"k": {"$env": "X"}}, [], ""):
            o = split_option({"$opt": raw})
            self.assertEqual(o, Option(True, raw, None, False))
            self.assertIs(o.opt, raw) if not isinstance(raw, (int, float, str)) else None

    def test_val_present_and_untouched(self):
        val = {"$env": "P"}
        o = split_option({"$opt": "x", "$val": val})
        self.assertTrue(o.has_val)
        self.assertIs(o.val, val)

    def test_val_null_counts_as_present(self):
        self.assertEqual(split_option({"$opt": "x", "$val": None}), Option(True, "x", None, True))

    def test_extra_keys_ignored(self):
        o = split_option({"$opt": "x", "$envs": {"A": "1"}, "$ref": "nope", "_note": "n"})
        self.assertEqual(o, Option(True, "x", None, False))


class TestOptionNames(Base):

    def test_single_and_array(self):
        self.assertEqual(option_names("bare", False, ["p"], TABLE), frozenset({"bare"}))
        self.assertEqual(option_names(["append", "mkdir"], True, ["p"], TABLE),
                         frozenset({"append", "mkdir"}))

    def test_type_mismatch(self):
        for raw in (1, None, [], ["a", 1], [1], {"a": 1}, True):
            self.fails("DirectiveValueTypeMismatch", option_names, raw, False, ["p"], TABLE)

    def test_unknown(self):
        self.fails("UnknownOption", option_names, "nope", False, ["p"], TABLE)
        self.fails("UnknownOption", option_names, "Append", False, ["p"], TABLE)   # 區分大小寫

    def test_duplicate(self):
        e = self.fails("UnknownOption", option_names, ["append", "append"], True, ["p"], TABLE)
        self.assertIn("重複", str(e))

    def test_empty_table(self):
        e = self.fails("UnknownOption", option_names, "append", True, ["argv", "0"], {})
        self.assertIn("沒有任何選項", str(e))

    def test_val_required(self):
        self.fails("OptionConflict", option_names, "append", False, ["p"], TABLE)
        self.assertEqual(option_names("append", True, ["p"], TABLE), frozenset({"append"}))

    def test_val_forbidden(self):
        self.fails("OptionConflict", option_names, "inherit", True, ["p"], TABLE)
        self.assertEqual(option_names("inherit", False, ["p"], TABLE), frozenset({"inherit"}))

    def test_val_optional(self):
        self.assertEqual(option_names("clear", False, ["p"], TABLE), frozenset({"clear"}))
        self.assertEqual(option_names("clear", True, ["p"], TABLE), frozenset({"clear"}))

    def test_alone(self):
        self.fails("OptionConflict", option_names, ["inherit", "append"], True, ["p"], TABLE)
        self.fails("OptionConflict", option_names, ["append", "inherit"], True, ["p"], TABLE)

    def test_bad_table_is_programming_error(self):
        with self.assertRaises(ValueError):
            option_names("x", False, ["p"], {"x": {"val": "require"}})


class TestParseOptions(Base):

    def test_passthrough(self):
        for v in ("s", 1, None, {"a": 1}, {"$env": "X"}):
            self.assertEqual(parse_options(v, ["p"], TABLE), (frozenset(), v, True))

    def test_compose(self):
        val = {"$env": "P"}
        self.assertEqual(parse_options({"$opt": ["append", "mkdir"], "$val": val}, ["p"], TABLE),
                         (frozenset({"append", "mkdir"}), val, True))
        self.assertEqual(parse_options({"$opt": "inherit"}, ["p"], TABLE),
                         (frozenset({"inherit"}), None, False))

    def test_errors_propagate(self):
        self.fails("UnknownOption", parse_options, {"$opt": "nope"}, ["p"], TABLE)
        self.fails("OptionConflict", parse_options, {"$opt": "append"}, ["p"], TABLE)
        self.fails("DirectiveValueTypeMismatch", parse_options, {"$opt": 1}, ["p"], TABLE)

    def test_host_flow(self):
        """宿主的典型流程：解這格 → 拆選項 → 再解 $val。"""
        self.write("o.json", {"$opt": ["append", "mkdir"], "$val": {"$fmt": {"$val": "${d}/out.txt", "d": {"$env": "D"}}}})
        c = self.ctx({}, {"D": "/tmp/x"})
        loc = resolve_located({"$ref": "o.json"}, c, ["stdout"])
        names, val, has_val = parse_options(loc.value, loc.position, TABLE)
        self.assertEqual(names, frozenset({"append", "mkdir"}))
        self.assertTrue(has_val)
        self.assertEqual(resolve(val, loc.ctx, loc.position + ["$val"]), "/tmp/x/out.txt")


if __name__ == "__main__":
    unittest.main()
