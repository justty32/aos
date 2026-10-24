#!/usr/bin/env python3
"""test_cli.py：aos-daemon 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-daemon

從 proto8/tests/test_daemon.py（bin 版）逐案移植（10-21 傍晚重新照抄一次：命令列 `aos-daemon [旗標] 設定檔`、exec 陣列、
子 loop 經 aos-exec 起、收工時剛死的子項標 done）：daemon.json＝loop.json 的超集、loops 表、ctl 增減、不自動重起、
收工收子項、接回（N-28、N-54、P-36）。差別只有：PATH 放 impls 的 aos-exec、aos-loop 兩支的 bin/（子 loop 經 aos-exec
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


def rows_of(stack, st):
    """state 的 loops 欄解開：物件照原樣；切檔（{"$ref": ["state_loops/<雜湊>.json", …]}）照順序讀回來合起來（10-23）。"""
    v = st.get("loops", {})
    if "$ref" not in v:
        return v
    out = {}
    for ref in v["$ref"]:
        out.update(json.loads((Path(stack) / ref).read_text()))
    return out


DIRECTIVE = IMPLS / "aos-directive" / "bin" / "aos-directive"


def directive(doc, cwd):
    """用 aos-directive 解一份 JSON（讀 state 的人就這樣拿回完整的 loops）。"""
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
        st = self.s / "state.json"
        if st.is_file():   # 測試失敗時別留孤兒（子項叫 state.json 時它是小格）
            try:
                rows = rows_of(self.s, json.loads(st.read_text()))
            except (OSError, ValueError):
                rows = {}
            for r in rows.values():
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

    def kids(self):
        return rows_of(self.s, self.state())

    def ctl(self, doc):
        tmp = self.s / ".ctl.json"
        tmp.write_text(json.dumps(doc))
        os.replace(tmp, self.s / "ctl.json")

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
        self.assertEqual({r["phase"] for r in st["loops"].values()}, {"stopped"})   # daemon 收掉的＝stopped（10-23 命名統合）
        self.assertEqual(list(st["loops"]["a"]), ["pid", "started_at_ticks", "phase", "code", "signal"])
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
        self.ctl({"loops": {"b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and "a" not in self.kids() and self.kids())
        self.assertEqual(list(k), ["b"])
        self.assertFalse(alive(a_pid))
        self.ctl({"loops": {"b": self.long()}, "stopped": True})
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
        self.assertEqual({r["phase"] for r in st["loops"].values()}, {"stopped"})

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
        # ctl 改 loops 撞名＝那份 ctl 整份不採用、維持上一份好的，原因進 state 的 ctl_warning（N-08）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        self.ctl({"loops": {"state.json": self.long()}, "stopped": True})
        st = until(lambda: "撞名" in (self.state()["ctl_warning"] or "") and self.state())
        self.assertTrue(st)
        self.assertEqual((list(st["loops"]), st["loops"]["a"]["pid"], alive(k["a"]["pid"])), (["a"], k["a"]["pid"], True))
        self.assertTrue((self.s / "state.json").is_file())
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
        self.ctl({"loops": {"a": self.long(), "b": self.long()}})   # 後來才起的也是自己的 pid
        kb = until(lambda: (self.s / "b" / "starts").exists() and "b" in self.kids() and self.kids())
        sb = until(lambda: json.loads((self.s / "b" / "state.json").read_text()))
        self.assertEqual(sb["pid"], kb["b"]["pid"])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    # ---- 10-23 壓測後（使用者「都修都處理」）

    def watch(self, secs):
        """secs 秒內每 10 毫秒讀一次 state，回看到的每一份（at 不同才算一份）。"""
        seen, end = [], time.monotonic() + secs
        while time.monotonic() < end:
            try:
                st = self.state()
                if not seen or st["at"] != seen[-1]["at"]:
                    seen.append(st)
            except (OSError, ValueError):
                pass
            time.sleep(0.01)
        return seen

    @staticmethod
    def gaps(seen):
        ts = [datetime.datetime.fromisoformat(s["at"]).timestamp() for s in seen]
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
        self.ctl({"loops": {"s2": s2, "a": self.long()}})
        seen = self.watch(1.0)
        self.assertEqual(seen[-1]["loops"]["s1"]["phase"], "stopping")
        self.assertTrue(alive(k["s1"]["pid"]))
        self.ctl({"loops": {"s2": s2, "a": self.long(), "b": self.long()}})   # 收 s1 的途中照樣起別的
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
        self.assertEqual(sorted(st["loops"]), ["a", "b", "s2"])   # s1 是 ctl 要拿掉的，收完照樣拿掉
        r2 = st["loops"]["s2"]
        self.assertEqual((r2["phase"], r2["code"], r2["signal"]), ("stopped", 137, 9))
        self.assertEqual({st["loops"][n]["phase"] for n in ("a", "b")}, {"stopped"})
        for n in ("s1", "s2"):
            cs = json.loads((self.s / n / "state.json").read_text())
            self.assertEqual(cs["phase"], "running", n)   # 來不及寫最後一份
            self.assertFalse(alive(cs["pid"]), n)          # 讀的人看 pid（＋started_at_ticks）判斷：已經不在了

    def test_one_state_per_cycle(self):
        # 第 3、4 點：沒有 exec 的 daemon 一輪只 tend 一次、只寫一份 state（不寫 running），at 的間隔穩定在 interval_ms 上下
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
        self.assertEqual(len({s["runs"] for s in seen}), len(seen), "一次只寫一份")
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
        self.assertEqual((st["phase"], st["runs"], st["loops"]), ("waiting", 0, {}))
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
        # 沒開＝起第一個子項時建不了小格＝MkdirFailed；兩種都退 1、stderr 一行、什麼都沒起
        gone = self.t / "no" / "stack"
        for doc, code in (({"state": "state.json", "loops": {"a": self.long()}}, "WriteFailed"),
                          ({"loops": {"a": self.long()}}, "MkdirFailed")):
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
        # 期望表＝（ctl 的 loops，沒寫＝daemon.json 的）＋loops_added－loops_removed；整份 ctl 就是期望（N-06），
        # 拿掉 loops_added 就回 daemon.json 的名單（加進來的收掉）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        a1 = k["a"]["pid"]
        self.ctl({"loops_added": {"b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and set(self.kids()) == {"a", "b"} and self.kids())
        self.assertEqual((k["a"]["pid"], k["b"]["phase"]), (a1, "running"))
        b1 = k["b"]["pid"]
        self.ctl({"loops_added": {"b": self.long()}, "loops_removed": ["a", "nobody"]})
        k = until(lambda: list(self.kids()) == ["b"] and self.kids())
        self.assertEqual((k["b"]["pid"], alive(a1)), (b1, False))
        self.ctl({"seq": 1})   # 沒寫 loops_added／loops_removed＝回 daemon.json 的名單：a 重新起、b 收掉
        k = until(lambda: list(self.kids()) == ["a"] and self.kids()["a"]["pid"] != a1 and self.kids())
        self.assertTrue(k)
        self.assertFalse(until(lambda: alive(b1), secs=1))
        a2 = k["a"]["pid"]
        # 跟 ctl 的 loops 一起寫：相對 ctl 的 loops 加減；同一個名字兩邊都寫＝不要（先加後減）
        self.ctl({"loops": {"a": self.long(), "c": self.long()}, "loops_added": {"d": self.long(), "e": self.long()},
                  "loops_removed": ["c", "e"]})
        k = until(lambda: set(self.kids()) == {"a", "d"} and (self.s / "d" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual((k["a"]["pid"], (self.s / "c").exists(), (self.s / "e").exists()), (a2, False, False))
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual([alive(x["pid"]) for x in k.values()], [False, False])

    def test_ctl_loops_added_bad_and_ref(self):
        # 寫壞＝整份不採用、記 ctl_warning（N-08）；ctl 裡的相對 $ref 從 ctl 的資料夾（$AOS_STACK）算
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {"a": self.long()}})
        until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        for bad, why in (({"loops_removed": "a"}, "loops_removed"), ({"loops_removed": [1]}, "loops_removed"),
                         ({"loops_added": {"x/y": "long"}}, "資料夾名"), ({"loops_added": {"state.json": "long"}}, "撞名"),
                         ({"loops_added": [{"b": "long"}]}, "要是 {名字"),
                         ({"loops_added": {"$ref": "nope.json"}}, "指示詞解不開")):
            self.ctl(dict(bad, loops_removed=bad.get("loops_removed", ["a"])))
            st = until(lambda: why in (self.state()["ctl_warning"] or "") and self.state())
            self.assertTrue(st, bad)
            self.assertEqual(list(rows_of(self.s, st)), ["a"], bad)   # 維持上一份好的
        (self.s / "more.json").write_text(json.dumps({"b": "long"}))
        (self.s / "w").mkdir()
        (self.s / "w" / "more2.json").write_text(json.dumps({"c": "long"}))
        self.ctl({"loops_added": {"$ref": ["more.json", "w/more2.json"]}})
        k = until(lambda: (self.s / "c" / "starts").exists() and set(self.kids()) == {"a", "b", "c"} and self.kids())
        self.assertTrue(k)
        self.assertIsNone(self.state()["ctl_warning"])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_state_split(self):
        # state 的 loops 表超過 100 列就切檔：loops＝{"$ref": ["state_loops/<雜湊>.json", …]}，每份最多 100 列
        names = ["k%03d" % i for i in range(101)]
        r = self.run_d({"state": "state.json", "max": 4, "interval_ms": 100, "b": {"argv": ["true"]},
                        "loops": {n: self.quick() for n in names}}, timeout=60)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.state()
        self.assertEqual(list(st["loops"]), ["$ref"])
        refs = st["loops"]["$ref"]
        self.assertTrue(all(re.fullmatch(r"state_loops/[0-9a-f]{16}\.json", x) for x in refs), refs)
        pages = [json.loads((self.s / x).read_text()) for x in refs]
        self.assertEqual([len(x) for x in pages], [100, 1])
        rows = rows_of(self.s, st)
        self.assertEqual((list(rows), {x["phase"] for x in rows.values()}), (names, {"done"}))
        self.assertEqual(directive(st, self.s)["loops"], rows)   # 讀 state 的人用 aos-directive 解就拿回整張表
        left = sorted(x.name for x in (self.s / "state_loops").iterdir())
        self.assertTrue(set(x.split("/")[1] for x in refs) <= set(left) and len(left) <= 4, left)   # 只留這次與上一次的
        self.assertFalse(any(x.startswith(".") for x in left), left)
        # 子項名字不能跟分檔資料夾撞名
        r = self.run_d({"state": "state.json", "max": 1, "loops": {"state_loops": self.long()}})
        self.assertTrue(r.returncode == 1 and "撞名" in r.stderr, r.stderr)

    def test_state_split_adopt_and_shrink(self):
        # 切了檔的 state 照樣接回；名單縮回 100 以內，loops 變回物件、分檔清掉
        names = ["k%03d" % i for i in range(101)]
        doc = {"state": "state.json", "ctl": "ctl.json", "loops": {n: ["/bin/sleep", "1000"] for n in names}}
        p = self.start(doc)
        k = until(lambda: len(self.kids()) == 101 and all(r["phase"] == "running" for r in self.kids().values())
                  and self.kids(), secs=60)
        self.assertTrue(k)
        self.assertEqual(list(self.state()["loops"]), ["$ref"])
        p.kill()
        p.wait()
        p2 = self.start()
        time.sleep(1.5)
        k2 = self.kids()
        self.assertEqual({n: r["pid"] for n, r in k2.items()}, {n: r["pid"] for n, r in k.items()})   # 全部接回、沒重起
        self.ctl({"loops_removed": names[:2]})
        st = until(lambda: "$ref" not in self.state()["loops"] and len(self.state()["loops"]) == 99 and self.state())
        self.assertTrue(st)
        self.assertTrue(until(lambda: not (self.s / "state_loops").exists()))
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
        # ctl 半路加的子項，exec 是單子也能跑
        p = self.start({"state": "state.json", "ctl": "ctl.json", "loops": {}})
        until(lambda: self.state())
        self.ctl({"loops_added": {"x": {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"; exit 3']}, "max": 2}}})
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
        # 看得出來的地方：之後讀 ctl 時 loops 用 $env 讀它們——還原了＝指到 p1／p2／p3、子項都退 0；
        # 沒還原＝指到 daemon.json、它的資料夾、/exec，子項起不來
        for n in ("p1", "pd/p2", "p3"):   # p2 放在 pd/ 底下：AOS_CD 原本＝pd，跟 daemon.json 的資料夾分得開
            (self.t / n).mkdir(parents=True)
            (self.t / n / "_entry").write_text('#!/bin/sh\necho x >> "$AOS_STACK/ran"\n')
            (self.t / n / "_entry").chmod(0o755)
        self.cfg({"exec": {"argv": ["true"]}, "interval_ms": 100, "state": "state.json", "ctl": "ctl.json", "loops": {}})
        p = self.popen_env({"AOS_STACK": str(self.s), "AOS_CF": str(self.t / "p1"), "AOS_CD": str(self.t / "pd"), "AOS_CO": "p3"})
        self.assertTrue(until(lambda: self.state()["runs"] >= 1))
        self.ctl({"loops": {"a": {"exec": {"$env": "AOS_CF"}, "max": 1}, "b": {"exec": {"$env": "AOS_CD", "$path": "p2"}, "max": 1},
                            "c": {"exec": {"$env": "AOS_CO"}, "max": 1}}})
        k = until(lambda: len(self.kids()) == 3 and all(r["phase"] == "done" for r in self.kids().values()) and self.kids())
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual({n: r["code"] for n, r in k.items()}, {"a": 0, "b": 0, "c": 0})
        self.assertEqual({n: (self.s / n / "ran").read_text() for n in "abc"}, {n: "x\n" for n in "abc"})

    TRAP = 'trap \'echo got > "$AOS_STACK/got"; exit 0\' TERM; touch "$AOS_STACK/up"; while :; do sleep 0.05; done'

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


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
