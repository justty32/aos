"""aos-daemon：daemon.json＝loop.json 的超集、loops 表、ctl 增減、不自動重起、收工收子項、接回（N-28、N-54、P-36）。
10-29 拆窗（thinking 2026-10-29-medium-plan § 四）：名單的手把在 loops_ctl.json、子項表在 loops_state.json；ctl.json／state.json 只管 loop 面向。
10-30 exec 型子項 execs（thinking 2026-10-30-agent-lifecycle B-12 ②）：直接 aos-exec 一次、不包 aos-loop，loops_state.json 多一張 execs 表。
10-30 eca 子項的工作區 ws（thinking 2026-10-30-eca 衝突 1）：子項物件寫 ws＝起它時設 AOS_WS，沒寫＝繼承 daemon 的。
11-02（thinking 2026-11-02-state-window）：daemon 自己的窗慣用名 daemon_ctl.json／daemon_state.json；子項結束（done／stopped）就從
loops_state 的表上拿掉，結束的 phase／code 改看 daemon 的 log（--enable-logs 時 stdout 一行一個 JSON，ended()）。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # 錯誤一行的代號（照 10-23 命名統合）：檢查對得上原因開頭再拿掉

from aos_bins import ROOT, tool, path_with  # noqa: E402  四支 C++ 在 impls/<名>/bin/、aos-tick 在 proto8/bin/（10-23）
DAEMON = tool("aos-daemon")
LONG = 'echo x >> "$AOS_STACK/starts"; while :; do sleep 0.05; done'


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = path_with(e.get("PATH", ""))
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


def logs(out):
    """daemon 的 log（--enable-logs，stdout）裡子項那幾行（有 name、table）；身體每次一行的不算。"""
    rows = []
    for l in out.splitlines():
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if isinstance(d, dict) and "name" in d and "table" in d:
            rows.append(d)
    return rows


def ended(out):
    """{名字: 結束那一行}（phase done／stopped；同名多次＝最後一次）。"""
    return {d["name"]: d for d in logs(out) if d["phase"] in ("done", "stopped")}


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
            doc = json.loads(st.read_text())
            for r in list(doc.get("loops", {}).values()) + list(doc.get("execs", {}).values()):   # execs：exec 型子項（10-30）
                if r.get("pid") and alive(r["pid"]):
                    try:
                        os.killpg(r["pid"], signal.SIGKILL)
                    except OSError:
                        pass

    def cfg(self, doc):
        (self.t / "daemon.json").write_text(json.dumps(doc))

    def run_d(self, doc, timeout=30, env=None, argv=("--enable-logs", "daemon.json")):
        if doc is not None:
            self.cfg(doc)
        return subprocess.run([DAEMON, *argv], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)} if env is None else env),
                              capture_output=True, text=True, timeout=timeout)

    def start(self, doc=None):
        if doc is not None:
            self.cfg(doc)
        p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def state(self):
        return json.loads((self.s / "daemon_state.json").read_text())

    def lstate(self):
        return json.loads((self.s / "loops_state.json").read_text())

    def kids(self):
        return self.lstate()["loops"]

    def ctl(self, doc, name="daemon_ctl.json"):
        tmp = self.s / ("." + name)
        tmp.write_text(json.dumps(doc))
        os.replace(tmp, self.s / name)

    def lctl(self, doc):
        self.ctl(doc, "loops_ctl.json")

    def long(self, mx=1):
        return {"exec": "long", "max": mx}

    def test_loop_json_runs_as_is(self):
        # 合法的 loop.json 直接丟給 daemon 也能跑（N-28）
        r = self.run_d({"exec": "daemon.json#/body", "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']},
                        "max": 3, "interval_ms": 0})
        self.assertEqual((r.returncode, r.stderr, len((self.s / "runs").read_text().split())), (0, "", 3))

    def test_needs_stack(self):
        r = self.run_d({"max": 1}, env={})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-daemon: ") and "AOS_STACK" in r.stderr, r.stderr)

    def test_bad_loops_is_own_error(self):
        for bad in ([1], {"a/b": "x"}, {"a": 3}, {"a#b": "x"}, {".a": "x"}):
            r = self.run_d({"loops": bad, "max": 1})
            self.assertEqual(r.returncode, 1, bad)
            self.assertTrue(r.stderr.startswith("aos-daemon: "), r.stderr)

    def test_loops_started_in_cells_then_stop(self):
        sub = self.t / "sub"
        sub.mkdir()
        (sub / "_entry").write_text("#!/bin/sh\n" + LONG + "\n")
        (sub / "_entry").chmod(0o755)
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": "sub", "b": self.long()}})
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and (self.s / "loops" / "b" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual({n: r["phase"] for n, r in k.items()}, {"a": "running", "b": "running"})
        a = json.loads((self.s / "loops" / "a" / "loop.json").read_text())
        # 10-21 傍晚：相對的 exec 照 daemon 的 cwd 轉成絕對、蓋上 _entry，子 loop 經 aos-exec 起
        self.assertEqual(a, {"exec": os.path.join(os.path.realpath(self.t), "sub"), "ctl": "ctl.json", "state": "state.json",
                             "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
        self.assertTrue(until(lambda: json.loads((self.s / "loops" / "b" / "state.json").read_text())["phase"] == "running"))
        pids = [r["pid"] for r in k.values()]
        self.ctl({"stopped": True, "seq": 1})
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["ctl_seq"]), (0, "", "stopped", 1))
        # 10-23 命名統合：daemon 收掉的子項＝stopped（統合前叫 exited）；每列 {pid, started_at_ticks, phase, code, signal}
        self.assertNotIn("loops", st)   # 10-29 拆窗：子項表在 loops_state.json
        self.assertEqual({frozenset(r) for r in k.values()}, {frozenset({"pid", "started_at_ticks", "phase", "code", "signal"})})
        # 11-02：收掉的從表上拿掉，log 記一行 stopped
        self.assertEqual((self.kids(), {n: (d["phase"], d["pid"]) for n, d in ended(out).items()}),
                         ({}, {n: ("stopped", r["pid"]) for n, r in k.items()}))
        self.assertEqual([alive(x) for x in pids], [False, False])

    def test_done_child_not_restarted(self):
        p = self.start({"state": "daemon_state.json", "max": 15, "interval_ms": 100,
                        "loops": {"once": {"exec": "daemon.json#/loops/once/body", "max": 1,   # D4：內嵌單子
                                              "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"']}}}})
        out, err = p.communicate(timeout=30)
        k = ended(out)
        # 子 loop 自己結束的＝done（10-23 命名統合，統合前叫 exited）；11-02 起表上不留、看 log
        self.assertEqual((p.returncode, err, k["once"]["phase"], k["once"]["code"], self.kids()), (0, "", "done", 0, {}))
        self.assertEqual(len((self.s / "loops" / "once" / "starts").read_text().split()), 1)

    def test_failing_child_stderr_in_cell(self):
        p = self.start({"state": "daemon_state.json", "max": 10, "interval_ms": 100,
                        "loops": {"bad": {"exec": "daemon.json#/loops/bad/body",
                                             "body": {"argv": ["sh", "-c", "exit 3"]}},
                                     "obj": {"exec": {"argv": "true"}}}})   # 10-24 起物件＝內嵌單子；形狀壞＝子 loop 自己的錯（10-21～10-23 物件本身就是錯）
        out, err = p.communicate(timeout=30)
        k = ended(out)
        self.assertEqual((p.returncode, err, k["bad"]["phase"], k["bad"]["code"], k["obj"]["phase"], k["obj"]["code"]),
                         (0, "", "done", 3, "done", 1))
        self.assertIn("aos-loop: ", (self.s / "loops" / "bad" / "stderr.txt").read_text())
        self.assertIn("aos-loop: EntryBad 單子跑不起來：", (self.s / "loops" / "obj" / "stderr.txt").read_text())

    def test_ctl_loops_add_and_remove(self):
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        a_pid = k["a"]["pid"]
        self.lctl({"loops": {"b": self.long()}})
        k = until(lambda: (self.s / "loops" / "b" / "starts").exists() and "a" not in self.kids() and self.kids())
        self.assertEqual(list(k), ["b"])
        self.assertFalse(alive(a_pid))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_sigterm_collects_loops_nonzero(self):
        p = self.start({"state": "daemon_state.json", "loops": {"a": self.long(), "b": self.long()}})
        k = until(lambda: (self.s / "loops" / "b" / "starts").exists() and len(self.kids()) == 2 and self.kids())
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["phase"], st["code"]), (143, "", "stopped", 143))
        self.assertEqual([alive(r["pid"]) for r in k.values()], [False, False])
        self.assertEqual((self.kids(), {n: d["phase"] for n, d in ended(out).items()}), ({}, {"a": "stopped", "b": "stopped"}))

    # ---- 10-21 計畫第 2 段：命令列（D1，跟 aos-loop 共用；10-23 前 Python 版是 aos_loop.cli）、字串子項（D2）、收工時剛死的子項（D7）

    def test_flags_override_cfg(self):
        # --max／--interval-ms 蓋過 daemon.json（旗標 ＞ 設定檔）；state 回報實際生效的值
        r = self.run_d({"exec": "daemon.json#/body", "body": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']},
                        "max": 100, "interval_ms": 5000, "state": "daemon_state.json"},
                       argv=("--max", "3", "--interval-ms", "0", "daemon.json"))
        st = self.state()
        self.assertEqual((r.returncode, r.stderr, len((self.s / "runs").read_text().split())), (0, "", 3))
        self.assertEqual((st["max"], st["interval_ms"], st["phase"]), (3, 0, "done"))

    def test_val_array_and_cfg_rules(self):
        # 10-21 傍晚：唯一的位置參數＝設定檔；exec 可以是 [目標, 參數...]，參數每次接上；設定檔可寫 檔#/指標
        job = self.t / "job"
        job.mkdir()
        (job / "_entry").write_text('#!/bin/sh\necho "$@" >> "$AOS_STACK/runs"\n')
        (job / "_entry").chmod(0o755)
        self.cfg({"exec": ["job", "a", "b"], "interval_ms": 0, "max": 2, "sub": {"exec": ["job", "c"], "max": 1}})
        for argv, want in ((("daemon.json",), "a b\na b\n"), (("daemon.json#/sub",), "c\n")):
            (self.s / "runs").unlink(missing_ok=True)
            r = self.run_d(None, argv=argv)
            self.assertEqual((r.returncode, r.stderr, (self.s / "runs").read_text()), (0, "", want), argv)
        for argv in ((), ("daemon.json", "job"), ("--cfg", "daemon.json")):
            r = self.run_d(None, argv=argv)
            self.assertEqual((r.returncode, r.stderr.startswith("aos-daemon: usage: ")), (1, True), (argv, r.stderr))

    def test_child_started_through_aos_exec(self):
        # 使用者 10-21 傍晚「5.要」：子 loop 經 aos-exec 起（aos-exec 設好 AOS_CF／AOS_CD 再 exec 成 aos-loop，pid 不變）
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": ["long"]}})
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        env = dict(x.split("=", 1) for x in Path("/proc/%d/environ" % k["a"]["pid"]).read_text().split("\0") if "=" in x)
        cell = os.path.realpath(self.s / "loops" / "a")
        self.assertEqual((env.get("AOS_CF"), env.get("AOS_CD"), env.get("AOS_CO")),
                         (os.path.join(cell, "loop.json"), cell, "/_entry"))
        self.assertEqual(json.loads((self.s / "loops" / "a" / "loop.json").read_text())["exec"],
                         [os.path.join(os.path.realpath(self.t), "long")])
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_string_child_is_exec_target(self):
        # 字串子項＝aos-exec 的目標（不限資料夾，這裡指進 daemon.json），包成 {"exec": 它}
        p = self.start({"state": "daemon_state.json", "max": 10, "interval_ms": 100,
                        "loops": {"s": "daemon.json#/kids/s"},
                        "kids": {"s": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        k = ended(out)
        self.assertEqual((p.returncode, err, k["s"]["phase"], k["s"]["code"]), (0, "", "done", 0))
        self.assertEqual(json.loads((self.s / "loops" / "s" / "loop.json").read_text()),
                         {"exec": os.path.join(os.path.realpath(self.t), "daemon.json#/kids/s"), "ctl": "ctl.json",
                          "state": "state.json", "_entry": ["aos-loop", {"$env": "AOS_CF"}]})
        self.assertEqual(len((self.s / "loops" / "s" / "starts").read_text().split()), 1)

    def test_child_dead_at_finish_marked_done(self):
        # D7：最後一次的 tend 之後才結束的子項，收工後的最後一份 state 也要是 done、記 code（不留 running、也不算 daemon 收掉的 stopped）
        p = self.start({"state": "daemon_state.json", "exec": "daemon.json#/body",
                        "body": {"argv": ["sh", "-c", "sleep 2; exit 10"]},
                        "loops": {"q": "daemon.json#/kids/q"},
                        "kids": {"q": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"; exit 10']}}})
        out, err = p.communicate(timeout=30)
        q = ended(out)["q"]
        self.assertEqual((p.returncode, err, len((self.s / "loops" / "q" / "starts").read_text().split())), (0, "", 1))
        self.assertEqual((q["phase"], q["code"], q["signal"]), ("done", 0, None))

    def test_adopt_after_crash(self):
        doc = {"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        pid = k["a"]["pid"]
        p.kill()
        p.wait()
        self.assertTrue(alive(pid))
        p2 = self.start()
        time.sleep(1)
        self.assertEqual((self.kids()["a"]["pid"], len((self.s / "loops" / "a" / "starts").read_text().split())), (pid, 1))
        self.ctl({"stopped": True})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(pid)), (0, False))

    def test_restart_starts_loops_died_while_down(self):
        # 使用者 10-22「daemon 重開時照表起，算重新開始、不算自動重起」：停機期間死掉的子項，重開時照名單起
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        os.killpg(old, signal.SIGKILL)
        self.assertTrue(until(lambda: not alive(old)))
        p2 = self.start()
        k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
        self.assertTrue(k2)
        self.assertTrue(until(lambda: len((self.s / "loops" / "a" / "starts").read_text().split()) == 2))
        self.ctl({"stopped": True})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(k2["a"]["pid"])), (0, False))

    def test_child_name_same_as_own_windows(self):
        # 11-02 拿掉 10-22 的「子項名字擋掉跟 ctl／state 同名」（使用者 11-02 答衝突 1「那兩題中的1.，可以」）：
        # 小格在 $AOS_STACK/loops/<名字>/，跟 daemon 自己放在 stack 頂層的窗撞不到——同名照起、窗照寫
        absst = str(self.s / "st.json")
        (self.s / "x").mkdir()   # state 的路徑照字面寫（./x/../s.json 要 x 在）；11-02 前撞名在寫之前就擋了
        for win, name in (({"state": "state.json"}, "state.json"), ({"ctl": "ctl.json"}, "ctl.json"),
                          ({"ctl": "w/c.json"}, "w"), ({"state": "./x/../s.json"}, "s.json"), ({"state": absst}, "st.json")):
            (self.s / "loops_state.json").unlink(missing_ok=True)
            r = self.run_d(dict(win, loops={name: {"exec": "daemon.json#/b", "max": 1}},
                                b={"argv": ["true"]}, max=3, interval_ms=100))
            self.assertEqual((r.returncode, r.stderr, (self.s / "loops" / name / "loop.json").exists(), list(ended(r.stdout))),
                             (0, "", True, [name]), (win, name))
        for f in ("state.json", "s.json", "st.json"):
            self.assertEqual(json.loads((self.s / f).read_text())["phase"], "done", f)   # 窗照寫

    def test_ctl_loops_same_name_as_windows_adopted(self):
        # 11-02 起 loops_ctl 改名單用到跟窗同名的名字也照採用（10-22 的撞名不採用拿掉；小格在 loops/<名字>/）
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": self.long()}})
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        self.lctl({"loops": {"a": self.long(), "daemon_state.json": self.long()}})
        st = until(lambda: set(self.kids()) == {"a", "daemon_state.json"} and self.lstate())
        self.assertTrue(st)
        self.assertTrue(until(lambda: (self.s / "loops" / "daemon_state.json" / "starts").exists()))
        self.assertEqual((self.kids()["a"]["pid"], alive(k["a"]["pid"]), st["ctl_warning"]), (k["a"]["pid"], True, None))
        self.assertTrue((self.s / "daemon_state.json").is_file())
        self.ctl({"stopped": True})
        out, err = p.communicate(timeout=30)
        self.assertEqual((p.returncode, err, self.state()["ctl_warning"]), (0, "", None))

    def test_ctl_loops_moved_to_loops_ctl(self):
        # 10-29 拆窗：ctl.json 寫 loops_added 不採用（state 的 ctl_warning 提醒搬家，過渡期）；寫進 loops_ctl.json 才起
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "loops": {"a": self.long()}})
        self.assertTrue(until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids()))
        self.ctl({"loops_added": {"b": self.long()}, "seq": 1})
        st = until(lambda: self.state()["ctl_seq"] == 1 and self.state())
        self.assertIn("loops_ctl.json", st["ctl_warning"] or "")
        time.sleep(1)
        self.assertFalse((self.s / "loops" / "b").exists())
        self.lctl({"loops_added": {"b": self.long()}, "seq": 1})
        self.assertTrue(until(lambda: (self.s / "loops" / "b" / "starts").exists() and set(self.kids()) == {"a", "b"}))
        self.assertEqual(self.lstate()["ctl_seq"], 1)
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_adopt_false_starts_fresh(self):
        doc = {"state": "daemon_state.json", "loops": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.kids())
        old = k["a"]["pid"]
        p.kill()
        p.wait()
        try:
            p2 = self.start(dict(doc, adopt=False))
            k2 = until(lambda: self.kids()["a"]["pid"] != old and self.kids())
            self.assertTrue(k2)
            self.assertTrue(until(lambda: len((self.s / "loops" / "a" / "starts").read_text().split()) == 2))
            p2.send_signal(signal.SIGTERM)
            p2.communicate(timeout=30)
        finally:
            os.killpg(old, signal.SIGKILL)

    # ---- 10-30 exec 型子項 execs（thinking 2026-10-30-agent-lifecycle B-12 ②、實作步驟 7；N-28／N-54 的 10-30 補草稿）

    def xkids(self):
        return self.lstate()["execs"]

    def prog(self, name, body):
        d = self.t / name
        d.mkdir()
        (d / "_entry").write_text("#!/bin/sh\n" + body)
        (d / "_entry").chmod(0o755)

    def test_execs_once_done_not_restarted(self):
        # execs 一項跑完＝done、記 code、不重起；不包 aos-loop（小格沒有 loop.json、ctl、state；表上的 pid 就是那支程式）
        self.prog("job", 'echo "$$ $*" >> "$AOS_STACK/runs"\nexit 3\n')
        r = self.run_d({"state": "daemon_state.json", "max": 15, "interval_ms": 100, "execs": {"j": ["job", "a"]}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        st = self.lstate()
        j = ended(r.stdout)["j"]
        self.assertEqual((st["loops"], st["execs"], j["table"], j["phase"], j["code"], j["signal"]), ({}, {}, "execs", "done", 3, None))
        self.assertEqual([d["name"] for d in logs(r.stdout)], ["j", "j"])   # 起來一行、結束一行；不重起
        self.assertEqual((self.s / "loops" / "j" / "runs").read_text(), "%d a\n" % j["pid"])
        self.assertEqual(sorted(f.name for f in (self.s / "loops" / "j").iterdir()), ["runs", "stderr.txt"])

    def test_execs_removed_sigterm_then_kill_group(self):
        # execs_removed 送 SIGTERM（直接給那支程式）；不理的 10 秒後 SIGKILL 整群
        self.prog("stub", 'trap "" TERM\nsleep 1000 &\necho "$$ $!" > "$AOS_STACK/pids"\nwhile :; do sleep 0.05; done\n')
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "execs": {"a": "long", "b": "stub"}})
        x = until(lambda: (self.s / "loops" / "a" / "starts").exists() and (self.s / "loops" / "b" / "pids").exists() and len(self.xkids()) == 2
                  and self.xkids())
        self.assertTrue(x)
        bpid, bsleep = map(int, (self.s / "loops" / "b" / "pids").read_text().split())
        self.addCleanup(lambda: alive(bsleep) and os.kill(bsleep, signal.SIGKILL))
        t0 = time.monotonic()
        self.lctl({"execs_removed": ["a", "b"]})
        self.assertTrue(until(lambda: list(self.xkids()) == ["b"] and self.xkids()["b"]["phase"] == "stopping", 5))
        self.assertFalse(alive(x["a"]["pid"]))
        self.assertTrue(until(lambda: self.xkids() == {}, 20))
        self.assertGreater(time.monotonic() - t0, 9)
        self.assertEqual((alive(bpid), alive(bsleep)), (False, False))
        self.ctl({"stopped": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_execs_loops_same_name_is_cfg_bad(self):
        # execs 與 loops 共用名字空間（小格同一個資料夾）：同名＝自己的錯、退 1
        r = self.run_d({"loops": {"x": self.long()}, "execs": {"x": "long"}, "max": 1})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-daemon: ") and "loops 與 execs" in r.stderr and r.stderr.count("\n") == 1,
                        r.stderr)
        self.assertFalse((self.s / "loops" / "x").exists())

    def test_execs_adopted_after_crash(self):
        # adopt 接回 execs 那張表的列（pid＋started_at_ticks 對得上），不重起
        p = self.start({"state": "daemon_state.json", "ctl": "daemon_ctl.json", "execs": {"a": "long"}})
        x = until(lambda: (self.s / "loops" / "a" / "starts").exists() and self.xkids())
        pid = x["a"]["pid"]
        p.kill()
        p.wait()
        p2 = self.start()
        time.sleep(1)
        self.assertEqual((self.xkids()["a"]["pid"], len((self.s / "loops" / "a" / "starts").read_text().split())), (pid, 1))
        self.ctl({"stopped": True})
        out, err = p2.communicate(timeout=30)
        a = [(d["phase"], d["pid"], d["code"], d["signal"]) for d in logs(out)]
        # 接回的也印一行 running；不是自己的子行程，結束那行 code／signal 是 null（11-02）
        self.assertEqual((p2.returncode, alive(pid), self.xkids(), a),
                         (0, False, {}, [("running", pid, None, None), ("stopped", pid, None, None)]))

    def test_max1_loop_still_runs(self):
        # ①（使用者 10-30「包成max:1也是可以」）：{"exec": X, "max": 1} 的 loop 型照舊能跑，列在 loops 表、小格有 loop.json
        self.prog("job", 'echo x >> "$AOS_STACK/runs"\n')
        r = self.run_d({"state": "daemon_state.json", "max": 15, "interval_ms": 100, "loops": {"bob": {"exec": "job", "max": 1}}})
        b = ended(r.stdout)["bob"]
        self.assertEqual((r.returncode, r.stderr, b["table"], b["phase"], b["code"], self.lstate()["execs"]),
                         (0, "", "loops", "done", 0, {}))
        self.assertEqual(((self.s / "loops" / "bob" / "runs").read_text(), (self.s / "loops" / "bob" / "loop.json").is_file()), ("x\n", True))

    # ---- 10-30 eca 子項的工作區 ws（thinking 2026-10-30-eca 衝突 1、實作步驟 1；N-28／N-54 補草稿）

    def ws_run(self, doc, daemon_ws=None):
        # 子項印出自己看到的 AOS_WS；跑 1.5 秒收工
        if not (self.t / "pw").exists():
            self.prog("pw", 'printf %s "$AOS_WS" > "$AOS_STACK/ws"\n')
        env = {"AOS_STACK": str(self.s)}
        if daemon_ws:
            env["AOS_WS"] = daemon_ws
        return self.run_d(dict({"state": "daemon_state.json", "max": 15, "interval_ms": 100}, **doc), env=env)

    def test_ws_execs_child_sees_it(self):
        # execs 子項寫 ws：子程式看到的 AOS_WS 等於它，loops_state 的列記著
        w = self.t / "w1"
        w.mkdir()
        r = self.ws_run({"execs": {"j": {"exec": "pw", "ws": str(w)}}}, daemon_ws=str(self.t))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(((self.s / "loops" / "j" / "ws").read_text(), ended(r.stdout)["j"]["ws"]), (str(w), str(w)))

    def test_ws_loop_child_sees_it(self):
        # loop 子項寫 ws：同上，而且 ws 不灌進小格的 loop.json（不是 loop 的 key）
        w = self.t / "w2"
        w.mkdir()
        r = self.ws_run({"loops": {"bob": {"exec": "pw", "max": 1, "ws": str(w)}}}, daemon_ws=str(self.t))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(((self.s / "loops" / "bob" / "ws").read_text(), ended(r.stdout)["bob"]["ws"]), (str(w), str(w)))
        self.assertNotIn("ws", json.loads((self.s / "loops" / "bob" / "loop.json").read_text()))

    def test_ws_unset_inherits_daemon(self):
        # 沒寫 ws＝照舊繼承 daemon 的 AOS_WS；列上不寫 ws 這欄（形狀同 10-30 前）
        d = self.t / "dws"
        d.mkdir()
        r = self.ws_run({"loops": {"bob": {"exec": "pw", "max": 1}}, "execs": {"j": "pw"}}, daemon_ws=str(d))
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(((self.s / "loops" / "bob" / "ws").read_text(), (self.s / "loops" / "j" / "ws").read_text()), (str(d), str(d)))
        self.assertEqual({n: "ws" in d for n, d in ended(r.stdout).items()}, {"bob": False, "j": False})

    def test_ws_relative_from_daemon_cwd(self):
        # 相對的 ws 從 daemon 的 cwd 算（daemon.json、loops_ctl 的 *_added 都一樣）；型別錯＝CfgBad 退 1
        for n in ("r1", "r2", "r3"):
            (self.t / "rel" / n).mkdir(parents=True)
        self.prog("pw", 'printf %s "$AOS_WS" > "$AOS_STACK/ws"\n')
        self.lctl({"loops_added": {"c": {"exec": "pw", "max": 1, "ws": "./rel/x/../r3"}}})
        r = self.ws_run({"loops": {"a": {"exec": "pw", "max": 1, "ws": "rel/r1"}}, "execs": {"b": {"exec": "pw", "ws": "rel/r2"}}})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        for n, rel in (("a", "r1"), ("b", "r2"), ("c", "r3")):
            self.assertEqual((self.s / "loops" / n / "ws").read_text(), str(self.t / "rel" / rel), n)
        r = self.run_d({"max": 1, "execs": {"b": {"exec": "pw", "ws": 3}}})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-daemon: ") and "ws" in r.stderr, r.stderr)


if __name__ == "__main__":
    unittest.main()
