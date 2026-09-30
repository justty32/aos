"""展開與驗證：inst 欄位、選項、指示詞、循環、解析順序（inst.md 與 directives/）。"""
import os

from aos_inst import InstError
from tests.util import TmpCase


class InstFields(TmpCase):
    def test_minimal_defaults(self):
        p = self.plan({"argv": ["echo", "hi"]})
        self.assertEqual(p.argv, ["echo", "hi"])
        self.assertEqual(p.cwd, self.dir)
        self.assertEqual((p.envs, p.envs_clear), ({}, False))
        for s in (p.stdin, p.stdout, p.stderr, p.exit):
            self.assertEqual(s.path, "")
        self.assertEqual(p.metainfo, {"_type": "posix", "_version": 1})
        self.assertEqual(p.source, self.path("inst.json"))

    def test_read_failed(self):
        os.symlink(self.path("gone"), self.path("broken.json"))
        from aos_inst import load_plan, grant_only
        with self.assertRaises(InstError) as cm:
            load_plan(self.path("broken.json"), grant_only([os.getuid()]))
        self.assertEqual(cm.exception.code, "ReadFailed")

    def test_json_syntax(self):
        self.write("inst.json", "{nope", raw=True)
        self.assertCode("JsonSyntax", None)
        self.write("inst.json", b"\xff\xfe", raw=True)
        self.assertCode("JsonSyntax", None)

    def test_not_an_object(self):
        self.assertCode("NotAnObject", [1])
        self.write("arr.json", [1])
        self.assertCode("NotAnObject", {"$ref": "arr.json"})

    def test_metainfo(self):
        self.assertCode("MetainfoInvalid", {"_metainfo": "posix", "argv": ["x"]})
        self.assertCode("MetainfoInvalid", {"_metainfo": {"_type": "posix"}, "argv": ["x"]})
        self.assertCode("UnsupportedInstType", {"_metainfo": {"_type": "win", "_version": 1},
                                                "argv": ["x"]})
        for v in (2, True, "1"):
            self.assertCode("UnsupportedInstVersion", {"_metainfo": {"_type": "posix", "_version": v},
                                                       "argv": ["x"]})
        # _metainfo 不展開：指示詞物件就是缺鍵
        self.assertCode("MetainfoInvalid", {"_metainfo": {"$env": "X"}, "argv": ["x"]})

    def test_metainfo_from_expanded_top(self):
        self.write("real.json", {"_metainfo": {"_type": "posix", "_version": 9}, "argv": ["x"]})
        self.assertCode("UnsupportedInstVersion", {"$ref": "real.json"})

    def test_empty_argv(self):
        self.assertCode("EmptyArgv", {})
        self.assertCode("EmptyArgv", {"argv": []})
        self.assertCode("EmptyArgv", {"argv": ["", "a"]})

    def test_field_type_mismatch(self):
        for inst in ({"argv": "echo"}, {"argv": ["a", 1]}, {"argv": ["a\0b"]},
                     {"argv": ["x"], "stdout": 3}, {"argv": ["x"], "cwd": ["a"]},
                     {"argv": ["x"], "envs": []}, {"argv": ["x"], "envs": {"A": 1}},
                     {"argv": ["x"], "envs": {"$opt": "clear", "$val": "A=1"}},
                     {"argv": ["x"], "stdout": {"$opt": "append", "$val": 5}}):
            self.assertCode("FieldTypeMismatch", inst)

    def test_env_key_invalid(self):
        self.assertCode("EnvKeyInvalid", {"argv": ["x"], "envs": {"": "1"}})
        self.assertCode("EnvKeyInvalid", {"argv": ["x"], "envs": {"A=B": "1"}})

    def test_unknown_top_keys_kept(self):
        p = self.plan({"argv": ["x"], "id": 3, "_x": {"$env": "NOPE"}})
        self.assertEqual(p.extra, {"id": 3, "_x": {"$env": "NOPE"}})    # 不展開、不驗

    def test_paths_relative_to_cwd_and_empty_is_omitted(self):
        p = self.plan({"argv": ["x"], "cwd": "w", "stdin": "in.txt", "stdout": "/abs/o",
                       "stderr": "", "exit": "e/code"})
        self.assertEqual(p.cwd, self.path("w"))
        self.assertEqual(p.stdin.path, self.path("w", "in.txt"))
        self.assertEqual(p.stdout.path, "/abs/o")
        self.assertEqual(p.stderr.path, "")
        self.assertEqual(p.exit.path, self.path("w", "e", "code"))


