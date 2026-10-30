#!/usr/bin/env python3
"""test_cli.py：aos-daemon 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-daemon

從 proto8/tests/test_daemon.py（bin 版）逐案移植（10-21 傍晚重新照抄一次：命令列 `aos-daemon [旗標] 設定檔`、exec 陣列、
子 loop 經 aos-exec 起、收工時剛死的子項標 done）：daemon.json＝loop.json 的超集、loops 表、ctl 增減、不自動重起、
收工收子項、接回（N-28、N-54、P-36）。10-29 拆窗（medium-plan § 四）：名單的手把在 loops_ctl.json、子項表在 loops_state.json，
ctl.json／state.json 只管 loop 面向（H 段）；信箱模式 loops_mailbox（I 段，實作步驟 5）。差別只有：PATH 放 impls 的 aos-exec、aos-loop 兩支的 bin/（子 loop 經 aos-exec
exec 成 PATH 上的 aos-loop，10-21 傍晚起同 bin 版）、usage 一行多了代號（「aos-daemon: ArgumentsBad usage: …」）、
自己的錯多驗代號（E 段）。
"""
import ctypes, datetime, json, os, re, struct, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path

DAEMON = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "bin",
                                                                             "aos-daemon"))
IMPLS = Path(__file__).resolve().parent.parent.parent
LONG = 'echo x >> "$AOS_STACK/starts"; while :; do sleep 0.05; done'


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = os.pathsep.join([str(IMPLS / "aos-exec" / "bin"), str(IMPLS / "aos-loop" / "bin"), e.get("PATH", "")])
    e.update(extra or {})
    return e


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:   # 殭屍不算活著
        return Path("/proc/%d/stat" % pid).read_text().rpartition(")")[2].split()[0] != "Z"
    except OSError:
        return False


def rows_of(stack, st, key="loops"):
    """loops_state 的 loops 欄（key＝"execs"：exec 型子項那張表，10-30）解開：物件照原樣；
    切檔（{"$ref": ["loops_state_loops/<雜湊>.json", …]}）照順序讀回來合起來（10-23）。"""
    v = st.get(key, {})
    if "$ref" not in v:
        return v
    out = {}
    for ref in v["$ref"]:
        out.update(json.loads((Path(stack) / ref).read_text()))
    return out


DIRECTIVE = IMPLS / "aos-directive" / "bin" / "aos-directive"


