"""aos_directives 的測試：每條規則、每個錯誤代號至少一條。"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from aos_directives import DirectiveError, resolve


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-directives-")
        self.addCleanup(shutil.rmtree, self.d, True)

    def write(self, name, obj, raw=False):
        p = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(obj if raw else json.dumps(obj, ensure_ascii=False))
        return p

    def r(self, doc):
        return resolve(doc, self.d)

    def fails(self, code, doc):
        with self.assertRaises(DirectiveError) as cm:
            self.r(doc)
        self.assertEqual(cm.exception.code, code, str(cm.exception))
        return cm.exception


class TestBasics(Base):
    def test_plain_values_untouched(self):
        for v in (1, "s", None, True, [], {}, [1, {"a": "$not-a-key"}], {"a": [1, 2]}):
            self.assertEqual(self.r(v), v)

    def test_input_not_mutated(self):
        doc = {"a": {"$env": "X"}}
        with mock.patch.dict(os.environ, {"X": "1"}):
            self.assertEqual(self.r(doc), {"a": "1"})
        self.assertEqual(doc, {"a": {"$env": "X"}})

    def test_deep_resolution(self):
        """容器裡每一層的指示詞都會解。"""
        doc = {"a": [{"b": {"$ref": "#/v"}}], "v": 3}
        self.assertEqual(self.r(doc), {"a": [{"b": 3}], "v": 3})

    def test_error_shape(self):
        e = self.fails("UnknownDirective", {"$what": 1})
        self.assertTrue(str(e).startswith("UnknownDirective: "))

    def test_ref_beats_env(self):
        with mock.patch.dict(os.environ, {"X": "env"}):
            self.assertEqual(self.r({"v": 1, "a": {"$ref": "#/v", "$env": "X"}})["a"], 1)

    def test_extra_keys_ignored(self):
        self.assertEqual(self.r({"v": 1, "a": {"$ref": "#/v", "other": 2, "$x": 3}})["a"], 1)

    def test_removed_directives_are_unknown(self):
        for d in ({"$fmt": {"$val": "x"}}, {"$opt": "a", "$val": 1}, {"$at": "/a"}):
            with self.subTest(d=d):
                self.fails("UnknownDirective", d)

    def test_relative_base_dir_is_from_cwd(self):
        self.write("a.json", 5)
        old = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, old)
        self.assertEqual(resolve({"$ref": "a.json"}, "."), 5)


class TestEnv(Base):
    def test_env(self):
        with mock.patch.dict(os.environ, {"X": "v", "E": ""}):
            self.assertEqual(self.r([{"$env": "X"}, {"$env": "E"}]), ["v", ""])

    def test_env_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.fails("EnvironmentVariableMissing", {"$env": "NOPE"})

    def test_env_not_string(self):
        self.fails("DirectiveValueTypeMismatch", {"$env": 1})


class TestRef(Base):
    def test_whole_file(self):
        self.write("a.json", {"x": 1})
        self.assertEqual(self.r({"$ref": "a.json"}), {"x": 1})

    def test_hash_and_at(self):
        self.write("a.json", {"x": [10, 20]})
        self.assertEqual(self.r([{"$ref": "a.json#/x/1"}, {"$ref": "a.json", "$at": "/x/0"}]), [20, 10])

    def test_at_wins_over_hash(self):
        self.write("a.json", {"x": 1, "y": 2})
        self.assertEqual(self.r({"$ref": "a.json#/x", "$at": "/y"}), 2)

    def test_absolute_file(self):
        p = self.write("a.json", 7)
        self.assertEqual(resolve({"$ref": p}, "/"), 7)

    def test_relative_file_from_base_dir(self):
        self.write("sub/a.json", 8)
        self.assertEqual(resolve({"$ref": "a.json"}, os.path.join(self.d, "sub")), 8)

    def test_base_dir_kept_inside_other_files(self):
        """進了 sub/b.json，它裡面的相對檔名照樣從 base_dir 算，不從 sub/ 算。"""
        self.write("sub/b.json", {"$ref": "c.json"})
        self.write("c.json", "top")
        self.write("sub/c.json", "sub")
        self.assertEqual(self.r({"$ref": "sub/b.json"}), "top")

    def test_self_positions(self):
        doc = {"a": 1, "b": {"c": 2, "x": {"$ref": "", "$at": "../c"}, "y": {"$ref": "#./k", "k": 3}},
               "z": {"$ref": "#/a"}}
        out = self.r(doc)
        self.assertEqual((out["b"]["x"], out["b"]["y"], out["z"]), (2, 3, 1))

    def test_dotdot_from_array_element(self):
        self.assertEqual(self.r({"v": 9, "l": [{"$ref": "#../../v"}]})["l"], [9])

    def test_relative_in_other_file_is_from_its_root(self):
        self.write("a.json", {"x": 1})
        self.assertEqual(self.r({"$ref": "a.json#./x"}), 1)
        self.fails("ReferencePointerInvalid", {"$ref": "a.json#../x"})

    def test_pointer_escapes_and_empty_segment(self):
        doc = {"a/b": 1, "m~n": 2, "": 3,
               "r": [{"$ref": "#/a~1b"}, {"$ref": "#/m~0n"}, {"$ref": "#/"}]}
        self.assertEqual(self.r(doc)["r"], [1, 2, 3])

    def test_hash_split_at_first_hash(self):
        self.assertEqual(self.r({"a#b": 1, "r": {"$ref": "#/a#b"}})["r"], 1)

    def test_nested_ref_resolved_where_it_lives(self):
        """取回來的值裡的指示詞，以它所在的檔、所在的位置為準。"""
        self.write("b.json", {"x": {"$ref": "#./y", "y": "b-local"}, "w": {"$ref": "", "$at": "/q"}, "q": "b-q"})
        out = self.r({"q": "input-q", "a": {"$ref": "b.json#/x"}, "c": {"$ref": "b.json#/w"}})
        self.assertEqual((out["a"], out["c"]), ("b-local", "b-q"))

    def test_referenced_container_resolved_deeply(self):
        self.write("b.json", {"list": [{"$ref": "#/v"}], "v": 4})
        self.assertEqual(self.r({"$ref": "b.json#/list"}), [4])

    def test_same_target_twice_not_cycle(self):
        self.assertEqual(self.r({"v": 1, "a": {"$ref": "#/v"}, "b": [{"$ref": "#/v"}, {"$ref": "#/v"}]})["b"], [1, 1])

    def test_ref_to_sibling_subtree_not_cycle(self):
        self.assertEqual(self.r({"a": {"x": 1, "y": {"$ref": "#../x"}}})["a"], {"x": 1, "y": 1})


class TestRefErrors(Base):
    def test_ref_not_string(self):
        self.fails("DirectiveValueTypeMismatch", {"$ref": 1})

    def test_at_not_string_or_null(self):
        for at in (1, None, ["/a"]):
            with self.subTest(at=at):
                self.fails("DirectiveValueTypeMismatch", {"a": 1, "r": {"$ref": "", "$at": at}})

    def test_bad_pointers(self):
        doc = {"a": {"b": 1}, "l": [0, 1]}
        for at in ("a", "/nope", "/a/b/c", "/l/2", "/l/-1", "/l/x", "/l/²", "/l/١", "/l/" + "9" * 5000, "/.."):
            with self.subTest(at=at[:20]):
                self.fails("ReferencePointerInvalid", dict(doc, r={"$ref": "", "$at": at}))

    def test_leading_zero_index_ok(self):
        doc = {"l": [7, 8]}
        self.assertEqual(self.r(dict(doc, r={"$ref": "#/l/0001"}))["r"], 8)
        self.assertEqual(self.r(dict(doc, r={"$ref": "", "$at": "/l/" + "0" * 5000 + "1"}))["r"], 8)

    def test_read_failed_and_json_invalid(self):
        self.fails("ReferenceReadFailed", {"$ref": "missing.json"})
        self.write("bad.json", "{nope", raw=True)
        self.fails("ReferenceJsonInvalid", {"$ref": "bad.json"})

    def test_filename_with_hash_cannot_be_referenced(self):
        """# 之後一律當位置，所以 a#b.json 讀的是 a 的位置 b.json（不合法）。"""
        self.write("a#b.json", 1)
        self.fails("ReferencePointerInvalid", {"$ref": "a#b.json"})