class Options(TmpCase):
    def test_valid_options(self):
        p = self.plan({"argv": ["x"],
                       "stdin": {"$opt": "inherit"},
                       "stdout": {"$opt": ["append", "mkdir"], "$val": "o/out", "_note": 1},
                       "stderr": {"$opt": "merge"},
                       "exit": {"$opt": "mkdir", "$val": "x/code"},
                       "cwd": {"$opt": "mkdir", "$val": "w"},
                       "envs": {"$opt": "clear"}})
        self.assertTrue(p.stdin.inherit)
        self.assertTrue(p.stdout.append and p.stdout.mkdir)
        self.assertEqual(p.stdout.path, self.path("w", "o", "out"))
        self.assertTrue(p.stderr.merge)
        self.assertTrue(p.exit.mkdir and not p.exit.append)
        self.assertTrue(p.cwd_mkdir)
        self.assertEqual((p.envs, p.envs_clear), ({}, True))

    def test_val_can_be_directive(self):
        p = self.plan({"argv": ["x"], "stdout": {"$opt": "append", "$val": {"$env": "O"}},
                       "envs": {"$opt": "clear", "$val": {"A": {"$env": "O"}}}}, env={"O": "o.txt"})
        self.assertEqual(p.stdout.path, self.path("o.txt"))
        self.assertEqual(p.envs, {"A": "o.txt"})

    def test_option_conflict(self):
        for field, obj in (
                ("stdout", {"$opt": ["inherit", "append"], "$val": "a"}),
                ("stderr", {"$opt": ["merge", "mkdir"], "$val": "a"}),
                ("stdout", {"$opt": "append"}),
                ("stdout", {"$opt": "append", "$val": ""}),
                ("exit", {"$opt": "mkdir", "$val": {"$env": "EMPTY"}}),
                ("stdin", {"$opt": "inherit", "$val": "a"}),
                ("stderr", {"$opt": "merge", "$val": "a"}),
                ("cwd", {"$opt": "mkdir"})):
            self.assertCode("OptionConflict", {"argv": ["x"], field: obj}, env={"EMPTY": ""})

    def test_unknown_option(self):
        for inst in ({"argv": ["x"], "stdin": {"$opt": "append", "$val": "a"}},
                     {"argv": ["x"], "stdout": {"$opt": "INHERIT"}},
                     {"argv": ["x"], "stdout": {"$opt": ["append", "append"], "$val": "a"}},
                     {"argv": ["x"], "exit": {"$opt": "inherit"}},
                     {"argv": ["x"], "cwd": {"$opt": "clear"}},
                     {"$opt": "clear", "$val": {"argv": ["x"]}},
                     {"argv": {"$opt": "inherit"}},
                     {"argv": ["x", {"$opt": "inherit"}]},
                     {"argv": ["x"], "envs": {"A": {"$opt": "clear"}}},
                     {"argv": ["x"], "stdout": {"$opt": "append", "$val": {"$opt": "mkdir", "$val": "a"}}},
                     {"argv": ["x"], "envs": {"$opt": "clear", "$val": {"$opt": "clear"}}}):
            self.assertCode("UnknownOption", inst)

    def test_opt_type(self):
        for opt in (3, [], ["append", 1], None):
            self.assertCode("DirectiveValueTypeMismatch",
                            {"argv": ["x"], "stdout": {"$opt": opt, "$val": "a"}})

    def test_option_from_ref(self):
        self.write("o.json", {"$opt": "append", "$val": "log"})
        p = self.plan({"argv": ["x"], "stdout": {"$ref": "o.json"}})
        self.assertTrue(p.stdout.append)
        self.assertEqual(p.stdout.path, self.path("log"))


