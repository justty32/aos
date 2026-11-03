"""aos-daemon-ctl：把東西掛到 aos-daemon 上（10-30，使用者「或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop」）。
哪個 daemon＝--daemon-stack ＞ $AOS_DAEMON_STACK（N-63；11-02 從 --daemon／AOS_DAEMON 改名、不留別名），值＝daemon 的 $AOS_STACK；投信進 <D>/loops_ctl_mailbox/（信箱，11-02 前叫 loops_mailbox）；
ls 讀 loops_state.json 兩張表。
10-30 eca 第 2 步：add --ws（子項的 ws）、ls 多一欄 ws；11-03 起不碰 <WS>/.stack（捷徑拿掉），改用 where --stack 名字 找子項的 stack（只認表上的）。
11-02（使用者「把--kind刪掉，XXX後面可以接-- ... 也就是附加argv參數。改成子項結束後不留名單」）：--kind 拿掉（＝FlagUnknown）、
`add XXX -- 參數...` 進 execs_added、loop 型帶參數＝ArgumentsBad；子項結束就不在表上，結束碼看 daemon 的 log（--enable-logs、stdout）；
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
                                                        "loops_ctl_mailbox": "loops_ctl_mailbox"}))
        with open(self.t / "log", "w") as out:   # daemon 的 log（--enable-logs）：子項起來一行、結束一行
            self.p = subprocess.Popen([DAEMON, "--enable-logs", "daemon.json"], cwd=str(self.t),
                                      env=env_of({"AOS_STACK": str(self.s), "GO": str(self.go)}),
                                      stdout=out, stderr=subprocess.PIPE, text=True)
        self.assertTrue(until(lambda: (self.s / "loops_ctl_mailbox" / "new").is_dir() and (self.s / "loops_state.json").is_file()))

    def logs(self):
        rows = []
        for l in (self.t / "log").read_text().splitlines():
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if isinstance(d, dict) and "name" in d and "table" in d:
                rows.append(d)
        return rows

    def ended(self):
        """{名字: 最後一次結束那行}（done／stopped）。"""
        return {d["name"]: d for d in self.logs() if d["phase"] in ("done", "stopped")}

    def ctl(self, *args, env=None, cwd=None):
        e = env_of({"AOS_DAEMON_STACK": str(self.s)} if env is None else env)
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
        for args, env, code in ((("ls",), {}, "DaemonMissing"), (("--daemon-stack", str(self.t / "no"), "ls"), None, "DaemonMissing"),
                                (("--daemon", str(self.s), "ls"), None, "FlagUnknown"),       # 11-02 舊旗標不留別名
                                (("ls",), {"AOS_DAEMON": str(self.s)}, "DaemonMissing"),     # 11-02 只設舊名
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
        self.assertIn("AOS_DAEMON_STACK", self.ctl("ls", env={"AOS_DAEMON": str(self.s)}).stderr)   # 提示改名
        self.assertNotIn("改名", self.ctl("ls", env={}).stderr)
        r = self.ctl("add", "job")   # stack 在、但沒開信箱
        self.assertEqual(r.returncode, 1)
        self.assertIn('"loops_ctl_mailbox": "loops_ctl_mailbox"', r.stderr)

    def test_add_exec_ls_then_same_name_again(self):
        # 沒 loop.json 的資料夾＝exec 型（execs）：跑著時 ls 一行；結束後從表上拿掉（11-02）、結束碼在 daemon 的 log；
        # 做完的同名再 add＝重新起，不用先 rm 等一下（試驗場的坑，11-02 信箱模式改成 done 從期望表拿掉）
        self.prog("job", 'echo "$$" >> "$AOS_STACK/runs"\n' + WAIT_GO + "exit 3\n")
        self.start()
        r = self.ctl("add", "job")
        self.assertEqual((r.returncode, r.stderr, r.stdout.count("\n")), (0, "", 1))   # 印信號
        x = until(lambda: self.tables()["execs"].get("job", {}).get("phase") == "running" and self.tables())
        self.assertTrue(x)
        self.assertFalse((self.s / "loops" / "job" / "loop.json").exists())
        r = self.ctl("ls")
        self.assertEqual((r.stdout, r.stderr), ("job\texec\trunning\t%d\t-\t-\n" % x["execs"]["job"]["pid"], ""))   # 最後一欄 ws
        self.go.write_text("")
        self.assertTrue(until(lambda: "job" in self.ended() and self.tables() == {"loops": {}, "execs": {}}))
        e = self.ended()["job"]
        self.assertEqual((e["table"], e["phase"], e["code"], e["pid"]), ("execs", "done", 3, x["execs"]["job"]["pid"]))
        self.assertEqual(self.ctl("ls").stdout, "")
        self.assertEqual(self.ctl("add", "job").returncode, 0)   # 同名再來，沒 rm
        self.assertTrue(until(lambda: [d["phase"] for d in self.logs()].count("done") == 2))
        self.assertEqual((self.s / "loops" / "job" / "runs").read_text().count("\n"), 2)
        self.assertEqual(self.ctl("rm", "job").returncode, 0)   # 已經不在了：照樣送出、不報

    def test_add_args_go_to_execs(self):
        # 11-02：add XXX -- 參數...＝execs_added {名字: [XXX, 參數...]}，參數原樣（- 開頭、空白都照給）；帶 --ws 的＝{"exec": [...], "ws": WS}
        self.prog("job", 'for a in "$@"; do printf "%s|" "$a"; done > "$AOS_STACK/args"\nprintf %s "$AOS_WS" > "$AOS_STACK/ws"\n')
        w = self.t / "w"
        w.mkdir()
        self.start()
        for args in (("job", "--", "a", "b c", "--x", "--"), ("--name", "j2", "--ws", "w", "job", "--", "p"), ("--name", "j3", "job", "--")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
        self.assertTrue(until(lambda: set(self.ended()) == {"job", "j2", "j3"}), self.logs())
        self.assertEqual([(self.s / "loops" / n / "args").read_text() for n in ("job", "j2", "j3")], ["a|b c|--x|--|", "p|", ""])
        self.assertEqual(((self.s / "loops" / "j2" / "ws").read_text(), self.ended()["j2"]["ws"]), (str(w), str(w)))

    def test_add_loop_runs_its_loop_json(self):
        # 有 loop.json＝loop 型：子 loop 直接跑 XXX 的 loop.json（相對 exec 照 XXX 轉絕對、單子指回 XXX/loop.json#/exec＝cwd 是 XXX）；--name 改名
        d = self.prog("ag", "exit 0\n", loop={"exec": "loop.json#/b", "max": 2, "_entry": ["x"],
                                              "b": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}})
        d2 = self.prog("ag2", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'pwd > "$AOS_STACK/pwd"']}, "max": 1})
        self.start()
        self.assertEqual(self.ctl("add", "ag").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "two", str(d2)).returncode, 0)
        self.assertTrue(until(lambda: set(self.ended()) == {"ag", "two"}), self.logs())
        self.assertEqual({n: (r["table"], r["phase"], r["code"]) for n, r in self.ended().items()},
                         {"ag": ("loops", "done", 0), "two": ("loops", "done", 0)})
        self.assertTrue(until(lambda: self.tables() == {"loops": {}, "execs": {}}))
        self.assertEqual((self.s / "loops" / "ag" / "runs").read_text(), "x\nx\n")
        cell = json.loads((self.s / "loops" / "ag" / "loop.json").read_text())
        self.assertEqual((cell["exec"], cell["max"], cell["_entry"][0]), (os.path.realpath(d) + "/loop.json#/b", 2, "aos-loop"))
        self.assertEqual((self.s / "loops" / "two" / "pwd").read_text().strip(), os.path.realpath(d2))

    def test_flag_over_env(self):
        # --daemon-stack 蓋過 AOS_DAEMON_STACK
        self.prog("job", 'echo x >> "$AOS_STACK/runs"\n')
        self.start()
        r = self.ctl("--daemon-stack", str(self.s), "add", "job", env={"AOS_DAEMON_STACK": str(self.t / "nowhere")})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(until(lambda: self.ended().get("job", {}).get("phase") == "done"))
        self.assertEqual((self.s / "loops" / "job" / "runs").read_text(), "x\n")

    def test_ls_notes_daemon_not_running(self):
        # 11-02（使用者「要看一個proc是否還活著，除去linux底層proc機制外，我們的aos-daemon-ctl問詢也是一個方式，兩者並存」）：
        # loops_state 頂層的 pid＋started_at_ticks（＋boot_id）對不上 /proc＝stderr 一句注意、照樣列、退 0；--json 不加欄
        self.prog("job", WAIT_GO)
        self.start()
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        x = until(lambda: self.tables()["execs"].get("job") and self.tables())
        self.assertTrue(x)
        pid = x["execs"]["job"]["pid"]
        self.addCleanup(lambda: self.go.write_text(""))
        self.assertEqual(self.ctl("ls").stderr, "")
        self.p.kill()   # 不收子項、不改表（像 crash）
        self.p.communicate(timeout=30)
        note = "aos-daemon-ctl: 注意 daemon 沒在跑（pid %d）；表是它最後寫的\n" % self.p.pid
        r = self.ctl("ls")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "job\texec\trunning\t%d\t-\t-\n" % pid, note))
        r = self.ctl("ls", "--json")
        self.assertEqual((r.returncode, set(json.loads(r.stdout)), r.stderr), (0, {"loops", "execs"}, note))
        st = json.loads((self.s / "loops_state.json").read_text())
        (self.s / "loops_state.json").write_text(json.dumps(dict(st, boot_id="not-this-boot", pid=os.getpid(),
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
        self.assertEqual(({n: x[n]["table"] for n in x}, (x["job"]["ws"], x["ag"]["ws"], x["m"]["ws"])),
                         ({"job": "execs", "ag": "loops", "m": "execs"}, tuple(map(str, ws))))
        for n, w in (("job", ws[0]), ("ag", ws[1]), ("m", ws[2])):
            self.assertEqual((self.s / "loops" / n / "ws").read_text(), str(w), n)
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
        self.assertTrue(until(lambda: (self.s / "loops" / "job" / "ws").exists()))
        self.assertEqual((self.s / "loops" / "job" / "ws").read_text().strip(), str(w))
        self.assertFalse(os.path.lexists(w / ".stack"))
        x = until(lambda: len(self.tables()["execs"]) == 2 and self.tables())
        self.assertEqual(self.ctl("ls").stdout.splitlines()[0], "job\texec\trunning\t%d\t-\t%s" % (x["execs"]["job"]["pid"], w))
        self.assertEqual((self.ctl("rm", "job").returncode, self.ctl("rm", "b").returncode), (0, 0))
        self.assertTrue(until(lambda: self.tables()["execs"] == {}))
        self.assertEqual((os.path.lexists(w / ".stack"), (w2 / ".stack").is_dir()), (False, True))

    def test_where(self):
        # 11-03 where --stack 名字：只認表上的（loops、execs；running、stopping）→ 印 <D>/loops/<名字>；表上沒有＝ProcMissing（小格在也一樣）；
        # 只認 --stack；loops_state 不在＝StateMissing；daemon 沒在跑＝同 ls 一句注意、照表印
        self.prog("job", WAIT_GO)
        self.prog("ag", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", WAIT_GO]}, "max": 1})
        self.assertEqual(self.ctl("where", "--stack", "job").stderr.split()[1], "StateMissing")
        self.start()
        self.addCleanup(lambda: self.go.write_text(""))
        self.assertEqual(self.ctl("add", "job").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "a", "ag").returncode, 0)
        self.assertTrue(until(lambda: "job" in self.tables()["execs"] and "a" in self.tables()["loops"]))
        for n in ("job", "a"):
            r = self.ctl("where", "--stack", n)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, str(self.s / "loops" / n) + "\n", ""), n)
        r = self.ctl("--daemon-stack", ".", "where", "--stack", "a", env={}, cwd=self.s)   # 相對的 --daemon-stack 也印絕對路徑
        self.assertEqual(r.stdout, str(self.s / "loops" / "a") + "\n")
        for args, code in ((("where", "--stack", "nobody"), "ProcMissing"), (("where",), "ArgumentsBad"),
                           (("where", "job"), "ArgumentsBad"), (("where", "--ws", "x"), "FlagUnknown")):
            r = self.ctl(*args)
            self.assertEqual((r.returncode, r.stdout, r.stderr.split()[:2]), (1, "", ["aos-daemon-ctl:", code]), args)
        self.go.write_text("")
        self.assertTrue(until(lambda: self.tables() == {"loops": {}, "execs": {}}))
        self.assertTrue((self.s / "loops" / "job").is_dir())          # 小格還在，但表上沒有＝不存在
        self.assertEqual(self.ctl("where", "--stack", "job").stderr.split()[1], "ProcMissing")

    def test_add_inst_points_back(self):
        # 11-01：loop 型的 exec 是內嵌單子＝小格的 exec 換成 <XXX>/loop.json#/exec，跑的時候 AOS_CD 是 XXX
        # （{"$env": "AOS_CD"}、帶 $path 的都照原地解）。demo/agent-nia（aos-fsm 表在 lib/agent/round）掛上去也一樣指回定義資料夾、
        # 小格裡先放的一題答得出來（表的 {"$env": "AOS_CD"}＝nia）
        nia = Path(__file__).resolve().parent.parent / "demo" / "agent-nia"
        d = self.prog("odd", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'echo "$0 $1" > "$AOS_STACK/args"',
                                                                 {"$env": "AOS_CD"}, {"$env": "AOS_CD", "$path": "x"}]},
                                               "max": 1})
        (self.s / "loops" / "nia").mkdir(parents=True)
        r = subprocess.run([tool("aos-exec"), str(nia / "parts.json") + "#/queue", str(nia), "push"], input='{"role": "user", "content": "幾點？"}',
                           env=env_of({"AOS_STACK": str(self.s / "loops" / "nia") + "/", "AOS_WS": str(self.t)}), capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.start()
        self.assertEqual(self.ctl("add", "--name", "nia", str(nia)).returncode, 0)
        self.assertEqual(self.ctl("add", "odd").returncode, 0)
        self.assertTrue(until(lambda: (self.s / "loops" / "nia" / "loop.json").is_file() and (self.s / "loops" / "odd" / "args").is_file()))
        self.assertEqual(json.loads((self.s / "loops" / "nia" / "loop.json").read_text())["exec"], str(nia) + "/loop.json#/exec")
        self.assertEqual(json.loads((self.s / "loops" / "odd" / "loop.json").read_text())["exec"], os.path.realpath(d) + "/loop.json#/exec")
        self.assertEqual((self.s / "loops" / "odd" / "args").read_text().split(), [os.path.realpath(d), os.path.join(os.path.realpath(d), "x")])
        self.assertTrue(until(lambda: self.ended().get("nia", {}).get("phase") == "done", secs=60), (self.s / "loops" / "nia" / "stderr.txt").read_text())
        last = json.loads((self.s / "loops" / "nia" / "history.jsonl").read_text().splitlines()[-1])
        self.assertTrue(last["content"].startswith("FAKE ANSWER to: 幾點？"), last)


if __name__ == "__main__":
    unittest.main()