def directive(doc, cwd):
    """用 aos-directive 解一份 JSON（讀 loops_state 的人就這樣拿回完整的 loops）。"""
    r = subprocess.run([str(DIRECTIVE)], input=json.dumps(doc), cwd=str(cwd), capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def until(f, secs=15):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        try:
            v = f()
            if v:
                return v
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.05)
    return None


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.s = self.t / "stack"
        self.s.mkdir()
        lg = self.t / "long"   # 長壽的子項：字串目標 "long"（子 loop 的 cwd＝daemon 的 cwd＝self.t）
        lg.mkdir()
        (lg / "_entry").write_text("#!/bin/sh\n" + LONG + "\n")
        (lg / "_entry").chmod(0o755)
        self.procs = []
        self.addCleanup(self._t.cleanup)
        self.addCleanup(self.reap)

    def reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()
        st = self.s / "loops_state.json"
        if st.is_file():   # 測試失敗時別留孤兒（子項叫 loops_state.json 時它是小格）
            try:
                doc = json.loads(st.read_text())
                rows = list(rows_of(self.s, doc).values()) + list(rows_of(self.s, doc, "execs").values())
            except (OSError, ValueError, AttributeError):
                rows = []
            for r in rows:
                if r.get("pid") and alive(r["pid"]):
                    try:
                        os.killpg(r["pid"], signal.SIGKILL)
                    except OSError:
                        pass

    def cfg(self, doc):
        (self.t / "daemon.json").write_text(json.dumps(doc))

    def run_d(self, doc, timeout=30, env=None, argv=("daemon.json",)):
        if doc is not None:
            self.cfg(doc)
        return subprocess.run([DAEMON, *argv], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)} if env is None else env),
                              capture_output=True, text=True, timeout=timeout)

    def start(self, doc=None):
        if doc is not None:
            self.cfg(doc)
        p = subprocess.Popen([DAEMON, "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def state(self):
        return json.loads((self.s / "state.json").read_text())

    def lstate(self):
        return json.loads((self.s / "loops_state.json").read_text())

    def kids(self):
        return rows_of(self.s, self.lstate())

    def ctl(self, doc, name="ctl.json"):
        tmp = self.s / ("." + name)
        tmp.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
        os.replace(tmp, self.s / name)

    def lctl(self, doc):
        self.ctl(doc, "loops_ctl.json")

    def long(self, mx=1):
        return {"exec": "long", "max": mx}

    def test_loop_json_runs_as_is(self):
        # 合法的 loop.json 直接丟給 daemon 也能跑（N-28）
        r = self.run_d({"exec": "daemon.json#/body", "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/laps"']},
                        "max": 3, "interval_ms": 0})
        self.assertEqual((r.returncode, r.stderr, len((self.s / "laps").read_text().split())), (0, "", 3))

    def test_needs_stack(self):
        r = self.run_d({"max": 1}, env={})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-daemon: ") and "AOS_STACK" in r.stderr, r.stderr)

    def test_bad_loops_is_own_error(self):
        for bad in ([1], {"a/b": "x"}, {"a": 3}, {"a#b": "x"}, {".a": "x"}):
            r = self.run_d({"loops": bad, "max": 1})
            self.assertEqual(r.returncode, 1, bad)
            self.assertTrue(r.stderr.startswith("aos-daemon: "), r.stderr)

    def test_loops_up_in_cells_then_stop(self):
        sub = self.t / "sub"
        sub.mkdir()
        (sub / "_entry").write_text("#!/bin/sh\n" + LONG + "\n")
        (sub / "_entry").chmod(0o755)
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": "sub", "b": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and (self.s / "b" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual({n: r["phase"] for n, r in k.items()}, {"a": "running", "b": "running"})
        a = json.loads((self.s / "a" / "loop.json").read_text())
        # 10-21 傍晚：相對的 exec 照 daemon 的 cwd 轉成絕對、蓋上 _entry，子 loop 經 aos-exec 起
        self.assertEqual(a, {"exec": os.path.join(os.path.realpath(self.t), "sub"), "ctl": "ctl.json", "state": "state.json",
                             "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
        self.assertTrue(until(lambda: json.loads((self.s / "b" / "state.json").read_text())["phase"] == "running"))
        pids = [r["pid"] for r in k.values()]
        self.ctl({"stopped": True, "seq": 1})
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["ctl_seq"]), (0, "", "stopped", 1))
        self.assertNotIn("loops", st)   # 10-29 拆窗：子項表在 loops_state.json
        ls = self.lstate()
        self.assertEqual({r["phase"] for r in ls["loops"].values()}, {"stopped"})   # daemon 收掉的＝stopped（10-23 命名統合）
        self.assertEqual(list(ls["loops"]["a"]), ["pid", "started_at_ticks", "phase", "code", "signal"])
        self.assertEqual(list(ls), ["kind", "ctl_seq", "ctl_warning", "loops", "execs", "pid", "started_at_ticks", "boot_id",
                                    "recorded_at"])   # execs＝exec 型子項那張表（10-30；沒有就是 {}）
        self.assertEqual(ls["execs"], {})
        self.assertEqual([ls[k] for k in ("kind", "ctl_seq", "ctl_warning", "pid", "started_at_ticks", "boot_id")],
                         ["state", None, None] + [st[k] for k in ("pid", "started_at_ticks", "boot_id")])   # 心跳同一個行程的值
        self.assertEqual([alive(x) for x in pids], [False, False])

    def test_done_child_not_restarted(self):
        p = self.start({"state": "state.json", "max": 15, "interval_ms": 100,
                        "loops": {"once": {"exec": "daemon.json#/loops/once/body", "max": 1,   # D4：內嵌單子
                                              "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"']}}}})
        out, err = p.communicate(timeout=30)
        k = self.kids()
        self.assertEqual((p.returncode, err, k["once"]["phase"], k["once"]["code"]), (0, "", "done", 0))   # 子 loop 自己結束＝done
        self.assertEqual(len((self.s / "once" / "starts").read_text().split()), 1)

    def test_failing_child_stderr_in_cell(self):
        p = self.start({"state": "state.json", "max": 10, "interval_ms": 100,
                        "loops": {"bad": {"exec": "daemon.json#/loops/bad/body",
                                             "body": {"argv": ["sh", "-c", "exit 3"]}},
                                     "obj": {"exec": {"argv": "true"}}}})   # 10-24 起物件＝內嵌單子；形狀壞＝子 loop 自己的錯（10-21～10-23 物件本身就是錯）
        out, err = p.communicate(timeout=30)
        k = self.kids()
        self.assertEqual((p.returncode, err, k["bad"]["phase"], k["bad"]["code"], k["obj"]["phase"], k["obj"]["code"]),
                         (0, "", "done", 3, "done", 1))
        self.assertIn("aos-loop: ", (self.s / "bad" / "stderr.txt").read_text())
        self.assertIn("aos-loop: EntryBad 單子跑不起來：", (self.s / "obj" / "stderr.txt").read_text())

    def test_ctl_loops_add_and_remove(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        a_pid = k["a"]["pid"]
        self.lctl({"loops": {"b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and "a" not in self.kids() and self.kids())
        self.assertEqual(list(k), ["b"])
        self.assertFalse(alive(a_pid))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_sigterm_collects_loops_nonzero(self):
        p = self.start({"state": "state.json", "loops": {"a": self.long(), "b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and len(self.kids()) == 2 and self.kids())
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["code"]), (143, "", "stopped", 143))
        self.assertEqual([alive(r["pid"]) for r in k.values()], [False, False])
        self.assertEqual({r["phase"] for r in self.kids().values()}, {"stopped"})

    # ---- 10-21 計畫第 2 段：命令列（D1，共用 aos_loop.cli）、字串子項（D2）、收工時剛死的子項（D7）

    def test_flags_override_cfg(self):
        # --max／--interval-ms 蓋過 daemon.json（旗標 ＞ 設定檔）；state 回報實際生效的值
        r = self.run_d({"exec": "daemon.json#/body", "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/laps"']},
                        "max": 100, "interval_ms": 5000, "state": "state.json"},
                       argv=("--max", "3", "--interval-ms", "0", "daemon.json"))
        st = self.state()
        self.assertEqual((r.returncode, r.stderr, len((self.s / "laps").read_text().split())), (0, "", 3))
        self.assertEqual((st["max"], st["interval_ms"], st["phase"]), (3, 0, "done"))

    def test_val_array_and_cfg_rules(self):
        # 10-21 傍晚：唯一的位置參數＝設定檔；exec 可以是 [目標, 參數...]，參數每次接上；設定檔可寫 檔#/指標
        job = self.t / "job"
        job.mkdir()
        (job / "_entry").write_text('#!/bin/sh\necho "$@" >> "$AOS_STACK/laps"\n')
        (job / "_entry").chmod(0o755)
        self.cfg({"exec": ["job", "a", "b"], "interval_ms": 0, "max": 2, "sub": {"exec": ["job", "c"], "max": 1}})
        for argv, want in ((("daemon.json",), "a b\na b\n"), (("daemon.json#/sub",), "c\n")):
            (self.s / "laps").unlink(missing_ok=True)
            r = self.run_d(None, argv=argv)
            self.assertEqual((r.returncode, r.stderr, (self.s / "laps").read_text()), (0, "", want), argv)
        for argv, code in (((), "ArgumentsBad"), (("daemon.json", "job"), "ArgumentsBad"), (("--cfg", "daemon.json"), "FlagUnknown")):
            r = self.run_d(None, argv=argv)
            self.assertEqual((r.returncode, r.stderr.startswith("aos-daemon: %s usage: " % code)), (1, True), (argv, r.stderr))

    def test_child_launched_through_aos_exec(self):
        # 使用者 10-21 傍晚「5.要」：子 loop 經 aos-exec 起（aos-exec 設好 AOS_CF／AOS_CD 再 exec 成 aos-loop，pid 不變）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": ["long"]}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        env = dict(x.split("=", 1) for x in Path("/proc/%d/environ" % k["a"]["pid"]).read_text().split("\0") if "=" in x)
        cell = os.path.realpath(self.s / "a")
        self.assertEqual((env.get("AOS_CF"), env.get("AOS_CD"), env.get("AOS_CO")),
                         (os.path.join(cell, "loop.json"), cell, "/_entry"))
        self.assertEqual(json.loads((self.s / "a" / "loop.json").read_text())["exec"],
                         [os.path.join(os.path.realpath(self.t), "long")])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_string_child_is_exec_target(self):
        # 字串子項＝aos-exec 的目標（不限資料夾，這裡指進 daemon.json），包成 {"exec": 它}
        p = self.start({"state": "state.json", "max": 10, "interval_ms": 100,
                        "loops": {"s": "daemon.json#/kids/s"},
                        "kids": {"s": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        k = self.kids()
        self.assertEqual((p.returncode, err, k["s"]["phase"], k["s"]["code"]), (0, "", "done", 0))
        self.assertEqual(json.loads((self.s / "s" / "loop.json").read_text()),
                         {"exec": os.path.join(os.path.realpath(self.t), "daemon.json#/kids/s"), "ctl": "ctl.json",
                          "state": "state.json", "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
        self.assertEqual(len((self.s / "s" / "starts").read_text().split()), 1)

    def test_child_dead_at_finish_marked_done(self):
        # D7：最後一次的 tend 之後才自己結束的子項，收工後的最後一份 state 也要是 done、記 code（不留 running）
        p = self.start({"state": "state.json", "exec": "daemon.json#/body",
                        "body": {"argv": ["sh", "-c", "sleep 2; exit 10"]},
                        "loops": {"q": "daemon.json#/kids/q"},
                        "kids": {"q": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        q = self.kids()["q"]
        self.assertEqual((p.returncode, err, len((self.s / "q" / "starts").read_text().split())), (0, "", 1))
        self.assertEqual((q["phase"], q["code"], q["signal"]), ("done", 0, None))

    def test_adopt_after_crash(self):
        doc = {"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        pid = k["a"]["pid"]
        p.kill()
        p.wait()
        self.assertTrue(alive(pid))
        p2 = self.start()
        time.sleep(1)
        self.assertEqual((self.kids()["a"]["pid"], len((self.s / "a" / "starts").read_text().split())), (pid, 1))
        self.ctl({"stopped": True})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(pid)), (0, False))

    def test_adopt_false_starts_fresh(self):
        doc = {"state": "state.json", "loops": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        try:
            p2 = self.start(dict(doc, adopt=False))
            k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
            self.assertTrue(k2)
            self.assertTrue(until(lambda: len((self.s / "a" / "starts").read_text().split()) == 2))
            p2.send_signal(signal.SIGTERM)
            p2.communicate(timeout=30)
        finally:
            os.killpg(old, signal.SIGKILL)


    def test_restart_starts_loops_died_while_down(self):
        # 使用者 10-22「daemon 重開時照表起，算重新開始、不算自動重起」：停機期間死掉的子項，重開時照名單起
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        os.killpg(old, signal.SIGKILL)
        self.assertTrue(until(lambda: not alive(old)))
        p2 = self.start()
        k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
        self.assertTrue(k2)
        self.assertTrue(until(lambda: len((self.s / "a" / "starts").read_text().split()) == 2))
        self.ctl({"stopped": True})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(k2["a"]["pid"])), (0, False))

    def test_child_name_clashes_with_own_windows(self):
        # 使用者 10-22「子項名字擋掉跟 ctl／state 同名」：小格 $AOS_STACK/<名字>/ 會跟 daemon 自己的 ctl、state 撞的名字，
        # 起來時退 1（代號 CfgBad）
        absst = str(self.s / "st.json")
        for win, name in (({"state": "state.json"}, "state.json"), ({"ctl": "ctl.json"}, "ctl.json"),
                          ({"ctl": "w/c.json"}, "w"), ({"state": "./x/../s.json"}, "s.json"), ({"state": absst}, "st.json")):
            r = self.run_d(dict(win, loops={name: self.long()}, max=1))
            self.assertEqual(r.returncode, 1, (win, name))
            self.assertTrue(r.stderr.startswith("aos-daemon: CfgBad ") and "撞名" in r.stderr
                            and r.stderr.count("\n") == 1, r.stderr)
            self.assertFalse((self.s / name).exists(), name)
        # 旗標給的 --state 也算
        r = self.run_d({"loops": {"s2.json": self.long()}, "max": 1}, argv=("--state", "s2.json", "daemon.json"))
        self.assertTrue(r.returncode == 1 and r.stderr.startswith("aos-daemon: CfgBad "), r.stderr)
        # 不撞的照起：沒開 state 時 "state.json" 只是普通名字；ctl 在 stack 外面也不算
        for win, name in (({}, "state.json"), ({"ctl": str(self.t / "ctl.json")}, "ctl.json")):
            r = self.run_d(dict(win, loops={name: {"exec": "daemon.json#/b", "max": 1}},
                                b={"argv": ["true"]}, max=3, interval_ms=100))
            self.assertEqual((r.returncode, r.stderr, (self.s / name / "loop.json").exists()), (0, "", True), (win, name))

    def test_ctl_loops_clash_not_adopted(self):
        # loops_ctl 改 loops 撞名＝那份 loops_ctl 整份不採用、維持上一份好的，原因進 loops_state 的 ctl_warning（N-08）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        for name in ("state.json", "loops_state.json"):
            self.lctl({"loops": {name: self.long()}, "seq": 5})
            ls = until(lambda: "撞名" in (self.lstate()["ctl_warning"] or "") and name in self.lstate()["ctl_warning"]
                       and self.lstate())
            self.assertTrue(ls, name)
            self.assertEqual((list(ls["loops"]), ls["loops"]["a"]["pid"], alive(k["a"]["pid"]), ls["ctl_seq"]),
                             (["a"], k["a"]["pid"], True, None), name)
        self.assertTrue((self.s / "state.json").is_file() and (self.s / "loops_state.json").is_file())
        self.assertIsNone(self.state()["ctl_warning"])   # 壞的是 loops_ctl：state.json 不提
        self.lctl({"seq": 6})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 6 and self.lstate()["ctl_warning"] is None))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.state()["ctl_warning"]), (0, "", None))


    # ───── E. impls 才有的：錯誤代號、子 loop 的心跳是自己的 pid ─────

    def test_error_codes(self):
        r = self.run_d({"max": 1}, env={})
        self.assertTrue(r.stderr.startswith("aos-daemon: StackMissing "), r.stderr)
        for doc in ({"loops": [1], "max": 1}, {"loops": {"a/b": "x"}, "max": 1}, {"loops": {"a#b": "x"}, "max": 1}, {"adopt": 1, "max": 1},
                    {"max": None}, {"exec": 3}):   # 10-24 起 {"exec": {"argv": [...]}} 不算壞（內嵌單子，見 test_inline_*）
            r = self.run_d(doc)
            self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "CfgBad"), (doc, r.stderr))

    def test_child_state_has_own_pid(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        st = until(lambda: json.loads((self.s / "a" / "state.json").read_text()))
        self.assertEqual((st["pid"], st["kind"]), (k["a"]["pid"], "state"))
        self.lctl({"loops": {"a": self.long(), "b": self.long()}})   # 後來才起的也是自己的 pid
        kb = until(lambda: (self.s / "b" / "starts").exists() and "b" in self.kids() and self.kids())
        sb = until(lambda: json.loads((self.s / "b" / "state.json").read_text()))
        self.assertEqual(sb["pid"], kb["b"]["pid"])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    # ---- 10-23 壓測後（使用者「都修都處理」）

    def watch(self, secs):
        """secs 秒內每 10 毫秒讀一次 state，回看到的每一份（recorded_at 不同才算一份）。"""
        seen, end = [], time.monotonic() + secs
        while time.monotonic() < end:
            try:
                st = self.state()
                if not seen or st["recorded_at"] != seen[-1]["recorded_at"]:
                    seen.append(st)
            except (OSError, ValueError):
                pass
            time.sleep(0.01)
        return seen

    @staticmethod
    def gaps(seen):
        ts = [datetime.datetime.fromisoformat(s["recorded_at"]).timestamp() for s in seen]
        return [b - a for a, b in zip(ts, ts[1:])]

    def test_stubborn_child_does_not_block(self):
        # 第 1 點：不肯退的子 loop（那次不理 SIGTERM）不會卡住 daemon——送了 SIGTERM 照常巡（state 照寫、ctl 照讀、別的子項照起），
        # 收的途中那列是 stopping，滿 10 秒才 SIGKILL 整群。第 2 點：被 SIGKILL 的子 loop 自己的 state 停在 running（只有它自己寫，
        # N-09），看死活照 pid＋started_at_ticks（N-17）；daemon 自己的 state 那列寫 stopped、signal 9
        stub = self.t / "stub"
        stub.mkdir()
        (stub / "_entry").write_text('#!/bin/sh\ntrap "" TERM\necho x >> "$AOS_STACK/starts"\nwhile :; do sleep 0.05; done\n')
        (stub / "_entry").chmod(0o755)
        s1, s2 = {"exec": "stub", "max": 1}, {"exec": "stub", "max": 1}
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 100,
                        "loops": {"s1": s1, "s2": s2, "a": self.long()}})
        k = until(lambda: all((self.s / n / "starts").exists() for n in ("s1", "s2", "a")) and self.kids())
        self.assertTrue(k)
        self.assertTrue(until(lambda: json.loads((self.s / "s2" / "state.json").read_text())["phase"] == "running"))
        t0 = time.monotonic()
        self.lctl({"loops": {"s2": s2, "a": self.long()}})
        seen = self.watch(1.0)
        self.assertEqual(self.kids()["s1"]["phase"], "stopping")
        self.assertTrue(alive(k["s1"]["pid"]))
        self.lctl({"loops": {"s2": s2, "a": self.long(), "b": self.long()}})   # 收 s1 的途中照樣起別的
        kb = until(lambda: (self.s / "b" / "starts").exists() and self.kids()["b"]["phase"] == "running" and self.kids(), 3)
        self.assertTrue(kb)
        self.assertLess(time.monotonic() - t0, 5)
        seen += self.watch(0.5)
        self.assertLess(max(self.gaps(seen)), 0.5, "收子項的途中 state 照寫")
        p.send_signal(signal.SIGTERM)   # 收工：s2 也不肯退，等它的時候 state 照樣每秒寫（phase stopping）
        fin = self.watch(3)
        self.assertEqual(fin[-1]["phase"], "stopping")
        self.assertLess(max(self.gaps(fin)), 1.5)
        out, err = p.communicate(timeout=30)
        took = time.monotonic() - t0
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"]), (143, "", "stopped"))
        self.assertGreater(took, 9)
        rows = self.kids()
        self.assertEqual(sorted(rows), ["a", "b", "s2"])   # s1 是 loops_ctl 要拿掉的，收完照樣拿掉
        r2 = rows["s2"]
        self.assertEqual((r2["phase"], r2["code"], r2["signal"]), ("stopped", 137, 9))
        self.assertEqual({rows[n]["phase"] for n in ("a", "b")}, {"stopped"})
        for n in ("s1", "s2"):
            cs = json.loads((self.s / n / "state.json").read_text())
            self.assertEqual(cs["phase"], "running", n)   # 來不及寫最後一份
            self.assertFalse(alive(cs["pid"]), n)          # 讀的人看 pid（＋started_at_ticks）判斷：已經不在了

    def test_one_state_per_cycle(self):
        # 第 3、4 點：沒有 exec 的 daemon 一輪只 tend 一次、只寫一份 state（不寫 running），recorded_at 的間隔穩定在 interval_ms 上下
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 300, "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "a" / "starts").exists()))
        # 數 state.json 被改名蓋過幾次（inotify IN_MOVED_TO）；只靠輪詢讀會漏掉連著的兩份。也聽 IN_CREATE（每份先建 .state.json），
        # 不然連著的 IN_MOVED_TO 會被 kernel 併成一個
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK)
        self.assertGreaterEqual(libc.inotify_add_watch(fd, str(self.s).encode(), 0x180), 0)
        seen = self.watch(3.0)
        writes, buf = 0, b""
        while True:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                break
        os.close(fd)
        while buf:
            _, mask, _, n = struct.unpack_from("iIII", buf)
            writes += bool(mask & 0x80) and buf[16:16 + n].rstrip(b"\0") == b"state.json"
            buf = buf[16 + n:]
        self.assertTrue(3.0 / 0.3 - 3 <= writes <= 3.0 / 0.3 + 2, writes)   # 一輪只寫一份（原本一輪兩份，約 20）
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertGreater(len(seen), 5)
        self.assertEqual({s["phase"] for s in seen}, {"waiting"})
        self.assertEqual(len({s["counter_runs"] for s in seen}), len(seen), "一次只寫一份")
        g = self.gaps(seen)
        self.assertTrue(all(0.25 < x < 0.5 for x in g), g)

    def test_state_written_before_spawning(self):
        # 第 5 點：起子項之前就先寫一份 state（起一大批要好一陣子）。小格的 stderr.txt 先放一個 FIFO，daemon 開它時會卡住，
        # 卡住的這段 state.json 已經在了
        cell = self.s / "x"
        cell.mkdir()
        os.mkfifo(cell / "stderr.txt")
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"x": self.long()}})
        st = until(lambda: self.state(), 5)
        self.assertTrue(st, "起子項之前沒寫 state")
        self.assertEqual((st["phase"], st["counter_runs"], self.lstate()["loops"]), ("waiting", 0, {}))
        fd = os.open(cell / "stderr.txt", os.O_RDONLY | os.O_NONBLOCK)
        try:
            self.assertTrue(until(lambda: (cell / "starts").exists() and self.kids()["x"]["phase"] == "running"))
            self.ctl({"stopped": True})
            p.communicate(timeout=30)
        finally:
            os.close(fd)
        self.assertEqual(p.returncode, 0)

    def test_stack_missing_not_created(self):
        # 第 6 點：$AOS_STACK 不在＝daemon 不自己建（建 stack 只在 aos-exec 做，N-59 第 1 件）：開了 state 窗＝WriteFailed、
        # 沒開＝起第一個子項時建不了小格＝MkdirFailed；兩種都退 1、stderr 一行、什麼都沒起。
        # 10-29 拆窗：loops_state 沒寫＝開著（loops_state.json），也是一扇 state 窗；兩扇都關才輪到 MkdirFailed
        gone = self.t / "no" / "stack"
        for doc, code in (({"state": "state.json", "loops": {"a": self.long()}}, "WriteFailed"),
                          ({"loops": {"a": self.long()}}, "WriteFailed"),
                          ({"loops": {"a": self.long()}, "loops_state": None}, "MkdirFailed")):
            r = self.run_d(dict(doc, max=1), env={"AOS_STACK": str(gone) + "/"})
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n"), gone.exists()), (1, code, 1, False),
                             r.stderr)

    # ───── G. 10-23 晚：指示詞（daemon.json、ctl）、ctl 的 loops_added／loops_removed、state 的 loops 切檔 ─────

    def quick(self):
        return {"exec": "daemon.json#/b", "max": 1}

    def test_loops_ref_split(self):
        # loops 拆成好幾份檔＝{"$ref": [檔, …]}（10-23 使用者：$ref 陣列，合物件、同名後面的蓋前面的），每個子項也能是 $ref；
        # 相對 $ref 從寫著它的那份檔的資料夾算（拆出去的每一份各從自己的資料夾）。
        # 子項的 loop key（exec、max…）由 daemon 先解好再寫進小格；其他 key（body）原樣交出去（daemon 不讀它）
        sub = self.t / "sub"
        sub.mkdir()
        (self.t / "loops-1.json").write_text(json.dumps({"a": self.quick()}))
        (sub / "loops-2.json").write_text(json.dumps({"b": {"$ref": "b.json"}, "c": ["daemon.json#/b"], "a": self.quick()}))
        (sub / "b.json").write_text(json.dumps({"exec": "daemon.json#/b", "max": {"$ref": "m.json#/n"},
                                                "body": {"stdout": {"$env": "NOPE_XYZ"}}}))
        (sub / "m.json").write_text(json.dumps({"n": 1}))
        r = self.run_d({"state": "state.json", "max": 3, "interval_ms": 100, "b": {"argv": ["true"]},
                        "loops": {"$ref": ["loops-1.json", "sub/loops-2.json"]}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(list(self.kids()), ["a", "b", "c"])   # 兩份都有 a：後面的蓋前面的、位置留在第一次
        self.assertEqual({n: k["phase"] for n, k in self.kids().items()}, {"a": "done", "b": "done", "c": "stopped"})   # c 是目標（沒 max＝不限），收工時收掉
        b = json.loads((self.s / "b" / "loop.json").read_text())
        self.assertEqual((b["max"], b["body"]), (1, {"stdout": {"$env": "NOPE_XYZ"}}))
        # loops 整個是一個 $ref；adopt 也解（解成 1＝不是布林）
        (self.t / "all.json").write_text(json.dumps({"d": self.quick()}))
        r = self.run_d({"max": 3, "interval_ms": 100, "state": "state.json", "b": {"argv": ["true"]},
                        "loops": {"$ref": "all.json"}, "adopt": {"$ref": "sub/m.json#/n"}})
        self.assertTrue(r.returncode == 1 and r.stderr.startswith("aos-daemon: CfgBad ") and "adopt" in r.stderr, r.stderr)
        r = self.run_d({"max": 3, "interval_ms": 100, "state": "state.json", "b": {"argv": ["true"]},
                        "loops": {"$ref": "all.json"}})
        self.assertEqual((r.returncode, r.stderr, list(self.kids())), (0, "", ["d"]))

    def test_loops_split_bad(self):
        (self.t / "p.json").write_text(json.dumps({"a": "x"}))
        (self.t / "l.json").write_text(json.dumps(["x"]))
        for loops, code in (([{"$ref": "p.json"}, {"a": "y"}], "CfgBad"),        # 舊的「物件的陣列＝分頁」不收了（10-23 使用者改）
                            ({"$ref": ["p.json", "l.json"]}, "DirectiveBad"),    # 一份物件、一份陣列：合不起來
                            ({"$ref": ["p.json", "nope.json"]}, "DirectiveBad"), # 有一份讀不到
                            ({"$ref": ["l.json", "l.json"]}, "CfgBad"),          # 合成陣列：不是 {名字: 子項}
                            ({"$ref": "nope.json"}, "DirectiveBad"),              # 讀不到
                            ({"a": {"$env": "NOPE_XYZ"}}, "DirectiveBad"),        # 子項解不開
                            ({"a": {"exec": "x", "max": {"$env": "NOPE_XYZ"}}}, "DirectiveBad")):
            r = self.run_d({"loops": loops, "max": 1})
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, code, 1), (loops, r.stderr))
            self.assertEqual(list(self.s.iterdir()), [], loops)   # 沒起任何子項

    def test_ctl_loops_added_removed(self):
        # 期望表＝（loops_ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed；整份 loops_ctl 就是期望（N-06），
        # 拿掉 loops_added 就回 daemon.json 的名單（加進來的收掉）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        a1 = k["a"]["pid"]
        self.lctl({"loops_added": {"b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and set(self.kids()) == {"a", "b"} and self.kids())
        self.assertEqual((k["a"]["pid"], k["b"]["phase"]), (a1, "running"))
        b1 = k["b"]["pid"]
        self.lctl({"loops_added": {"b": self.long()}, "loops_removed": ["a", "nobody"]})
        k = until(lambda: list(self.kids()) == ["b"] and self.kids())
        self.assertEqual((k["b"]["pid"], alive(a1)), (b1, False))
        self.lctl({"seq": 1})   # 沒寫 loops_added／loops_removed＝回 daemon.json 的名單：a 重新起、b 收掉
        k = until(lambda: list(self.kids()) == ["a"] and self.kids()["a"]["pid"] != a1 and self.kids())
        self.assertTrue(k)
        self.assertFalse(until(lambda: alive(b1), secs=1))
        a2 = k["a"]["pid"]
        # 跟 ctl 的 loops 一起寫：相對 ctl 的 loops 加減；同一個名字兩邊都寫＝不要（先加後減）
        self.lctl({"loops": {"a": self.long(), "c": self.long()}, "loops_added": {"d": self.long(), "e": self.long()},
                   "loops_removed": ["c", "e"]})
        k = until(lambda: set(self.kids()) == {"a", "d"} and (self.s / "d" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual((k["a"]["pid"], (self.s / "c").exists(), (self.s / "e").exists()), (a2, False, False))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual([alive(x["pid"]) for x in k.values()], [False, False])

    def test_ctl_loops_added_bad_and_ref(self):
        # 寫壞＝整份不採用、記 loops_state 的 ctl_warning（N-08）；loops_ctl 裡的相對 $ref 從它的資料夾（$AOS_STACK）算
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        for bad, why in (({"loops_removed": "a"}, "loops_removed"), ({"loops_removed": [1]}, "loops_removed"),
                         ({"loops_added": {"x/y": "long"}}, "資料夾名"), ({"loops_added": {"state.json": "long"}}, "撞名"),
                         ({"loops_added": [{"b": "long"}]}, "要是 {名字"),
                         ({"loops_added": {"$ref": "nope.json"}}, "指示詞解不開")):
            self.lctl(dict(bad, loops_removed=bad.get("loops_removed", ["a"])))
            st = until(lambda: why in (self.lstate()["ctl_warning"] or "") and self.lstate())
            self.assertTrue(st, bad)
            self.assertEqual(list(rows_of(self.s, st)), ["a"], bad)   # 維持上一份好的
        (self.s / "more.json").write_text(json.dumps({"b": "long"}))
        (self.s / "w").mkdir()
        (self.s / "w" / "more2.json").write_text(json.dumps({"c": "long"}))
        self.lctl({"loops_added": {"$ref": ["more.json", "w/more2.json"]}})
        k = until(lambda: (self.s / "c" / "starts").exists() and set(self.kids()) == {"a", "b", "c"} and self.kids())
        self.assertTrue(k)
        self.assertIsNone(self.lstate()["ctl_warning"])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_state_split(self):
        # loops_state 的 loops 表超過 100 列就切檔：loops＝{"$ref": ["loops_state_loops/<雜湊>.json", …]}，每份最多 100 列
        names = ["k%03d" % i for i in range(101)]
        r = self.run_d({"state": "state.json", "max": 4, "interval_ms": 100, "b": {"argv": ["true"]},
                        "loops": {n: self.quick() for n in names}}, timeout=60)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        self.assertEqual(list(st["loops"]), ["$ref"])
        refs = st["loops"]["$ref"]
        self.assertTrue(all(re.fullmatch(r"loops_state_loops/[0-9a-f]{16}\.json", x) for x in refs), refs)
        pages = [json.loads((self.s / x).read_text()) for x in refs]
        self.assertEqual([len(x) for x in pages], [100, 1])
        rows = rows_of(self.s, st)
        self.assertEqual((list(rows), {x["phase"] for x in rows.values()}), (names, {"done"}))
        self.assertEqual(directive(st, self.s)["loops"], rows)   # 讀 loops_state 的人用 aos-directive 解就拿回整張表
        left = sorted(x.name for x in (self.s / "loops_state_loops").iterdir())
        self.assertTrue(set(x.split("/")[1] for x in refs) <= set(left) and len(left) <= 4, left)   # 只留這次與上一次的
        self.assertFalse(any(x.startswith(".") for x in left), left)
        # 子項名字不能跟分檔資料夾撞名
        r = self.run_d({"state": "state.json", "max": 1, "loops": {"loops_state_loops": self.long()}})
        self.assertTrue(r.returncode == 1 and "撞名" in r.stderr, r.stderr)

    def test_state_split_adopt_and_shrink(self):
        # 切了檔的 loops_state 照樣接回；名單縮回 100 以內，loops 變回物件、分檔清掉
        names = ["k%03d" % i for i in range(101)]
        doc = {"state": "state.json", "ctl": "ctl.json", "loops": {n: ["/bin/sleep", "1000"] for n in names}}
        p = self.start(doc)
        k = until(lambda: len(self.kids()) == 101 and all(r["phase"] == "running" for r in self.kids().values())
                  and self.kids(), secs=60)
        self.assertTrue(k)
        self.assertEqual(list(self.lstate()["loops"]), ["$ref"])
        p.kill()
        p.wait()
        p2 = self.start()
        time.sleep(1.5)
        k2 = self.kids()
        self.assertEqual({n: r["pid"] for n, r in k2.items()}, {n: r["pid"] for n, r in k.items()})   # 全部接回、沒重起
        self.lctl({"loops_removed": names[:2]})
        st = until(lambda: "$ref" not in self.lstate()["loops"] and len(self.lstate()["loops"]) == 99 and self.lstate())
        self.assertTrue(st)
        self.assertTrue(until(lambda: not (self.s / "loops_state_loops").exists()))
        self.ctl({"stopped": True})
        out, err = p2.communicate(timeout=60)
        self.assertEqual((p2.returncode, err), (0, ""))
        self.assertEqual([n for n, r in k.items() if alive(r["pid"])], [])


    # ---- 10-24：exec 直接放內嵌單子（使用者「exec本來就應該要可以直接放內嵌單子吧」）

    SHOW = 'printf "%s|%s|%s|%s\\n" "$AOS_CF" "$AOS_CD" "$AOS_CO" "$PWD" >> "$AOS_STACK/seen"'

    def test_inline_own_exec(self):
        # daemon 自己的 exec 是單子：行程內跑，AOS_CF＝daemon.json、AOS_CO＝/exec、cwd＝daemon.json 的資料夾
        r = self.run_d({"exec": {"argv": ["sh", "-c", self.SHOW]}, "max": 2, "interval_ms": 0})
        real = os.path.realpath(self.t)
        line = "%s/daemon.json|%s|/exec|%s" % (real, real, real)
        self.assertEqual((r.returncode, r.stderr, (self.s / "seen").read_text().splitlines()), (0, "", [line, line]))

    def test_inline_own_exec_codes(self):
        r = self.run_d({"exec": {"argv": ["sh", "-c", "exit 6"]}, "max": 3, "interval_ms": 0})
        self.assertEqual((r.returncode, r.stderr), (6, "aos-daemon: 第 1 次 daemon.json#/exec 失敗，結束碼 6\n"))
        r = self.run_d({"exec": {"argv": ["sleep", "30"], "timeout_ms": 200, "grace_ms": 200}, "max": 3})
        self.assertEqual((r.returncode, r.stderr), (143, "aos-daemon: 第 1 次 daemon.json#/exec 失敗，結束碼 143\n"))
        r = self.run_d({"exec": {"argv": ["true"], "timeout_ms": "x"}, "max": 3})
        self.assertEqual((r.returncode, len(r.stderr.splitlines())), (1, 1), r.stderr)
        self.assertTrue(r.stderr.startswith("aos-daemon: EntryBad 單子跑不起來："), r.stderr)

    def test_inline_child(self):
        # 子項的 exec 是單子：子 loop 跑它（AOS_CF＝小格的 loop.json、AOS_CO＝/exec）；cwd 定成 daemon 的 cwd（沒寫＝它、相對的接在它後面），
        # 裡面相對的 $ref 照 daemon.json 的資料夾轉成絕對
        (self.t / "sub").mkdir()
        (self.t / "data.json").write_text('{"m": "hi"}')
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {
            "a": {"exec": {"argv": ["sh", "-c", self.SHOW]}, "max": 1},
            "b": {"exec": {"argv": ["sh", "-c", 'pwd > "$AOS_STACK/pwd"'], "cwd": "sub"}, "max": 1},
            "c": {"exec": {"argv": ["echo", {"$ref": "data.json#/m"}], "stdout": {"$env": "AOS_STACK", "$path": "out"}}, "max": 1}}})
        k = until(lambda: len(self.kids()) == 3 and all(r["phase"] == "done" for r in self.kids().values()) and self.kids())
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, {n: r["code"] for n, r in k.items()}), (0, "", {"a": 0, "b": 0, "c": 0}))
        real = os.path.realpath(self.t)
        cell = os.path.realpath(self.s / "a")
        self.assertEqual((self.s / "a" / "seen").read_text(), "%s/loop.json|%s|/exec|%s\n" % (cell, cell, real))
        self.assertEqual((self.s / "b" / "pwd").read_text().strip(), real + "/sub")
        self.assertEqual((self.s / "c" / "out").read_text(), "hi\n")
        lj = json.loads((self.s / "c" / "loop.json").read_text())
        self.assertEqual(lj["exec"]["argv"][1], {"$ref": real + "/data.json#/m"})   # 只轉 $ref 的檔名、不解

    def test_inline_child_via_ctl(self):
        # loops_ctl 半路加的子項，exec 是單子也能跑
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {}})
        until(lambda: self.state())
        self.lctl({"loops_added": {"x": {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"; exit 3']}, "max": 2}}})
        k = until(lambda: self.kids().get("x", {}).get("phase") == "done" and self.kids())
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, k["x"]["code"], (self.s / "x" / "ran").read_text()), (0, "", 3, "x\n"))
        self.assertIn("aos-loop: 第 1 次 loop.json#/exec 失敗，結束碼 3", (self.s / "x" / "stderr.txt").read_text())

    # ---- 10-24 審後補：還原、訊號、abs_refs 邊界、收不肯退的單子

    def popen_env(self, extra):
        p = subprocess.Popen([DAEMON, "daemon.json"], cwd=str(self.t), env=env_of(extra),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def test_inline_env_restored_had_values(self):
        # daemon 自己的 exec 是單子：跑的那段 AOS_CF／CD／CO 設成單子的位置，跑完還原成原本的值（原本有值）。
        # 看得出來的地方：之後讀 loops_ctl 時 loops 用 $env 讀它們——還原了＝指到 p1／p2／p3、子項都退 0；
        # 沒還原＝指到 daemon.json、它的資料夾、/exec，子項起不來
        for n in ("p1", "pd/p2", "p3"):   # p2 放在 pd/ 底下：AOS_CD 原本＝pd，跟 daemon.json 的資料夾分得開
            (self.t / n).mkdir(parents=True)
            (self.t / n / "_entry").write_text('#!/bin/sh\necho x >> "$AOS_STACK/ran"\n')
            (self.t / n / "_entry").chmod(0o755)
        self.cfg({"exec": {"argv": ["true"]}, "interval_ms": 100, "state": "state.json", "ctl": "ctl.json", "loops": {}})
        p = self.popen_env({"AOS_STACK": str(self.s), "AOS_CF": str(self.t / "p1"), "AOS_CD": str(self.t / "pd"), "AOS_CO": "p3"})
        self.assertTrue(until(lambda: self.state()["counter_runs"] >= 1))
        self.lctl({"loops": {"a": {"exec": {"$env": "AOS_CF"}, "max": 1}, "b": {"exec": {"$env": "AOS_CD", "$path": "p2"}, "max": 1},
                             "c": {"exec": {"$env": "AOS_CO"}, "max": 1}}})
        k = until(lambda: len(self.kids()) == 3 and all(r["phase"] == "done" for r in self.kids().values()) and self.kids())
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual({n: r["code"] for n, r in k.items()}, {"a": 0, "b": 0, "c": 0})
        self.assertEqual({n: (self.s / n / "ran").read_text() for n in "abc"}, {n: "x\n" for n in "abc"})

    # 內嵌單子收的是整群的 SIGTERM，sleep 也被殺；sh（dash／bash）有時會在自己的 stderr 報一行「Terminated」
    # （看時序，10-28 WSL 撞到）——那是測試小程式自己說的、不是被測程式；開頭 exec 2>/dev/null 讓 err 只剩被測程式自己的。
    TRAP = 'exec 2>/dev/null; trap \'echo got > "$AOS_STACK/got"; exit 0\' TERM; touch "$AOS_STACK/up"; while :; do sleep 0.05; done'

    def test_inline_child_sigterm_forwarded(self):
        # daemon 收 SIGTERM → 送給子 loop → 子 loop 轉給它正在跑的內嵌單子（整群）、等它收完再退
        p = self.start({"state": "state.json", "loops": {"a": {"exec": {"argv": ["sh", "-c", self.TRAP]}, "max": 5}}})
        self.assertTrue(until(lambda: (self.s / "a" / "up").exists()))
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        r = self.kids()["a"]
        self.assertEqual((p.returncode, err, (self.s / "a" / "got").read_text(), r["phase"], r["code"]), (143, "", "got\n", "stopped", 143))

    def test_inline_own_exec_sigterm(self):
        # daemon 自己的 exec 是內嵌單子、跑一半收 SIGTERM：轉給單子、等它收完，以 143 結束
        p = self.start({"exec": {"argv": ["sh", "-c", self.TRAP]}, "max": 5, "state": "state.json"})
        self.assertTrue(until(lambda: (self.s / "up").exists()))
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, (self.s / "got").read_text(), self.state()["phase"]), (143, "", "got\n", "stopped"))

    def test_abs_refs_edges(self):
        # 子項單子裡的 $ref 搬進小格前轉成絕對（abs_refs）：絕對的不動、$ref 陣列每個字串元素都轉、只有 #/… 的不動、
        # 寫法不合（不是字串）的不動、指示詞裡別的 key 不往裡走、不是指示詞的物件往裡走
        unit = {"argv": ["true"], "x": [
            {"$ref": "/abs/d.json#/m"}, {"$ref": ["d1.json", "sub/d2.json#/x", "/abs/d3.json"]}, {"$ref": "#/m"},
            {"$ref": 5}, {"$ref": ["d1.json", 7]}, {"$ref": "d.json", "$path": {"$ref": "in.json"}},
            {"deep": {"$ref": "sub/d4.json"}}, {"$env": "HOME"}]}
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": {"exec": unit, "max": 1}}})
        until(lambda: self.kids().get("a", {}).get("phase") == "done")
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        real = os.path.realpath(self.t)
        x = json.loads((self.s / "a" / "loop.json").read_text())["exec"]["x"]
        self.assertEqual(x, [
            {"$ref": "/abs/d.json#/m"}, {"$ref": [real + "/d1.json", real + "/sub/d2.json#/x", "/abs/d3.json"]}, {"$ref": "#/m"},
            {"$ref": 5}, {"$ref": [real + "/d1.json", 7]}, {"$ref": real + "/d.json", "$path": {"$ref": "in.json"}},
            {"deep": {"$ref": real + "/sub/d4.json"}}, {"$env": "HOME"}])

    def test_stubborn_inline_child_killed_with_loop(self):
        # 子 loop 的內嵌單子不理 SIGTERM、grace_ms 又比 daemon 的 10 秒長：滿 10 秒 daemon SIGKILL 子 loop 那群時，
        # 單子（inst 起的、自成一群）也一起收掉，不留孤兒（10-24 審後補；原本整群打不到它）
        body = 'trap "" TERM; echo $$ > "$AOS_STACK/pid"; while :; do sleep 0.05; done'
        p = self.start({"state": "state.json", "loops": {"a": {"exec": {"argv": ["sh", "-c", body], "grace_ms": 60000}, "max": 1}}})
        self.assertTrue(until(lambda: (self.s / "a" / "pid").read_text().strip()))
        pid = int((self.s / "a" / "pid").read_text())
        self.addCleanup(lambda: alive(pid) and os.killpg(pid, signal.SIGKILL))
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (143, ""))
        self.assertGreater(time.monotonic() - t0, 9)
        self.assertTrue(until(lambda: not alive(pid), 3), "單子留成孤兒")

    # ───── H. 10-29 拆窗（medium-plan § 四、實作步驟 1）：ctl.json／state.json 管 loop 面向，loops_ctl.json／loops_state.json 管名單 ─────

    def test_ctl_loops_moved_warns(self):
        # ctl.json 寫 loops_added 沒反應（其他 key 照採），state 的 ctl_warning 提醒搬家（過渡期，衝突 5）；寫到 loops_ctl.json 才起
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "a" / "starts").exists() and self.kids()))
        self.ctl({"loops_added": {"b": self.long()}, "loops_removed": ["a"], "seq": 1})
        st = until(lambda: self.state()["ctl_seq"] == 1 and self.state())
        self.assertTrue(st)
        self.assertIn("已搬到 loops_ctl.json", st["ctl_warning"] or "")
        time.sleep(1)
        self.assertEqual((list(self.kids()), (self.s / "b").exists()), (["a"], False))
        self.lctl({"loops_added": {"b": self.long()}})
        self.assertTrue(until(lambda: (self.s / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        self.ctl({"seq": 2})   # 拿掉 loops* 的 ctl：提醒清掉
        self.assertTrue(until(lambda: self.state()["ctl_seq"] == 2 and self.state()["ctl_warning"] is None))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))

    def test_both_ctls_same_cycle(self):
        # 同一圈 ctl.json 改 interval_ms、loops_ctl.json 加子項：兩邊都生效，各自回自己的 seq
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 300, "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "a" / "starts").exists() and self.kids()))
        self.lctl({"loops_added": {"b": self.long()}, "seq": 3})
        self.ctl({"interval_ms": 50, "seq": 7})
        self.assertTrue(until(lambda: (self.s / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        st = until(lambda: self.state()["interval_ms"] == 50 and self.state())
        self.assertTrue(st)
        ls = self.lstate()
        self.assertEqual((st["ctl_seq"], st["ctl_warning"], ls["ctl_seq"], ls["ctl_warning"]), (7, None, 3, None))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_bad_ctl_good_loops_ctl(self):
        # ctl.json 壞、loops_ctl.json 好：只有 state.json 有 ctl_warning，名單照 loops_ctl 改
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "a" / "starts").exists() and self.kids()))
        self.ctl("{not json")
        self.lctl({"loops_added": {"b": self.long()}, "seq": 1})
        self.assertTrue(until(lambda: (self.s / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        self.assertTrue(until(lambda: "不是 JSON" in (self.state()["ctl_warning"] or "")))
        self.assertEqual((self.lstate()["ctl_seq"], self.lstate()["ctl_warning"]), (1, None))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_paused_holds_loops_ctl(self):
        # ctl.json paused＝整圈暫停：loops_ctl 的變動不生效（照讀、ctl_seq 照回），兩扇 state 照寫；解除暫停那圈才生效
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        self.ctl({"paused": True, "seq": 1})
        self.assertTrue(until(lambda: self.state()["phase"] == "paused"))
        self.lctl({"loops_added": {"b": self.long()}, "loops_removed": ["a"], "seq": 2})
        ls = until(lambda: self.lstate()["ctl_seq"] == 2 and self.lstate())
        self.assertTrue(ls)
        time.sleep(1.5)
        ls2 = self.lstate()
        self.assertNotEqual(ls2["recorded_at"], ls["recorded_at"])   # 暫停中照寫
        self.assertEqual((list(ls2["loops"]), ls2["loops"]["a"]["phase"], alive(k["a"]["pid"]), (self.s / "b").exists()),
                         (["a"], "running", True, False))
        self.ctl({"seq": 3})   # 解除暫停：b 起、a 收掉
        self.assertTrue(until(lambda: (self.s / "b" / "starts").exists() and list(self.kids()) == ["b"]))
        self.assertFalse(alive(k["a"]["pid"]))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_loops_windows_null_and_bad(self):
        # loops_state／loops_ctl 寫 null＝不開：不寫 loops_state.json、不讀 loops_ctl.json，那兩個名字也就不撞名
        (self.s / "loops_ctl.json").write_text(json.dumps({"loops_added": {"x": self.quick()}}))
        r = self.run_d({"state": "state.json", "loops_state": None, "loops_ctl": None, "max": 3, "interval_ms": 100,
                        "b": {"argv": ["true"]}, "loops": {"loops_state.json": self.quick()}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(((self.s / "loops_state.json" / "loop.json").exists(), (self.s / "x").exists(),
                          (self.s / ".loops_state.json").exists(), "loops" in self.state()), (True, False, False, False))
        # 檔名可以改、指示詞照解（這裡指到 stack 裡不在的資料夾＝寫不了）；型別不對＝CfgBad
        (self.t / "names.json").write_text(json.dumps({"ls": "w/ls.json"}))
        r = self.run_d({"loops_state": {"$ref": "names.json#/ls"}, "max": 1})
        self.assertEqual((r.returncode, r.stderr.split(" ")[1], "w/.ls.json" in r.stderr), (1, "WriteFailed", True), r.stderr)
        for bad in (3, "", ["a"]):
            for k in ("loops_ctl", "loops_state"):
                r = self.run_d({k: bad, "max": 1})
                self.assertEqual((r.returncode, r.stderr.split(" ")[1], k in r.stderr), (1, "CfgBad", True), (k, bad, r.stderr))

    def test_child_name_clashes_with_loops_windows(self):
        # 撞名跟著多兩扇窗與分檔資料夾：預設 loops_ctl.json、loops_state.json、loops_state_loops；改了名照實際的第一段
        for win, name in (({}, "loops_ctl.json"), ({}, "loops_state.json"), ({}, "loops_state_loops"),
                          ({"loops_ctl": "lc/x.json"}, "lc"), ({"loops_state": "ls.json"}, "ls_loops")):
            r = self.run_d(dict(win, loops={name: self.long()}, max=1))
            self.assertEqual(r.returncode, 1, (win, name))
            self.assertTrue(r.stderr.startswith("aos-daemon: CfgBad ") and "撞名" in r.stderr
                            and r.stderr.count("\n") == 1, r.stderr)
            self.assertFalse((self.s / name).exists(), name)
        # state.json 不再有 loops 表，原本的 state_loops 就只是普通名字
        r = self.run_d({"state": "state.json", "loops": {"state_loops": self.quick()}, "b": {"argv": ["true"]}, "max": 3,
                        "interval_ms": 100})
        self.assertEqual((r.returncode, r.stderr, (self.s / "state_loops" / "loop.json").exists()), (0, "", True))

    # ───── I. 10-29 信箱模式（medium-plan § 四 3、實作步驟 5）：daemon.json 寫 loops_mailbox，名單的增減改成一封封信 ─────

    def box(self):
        return self.s / "box"

    def post(self, name, body, reply_to=None, raw=None):
        """照 N-16 寄一封（tmp/ 寫好再 rename 進 new/）；信號自己取，好控制名字順序。"""
        d = self.box() / "tmp" / name
        d.mkdir()
        letter = {"kind": "letter", "sender": str(self.t), "sent_at": "2026-10-29T00:00:00.000+00:00", "body": body}
        if reply_to is not None:
            letter["reply_to"] = str(reply_to)
        (d / "letter.json").write_text(raw if raw is not None else json.dumps(letter))
        os.rename(d, self.box() / "new" / name)

    def drained(self):
        return not list((self.box() / "new").iterdir()) and not list((self.box() / "cur").iterdir())

    def reply_box(self):
        rb = self.t / "rb"
        for x in ("tmp", "new", "cur"):
            (rb / x).mkdir(parents=True)
        return rb

    def mstart(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops_mailbox": "box", "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "a" / "starts").exists() and self.kids()))
        return p

    def pause(self, seq):
        self.ctl({"paused": True, "seq": seq})
        self.assertTrue(until(lambda: self.state()["phase"] == "paused" and self.state()["ctl_seq"] == seq))

    def mstop(self, p):
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))

    def test_mailbox_same_cycle_later_name_wins_and_paused_holds(self):
        # 兩個寄信人同一圈各一封（一加 bob、一刪 bob）：照名字順序套，後面的贏。paused＝信留在 new/ 不認領，解除那圈才套
        p = self.mstart()
        self.assertEqual((sorted(x.name for x in self.box().iterdir()), (self.s / "loops_ctl.json").exists()),
                         (["cur", "new", "tmp"], False))
        self.pause(1)
        self.post("0001", {"loops_added": {"bob": self.long()}})
        self.post("0002", {"loops_removed": ["bob"]})
        time.sleep(1)
        self.assertEqual((sorted(x.name for x in (self.box() / "new").iterdir()), (self.s / "bob").exists()),
                         (["0001", "0002"], False))
        self.ctl({"seq": 2})   # 解除暫停：同一圈認領兩封，加了又刪＝bob 沒起
        self.assertTrue(until(self.drained))
        time.sleep(0.6)
        self.assertEqual((list(self.kids()), (self.s / "bob").exists()), (["a"], False))
        self.pause(3)
        self.post("0003", {"loops_removed": ["bob"]})   # 反過來：先刪後加＝bob 起
        self.post("0004", {"loops_added": {"bob": self.long()}})
        self.ctl({"seq": 4})
        self.assertTrue(until(lambda: (self.s / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        self.assertEqual(((self.box() / "done").exists(), self.lstate()["letter_warning"]), (False, None))   # 預設收掉、不留 done/
        self.mstop(p)

    def test_mailbox_adopted_stays_until_removed(self):
        # 方向題 1：重起後 adopt 接回的（daemon.json 沒有的）留在名單上，直到有信 loops_removed 它
        p = self.mstart()
        self.post("0001", {"loops_added": {"bob": self.long()}})
        k = until(lambda: (self.s / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"} and self.kids())
        self.assertTrue(k)
        bob = k["bob"]["pid"]
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        time.sleep(1.5)
        k2 = self.kids()
        self.assertEqual((set(k2), k2["bob"]["pid"], k2["bob"]["phase"], alive(bob),
                          len((self.s / "bob" / "starts").read_text().split())), ({"a", "bob"}, bob, "running", True, 1))
        self.post("0002", {"loops_removed": ["bob"]})
        self.assertTrue(until(lambda: list(self.kids()) == ["a"]))
        self.assertFalse(alive(bob))
        self.mstop(p2)

    def test_mailbox_bad_letters_dont_block_good(self):
        # 壞信丟掉、不影響同一圈的好信；letter_warning＝最後一封壞信的原因（沒有壞信的圈維持原值）；壞信有 reply_to 也不回（決定 27）
        rb = self.reply_box()
        p = self.mstart()
        self.pause(1)
        self.post("0001", [1], reply_to=rb)                                   # body 不是物件
        self.post("0002", {"loops_added": {"box": self.long()}})              # 跟信箱撞名
        self.post("0003", {"loops_added": {"bob": self.long()}, "x": 1})      # 好信（不認得的 key 忽略）
        self.post("0004", {"loops_removed": "bob"})                           # 型別錯
        self.post("0005", None, raw="{not json")                              # letter.json 壞
        self.ctl({"seq": 2})
        self.assertTrue(until(lambda: (self.s / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        w = until(lambda: self.lstate()["letter_warning"])
        self.assertTrue(w and w.startswith("信 0005 不採用：") and "letter.json" in w, w)
        self.assertEqual((list((rb / "new").iterdir()), (self.box() / "loop.json").exists()), ([], False))
        self.post("0006", {"loops_removed": ["bob"]})   # 只有好信的圈：letter_warning 維持
        self.assertTrue(until(lambda: list(self.kids()) == ["a"]))
        self.assertEqual(self.lstate()["letter_warning"], w)
        self.mstop(p)

    def test_mailbox_reply_to_applied(self):
        # 寫了 reply_to 的好信：對完表才回一封 body {"applied": true}、in_reply_to＝原信號；沒寫 reply_to 的不回
        rb = self.reply_box()
        p = self.mstart()
        self.post("0001", {"loops_added": {"bob": self.long()}}, reply_to=rb)
        self.post("0002", {"loops_added": {"carl": self.long()}})
        got = until(lambda: list((rb / "new").iterdir()))
        self.assertTrue(got)
        self.assertTrue((self.s / "bob" / "loop.json").exists())
        time.sleep(0.6)
        self.assertEqual(len(list((rb / "new").iterdir())), 1)
        r = json.loads((got[0] / "letter.json").read_text())
        self.assertEqual((r["kind"], r["in_reply_to"], r["body"]), ("letter", "0001", {"applied": True}))
        self.mstop(p)

    def test_mailbox_cfg_rules(self):
        # loops_ctl 明寫（非 null）＋loops_mailbox＝CfgBad；loops_ctl 寫 null 或沒寫＝不開、不報錯；型別錯、撞名＝CfgBad
        for doc in ({"loops_mailbox": "box", "loops_ctl": "loops_ctl.json"}, {"loops_mailbox": "box", "loops_ctl": "x.json"},
                    {"loops_mailbox": 3}, {"loops_mailbox": ""}, {"loops_mailbox": ["box"]},
                    {"loops_mailbox": "m/box", "loops": {"m": self.long()}}):
            r = self.run_d(dict(doc, max=1))
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, "CfgBad", 1), (doc, r.stderr))
            self.assertFalse((self.s / "box").exists() or (self.s / "m").exists(), doc)
        (self.s / "loops_ctl.json").write_text(json.dumps({"loops_added": {"x": self.quick()}}))
        for lc in ({}, {"loops_ctl": None}):
            r = self.run_d(dict(lc, loops_mailbox="box", state="state.json", max=3, interval_ms=100))
            self.assertEqual((r.returncode, r.stderr, (self.s / "x").exists(), (self.box() / "new").is_dir()),
                             (0, "", False, True), lc)
        # $AOS_STACK 不在＝不替人建（信箱的 init 是 mkdir -p）
        gone = self.t / "no" / "stack"
        r = self.run_d({"loops_mailbox": "box", "loops_state": None, "max": 1}, env={"AOS_STACK": str(gone)})
        self.assertEqual((r.returncode, r.stderr.split(" ")[1], gone.exists()), (1, "MkdirFailed", False), r.stderr)

    def test_mailbox_cur_leftovers_redone_first(self):
        # 起來時 cur/ 不空（上次認領了、沒收完就死）：當成這圈認領到的，排在 new/ 前面重做
        for x in ("tmp", "new", "cur"):
            (self.box() / x).mkdir(parents=True)
        self.post("0009", {"loops_added": {"bob": self.long(), "carl": self.long()}})
        os.rename(self.box() / "new" / "0009", self.box() / "cur" / "0009")
        self.post("0001", {"loops_removed": ["carl"]})   # 名字排前面，但在 new/：排在 cur/ 的後面＝carl 被刪
        p = self.mstart()
        self.assertTrue(until(lambda: (self.s / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        time.sleep(0.6)
        self.assertEqual((set(self.kids()), (self.s / "carl").exists()), ({"a", "bob"}, False))
        self.mstop(p)

    # ───── J. 10-30 exec 型子項 execs（thinking 2026-10-30-agent-lifecycle B-12 ②、實作步驟 7）：直接 aos-exec 一次、不包 aos-loop ─────

    JOB = ('echo "$*" >> "$AOS_STACK/runs"\necho "$AOS_STACK" > "$AOS_STACK/stack.txt"\ncat > "$AOS_STACK/stdin.txt"\n'
           'echo "$$ $(cut -d" " -f5 /proc/$$/stat)" > "$AOS_STACK/ids"\necho "job 的 stderr" >&2\nexit 3\n')

    def prog(self, name, body):
        d = self.t / name
        d.mkdir()
        (d / "_entry").write_text("#!/bin/sh\n" + body)
        (d / "_entry").chmod(0o755)

    def xkids(self):
        return rows_of(self.s, self.lstate(), "execs")

    def test_execs_once_done_not_restarted(self):
        # 字串、[目標, 參數...]、{"exec": 目標}（其他 key 忽略）三種寫法；各跑一次、退 3＝done／code 3、不重起；
        # 小格裡沒有 loop.json／ctl.json／state.json；AOS_STACK＝小格/、stdin /dev/null、stderr 進小格的 stderr.txt、自成群組（pgrp＝pid）
        self.prog("job", self.JOB)
        r = self.run_d({"state": "state.json", "max": 15, "interval_ms": 100,
                        "execs": {"j": "job", "k": ["job", "a", "b"], "o": {"exec": ["job", "c"], "max": 5}}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        self.assertEqual(st["loops"], {})
        x = self.xkids()
        self.assertEqual(list(x), ["j", "k", "o"])
        self.assertEqual({n: (r["phase"], r["code"], r["signal"]) for n, r in x.items()},
                         {n: ("done", 3, None) for n in "jko"})
        self.assertEqual({frozenset(r) for r in x.values()}, {frozenset({"pid", "started_at_ticks", "phase", "code", "signal"})})
        for n, args in (("j", ""), ("k", "a b"), ("o", "c")):
            cell = self.s / n
            self.assertEqual((cell / "runs").read_text(), args + "\n", n)   # 只跑一次
            self.assertEqual(sorted(f.name for f in cell.iterdir()), ["ids", "runs", "stack.txt", "stderr.txt", "stdin.txt"], n)
            self.assertEqual(((cell / "stack.txt").read_text(), (cell / "stdin.txt").read_text()), (str(cell) + "/\n", ""), n)
            self.assertEqual((cell / "stderr.txt").read_text(), "job 的 stderr\n", n)
            pid, pgrp = (cell / "ids").read_text().split()
            self.assertEqual((int(pid), int(pgrp)), (x[n]["pid"], x[n]["pid"]), n)   # 那支程式就是表上的 pid（中間沒有 aos-loop）

    def test_execs_removed_sigterm_then_kill_group(self):
        # execs_removed：SIGTERM 直接打那支程式（a 退了就拿掉）；不理的（b）10 秒後 SIGKILL 整群（連它的 sleep）
        self.prog("stub", 'trap "" TERM\nsleep 1000 &\necho "$$ $!" > "$AOS_STACK/pids"\nwhile :; do sleep 0.05; done\n')
        p = self.start({"state": "state.json", "ctl": "ctl.json", "execs": {"a": "long", "b": "stub"}})
        x = until(lambda: (self.s / "a" / "starts").exists() and (self.s / "b" / "pids").exists() and len(self.xkids()) == 2
                  and self.xkids())
        self.assertTrue(x)
        self.assertIn("long/_entry", Path("/proc/%d/cmdline" % x["a"]["pid"]).read_text())   # 就是那支程式、不是 aos-loop
        bpid, bsleep = map(int, (self.s / "b" / "pids").read_text().split())
        self.addCleanup(lambda: alive(bsleep) and os.kill(bsleep, signal.SIGKILL))
        self.assertEqual(bpid, x["b"]["pid"])
        t0 = time.monotonic()
        self.lctl({"execs_removed": ["a", "b"], "seq": 1})
        self.assertTrue(until(lambda: list(self.xkids()) == ["b"] and self.xkids()["b"]["phase"] == "stopping", 5))
        self.assertLess(time.monotonic() - t0, 5)
        self.assertFalse(alive(x["a"]["pid"]))
        self.assertTrue(until(lambda: self.xkids() == {}, 20))
        self.assertGreater(time.monotonic() - t0, 9)
        self.assertEqual((alive(bpid), alive(bsleep)), (False, False))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))

    def test_execs_cfg_rules_and_clash(self):
        # daemon.json：execs 跟 loops 同名、跟自己的窗撞名、寫法不合＝CfgBad 退 1、一行、不建小格
        for doc in ({"loops": {"x": self.long()}, "execs": {"x": "long"}}, {"state": "state.json", "execs": {"state.json": "long"}},
                    {"execs": [1]}, {"execs": {"a": 3}}, {"execs": {"a": {"exec": {"argv": ["true"]}}}}, {"execs": {"a": {"max": 1}}},
                    {"execs": {"a": []}}, {"execs": {"a": ["long", 1]}}, {"execs": {"a/b": "long"}}):
            r = self.run_d(dict(doc, max=1))
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, "CfgBad", 1), (doc, r.stderr))
            self.assertFalse((self.s / "x").exists() or (self.s / "a").exists(), doc)
        # loops_ctl：合出來 loops 與 execs 同名＝整份不採用（ctl_warning）；loops_removed＋execs_added 同名＝換種類：收掉舊的 loop、起 exec 型
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        self.lctl({"execs_added": {"a": "long"}, "seq": 1})
        w = until(lambda: self.lstate()["ctl_warning"])
        self.assertIn("同時在 loops 與 execs", w)
        self.assertEqual((list(self.kids()), self.xkids(), alive(k["a"]["pid"])), (["a"], {}, True))
        self.lctl({"loops_removed": ["a"], "execs_added": {"a": "long"}, "seq": 2})
        x = until(lambda: "a" in self.xkids() and self.xkids()["a"]["phase"] == "running" and self.xkids())
        self.assertTrue(x)
        self.assertEqual((self.kids(), alive(k["a"]["pid"]), self.lstate()["ctl_warning"], self.lstate()["ctl_seq"]), ({}, False, None, 2))
        self.assertTrue(until(lambda: len((self.s / "a" / "starts").read_text().split()) == 2))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.xkids()["a"]["phase"], alive(x["a"]["pid"])), (0, "", "stopped", False))

    def test_execs_adopt(self):
        # adopt 兩張表都接：exec 型子項接回、不重起；收工時照收
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"l": self.long()}, "execs": {"a": "long"}})
        x = until(lambda: (self.s / "a" / "starts").exists() and (self.s / "l" / "starts").exists() and self.xkids()
                  and self.kids() and self.xkids())
        self.assertTrue(x)
        pid, lpid = x["a"]["pid"], self.kids()["l"]["pid"]
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        time.sleep(1)
        self.assertEqual((self.xkids()["a"]["pid"], self.kids()["l"]["pid"], len((self.s / "a" / "starts").read_text().split())),
                         (pid, lpid, 1))
        self.ctl({"stopped": True})
        out, err = p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, err, self.xkids()["a"]["phase"], alive(pid), alive(lpid)), (0, "", "stopped", False, False))

    def test_max1_loop_still_runs_beside_execs(self):
        # ①（使用者 10-30「包成max:1也是可以」）：{"exec": X, "max": 1} 的 loop 型照舊——小格有 loop.json／ctl／state、列在 loops 表；
        # 同一份 daemon.json 裡的 exec 型子項列在 execs 表、小格沒有 loop.json
        self.prog("job", self.JOB)
        r = self.run_d({"state": "state.json", "max": 15, "interval_ms": 100,
                        "loops": {"bob": {"exec": "job", "max": 1}}, "execs": {"carl": "job"}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        self.assertEqual(({n: (r["phase"], r["code"]) for n, r in st["loops"].items()},
                          {n: (r["phase"], r["code"]) for n, r in st["execs"].items()}),
                         ({"bob": ("done", 3)}, {"carl": ("done", 3)}))
        self.assertEqual(((self.s / "bob" / "runs").read_text(), (self.s / "carl" / "runs").read_text()), ("\n", "\n"))
        self.assertTrue(all((self.s / "bob" / f).is_file() for f in ("loop.json", "state.json")))
        self.assertFalse((self.s / "carl" / "loop.json").exists())
        self.assertIn("aos-loop: 第 1 次", (self.s / "bob" / "stderr.txt").read_text())   # 多一層 aos-loop：它自己的那行

    def test_execs_mailbox(self):
        # 信箱模式的信多認 execs_added／execs_removed；套完 loops 與 execs 同名＝壞信、不套；done 的列留著，execs_removed 才拿掉（方向題 2）
        self.prog("job", self.JOB)
        p = self.mstart()
        self.post("0001", {"execs_added": {"j": "job"}})
        self.assertTrue(until(lambda: self.xkids().get("j", {}).get("phase") == "done"))
        time.sleep(0.6)
        self.assertEqual(((self.s / "j" / "runs").read_text(), self.xkids()["j"]["code"]), ("\n", 3))   # 不重起
        self.post("0002", {"execs_added": {"a": "long"}})   # a 已是 loop＝撞名
        w = until(lambda: self.lstate()["letter_warning"])
        self.assertTrue(w.startswith("信 0002 不採用：") and "同時在 loops 與 execs" in w, w)
        self.assertEqual(set(self.xkids()), {"j"})
        self.post("0003", {"execs_removed": ["j"]})
        self.assertTrue(until(lambda: self.xkids() == {}))
        self.mstop(p)

    def test_execs_state_split(self):
        # execs 表超過 100 列一樣切檔（同一個分檔資料夾）；loops 表照舊是物件
        names = ["x%03d" % i for i in range(101)]
        r = self.run_d({"state": "state.json", "max": 4, "interval_ms": 100, "b": {"argv": ["true"]},
                        "loops": {"l": self.quick()}, "execs": {n: "daemon.json#/b" for n in names}}, timeout=60)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        self.assertEqual((list(st["execs"]), list(st["loops"])), (["$ref"], ["l"]))
        self.assertTrue(all(re.fullmatch(r"loops_state_loops/[0-9a-f]{16}\.json", x) for x in st["execs"]["$ref"]))
        rows = self.xkids()
        self.assertEqual((list(rows), {(x["phase"], x["code"]) for x in rows.values()}), (names, {("done", 0)}))
        self.assertEqual(directive(st, self.s)["execs"], rows)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
