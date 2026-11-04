"""aos-daemon-ctl：把東西掛到 aos-daemon 上（10-30，使用者「或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop」）。
哪個 daemon＝--daemon ＞ $AOS_DAEMON（N-63；11-04 晚從 --daemon-stack／AOS_DAEMON_STACK 改名、不留別名），值＝daemon 的 $AOS_STACK；投信進 <D>/procs_ctl_mailbox/；
ls 讀 procs_state.json 的一張表（11-03 loops／execs 統稱 procs，thinking 2026-11-03-procs：信 procs_added／procs_removed／procs_stopped／procs_started、
ls 沒有種類欄、--json 印 {"procs"}、add --stack、loop 型一定帶 ctl／state、stop／start／pause／resume、exec 型的那幾個＝CtlMissing、where 讀列上的 stack）。
10-30 eca 第 2 步：add --ws（子項的 ws）、ls 多一欄 ws；11-03 起不碰 <WS>/.stack（捷徑拿掉），改用 where --stack 名字 找子項的 stack（只認表上的）。
11-02（使用者「把--kind刪掉，XXX後面可以接-- ... 也就是附加argv參數。改成子項結束後不留名單」）：--kind 拿掉（＝FlagUnknown）、
`add XXX -- 參數...` 進 procs_added、loop 型帶參數＝ArgumentsBad；子項結束就不在表上，結束碼看 daemon 的 log（--enable-logs、stdout）；
ls 另判 daemon 活著（pid＋started_at_ticks＋boot_id），沒在跑＝stderr 一句注意、照樣列；做完的同名再 add＝重新起（不用先 rm）。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import tool, path_with  # noqa: E402
DAEMON = tool("aos-daemon")
CTL = tool("aos-daemon-ctl")
WAIT_GO = 'while [ ! -e "$GO" ]; do sleep 0.05; done\n'   # 等測試建 $GO 才往下（讓它在表上待著）


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


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
        self.go = self.t / "go"
        self.p = None
        self.addCleanup(self._t.cleanup)
        self.addCleanup(self.stop)

    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.send_signal(signal.SIGTERM)
            self.p.communicate(timeout=30)

    def start(self):
        (self.t / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                        "procs_ctl_mailbox": "procs_ctl_mailbox"}))
        with open(self.t / "log", "w") as out:   # daemon 的 log（--enable-logs）：子項起來一行、結束一行
            self.p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t),
                                      env=env_of({"AOS_STACK": str(self.s), "GO": str(self.go)}),
                                      stdout=out, stderr=subprocess.PIPE, text=True)
        self.assertTrue(until(lambda: (self.s / "procs_ctl_mailbox" / "new").is_dir() and (self.s / "procs_state.json").is_file()))

    def logs(self):
        rows = []
        for l in (self.t / "log").read_text().splitlines():
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if isinstance(d, dict) and "name" in d and "phase" in d:
                rows.append(d)
        return rows

    def ended(self):
        """{名字: 最後一次結束那行}（done／stopped）。"""
        return {d["name"]: d for d in self.logs() if d["phase"] in ("done", "stopped")}

    def ctl(self, *args, env=None, cwd=None):
        e = env_of({"AOS_DAEMON": str(self.s)} if env is None else env)
        return subprocess.run([CTL, *args], cwd=str(cwd or self.t), env=e, capture_output=True, text=True, timeout=30)

    def tables(self):
        r = self.ctl("ls", "--json")
        return json.loads(r.stdout)

    def prog(self, name, body, loop=None):
        d = self.t / name
        d.mkdir()
        (d / "_entry").write_text("#!/bin/sh\n" + body)
        (d / "_entry").chmod(0o755)
        if loop is not None:
            (d / "loop.json").write_text(json.dumps(loop))
        return d

    def test_errors(self):
        self.prog("job", "exit 0\n")
        self.prog("ag", "exit 0\n", loop={"exec": "x", "max": 1})
        for args, env, code in ((("ls",), {}, "DaemonMissing"), (("--daemon", str(self.t / "no"), "ls"), None, "DaemonMissing"),
                                (("--daemon-stack", str(self.s), "ls"), None, "FlagUnknown"),       # 11-04 晚舊旗標不留別名
                                (("ls",), {"AOS_DAEMON_STACK": str(self.s)}, "DaemonMissing"),     # 11-04 晚只設舊名
                                (("add", "x"), None, "PathMissing"), (("ls",), None, "StateMissing"),
                                (("frob",), None, "CommandUnknown"), ((), None, "ArgumentsBad"), (("rm",), None, "ArgumentsBad"),
                                (("add", "--kind", "loop", "job"), None, "FlagUnknown"),     # 11-02 --kind 拿掉
                                (("add", "job", "a"), None, "ArgumentsBad"),                 # XXX 後面只能接 --
                                (("add", "job", "--name", "n"), None, "ArgumentsBad"),
                                (("add", "ag", "--", "a"), None, "ArgumentsBad")):           # loop 型不收參數
            r = self.ctl(*args, env=env)
            self.assertEqual((r.returncode, r.stdout, r.stderr.count("\n")), (1, "", 1), (args, r.stderr))
            self.assertTrue(r.stderr.startswith("aos-daemon-ctl: %s " % code), (args, r.stderr))
        self.assertIn("loop.json 的 exec", self.ctl("add", "ag", "--", "a").stderr)
        self.assertIn("改設 AOS_DAEMON", self.ctl("ls", env={"AOS_DAEMON_STACK": str(self.s)}).stderr)   # 提示改名
        self.assertNotIn("改名", self.ctl("ls", env={}).stderr)
        r = self.ctl("add", "job")   # stack 在、但沒開信箱
        self.assertEqual(r.returncode, 1)
        self.assertIn('"procs_ctl_mailbox": "procs_ctl_mailbox"', r.stderr)

    def test_add_exec_ls_then_same_name_again(self):
        # 沒 loop.json 的資料夾＝exec 型（跑一次）：跑著時 ls 一行；結束後從表上拿掉（11-02）、結束碼在 daemon 的 log；
        # 做完的同名再 add＝重新起，不用先 rm 等一下（試驗場的坑，11-02 信箱模式改成 done 從期望表拿掉）
        self.prog("job", 'echo "$$" >> "$AOS_STACK/runs"\n' + WAIT_GO + "exit 3\n")
        self.start()
        r = self.ctl("add", "job")
        self.assertEqual((r.returncode, r.stderr, r.stdout.count("\n")), (0, "", 1))   # 印信件名稱
        x = until(lambda: self.tables()["procs"].get("job", {}).get("phase") == "running" and self.tables())
        self.assertTrue(x)
        self.assertFalse((self.s / "procs" / "job" / "loop.json").exists())
        r = self.ctl("ls")
        self.assertEqual((r.stdout, r.stderr), ("job\trunning\t%d\t-\t-\n" % x["procs"]["job"]["pid"], ""))   # 沒有種類欄；最後一欄 ws
        self.go.write_text("")
        self.assertTrue(until(lambda: "job" in self.ended() and self.tables() == {"procs": {}}))
        e = self.ended()["job"]
        self.assertEqual(("table" in e, e["phase"], e["code"], e["pid"]), (False, "done", 3, x["procs"]["job"]["pid"]))
        self.assertEqual(self.ctl("ls").stdout, "")
        self.assertEqual(self.ctl("add", "job").returncode, 0)   # 同名再來，沒 rm
        self.assertTrue(until(lambda: [d["phase"] for d in self.logs()].count("done") == 2))
        self.assertEqual((self.s / "procs" / "job" / "runs").read_text().count("\n"), 2)
        self.assertEqual(self.ctl("rm", "job").returncode, 0)   # 已經不在了：照樣送出、不報

    def test_add_args_exec_type(self):
        # 11-02：add XXX -- 參數...＝procs_added {名字: [XXX, 參數...]}，參數原樣（- 開頭、空白都照給）；帶 --ws 的＝{"exec": [...], "ws": WS}
        self.prog("job", 'for a in "$@"; do printf "%s|" "$a"; done > "$AOS_STACK/args"\nprintf %s "$AOS_WS" > "$AOS_STACK/ws"\n')
        w = self.t / "w"
        w.mkdir()
        self.start()
        for args in (("job", "--", "a", "b c", "--x", "--"), ("--name", "j2", "--ws", "w", "job", "--", "p"), ("--name", "j3", "job", "--")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
        self.assertTrue(until(lambda: set(self.ended()) == {"job", "j2", "j3"}), self.logs())
        self.assertEqual([(self.s / "procs" / n / "args").read_text() for n in ("job", "j2", "j3")], ["a|b c|--x|--|", "p|", ""])
        self.assertEqual(((self.s / "procs" / "j2" / "ws").read_text(), self.ended()["j2"]["ws"]), (str(w), str(w)))

    def test_add_loop_runs_its_loop_json(self):
        # 有 loop.json＝loop 型：子 loop 直接跑 XXX 的 loop.json（相對 exec 照 XXX 轉絕對、單子指回 XXX/loop.json#/exec＝cwd 是 XXX）；--name 改名
        d = self.prog("ag", "exit 0\n", loop={"exec": "loop.json#/b", "max": 2, "_entry": ["x"],
                                              "b": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}})
        d2 = self.prog("ag2", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'pwd > "$AOS_STACK/pwd"']}, "max": 1})
        self.start()
        self.assertEqual(self.ctl("add", "ag").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "two", str(d2)).returncode, 0)
        self.assertTrue(until(lambda: set(self.ended()) == {"ag", "two"}), self.logs())
        self.assertEqual({n: (r["phase"], r["code"]) for n, r in self.ended().items()}, {"ag": ("done", 0), "two": ("done", 0)})
        self.assertTrue(until(lambda: self.tables() == {"procs": {}}))
        self.assertEqual((self.s / "procs" / "ag" / "runs").read_text(), "x\nx\n")
        cell = json.loads((self.s / "procs" / "ag" / "loop.json").read_text())
        self.assertEqual((cell["exec"], cell["max"], cell["_entry"][0], cell["ctl"], cell["state"]),
                         (os.path.realpath(d) + "/loop.json#/b", 2, "aos-loop", "ctl.json", "state.json"))   # 11-03 loop 型一定帶 ctl／state
        self.assertEqual((self.s / "procs" / "two" / "pwd").read_text().strip(), os.path.realpath(d2))

    def test_flag_over_env(self):
        # --daemon 蓋過 AOS_DAEMON
        self.prog("job", 'echo x >> "$AOS_STACK/runs"\n')
        self.start()
        r = self.ctl("--daemon", str(self.s), "add", "job", env={"AOS_DAEMON": str(self.t / "nowhere")})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(until(lambda: self.ended().get("job", {}).get("phase") == "done"))
        self.assertEqual((self.s / "procs" / "job" / "runs").read_text(), "x\n")

    def test_ls_notes_daemon_not_running(self):
        # 11-02（使用者「要看一個proc是否還活著，除去linux底層proc機制外，我們的aos-daemon-ctl問詢也是一個方式，兩者並存」）：
        # procs_state 頂層的 pid＋started_at_ticks（＋boot_id）對不上 /proc＝stderr 一句注意、照樣列、退 0；--json 不加欄
        self.prog("job", WAIT_GO)
        self.start()
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        x = until(lambda: self.tables()["procs"].get("job") and self.tables())
        self.assertTrue(x)
        pid = x["procs"]["job"]["pid"]
        self.addCleanup(lambda: self.go.write_text(""))
        self.assertEqual(self.ctl("ls").stderr, "")
        self.p.kill()   # 不收子項、不改表（像 crash）
        self.p.communicate(timeout=30)
        note = "aos-daemon-ctl: 注意 daemon 沒在跑（pid %d）；表是它最後寫的\n" % self.p.pid
        r = self.ctl("ls")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "job\trunning\t%d\t-\t-\n" % pid, note))
        r = self.ctl("ls", "--json")
        self.assertEqual((r.returncode, set(json.loads(r.stdout)), r.stderr), (0, {"procs"}, note))
        st = json.loads((self.s / "procs_state.json").read_text())
        (self.s / "procs_state.json").write_text(json.dumps(dict(st, boot_id="not-this-boot", pid=os.getpid(),
                                                                 started_at_ticks=int(Path("/proc/self/stat").read_text().rpartition(")")[2].split()[19]))))
        self.assertIn("注意 daemon 沒在跑", self.ctl("ls").stderr)   # pid 對得上（這支測試）但 boot_id 不對＝不算

    # ---- 10-30 eca 第 2 步：--ws（thinking 2026-10-30-eca 衝突 1、3）

    def wsprog(self, name, loop=None):
        # 子程式印出自己看到的 AOS_WS
        return self.prog(name, 'printf %s "$AOS_WS" > "$AOS_STACK/ws"\n', loop=loop)

    def test_add_ws_exec_and_loop_and_env(self):
        # add --ws：exec 型、loop 型的子項都帶 ws；子程式看到的 AOS_WS 對；log 那行帶 ws（11-02 起結束的不在表上）
        self.wsprog("job")
        self.prog("ag", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'printf %s "$AOS_WS" > "$AOS_STACK/ws"']}, "max": 1})
        ws = [self.t / ("w%d" % i) for i in range(3)]
        for w in ws:
            w.mkdir()
        self.start()
        for args in (("--ws", str(ws[0]), "job"), ("--ws", "w1", "ag"), ("--name", "m", "--ws", str(ws[2]), "job")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
        self.assertTrue(until(lambda: set(self.ended()) == {"job", "ag", "m"}), self.logs())
        x = self.ended()
        self.assertEqual((x["job"]["ws"], x["ag"]["ws"], x["m"]["ws"]), tuple(map(str, ws)))
        for n, w in (("job", ws[0]), ("ag", ws[1]), ("m", ws[2])):
            self.assertEqual((self.s / "procs" / n / "ws").read_text(), str(w), n)
        self.assertTrue((self.s / "procs" / "ag" / "loop.json").is_file())
        self.assertFalse((self.s / "procs" / "job" / "loop.json").exists())
        r = self.ctl("add", "--ws", str(self.t / "nope"), "job")
        self.assertEqual((r.returncode, r.stderr.startswith("aos-daemon-ctl: ")), (1, True), r.stderr)

    def test_add_ws_no_stack_link(self):
        # 11-03（使用者「那其實.stack根本不需要放到ws那邊」）：add --ws 不再建 <WS>/.stack 捷徑、rm 不拆；工作區原本有什麼都不動；ls 多一欄 ws
        self.prog("job", 'echo "$AOS_WS" > "$AOS_STACK/ws"\nwhile :; do sleep 0.05; done\n')
        w, w2 = self.t / "proj", self.t / "p2"
        w.mkdir()
        (w2 / ".stack").mkdir(parents=True)
        self.start()
        r = self.ctl("add", "--ws", str(w), "job")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        r = self.ctl("add", "--ws", str(w2), "--name", "b", "job")
        self.assertEqual((r.returncode, r.stderr), (0, ""))               # 不再說「工作區已有 .stack」
        self.assertTrue(until(lambda: (self.s / "procs" / "job" / "ws").exists()))
        self.assertEqual((self.s / "procs" / "job" / "ws").read_text().strip(), str(w))
        self.assertFalse(os.path.lexists(w / ".stack"))
        x = until(lambda: len(self.tables()["procs"]) == 2 and self.tables())
        self.assertEqual(self.ctl("ls").stdout.splitlines()[0], "job\trunning\t%d\t-\t%s" % (x["procs"]["job"]["pid"], w))
        self.assertEqual((self.ctl("rm", "job").returncode, self.ctl("rm", "b").returncode), (0, 0))
        self.assertTrue(until(lambda: self.tables()["procs"] == {}))
        self.assertEqual((os.path.lexists(w / ".stack"), (w2 / ".stack").is_dir()), (False, True))

    def test_where(self):
        # 11-03 where --stack 名字：只認表上的（running、stopping、stopped）→ 印列上的 stack（預設 <D>/procs/<名字>；add --stack 給的）；
        # 表上沒有＝ProcMissing（小格在也一樣）；只認 --stack；procs_state 不在＝StateMissing
        self.prog("job", WAIT_GO)
        self.prog("ag", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", WAIT_GO]}, "max": 1})
        self.assertEqual(self.ctl("where", "--stack", "job").stderr.split()[1], "StateMissing")
        self.start()
        self.addCleanup(lambda: self.go.write_text(""))
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "a", "ag").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "c", "--stack", "mine/c/", "job").returncode, 0)   # 相對的 --stack 從呼叫的 cwd 算
        self.assertTrue(until(lambda: {"job", "a", "c"} <= set(self.tables()["procs"])))
        for n, want in (("job", self.s / "procs" / "job"), ("a", self.s / "procs" / "a"), ("c", self.t / "mine" / "c")):
            r = self.ctl("where", "--stack", n)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, str(want) + "\n", ""), n)
        self.assertFalse((self.s / "procs" / "c").exists())
        r = self.ctl("--daemon", ".", "where", "--stack", "a", env={}, cwd=self.s)   # 相對的 --daemon 照樣印列上的絕對路徑
        self.assertEqual(r.stdout, str(self.s / "procs" / "a") + "\n")
        for args, code in ((("where", "--stack", "nobody"), "ProcMissing"), (("where",), "ArgumentsBad"),
                           (("where", "job"), "ArgumentsBad"), (("where", "--ws", "x"), "FlagUnknown")):
            r = self.ctl(*args)
            self.assertEqual((r.returncode, r.stdout, r.stderr.split()[:2]), (1, "", ["aos-daemon-ctl:", code]), args)
        self.go.write_text("")
        self.assertTrue(until(lambda: self.tables() == {"procs": {}}))
        self.assertTrue((self.s / "procs" / "job").is_dir())          # 小格還在，但表上沒有＝不存在
        self.assertEqual(self.ctl("where", "--stack", "job").stderr.split()[1], "ProcMissing")

    def test_add_inst_points_back(self):
        # 11-01：loop 型的 exec 是內嵌單子＝小格的 exec 換成 <XXX>/loop.json#/exec，跑的時候 AOS_CD 是 XXX
        # （{"$env": "AOS_CD"}、帶 $path 的都照原地解）。單子的相對 cwd（例：表與格放在定義底下的子資料夾）也照原地算
        # （11-03 前用 demo/agent-nia 測這條，它隨 round 一起刪了，改用這裡的 far）
        d = self.prog("odd", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'echo "$0 $1" > "$AOS_STACK/args"',
                                                                 {"$env": "AOS_CD"}, {"$env": "AOS_CD", "$path": "x"}]},
                                               "max": 1})
        far = self.prog("far", "exit 0\n", loop={"exec": {"argv": ["sh", "run.sh", {"$env": "AOS_CD"}], "cwd": "tbl"}, "max": 1})
        (far / "tbl").mkdir()
        (far / "tbl" / "run.sh").write_text('echo "$1 $(pwd)" > "$AOS_STACK/args"\n')
        self.start()
        self.assertEqual(self.ctl("add", "odd").returncode, 0)
        self.assertEqual(self.ctl("add", "far").returncode, 0)
        self.assertTrue(until(lambda: (self.s / "procs" / "far" / "args").is_file() and (self.s / "procs" / "odd" / "args").is_file()))
        self.assertEqual(json.loads((self.s / "procs" / "odd" / "loop.json").read_text())["exec"], os.path.realpath(d) + "/loop.json#/exec")
        self.assertEqual((self.s / "procs" / "odd" / "args").read_text().split(), [os.path.realpath(d), os.path.join(os.path.realpath(d), "x")])
        self.assertEqual(json.loads((self.s / "procs" / "far" / "loop.json").read_text())["exec"], os.path.realpath(far) + "/loop.json#/exec")
        self.assertEqual((self.s / "procs" / "far" / "args").read_text().split(), [os.path.realpath(far), os.path.join(os.path.realpath(far), "tbl")])

    # ---- 11-03 procs（thinking 2026-11-03-procs § 2、2b、2c、§ 6 第一列）

    def fake_daemon(self, rows):
        """不起 daemon：手做一個信箱（new/ 在）與一份 procs_state.json（pid＝這支測試，算活著），看 aos-daemon-ctl 寄了什麼信。"""
        for sub in ("tmp", "new", "cur"):
            (self.s / "procs_ctl_mailbox" / sub).mkdir(parents=True, exist_ok=True)
        ticks = int(Path("/proc/self/stat").read_text().rpartition(")")[2].split()[19])
        (self.s / "procs_state.json").write_text(json.dumps({"ctl_seq": None, "ctl_warning": None, "procs": rows,
                                                             "pid": os.getpid(), "started_at_ticks": ticks}))

    def letters(self):
        """信箱 new/ 裡的信 body（照名字排）；看完清掉。"""
        new = self.s / "procs_ctl_mailbox" / "new"
        out = []
        for d in sorted(new.iterdir()):
            out.append(json.loads((d / "letter.json").read_text())["body"])
            for f in d.iterdir():
                f.unlink()
            d.rmdir()
        return out

    def test_letter_bodies(self):
        # add：loop 型一定帶 ctl／state（只有 exec 的 loop.json 也是）、--stack 從呼叫的 cwd 轉絕對（不驗在不在）、--ws；exec 型沒旗標＝裸目標、
        # 有 --stack／--ws＝{"exec", "ws"?, "stack"?}；rm 只寫 procs_removed；--stack 空＝ArgumentsBad
        self.prog("job", "exit 0\n")
        d = self.prog("ag", "exit 0\n", loop={"exec": "x", "_entry": ["y"]})
        (self.t / "w").mkdir()
        self.fake_daemon({})
        for args in (("ag",), ("--name", "b", "--stack", "st/b", "--ws", "w", "ag"), ("job",), ("--name", "j", "--stack", "/abs/j/", "job", "--", "1"),
                     ("--name", "k", "--ws", "w", "job")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
        self.assertEqual(self.ctl("rm", "ag").returncode, 0)
        x = str(d / "x")
        self.assertEqual(self.letters(), [
            {"procs_added": {"ag": {"exec": x, "ctl": "ctl.json", "state": "state.json"}}},
            {"procs_added": {"b": {"exec": x, "ctl": "ctl.json", "state": "state.json", "ws": str(self.t / "w"), "stack": str(self.t / "st" / "b")}}},
            {"procs_added": {"job": str(self.t / "job")}},
            {"procs_added": {"j": {"exec": [str(self.t / "job"), "1"], "stack": "/abs/j"}}},
            {"procs_added": {"k": {"exec": str(self.t / "job"), "ws": str(self.t / "w")}}},
            {"procs_removed": ["ag"]}])
        self.assertFalse((self.t / "st").exists())                            # 不替人建
        (d / "loop.json").write_text(json.dumps({"exec": "x", "ctl": None, "state": "s.json"}))   # 寫了的照原樣（null 也是）
        self.assertEqual(self.ctl("add", "ag").returncode, 0)
        self.assertEqual(self.letters(), [{"procs_added": {"ag": {"exec": x, "ctl": None, "state": "s.json"}}}])
        for args in (("--stack", "", "job"), ("--stack=", "job")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr.split()[:2]), (1, ["aos-daemon-ctl:", "ArgumentsBad"]), args)
        self.assertEqual(self.letters(), [])

    def test_ctl_missing_and_bodies(self):
        # stop／start／pause／resume：先看它的 stack 有沒有 daemon 寫的 loop.json——沒有（exec 型）＝CtlMissing、不送信、不寫；
        # 表上沒有＝ProcMissing；stop／start 寄 procs_stopped／procs_started；stopped 的列 start 不看 loop.json（stack 可能還沒建）；
        # pause／resume 直接寫它的 ctl（loop.json 的 ctl 那格）{"cmd", "seq": 現有＋1}、印 seq；ctl 是 null＝CtlMissing
        lp, ex, nul = self.t / "lp", self.t / "ex", self.t / "nul"
        for p in (lp, ex, nul):
            p.mkdir()
        (lp / "loop.json").write_text(json.dumps({"exec": "x", "ctl": "c.json", "state": "state.json"}))
        (nul / "loop.json").write_text(json.dumps({"exec": "x", "ctl": None}))
        run = {"pid": 1, "started_at_ticks": 1, "phase": "running", "code": None, "signal": None}
        self.fake_daemon({"lp": dict(run, stack=str(lp)), "ex": dict(run, stack=str(ex)), "nul": dict(run, stack=str(nul)),
                          "zz": {"pid": None, "started_at_ticks": None, "phase": "stopped", "code": None, "signal": None,
                                 "stack": str(self.t / "never")}})
        for cmd in ("stop", "start", "pause", "resume"):
            r = self.ctl(cmd, "ex")
            self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", "aos-daemon-ctl: CtlMissing ex 沒有 ctl（exec 型只有跑和拔）\n"), cmd)
            self.assertEqual(self.ctl(cmd, "nobody").stderr.split()[1], "ProcMissing", cmd)
            self.assertEqual(self.ctl(cmd).stderr.split()[1], "ArgumentsBad", cmd)
        for cmd in ("pause", "resume", "stop"):
            self.assertEqual(self.ctl(cmd, "nul").stderr.split()[1], "CtlMissing", cmd)
        self.assertEqual(list((ex).iterdir()), [])
        self.assertEqual(self.letters(), [])
        for cmd in ("stop", "start"):
            r = self.ctl(cmd, "lp")
            self.assertEqual((r.returncode, r.stderr, r.stdout.count("\n")), (0, "", 1), cmd)   # 印信件名稱
        self.assertEqual(self.ctl("start", "zz").returncode, 0)
        self.assertEqual(self.letters(), [{"procs_stopped": ["lp"]}, {"procs_started": ["lp"]}, {"procs_started": ["zz"]}])
        r = self.ctl("pause", "lp")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "1\n", ""))
        self.assertEqual(json.loads((lp / "c.json").read_text()), {"cmd": "pause", "seq": 1})
        (lp / "c.json").write_text(json.dumps({"cmd": "stop", "seq": 7}))
        self.assertEqual(self.ctl("resume", "lp").stdout, "8\n")
        self.assertEqual(json.loads((lp / "c.json").read_text()), {"cmd": "resume", "seq": 8})
        self.assertEqual(sorted(p.name for p in lp.iterdir()), ["c.json", "loop.json"])   # 暫存改名，不留 .c.json

    def test_stop_start_pause_resume(self):
        # 真的 daemon：loop 型（只有 exec 的 loop.json＝補了 ctl／state，照 loop 一直跑）掛在 --stack 給的地方；
        # pause→它的 state.json paused、不再跑；resume→接著跑；stop→跑完這次退 0、表上 stopped（pid -、code 0）、where 照找得到；
        # start→同一個 stack 再起；rm→表上沒了、stack 留著。exec 型的 stop／pause＝CtlMissing
        self.prog("lp", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"; sleep 0.05']}, "interval_ms": 50})
        self.prog("job", WAIT_GO)
        self.addCleanup(lambda: self.go.write_text(""))
        self.start()
        st = self.t / "c"
        self.assertEqual(self.ctl("add", "--stack", "c", "lp").returncode, 0)
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        x = until(lambda: {"lp", "job"} <= set(self.tables()["procs"]) and self.tables())
        self.assertTrue(x)
        self.assertEqual(self.ctl("where", "--stack", "lp").stdout, str(st) + "\n")
        runs = lambda: (st / "runs").read_text().count("\n")
        loop_state = lambda: json.loads((st / "state.json").read_text())
        self.assertTrue(until(lambda: runs() >= 2))                          # 一直跑＝loop 型
        for cmd in ("stop", "pause", "resume"):
            self.assertEqual(self.ctl(cmd, "job").stderr.split()[1], "CtlMissing", cmd)
        self.assertEqual(self.ctl("pause", "lp").returncode, 0)
        self.assertTrue(until(lambda: loop_state()["phase"] == "paused"))
        n = runs()
        time.sleep(0.5)
        self.assertEqual(runs(), n)
        self.assertEqual(self.ctl("resume", "lp").returncode, 0)
        self.assertTrue(until(lambda: runs() > n))
        pid = x["procs"]["lp"]["pid"]
        self.assertEqual(self.ctl("stop", "lp").returncode, 0)
        self.assertTrue(until(lambda: self.tables()["procs"]["lp"]["phase"] == "stopped"))
        self.assertEqual(self.ctl("ls").stdout.splitlines()[0], "lp\tstopped\t-\t0\t-")
        self.assertEqual(self.ctl("where", "--stack", "lp").stdout, str(st) + "\n")
        n = runs()
        time.sleep(0.5)
        self.assertEqual((runs(), loop_state()["phase"]), (n, "stopped"))
        self.assertEqual(self.ctl("start", "lp").returncode, 0)
        y = until(lambda: self.tables()["procs"]["lp"]["phase"] == "running" and self.tables())
        self.assertTrue(y)
        self.assertNotEqual(y["procs"]["lp"]["pid"], pid)
        self.assertTrue(until(lambda: runs() > n))
        self.assertEqual(self.ctl("rm", "lp").returncode, 0)
        self.assertTrue(until(lambda: "lp" not in self.tables()["procs"]))
        self.assertEqual(self.ctl("where", "--stack", "lp").stderr.split()[1], "ProcMissing")
        self.assertTrue((st / "loop.json").is_file())                        # rm 不清 stack

    def test_sleep_wake(self):
        # 11-03 sleep／wake（procs § 8）：daemon 收工時還在跑的 loop 型＝表上 sleeping（ls 的 pid 印 -、where 照找得到），exec 型拿掉；
        # daemon 再開＝用同一個 stack 自動起來接著跑
        self.prog("lp", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"; sleep 0.05']}, "interval_ms": 50})
        self.prog("job", WAIT_GO)
        self.addCleanup(lambda: self.go.write_text(""))
        self.start()
        st = self.t / "c"
        self.assertEqual(self.ctl("add", "--stack", "c", "lp").returncode, 0)
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        self.assertTrue(until(lambda: {"lp", "job"} <= set(self.tables()["procs"])))
        runs = lambda: (st / "runs").read_text().count("\n")
        self.assertTrue(until(lambda: runs() >= 1))
        self.stop()                                                          # SIGTERM 收工
        r = self.ctl("ls")
        self.assertEqual(r.stdout.split("\t")[:3], ["lp", "sleeping", "-"])
        self.assertEqual((len(r.stdout.splitlines()), "沒在跑" in r.stderr), (1, True))
        self.assertEqual(self.ctl("where", "--stack", "lp").stdout, str(st) + "\n")
        n = runs()
        self.start()
        self.assertTrue(until(lambda: self.tables()["procs"]["lp"]["phase"] == "running" and runs() > n))
        self.assertEqual((set(self.tables()["procs"]), self.tables()["procs"]["lp"]["stack"]), ({"lp"}, str(st)))


if __name__ == "__main__":
    unittest.main()
