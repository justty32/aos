#!/usr/bin/env python3
"""test_cli.py：aos-daemon 命令列的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_cli.py bin/aos-daemon

從 proto8/tests/test_daemon.py（bin 版）逐案移植（10-21 傍晚重新照抄一次：命令列 `aos-daemon [旗標] 設定檔`、exec 陣列、
子 loop 經 aos-exec 起、收工時剛死的子項標 done）：daemon.json＝loop.json 的超集、procs 表、ctl 增減、不自動重起、
收工收子項、接回（N-28、N-54、P-36）。10-29 拆窗（medium-plan § 四）：名單的手把在 procs_ctl.json、子項表在 procs_state.json，
ctl.json／state.json 只管 loop 面向（H 段）；信箱 procs_ctl_mailbox（I 段，實作步驟 5；M 段跟 procs_ctl 共存）；exec 型（J 段）；子項的工作區 ws（K 段，10-30 eca）。
11-03（thinking 2026-11-03-procs）：loops／execs 統稱 procs、一份名單一張表、看寫法決定怎麼起（字串＝跑一次）、每項可寫 stack（O 段）、
daemon 的 stop／start（P 段：寫子 loop 的 ctl {"cmd": "stop"}、列留 stopped）；舊 key 不認（H 段）。差別只有：PATH 放 impls 的 aos-exec、aos-loop 兩支的 bin/（子 loop 經 aos-exec
exec 成 PATH 上的 aos-loop，10-21 傍晚起同 bin 版）、usage 一行多了代號（「aos-daemon: ArgumentsBad usage: …」）、
自己的錯多驗代號（E 段）。11-02（L 段）：log 印到 stdout（11-02 晚改預設不印、--enable-logs 才印；這裡 run_d／start 一律帶 --enable-logs），子項結束後不留名單（結束的 phase／code 看 log 那行：ended）、
兩扇窗有變才寫（心跳拿掉）。N 段（11-02）：子項的環境多 AOS_DAEMON_STACK＝daemon 的 stack（resident-bob 衝突 2）。
"""
import ctypes, datetime, json, os, re, shutil, struct, signal, subprocess, sys, tempfile, time, unittest
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
    """procs_state 的 procs 欄（11-03 起一張表）解開：物件照原樣；
    切檔（{"$ref": ["procs_state_procs/<雜湊>.json", …]}）照順序讀回來合起來（10-23）。"""
    v = st.get("procs", {})
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
        st = self.s / "procs_state.json"
        if st.is_file():   # 測試失敗時別留孤兒（子項叫 procs_state.json 時它是小格）
            try:
                doc = json.loads(st.read_text())
                rows = list(rows_of(self.s, doc).values())
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

    def run_d(self, doc, timeout=30, env=None, argv=("daemon.json",), log=True):
        if doc is not None:
            self.cfg(doc)
        return subprocess.run([DAEMON, *(["--enable-logs"] if log else []), *argv], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)} if env is None else env),
                              capture_output=True, text=True, timeout=timeout)

    def start(self, doc=None):
        if doc is not None:
            self.cfg(doc)
        p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def state(self):
        return json.loads((self.s / "state.json").read_text())

    def lstate(self):
        return json.loads((self.s / "procs_state.json").read_text())

    def kids(self):
        return rows_of(self.s, self.lstate())

    def ctl(self, doc, name="ctl.json"):
        tmp = self.s / ("." + name)
        tmp.write_text(json.dumps(doc) if not isinstance(doc, str) else doc)
        os.replace(tmp, self.s / name)

    def lctl(self, doc):
        self.ctl(doc, "procs_ctl.json")

    def long(self, mx=1):
        return {"exec": "long", "max": mx}

    # 11-02：子項結束後不留名單（loops_state 看不到它），結束的 phase／code／signal 看 daemon 的 log（stdout，預設開）
    @staticmethod
    def logs(out):
        """daemon 的 stdout 裡子項的那幾行（有 name 的），照印的順序。"""
        return [x for x in map(json.loads, out.splitlines()) if "name" in x]

    def ended(self, out):
        """{名字: 結束那行}（照結束的順序；同名結束過好幾次＝最後一次）。11-03 起 log 沒有 table。"""
        return {x["name"]: x for x in self.logs(out) if x["phase"] != "running"}

    def upped(self, out):
        """起來那幾行的名字（照起的順序，重起的會出現好幾次）。"""
        return [x["name"] for x in self.logs(out) if x["phase"] == "running"]

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
            r = self.run_d({"procs": bad, "max": 1})
            self.assertEqual(r.returncode, 1, bad)
            self.assertTrue(r.stderr.startswith("aos-daemon: "), r.stderr)

    def test_loops_up_in_cells_then_stop(self):
        sub = self.t / "sub"
        sub.mkdir()
        (sub / "_entry").write_text("#!/bin/sh\n" + LONG + "\n")
        (sub / "_entry").chmod(0o755)
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": {"exec": "sub", "max": 1}, "b": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and (self.s / "procs" / "b" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual({n: r["phase"] for n, r in k.items()}, {"a": "running", "b": "running"})
        a = json.loads((self.s / "procs" / "a" / "loop.json").read_text())
        # 10-21 傍晚：相對的 exec 照 daemon 的 cwd 轉成絕對、蓋上 _entry，子 loop 經 aos-exec 起
        self.assertEqual(a, {"exec": os.path.join(os.path.realpath(self.t), "sub"), "max": 1, "ctl": "ctl.json", "state": "state.json",
                             "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
        self.assertTrue(until(lambda: json.loads((self.s / "procs" / "b" / "state.json").read_text())["phase"] == "running"))
        pids = [r["pid"] for r in k.values()]
        self.ctl({"cmd": "stop", "seq": 1})
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["ctl_seq"]), (0, "", "stopped", 1))
        self.assertNotIn("procs", st)   # 10-29 拆窗：子項表在 procs_state.json
        self.assertEqual(list(k["a"]), ["pid", "started_at_ticks", "phase", "code", "signal", "stack"])   # 11-03 多 stack（一律寫）
        self.assertEqual(k["a"]["stack"], str(self.s / "procs" / "a"))
        ls = self.lstate()
        # 11-02 結束的子項不留在表上；11-03 sleep／wake 起收工時還在跑的 loop 型例外：列留成 sleeping（pid null、stack 留著）
        self.assertEqual(ls["procs"], {n: {"pid": None, "started_at_ticks": None, "phase": "sleeping", "code": ls["procs"][n]["code"], "signal": ls["procs"][n]["signal"],
                                           "stack": str(self.s / "procs" / n)} for n in ("a", "b")})
        self.assertEqual(list(ls), ["ctl_seq", "ctl_warning", "procs", "pid", "started_at_ticks", "boot_id",
                                    "updated_at"])   # 11-02：kind、recorded_at 拿掉；11-03 一張表 procs
        self.assertEqual([ls[k] for k in ("ctl_seq", "ctl_warning", "pid", "started_at_ticks", "boot_id")],
                         [None, None] + [st[k] for k in ("pid", "started_at_ticks", "boot_id")])   # 同一個行程的值
        # log：起來各一行、收掉各一行（收工時收掉的 loop 型＝sleeping，11-03；10-23 命名統合時是 stopped）
        lines = self.logs(out)
        self.assertEqual([(x["name"], x["phase"]) for x in lines[:2]], [("a", "running"), ("b", "running")])
        self.assertEqual(sorted((x["name"], x["phase"]) for x in lines[2:]), [("a", "sleeping"), ("b", "sleeping")])
        self.assertEqual([list(x) for x in lines], [["at", "name", "phase", "pid", "code", "signal"]] * 4)   # 11-03 拿掉 table
        self.assertEqual([x["pid"] for x in lines[:2]], [k["a"]["pid"], k["b"]["pid"]])
        self.assertEqual([(x["code"], x["signal"]) for x in lines[:2]], [(None, None)] * 2)
        self.assertTrue(all(isinstance(x["code"], int) for x in lines[2:]), lines)
        self.assertEqual([alive(x) for x in pids], [False, False])

    def test_done_child_not_restarted(self):
        p = self.start({"state": "state.json", "max": 15, "interval_ms": 100,
                        "procs": {"once": {"exec": "daemon.json#/procs/once/body", "max": 1,   # D4：內嵌單子
                                              "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"']}}}})
        out, err = p.communicate(timeout=30)
        e = self.ended(out)
        self.assertEqual((p.returncode, err, e["once"]["phase"], e["once"]["code"]), (0, "", "done", 0))   # 子 loop 自己結束＝done
        # 11-02：結束後不留在表上，本次執行也不再起（ctl 模式：daemon.json 的名單照舊有它）
        self.assertEqual((self.kids(), self.upped(out), len((self.s / "procs" / "once" / "starts").read_text().split())), ({}, ["once"], 1))

    def test_failing_child_stderr_in_cell(self):
        p = self.start({"state": "state.json", "max": 10, "interval_ms": 100,
                        "procs": {"bad": {"exec": "daemon.json#/procs/bad/body",
                                             "body": {"argv": ["sh", "-c", "exit 3"]}},
                                     "obj": {"exec": {"argv": "true"}}}})   # 10-24 起物件＝內嵌單子；形狀壞＝跑它的人的錯（11-03 只有 exec＝exec 型：aos-exec 的錯）
        out, err = p.communicate(timeout=30)
        k = self.ended(out)
        self.assertEqual((p.returncode, err, k["bad"]["phase"], k["bad"]["code"], k["obj"]["phase"], k["obj"]["code"]),
                         (0, "", "done", 3, "done", 1))
        self.assertIn("aos-loop: ", (self.s / "procs" / "bad" / "stderr.txt").read_text())
        self.assertIn("aos-exec: EntryBad 單子跑不起來：", (self.s / "procs" / "obj" / "stderr.txt").read_text())

    def test_ctl_loops_add_and_remove(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        a_pid = k["a"]["pid"]
        self.lctl({"procs": {"b": self.long()}})
        k = until(lambda: (self.s / "procs" / "b" / "starts").exists() and "a" not in self.kids() and self.kids())
        self.assertEqual(list(k), ["b"])
        self.assertFalse(alive(a_pid))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_sigterm_collects_loops_nonzero(self):
        p = self.start({"state": "state.json", "procs": {"a": self.long(), "b": self.long()}})
        k = until(lambda: (self.s / "procs" / "b" / "starts").exists() and len(self.kids()) == 2 and self.kids())
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["code"]), (143, "", "stopped", 143))
        self.assertEqual([alive(r["pid"]) for r in k.values()], [False, False])
        # 11-03 sleep／wake：收工時還在跑的 loop 型＝列留成 sleeping（pid null、stack 留著），log 那行也是 sleeping
        self.assertEqual(({n: r["phase"] for n, r in self.ended(out).items()}, {n: (r["phase"], r["pid"]) for n, r in self.kids().items()}),
                         ({"a": "sleeping", "b": "sleeping"}, {"a": ("sleeping", None), "b": ("sleeping", None)}))

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
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": {"exec": ["long"], "max": 1}}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        env = dict(x.split("=", 1) for x in Path("/proc/%d/environ" % k["a"]["pid"]).read_text().split("\0") if "=" in x)
        cell = os.path.realpath(self.s / "procs" / "a")
        self.assertEqual((env.get("AOS_CF"), env.get("AOS_CD"), env.get("AOS_CO")),
                         (os.path.join(cell, "loop.json"), cell, "/_entry"))
        self.assertEqual(json.loads((self.s / "procs" / "a" / "loop.json").read_text())["exec"],
                         [os.path.join(os.path.realpath(self.t), "long")])
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_string_child_is_exec_target(self):
        # 字串子項＝aos-exec 的目標（不限資料夾，這裡指進 daemon.json）。11-03 起字串＝exec 型：aos-exec 跑一次、不包 aos-loop
        # （原本包成 {"exec": 它} 的子 loop；procs § 2 第 1 條）——退 10 就是結束碼 10、小格沒有 loop.json
        p = self.start({"state": "state.json", "max": 10, "interval_ms": 100,
                        "procs": {"s": "daemon.json#/kids/s"},
                        "kids": {"s": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        k = self.ended(out)
        self.assertEqual((p.returncode, err, k["s"]["phase"], k["s"]["code"]), (0, "", "done", 10))
        self.assertFalse((self.s / "procs" / "s" / "loop.json").exists())
        self.assertEqual(len((self.s / "procs" / "s" / "starts").read_text().split()), 1)

    def test_child_dead_at_finish_marked_done(self):
        # D7：最後一次的 tend 之後才自己結束的子項，收工後的最後一份 state 也要是 done、記 code（不留 running）
        p = self.start({"state": "state.json", "exec": "daemon.json#/body",
                        "body": {"argv": ["sh", "-c", "sleep 2; exit 10"]},
                        "procs": {"q": {"exec": "daemon.json#/kids/q", "max": 5}},
                        "kids": {"q": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        q = self.ended(out)["q"]
        self.assertEqual((p.returncode, err, len((self.s / "procs" / "q" / "starts").read_text().split())), (0, "", 1))
        self.assertEqual((q["phase"], q["code"], q["signal"], self.kids()), ("done", 0, None, {}))

    def test_adopt_after_crash(self):
        doc = {"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        pid = k["a"]["pid"]
        p.kill()
        p.wait()
        self.assertTrue(alive(pid))
        p2 = self.start()
        time.sleep(1)
        self.assertEqual((self.kids()["a"]["pid"], len((self.s / "procs" / "a" / "starts").read_text().split())), (pid, 1))
        self.ctl({"cmd": "stop"})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(pid)), (0, False))

    def test_adopt_false_starts_fresh(self):
        doc = {"state": "state.json", "procs": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        try:
            p2 = self.start(dict(doc, adopt=False))
            k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
            self.assertTrue(k2)
            self.assertTrue(until(lambda: len((self.s / "procs" / "a" / "starts").read_text().split()) == 2))
            p2.send_signal(signal.SIGTERM)
            p2.communicate(timeout=30)
        finally:
            os.killpg(old, signal.SIGKILL)


    def test_restart_starts_loops_died_while_down(self):
        # 使用者 10-22「daemon 重開時照表起，算重新開始、不算自動重起」：停機期間死掉的子項，重開時照名單起
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        os.killpg(old, signal.SIGKILL)
        self.assertTrue(until(lambda: not alive(old)))
        p2 = self.start()
        k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
        self.assertTrue(k2)
        self.assertTrue(until(lambda: len((self.s / "procs" / "a" / "starts").read_text().split()) == 2))
        self.ctl({"cmd": "stop"})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(k2["a"]["pid"])), (0, False))

    def test_child_name_same_as_own_windows(self):
        # 11-02 拿掉 10-22 的「子項名字擋掉跟 ctl／state 同名」（使用者 11-02 答衝突 1「那兩題中的1.，可以」）：
        # 小格在 $AOS_STACK/procs/<名字>/（11-03 前 loops/），跟 daemon 自己放在 stack 頂層的窗撞不到——同名照起、窗照寫
        absst = str(self.s / "st.json")
        (self.s / "x").mkdir()   # state 的路徑照字面寫（./x/../s.json 要 x 在）；11-02 前撞名在寫之前就擋了
        for win, name, argv in (({"state": "state.json"}, "state.json", None), ({"ctl": "ctl.json"}, "ctl.json", None),
                                ({"ctl": "w/c.json"}, "w", None), ({"state": "./x/../s.json"}, "s.json", None),
                                ({"state": absst}, "st.json", None), ({}, "s2.json", ("--state", "s2.json", "daemon.json"))):
            (self.s / "procs_state.json").unlink(missing_ok=True)
            r = self.run_d(dict(win, procs={name: {"exec": "daemon.json#/b", "max": 1}}, b={"argv": ["true"]}, max=3,
                                interval_ms=100), argv=argv or ("daemon.json",))
            self.assertEqual((r.returncode, r.stderr, (self.s / "procs" / name / "loop.json").exists(),
                              list(self.ended(r.stdout))), (0, "", True, [name]), (win, name))
        for f in ("state.json", "s.json", "st.json", "s2.json"):
            self.assertEqual(json.loads((self.s / f).read_text())["phase"], "done", f)   # 窗照寫

    def test_ctl_loops_same_name_as_windows_adopted(self):
        # 11-02 起 procs_ctl 改名單用到跟窗同名的名字也照採用（10-22 的撞名不採用拿掉；小格在 procs/<名字>/）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        self.lctl({"procs": {"a": self.long(), "state.json": self.long(), "procs_state.json": self.long()}, "seq": 5})
        ls = until(lambda: self.lstate()["ctl_seq"] == 5 and set(self.kids()) == {"a", "state.json", "procs_state.json"}
                   and self.lstate())
        self.assertTrue(ls)
        self.assertTrue(until(lambda: all((self.s / "procs" / n / "starts").exists() for n in ("state.json", "procs_state.json"))))
        self.assertEqual((self.kids()["a"]["pid"], alive(k["a"]["pid"]), ls["ctl_warning"]), (k["a"]["pid"], True, None))
        self.assertTrue((self.s / "state.json").is_file() and (self.s / "procs_state.json").is_file())
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.state()["ctl_warning"]), (0, "", None))


    # ───── E. impls 才有的：錯誤代號、子 loop 的心跳是自己的 pid ─────

    def test_error_codes(self):
        r = self.run_d({"max": 1}, env={})
        self.assertTrue(r.stderr.startswith("aos-daemon: StackMissing "), r.stderr)
        for doc in ({"procs": [1], "max": 1}, {"procs": {"a/b": "x"}, "max": 1}, {"procs": {"a#b": "x"}, "max": 1}, {"adopt": 1, "max": 1},
                    {"max": None}, {"exec": 3}):   # 10-24 起 {"exec": {"argv": [...]}} 不算壞（內嵌單子，見 test_inline_*）
            r = self.run_d(doc)
            self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "CfgBad"), (doc, r.stderr))

    def test_child_state_has_own_pid(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        st = until(lambda: json.loads((self.s / "procs" / "a" / "state.json").read_text()))
        self.assertEqual(st["pid"], k["a"]["pid"])
        self.lctl({"procs": {"a": self.long(), "b": self.long()}})   # 後來才起的也是自己的 pid
        kb = until(lambda: (self.s / "procs" / "b" / "starts").exists() and "b" in self.kids() and self.kids())
        sb = until(lambda: json.loads((self.s / "procs" / "b" / "state.json").read_text()))
        self.assertEqual(sb["pid"], kb["b"]["pid"])
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    # ---- 10-23 壓測後（使用者「都修都處理」）

    def watch(self, secs):
        """secs 秒內每 10 毫秒讀一次 state，回看到的每一份（updated_at 不同才算一份）。"""
        seen, end = [], time.monotonic() + secs
        while time.monotonic() < end:
            try:
                st = self.state()
                if not seen or st["updated_at"] != seen[-1]["updated_at"]:
                    seen.append(st)
            except (OSError, ValueError):
                pass
            time.sleep(0.01)
        return seen

    def test_stubborn_child_does_not_block(self):
        # 第 1 點：不肯退的子 loop（那次不理 SIGTERM）不會卡住 daemon——送了 SIGTERM 照常巡（ctl 照讀、別的子項照起），
        # 收的途中那列是 stopping，滿 10 秒才 SIGKILL 整群。第 2 點：被 SIGKILL 的子 loop 自己的 state 停在 running（只有它自己寫，
        # N-09），看死活照 pid＋started_at_ticks（N-17）；daemon 的 log 那行寫 stopped、signal 9（11-02 起列不留在表上）。
        # 11-02 心跳拿掉：收的途中、收工等子項時 state 不再每秒寫（有變才寫），只看 loops_state 的列變
        stub = self.t / "stub"
        stub.mkdir()
        (stub / "_entry").write_text('#!/bin/sh\ntrap "" TERM\necho x >> "$AOS_STACK/starts"\nwhile :; do sleep 0.05; done\n')
        (stub / "_entry").chmod(0o755)
        s1, s2 = {"exec": "stub", "max": 1}, {"exec": "stub", "max": 1}
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 100,
                        "procs": {"s1": s1, "s2": s2, "a": self.long()}})
        k = until(lambda: all((self.s / "procs" / n / "starts").exists() for n in ("s1", "s2", "a")) and self.kids())
        self.assertTrue(k)
        self.assertTrue(until(lambda: json.loads((self.s / "procs" / "s2" / "state.json").read_text())["phase"] == "running"))
        t0 = time.monotonic()
        self.lctl({"procs": {"s2": s2, "a": self.long()}})
        self.assertTrue(until(lambda: self.kids()["s1"]["phase"] == "stopping", 3))
        self.assertTrue(alive(k["s1"]["pid"]))
        self.lctl({"procs": {"s2": s2, "a": self.long(), "b": self.long()}})   # 收 s1 的途中照樣起別的
        kb = until(lambda: (self.s / "procs" / "b" / "starts").exists() and self.kids()["b"]["phase"] == "running" and self.kids(), 3)
        self.assertTrue(kb)
        self.assertLess(time.monotonic() - t0, 5)
        p.send_signal(signal.SIGTERM)   # 收工：s2 也不肯退，等它的時候 state 停在 stopping（寫一份，之後有變才寫）
        fin = self.watch(3)
        self.assertEqual(fin[-1]["phase"], "stopping")
        # 肯退的 a、b 一退就留成 sleeping 的列（procs_state 照寫；11-03 sleep／wake：收工時還在跑的 loop 型不拿掉）
        self.assertTrue(until(lambda: {self.kids()[n]["phase"] for n in ("a", "b")} == {"sleeping"}, 3))
        out, err = p.communicate(timeout=30)
        took = time.monotonic() - t0
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"]), (143, "", "stopped"))
        self.assertGreater(took, 9)
        rows = self.ended(out)
        # s1 是 procs_ctl 要拿掉的，收完照樣拿掉；s2、a、b 是收工時還在跑的 loop 型＝留成 sleeping（11-03）
        self.assertEqual((sorted(rows), {n: r["phase"] for n, r in self.kids().items()}), (["a", "b", "s1", "s2"], {n: "sleeping" for n in ("s2", "a", "b")}))
        self.assertEqual((rows["s1"]["phase"], rows["s1"]["code"], rows["s1"]["signal"]), ("stopped", 137, 9))
        self.assertEqual((rows["s2"]["phase"], rows["s2"]["code"], rows["s2"]["signal"]), ("sleeping", 137, 9))
        self.assertEqual({rows[n]["phase"] for n in ("a", "b")}, {"sleeping"})
        for n in ("s1", "s2"):
            cs = json.loads((self.s / "procs" / n / "state.json").read_text())
            self.assertEqual(cs["phase"], "running", n)   # 來不及寫最後一份
            self.assertFalse(alive(cs["pid"]), n)          # 讀的人看 pid（＋started_at_ticks）判斷：已經不在了

    def test_quiet_while_sleeping(self):
        # 11-02（原 10-23 的「一輪只寫一份」）：沒有 exec 的 daemon 睡著時兩扇窗都不動——心跳拿掉、counter_runs 不算變動，
        # 每圈組好的那份跟上一份一樣就不碰檔：1.5 秒內 updated_at、mtime 都不變，也沒有任何改名（inotify IN_MOVED_TO／IN_CREATE）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 100, "procs": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids()))
        time.sleep(0.5)
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(os.O_NONBLOCK)
        self.assertGreaterEqual(libc.inotify_add_watch(fd, str(self.s).encode(), 0x180), 0)
        names = ("state.json", "procs_state.json")
        before = [((self.s / n).read_text(), os.stat(self.s / n).st_mtime_ns) for n in names]
        time.sleep(1.5)
        after = [((self.s / n).read_text(), os.stat(self.s / n).st_mtime_ns) for n in names]
        events, buf = [], b""
        while True:
            try:
                buf += os.read(fd, 65536)
            except BlockingIOError:
                break
        os.close(fd)
        while buf:
            _, mask, _, n = struct.unpack_from("iIII", buf)
            events.append(buf[16:16 + n].rstrip(b"\0"))
            buf = buf[16 + n:]
        self.assertEqual((before == after, events), (True, []))
        st = json.loads(after[0][0])
        self.assertEqual((st["phase"], st["counter_runs"] >= 1), ("waiting", True))   # counter_runs 是寫那一刻的快照
        self.ctl({"cmd": "stop"})   # ctl 變了（stopped）：寫
        p.communicate(timeout=30)
        self.assertEqual((p.returncode, self.state()["phase"]), (0, "stopped"))
        self.assertNotEqual(self.state()["updated_at"], st["updated_at"])

    def test_state_written_before_spawning(self):
        # 第 5 點：起子項之前就先寫一份（起一大批要好一陣子）。小格的 stderr.txt 先放一個 FIFO，daemon 開它時會卡住，
        # 卡住的這段 procs_state.json 已經在了（11-02：原本 beat 連 state.json 也寫；現在對表時起子項之前寫 loops_state、每起一個再寫）
        cell = self.s / "procs" / "x"
        cell.mkdir(parents=True)
        os.mkfifo(cell / "stderr.txt")
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"x": self.long()}})
        st = until(lambda: self.lstate(), 5)
        self.assertTrue(st, "起子項之前沒寫 procs_state")
        self.assertEqual(st["procs"], {})
        fd = os.open(cell / "stderr.txt", os.O_RDONLY | os.O_NONBLOCK)
        try:
            self.assertTrue(until(lambda: (cell / "starts").exists() and self.kids()["x"]["phase"] == "running"))
            self.ctl({"cmd": "stop"})
            p.communicate(timeout=30)
        finally:
            os.close(fd)
        self.assertEqual(p.returncode, 0)

    def test_stack_missing_not_created(self):
        # 第 6 點：$AOS_STACK 不在＝daemon 不自己建（建 stack 只在 aos-exec 做，N-59 第 1 件）：開了 state 窗＝WriteFailed、
        # 沒開＝起第一個子項時建不了小格＝MkdirFailed；兩種都退 1、stderr 一行、什麼都沒起。
        # 10-29 拆窗：loops_state 沒寫＝開著（procs_state.json），也是一扇 state 窗；兩扇都關才輪到 MkdirFailed
        gone = self.t / "no" / "stack"
        for doc, code in (({"state": "state.json", "procs": {"a": self.long()}}, "WriteFailed"),
                          ({"procs": {"a": self.long()}}, "WriteFailed"),
                          ({"procs": {"a": self.long()}, "procs_state": None}, "MkdirFailed")):
            r = self.run_d(dict(doc, max=1), env={"AOS_STACK": str(gone) + "/"})
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n"), gone.exists()), (1, code, 1, False),
                             r.stderr)

    # ───── G. 10-23 晚：指示詞（daemon.json、ctl）、ctl 的 procs_added／procs_removed、state 的 loops 切檔 ─────

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
                        "procs": {"$ref": ["loops-1.json", "sub/loops-2.json"]}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(self.upped(r.stdout), ["a", "b", "c"])   # 兩份都有 a：後面的蓋前面的、位置留在第一次
        self.assertEqual({n: k["phase"] for n, k in self.ended(r.stdout).items()}, {"a": "done", "b": "done", "c": "done"})   # c 是目標＝11-03 起跑一次
        b = json.loads((self.s / "procs" / "b" / "loop.json").read_text())
        self.assertEqual((b["max"], b["body"]), (1, {"stdout": {"$env": "NOPE_XYZ"}}))
        # loops 整個是一個 $ref；adopt 也解（解成 1＝不是布林）
        (self.t / "all.json").write_text(json.dumps({"d": self.quick()}))
        r = self.run_d({"max": 3, "interval_ms": 100, "state": "state.json", "b": {"argv": ["true"]},
                        "procs": {"$ref": "all.json"}, "adopt": {"$ref": "sub/m.json#/n"}})
        self.assertTrue(r.returncode == 1 and r.stderr.startswith("aos-daemon: CfgBad ") and "adopt" in r.stderr, r.stderr)
        r = self.run_d({"max": 3, "interval_ms": 100, "state": "state.json", "b": {"argv": ["true"]},
                        "procs": {"$ref": "all.json"}})
        self.assertEqual((r.returncode, r.stderr, self.upped(r.stdout)), (0, "", ["d"]))

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
            r = self.run_d({"procs": loops, "max": 1})
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, code, 1), (loops, r.stderr))
            self.assertEqual(list(self.s.iterdir()), [], loops)   # 沒起任何子項

    def test_ctl_procs_added_removed(self):
        # 期望表＝（loops_ctl 的 loops，沒寫＝daemon.json 的）＋procs_added－procs_removed；整份 loops_ctl 就是期望（N-06），
        # 拿掉 procs_added 就回 daemon.json 的名單（加進來的收掉）
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        a1 = k["a"]["pid"]
        self.lctl({"procs_added": {"b": self.long()}})
        k = until(lambda: (self.s / "procs" / "b" / "starts").exists() and set(self.kids()) == {"a", "b"} and self.kids())
        self.assertEqual((k["a"]["pid"], k["b"]["phase"]), (a1, "running"))
        b1 = k["b"]["pid"]
        self.lctl({"procs_added": {"b": self.long()}, "procs_removed": ["a", "nobody"]})
        k = until(lambda: list(self.kids()) == ["b"] and self.kids())
        self.assertEqual((k["b"]["pid"], alive(a1)), (b1, False))
        self.lctl({"seq": 1})   # 沒寫 procs_added／procs_removed＝回 daemon.json 的名單：a 重新起、b 收掉
        k = until(lambda: list(self.kids()) == ["a"] and self.kids()["a"]["pid"] != a1 and self.kids())
        self.assertTrue(k)
        self.assertFalse(until(lambda: alive(b1), secs=1))
        a2 = k["a"]["pid"]
        # 跟 ctl 的 loops 一起寫：相對 ctl 的 loops 加減；同一個名字兩邊都寫＝不要（先加後減）
        self.lctl({"procs": {"a": self.long(), "c": self.long()}, "procs_added": {"d": self.long(), "e": self.long()},
                   "procs_removed": ["c", "e"]})
        k = until(lambda: set(self.kids()) == {"a", "d"} and (self.s / "procs" / "d" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual((k["a"]["pid"], (self.s / "procs" / "c").exists(), (self.s / "procs" / "e").exists()), (a2, False, False))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual([alive(x["pid"]) for x in k.values()], [False, False])

    def test_ctl_procs_added_bad_and_ref(self):
        # 寫壞＝整份不採用、記 loops_state 的 ctl_warning（N-08）；loops_ctl 裡的相對 $ref 從它的資料夾（$AOS_STACK）算
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        for bad, why in (({"procs_removed": "a"}, "procs_removed"), ({"procs_removed": [1]}, "procs_removed"),
                         ({"procs_added": {"x/y": "long"}}, "資料夾名"),
                         ({"procs_added": [{"b": "long"}]}, "要是 {名字"),
                         ({"procs_added": {"$ref": "nope.json"}}, "指示詞解不開")):
            self.lctl(dict(bad, procs_removed=bad.get("procs_removed", ["a"])))
            st = until(lambda: why in (self.lstate()["ctl_warning"] or "") and self.lstate())
            self.assertTrue(st, bad)
            self.assertEqual(list(rows_of(self.s, st)), ["a"], bad)   # 維持上一份好的
        (self.s / "more.json").write_text(json.dumps({"b": "long"}))
        (self.s / "w").mkdir()
        (self.s / "w" / "more2.json").write_text(json.dumps({"c": "long"}))
        self.lctl({"procs_added": {"$ref": ["more.json", "w/more2.json"]}})
        k = until(lambda: (self.s / "procs" / "c" / "starts").exists() and set(self.kids()) == {"a", "b", "c"} and self.kids())
        self.assertTrue(k)
        self.assertIsNone(self.lstate()["ctl_warning"])
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_state_split(self):
        # loops_state 的 loops 表超過 100 列就切檔：loops＝{"$ref": ["procs_state_procs/<雜湊>.json", …]}，每份最多 100 列。
        # 11-02 起結束的子項不留在表上：要長壽的才看得到 101 列；收工後表空了、loops 變回物件
        names = ["k%03d" % i for i in range(101)]
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {n: ["/bin/sleep", "1000"] for n in names}})
        st = until(lambda: len(rows_of(self.s, self.lstate())) == 101 and self.lstate(), secs=60)
        self.assertTrue(st)
        self.assertEqual(list(st["procs"]), ["$ref"])
        refs = st["procs"]["$ref"]
        self.assertTrue(all(re.fullmatch(r"procs_state_procs/[0-9a-f]{16}\.json", x) for x in refs), refs)
        pages = [json.loads((self.s / x).read_text()) for x in refs]
        self.assertEqual([len(x) for x in pages], [100, 1])
        rows = rows_of(self.s, st)
        self.assertEqual((list(rows), {x["phase"] for x in rows.values()}), (names, {"running"}))
        self.assertEqual(directive(st, self.s)["procs"], rows)   # 讀 loops_state 的人用 aos-directive 解就拿回整張表
        left = sorted(x.name for x in (self.s / "procs_state_procs").iterdir())
        self.assertTrue(set(x.split("/")[1] for x in refs) <= set(left) and len(left) <= 4, left)   # 只留這次與上一次的
        self.assertFalse(any(x.startswith(".") for x in left), left)
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=60)
        self.assertEqual((p.returncode, err, self.lstate()["procs"], len(self.ended(out))), (0, "", {}, 101))
        # 子項名字跟分檔資料夾同名也照起（11-02 拿掉撞名：小格在 procs/<名字>/，分檔資料夾在頂層）
        (self.s / "procs_state.json").unlink()
        r = self.run_d({"state": "state.json", "max": 3, "interval_ms": 100, "b": {"argv": ["true"]},
                        "procs": {"procs_state_procs": self.quick()}})
        self.assertEqual((r.returncode, r.stderr, (self.s / "procs" / "procs_state_procs" / "loop.json").exists()), (0, "", True))

    def test_state_split_adopt_and_shrink(self):
        # 切了檔的 loops_state 照樣接回；名單縮回 100 以內，loops 變回物件、分檔清掉
        names = ["k%03d" % i for i in range(101)]
        doc = {"state": "state.json", "ctl": "ctl.json", "procs": {n: ["/bin/sleep", "1000"] for n in names}}
        p = self.start(doc)
        k = until(lambda: len(self.kids()) == 101 and all(r["phase"] == "running" for r in self.kids().values())
                  and self.kids(), secs=60)
        self.assertTrue(k)
        self.assertEqual(list(self.lstate()["procs"]), ["$ref"])
        p.kill()
        p.wait()
        p2 = self.start()
        time.sleep(1.5)
        k2 = self.kids()
        self.assertEqual({n: r["pid"] for n, r in k2.items()}, {n: r["pid"] for n, r in k.items()})   # 全部接回、沒重起
        self.lctl({"procs_removed": names[:2]})
        st = until(lambda: "$ref" not in self.lstate()["procs"] and len(self.lstate()["procs"]) == 99 and self.lstate())
        self.assertTrue(st)
        self.assertTrue(until(lambda: not (self.s / "procs_state_procs").exists()))
        self.ctl({"cmd": "stop"})
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
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {
            "a": {"exec": {"argv": ["sh", "-c", self.SHOW]}, "max": 1},
            "b": {"exec": {"argv": ["sh", "-c", 'pwd > "$AOS_STACK/pwd"'], "cwd": "sub"}, "max": 1},
            "c": {"exec": {"argv": ["echo", {"$ref": "data.json#/m"}], "stdout": {"$env": "AOS_STACK", "$path": "out"}}, "max": 1}}})
        self.assertTrue(until(lambda: all((self.s / "procs" / n / f).exists() for n, f in (("a", "seen"), ("b", "pwd"), ("c", "out")))
                              and self.kids() == {}))   # 11-02：結束的不留在表上
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        k = self.ended(out)
        self.assertEqual((p.returncode, err, {n: (r["phase"], r["code"]) for n, r in k.items()}),
                         (0, "", {"a": ("done", 0), "b": ("done", 0), "c": ("done", 0)}))
        real = os.path.realpath(self.t)
        cell = os.path.realpath(self.s / "procs" / "a")
        self.assertEqual((self.s / "procs" / "a" / "seen").read_text(), "%s/loop.json|%s|/exec|%s\n" % (cell, cell, real))
        self.assertEqual((self.s / "procs" / "b" / "pwd").read_text().strip(), real + "/sub")
        self.assertEqual((self.s / "procs" / "c" / "out").read_text(), "hi\n")
        lj = json.loads((self.s / "procs" / "c" / "loop.json").read_text())
        self.assertEqual(lj["exec"]["argv"][1], {"$ref": real + "/data.json#/m"})   # 只轉 $ref 的檔名、不解

    def test_inline_child_via_ctl(self):
        # loops_ctl 半路加的子項，exec 是單子也能跑
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {}})
        until(lambda: self.state())
        self.lctl({"procs_added": {"x": {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"; exit 3']}, "max": 2}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "ran").exists() and "x" not in self.kids()))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        k = self.ended(out)
        self.assertEqual((p.returncode, err, k["x"]["code"], (self.s / "procs" / "x" / "ran").read_text()), (0, "", 3, "x\n"))
        self.assertIn("aos-loop: 第 1 次 loop.json#/exec 失敗，結束碼 3", (self.s / "procs" / "x" / "stderr.txt").read_text())

    # ---- 10-24 審後補：還原、訊號、abs_refs 邊界、收不肯退的單子

    def popen_env(self, extra):
        p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t), env=env_of(extra),
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
        self.cfg({"exec": {"argv": ["true"]}, "interval_ms": 100, "state": "state.json", "ctl": "ctl.json", "procs": {}})
        p = self.popen_env({"AOS_STACK": str(self.s), "AOS_CF": str(self.t / "p1"), "AOS_CD": str(self.t / "pd"), "AOS_CO": "p3"})
        self.assertTrue(until(lambda: self.state()["counter_runs"] >= 1))
        self.lctl({"procs": {"a": {"exec": {"$env": "AOS_CF"}, "max": 1}, "b": {"exec": {"$env": "AOS_CD", "$path": "p2"}, "max": 1},
                             "c": {"exec": {"$env": "AOS_CO"}, "max": 1}}})
        self.assertTrue(until(lambda: all((self.s / "procs" / n / "ran").exists() for n in "abc") and self.kids() == {}))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual({n: r["code"] for n, r in self.ended(out).items()}, {"a": 0, "b": 0, "c": 0})
        self.assertEqual({n: (self.s / "procs" / n / "ran").read_text() for n in "abc"}, {n: "x\n" for n in "abc"})

    # 內嵌單子收的是整群的 SIGTERM，sleep 也被殺；sh（dash／bash）有時會在自己的 stderr 報一行「Terminated」
    # （看時序，10-28 WSL 撞到）——那是測試小程式自己說的、不是被測程式；開頭 exec 2>/dev/null 讓 err 只剩被測程式自己的。
    TRAP = 'exec 2>/dev/null; trap \'echo got > "$AOS_STACK/got"; exit 0\' TERM; touch "$AOS_STACK/up"; while :; do sleep 0.05; done'

    def test_inline_child_sigterm_forwarded(self):
        # daemon 收 SIGTERM → 送給子 loop → 子 loop 轉給它正在跑的內嵌單子（整群）、等它收完再退
        p = self.start({"state": "state.json", "procs": {"a": {"exec": {"argv": ["sh", "-c", self.TRAP]}, "max": 5}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "up").exists()))
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        r = self.ended(out)["a"]
        self.assertEqual((p.returncode, err, (self.s / "procs" / "a" / "got").read_text(), r["phase"], r["code"]), (143, "", "got\n", "sleeping", 143))

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
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": {"exec": unit, "max": 1}}})
        until(lambda: (self.s / "procs" / "a" / "loop.json").exists() and "a" not in self.kids())
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        real = os.path.realpath(self.t)
        x = json.loads((self.s / "procs" / "a" / "loop.json").read_text())["exec"]["x"]
        self.assertEqual(x, [
            {"$ref": "/abs/d.json#/m"}, {"$ref": [real + "/d1.json", real + "/sub/d2.json#/x", "/abs/d3.json"]}, {"$ref": "#/m"},
            {"$ref": 5}, {"$ref": [real + "/d1.json", 7]}, {"$ref": real + "/d.json", "$path": {"$ref": "in.json"}},
            {"deep": {"$ref": real + "/sub/d4.json"}}, {"$env": "HOME"}])

    def test_stubborn_inline_child_killed_with_loop(self):
        # 子 loop 的內嵌單子不理 SIGTERM、grace_ms 又比 daemon 的 10 秒長：滿 10 秒 daemon SIGKILL 子 loop 那群時，
        # 單子（inst 起的、自成一群）也一起收掉，不留孤兒（10-24 審後補；原本整群打不到它）
        body = 'trap "" TERM; echo $$ > "$AOS_STACK/pid"; while :; do sleep 0.05; done'
        p = self.start({"state": "state.json", "procs": {"a": {"exec": {"argv": ["sh", "-c", body], "grace_ms": 60000}, "max": 1}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "pid").read_text().strip()))
        pid = int((self.s / "procs" / "a" / "pid").read_text())
        self.addCleanup(lambda: alive(pid) and os.killpg(pid, signal.SIGKILL))
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (143, ""))
        self.assertGreater(time.monotonic() - t0, 9)
        self.assertTrue(until(lambda: not alive(pid), 3), "單子留成孤兒")

    # ───── H. 10-29 拆窗（medium-plan § 四、實作步驟 1）：ctl.json／state.json 管 loop 面向，procs_ctl.json／procs_state.json 管名單 ─────

    def test_old_keys_ignored(self):
        # 11-03（使用者「1. 當沒看到。」，C-48）：舊名 loops、execs、loops_ctl、loops_state、loops_ctl_mailbox，procs_ctl／信的 loops_added／execs_added，
        # ctl.json 的 loops*／procs*——一律當不認得的 key：不起、不報錯、不提醒（10-29 的「已搬到 loops_ctl.json」過渡提醒拿掉）
        (self.s / "loops_ctl.json").write_text(json.dumps({"loops_added": {"y": self.long()}}))
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs_ctl_mailbox": "box", "loops_ctl_mailbox": "box2",
                        "loops": {"a": self.long()}, "execs": {"e": "long"}, "loops_state": "ls.json", "loops_ctl": "lc.json"})
        self.assertTrue(until(lambda: self.lstate() and self.state()))
        self.ctl({"loops_added": {"b": self.long()}, "procs_added": {"b": self.long()}, "seq": 1})
        self.lctl({"loops_added": {"c": self.long()}, "execs": {"d": "long"}, "seq": 2})
        self.post("0001", {"loops_added": {"f": self.long()}, "execs_added": {"g": "long"}})
        self.assertTrue(until(lambda: self.state()["ctl_seq"] == 1 and self.lstate()["ctl_seq"] == 2 and self.drained()))
        time.sleep(0.6)
        st, ls = self.state(), self.lstate()
        self.assertEqual((st["ctl_warning"], ls["ctl_warning"], ls["mailbox_warning"], ls["procs"]), (None, None, None, {}))
        self.assertEqual(sorted(x.name for x in self.s.iterdir()),
                         ["box", "ctl.json", "loops_ctl.json", "procs_ctl.json", "procs_state.json", "state.json"])   # 沒有小格、ls.json、box2
        self.mstop(p)

    def test_both_ctls_same_cycle(self):
        # 同一圈 ctl.json 改 interval_ms、procs_ctl.json 加子項：兩邊都生效，各自回自己的 seq
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 300, "procs": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids()))
        self.lctl({"procs_added": {"b": self.long()}, "seq": 3})
        self.ctl({"interval_ms": 50, "seq": 7})
        self.assertTrue(until(lambda: (self.s / "procs" / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        st = until(lambda: self.state()["interval_ms"] == 50 and self.state())
        self.assertTrue(st)
        ls = self.lstate()
        self.assertEqual((st["ctl_seq"], st["ctl_warning"], ls["ctl_seq"], ls["ctl_warning"]), (7, None, 3, None))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_bad_ctl_good_loops_ctl(self):
        # ctl.json 壞、procs_ctl.json 好：只有 state.json 有 ctl_warning，名單照 loops_ctl 改
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids()))
        self.ctl("{not json")
        self.lctl({"procs_added": {"b": self.long()}, "seq": 1})
        self.assertTrue(until(lambda: (self.s / "procs" / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        self.assertTrue(until(lambda: "不是 JSON" in (self.state()["ctl_warning"] or "")))
        self.assertEqual((self.lstate()["ctl_seq"], self.lstate()["ctl_warning"]), (1, None))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_paused_holds_loops_ctl(self):
        # ctl.json paused＝整圈暫停：loops_ctl 的變動不生效（照讀、ctl_seq 照回），兩扇 state 照寫；解除暫停那圈才生效
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        self.ctl({"cmd": "pause", "seq": 1})
        self.assertTrue(until(lambda: self.state()["phase"] == "paused"))
        self.lctl({"procs_added": {"b": self.long()}, "procs_removed": ["a"], "seq": 2})
        ls = until(lambda: self.lstate()["ctl_seq"] == 2 and self.lstate())
        self.assertTrue(ls)
        time.sleep(1.5)
        ls2 = self.lstate()
        self.assertEqual(ls2["updated_at"], ls["updated_at"])   # 暫停中照讀 loops_ctl、seq 變了寫一次；之後沒變就不寫（11-02）
        self.assertEqual((list(ls2["procs"]), ls2["procs"]["a"]["phase"], alive(k["a"]["pid"]), (self.s / "procs" / "b").exists()),
                         (["a"], "running", True, False))
        self.ctl({"cmd": "resume", "seq": 3})   # 解除暫停：b 起、a 收掉
        self.assertTrue(until(lambda: (self.s / "procs" / "b" / "starts").exists() and list(self.kids()) == ["b"]))
        self.assertFalse(alive(k["a"]["pid"]))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_loops_windows_null_and_bad(self):
        # procs_state／procs_ctl 寫 null＝不開：不寫 procs_state.json、不讀 procs_ctl.json（11-02 起子項同名本來就不撞：小格在 procs/）
        (self.s / "procs_ctl.json").write_text(json.dumps({"procs_added": {"x": self.quick()}}))
        r = self.run_d({"state": "state.json", "procs_state": None, "procs_ctl": None, "max": 3, "interval_ms": 100,
                        "b": {"argv": ["true"]}, "procs": {"procs_state.json": self.quick()}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(((self.s / "procs" / "procs_state.json" / "loop.json").exists(), (self.s / "procs" / "x").exists(),
                          (self.s / ".procs_state.json").exists(), "procs" in self.state()), (True, False, False, False))
        # 檔名可以改、指示詞照解（這裡指到 stack 裡不在的資料夾＝寫不了）；型別不對＝CfgBad
        (self.t / "names.json").write_text(json.dumps({"ls": "w/ls.json"}))
        r = self.run_d({"procs_state": {"$ref": "names.json#/ls"}, "max": 1})
        self.assertEqual((r.returncode, r.stderr.split(" ")[1], "w/.ls.json" in r.stderr), (1, "WriteFailed", True), r.stderr)
        for bad in (3, "", ["a"]):
            for k in ("procs_ctl", "procs_state"):
                r = self.run_d({k: bad, "max": 1})
                self.assertEqual((r.returncode, r.stderr.split(" ")[1], k in r.stderr), (1, "CfgBad", True), (k, bad, r.stderr))

    def test_child_name_same_as_loops_windows(self):
        # 跟 procs_ctl.json、procs_state.json、分檔資料夾（改了名的也一樣）同名的子項照起（11-02 拿掉 10-22 的撞名；小格在 procs/<名字>/）
        for win, name in (({}, "procs_ctl.json"), ({}, "procs_state.json"), ({}, "procs_state_procs"),
                          ({"procs_ctl": "lc/x.json"}, "lc"), ({"procs_state": "ls.json"}, "ls_procs")):
            r = self.run_d(dict(win, procs={name: self.quick()}, b={"argv": ["true"]}, max=3, interval_ms=100))
            self.assertEqual((r.returncode, r.stderr, (self.s / "procs" / name / "loop.json").exists()), (0, "", True), (win, name))
        self.assertTrue((self.s / "procs_state.json").is_file() and (self.s / "ls.json").is_file())
        # state.json 不再有 loops 表，原本的 state_loops 就只是普通名字
        r = self.run_d({"state": "state.json", "procs": {"state_loops": self.quick()}, "b": {"argv": ["true"]}, "max": 3,
                        "interval_ms": 100})
        self.assertEqual((r.returncode, r.stderr, (self.s / "procs" / "state_loops" / "loop.json").exists()), (0, "", True))

    # ───── I. 10-29 信箱模式（medium-plan § 四 3、實作步驟 5）：daemon.json 寫 procs_ctl_mailbox（11-02 晚原 loops_mailbox），名單的增減改成一封封信 ─────

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
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs_ctl_mailbox": "box", "procs": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids()))
        return p

    def pause(self, seq):
        self.ctl({"cmd": "pause", "seq": seq})
        self.assertTrue(until(lambda: self.state()["phase"] == "paused" and self.state()["ctl_seq"] == seq))

    def mstop(self, p):
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))

    def test_mailbox_same_cycle_later_name_wins_and_paused_holds(self):
        # 兩個寄信人同一圈各一封（一加 bob、一刪 bob）：照名字順序套，後面的贏。paused＝信留在 new/ 不認領，解除那圈才套
        p = self.mstart()
        self.assertEqual((sorted(x.name for x in self.box().iterdir()), (self.s / "procs_ctl.json").exists()),
                         (["cur", "new", "tmp"], False))
        self.pause(1)
        self.post("0001", {"procs_added": {"bob": self.long()}})
        self.post("0002", {"procs_removed": ["bob"]})
        time.sleep(1)
        self.assertEqual((sorted(x.name for x in (self.box() / "new").iterdir()), (self.s / "procs" / "bob").exists()),
                         (["0001", "0002"], False))
        self.ctl({"cmd": "resume", "seq": 2})   # 解除暫停：同一圈認領兩封，加了又刪＝bob 沒起
        self.assertTrue(until(self.drained))
        time.sleep(0.6)
        self.assertEqual((list(self.kids()), (self.s / "procs" / "bob").exists()), (["a"], False))
        self.pause(3)
        self.post("0003", {"procs_removed": ["bob"]})   # 反過來：先刪後加＝bob 起
        self.post("0004", {"procs_added": {"bob": self.long()}})
        self.ctl({"cmd": "resume", "seq": 4})
        self.assertTrue(until(lambda: (self.s / "procs" / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        self.assertEqual(((self.box() / "done").exists(), self.lstate()["mailbox_warning"]), (False, None))   # 預設收掉、不留 done/
        self.mstop(p)

    def test_mailbox_adopted_stays_until_removed(self):
        # 方向題 1：重起後 adopt 接回的（daemon.json 沒有的）留在名單上，直到有信 procs_removed 它
        p = self.mstart()
        self.post("0001", {"procs_added": {"bob": self.long()}})
        k = until(lambda: (self.s / "procs" / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"} and self.kids())
        self.assertTrue(k)
        bob = k["bob"]["pid"]
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        time.sleep(1.5)
        k2 = self.kids()
        self.assertEqual((set(k2), k2["bob"]["pid"], k2["bob"]["phase"], alive(bob),
                          len((self.s / "procs" / "bob" / "starts").read_text().split())), ({"a", "bob"}, bob, "running", True, 1))
        self.post("0002", {"procs_removed": ["bob"]})
        self.assertTrue(until(lambda: list(self.kids()) == ["a"]))
        self.assertFalse(alive(bob))
        self.mstop(p2)

    def test_mailbox_bad_letters_dont_block_good(self):
        # 壞信丟掉、不影響同一圈的好信；mailbox_warning（11-02 晚原 letter_warning）＝最後一封壞信的原因（沒有壞信的圈維持原值）；壞信有 reply_to 也不回（決定 27）
        rb = self.reply_box()
        p = self.mstart()
        self.pause(1)
        self.post("0001", [1], reply_to=rb)                                   # body 不是物件
        self.post("0002", {"procs_added": {"x/y": self.long()}})              # 名字含 /（11-02 前這裡是跟信箱撞名的 box）
        self.post("0003", {"procs_added": {"bob": self.long()}, "x": 1})      # 好信（不認得的 key 忽略）
        self.post("0004", {"procs_removed": "bob"})                           # 型別錯
        self.post("0005", None, raw="{not json")                              # letter.json 壞
        self.ctl({"cmd": "resume", "seq": 2})
        self.assertTrue(until(lambda: (self.s / "procs" / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        w = until(lambda: self.lstate()["mailbox_warning"])
        self.assertTrue(w and w.startswith("信 0005 不採用：") and "letter.json" in w, w)
        self.assertEqual(list((rb / "new").iterdir()), [])
        self.post("0006", {"procs_removed": ["bob"]})   # 只有好信的圈：mailbox_warning 維持
        self.assertTrue(until(lambda: list(self.kids()) == ["a"]))
        self.assertEqual(self.lstate()["mailbox_warning"], w)
        self.mstop(p)

    def test_mailbox_reply_to_applied(self):
        # 寫了 reply_to 的好信：對完表才回一封 body {"applied": true}、in_reply_to＝原信號；沒寫 reply_to 的不回
        rb = self.reply_box()
        p = self.mstart()
        self.post("0001", {"procs_added": {"bob": self.long()}}, reply_to=rb)
        self.post("0002", {"procs_added": {"carl": self.long()}})
        got = until(lambda: list((rb / "new").iterdir()))
        self.assertTrue(got)
        self.assertTrue((self.s / "procs" / "bob" / "loop.json").exists())
        time.sleep(0.6)
        self.assertEqual(len(list((rb / "new").iterdir())), 1)
        r = json.loads((got[0] / "letter.json").read_text())
        self.assertEqual((r["kind"], r["in_reply_to"], r["body"]), ("letter", "0001", {"applied": True}))
        self.mstop(p)

    def test_mailbox_cfg_rules(self):
        # procs_ctl_mailbox（11-03 前 loops_ctl_mailbox）；跟 procs_ctl 可以同時開（沒寫 procs_ctl＝預設 procs_ctl.json 照開、照讀），寫 null＝不開；
        # 型別錯＝CfgBad；舊名 loops_ctl_mailbox 不認（其他 key 忽略：不開信箱）
        for doc in ({"procs_ctl_mailbox": 3}, {"procs_ctl_mailbox": ""}, {"procs_ctl_mailbox": ["box"]}):
            r = self.run_d(dict(doc, max=1))
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, "CfgBad", 1), (doc, r.stderr))
            self.assertFalse((self.s / "box").exists(), doc)
        (self.s / "procs_ctl.json").write_text(json.dumps({"procs_added": {"x": self.quick()}}))
        for lc, ran in (({}, True), ({"procs_ctl": None}, False)):
            shutil.rmtree(self.s / "procs", ignore_errors=True)
            r = self.run_d(dict(lc, procs_ctl_mailbox="box", b={"argv": ["true"]}, state="state.json", max=3, interval_ms=100))
            self.assertEqual((r.returncode, r.stderr, (self.s / "procs" / "x").exists(), (self.box() / "new").is_dir()),
                             (0, "", ran, True), lc)
        shutil.rmtree(self.box())
        r = self.run_d({"loops_ctl_mailbox": "box", "procs_ctl": None, "max": 1})
        self.assertEqual((r.returncode, r.stderr, self.box().exists(), "mailbox_warning" in self.lstate()), (0, "", False, False))
        r = self.run_d({"procs_ctl_mailbox": None, "procs_ctl": None, "b": {"argv": ["true"]}, "procs": {"y": self.quick()}, "max": 3,
                        "interval_ms": 100})   # 兩個都不開＝名單只看 daemon.json
        self.assertEqual((r.returncode, r.stderr, list(self.ended(r.stdout))), (0, "", ["y"]))
        # $AOS_STACK 不在＝不替人建（信箱的 init 是 mkdir -p）
        gone = self.t / "no" / "stack"
        r = self.run_d({"procs_ctl_mailbox": "box", "procs_state": None, "max": 1}, env={"AOS_STACK": str(gone)})
        self.assertEqual((r.returncode, r.stderr.split(" ")[1], gone.exists()), (1, "MkdirFailed", False), r.stderr)

    def test_mailbox_cur_leftovers_redone_first(self):
        # 起來時 cur/ 不空（上次認領了、沒收完就死）：當成這圈認領到的，排在 new/ 前面重做
        for x in ("tmp", "new", "cur"):
            (self.box() / x).mkdir(parents=True)
        self.post("0009", {"procs_added": {"bob": self.long(), "carl": self.long()}})
        os.rename(self.box() / "new" / "0009", self.box() / "cur" / "0009")
        self.post("0001", {"procs_removed": ["carl"]})   # 名字排前面，但在 new/：排在 cur/ 的後面＝carl 被刪
        p = self.mstart()
        self.assertTrue(until(lambda: (self.s / "procs" / "bob" / "starts").exists() and set(self.kids()) == {"a", "bob"}))
        self.assertTrue(until(self.drained))
        time.sleep(0.6)
        self.assertEqual((set(self.kids()), (self.s / "procs" / "carl").exists()), ({"a", "bob"}, False))
        self.mstop(p)

    # ───── J. 10-30 exec 型子項 execs（thinking 2026-10-30-agent-lifecycle B-12 ②、實作步驟 7）：直接 aos-exec 一次、不包 aos-loop ─────

    JOB = ('echo "$*" >> "$AOS_STACK/runs"\necho "$AOS_STACK" > "$AOS_STACK/stack.txt"\ncat > "$AOS_STACK/stdin.txt"\n'
           'echo "$$ $(cut -d" " -f5 /proc/$$/stat)" > "$AOS_STACK/ids"\necho "job 的 stderr" >&2\nexit 3\n')

    def prog(self, name, body):
        d = self.t / name
        d.mkdir()
        (d / "_entry").write_text("#!/bin/sh\n" + body)
        (d / "_entry").chmod(0o755)

    def test_execs_once_done_not_restarted(self):
        # 字串、[目標, 參數...]、{"exec": 目標}（11-03 起多一個 key＝loop 設定）三種寫法；各跑一次、退 3＝done／code 3、不重起；
        # 小格裡沒有 loop.json／ctl.json／state.json；AOS_STACK＝小格/、stdin /dev/null、stderr 進小格的 stderr.txt、自成群組（pgrp＝pid）
        self.prog("job", self.JOB)
        r = self.run_d({"state": "state.json", "max": 15, "interval_ms": 100,
                        "procs": {"j": "job", "k": ["job", "a", "b"], "o": {"exec": ["job", "c"]}}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        self.assertEqual(st["procs"], {})   # 11-02：結束後不留在表上
        self.assertEqual(self.upped(r.stdout), ["j", "k", "o"])   # 各起一次、不重起
        x = self.ended(r.stdout)
        self.assertEqual({n: (r["phase"], r["code"], r["signal"]) for n, r in x.items()},
                         {n: ("done", 3, None) for n in "jko"})
        self.assertEqual({tuple(r) for r in x.values()}, {("at", "name", "phase", "pid", "code", "signal")})
        for n, args in (("j", ""), ("k", "a b"), ("o", "c")):
            cell = self.s / "procs" / n
            self.assertEqual((cell / "runs").read_text(), args + "\n", n)   # 只跑一次
            self.assertEqual(sorted(f.name for f in cell.iterdir()), ["ids", "runs", "stack.txt", "stderr.txt", "stdin.txt"], n)
            self.assertEqual(((cell / "stack.txt").read_text(), (cell / "stdin.txt").read_text()), (str(cell) + "/\n", ""), n)
            self.assertEqual((cell / "stderr.txt").read_text(), "job 的 stderr\n", n)
            pid, pgrp = (cell / "ids").read_text().split()
            self.assertEqual((int(pid), int(pgrp)), (x[n]["pid"], x[n]["pid"]), n)   # 那支程式就是表上的 pid（中間沒有 aos-loop）

    def test_procs_removed_sigterm_then_kill_group(self):
        # procs_removed：SIGTERM 直接打那支程式（a 退了就拿掉）；不理的（b）10 秒後 SIGKILL 整群（連它的 sleep）
        self.prog("stub", 'trap "" TERM\nsleep 1000 &\necho "$$ $!" > "$AOS_STACK/pids"\nwhile :; do sleep 0.05; done\n')
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": "long", "b": "stub"}})
        x = until(lambda: (self.s / "procs" / "a" / "starts").exists() and (self.s / "procs" / "b" / "pids").exists() and len(self.kids()) == 2
                  and self.kids())
        self.assertTrue(x)
        self.assertIn("long/_entry", Path("/proc/%d/cmdline" % x["a"]["pid"]).read_text())   # 就是那支程式、不是 aos-loop
        bpid, bsleep = map(int, (self.s / "procs" / "b" / "pids").read_text().split())
        self.addCleanup(lambda: alive(bsleep) and os.kill(bsleep, signal.SIGKILL))
        self.assertEqual(bpid, x["b"]["pid"])
        t0 = time.monotonic()
        self.lctl({"procs_removed": ["a", "b"], "seq": 1})
        self.assertTrue(until(lambda: list(self.kids()) == ["b"] and self.kids()["b"]["phase"] == "stopping", 5))
        self.assertLess(time.monotonic() - t0, 5)
        self.assertFalse(alive(x["a"]["pid"]))
        self.assertTrue(until(lambda: self.kids() == {}, 20))
        self.assertGreater(time.monotonic() - t0, 9)
        self.assertEqual((alive(bpid), alive(bsleep)), (False, False))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))

    def test_procs_cfg_rules_and_same_name_rewrite(self):
        # daemon.json：寫法不合＝CfgBad 退 1、一行、不建小格；exec 型的物件（只有 exec＋ws／stack）的 exec 也要是目標或單子。
        # 11-03：沒有 exec 的物件＝loop 設定（交給子 loop 退 1，procs § 2 第 4 條），不是 daemon 的錯
        for doc in ({"procs": [1]}, {"procs": {"a": 3}}, {"procs": {"a": []}}, {"procs": {"a": ["long", 1]}}, {"procs": {"a/b": "long"}},
                    {"procs": {"a": {"exec": 3}}}, {"procs": {"a": {"exec": None, "ws": "."}}}, {"procs": {"a": {"exec": "long", "ws": 3}}}):
            r = self.run_d(dict(doc, max=1))
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], r.stderr.count("\n")), (1, "CfgBad", 1), (doc, r.stderr))
            self.assertFalse((self.s / "procs" / "a").exists(), doc)
        r = self.run_d({"procs": {"a": {"max": 1}}, "max": 3, "interval_ms": 100})
        self.assertEqual((r.returncode, r.stderr, self.ended(r.stdout)["a"]["code"]), (0, "", 1))
        # 同名改寫法（loop 型→exec 型）：已在跑的不重起（N-54；10-30「種類不一樣＝收掉重起」11-03 拿掉）；被拿掉再放回才照新寫法
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"a": self.long()}})
        k = until(lambda: (self.s / "procs" / "a" / "starts").exists() and self.kids())
        self.lctl({"procs_added": {"a": "long"}, "seq": 1})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 1))
        time.sleep(0.6)
        self.assertEqual((self.kids()["a"]["pid"], alive(k["a"]["pid"]), self.lstate()["ctl_warning"]), (k["a"]["pid"], True, None))
        self.lctl({"procs_removed": ["a"], "seq": 2})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 2 and self.kids() == {}))
        self.lctl({"procs_added": {"a": "long"}, "seq": 3})
        x = until(lambda: "a" in self.kids() and self.kids()["a"]["pid"] != k["a"]["pid"] and self.kids())
        self.assertTrue(x)
        self.assertTrue(until(lambda: len((self.s / "procs" / "a" / "starts").read_text().split()) == 2))
        self.assertIn("long/_entry", Path("/proc/%d/cmdline" % x["a"]["pid"]).read_text())   # exec 型：就是那支程式
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.upped(out), alive(x["a"]["pid"])), (0, "", ["a", "a"], False))

    def test_execs_adopt(self):
        # adopt：exec 型子項也接回、不重起；收工時照收
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"l": self.long(), "a": "long"}})
        x = until(lambda: (self.s / "procs" / "a" / "starts").exists() and (self.s / "procs" / "l" / "starts").exists() and self.kids()
                  and self.kids() and self.kids())
        self.assertTrue(x)
        pid, lpid = x["a"]["pid"], self.kids()["l"]["pid"]
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        time.sleep(1)
        self.assertEqual((self.kids()["a"]["pid"], self.kids()["l"]["pid"], len((self.s / "procs" / "a" / "starts").read_text().split())),
                         (pid, lpid, 1))
        self.ctl({"cmd": "stop"})
        out, err = p2.communicate(timeout=30)
        e = self.ended(out)["a"]
        self.assertEqual((p2.returncode, err, e["phase"], e["pid"], alive(pid), alive(lpid)), (0, "", "stopped", pid, False, False))
        # 接回的也印起來那一行；不是自己的子行程（拿不到結束碼），結束那行 code／signal 是 null
        self.assertEqual((self.upped(out), e["code"], e["signal"]), (["l", "a"], None, None))

    def test_max1_loop_still_runs_beside_execs(self):
        # ①（使用者 10-30「包成max:1也是可以」）：{"exec": X, "max": 1} 的 loop 型照舊——小格有 loop.json／ctl／state；
        # 同一份名單裡的 exec 型（字串）小格沒有 loop.json（11-03 看寫法決定怎麼起）
        self.prog("job", self.JOB)
        r = self.run_d({"state": "state.json", "max": 15, "interval_ms": 100,
                        "procs": {"bob": {"exec": "job", "max": 1}, "carl": "job"}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual({n: (r["phase"], r["code"]) for n, r in self.ended(r.stdout).items()},
                         {"bob": ("done", 3), "carl": ("done", 3)})
        self.assertEqual(((self.s / "procs" / "bob" / "runs").read_text(), (self.s / "procs" / "carl" / "runs").read_text()), ("\n", "\n"))
        self.assertTrue(all((self.s / "procs" / "bob" / f).is_file() for f in ("loop.json", "state.json")))
        self.assertFalse((self.s / "procs" / "carl" / "loop.json").exists())
        self.assertIn("aos-loop: 第 1 次", (self.s / "procs" / "bob" / "stderr.txt").read_text())   # 多一層 aos-loop：它自己的那行

    def test_execs_mailbox(self):
        # 信的 procs_added 收 exec 型；11-02：結束（done）的不留在表上、從期望表拿掉（不重起）；之後再有信同名 procs_added＝重新起。
        # 11-03：procs_stopped／procs_started 裡有 exec 型＝壞信（exec 型只有跑和拔）、mailbox_warning、有 reply_to 也不回
        self.prog("job", self.JOB)
        rb = self.reply_box()
        p = self.mstart()
        self.post("0001", {"procs_added": {"j": "job", "e": "long"}})
        self.assertTrue(until(lambda: (self.s / "procs" / "j" / "runs").exists() and set(self.kids()) == {"a", "e"}))
        time.sleep(0.6)
        self.assertEqual(((self.s / "procs" / "j" / "runs").read_text(), set(self.kids())), ("\n", {"a", "e"}))   # 不重起
        for i, body in enumerate(({"procs_stopped": ["e"]}, {"procs_started": ["e"]}, {"procs_added": {"x": "long"}, "procs_stopped": ["x"]})):
            self.post("000%d" % (i + 2), body, reply_to=rb)
            w = until(lambda: (self.lstate()["mailbox_warning"] or "").startswith("信 000%d 不採用：" % (i + 2)) and self.lstate()["mailbox_warning"])
            self.assertTrue(w and "exec 型" in w, (body, w))
        self.assertEqual((set(self.kids()), {r["phase"] for r in self.kids().values()}, list((rb / "new").iterdir())), ({"a", "e"}, {"running"}, []))
        self.post("0009", {"procs_added": {"j": "job"}})   # 同名再加＝重新起（不用先 procs_removed）
        self.assertTrue(until(lambda: (self.s / "procs" / "j" / "runs").read_text() == "\n\n" and "j" not in self.kids()))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, [n for n in self.upped(out) if n == "j"], [x["code"] for x in self.logs(out) if x["name"] == "j"]),
                         (0, "", ["j", "j"], [None, 3, None, 3]))

    def test_execs_state_split(self):
        # exec 型、loop 型同一張表，超過 100 列一樣切檔（11-02：結束的不留，要長壽的才看得到 101 列）
        names = ["x%03d" % i for i in range(101)]
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": dict({"l": self.long()}, **{n: ["/bin/sleep", "1000"] for n in names})})
        st = until(lambda: len(rows_of(self.s, self.lstate())) == 102 and self.lstate(), secs=60)
        self.assertTrue(st)
        self.assertEqual(list(st["procs"]), ["$ref"])
        self.assertTrue(all(re.fullmatch(r"procs_state_procs/[0-9a-f]{16}\.json", x) for x in st["procs"]["$ref"]))
        rows = rows_of(self.s, st)
        self.assertEqual((list(rows), {x["phase"] for x in rows.values()}), (["l"] + names, {"running"}))
        self.assertEqual(directive(st, self.s)["procs"], rows)
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=60)
        # 收工：exec 型照舊拿掉，loop 型 l 留成 sleeping（11-03）
        self.assertEqual((p.returncode, err, {n: r["phase"] for n, r in self.lstate()["procs"].items()}, len(self.ended(out))), (0, "", {"l": "sleeping"}, 102))

    # ───── L. 11-02：log（stdout；11-02 晚預設不印、--enable-logs 才印）、子項結束後不留名單、窗有變才寫 ─────

    def test_log_off_and_no_body_quiet(self):
        # 沒給 --enable-logs：什麼都不印；沒有身體的 daemon 不印每圈的行（只有子項的起、退）；有身體的每跑完一次一行（同 aos-loop）
        r = self.run_d({"max": 5, "interval_ms": 0})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        r = self.run_d({"max": 3, "interval_ms": 100, "b": {"argv": ["true"]}, "procs": {"a": self.quick()}}, log=False)
        self.assertEqual((r.returncode, r.stdout, r.stderr, (self.s / "procs" / "a" / "loop.json").exists()), (0, "", "", True))
        r = self.run_d({"exec": {"argv": ["true"]}, "max": 2, "interval_ms": 0})
        lines = [json.loads(x) for x in r.stdout.splitlines()]
        self.assertEqual((r.returncode, [list(x) for x in lines], [x["counter_runs"] for x in lines]),
                         (0, [["started_at", "counter_runs", "code", "signal", "elapsed_ms"]] * 2, [1, 2]))

    def test_log_ws_field(self):
        # 子項給了 ws：log 兩行都帶 ws（最後一欄）
        (self.t / "w").mkdir()
        r = self.run_d({"max": 3, "interval_ms": 100, "b": {"argv": ["true"]},
                        "procs": {"a": dict(self.quick(), ws="w")}})
        lines = self.logs(r.stdout)
        self.assertEqual((r.returncode, [(x["phase"], list(x)[-1], x["ws"]) for x in lines]),
                         (0, [("running", "ws", str(self.t / "w")), ("done", "ws", str(self.t / "w"))]))

    def test_ctl_done_child_not_restarted_until_list_drops_it(self):
        # ctl 模式：自己結束的子項本次執行不再起（名單照舊有它）；某一圈名單裡沒有它了（daemon 看過，ctl_seq 回音），
        # 之後名單再有它就照常起
        p = self.start({"state": "state.json", "ctl": "ctl.json", "interval_ms": 50, "b": {"argv": ["true"]}, "procs": {}})
        self.assertTrue(until(lambda: self.lstate()))
        self.lctl({"procs_added": {"x": self.quick()}, "seq": 1})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "loop.json").exists() and self.lstate()["ctl_seq"] == 1 and self.kids() == {}))
        time.sleep(0.6)
        self.assertEqual(self.kids(), {})   # 名單上還有 x：不重起
        self.lctl({"seq": 2})               # 名單裡沒有 x 了
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 2))
        self.lctl({"procs_added": {"x": self.quick()}, "seq": 3})   # 再放回＝照常起
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 3))
        time.sleep(0.6)
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.upped(out), [x["phase"] for x in self.logs(out)]),
                         (0, "", ["x", "x"], ["running", "done", "running", "done"]))

    def test_mailbox_done_child_readded(self):
        # 信箱模式：自己結束的子 loop 從表上、期望表拿掉（不重起）；同名再寄一封 procs_added＝重新起（不用先 rm、先 procs_removed）
        p = self.mstart()
        self.post("0001", {"procs_added": {"x": {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"']}, "max": 1}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "ran").exists() and set(self.kids()) == {"a"}))
        time.sleep(0.6)
        self.assertEqual(((self.s / "procs" / "x" / "ran").read_text(), set(self.kids())), ("x\n", {"a"}))
        self.post("0002", {"procs_added": {"x": {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"']}, "max": 1}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "ran").read_text() == "x\nx\n" and set(self.kids()) == {"a"}))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.upped(out), {n: r["phase"] for n, r in self.ended(out).items()}),
                         (0, "", ["a", "x", "x"], {"x": "done", "a": "sleeping"}))

    def test_closed_stdout_keeps_running(self):
        # stdout 是關掉的管子：log 印不了就靜靜停掉，daemon 照跑、照起子項（不被 SIGPIPE 打死）
        self.cfg({"state": "state.json", "max": 4, "interval_ms": 100, "b": {"argv": ["true"]}, "procs": {"a": self.quick()}})
        p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.procs.append(p)
        p.stdout.close()
        err = p.communicate(timeout=30)[1]
        self.assertEqual((p.returncode, err, self.state()["phase"], (self.s / "procs" / "a" / "loop.json").exists()), (0, b"", "done", True))


    # ───── K. 10-30 eca 子項的工作區 ws（thinking 2026-10-30-eca 衝突 1、實作步驟 1；N-28／N-54 補草稿）─────

    def test_ws_mailbox_change_and_adopt(self):
        # 信的 procs_added 帶相對 ws＝從 daemon 的 cwd 算；名單改了 ws＝設定變了、已在跑的不重起（N-54），列上仍是起它時的；
        # 重起 adopt 接回時列上的 ws 照留；ws 型別錯＝壞信
        for n in ("w1", "w2", "w3"):
            (self.t / "rel" / n).mkdir(parents=True)
        self.prog("lw", 'printf %s "$AOS_WS" > "$AOS_STACK/ws"\nwhile :; do sleep 0.05; done\n')
        p = self.mstart()
        self.post("0001", {"procs_added": {"b": {"exec": "lw", "max": 1, "ws": "rel/w1"}, "x": {"exec": "lw", "ws": "./rel/w2"}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "b" / "ws").exists() and (self.s / "procs" / "x" / "ws").exists()
                              and len(self.kids()) == 3))
        w1, w2 = str(self.t / "rel" / "w1"), str(self.t / "rel" / "w2")
        self.assertEqual(((self.s / "procs" / "b" / "ws").read_text(), (self.s / "procs" / "x" / "ws").read_text()), (w1, w2))
        self.assertEqual((self.kids()["b"]["ws"], self.kids()["x"]["ws"], "ws" in self.kids()["a"]), (w1, w2, False))
        self.assertNotIn("ws", json.loads((self.s / "procs" / "b" / "loop.json").read_text()))
        bpid = self.kids()["b"]["pid"]
        self.post("0002", {"procs_added": {"b": {"exec": "lw", "max": 1, "ws": "rel/w3"}}})
        self.assertTrue(until(lambda: self.drained()))
        time.sleep(0.5)
        self.assertEqual((self.kids()["b"]["pid"], self.kids()["b"]["ws"]), (bpid, w1))
        self.post("0003", {"procs_added": {"y": {"exec": "lw", "ws": ["rel/w3"]}}})
        w = until(lambda: self.lstate()["mailbox_warning"])
        self.assertTrue(w.startswith("信 0003 不採用：") and "ws" in w, w)
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        self.assertEqual((self.kids()["b"]["pid"], self.kids()["b"]["ws"], self.kids()["x"]["ws"]), (bpid, w1, w2))
        self.mstop(p2)


    # ───── M. 11-02 晚：信箱與 procs_ctl 共存、procs_ctl 的整份 procs、exec 型收內嵌單子、ctl／state 寫 null、`-- 參數`、running／waiting ─────

    def test_mailbox_and_loops_ctl_together(self):
        # 信改的是底（daemon.json＋信），procs_ctl 每圈疊在底上：procs_added 加在底上、拿掉 procs_ctl 的變動＝回到底（信加的還在）
        p = self.mstart()   # 底：a
        self.post("0001", {"procs_added": {"bob": self.long()}})
        self.assertTrue(until(lambda: set(self.kids()) == {"a", "bob"}))
        self.lctl({"procs_added": {"carl": self.long()}, "procs_removed": ["a"], "seq": 1})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 1 and set(self.kids()) == {"bob", "carl"}))
        self.post("0002", {"procs_added": {"dan": self.long()}})   # 信照樣改底，疊上 loops_ctl 之後還在
        self.assertTrue(until(lambda: set(self.kids()) == {"bob", "carl", "dan"}))
        self.lctl({"seq": 2})   # loops_ctl 不加不減＝期望表就是底：a 回來、carl 收掉
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 2 and set(self.kids()) == {"a", "bob", "dan"}))
        self.lctl({"procs": {"zed": self.long()}, "seq": 3})   # 整份 loops＝蓋過底
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 3 and set(self.kids()) == {"zed"}))
        self.mstop(p)

    def test_mailbox_and_ctl_done_child_readded_by_letter(self):
        # 兩個都開：底來的子項自己結束＝不重起；同名再寄一封＝重新起（下一圈就能起）
        p = self.mstart()
        quick = {"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/ran"']}, "max": 1}
        self.post("0001", {"procs_added": {"x": quick}})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "ran").exists() and set(self.kids()) == {"a"}))
        self.post("0002", {"procs_added": {"x": quick}})
        self.assertTrue(until(lambda: (self.s / "procs" / "x" / "ran").read_text() == "x\nx\n" and set(self.kids()) == {"a"}))
        self.lctl({"procs_added": {"y": quick}, "seq": 1})   # loops_ctl 疊的照 ended_ 規則：結束後名單還有它＝不重起
        self.assertTrue(until(lambda: (self.s / "procs" / "y" / "ran").exists() and self.lstate()["ctl_seq"] == 1 and set(self.kids()) == {"a"}))
        time.sleep(0.6)
        self.assertEqual((self.s / "procs" / "y" / "ran").read_text(), "x\n")
        self.mstop(p)

    def test_procs_ctl_whole_procs(self):
        # procs_ctl 的 procs＝整份取代底，再＋procs_added－procs_removed；壞了整份不採用、維持上一份好的
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"e1": "long"}})
        self.assertTrue(until(lambda: set(self.kids()) == {"e1"}))
        self.lctl({"procs": {"e2": "long", "e3": "long"}, "procs_removed": ["e3"], "seq": 1})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 1 and set(self.kids()) == {"e2"}))
        self.lctl({"procs": {"e2": 3}, "seq": 2})
        w = until(lambda: self.lstate()["ctl_warning"])
        self.assertTrue(w and "procs" in w, w)
        self.assertEqual(set(self.kids()), {"e2"})   # 維持上一份好的
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, sorted(self.ended(out))), (0, "", ["e1", "e2"]))

    def test_execs_inline_inst(self):
        # execs 收 {"exec": 內嵌單子}（daemon.json、loops_ctl 的 procs_added、信）：跑一次、小格多一份 exec.json、cwd＝daemon 的 cwd；
        # 單子沒寫 stdout＝/dev/null，寫了照它；相對 $ref 從寫著它的檔算
        (self.t / "data.json").write_text('{"m": "hi"}')
        body = 'echo "$AOS_CF|$AOS_CO|$PWD|$1" > "$AOS_STACK/seen"; echo out; exit 4'
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs_ctl_mailbox": "box",
                        "procs": {"i": {"exec": {"argv": ["sh", "-c", body, "x", {"$ref": "data.json#/m"}]}}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "i" / "seen").exists() and self.kids() == {}))
        cell = os.path.realpath(self.s / "procs" / "i")
        real = os.path.realpath(self.t)
        self.assertEqual((self.s / "procs" / "i" / "seen").read_text(), "%s/exec.json|/exec|%s|hi\n" % (cell, real))
        self.assertEqual(sorted(f.name for f in (self.s / "procs" / "i").iterdir()), ["exec.json", "seen", "stderr.txt"])
        self.lctl({"procs_added": {"j": {"exec": {"argv": ["sh", "-c", "echo hey"], "stdout": "j.out"}}}, "seq": 1})
        self.assertTrue(until(lambda: (self.t / "j.out").exists() and self.lstate()["ctl_seq"] == 1 and self.kids() == {}))
        self.post("0001", {"procs_added": {"k": {"exec": {"argv": ["true"]}, "ws": "."}}})
        self.assertTrue(until(lambda: (self.s / "procs" / "k" / "exec.json").exists() and self.drained() and self.kids() == {}))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        e = self.ended(out)
        self.assertEqual((p.returncode, err, (self.t / "j.out").read_text(), {n: x["code"] for n, x in e.items()}),
                         (0, "", "hey\n", {"i": 4, "j": 0, "k": 0}))
        self.assertEqual(e["k"]["ws"], str(self.t))

    def test_daemon_windows_null(self):
        # daemon.json 的 ctl、state 寫 null＝不開（同沒寫）；loops_ctl、loops_state、procs_ctl_mailbox 寫 null 也不開
        r = self.run_d({"ctl": None, "state": None, "procs_ctl": None, "procs_state": None, "procs_ctl_mailbox": None, "max": 2})
        self.assertEqual((r.returncode, r.stderr, list(self.s.iterdir())), (0, "", []))

    def test_extra_args_to_own_exec(self):
        # `daemon.json -- 參數...` 只接在 daemon 自己的 exec 後面（子項不受影響）；沒有 exec 卻給了＝ArgumentsBad
        r = self.run_d({"exec": {"argv": ["sh", "-c", 'echo "$1" >> "$AOS_STACK/got"', "x"]}, "max": 2, "interval_ms": 0,
                        "b": {"argv": ["sh", "-c", 'echo "[$1]" > "$AOS_STACK/kid"', "x"]}, "procs": {"k": self.quick()}},
                       argv=("daemon.json", "--", "題"), log=False)
        self.assertEqual((r.returncode, r.stderr, (self.s / "got").read_text()), (0, "", "題\n題\n"))
        r = self.run_d({"max": 1}, argv=("daemon.json", "--", "題"))
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "ArgumentsBad"), r.stderr)
        r = self.run_d({"max": 1}, argv=("daemon.json", "題"))
        self.assertEqual((r.returncode, r.stderr.split(" ")[1]), (1, "ArgumentsBad"), r.stderr)

    def test_running_waiting_not_a_change(self):
        # 有身體的 daemon 跑著／睡著來回（running ⇄ waiting）不算變動：1 秒多 daemon 自己的 state 不動
        p = self.start({"exec": {"argv": ["true"]}, "interval_ms": 100, "state": "state.json", "ctl": "ctl.json"})
        self.assertTrue(until(lambda: self.state()))
        time.sleep(0.3)
        a = (self.s / "state.json").read_text()
        time.sleep(1.2)
        self.assertEqual((self.s / "state.json").read_text(), a)
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    # ───── N. 11-02 子項的 AOS_DAEMON_STACK（thinking 2026-11-02-resident-bob 衝突 2、2026-11-02-daemon-env 方向題 2）─────

    def test_children_get_daemon_stack(self):
        # loop 型（身體）、exec 型子項都看到 AOS_DAEMON_STACK＝daemon 的 stack（絕對、結尾 /）；AOS_DAEMON 開頭的只有這一個。
        # daemon 自己的環境沒設它（env_of 濾掉 AOS_）；daemon 的 $AOS_STACK 是相對的也轉成絕對（子項會 cd 走）
        self.prog("pe", 'env | grep "^AOS_DAEMON" > "$AOS_STACK/denv"\n')
        for st in (str(self.s), "stack"):
            r = self.run_d({"max": 15, "interval_ms": 100, "procs": {"bob": {"exec": "pe", "max": 1}, "j": "pe"}},
                           env={"AOS_STACK": st})
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            for n in ("bob", "j"):
                self.assertEqual((self.s / "procs" / n / "denv").read_text(), "AOS_DAEMON_STACK=%s/\n" % self.s, (st, n))


    # ───── O. 11-03 procs（thinking 2026-11-03-procs § 2b）：每個 proc 可寫自己的 stack ─────

    def test_stack_own_place(self):
        # stack＝proc 的 stack（AOS_STACK＝它/）：相對從 daemon 的 cwd 算、結尾 / 可有可無、不在就 mkdir -p；loop 型的 loop.json／ctl／state、
        # stderr.txt 都寫在那裡、loop.json 沒有 stack；procs/<名字>/ 根本不建；列上的 stack 一律絕對（預設小格也寫）；$env 照解；
        # 兩個 proc 同一個 S 不擋；null＝當沒寫；kill -9 daemon 再起照列上的接回
        self.prog("job", self.JOB)
        absx = self.t / "abs" / "x"
        shared = {"$env": "AOS_STACK", "$path": "shared"}
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {
            "a": dict(self.long(), stack="my/st"), "j1": {"exec": "job", "stack": str(absx) + "/"},
            "j2": {"exec": ["job", "2"], "stack": shared}, "j3": {"exec": ["job", "3"], "stack": shared}, "n": dict(self.long(), stack=None)}})
        mine = self.t / "my" / "st"
        k = until(lambda: (mine / "starts").exists() and (self.s / "procs" / "n" / "starts").exists() and set(self.kids()) == {"a", "n"}
                  and self.kids())
        self.assertTrue(k)
        self.assertEqual((k["a"]["stack"], k["n"]["stack"]), (str(mine), str(self.s / "procs" / "n")))
        lj = json.loads((mine / "loop.json").read_text())
        self.assertEqual((sorted(lj), (mine / "stderr.txt").exists()), (["_entry", "ctl", "exec", "max", "state"], True))
        self.assertTrue(until(lambda: json.loads((mine / "state.json").read_text())["phase"] == "running"))
        self.assertEqual(sorted(x.name for x in (self.s / "procs").iterdir()), ["n"])   # 寫了 stack 的不建預設小格
        self.assertTrue(until(lambda: len((self.s / "shared" / "runs").read_text().split("\n")) == 3))
        self.assertEqual(sorted((self.s / "shared" / "runs").read_text().split()), ["2", "3"])   # 同一個 S：兩個都照跑
        self.assertEqual(((absx / "stack.txt").read_text(), (absx / "stderr.txt").read_text()), (str(absx) + "/\n", "job 的 stderr\n"))
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        time.sleep(1)
        k2 = self.kids()
        self.assertEqual(({n: (r["pid"], r["stack"]) for n, r in k2.items()}, len((mine / "starts").read_text().split())),
                         ({n: (k[n]["pid"], k[n]["stack"]) for n in ("a", "n")}, 1))
        self.ctl({"cmd": "stop"})
        out, err = p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, err), (0, ""))
        for bad in (3, "", ["x"]):
            r = self.run_d({"procs": {"b": {"exec": "long", "stack": bad}}, "max": 1})
            self.assertEqual((r.returncode, r.stderr.split(" ")[1], "stack" in r.stderr), (1, "CfgBad", True), (bad, r.stderr))

    # ───── P. 11-03 daemon 的 stop／start（procs § 2c，照 ctl-commands § 5 改）：寫子 loop 的 ctl {"cmd": "stop"}、列留 stopped ─────

    def clock(self):
        d = self.t / "clk"
        if not d.exists():
            self.prog("clk", 'echo x >> "$AOS_STACK/ticks"\n')
        return {"exec": "clk", "interval_ms": 100}

    @staticmethod
    def ticks(cell):
        try:
            return len((cell / "ticks").read_text().split())
        except OSError:
            return 0

    @staticmethod
    def cctl(cell, doc):
        """直接寫子 loop 的 ctl.json（先寫 .ctl.json 再改名，N-05）。"""
        (cell / ".ctl.json").write_text(json.dumps(doc))
        os.replace(cell / ".ctl.json", cell / "ctl.json")

    def test_stop_start(self):
        # procs_stopped＝daemon 往子 loop 的 ctl 寫 {"cmd": "stop", "seq": N}（不 SIGTERM）：它跑完這次自己退 0，列留成 stopped
        # （pid null、stack 留著）、不重起；名字拿出 stopped 集合（procs_ctl 拿掉＝回初始＝起）＝同一個 stack 再起、ctl 不清（基準線）；
        # 再停一次 seq 往上（內容跟上一道不同）；同名兩邊都寫＝起；不在期望表的名字＝不管
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        k = until(lambda: self.ticks(c) >= 2 and self.kids())
        pid = k["c"]["pid"]
        self.lctl({"procs_stopped": ["c", "nobody"], "seq": 1})
        r = until(lambda: self.kids()["c"]["phase"] == "stopped" and self.kids()["c"])
        self.assertEqual(r, {"pid": None, "started_at_ticks": None, "phase": "stopped", "code": 0, "signal": None, "stack": str(c)})
        self.assertEqual((json.loads((c / "ctl.json").read_text()), json.loads((c / "state.json").read_text())["phase"], alive(pid)),
                         ({"cmd": "stop", "seq": 1}, "stopped", False))
        self.assertIsNone(self.lstate()["ctl_warning"])
        n = self.ticks(c)
        time.sleep(1)
        self.assertEqual((self.ticks(c), self.kids()["c"]["phase"]), (n, "stopped"))
        self.lctl({"seq": 2})
        k2 = until(lambda: self.kids()["c"]["phase"] == "running" and self.ticks(c) > n and self.kids())
        self.assertTrue(k2)
        self.assertEqual((k2["c"]["stack"], json.loads((c / "ctl.json").read_text())), (str(c), {"cmd": "stop", "seq": 1}))
        self.lctl({"procs_stopped": ["c"], "seq": 3})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "stopped"))
        self.assertEqual(json.loads((c / "ctl.json").read_text()), {"cmd": "stop", "seq": 2})
        self.lctl({"procs_stopped": ["c"], "procs_started": ["c"], "seq": 4})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "running"))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.upped(out), [x["phase"] for x in self.logs(out)], self.kids()["c"]["phase"]),
                         (0, "", ["c", "c", "c"], ["running", "stopped", "running", "stopped", "running", "sleeping"], "sleeping"))

    def test_start_comes_back_paused(self):
        # 暫停中被 stop 的子 loop，start 之後照它自己 state.json 的 paused 起來先暫停（ctl-commands § 4）；直接寫它的 ctl resume 才接著跑
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        self.assertTrue(until(lambda: self.ticks(c) >= 1))
        self.cctl(c, {"cmd": "pause"})
        self.assertTrue(until(lambda: json.loads((c / "state.json").read_text())["phase"] == "paused"))
        self.lctl({"procs_stopped": ["c"], "seq": 1})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "stopped"))
        cs = json.loads((c / "state.json").read_text())
        self.assertEqual((cs["phase"], cs["paused"]), ("stopped", True))
        self.lctl({"seq": 2})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "running"))
        self.assertTrue(until(lambda: json.loads((c / "state.json").read_text())["pid"] == self.kids()["c"]["pid"]
                              and json.loads((c / "state.json").read_text())["phase"] == "paused"))
        n = self.ticks(c)
        time.sleep(0.6)
        self.assertEqual(self.ticks(c), n)
        self.cctl(c, {"cmd": "resume"})
        self.assertTrue(until(lambda: self.ticks(c) > n))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_mailbox_stop_start_rm(self):
        # 信的 procs_stopped／procs_started：同一封 add＋stop＝列直接 stopped、不起、stack 不建；同名 add＝設定換掉、停照停（信來不叫起）；
        # procs_started＝起；stopped 的被 procs_removed＝列拿掉、stack 不碰
        p = self.mstart()
        z = self.s / "procs" / "z"
        self.post("0001", {"procs_added": {"z": self.clock()}, "procs_stopped": ["z"]})
        r = until(lambda: "z" in self.kids() and self.kids()["z"])
        self.assertEqual((r["phase"], r["pid"], r["code"], r["stack"], z.exists()), ("stopped", None, None, str(z), False))
        self.post("0002", {"procs_added": {"z": self.clock()}})
        self.assertTrue(until(self.drained))
        time.sleep(0.6)
        self.assertEqual((self.kids()["z"]["phase"], z.exists(), self.lstate()["mailbox_warning"]), ("stopped", False, None))
        self.post("0003", {"procs_started": ["z"]})
        self.assertTrue(until(lambda: self.kids()["z"]["phase"] == "running" and self.ticks(z) >= 1))
        self.post("0004", {"procs_stopped": ["z"]})
        self.assertTrue(until(lambda: self.kids()["z"]["phase"] == "stopped"))
        self.post("0005", {"procs_removed": ["z"]})
        self.assertTrue(until(lambda: "z" not in self.kids()))
        self.assertEqual((set(self.kids()), (z / "ticks").exists(), (z / "loop.json").exists()), ({"a"}, True, True))
        self.post("0006", {"procs_added": {"z": self.clock()}})   # 拿掉之後再加＝新的，照常起（底的 stopped 集合也沒留它）
        self.assertTrue(until(lambda: "z" in self.kids() and self.kids()["z"]["phase"] == "running"))
        self.mstop(p)

    def test_stopped_adopted_after_crash(self):
        # kill -9 daemon 再起：stopped 的列接成 stopped（不起、不判活）、名字進底的 stopped 集合——procs_ctl 拿掉 procs_stopped 也照停，
        # 要 procs_started 才起（底＝adopt 接回的，N-06「沒寫＝回初始值」的初始就是它）
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        self.assertTrue(until(lambda: self.ticks(c) >= 1))
        self.lctl({"procs_stopped": ["c"], "seq": 1})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "stopped"))
        p.kill()
        p.wait()
        p2 = self.start()
        self.assertTrue(until(lambda: self.lstate()["pid"] == p2.pid))
        n = self.ticks(c)
        time.sleep(1)
        self.assertEqual((self.kids()["c"]["phase"], self.kids()["c"]["pid"], self.ticks(c)), ("stopped", None, n))
        self.lctl({"seq": 2})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 2))
        time.sleep(0.6)
        self.assertEqual(self.kids()["c"]["phase"], "stopped")
        self.lctl({"procs_started": ["c"], "seq": 3})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "running" and self.ticks(c) > n))
        self.ctl({"cmd": "stop"})
        p2.communicate(timeout=30)
        self.assertEqual(p2.returncode, 0)

    def test_exec_type_has_no_stop(self):
        # exec 型只有跑和拔：procs_stopped／procs_started 裡有 exec 型（表上的看那列、還沒起的看寫法）＝procs_ctl 整份不採用、ctl_warning
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"e": "long", "c": self.clock()}})
        k = until(lambda: set(self.kids()) == {"e", "c"} and self.kids())
        for i, doc in enumerate(({"procs_stopped": ["e"]}, {"procs_started": ["e"]}, {"procs_added": {"x": "long"}, "procs_stopped": ["x"]})):
            self.lctl(dict(doc, seq=i + 1))
            w = until(lambda: "exec 型" in (self.lstate()["ctl_warning"] or "") and self.lstate()["ctl_warning"])
            self.assertTrue(w, doc)
            self.lctl({"seq": 10 + i})
            self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 10 + i and self.lstate()["ctl_warning"] is None))
        self.assertEqual((set(self.kids()), self.kids()["e"]["pid"], alive(k["e"]["pid"])), ({"e", "c"}, k["e"]["pid"], True))
        self.lctl({"procs_stopped": ["c"], "seq": 20})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "stopped" and self.lstate()["ctl_warning"] is None))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_daemon_paused_holds_stop(self):
        # daemon 自己暫停中：起停也等解除（不寫子 loop 的 ctl）；解除那圈才停
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        self.assertTrue(until(lambda: self.ticks(c) >= 1))
        self.ctl({"cmd": "pause", "seq": 1})
        self.assertTrue(until(lambda: self.state()["phase"] == "paused"))
        self.lctl({"procs_stopped": ["c"], "seq": 2})
        self.assertTrue(until(lambda: self.lstate()["ctl_seq"] == 2))
        n = self.ticks(c)
        time.sleep(0.6)
        self.assertEqual((self.ticks(c) > n, self.kids()["c"]["phase"], (c / "ctl.json").exists()), (True, "running", False))
        self.ctl({"cmd": "resume", "seq": 3})
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "stopped"))
        self.ctl({"cmd": "stop"})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_child_ctl_stop_bypassing_daemon_drops_row(self):
        # 繞過 daemon 直接往子 loop 的 ctl 寫 stop：子 loop 退 0，daemon 看到的是「退了」＝照 11-02 從表上拿掉（使用者 11-03「照舊拿掉」）、本次不再起
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        self.assertTrue(until(lambda: self.ticks(c) >= 1 and self.kids()))
        self.cctl(c, {"cmd": "stop"})
        self.assertTrue(until(lambda: self.kids() == {}))
        n = self.ticks(c)
        time.sleep(0.6)
        self.assertEqual((self.kids(), self.ticks(c)), ({}, n))
        self.ctl({"cmd": "stop"})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, (self.ended(out)["c"]["phase"], self.ended(out)["c"]["code"])), (0, "", ("done", 0)))

    # ───── Q. 11-03 sleep／wake：daemon 收工時還在跑的 loop 型留成 sleeping，再開自動 wake（procs § 8） ─────

    def test_sleep_wake(self):
        # ctl 的 stop 收工：跑著的 loop 型 c＝SIGTERM、列留成 sleeping（pid null、stack 留著）；daemon 下 stop 的 s 照舊 stopped；
        # exec 型 e 照舊拿掉。再開：c 用列上的 stack 自動 wake（log 一行 running、ticks 接著長），s 照停，e 照 daemon.json 重新起
        c, sc = self.s / "procs" / "c", self.s / "procs" / "s"
        doc = {"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock(), "s": self.clock(), "e": "long"}}
        p = self.start(doc)
        self.assertTrue(until(lambda: self.ticks(c) >= 1 and self.ticks(sc) >= 1 and set(self.kids()) == {"c", "s", "e"}))
        self.lctl({"procs_stopped": ["s"], "seq": 1})
        self.assertTrue(until(lambda: self.kids()["s"]["phase"] == "stopped"))
        old = self.kids()["c"]["pid"]
        self.ctl({"cmd": "stop", "seq": 1})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err), (0, ""))
        k = self.kids()
        self.assertEqual({n: (r["phase"], r["pid"], r["stack"]) for n, r in k.items()},
                         {"c": ("sleeping", None, str(c)), "s": ("stopped", None, str(sc))})
        self.assertEqual({n: x["phase"] for n, x in self.ended(out).items()}, {"s": "stopped", "c": "sleeping", "e": "stopped"})
        self.assertFalse(alive(old))
        n, ns = self.ticks(c), self.ticks(sc)
        p2 = self.start()
        k2 = until(lambda: self.kids()["c"]["phase"] == "running" and "e" in self.kids() and self.kids())
        self.assertTrue(k2)
        self.assertEqual((k2["c"]["stack"], k2["s"]["phase"], k2["c"]["pid"] != old), (str(c), "stopped", True))
        self.assertTrue(until(lambda: self.ticks(c) > n))
        time.sleep(0.5)
        self.assertEqual((self.ticks(sc), self.kids()["s"]["phase"]), (ns, "stopped"))
        self.lctl({"procs_started": ["s"], "seq": 2})   # stopped 的照舊要 start 才起
        self.assertTrue(until(lambda: self.kids()["s"]["phase"] == "running" and self.ticks(sc) > ns))
        self.ctl({"cmd": "stop", "seq": 2})
        out2, err2 = p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, err2, self.upped(out2)[:2]), (0, "", ["c", "e"]))

    def test_sleep_wake_paused_and_sigint(self):
        # Ctrl+C（SIGINT）收工一樣睡；收工時本來暫停中的：醒來照它自己 state.json 的 paused 接著暫停（ctl-commands § 4），寫它的 ctl resume 才接著跑
        c = self.s / "procs" / "c"
        p = self.start({"state": "state.json", "ctl": "ctl.json", "procs": {"c": self.clock()}})
        self.assertTrue(until(lambda: self.ticks(c) >= 1))
        self.cctl(c, {"cmd": "pause"})
        self.assertTrue(until(lambda: json.loads((c / "state.json").read_text())["phase"] == "paused"))
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.kids()["c"]["phase"]), (130, "", "sleeping"))
        cs = json.loads((c / "state.json").read_text())
        self.assertEqual((cs["phase"], cs["paused"]), ("stopped", True))
        p2 = self.start()
        self.assertTrue(until(lambda: self.kids()["c"]["phase"] == "running"
                              and json.loads((c / "state.json").read_text())["pid"] == self.kids()["c"]["pid"]
                              and json.loads((c / "state.json").read_text())["phase"] == "paused"))
        n = self.ticks(c)
        time.sleep(0.6)
        self.assertEqual(self.ticks(c), n)
        self.cctl(c, {"cmd": "resume"})
        self.assertTrue(until(lambda: self.ticks(c) > n))
        self.ctl({"cmd": "stop"})
        p2.communicate(timeout=30)
        self.assertEqual(p2.returncode, 0)

    def test_sleep_wake_mailbox(self):
        # 信箱模式（aos-daemon-ctl add 的路）：信加的 z、y、x 收工時都睡；daemon 沒在跑時寄的信下次開門先套再 wake——
        # y 被 procs_stopped＝改成 stopped、不 wake；x 被 procs_removed＝列拿掉；z（設定只在記憶體，接回記 null）照它 stack 裡的 loop.json wake
        p = self.mstart()
        z, y = self.s / "procs" / "z", self.s / "procs" / "y"
        self.post("0001", {"procs_added": {"z": self.clock(), "y": self.clock(), "x": self.clock()}})
        self.assertTrue(until(lambda: all(self.ticks(self.s / "procs" / q) >= 1 for q in "zyx")))
        self.mstop(p)
        self.assertEqual({q: r["phase"] for q, r in self.kids().items()}, {q: "sleeping" for q in "azyx"})
        self.post("0002", {"procs_stopped": ["y"]})
        self.post("0003", {"procs_removed": ["x"]})
        n, ny = self.ticks(z), self.ticks(y)
        p2 = self.start()
        self.assertTrue(until(lambda: self.drained() and self.kids()["z"]["phase"] == "running" and self.ticks(z) > n))
        time.sleep(0.5)
        self.assertEqual(({q: r["phase"] for q, r in self.kids().items()}, self.ticks(y), self.lstate()["mailbox_warning"]),
                         ({"a": "running", "z": "running", "y": "stopped"}, ny, None))
        self.post("0004", {"procs_started": ["y"]})
        self.assertTrue(until(lambda: self.kids()["y"]["phase"] == "running" and self.ticks(y) > ny))
        self.ctl({"cmd": "stop", "seq": 2})   # 上一個行程的 {"cmd": "stop"} 是這個行程的基準線：內容要不一樣才算新的
        out, err = p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, err), (0, ""))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