class TestCycle(Base):
    def test_self(self):
        self.fails("ReferenceCycle", {"a": {"$ref": "", "$at": "."}})
        self.fails("ReferenceCycle", {"a": {"$ref": "#/a"}})

    def test_ref_to_ancestor(self):
        self.fails("ReferenceCycle", {"a": {"b": {"$ref": "#/a"}}})
        self.fails("ReferenceCycle", {"a": [{"$ref": ""}]})

    def test_two_step(self):
        self.fails("ReferenceCycle", {"a": {"$ref": "#/b"}, "b": {"$ref": "#/a"}})

    def test_two_files(self):
        self.write("a.json", {"$ref": "b.json"})
        self.write("b.json", {"$ref": "a.json"})
        self.fails("ReferenceCycle", {"$ref": "a.json"})

    def test_file_referring_back_into_itself(self):
        self.write("a.json", {"x": {"y": {"$ref": "a.json#/x"}}})
        self.fails("ReferenceCycle", {"$ref": "a.json"})

    def test_cycle_reported_before_reading(self):
        """繞回自己的檔即使已經讀不到，也先報循環。"""
        p = self.write("a.json", {"$ref": "a.json"})
        self.fails("ReferenceCycle", {"$ref": p})


if __name__ == "__main__":
    unittest.main()
