"""inst 單子。10-22 使用者「aos-inst指令可以刪掉了，跟C++版一樣做成lib就好」：aos-inst 命令列刪了，
原本叫 aos-inst 的案例改成經 aos-exec 跑同一張單子（沒 +x 的 JSON 檔＝inst 單子入口，行程內交給 libaos）；
10-23 Python 版刪了（使用者「python版本可以刪掉了」）：原本直接叫 Python 庫 aos_inst.run 的案例改成經 aos-exec 看行為，只測庫回傳形狀的拿掉；
單子的錯＝aos-exec 退 1、一行「aos-exec: 代號 單子跑不起來：…」（10-23 起帶代號，own_error 對過再拿掉）（JSON 壞、檔不在、不是單子則是入口的錯）。"""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉

from aos_bins import EXEC, path_with  # noqa: E402  四支 C++ 在 impls/<名>/bin/（10-23）


def run(*args, env=None, **kw):
    # aos 的程式都不動 PATH（ideas § 24）：入口裡叫 aos-exec，由呼叫者把各支的 bin/ 放進 PATH
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws0"
        self.ws.mkdir()

    def single(self, doc, name="s.json", shebang=False):
        p = self.tmp / name
        p.write_text(("#!/usr/bin/env 隨便\n" if shebang else "") + json.dumps(doc))
        return str(p)

    def inst(self, f, *args, **kw):
        """經 aos-exec 跑一張單子檔（原本的 aos-inst FILE args...）。"""
        return run(EXEC, "--ws", str(self.ws), f, *args, **kw)

    def test_argv_runs(self):
        r = self.inst(self.single({"argv": ["echo", "hi"]}))
        self.assertEqual((r.returncode, r.stdout), (0, "hi\n"))

    def test_exit_code_passthrough(self):
        for n in (7, 10):
            r = self.inst(self.single({"argv": ["sh", "-c", f"exit {n}"]}))
            self.assertEqual(r.returncode, n)

    def test_own_errors_exit_1_one_line(self):
        cases = {
            "not_object": [1, 2],
            "no_argv": {"cwd": "."},
            "no_command": {"argv": ["no-such-command-xyz"]},
            "env_unset": {"argv": ["echo", {"$env": "AOS_NOPE_NOT_SET"}]},
        }
        for name, doc in cases.items():
            r = self.inst(self.single(doc, name + ".json"))
            self.assertEqual(r.returncode, 1, name)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, name)
            self.assertTrue(r.stderr.startswith("aos-exec: "), name)
        for name in ("no_command", "env_unset"):   # 單子本身的錯
            r = self.inst(str(self.tmp / (name + ".json")))
            self.assertTrue(r.stderr.startswith("aos-exec: 單子跑不起來："), (name, r.stderr))
        # 起不來的原因字（10-23 命名統合，統合前叫 CommandNotFound／CommandNotExecutable）
        noexec = self.tmp / "noexec"; noexec.write_text("x")
        for doc, head in (({"argv": ["no-such-command-xyz"]}, "LaunchFailed 單子跑不起來：CommandMissing "),
                          ({"argv": ["noexec"], "envs": {"PATH": str(self.tmp)}}, "LaunchFailed 單子跑不起來：CommandBad ")):
            r = self.inst(self.single(doc, "launch.json"))
            self.assertTrue(r.raw_stderr.startswith("aos-exec: " + head), r.raw_stderr)
        r = self.inst(self.single({"argv": ["echo", {"$env": "AOS_NOPE_NOT_SET"}]}))
        self.assertIn("AOS_NOPE_NOT_SET", r.stderr)
        for k, v in (("timeout_ms", 0), ("grace_ms", -1), ("envs", {"A": 1}), ("cwd", 3), ("stdout_append", "y")):
            r = self.inst(self.single({"argv": ["true"], k: v}, k + ".json"))
            self.assertEqual(r.returncode, 1, k)
            # 10-23 起照 C++ 版的字面「單子的 <key> …」（Python 版是 key 名開頭；使用者 10-23 說兩版這個差別照現狀留，Python 版刪了就照 C++）
            self.assertTrue(r.stderr.startswith("aos-exec: 單子跑不起來：單子的 %s " % k), (k, r.stderr))
        r = self.inst(self.single({"argv": []}, "empty.json"))   # 原本直接叫庫（丟 InstError），10-23 改經 aos-exec
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_bad_json_and_missing_file(self):
        p = self.tmp / "bad.json"; p.write_text("{nope")
        self.assertEqual(self.inst(str(p)).returncode, 1)
        r = self.inst(str(self.tmp / "absent.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-exec:", r.stderr)
        # 單子檔本身不在＝EntryMissing、不是 JSON＝EntryBad（10-23 命名統合，統合前叫 ReadFailed／JsonSyntax；
        # 原本直接叫 Python 庫的 run(FILE) 看例外的代號，10-23 改經 aos-exec 看錯誤一行的代號）
        self.assertTrue(self.inst(str(p)).raw_stderr.startswith("aos-exec: EntryBad "))
        self.assertTrue(r.raw_stderr.startswith("aos-exec: EntryMissing "), r.raw_stderr)

    def test_timeout_kills(self):
        t0 = time.monotonic()   # 原本直接叫庫看 timed_out／elapsed_ms，10-23 改經 aos-exec 看時間與結束碼
        r = self.inst(self.single({"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 500}))
        self.assertNotEqual(r.returncode, 0)
        self.assertLess(time.monotonic() - t0, 5)

    def test_stdout_to_file_and_append(self):
        d = self.tmp / "w"; d.mkdir()
        doc = {"argv": ["echo", "one"], "cwd": str(d), "stdout": "o.txt"}
        r = self.inst(self.single(doc))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual((d / "o.txt").read_text(), "one\n")
        self.inst(self.single(dict(doc, argv=["echo", "two"])))
        self.assertEqual((d / "o.txt").read_text(), "two\n")
        self.inst(self.single(dict(doc, argv=["echo", "three"], stdout_append=True)))
        self.assertEqual((d / "o.txt").read_text(), "two\nthree\n")

    def test_stdin_file(self):
        (self.tmp / "in.txt").write_text("from file")
        r = self.inst(self.single({"argv": ["cat"], "stdin": str(self.tmp / "in.txt")}))
        self.assertEqual(r.stdout, "from file")

    def test_unset_streams_inherit(self):
        r = self.inst(self.single({"argv": ["sh", "-c", "echo err >&2; cat"]}), input="in")
        self.assertEqual((r.stdout, r.stderr), ("in", "err\n"))

    def test_shebang_line_skipped(self):
        r = self.inst(self.single({"argv": ["echo", "ok"]}, shebang=True))
        self.assertEqual((r.returncode, r.stdout), (0, "ok\n"))

    def test_unknown_keys_ignored(self):
        r = self.inst(self.single({"argv": ["echo", "ok"], "bogus": {"a": 1}, "id": "x"}))
        self.assertEqual((r.returncode, r.stdout), (0, "ok\n"))

    def test_args_appended_to_argv(self):
        r = self.inst(self.single({"argv": ["echo", "a"]}), "b", "c")
        self.assertEqual(r.stdout, "a b c\n")

    def test_envs(self):
        r = self.inst(self.single({"argv": ["sh", "-c", "echo $FOO"], "envs": {"FOO": "bar"}}))
        self.assertEqual(r.stdout, "bar\n")

    def test_env_path_with_trailing_slash_and_without(self):
        stack, ws = self.tmp / "stack", self.tmp / "ws"
        stack.mkdir(); ws.mkdir()
        doc = {"argv": ["echo", "x"],
               "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"},
               "stderr": {"$env": "AOS_WS", "$path": "err"}}
        r = run(EXEC, "--ws", str(ws), self.single(doc), env={"AOS_STACK": str(stack) + "/"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((stack / "plan.txt").read_text(), "x\n")
        self.assertTrue((ws / "err").exists())
        # 不帶 path：整個變數值
        r = run(EXEC, "--ws", str(ws), self.single({"argv": ["echo", {"$env": "AOS_WS"}]}))
        self.assertEqual(r.stdout.strip(), str(ws))

    def test_entry_inst_in_exec_file(self):
        # 原本是 (A)：+x 的 _entry 第一行 `#!/usr/bin/env aos-inst`；aos-inst 刪了（10-22），改成沒 +x 的 _entry 放單子
        # （第一行 #! 照樣跳過），由 aos-exec 行程內跑——同 C++ 版
        d = self.tmp / "prog"; d.mkdir(parents=True)
        entry = d / "_entry"
        entry.write_text('#!/usr/bin/env 隨便\n' + json.dumps(
            {"argv": ["sh", "-c", 'pwd; echo "$1"; exit 4', "sh"],
             "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}}))
        entry.chmod(0o644)
        ws = self.tmp / "ws"; ws.mkdir()
        r = run(EXEC, "--ws", str(ws), str(d), "arg1")
        self.assertEqual(r.returncode, 4, r.stderr)
        lines = (ws / ".stack" / "plan.txt").read_text().split("\n")
        self.assertEqual(lines[0], str(d))
        self.assertEqual(lines[1], "arg1")


    def test_timeout_kills_grandchildren(self):
        nl = chr(10)
        inner = self.tmp / "inner"; inner.mkdir(parents=True)
        (inner / "_entry").write_text("#!/bin/sh" + nl + 'echo $$ > "$AOS_STACK/pid"' + nl + "exec sleep 30" + nl)
        (inner / "_entry").chmod(0o755)
        outer = self.tmp / "outer"; outer.mkdir(parents=True)
        (outer / "_entry").write_text("#!/bin/sh" + nl + "aos-exec %s" % (self.tmp / "inner") + nl)
        (outer / "_entry").chmod(0o755)
        ws = self.ws   # 外層 aos-exec 定的 AOS_STACK（ws/.stack/）一路傳給 inner
        # 原本直接叫 Python 庫 aos_inst.run 看 timed_out，10-23 改成一張限時的單子經 aos-exec 跑
        t0 = time.monotonic()
        r = self.inst(self.single({"argv": ["aos-exec", "--ws", str(ws), str(self.tmp / "outer")],
                                   "timeout_ms": 300, "grace_ms": 200}))
        self.assertNotEqual(r.returncode, 0, r.stderr)
        self.assertLess(time.monotonic() - t0, 5)
        pid = int((ws / ".stack" / "pid").read_text())
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
