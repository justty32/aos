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

    def table(self, states, start="a", name="fsm.json", **extra):
        p = self.tmp / name
        p.write_text(json.dumps(dict(extra, start=start, states=states)))
        return str(p)

    def body(self, name, inst, nxt="a"):
        # 內嵌單子的格（10-21 plan F2）：val 指到同一格的 body
        return {"val": "fsm.json#/states/%s/body" % name, "body": inst, "next": nxt}

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

    def test_body_cell_timeout_no_timed_out_field(self):
        # 格是 fsm.json#/states/a/body：aos-exec 行程內跑單子、當監工；逾時收掉後 fsm 只看到結束碼 143（F3、F4）
        self.table({"a": self.body("a", {"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 300})})
        r = self.beat()
        self.assertEqual(r.returncode, 143, r.stderr)
        t = self.trace()[0]
        self.assertNotIn("timed_out", t)
        self.assertEqual(t["code"], 143)
        self.assertIsNone(t["signal"])   # 格（aos-exec）自己以 143 結束，不是被訊號殺掉（10-22 檔頭更正）
        self.assertLess(t["ms"], 5000)
        self.assertFalse((self.stack / "state").exists())

    def test_body_cell_exit_code_and_env_resolved(self):
        self.table({"a": self.body("a", {"argv": ["sh", "-c", "echo hi; exit 4"],
                                         "stdout": {"$env": "AOS_STACK", "$path": "out.txt"}})})
        self.assertEqual(self.beat().returncode, 4)
        self.assertEqual((self.stack / "out.txt").read_text(), "hi\n")
        self.assertFalse((self.stack / "state").exists())

    def test_object_val_is_own_error(self):
        # F2：val 只收字串；物件＝表壞，退 1、一行、提 #/states/<名>/body
        self.table({"a": {"val": {"argv": ["sh", "-c", 'touch "$AOS_STACK/ran"']}, "next": "a"}})
        r = self.beat()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-fsm: "), r.stderr)
        self.assertIn("#/states/a/body", r.stderr)
        self.assertFalse((self.stack / "ran").exists())
        self.assertFalse((self.stack / "trace.jsonl").exists())

    def test_cfg_is_only_positional(self):
        # 10-21 傍晚 ideas § 9：aos-fsm [旗標] 設定檔（原 --cfg 拿掉）；可寫 檔#/指標；沒給、多給、--cfg、不認得的旗標＝usage 錯
        self.cell("a", "exit 0\n")
        f = self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
        r = run(FSM, "--", f, stack=self.stack, cwd=str(self.tmp))
        self.assertEqual((r.returncode, r.stderr, self.state()), (0, "", "b\n"))
        (self.tmp / "big.json").write_text(json.dumps({"fsms": {"x": {"start": "a", "states": {
            "a": {"val": "a", "next": "c"}, "c": {"val": "a", "next": "a"}}}}}))
        (self.stack / "state").unlink()
        r = run(FSM, str(self.tmp / "big.json") + "#/fsms/x", stack=self.stack, cwd=str(self.tmp))
        self.assertEqual((r.returncode, r.stderr, self.state()), (0, "", "c\n"))
        for argv in ([], ["--cfg", f], ["--cfg=" + f], [f, "extra"], ["--max", "1", f]):
            r = run(FSM, *argv, stack=self.stack, cwd=str(self.tmp))
            self.assertEqual(r.returncode, 1, argv)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, argv)
            self.assertTrue(r.stderr.startswith("aos-fsm: usage: aos-fsm [旗標] 設定檔.json（"), (argv, r.stderr))   # 10-22 USAGE 補 [旗標]
        for argv in ([f + "#/nope"], [f + "#x"], [f + "#/start"]):
            r = run(FSM, *argv, stack=self.stack, cwd=str(self.tmp))
            self.assertEqual((r.returncode, len(r.stderr.strip().splitlines())), (1, 1), argv)
            self.assertTrue(r.stderr.startswith("aos-fsm: ") and "usage" not in r.stderr, (argv, r.stderr))
        self.assertEqual(self.state(), "c\n")   # 錯就不跑格

    def test_val_array_args(self):
        # val＝[目標, 參數...]（比照 loop 的 run）：每拍 aos-exec -- 目標 參數...；元素不是字串、空陣列＝表壞
        self.cell("a", 'echo "$@" > "$AOS_STACK/args"\n')
        self.table({"a": {"val": ["a", "x", "--y"], "next": "a"}})
        r = self.beat()
        self.assertEqual((r.returncode, r.stderr, (self.stack / "args").read_text()), (0, "", "x --y\n"))
        for bad in ([], ["a", 1], 3):
            self.table({"a": {"val": bad, "next": "a"}})
            r = self.beat()
            self.assertEqual((r.returncode, len(r.stderr.strip().splitlines())), (1, 1), bad)
            self.assertTrue(r.stderr.startswith("aos-fsm: "), r.stderr)

    def test_fsm_json_as_exec_entry(self):
        # F6：fsm.json 帶 _exec，`aos-exec fsm.json` 就是一拍；cwd＝fsm.json 的資料夾，表裡的 _exec、body 都被 fsm 忽略
        self.cell("a", 'touch "$AOS_STACK/ran"\n')   # 從 elsewhere 叫也找得到 a＝fsm 的 cwd 是 fsm.json 的資料夾
        f = self.table({"a": {"val": "a", "next": "b"}, "b": self.body("b", {"argv": ["sh", "-c", "exit 10"]})},
                       _exec=["aos-fsm", {"$env": "AOS_CF"}])
        other = self.tmp / "elsewhere"; other.mkdir()
        e = {"AOS_WS": str(self.tmp)}
        self.assertEqual(run(str(BIN / "aos-exec"), f, stack=self.stack, cwd=str(other), env=e).returncode, 0)
        self.assertEqual(self.state(), "b\n")
        self.assertTrue((self.stack / "ran").exists())
        r = run(str(BIN / "aos-exec"), f, stack=self.stack, cwd=str(other), env=e)
        self.assertEqual(r.returncode, 10, r.stderr)
        self.assertEqual([(t["state"], t["code"]) for t in self.trace()], [("a", 0), ("b", 10)])

    def test_trace_jsonl_one_line_per_beat(self):
        self.cell("a", "exit 0\n"); self.cell("b", "exit 5\n")
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "b", "next": "a"}})
        for _ in range(3):
            self.beat()
        tr = self.trace()
        self.assertEqual([(t["state"], t["code"]) for t in tr], [("a", 0), ("b", 5), ("b", 5)])
        self.assertEqual(set(tr[0]), {"at", "state", "code", "signal", "ms"})   # F4：沒有 timed_out
        for t in tr:
            datetime.datetime.fromisoformat(t["at"])

    def test_requires_stack(self):
        self.table({"a": {"val": "a", "next": "a"}})
        r = run(FSM, str(self.tmp / "fsm.json"), cwd=str(self.tmp))
        self.assertEqual(r.returncode, 1)
        self.assertIn("沒設定 AOS_STACK", r.stderr)

    def test_own_errors_exit_1_one_line(self):
        self.table({"a": {"val": "a", "next": "a"}})
        (self.stack / "state").write_text("zzz\n")
        bad = self.tmp / "bad.json"; bad.write_text("{nope")
        for f in (self.tmp / "fsm.json", bad, self.tmp / "absent.json"):
            r = self.beat(str(f))
            self.assertEqual(r.returncode, 1, str(f))
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, str(f))
            self.assertTrue(r.stderr.startswith("aos-fsm: "), str(f))

    def assert_own_error_no_beat(self, r, what):
        self.assertEqual(r.returncode, 1, (what, r.stderr))
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, (what, r.stderr))
        self.assertTrue(r.stderr.startswith("aos-fsm: "), (what, r.stderr))
        self.assertNotIn("Traceback", r.stderr, what)
        self.assertFalse((self.stack / "ran").exists(), what)   # 不跑格
        self.assertFalse((self.stack / "trace.jsonl").exists(), what)

    def test_state_exists_but_unreadable_is_own_error(self):
        # 10-22 a：state 在但讀不了（是資料夾、不是 UTF-8、沒權限）＝自己的錯，退 1、一行、不跑格（原本前兩種當沒有檔從 start 跑、
        # 不是 UTF-8 吐 traceback）；沒有檔照舊＝start
        self.cell("a", 'touch "$AOS_STACK/ran"\n')
        self.table({"a": {"val": "a", "next": "b"}, "b": {"val": "a", "next": "a"}})
        sf = self.stack / "state"
        sf.mkdir()
        self.assert_own_error_no_beat(self.beat(), "是資料夾")
        sf.rmdir()
        sf.write_bytes(b"\xff\xfe\n")
        self.assert_own_error_no_beat(self.beat(), "不是 UTF-8")
        self.assertEqual(sf.read_bytes(), b"\xff\xfe\n")
        if os.geteuid() != 0:   # root 讀得到沒權限的檔
            sf.write_text("b\n"); sf.chmod(0)
            try:
                self.assert_own_error_no_beat(self.beat(), "沒權限")
            finally:
                sf.chmod(0o644)
        sf.unlink()
        r = self.beat()
        self.assertEqual((r.returncode, r.stderr, self.state()), (0, "", "b\n"))   # 沒有檔＝start

    def test_whole_table_checked_before_beat(self):
        # 10-22 b、c：開跑時查整張表——start 不在表上、任何一格的 next 不在表上或是空字串（或頭尾有空白、不是字串）、
        # 任何一格的 val 壞，都＝表壞、退 1、不跑格（原本只查這拍那一格：next 不在表上要到下一拍才擋、空字串下一拍靜靜回 start）
        self.cell("a", 'touch "$AOS_STACK/ran"\n')
        good = {"val": "a", "next": "a"}
        for what, start, states in (
                ("start 不在表上", "zz", {"a": good}),
                ("next 不在表上", "a", {"a": {"val": "a", "next": "nope"}}),
                ("別格 next 不在表上", "a", {"a": good, "b": {"val": "a", "next": "nope"}}),
                ("next 空字串", "a", {"a": {"val": "a", "next": ""}}),
                ("別格 next 空字串", "a", {"a": good, "b": {"val": "a", "next": ""}}),
                ("next 頭尾空白", "a", {"a": {"val": "a", "next": " a"}, " a": good}),
                ("next 有換行", "a", {"a": {"val": "a", "next": "x\ny"}, "x\ny": good}),
                ("next 不是字串", "a", {"a": good, "b": {"val": "a", "next": 3}}),
                ("別格沒 next", "a", {"a": good, "b": {"val": "a"}}),
                ("別格不是物件", "a", {"a": good, "b": "a"}),
                ("別格 val 是物件", "a", {"a": good, "b": {"val": {"argv": ["true"]}, "next": "a"}}),
                ("別格 val 空陣列", "a", {"a": good, "b": {"val": [], "next": "a"}})):
            self.table(states, start=start)
            self.assert_own_error_no_beat(self.beat(), what)

    def test_state_value_not_in_table_is_own_error(self):
        # state 檔裡的狀態不在表上：照舊是自己的錯、退 1、不跑格（10-22 寫清楚）
        self.cell("a", 'touch "$AOS_STACK/ran"\n')
        self.table({"a": {"val": "a", "next": "a"}})
        (self.stack / "state").write_text("zzz\n")
        r = self.beat()
        self.assert_own_error_no_beat(r, "state 不在表上")
        self.assertIn("zzz", r.stderr)

    def test_broken_cell_is_aos_exec_error_passed_up(self):
        # 格指到跑不起來的東西：那是 aos-exec 的錯（它退 1、自己說），fsm 只把碼往上傳、不轉述（C-52）
        self.table({"a": self.body("a", {"argv": ["no-such-cmd-xyz"]})})
        r = self.beat()
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-exec: "), r.stderr)
        self.assertNotIn("aos-fsm", r.stderr)
        self.assertEqual(self.trace()[0]["code"], 1)

    def test_outer_timeout_kills_nested_tree(self):
        self.cell("slow/inner", 'echo $$ > "$AOS_STACK/pid"\nexec sleep 30\n')
        self.cell("slow", "aos-exec inner\n")
        self.table({"a": self.body("a", {"argv": ["aos-exec", "slow"], "timeout_ms": 300, "grace_ms": 200})})
        t0 = time.monotonic()
        r = self.beat()
        self.assertLess(time.monotonic() - t0, 10)   # 孤兒 sleep 會握著 pipe 拖滿 30 秒
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("timed_out", self.trace()[0])
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

    def test_sigint_body_cell(self):
        # 格是單子：fsm 把 SIGINT 轉給 aos-exec、aos-exec 轉給整群；aos-exec 以子程式的碼 130 正常結束（signal 是 null）
        self.table({"a": self.body("a", {"argv": ["sh", "-c", 'touch "$AOS_STACK/up"; exec sleep 30']})})
        p = self.start()
        ok = self.wait_file(self.stack / "up")
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=20)
        x = self.trace()[0]
        self.assertEqual((ok, p.returncode, x["code"], x["signal"], (self.stack / "state").exists()),
                         (True, 130, 130, None, False))


if __name__ == "__main__":
    unittest.main()
