"""aos_inst 的測試：找檔、基準、每個 key、衝突、跑、命令列。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import aos_inst
from aos_inst import InstError, load, parse, run

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-inst-")
        self.addCleanup(shutil.rmtree, self.d, True)

    def write(self, name, obj, raw=False):
        p = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(obj if raw else json.dumps(obj))
        return p

    def read(self, name):
        with open(os.path.join(self.d, name), encoding="utf-8") as f:
            return f.read()

    def fails(self, code, doc):
        with self.assertRaises(InstError) as cm:
            parse(doc, self.d)
        self.assertEqual(cm.exception.code, code, str(cm.exception))


class TestFindAndBase(Base):
    def test_folder_prefers_dot_aos(self):
        self.write(".aos/inst.json", {"argv": ["a"]})
        self.write("inst.json", {"argv": ["b"]})
        self.assertEqual(load(self.d)["argv"], ["a"])

    def test_folder_falls_back_to_inst_json(self):
        self.write("inst.json", {"argv": ["b"]})
        self.assertEqual(load(self.d)["argv"], ["b"])

    def test_folder_without_inst(self):
        with self.assertRaises(InstError) as cm:
            load(self.d)
        self.assertEqual(cm.exception.code, "NotFound")

    def test_base_inst_is_folder_even_for_dot_aos(self):
        """給資料夾時家是資料夾本身，不是 .aos/。"""
        self.write(".aos/inst.json", {"argv": ["x"], "cwd": "."})
        self.assertEqual(os.path.normpath(load(self.d)["cwd"]), self.d)

    def test_base_inst_for_file_is_its_folder(self):
        p = self.write("sub/i.json", {"argv": ["x"], "v": {"$ref": "data.json"}, "cwd": "w"})
        self.write("sub/data.json", 1)
        self.assertEqual(load(p)["cwd"], os.path.join(self.d, "sub", "w"))

    def test_base_cwd(self):
        p = self.write("sub/i.json", {"argv": ["x"], "cwd": "w", "envs": {"K": {"$ref": "v.json"}}})
        self.write("v.json", "from-cwd")
        old = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, old)
        inst = load(p, base="cwd")
        self.assertEqual((inst["cwd"], inst["envs"]), (os.path.join(self.d, "w"), {"K": "from-cwd"}))

    def test_bad_base(self):
        with self.assertRaises(InstError) as cm:
            load(self.d, base="here")
        self.assertEqual(cm.exception.code, "BadBase")

    def test_read_failed_and_json_syntax(self):
        with self.assertRaises(InstError) as cm:
            load(os.path.join(self.d, "nope.json"))
        self.assertEqual(cm.exception.code, "ReadFailed")
        p = self.write("bad.json", "{x", raw=True)
        with self.assertRaises(InstError) as cm:
            load(p)
        self.assertEqual(cm.exception.code, "JsonSyntax")


class TestParse(Base):
    def test_defaults_and_unknown_keys_ignored(self):
        inst = parse({"argv": ["a"], "whatever": {"x": 1}, "traits": []}, self.d)
        self.assertEqual(inst["cwd"], os.getcwd())
        self.assertEqual(inst["envs"], {})
        self.assertIsNone(inst["stdout"])
        self.assertFalse(any(inst[k] for k in aos_inst._BOOLS))

    def test_directive_errors_keep_code(self):
        self.fails("ReferencePointerInvalid", {"argv": ["a"], "x": {"$ref": "#/nope"}})

    def test_no_cwd_inherits_callers_and_streams_follow_it(self):
        """沒寫 cwd＝呼叫者的 cwd（不是基準）；串流從 cwd 算。"""
        old = os.getcwd()
        os.chdir(self.write("caller/x", "", raw=True) and os.path.join(self.d, "caller"))
        self.addCleanup(os.chdir, old)
        inst = parse({"argv": ["a"], "stdout": "o.txt"}, os.path.join(self.d, "home"))
        self.assertEqual((inst["cwd"], inst["stdout"]),
                         (os.path.join(self.d, "caller"), os.path.join(self.d, "caller", "o.txt")))

    def test_cwd_from_base_streams_from_cwd(self):
        inst = parse({"argv": ["a"], "cwd": "w", "stdin": "i", "stderr": "../e"}, self.d)
        self.assertEqual((inst["cwd"], inst["stdin"], inst["stderr"]),
                         (os.path.join(self.d, "w"), os.path.join(self.d, "w", "i"), os.path.join(self.d, "w", "../e")))

    def test_absolute_paths_kept(self):
        self.assertEqual(parse({"argv": ["a"], "stdout": "/tmp/o"}, self.d)["stdout"], "/tmp/o")

    def test_field_types(self):
        for doc in ([1], {"argv": []}, {"argv": "ls"}, {"argv": ["a", 1]}, {"argv": ["a"], "envs": {"K": 1}},
                    {"argv": ["a"], "envs": []}, {"argv": ["a"], "cwd": 1}, {"argv": ["a"], "stdout_append": "yes"}):
            with self.subTest(doc=doc):
                self.fails("FieldType", doc)

    def test_conflicts(self):
        for extra in ({"stdout": "o", "stdout_inherit": True}, {"stdin": "i", "stdin_inherit": True},
                      {"stderr_merge": True, "stderr": "e"}, {"stderr_merge": True, "stderr_inherit": True}):
            with self.subTest(extra=extra):
                self.fails("Conflict", dict({"argv": ["a"]}, **extra))


class TestRun(Base):
    def setUp(self):
        super().setUp()
        old = os.getcwd()
        os.chdir(self.d)      # 沒寫 cwd 的就在暫存資料夾跑
        self.addCleanup(os.chdir, old)

    def go(self, **kw):
        return run(parse(dict({"argv": ["sh", "-c", "echo out; echo err >&2; exit 3"]}, **kw), self.d))

    def test_exit_code_and_files(self):
        self.assertEqual(self.go(stdout="o.txt", stderr="e.txt"), 3)
        self.assertEqual((self.read("o.txt"), self.read("e.txt")), ("out\n", "err\n"))

    def test_append_mkdir_merge(self):
        self.write("o.txt", "old\n", raw=True)
        self.go(stdout="o.txt", stdout_append=True, stderr_merge=True)
        self.assertEqual(self.read("o.txt"), "old\nout\nerr\n")
        self.go(stdout="deep/er/o.txt", stdout_mkdir=True)
        self.assertEqual(self.read("deep/er/o.txt"), "out\n")

    def test_stdin_cwd_envs(self):
        """cwd 從基準算；stdin／stdout 從 cwd 算，所以落在 w/ 底下。"""
        self.write("w/in.txt", "hello", raw=True)
        code = run(parse({"argv": ["sh", "-c", 'cat; pwd; echo "$K-$HOME"'], "stdin": "in.txt", "stdout": "o.txt",
                          "cwd": "w", "cwd_mkdir": True, "envs": {"K": "k"}}, self.d))
        self.assertEqual(code, 0)
        self.assertEqual(self.read("w/o.txt"), "hello%s\nk-%s\n" % (os.path.join(self.d, "w"), os.environ.get("HOME", "")))

    def test_envs_clear(self):
        run(parse({"argv": ["/bin/sh", "-c", 'echo "[$HOME][$K]"'], "stdout": "o.txt",
                   "envs": {"K": "k"}, "envs_clear": True}, self.d))
        self.assertEqual(self.read("o.txt"), "[][k]\n")

    def test_signal_not_found_not_executable(self):
        self.assertEqual(run(parse({"argv": ["sh", "-c", "kill -9 $$"]}, self.d)), 137)
        self.assertEqual(run(parse({"argv": ["no-such-program-xyz"]}, self.d)), 127)
        p = self.write("noexec.sh", "echo hi", raw=True)
        self.assertEqual(run(parse({"argv": [p]}, self.d)), 126)


class TestCli(Base):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", os.path.join(LIB, "aos_inst.py")] + list(args),
                              capture_output=True, text=True, timeout=10)

    def test_runs_folder(self):
        self.write(".aos/inst.json", {"argv": ["sh", "-c", "exit 4"]})
        self.assertEqual(self.cli(self.d).returncode, 4)

    def test_inst_error_is_125_one_line(self):
        p = self.cli(self.d)
        self.assertEqual(p.returncode, 125)
        self.assertTrue(p.stderr.startswith("NotFound: "))
        self.assertEqual(len(p.stderr.splitlines()), 1)

    def test_usage_and_open_failed(self):
        self.assertEqual(self.cli().returncode, 125)
        p = self.write("i.json", {"argv": ["true"], "stdin": "missing.txt"})
        r = self.cli(p, "--base", "inst")
        self.assertEqual(r.returncode, 125)
        self.assertTrue(r.stderr.startswith("OpenFailed: "))


if __name__ == "__main__":
    unittest.main()
