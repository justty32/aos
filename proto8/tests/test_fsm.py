import datetime, json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
FSM = str(BIN / "aos-fsm")


def run(*args, stack=None, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
    e["PATH"] = str(BIN) + os.pathsep + e["PATH"]
    if stack is not None:
        e["AOS_STACK"] = str(stack)
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.stack = self.tmp / "stack"
        self.stack.mkdir()

    def cell(self, name, body):
        d = self.tmp / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "_exec").write_text("#!/bin/sh\n" + body)
        (d / "_exec").chmod(0o755)

    def table(self, states, start="a"):
        p = self.tmp / "fsm.json"
        p.write_text(json.dumps({"start": start, "states": states}))
        return str(p)

    def beat(self, fsm=None, **kw):
        return run(FSM, fsm or str(self.tmp / "fsm.json"), stack=self.stack, cwd=str(self.tmp), **kw)

    def state(self):
        return (self.stack / "state").read_text()

    def trace(self):
        return [json.loads(l) for l in (self.stack / "trace.jsonl").read_text().splitlines()]

    def test_state_in_stack_and_advances(self):
        self.cell("a", "exit 0\n"); self.cell("b", "exit 0\n")
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}})
        r = self.beat()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state(), "b\n")   # 純文字一行狀態名，跟 shell 版同格式
        self.beat()
        self.assertEqual(self.state(), "a\n")
        self.assertEqual(list(self.tmp.glob("state")), [])

    def test_state_written_by_rename_not_in_place(self):
        # N-05：先寫 .state 再改名蓋過去——蓋完 inode 換了、不留暫存檔
        self.cell("a", "exit 0\n"); self.cell("b", "exit 0\n")
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}})
        (self.stack / "state").write_text("a\n")
        before = os.stat(self.stack / "state").st_ino
        self.assertEqual(self.beat().returncode, 0)
        self.assertEqual(self.state(), "b\n")
        self.assertNotEqual(os.stat(self.stack / "state").st_ino, before)
        self.assertFalse((self.stack / ".state").exists())

    def test_cell_10_passes_up_and_state_unchanged(self):
        self.cell("a", "exit 10\n"); self.cell("b", "exit 0\n")
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}})
        (self.stack / "state").write_text("a\n")
        self.assertEqual(self.beat().returncode, 10)
        self.assertEqual(self.state(), "a\n")

    def test_cell_failure_code_state_unchanged(self):
        self.cell("a", "exit 3\n")
        self.table({"a": {"val": "a", "next": "a"}, "b": {"val": "a", "next": "a"}})
        (self.stack / "state").write_text("b\n")
        self.assertEqual(self.beat().returncode, 3)
        self.assertEqual(self.state(), "b\n")

    def test_string_cell_goes_through_aos_exec(self):
        self.cell("a", 'echo "$AOS_STACK" > "$AOS_STACK/seen"\n')
        self.table({"a": {"val": "a", "next": "a"}})
        self.assertEqual(self.beat().returncode, 0)
        self.assertEqual((self.stack / "seen").read_text().strip(), str(self.stack) + "/")

    def test_object_cell_in_process_with_timeout(self):
        self.table({"a": {"val": {"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 300}, "next": "a"}})
        r = self.beat()
        self.assertNotEqual(r.returncode, 0)
        t = self.trace()[0]
        self.assertTrue(t["timed_out"])
        self.assertLess(t["ms"], 5000)
        self.assertFalse((self.stack / "state").exists())

    def test_object_cell_exit_code_and_env_resolved(self):
        self.table({"a": {"val": {"argv": ["sh", "-c", "echo hi; exit 4"],
                                  "stdout": {"$env": "AOS_STACK", "path": "out.txt"}}, "next": "a"}})
        self.assertEqual(self.beat().returncode, 4)
        self.assertEqual((self.stack / "out.txt").read_text(), "hi\n")
        self.assertFalse((self.stack / "state").exists())

    def test_trace_jsonl_one_line_per_beat(self):
        self.cell("a", "exit 0\n"); self.cell("b", "exit 5\n")
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}})
        for _ in range(3):
            self.beat()
        tr = self.trace()
        self.assertEqual([(t["state"], t["code"]) for t in tr], [("a", 0), ("b", 5), ("b", 5)])
        self.assertEqual(set(tr[0]), {"at", "state", "code", "signal", "timed_out", "ms"})
        for t in tr:
            datetime.datetime.fromisoformat(t["at"])

    def test_requires_stack(self):
        self.table({"a": {"val": {"argv": ["true"]}, "next": "a"}})
        r = run(FSM, str(self.tmp / "fsm.json"), cwd=str(self.tmp))
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒設定 AOS_STACK", r.stderr)

    def test_own_errors_exit_1_one_line(self):
        self.table({"a": {"val": {"argv": ["true"]}, "next": "a"}})
        (self.stack / "state").write_text("zzz\n")
        bad = self.tmp / "bad.json"; bad.write_text("{nope")
        nocmd = self.tmp / "nocmd.json"
        nocmd.write_text(json.dumps({"start": "a", "states": {"a": {"val": {"argv": ["no-such-cmd-xyz"]}, "next": "a"}}}))
        for f in (self.tmp / "fsm.json", bad, self.tmp / "absent.json", nocmd):
            if f == nocmd:
                (self.stack / "state").write_text("a\n")
            r = self.beat(str(f))
            self.assertEqual(r.returncode, 1, str(f))
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, str(f))
            self.assertTrue(r.stderr.startswith("aos-fsm: "), str(f))

    def test_outer_timeout_kills_nested_tree(self):
        self.cell("slow/inner", 'echo $$ > "$AOS_STACK/pid"\nexec sleep 30\n')
        self.cell("slow", "aos-exec inner\n")
        self.table({"a": {"val": {"argv": ["aos-exec", "slow"], "timeout_ms": 300, "grace_ms": 200},
                          "next": "a"}})
        t0 = time.monotonic()
        r = self.beat()
        self.assertLess(time.monotonic() - t0, 10)   # 孤兒 sleep 會握著 pipe 拖滿 30 秒
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(self.trace()[0]["timed_out"])
        self.assertFalse((self.stack / "state").exists())
        pid = int((self.stack / "pid").read_text())
        gone = False
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                gone = True
                break
            time.sleep(0.05)
        self.assertTrue(gone, "內層的 sleep 還活著")

    def test_string_cell_path_as_is(self):
        # ideas § 24：aos 的程式都不動 PATH，字串格看到的 PATH 跟 fsm 收到的一樣（不加任何 bin）
        self.cell("a", 'echo "$PATH" > "$AOS_STACK/path"\n')
        self.table({"a": {"val": "a", "next": "a"}})
        path = str(BIN) + ":/usr/bin:/bin"
        self.assertEqual(self.beat(env={"PATH": path}).returncode, 0)
        self.assertEqual((self.stack / "path").read_text().strip(), path)

    # 訊號（ideas § 24；移植自 proto8/impls/aos-fsm/tests/test_cli.py 的 C 段）
    def start(self):
        e = {k: v for k, v in os.environ.items() if k not in ("AOS_WS", "AOS_ENTRY", "AOS_STACK")}
        e["PATH"] = str(BIN) + os.pathsep + e["PATH"]
        e["AOS_STACK"] = str(self.stack)
        return subprocess.Popen([FSM, str(self.tmp / "fsm.json")], cwd=str(self.tmp), env=e,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_file(self, path, secs=10):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if path.exists():
                return True
            time.sleep(0.02)
        return False

    def test_sigterm_cell_finishes_then_143(self):
        # 格收到轉來的 SIGTERM 收好、退 0：trace 有一行、state 照樣換，fsm 再以 143 結束（P-36）
        self.cell("a", 'trap \'exit 0\' TERM\ntouch "$AOS_STACK/up"\nwhile :; do sleep 0.05; done\n')
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
        p = self.start()
        ok = self.wait_file(self.stack / "up")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=20)
        self.assertEqual((ok, p.returncode, err, self.state(), self.trace()[0]["code"]), (True, 143, "", "b\n", 0))

    def test_sigint_inst_cell(self):
        self.table({"a": {"val": {"argv": ["sh", "-c", 'touch "$AOS_STACK/up"; exec sleep 30']}, "next": "a"}})
        p = self.start()
        ok = self.wait_file(self.stack / "up")
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        x = self.trace()[0]
        self.assertEqual((ok, p.returncode, x["code"], x["signal"], (self.stack / "state").exists()),
                         (True, 130, 130, 2, False))


if __name__ == "__main__":
    unittest.main()
