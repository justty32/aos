"""aos-daemon-ctl：把東西掛到 aos-daemon 上（10-30，使用者「或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop」）。
哪個 daemon＝--daemon ＞ $AOS_DAEMON（N-63），值＝daemon 的 $AOS_STACK；投信進 <D>/loops_mailbox/（信箱模式）；ls 讀 loops_state.json 兩張表。
10-30 eca 第 2 步：add --ws（子項的 ws、<WS>/.stack symlink 到小格、rm 拿掉）、ls 多一欄 ws。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import tool, path_with  # noqa: E402
DAEMON = tool("aos-daemon")
CTL = tool("aos-daemon-ctl")


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
        self.p = None
        self.addCleanup(self._t.cleanup)
        self.addCleanup(self.stop)

    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.send_signal(signal.SIGTERM)
            self.p.communicate(timeout=30)

    def start(self):
        (self.t / "daemon.json").write_text(json.dumps({"interval_ms": 100, "ctl": "ctl.json", "state": "state.json",
                                                        "loops_mailbox": "loops_mailbox"}))
        self.p = subprocess.Popen([DAEMON, "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)}),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertTrue(until(lambda: (self.s / "loops_mailbox" / "new").is_dir() and (self.s / "loops_state.json").is_file()))

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
        for args, env, code in ((("ls",), {}, "DaemonMissing"), (("--daemon", str(self.t / "no"), "ls"), None, "DaemonMissing"),
                                (("add", "x"), None, "PathMissing"), (("ls",), None, "StateMissing"),
                                (("frob",), None, "CommandUnknown"), ((), None, "ArgumentsBad"), (("rm",), None, "ArgumentsBad")):
            r = self.ctl(*args, env=env)
            self.assertEqual((r.returncode, r.stdout, r.stderr.count("\n")), (1, "", 1), (args, r.stderr))
            self.assertTrue(r.stderr.startswith("aos-daemon-ctl: "), r.stderr)
        self.prog("job", "exit 0\n")
        r = self.ctl("add", "job")   # stack 在、但不是信箱模式
        self.assertEqual(r.returncode, 1)
        self.assertIn("loops_mailbox", r.stderr)
        r = self.ctl("add", "--kind", "loop", "job")   # 沒 loop.json 卻要 loop
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_add_exec_then_rm_and_ls(self):
        # 沒 loop.json 的資料夾＝exec 型（execs）：跑一次、done、不重起；ls 一行一項；rm 拿掉
        self.prog("job", 'echo "$$" >> "$AOS_STACK/runs"\nexit 3\n')
        self.start()
        r = self.ctl("add", "job")
        self.assertEqual((r.returncode, r.stderr, r.stdout.count("\n")), (0, "", 1))   # 印信號
        x = until(lambda: self.tables()["execs"].get("job", {}).get("phase") == "done" and self.tables())
        self.assertTrue(x)
        self.assertEqual((x["loops"], x["execs"]["job"]["code"]), ({}, 3))
        self.assertFalse((self.s / "job" / "loop.json").exists())
        r = self.ctl("ls")
        self.assertEqual(r.stdout, "job\texec\tdone\t%d\t3\t-\n" % x["execs"]["job"]["pid"])   # 最後一欄 ws（沒給＝-，10-30 eca）
        self.assertEqual(self.ctl("rm", "job").returncode, 0)
        self.assertTrue(until(lambda: self.tables()["execs"] == {}))
        self.assertEqual((self.s / "job" / "runs").read_text().count("\n"), 1)

    def test_add_loop_runs_its_loop_json(self):
        # 有 loop.json＝loop 型：子 loop 直接跑 XXX 的 loop.json（相對 exec 照 XXX 轉絕對、單子補 cwd＝XXX）；--name 改名
        d = self.prog("ag", "exit 0\n", loop={"exec": "loop.json#/b", "max": 2, "_entry": ["x"],
                                              "b": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/runs"']}})
        d2 = self.prog("ag2", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'pwd > "$AOS_STACK/pwd"']}, "max": 1})
        self.start()
        self.assertEqual(self.ctl("add", "ag").returncode, 0)
        self.assertEqual(self.ctl("add", "--name", "two", str(d2)).returncode, 0)
        x = until(lambda: {r["phase"] for r in self.tables()["loops"].values()} == {"done"} and len(self.tables()["loops"]) == 2
                  and self.tables())
        self.assertTrue(x, self.tables())
        self.assertEqual(({n: r["code"] for n, r in x["loops"].items()}, x["execs"]), ({"ag": 0, "two": 0}, {}))
        self.assertEqual((self.s / "ag" / "runs").read_text(), "x\nx\n")
        cell = json.loads((self.s / "ag" / "loop.json").read_text())
        self.assertEqual((cell["exec"], cell["max"], cell["_entry"][0]), (os.path.realpath(d) + "/loop.json#/b", 2, "aos-loop"))
        self.assertEqual((self.s / "two" / "pwd").read_text().strip(), os.path.realpath(d2))

    def test_kind_max1_and_flag_over_env(self):
        # --kind max1＝{"exec": XXX, "max": 1} 的 loop（使用者的底線）；--daemon 蓋過 AOS_DAEMON
        self.prog("job", 'echo x >> "$AOS_STACK/runs"\n')
        self.start()
        r = self.ctl("--daemon", str(self.s), "add", "--kind", "max1", "job", env={"AOS_DAEMON": str(self.t / "nowhere")})
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertTrue(until(lambda: self.tables()["loops"].get("job", {}).get("phase") == "done"))
        self.assertEqual(json.loads((self.s / "job" / "loop.json").read_text())["exec"], os.path.realpath(self.t / "job"))
        self.assertEqual((self.s / "job" / "runs").read_text(), "x\n")


    # ---- 10-30 eca 第 2 步：--ws（thinking 2026-10-30-eca 衝突 1、3）

    def wsprog(self, name, loop=None):
        # 子程式印出自己看到的 AOS_WS
        return self.prog(name, 'printf %s "$AOS_WS" > "$AOS_STACK/ws"\n', loop=loop)

    def test_add_ws_exec_and_loop_ls_and_env(self):
        # add --ws：exec 型、loop 型、max1 的子項都帶 ws；子程式看到的 AOS_WS 對；ls --json 那列有 ws、ls 多一欄
        self.wsprog("job")
        self.prog("ag", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'printf %s "$AOS_WS" > "$AOS_STACK/ws"']}, "max": 1})
        ws = [self.t / ("w%d" % i) for i in range(3)]
        for w in ws:
            w.mkdir()
        self.start()
        for args in (("--ws", str(ws[0]), "job"), ("--ws", "w1", "ag"), ("--kind", "max1", "--name", "m", "--ws", str(ws[2]), "job")):
            r = self.ctl("add", *args)
            self.assertEqual((r.returncode, r.stderr), (0, ""), args)
        x = until(lambda: len(self.tables()["loops"]) == 2 and len(self.tables()["execs"]) == 1
                  and {r["phase"] for t in self.tables().values() for r in t.values()} == {"done"} and self.tables())
        self.assertTrue(x, self.tables())
        self.assertEqual((x["execs"]["job"]["ws"], x["loops"]["ag"]["ws"], x["loops"]["m"]["ws"]), tuple(map(str, ws)))
        for n, w in (("job", ws[0]), ("ag", ws[1]), ("m", ws[2])):
            self.assertEqual((self.s / n / "ws").read_text(), str(w), n)
        lines = {l.split("\t")[0]: l.split("\t") for l in self.ctl("ls").stdout.splitlines()}
        self.assertEqual((lines["job"][5], lines["ag"][5], len(lines["m"])), (str(ws[0]), str(ws[1]), 6))
        r = self.ctl("add", "--ws", str(self.t / "nope"), "job")
        self.assertEqual((r.returncode, r.stderr.startswith("aos-daemon-ctl: ")), (1, True), r.stderr)

    def test_add_ws_links_stack_and_rm_unlinks(self):
        # add --ws：<WS>/.stack 不在＝建 symlink 指到小格（小格還沒建也先建）；cd 到 WS 就是這隻的 stack；rm 後 symlink 拿掉
        self.prog("job", 'echo "$AOS_WS" > "$AOS_STACK/ws"\nwhile :; do sleep 0.05; done\n')
        w = self.t / "proj"
        w.mkdir()
        r = self.ctl("add", "--ws", str(w), "job")   # daemon 還沒起：信箱不在＝送不出去、也不建 symlink
        self.assertEqual(r.returncode, 1)
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.start()
        r = self.ctl("add", "--ws", str(w), "job")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(os.readlink(w / ".stack"), str(self.s / "job"))
        self.assertTrue(until(lambda: (w / ".stack" / "ws").exists()))
        self.assertEqual((w / ".stack" / "ws").read_text().strip(), str(w))
        self.assertEqual(self.ctl("rm", "job").returncode, 0)
        self.assertFalse(os.path.lexists(w / ".stack"))
        self.assertTrue(until(lambda: self.tables()["execs"] == {}))

    def test_add_ws_existing_stack_kept(self):
        # <WS>/.stack 已經在（資料夾、或指到別處的 symlink）＝不建、stderr 一句叫人先搬開（或用 --stack）、add 照樣成功；rm 不動別人的
        self.wsprog("job")
        w1, w2 = self.t / "p1", self.t / "p2"
        (w1 / ".stack").mkdir(parents=True)
        w2.mkdir()
        os.symlink(str(self.t / "elsewhere"), w2 / ".stack")
        self.start()
        for w, n in ((w1, "a"), (w2, "b")):
            r = self.ctl("add", "--ws", str(w), "--name", n, "job")
            self.assertEqual((r.returncode, r.stdout.count("\n"), r.stderr.count("\n")), (0, 1, 1), r.stderr)
            self.assertTrue(r.stderr.startswith("aos-daemon-ctl: 注意 工作區已有 .stack") and "請先搬開" in r.stderr
                            and "--stack" in r.stderr, r.stderr)
        self.assertTrue(until(lambda: {r.get("ws") for r in self.tables()["execs"].values()} == {str(w1), str(w2)}))
        self.assertEqual(((self.s / "a" / "ws").read_text(), os.readlink(w2 / ".stack")), (str(w1), str(self.t / "elsewhere")))
        self.assertEqual((self.ctl("rm", "a").returncode, self.ctl("rm", "b").returncode), (0, 0))
        self.assertEqual(((w1 / ".stack").is_dir(), os.readlink(w2 / ".stack")), (True, str(self.t / "elsewhere")))

    def test_add_pins_aos_cd(self):
        # 10-30 eca 代定：loop 型的 exec 裡剛好等於 {"$env": "AOS_CD"} 的值換成 XXX 的絕對路徑（搬進小格後 AOS_CD 是小格）；
        # 帶 $path 等其他 key 的不動。demo/agent-nia（aos-parts run round $AOS_CD）掛上去，小格的 loop.json 指回定義資料夾
        nia = Path(__file__).resolve().parent.parent / "demo" / "agent-nia"
        d = self.prog("odd", "exit 0\n", loop={"exec": {"argv": ["sh", "-c", 'echo "$0 $1" > "$AOS_STACK/args"',
                                                                 {"$env": "AOS_CD"}, {"$env": "AOS_CD", "$path": "x"}]},
                                               "max": 1})
        self.start()
        self.assertEqual(self.ctl("add", "--name", "nia", str(nia)).returncode, 0)
        self.assertEqual(self.ctl("add", "odd").returncode, 0)
        self.assertTrue(until(lambda: (self.s / "nia" / "loop.json").is_file() and (self.s / "odd" / "args").is_file()))
        argv = json.loads((self.s / "nia" / "loop.json").read_text())["exec"]["argv"]
        self.assertEqual(argv, ["aos-parts", "run", "round", str(nia)])
        odd = json.loads((self.s / "odd" / "loop.json").read_text())["exec"]["argv"]
        self.assertEqual(odd[3:], [os.path.realpath(d), {"$env": "AOS_CD", "$path": "x"}])
        self.assertEqual((self.s / "odd" / "args").read_text().split()[0], os.path.realpath(d))


if __name__ == "__main__":
    unittest.main()
