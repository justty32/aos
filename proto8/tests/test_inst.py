import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
INST = str(BIN / "aos-inst")
EXEC = str(BIN / "aos-exec")
sys.path.insert(0, str(BIN))
import aos_inst  # noqa: E402


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def single(self, doc, name="s.json", shebang=False):
        p = self.tmp / name
        p.write_text(("#!/usr/bin/env aos-inst\n" if shebang else "") + json.dumps(doc))
        return str(p)

    def test_argv_runs(self):
        r = run(INST, self.single({"argv": ["echo", "hi"]}))
        self.assertEqual((r.returncode, r.stdout), (0, "hi\n"))

    def test_exit_code_passthrough(self):
        for n in (7, 10):
            r = run(INST, self.single({"argv": ["sh", "-c", f"exit {n}"]}))
            self.assertEqual(r.returncode, n)

    def test_own_errors_exit_1_one_line(self):
        cases = {
            "not_object": [1, 2],
            "no_argv": {"cwd": "."},
            "no_command": {"argv": ["no-such-command-xyz"]},
            "env_unset": {"argv": ["echo", {"$env": "AOS_NOPE_NOT_SET"}]},
        }
        for name, doc in cases.items():
            r = run(INST, self.single(doc, name + ".json"))
            self.assertEqual(r.returncode, 1, name)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, name)
            self.assertTrue(r.stderr.startswith("aos-inst: "), name)
        r = run(INST, self.single({"argv": ["echo", {"$env": "AOS_NOPE_NOT_SET"}]}))
        self.assertIn("AOS_NOPE_NOT_SET", r.stderr)

    def test_bad_json_and_missing_file(self):
        p = self.tmp / "bad.json"; p.write_text("{nope")
        self.assertEqual(run(INST, str(p)).returncode, 1)
        r = run(INST, str(self.tmp / "absent.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-inst:", r.stderr)

    def test_timeout_kills(self):
        res = aos_inst.run({"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 500})
        self.assertTrue(res["timed_out"])
        self.assertLess(res["ms"], 5000)
        r = run(INST, self.single({"argv": ["sleep", "30"], "timeout_ms": 200}))
        self.assertNotEqual(r.returncode, 0)

    def test_run_result_shape(self):
        res = aos_inst.run({"argv": ["sh", "-c", "exit 3"]})
        self.assertEqual(set(res), {"code", "signal", "timed_out", "pid", "ms"})
        self.assertEqual((res["code"], res["signal"], res["timed_out"]), (3, None, False))

    def test_stdout_to_file_and_append(self):
        d = self.tmp / "w"; d.mkdir()
        doc = {"argv": ["echo", "one"], "cwd": str(d), "stdout": "o.txt"}
        r = run(INST, self.single(doc))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual((d / "o.txt").read_text(), "one\n")
        run(INST, self.single(dict(doc, argv=["echo", "two"])))
        self.assertEqual((d / "o.txt").read_text(), "two\n")
        run(INST, self.single(dict(doc, argv=["echo", "three"], stdout_append=True)))
        self.assertEqual((d / "o.txt").read_text(), "two\nthree\n")

    def test_stdin_file(self):
        (self.tmp / "in.txt").write_text("from file")
        r = run(INST, self.single({"argv": ["cat"], "stdin": str(self.tmp / "in.txt")}))
        self.assertEqual(r.stdout, "from file")

    def test_unset_streams_inherit(self):
        r = run(INST, self.single({"argv": ["sh", "-c", "echo err >&2; cat"]}), input="in")
        self.assertEqual((r.stdout, r.stderr), ("in", "err\n"))

    def test_shebang_line_skipped(self):
        r = run(INST, self.single({"argv": ["echo", "ok"]}, shebang=True))
        self.assertEqual((r.returncode, r.stdout), (0, "ok\n"))

    def test_unknown_keys_ignored(self):
        r = run(INST, self.single({"argv": ["echo", "ok"], "bogus": {"a": 1}, "id": "x"}))
        self.assertEqual((r.returncode, r.stdout), (0, "ok\n"))

    def test_args_appended_to_argv(self):
        r = run(INST, self.single({"argv": ["echo", "a"]}), "b", "c")
        self.assertEqual(r.stdout, "a b c\n")

    def test_envs(self):
        r = run(INST, self.single({"argv": ["sh", "-c", "echo $FOO"], "envs": {"FOO": "bar"}}))
        self.assertEqual(r.stdout, "bar\n")

    def test_env_path_with_trailing_slash_and_without(self):
        stack, ws = self.tmp / "stack", self.tmp / "ws"
        stack.mkdir(); ws.mkdir()
        doc = {"argv": ["echo", "x"],
               "stdout": {"$env": "AOS_STACK", "path": "plan"},
               "stderr": {"$env": "AOS_WS", "path": "err"}}
        r = run(INST, self.single(doc), env={"AOS_STACK": str(stack) + "/", "AOS_WS": str(ws)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((stack / "plan").read_text(), "x\n")
        self.assertTrue((ws / "err").exists())
        # 不帶 path：整個變數值
        r = run(INST, self.single({"argv": ["echo", {"$env": "AOS_WS"}]}), env={"AOS_WS": str(ws)})
        self.assertEqual(r.stdout.strip(), str(ws))

    def test_entry_form_A_via_aos_exec(self):
        d = self.tmp / "prog"; d.mkdir(parents=True)
        entry = d / "_exec"
        entry.write_text('#!/usr/bin/env aos-inst\n' + json.dumps(
            {"argv": ["sh", "-c", 'pwd; echo "$1"; exit 4', "sh"],
             "stdout": {"$env": "AOS_STACK", "path": "plan"}}))
        entry.chmod(0o755)
        ws = self.tmp / "ws"; ws.mkdir()
        r = run(EXEC, str(d), str(ws), "arg1")
        self.assertEqual(r.returncode, 4, r.stderr)
        lines = (ws / ".aos" / "plan").read_text().split("\n")
        self.assertEqual(lines[0], str(d))
        self.assertEqual(lines[1], "arg1")


    def test_timeout_kills_grandchildren(self):
        nl = chr(10)
        inner = self.tmp / "inner"; inner.mkdir(parents=True)
        (inner / "_exec").write_text("#!/bin/sh" + nl + 'echo $$ > "$AOS_STACK/pid"' + nl + "exec sleep 30" + nl)
        (inner / "_exec").chmod(0o755)
        outer = self.tmp / "outer"; outer.mkdir(parents=True)
        (outer / "_exec").write_text("#!/bin/sh" + nl + "aos-exec %s" % (self.tmp / "inner") + nl)
        (outer / "_exec").chmod(0o755)
        ws = self.tmp / "ws"; ws.mkdir()
        old = os.environ.copy()
        os.environ["PATH"] = str(BIN) + os.pathsep + os.environ["PATH"]
        os.environ.pop("AOS_STACK", None); os.environ.pop("AOS_WS", None)
        try:
            res = aos_inst.run({"argv": ["aos-exec", str(self.tmp / "outer"), str(ws)],
                                "timeout_ms": 300, "grace_ms": 200})
        finally:
            os.environ.clear(); os.environ.update(old)
        self.assertTrue(res["timed_out"])
        pid = int((ws / ".aos" / "pid").read_text())
        gone = False
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                gone = True
                break
            time.sleep(0.05)
        self.assertTrue(gone, "孫程式 sleep 還活著")


if __name__ == "__main__":
    unittest.main()
