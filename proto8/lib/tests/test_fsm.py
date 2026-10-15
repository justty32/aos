"""proto8/lib 的自動測試：fsm（aos_fsm、aos_methods）；起真的 aos_fsm 行程、走檔案。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。格多半用 sh：`cat >> NAME.args` 記下 fsm 給的 stdin（＝fsm 設定本身＋`fsm_state`），再 echo 一份結果。
"""
import json
import os
import signal
import subprocess
import sys

from helpers import FSM, Tmp
import aos_methods  # noqa: E402


def sh(name, script):
    """一格：在暫存資料夾跑 sh，先把 stdin（fsm 給的 args）附加到 NAME.args，再跑 script。"""
    return {"argv": ["sh", "-c", "cat >> %s.args; echo >> %s.args; %s" % (name, name, script)]}


class FsmTest(Tmp):
    def fsm(self, states, name="f", **keys):
        return self.write(name + ".json", dict({"start": "a", "states": states, "state": name + ".state.json"}, **keys))

    def tick(self, path, timeout=10):
        return subprocess.run([sys.executable, FSM, path], capture_output=True, text=True, cwd=self.tmp, timeout=timeout)

    def state(self, name="f.state.json"):
        return json.loads(self.read(name))

    def stdin(self, name):
        """格收到的 stdin（每次一份）。"""
        return [json.loads(x) for x in self.read(name + ".args").splitlines() if x.strip()]

    def args(self, name):
        """格收到的 state 窗（stdin 的 `fsm_state`）。"""
        return [d["fsm_state"] for d in self.stdin(name)]

    def cfg(self, name):
        """格收到的設定（stdin 拿掉 `fsm_state`）。"""
        return [{k: v for k, v in d.items() if k != "fsm_state"} for d in self.stdin(name)]

    def out(self, r):
        return [json.loads(x) for x in r.stdout.splitlines()]

    def test_first_tick_next_from_stdout(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"b\", \"data\": {\"x\": 1}}'"), "b": sh("b", "true")})
        self.assertFalse(os.path.exists(self.p("f.state.json")))
        r = self.tick(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        w = self.args("a")[0]                                                     # 第一拍從 start 起
        self.assertEqual((w["phase"], w["step"], w["running"], w["data"]), ("a", 0, False, None))
        st = self.state()
        self.assertEqual((st["phase"], st["data"], st["step"], st["running"], st["last_error"]),
                         ("b", {"x": 1}, 1, False, None))
        line = self.out(r)[0]                                                     # N-30 結果＋step／from／to
        self.assertEqual({k: line[k] for k in ("step", "from", "to", "code", "signal", "timed_out")},
                         {"step": 1, "from": "a", "to": "b", "code": 0, "signal": None, "timed_out": False})
        self.assertEqual(set(line), {"id", "code", "signal", "timed_out", "pid", "ms", "exit_file", "step", "from", "to"})
        self.tick(path)
        w = self.args("b")[0]                                                     # 格從 fsm_state 讀上一格的 data
        self.assertEqual((w["phase"], w["step"], w["data"]), ("b", 1, {"x": 1}))

    def test_cell_gets_cfg(self):
        # stdin＝這份 fsm 設定本身（有指示詞先解好）＋fsm_state；fsm 不認得的 key 也照帶
        os.environ["AOS_TEST_FSM_X"] = "hi"
        self.addCleanup(os.environ.pop, "AOS_TEST_FSM_X", None)
        doc = {"start": "a", "states": {"a": sh("a", "true")}, "state": "f.state.json",
               "brain": "b.json", "x": {"$env": "AOS_TEST_FSM_X"}}
        path = self.write("f.json", doc)
        self.assertEqual(self.tick(path).returncode, 0)
        self.assertEqual(self.cfg("a")[0], dict(doc, x="hi"))
        r = subprocess.run([sys.executable, FSM, "--max-steps", "5", path], capture_output=True, text=True,
                           cwd=self.tmp, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.cfg("a")[1]["max_steps"], 5)                         # 旗標也併進 cfg

    def test_static_next_and_stdout_wins(self):
        path = self.fsm({"a": {"target": sh("a", "true"), "next": "b"},
                         "b": {"target": sh("b", "echo '{\"next\": \"a\"}'"), "next": "b"}})
        self.tick(path)
        self.assertEqual(self.state()["phase"], "b")      # 沒吐 next＝表上靜態 next
        self.tick(path)
        self.assertEqual(self.state()["phase"], "a")      # stdout 的 next 蓋過表上的

    def test_stay_and_last_complete_json(self):
        # 沒 next、表上也沒有＝留原狀態；最後一份是半份＝不算，看前一份
        path = self.fsm({"a": sh("a", "echo '{\"data\": 7}'; printf '{\"next\": \"b\"'"), "b": sh("b", "true")})
        self.tick(path)
        st = self.state()
        self.assertEqual((st["phase"], st["data"], st["step"]), ("a", 7, 0))       # 待在 start：step 歸零

    def test_target_file_and_pointer(self):
        self.write("cells.json", {"one": sh("a", "echo '{\"next\": \"b\"}'")})
        path = self.fsm({"a": "cells.json#/one", "b": sh("b", "true")})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "b"), r.stderr)

    def test_next_not_in_table_is_error(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"zzz\"}'")})
        r = self.tick(path)
        self.assertEqual(r.returncode, 0, r.stderr)       # 格出錯由表處理，fsm 退 0
        st = self.state()
        self.assertEqual(st["phase"], "a")
        self.assertTrue(st["last_error"].startswith("UnknownNext"))
        self.assertEqual(self.out(r)[-1]["error"]["code"], "UnknownNext")          # N-29 形狀

    def test_error_cell_runs_next_tick(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"b\", \"data\": 5}'"), "b": sh("b", "exit 3"),
                         "error": sh("error", "echo '{\"next\": \"a\"}'")})
        self.tick(path)
        self.tick(path)                                   # b 結束碼 3 → 跳去 error，這拍不跑它
        st = self.state()
        self.assertFalse(os.path.exists(self.p("error.args")))
        self.assertEqual((st["phase"], st["step"]), ("error", 0))
        self.assertEqual((st["data"], st["error_from"]), (5, "b"))                 # data 照留、原狀態記在 error_from
        self.assertTrue(st["last_error"].startswith("CellFailed"))
        self.tick(path)
        w = self.args("error")[0]
        self.assertEqual((w["phase"], w["last_error"], w["error_from"], w["data"]), ("error", st["last_error"], "b", 5))
        self.assertEqual((self.state()["phase"], self.state()["last_error"], self.state()["error_from"]), ("a", None, None))

    def test_error_cell_failing_stays(self):
        path = self.fsm({"a": sh("a", "exit 1"), "error": sh("error", "exit 2")})
        self.tick(path)
        self.assertEqual(self.state()["phase"], "error")
        self.tick(path)
        st = self.state()
        self.assertEqual(st["phase"], "error")            # error 格自己出錯不再跳
        self.assertIn("結束碼 2", st["last_error"])

    def test_last_error_has_cell_own_error(self):
        # 格 stderr 吐 N-29 錯誤＝真正原因，接進 last_error（10-15 146 試跑後補）；沒吐就照舊寫結束碼
        path = self.fsm({"a": sh("a", "echo '{\"error\": {\"code\": \"BrainFailed\", \"msg\": \"HttpError: 400 no tools\"}}' >&2; exit 1")})
        self.tick(path)
        self.assertEqual(self.state()["last_error"], "CellFailed: BrainFailed: HttpError: 400 no tools")
        path = self.fsm({"a": sh("a", "exit 4")}, name="g")
        self.tick(path)
        self.assertEqual(self.state("g.state.json")["last_error"], "CellFailed: 格 a 結束碼 4")

    def test_stops_after_max_fails(self):
        path = self.fsm({"a": sh("a", "exit 1")}, max_fails=2)
        self.tick(path)
        self.assertEqual((self.state()["fails"], self.state()["halted"]), (1, False))
        self.tick(path)
        self.assertEqual((self.state()["fails"], self.state()["halted"]), (2, True))
        for _ in range(3):
            r = self.tick(path)
            self.assertEqual((r.returncode, r.stdout), (0, ""))          # 停住：不起格、不吐
        self.assertEqual(len(self.args("a")), 2)
        st = self.state()
        st["halted"] = False                                              # 人接手：拿掉 halted，再試一次
        self.write("f.state.json", st)
        self.tick(path)
        self.assertEqual(len(self.args("a")), 3)
        self.assertEqual((self.state()["fails"], self.state()["halted"]), (3, True))   # 又錯＝馬上再停

    def test_default_max_fails_and_reset_on_success(self):
        # 錯兩次、成功一次歸零、再錯兩次也不停（預設 3）；錯第三次才停
        self.write("n", "")
        path = self.fsm({"a": sh("a", "echo x >> n; c=$(wc -l < n); [ $c -ne 3 ] && [ $c -lt 6 ] && exit 1; true")})
        for _ in range(5):
            self.tick(path)
        self.assertEqual((self.state()["fails"], self.state()["halted"]), (2, False))
        self.tick(path)
        self.assertEqual((self.state()["fails"], self.state()["halted"]), (0, False))  # 第 6 次成功
        path2 = self.fsm({"a": sh("a", "exit 1")}, name="g")
        for _ in range(4):
            self.tick(path2)
        self.assertEqual(len(self.args("a")), 9)                          # g 起了 3 次（a 共 6＋3）
        self.assertEqual((self.state("g.state.json")["fails"], self.state("g.state.json")["halted"]), (3, True))

    def test_error_cell_then_halt(self):
        # 有 error 格照舊跳去；error 格也一直錯＝連續錯到 max_fails 就停住等人
        path = self.fsm({"a": sh("a", "exit 1"), "error": sh("error", "exit 2")})
        for _ in range(5):
            self.tick(path)
        st = self.state()
        self.assertEqual((st["phase"], st["fails"], st["halted"]), ("error", 3, True))
        self.assertEqual(len(self.args("error")), 2)

    def test_max_steps(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"b\"}'"), "b": sh("b", "true")}, max_steps=2)
        for _ in range(4):
            self.tick(path)
        st = self.state()
        self.assertEqual(len(self.args("b")), 1)          # a 第 1 格、b 第 2 格，之後再跑＝MaxSteps，不起格
        self.assertEqual((st["phase"], st["step"]), ("b", 2))
        self.assertTrue(st["last_error"].startswith("MaxSteps"))

    def test_killed_midway_reruns_with_interrupted(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"b\", \"data\": 9}'"),
                         "b": sh("b", "grep -q '\"running\": tru[e]' b.args || sleep 30")})   # [e]：cfg 裡帶著這段字，不能自己配到自己
        self.tick(path)
        p = subprocess.Popen([sys.executable, FSM, path], cwd=self.tmp, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.until(lambda: os.path.exists(self.p("b.args")) and self.state()["running"])
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        self.assertEqual((self.state()["phase"], self.state()["step"]), ("b", 2))
        r = self.tick(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        w = self.args("b")[-1]                                       # running 還是 true＝上一拍被殺一半
        self.assertEqual((w["phase"], w["step"], w["running"], w["data"]), ("b", 2, True, 9))
        self.assertFalse(self.state()["running"])

    def test_ctl_paused_and_stop_skip_tick(self):
        path = self.fsm({"a": sh("a", "echo '{\"next\": \"b\"}'"), "b": sh("b", "true")}, ctl="f.ctl.json")
        for ctl in ({"paused": True, "seq": 4}, {"stop": {"val": True, "now": False}, "seq": 5}):
            self.write("f.ctl.json", ctl)
            r = self.tick(path)
            self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
            self.assertFalse(os.path.exists(self.p("a.args")))
            st = self.state()
            self.assertEqual((st["phase"], st["ctl_seq"]), ("a", ctl["seq"]))
        self.write("f.ctl.json", {"seq": 6})
        self.tick(path)
        self.assertEqual((self.state()["phase"], self.state()["ctl_seq"]), ("b", 6))

    def test_missing_state_refused(self):
        path = self.write("f.json", {"start": "a", "states": {"a": sh("a", "true")}, "state": None})
        r = self.tick(path)
        self.assertEqual(r.returncode, 125)
        self.assertEqual(json.loads(r.stderr.splitlines()[-1])["error"]["code"], "WindowMissing")
        self.assertFalse(os.path.exists(self.p("a.args")))

    def test_lock_busy(self):
        path = self.fsm({"a": sh("a", "true")}, lock="f.lock")
        os.mkdir(self.p("f.lock"))
        r = self.tick(path)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stderr.splitlines()[-1])["error"]["code"], "LockBusy")
        self.assertFalse(os.path.exists(self.p("f.state.json")))      # 拿不到鎖不碰 state
        os.rmdir(self.p("f.lock"))
        self.assertEqual(self.tick(path).returncode, 0)
        self.assertFalse(os.path.exists(self.p("f.lock")))            # 退出前放鎖

    def test_nested_with_end(self):
        inner = self.fsm({"a": sh("ia", "echo '{\"next\": \"b\"}'"),
                          "b": sh("ib", "echo '{\"next\": \"done\", \"data\": {\"answer\": 42}}'")},
                         name="inner", end=["done"], history="inner-h")
        outer = self.fsm({"a": {"argv": [sys.executable, FSM, inner]}, "done": sh("done", "true")}, lock="f.lock",
                         brain="outer-b", history="outer-h", max_steps=9)
        r = self.tick(outer)                              # 內層 a → b：沒到終點，外層留在 a
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.state()["phase"], self.state("inner.state.json")["phase"]), ("a", "b"))
        # 內層的設定＝自己的＋外層 cfg 當預設（自己寫了的不蓋；fsm 自己的 key——state、lock、max_steps…——不繼承）
        self.assertEqual(self.cfg("ia")[0], dict(json.loads(self.read("inner.json")), brain="outer-b"))
        self.tick(outer)                                  # 內層 b 回 done（在 end 裡）→ 交給外層，子 phase 歸位
        self.assertEqual(self.state("inner.state.json")["phase"], "a")
        st = self.state()
        self.assertEqual((st["phase"], st["data"]), ("done", {"answer": 42}))
        self.tick(outer)
        self.assertEqual(self.args("done")[0]["data"], {"answer": 42})

    def test_methods_cell_forms(self):
        states = {"x": "nope/", "y": 3, "z": {"target": {"argv": ["true"]}, "next": "x"}}
        with self.assertRaises(aos_methods.MethodsError) as e:
            aos_methods.cell(states, "w")
        self.assertEqual(e.exception.code, "UnknownState")
        with self.assertRaises(aos_methods.MethodsError):
            aos_methods.cell(states, "y")
        self.assertEqual(aos_methods.cell(states, "z", "/f.json"), ({"argv": ["true"]}, "/f.json#/states/z", "x"))
        self.assertEqual(aos_methods.last_json('{"a": 1}\n{"b": 2}\n{"c"'), {"b": 2})
