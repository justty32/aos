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

    def test_base_is_callers_cwd(self):
        """指示詞的相對檔名、cwd 這個 key 都從呼叫者的 cwd 算，不從 inst 所在處算。"""
        p = self.write("sub/i.json", {"argv": ["x"], "cwd": "w", "envs": {"K": {"$ref": "v.json"}}})
        self.write("v.json", "from-cwd")
        self.write("sub/v.json", "from-inst-home")
        old = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, old)
        inst = load(p)
        self.assertEqual((inst["cwd"], inst["envs"]), (os.path.join(self.d, "w"), {"K": "from-cwd"}))

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

    def test_signal_returns_negative(self):
        self.assertEqual(run(parse({"argv": ["sh", "-c", "kill -9 $$"]}, self.d)), -9)

    def test_launch_failures_raise(self):
        p = self.write("noexec.sh", "echo hi", raw=True)
        for doc, code in (({"argv": ["no-such-program-xyz"]}, "CommandNotFound"),
                          ({"argv": [p]}, "CommandNotExecutable"),
                          ({"argv": ["true"], "cwd": "nope"}, "CwdMissing"),
                          ({"argv": ["true"], "stdin": "missing.txt"}, "OpenFailed")):
            with self.subTest(code=code):
                with self.assertRaises(InstError) as cm:
                    run(parse(dict(doc, exit="x.txt"), self.d))
                self.assertEqual(cm.exception.code, code)
                self.assertFalse(os.path.exists(os.path.join(self.d, "x.txt")), "沒起來就不寫 exit")


class TestExit(Base):
    def setUp(self):
        super().setUp()
        old = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, old)

    def go(self, code, **kw):
        return run(parse(dict({"argv": ["sh", "-c", "exit %d" % code]}, **kw), self.d))

    def test_exit_file(self):
        self.assertEqual(self.go(3, exit="x.txt"), 3)
        self.assertEqual(self.read("x.txt"), "3\n")
        self.go(0, exit="x.txt")
        self.assertEqual(self.read("x.txt"), "0\n")

    def test_exit_append_and_mkdir(self):
        self.go(1, exit="a/b/x.txt", exit_mkdir=True)
        self.go(2, exit="a/b/x.txt", exit_append=True)
        self.assertEqual(self.read("a/b/x.txt"), "1\n2\n")

    def test_exit_follows_cwd(self):
        self.go(5, cwd="w", cwd_mkdir=True, exit="x.txt")
        self.assertEqual(self.read("w/x.txt"), "5\n")

    def test_exit_not_written_when_signaled(self):
        """被訊號停掉不代寫 exit；舊的內容原封不動。"""
        self.write("x.txt", "old\n", raw=True)
        self.assertEqual(run(parse({"argv": ["sh", "-c", "kill -15 $$"], "exit": "x.txt"}, self.d)), -15)
        self.assertEqual(self.read("x.txt"), "old\n")

    def test_exit_write_failed_ignored(self):
        """exit 寫不進去不管：照樣回子程式的碼，不丟錯。"""
        self.assertEqual(self.go(4, exit="no/such/dir/x.txt"), 4)

    def test_exit_type(self):
        self.fails("FieldType", {"argv": ["a"], "exit": 1})
        self.fails("FieldType", {"argv": ["a"], "exit_append": 1})


class TestTimeout(Base):
    def setUp(self):
        super().setUp()
        old = os.getcwd()
        os.chdir(self.d)
        self.addCleanup(os.chdir, old)

    def test_timeout_sigterm_no_exit(self):
        self.assertEqual(run(parse({"argv": ["sleep", "5"], "timeout_ms": 100, "exit": "x.txt"}, self.d)), -15)
        self.assertFalse(os.path.exists(os.path.join(self.d, "x.txt")))

    def test_timeout_sigkill_after_grace(self):
        code = run(parse({"argv": ["sh", "-c", "trap '' TERM; sleep 5"],
                          "timeout_ms": 100, "timeout_grace_ms": 200}, self.d))
        self.assertEqual(code, -9)

    def test_grace_zero_kills_directly(self):
        """grace 0＝不送 SIGTERM，直接 SIGKILL（擋 TERM 的程式也是 -9，而且不用等）。"""
        code = run(parse({"argv": ["sh", "-c", "trap 'exit 7' TERM; sleep 5"],
                          "timeout_ms": 100, "timeout_grace_ms": 0}, self.d))
        self.assertEqual(code, -9)

    def test_term_handler_exit_code_is_written(self):
        """收到 SIGTERM 自己收工、自己回碼＝自己結束，照樣寫 exit。"""
        code = run(parse({"argv": ["sh", "-c", "trap 'exit 7' TERM; sleep 5 & wait"],
                          "timeout_ms": 100, "exit": "x.txt"}, self.d))
        self.assertEqual(code, 7)
        self.assertEqual(self.read("x.txt"), "7\n")

    def test_no_timeout_when_fast_or_zero(self):
        self.assertEqual(run(parse({"argv": ["sh", "-c", "exit 2"], "timeout_ms": 5000}, self.d)), 2)
        self.assertEqual(run(parse({"argv": ["sh", "-c", "exit 2"], "timeout_ms": 0}, self.d)), 2)

    def test_timeout_type(self):
        for k in ("timeout_ms", "timeout_grace_ms"):
            for t in (-1, 1.5, "100", True, None):
                with self.subTest(k=k, t=t):
                    self.fails("FieldType", {"argv": ["a"], k: t})


class TestCli(Base):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", os.path.join(LIB, "aos_inst.py")] + list(args),
                              capture_output=True, text=True, timeout=10, cwd=self.d)

    def test_child_code_not_returned(self):
        """子程式回 4，命令列照樣 0；4 只在 exit 檔裡。"""
        self.write(".aos/inst.json", {"argv": ["sh", "-c", "exit 4"], "exit": "x.txt"})
        r = self.cli(self.d)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.read("x.txt"), "4\n")

    def test_inst_error_is_1_one_line(self):
        p = self.cli(self.d)
        self.assertEqual(p.returncode, 1)
        self.assertTrue(p.stderr.startswith("NotFound: "))
        self.assertEqual(len(p.stderr.splitlines()), 1)

    def test_usage_and_launch_failures_are_1(self):
        self.assertEqual(self.cli().returncode, 1)
        self.assertEqual(self.cli(self.d, "extra").returncode, 1)
        for doc, code in (({"argv": ["true"], "stdin": "missing.txt"}, "OpenFailed"),
                          ({"argv": ["no-such-program-xyz"]}, "CommandNotFound")):
            with self.subTest(code=code):
                r = self.cli(self.write("i.json", doc))
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stderr.startswith(code + ": "), r.stderr)


if __name__ == "__main__":
    unittest.main()