class Directives(TmpCase):
    def test_env_fmt_ref(self):
        self.write("w/data.json", {"a": ["b", "c"], "path": "/opt"})
        p = self.plan({"cwd": "w",
                       "argv": [{"$env": "PROG"},
                                {"$fmt": {"$val": "${p}:$x ${q}", "p": {"$env": "HOME"},
                                          "q": {"$ref": "data.json#/a/1"}}},
                                {"$ref": "data.json", "$at": "/path"}],
                       "envs": {"E": {"$env": "EMPTY"}}},
                      env={"PROG": "prog", "HOME": "/h", "EMPTY": ""})
        self.assertEqual(p.argv, ["prog", "/h:$x c", "/opt"])
        self.assertEqual(p.envs, {"E": ""})

    def test_priority_and_ignored_keys(self):
        p = self.plan({"argv": [{"$env": "A", "$fmt": {"$val": "fmt"}, "_x": 1}, "y"]}, env={"A": "a"})
        self.assertEqual(p.argv[0], "fmt")

    def test_relative_at_and_siblings(self):
        p = self.plan({"argv": ["x", {"$ref": "", "$at": "../0"},
                                {"$ref": "#./k", "k": "own"}],
                       "envs": {"B": {"$fmt": {"$val": "${a}-${b}", "a": "1",
                                               "b": {"$ref": "", "$at": "../a"}}}}})
        self.assertEqual(p.argv, ["x", "x", "own"])
        self.assertEqual(p.envs, {"B": "1-1"})

    def test_whole_argv_and_envs_from_ref(self):
        self.write("w/a.json", {"argv": ["p", {"$ref": "", "$at": "/v"}], "v": "V",
                                "envs": {"K": {"$ref": "", "$at": "/v"}}})
        p = self.plan({"cwd": "w", "argv": {"$ref": "a.json#/argv"}, "envs": {"$ref": "a.json#/envs"}})
        self.assertEqual(p.argv, ["p", "V"])
        self.assertEqual(p.envs, {"K": "V"})

    def test_top_level_ref(self):
        self.write("sub/real.json", {"argv": ["x"], "cwd": "c", "stdout": "o"})
        p = self.plan({"$ref": "sub/real.json"})
        # 頂層與 cwd 以 base（inst.json 的資料夾）為中心
        self.assertEqual(p.cwd, self.path("c"))
        self.assertEqual(p.stdout.path, self.path("c", "o"))

    def test_errors(self):
        E = {"HOME": "/h"}
        cases = [
            ("UnknownDirective", {"argv": [{"$xyz": 1}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$env": 1}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$ref": 1}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$ref": "", "$at": 1}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$fmt": "x"}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$fmt": {"a": "1"}}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$fmt": {"$val": "${a}", "a": 1}}]}),
            ("DirectiveValueTypeMismatch", {"argv": [{"$fmt": {"$val": ["x"]}}]}),
            ("FormatVariableInvalid", {"argv": [{"$fmt": {"$val": "x", "$a": "1"}}]}),
            ("FormatVariableInvalid", {"argv": [{"$fmt": {"$val": "x", "": "1"}}]}),
            ("FormatVariableInvalid", {"argv": [{"$fmt": {"$val": "x", "a{": "1"}}]}),
            ("EnvironmentVariableMissing", {"argv": [{"$env": "NOPE"}]}),
            ("UnknownFormatVariable", {"argv": [{"$fmt": {"$val": "${zz}"}}]}),
            ("ReferenceReadFailed", {"argv": {"$ref": "missing.json"}}),
            ("ReferencePointerInvalid", {"argv": [{"$ref": "", "$at": "x/y"}]}),
            ("ReferencePointerInvalid", {"argv": [{"$ref": "", "$at": "../../../.."}]}),
            ("ReferencePointerInvalid", {"argv": [{"$ref": "", "$at": "/argv/9"}]}),
            ("ReferencePointerInvalid", {"argv": [{"$ref": "", "$at": "/nokey"}]}),
            ("ReferencePointerInvalid", {"argv": [{"$ref": "bad.json#../x"}]}),
        ]
        self.write("bad.json", {"x": 1})
        for code, inst in cases:
            self.assertCode(code, inst, env=E)

    def test_reference_json_invalid(self):
        self.write("junk.json", "{", raw=True)
        self.assertCode("ReferenceJsonInvalid", {"argv": {"$ref": "junk.json"}})


