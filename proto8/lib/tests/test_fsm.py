"""proto8/lib 的自動測試：fsm（aos_fsm、aos_methods）；起真的 aos_fsm 行程、走檔案。只用標準庫：

    python3 -m unittest discover -s proto8/lib/tests

共用的 `Tmp`、路徑在 helpers.py。10-15 收工後瘦身版（N-36～N-40）：fsm 不碰格的 stdin，state 窗只有 phase。
格多半用 sh：`echo run >> NAME.runs` 記下跑了幾次，再 echo 一份結果。
"""
import json
import os
import signal
import subprocess
import sys

from helpers import FSM, Tmp
import aos_methods  # noqa: E402


def sh(name, script):
    """一格：在暫存資料夾跑 sh，先在 NAME.runs 記一行，再跑 script。"""
    return {"argv": ["sh", "-c", "echo run >> %s.runs; %s" % (name, script)]}


def ok(name, out="{}"):
    return sh(name, "echo '%s'" % out)


class FsmTest(Tmp):
    def fsm(self, states, name="f", **keys):
        return self.write(name + ".json", dict({"start": "a", "states": states, "state": name + ".state.json"}, **keys))

    def tick(self, path, timeout=10, cwd=None):
        return subprocess.run([sys.executable, FSM, path], capture_output=True, text=True, cwd=cwd or self.tmp,
                              timeout=timeout)

    def state(self, name="f.state.json"):
        return json.loads(self.read(name))

    def runs(self, name):
        return len(self.read(name + ".runs").splitlines()) if os.path.exists(self.p(name + ".runs")) else 0

    def out(self, r):
        return [json.loads(x) for x in r.stdout.splitlines()]

    def test_first_tick_next_from_stdout(self):
        path = self.fsm({"a": ok("a", '{"next": "b", "data": {"x": 1}}'), "b": ok("b")})
        self.assertFalse(os.path.exists(self.p("f.state.json")))
        r = self.tick(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state(), {"phase": "b"})                   # state 窗只有 phase（N-39）
        line = self.out(r)[0]                                             # N-30 結果＋from／to＋next null（沒結束）
        self.assertEqual(set(line), {"id", "code", "signal", "timed_out", "pid", "ms", "exit_file", "from", "to", "next"})
        self.assertEqual((line["from"], line["to"], line["code"], line["next"]), ("a", "b", 0, None))
        self.tick(path)
        self.assertEqual((self.runs("a"), self.runs("b"), self.state()["phase"]), (1, 1, "b"))

    def test_fsm_does_not_touch_cell_stdin(self):
        # fsm 不餵格 stdin（N-37）；格要參數就用自己 inst 的 stdin
        self.write("in.json", {"q": 1})
        path = self.fsm({"a": dict(ok("a", '{"next": "b"}'), argv=["sh", "-c", "cat > a.in; echo '{\"next\": \"b\"}'"]),
                         "b": dict(ok("b"), argv=["sh", "-c", "cat > b.in; echo '{}'"], stdin="in.json")},
                        brain="x.json")
        self.tick(path)
        self.tick(path)
        self.assertEqual(self.read("a.in"), "")
        self.assertEqual(json.loads(self.read("b.in")), {"q": 1})

    def test_static_next_and_stdout_wins(self):
        path = self.fsm({"a": {"val": ok("a"), "next": "b"},
                         "b": {"val": ok("b", '{"next": "a"}'), "next": "b"}})
        self.tick(path)
        self.assertEqual(self.state()["phase"], "b")      # 沒吐 next＝表上靜態 next
        self.tick(path)
        self.assertEqual(self.state()["phase"], "a")      # stdout 的 next 蓋過表上的

    def test_stay_and_last_complete_json(self):
        # 最後一份是半份＝不算，看前一份；那份沒 next、表上也沒有＝留原狀態
        path = self.fsm({"a": sh("a", "echo '{\"data\": 7}'; printf '{\"next\": \"b\"'"), "b": ok("b")})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "a"), r.stderr)

    def test_no_result_is_error(self):
        path = self.fsm({"a": sh("a", "true")})
        r = self.tick(path)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.out(r)[-1]["error"]["code"], "ResultMissing")
        self.assertEqual(self.state()["phase"], "a")

    def test_end_line_marked(self):
        # 結束那拍那行多 "end": true（拍它的 loop 寫了 stop_on_end 就看這個停）；沒結束的拍沒有
        path = self.fsm({"a": ok("a", '{"next": "b"}'), "b": ok("b", '{"next": "out", "r": 1}')}, end=["out"])
        r = self.tick(path)
        self.assertNotIn("end", self.out(r)[0])
        r = self.tick(path)
        self.assertEqual((self.out(r)[0]["end"], self.out(r)[-1]), (True, {"next": "out", "r": 1}))

    def test_empty_stdout_follows_static_next(self):
        # 格沒輸出（只有空白也算）、表上有 next＝照表上走，不算錯（10-15 使用者，N-38）
        path = self.fsm({"a": {"val": sh("a", "echo"), "next": "b"}, "b": {"val": sh("b", "true"), "next": "a"}})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "b"), r.stdout)
        self.assertEqual(len(self.out(r)), 1)
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "a"), r.stdout)

    def test_empty_stdout_end_gives_nothing(self):
        # 沒輸出的格在 end 裡＝結束、phase 歸位，只吐那一行（沒有結果可交）
        path = self.fsm({"a": {"val": sh("a", "true"), "next": "b"}, "b": sh("b", "true")}, end=["b"])
        self.tick(path)
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (1, "b"))       # b 沒輸出也沒 next＝錯
        self.write("f.json", {"start": "a", "states": {"a": {"val": sh("a", "true"), "next": "out"}},
                              "end": ["out"], "state": "g.state.json"})
        r = self.tick(self.p("f.json"))
        self.assertEqual((r.returncode, len(self.out(r)), self.state("g.state.json")["phase"]), (0, 1, "a"))

    def test_non_json_output_with_static_next_is_error(self):
        # 吐了東西但不是完整 JSON＝錯，表上有 next 也一樣
        path = self.fsm({"a": {"val": sh("a", "echo hello; printf '{\"next\": \"b\"'"), "next": "b"}, "b": ok("b")})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.out(r)[-1]["error"]["code"], self.state()["phase"]), (1, "ResultMissing", "a"))

    def test_cell_names_from_config_folder(self):
        # 格的相對路徑從 fsm 設定檔所在的資料夾算（N-36），不是 cwd
        os.makedirs(self.p("sub"))
        self.write("sub/cells.json", {"one": ok("a", '{"next": "b"}')})
        path = self.write("sub/f.json", {"start": "a", "states": {"a": "cells.json#/one", "b": ok("b")},
                                         "state": "f.state.json"})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "b"), r.stderr)   # state 窗照 cwd 算

    def test_next_not_in_table_is_error(self):
        path = self.fsm({"a": ok("a", '{"next": "zzz"}')})
        r = self.tick(path)
        self.assertEqual(r.returncode, 1)                 # 格出錯：fsm 退非 0（N-43）
        self.assertEqual(self.state()["phase"], "a")
        self.assertEqual(self.out(r)[-1]["error"]["code"], "NextUnknown")          # N-29 形狀

    def test_cell_failure_stays_and_reports(self):
        # 格出錯＝phase 不動、往外報（只說結束碼；格的 stderr fsm 不讀、不轉，C-52 切乾淨）；error 不是特別的格
        path = self.fsm({"a": ok("a", '{"next": "b"}'),
                         "b": dict(sh("b", "echo '{\"error\": {\"code\": \"Boom\", \"msg\": \"壞了\"}}' >&2; exit 3"),
                                   stderr="b.err.json"),
                         "error": ok("error")})
        self.tick(path)
        for _ in range(2):
            r = self.tick(path)
            self.assertEqual(r.returncode, 1)
            err = self.out(r)[-1]["error"]
            self.assertEqual((err["code"], err["msg"]), ("CellFailed", "格 b 結束碼 3"))
            self.assertEqual(self.out(r)[-1]["code"], 3)
            self.assertEqual(self.state()["phase"], "b")
            self.assertEqual(r.stderr, "")                                         # 格的錯沒轉上來
        self.assertEqual(json.loads(self.read("b.err.json"))["error"]["code"], "Boom")   # 格自己寫的 stderr 檔才有
        self.assertEqual((self.runs("b"), self.runs("error")), (2, 0))
        path = self.fsm({"a": sh("a", "exit 4")}, name="g")
        self.assertEqual(self.out(self.tick(path))[-1]["error"]["msg"], "格 a 結束碼 4")

    def test_end_in_table_runs_then_ends(self):
        # (b) next 在表裡也在 end：進入、下一拍跑完那格，然後結束（結果交出去、phase 歸位 start）
        path = self.fsm({"a": ok("a", '{"next": "d"}'), "d": ok("d", '{"next": "out", "data": 42}')}, end=["d"])
        r = self.tick(path)
        self.assertEqual((len(self.out(r)), self.state()["phase"]), (1, "d"))
        r = self.tick(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.out(r)[-1], {"next": "out", "data": 42})
        self.assertEqual((self.out(r)[0]["from"], self.out(r)[0]["to"]), ("d", "a"))
        self.assertEqual((self.runs("d"), self.state()["phase"]), (1, "a"))

    def test_end_not_in_table_ends_now(self):
        # (c) next 不在表裡、在 end：直接結束，結果＝剛跑完那格的
        path = self.fsm({"a": ok("a", '{"next": "b"}'), "b": ok("b", '{"next": "idle", "data": 1}')}, end=["idle"])
        self.tick(path)
        r = self.tick(path)
        self.assertEqual((r.returncode, self.out(r)[-1]), (0, {"next": "idle", "data": 1}))
        self.assertEqual(self.state()["phase"], "a")

    def test_nested(self):
        # 外層不必知道那格是個 fsm（C-52）：表上照樣可以寫靜態 next——內層沒結束時吐 next null＝留原格，結束才交出結果
        inner = self.fsm({"a": ok("ia", '{"next": "b"}'), "b": ok("ib", '{"next": "done", "data": 42}')},
                         name="inner", end=["done"])
        outer = self.fsm({"a": {"val": {"argv": [sys.executable, FSM, inner]}, "next": "done"}, "done": ok("done")})
        r = self.tick(outer)                              # 內層 a → b：沒結束，外層留在 a（表上的 next 不會帶走）
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.state()["phase"], self.state("inner.state.json")["phase"]), ("a", "b"))
        self.tick(outer)                                  # 內層 b 回 done（表外、在 end）→ 結束、交給外層
        self.assertEqual((self.state("inner.state.json")["phase"], self.state()["phase"]), ("a", "done"))

    def test_next_null_stays(self):
        # 格回 {"next": null}＝「我還沒完」，留原狀態，表上有靜態 next 也不走（N-37）
        path = self.fsm({"a": {"val": ok("a", '{"next": null, "data": 1}'), "next": "b"}, "b": ok("b")})
        r = self.tick(path)
        self.assertEqual((r.returncode, self.state()["phase"]), (0, "a"), r.stdout)

    def test_killed_midway_reruns_same_cell(self):
        path = self.fsm({"a": ok("a", '{"next": "b"}'), "b": sh("b", "[ -f again ] || sleep 30; echo '{}'")})
        self.tick(path)
        p = subprocess.Popen([sys.executable, FSM, path], cwd=self.tmp, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.until(lambda: self.runs("b") == 1)
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        self.assertEqual(self.state(), {"phase": "b"})
        self.write("again", "")
        r = self.tick(path)                               # phase 沒變＝重跑同一格
        self.assertEqual((r.returncode, self.runs("b")), (0, 2), r.stderr)

    def test_missing_state_refused(self):
        path = self.write("f.json", {"start": "a", "states": {"a": ok("a")}, "state": None})
        r = self.tick(path)
        self.assertEqual(r.returncode, 1)                       # fsm 自己的錯也是 1（原 125，10-15 晚）
        self.assertEqual(json.loads(r.stderr.splitlines()[-1])["error"]["code"], "WindowMissing")
        self.assertEqual(self.runs("a"), 0)

    def test_old_keys_ignored(self):
        # ctl、lock、max_steps、max_fails 已不歸 fsm（N-39）：當不認得的 key 忽略
        os.mkdir(self.p("f.lock"))
        self.write("f.ctl.json", {"paused": True})
        path = self.fsm({"a": ok("a", '{"next": "b"}'), "b": ok("b")}, lock="f.lock", ctl="f.ctl.json",
                        max_steps=1, max_fails=1)
        for _ in range(3):
            self.assertEqual(self.tick(path).returncode, 0)
        self.assertEqual((self.runs("a"), self.runs("b")), (1, 2))

    def test_methods_cell_forms(self):
        states = {"x": "nope/", "y": 3, "z": {"val": {"argv": ["true"]}, "next": "x"}}
        with self.assertRaises(aos_methods.MethodsError) as e:
            aos_methods.cell(states, "w")
        self.assertEqual(e.exception.code, "StateUnknown")
        with self.assertRaises(aos_methods.MethodsError):
            aos_methods.cell(states, "y")
        self.assertEqual(aos_methods.cell(states, "z", "/f.json"), ({"argv": ["true"]}, "/f.json#/states/z", "x"))
        self.write("sub/c.json", {"argv": ["true"]})
        self.assertEqual(aos_methods.cell({"c": "c.json"}, "c", None, self.p("sub"))[0], {"argv": ["true"]})
        self.assertEqual(aos_methods.last_json('{"a": 1}\n{"b": 2}\n{"c"'), {"b": 2})
