"""aos-daemon-ctl：把東西掛到 aos-daemon 上（10-30，使用者「或許是aos-daemon-ctl add XXX這樣，然後會自動識別XXX是否為loop」）。
哪個 daemon＝--daemon ＞ $AOS_DAEMON（N-63），值＝daemon 的 $AOS_STACK；投信進 <D>/loops_mailbox/（信箱模式）；ls 讀 loops_state.json 兩張表。"""
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
        self.assertEqual(r.stdout, "job\texec\tdone\t%d\t3\n" % x["execs"]["job"]["pid"])
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


if __name__ == "__main__":
    unittest.main()
