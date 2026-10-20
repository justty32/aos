"""aos-daemon：daemon.json＝loop.json 的超集、children 表、ctl 增減、不自動重起、收工收子項、接回（N-28、N-54、P-36）。"""
import json, os, signal, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
DAEMON = str(BIN / "aos-daemon")
LONG = 'echo x >> "$AOS_STACK/starts"; while :; do sleep 0.05; done'


def env_of(extra=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    e["PATH"] = str(BIN) + os.pathsep + e.get("PATH", "")
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
        self.procs = []
        self.addCleanup(self._t.cleanup)
        self.addCleanup(self.reap)

    def reap(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.communicate()
        st = self.s / "state.json"
        if st.exists():   # 測試失敗時別留孤兒
            for r in json.loads(st.read_text()).get("children", {}).values():
                if r.get("pid") and alive(r["pid"]):
                    try:
                        os.killpg(r["pid"], signal.SIGKILL)
                    except OSError:
                        pass

    def cfg(self, doc):
        (self.t / "daemon.json").write_text(json.dumps(doc))

    def run_d(self, doc, timeout=30, env=None):
        self.cfg(doc)
        return subprocess.run([DAEMON, "daemon.json"], cwd=str(self.t), env=env_of({"AOS_STACK": str(self.s)} if env is None else env),
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
        return self.state()["children"]

    def ctl(self, doc):
        tmp = self.s / ".ctl.json"
        tmp.write_text(json.dumps(doc))
        os.replace(tmp, self.s / "ctl.json")

    def long(self, mx=1):
        return {"run": {"argv": ["sh", "-c", LONG]}, "max": mx}

    def test_loop_json_runs_as_is(self):
        # 合法的 loop.json 直接丟給 daemon 也能跑（N-28）
        r = self.run_d({"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/laps"']}, "max": 3, "interval_ms": 0})
        self.assertEqual((r.returncode, r.stderr, len((self.s / "laps").read_text().split())), (0, "", 3))

    def test_needs_stack(self):
        r = self.run_d({"max": 1}, env={})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("aos-daemon: ") and "AOS_STACK" in r.stderr, r.stderr)

    def test_bad_children_is_own_error(self):
        for bad in ([1], {"a/b": "x"}, {"a": 3}):
            r = self.run_d({"children": bad, "max": 1})
            self.assertEqual(r.returncode, 1, bad)
            self.assertTrue(r.stderr.startswith("aos-daemon: "), r.stderr)

    def test_children_started_in_cells_then_stop(self):
        sub = self.t / "sub"
        sub.mkdir()
        (sub / "_exec").write_text("#!/bin/sh\n" + LONG + "\n")
        (sub / "_exec").chmod(0o755)
        p = self.start({"state": "state.json", "ctl": "ctl.json", "children": {"a": "sub", "b": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and (self.s / "b" / "starts").exists() and self.kids())
        self.assertTrue(k)
        self.assertEqual({n: r["phase"] for n, r in k.items()}, {"a": "running", "b": "running"})
        a = json.loads((self.s / "a" / "loop.json").read_text())
        self.assertEqual(a, {"run": "sub", "ctl": "ctl.json", "state": "state.json"})
        self.assertTrue(until(lambda: json.loads((self.s / "b" / "state.json").read_text())["state"] == "running"))
        pids = [r["pid"] for r in k.values()]
        self.ctl({"stop": True, "seq": 1})
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["state"], st["ctl_seq"]), (0, "", "stopped", 1))
        self.assertEqual({r["phase"] for r in st["children"].values()}, {"exited"})
        self.assertEqual([alive(x) for x in pids], [False, False])

    def test_exited_child_not_restarted(self):
        p = self.start({"state": "state.json", "max": 15, "interval_ms": 100,
                        "children": {"once": {"run": {"argv": ["sh", "-c", 'echo x >> "$AOS_STACK/starts"']},
                                              "max": 1}}})
        out, err = p.communicate(timeout=30)
        k = self.kids()
        self.assertEqual((p.returncode, err, k["once"]["phase"], k["once"]["code"]), (0, "", "exited", 0))
        self.assertEqual(len((self.s / "once" / "starts").read_text().split()), 1)

    def test_failing_child_stderr_in_cell(self):
        p = self.start({"state": "state.json", "max": 10, "interval_ms": 100,
                        "children": {"bad": {"run": {"argv": ["sh", "-c", "exit 3"]}}}})
        out, err = p.communicate(timeout=30)
        k = self.kids()
        self.assertEqual((p.returncode, err, k["bad"]["phase"], k["bad"]["code"]), (0, "", "exited", 3))
        self.assertIn("aos-loop: ", (self.s / "bad" / "stderr").read_text())

    def test_ctl_children_add_and_remove(self):
        p = self.start({"state": "state.json", "ctl": "ctl.json", "children": {"a": self.long()}})
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        a_pid = k["a"]["pid"]
        self.ctl({"children": {"b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and "a" not in self.kids() and self.kids())
        self.assertEqual(list(k), ["b"])
        self.assertFalse(alive(a_pid))
        self.ctl({"children": {"b": self.long()}, "stop": True})
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0)

    def test_sigterm_collects_children_nonzero(self):
        p = self.start({"state": "state.json", "children": {"a": self.long(), "b": self.long()}})
        k = until(lambda: (self.s / "b" / "starts").exists() and len(self.kids()) == 2 and self.kids())
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        st = self.state()
        self.assertEqual((p.returncode, err, st["state"], st["code"]), (143, "", "stopped", 143))
        self.assertEqual([alive(r["pid"]) for r in k.values()], [False, False])
        self.assertEqual({r["phase"] for r in st["children"].values()}, {"exited"})

    def test_adopt_after_crash(self):
        doc = {"state": "state.json", "ctl": "ctl.json", "children": {"a": self.long()}}
        p = self.start(doc)
        k = until(lambda: (self.s / "a" / "starts").exists() and self.kids())
        pid = k["a"]["pid"]
        p.kill()
        p.wait()
        self.assertTrue(alive(pid))
        p2 = self.start()
        time.sleep(1)
        self.assertEqual((self.kids()["a"]["pid"], len((self.s / "a" / "starts").read_text().split())), (pid, 1))
        self.ctl({"stop": True})
        p2.communicate(timeout=30)
        self.assertEqual((p2.returncode, alive(pid)), (0, False))

    def test_adopt_false_starts_fresh(self):
        doc = {"state": "state.json", "children": {"a": self.long()}}
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


if __name__ == "__main__":
    unittest.main()