class Cycles(TmpCase):
    def test_self(self):
        self.assertCode("ReferenceCycle", {"argv": [{"$ref": "", "$at": "."}]})

    def test_two_files(self):
        self.write("a.json", {"$ref": "b.json"})
        self.write("b.json", {"$ref": "a.json"})
        self.assertCode("ReferenceCycle", {"argv": {"$ref": "a.json"}})

    def test_inside_referenced_container(self):
        # 走進 $ref 取回的 argv 容器時鏈要帶下去：元素指回容器所在位置＝循環
        self.write("a.json", {"list": ["p", {"$ref": "", "$at": "/list"}]})
        self.assertCode("ReferenceCycle", {"argv": {"$ref": "a.json#/list"}})
        # 對照：指到別的欄位的容器不在鏈上，只是型別錯
        self.assertCode("FieldTypeMismatch", {"argv": ["p", {"$ref": "", "$at": "/envs"}],
                                              "envs": {}})
        self.write("b.json", {"list": {"$ref": "", "$at": "/list"}})
        self.assertCode("ReferenceCycle", {"argv": {"$ref": "b.json#/list"}})
        self.write("c.json", {"v": {"$ref": "", "$at": "/e"}, "e": {"K": {"$ref": "", "$at": "/e"}}})
        self.assertCode("ReferenceCycle", {"argv": ["x"], "envs": {"$ref": "c.json#/e"}})

    def test_same_file_from_two_fields_is_fine(self):
        self.write("v.json", {"s": "same"})
        p = self.plan({"argv": [{"$ref": "v.json#/s"}, {"$ref": "v.json#/s"}],
                       "envs": {"A": {"$ref": "v.json#/s"}}, "stdout": {"$ref": "v.json#/s"}})
        self.assertEqual(p.argv, ["same", "same"])
        self.assertEqual(p.stdout.path, self.path("same"))

    def test_ref_to_self_by_filename_uses_snapshot(self):
        p = self.plan({"argv": ["x", {"$ref": "inst.json#/v"}], "v": "snap"})
        self.assertEqual(p.argv, ["x", "snap"])


class Order(TmpCase):
    def test_cwd_centre(self):
        # cwd 的 $ref 以 base 為中心；argv 的 $ref 以解出的 cwd 為中心
        self.write("c.json", "w")
        self.write("w/a.json", ["inner"])
        self.write("a.json", ["outer"])
        p = self.plan({"cwd": {"$ref": "c.json"}, "argv": {"$ref": "a.json"}})
        self.assertEqual(p.argv, ["inner"])

    def test_cwd_mkdir_created_only_when_asked(self):
        self.plan({"argv": ["x"], "cwd": {"$opt": "mkdir", "$val": "made"}})
        self.assertFalse(os.path.exists(self.path("made")))
        self.plan({"argv": ["x"], "cwd": {"$opt": "mkdir", "$val": "made"}}, create_dirs=True)
        self.assertTrue(os.path.isdir(self.path("made")))

    def test_cwd_before_argv_errors(self):
        # 兩欄都錯時先報 cwd 的
        self.assertCode("EnvironmentVariableMissing",
                        {"cwd": {"$env": "NOPE"}, "argv": [{"$xyz": 1}]})

    def test_argv_before_envs_before_paths(self):
        self.assertCode("UnknownDirective", {"argv": [{"$xyz": 1}], "envs": {"": "1"}})
        self.assertCode("EnvKeyInvalid", {"argv": ["x"], "envs": {"": "1"}, "stdout": 3})

    def test_prepare_failed_mkdir(self):
        self.write("file", "x")
        self.assertCode("PrepareFailed", {"argv": ["x"], "cwd": {"$opt": "mkdir", "$val": "file/sub"}},
                        create_dirs=True)
