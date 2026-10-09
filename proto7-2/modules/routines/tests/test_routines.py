"""兩張表、真 keep 取樣，以及先寫證據的 SIGKILL 窗口。"""
import datetime as dt
import importlib.util
import io
import os
import subprocess
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests"))
from base import MODULES
from aos7_fs import read_json, write_json
from _matrix import MatrixCase, fault
PATH = os.path.join(MODULES, "routines", "aos7_routines.py")
_spec = importlib.util.spec_from_file_location("aos7_routines", PATH)
routines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(routines)
NOW = dt.datetime(2026, 10, 9, 12).astimezone()

class TestRoutines(MatrixCase):
    def setup_node(self, tasks=()):
        node = self.mknode("a", tasks)
        script = os.path.join(node, "hello.sh")
        with open(script, "w") as f:
            f.write('#!/bin/sh\necho x >> "' + os.path.join(node, "count") + '"\n')
        os.chmod(script, 0o755)
        return node
    def put(self, node, kind, rows):
        write_json(os.path.join(node, "wf", kind + ".json"), dict(routines.empty(kind), rows=rows))
    def rows(self, node, kind):
        return read_json(os.path.join(node, "wf", kind + ".json"))["rows"]
    def count(self, node):
        path = os.path.join(node, "count")
        if not os.path.exists(path):
            return 0
        with open(path) as f:
            return len(f.readlines())
    def step(self, node, round, now=NOW):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            routines.step(node, round, now)
    def cli_result(self, *args, code=0, env=None):
        p = subprocess.run([sys.executable, "-B", routines.ENTRY, *args], capture_output=True, text=True, timeout=10, env=env)
        self.assertEqual(p.returncode, code, p.stderr)
        return p
    def cli(self, *args, code=0):
        return self.cli_result(*args, code=code).stdout
    def test_300_rounds(self):
        node = self.setup_node()
        self.put(node, "routines", [dict(name="r", every="10r", inst="hello.sh")])
        self.put(node, "schedule", [dict(name="past", at=(NOW-dt.timedelta(days=1)).isoformat(), inst="hello.sh"),
                                    dict(name="future", at=(NOW+dt.timedelta(days=1)).isoformat(), inst="hello.sh")])
        for r in range(1, 301):
            self.step(node, r)
            if r == 1:
                self.assertEqual(self.count(node), 2)
                self.assertEqual([i["name"] for i in self.rows(node, "schedule")], ["future"])
        self.assertEqual(self.count(node), 31)  # routine 正好 30 次，schedule 一次
        self.assertEqual(self.rows(node, "routines")[0]["last_code"], "0")
    def test_seconds_and_clock_round_rollback(self):
        node = self.setup_node()
        self.put(node, "routines", [dict(name="r", every="30s", inst="hello.sh")])
        for s in range(301):
            self.step(node, s+1, NOW+dt.timedelta(seconds=s))
        self.assertEqual(self.count(node), 11)
        self.step(node, 302, NOW+dt.timedelta(days=1))
        self.assertEqual(self.count(node), 12)
        self.step(node, 303, NOW)
        self.assertEqual(self.count(node), 13)
        self.put(node, "routines", [dict(name="r", every="10r", inst="hello.sh", last_round="99")])
        self.step(node, 1)
        self.assertEqual(self.count(node), 14)
    def crash_step(self, node, point):
        code = "import sys; sys.path.insert(0, %r); import aos7_routines as r; r.step(%r, 1, %r)" % (os.path.dirname(PATH), node, NOW.isoformat())
        p = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, AOS7_TEST_CRASH=point), capture_output=True, timeout=10)
        self.assertEqual(p.returncode, -9, p.stderr)
    def test_killed_claim_and_atomic_write(self):
        node = self.setup_node()
        self.put(node, "routines", [dict(name="r", every="10r", inst="hello.sh")])
        self.crash_step(node, "routines-after-claim")
        self.step(node, 1)
        self.assertEqual(self.count(node), 0)
        self.step(node, 11)
        self.assertEqual(self.count(node), 1)
        self.put(node, "routines", [])
        self.put(node, "schedule", [dict(name="s", at=NOW.isoformat(), inst="hello.sh")])
        self.crash_step(node, "routines-after-claim")
        self.step(node, 1)
        self.assertEqual(self.rows(node, "schedule"), [])
        self.assertEqual(self.count(node), 1)
        old = dict(name="r", every="10r", inst="hello.sh")
        self.put(node, "routines", [old])
        self.crash_step(node, "tmp:routines.json")
        self.assertEqual(self.rows(node, "routines"), [old])
        self.step(node, 1)
        self.assertEqual(self.count(node), 2)
    def test_unknown_and_bad_row(self):
        node = self.setup_node()
        self.step(node, 1)  # 缺表無事
        path = os.path.join(node, "wf", "routines.json")
        write_json(path, {})
        self.step(node, 1)
        self.assertEqual(read_json(path), {})
        with open(path, "w") as f:
            f.write("{")
        self.step(node, 1)
        with open(path) as f:
            self.assertEqual(f.read(), "{")
        self.assertEqual(self.count(node), 0)
        self.put(node, "routines", [dict(name="bad", every="oops", inst="hello.sh"), dict(name="ok", every="1r", inst="hello.sh")])
        with fault("open:*routines.json:EIO"):
            self.step(node, 1)
        self.assertEqual(self.count(node), 0)
        self.step(node, 1)
        self.assertEqual(self.count(node), 1)
    def test_stale_snapshot_and_huge_timeout(self):
        """astra 審：舊回合拿著舊快照晚進鎖不能再跑；timeout 溢位只跳過那列、不讓任務死掉。"""
        node = self.setup_node()
        self.put(node, "routines", [dict(name="r", every="10r", inst="hello.sh")])
        stale = routines.load(os.path.join(node, "wf", "routines.json"))
        self.step(node, 11)
        load, routines.load = routines.load, lambda path: stale if path.endswith("routines.json") else load(path)
        try:
            self.step(node, 10)
        finally:
            routines.load = load
        self.assertEqual(self.count(node), 1)
        self.put(node, "routines", [dict(name="big", every="1r", inst="hello.sh", timeout="1e308"),
                                    dict(name="ok", every="1r", inst="hello.sh")])
        self.step(node, 1)
        self.assertEqual(self.count(node), 2)
    def test_cli(self):
        node = os.path.join(self.root, "plain")
        os.mkdir(node)
        with open(os.path.join(node, "hello.sh"), "w") as f:
            f.write("#!/bin/sh\necho hello\n")
        out = self.cli("add", node, "r", "--every", "10r", "hello.sh")
        self.assertFalse(os.path.exists(os.path.join(node, ".aos")))
        self.assertIn("要讓心跳自動跑", out)
        self.assertEqual(len(out.splitlines()), 2)
        self.cli("add", node, "r", "--every", "10r", "hello.sh", code=1)
        self.cli("add", node, "s", "--at", "+90s", "hello.sh")
        delta = (routines.instant(self.rows(node, "schedule")[0]["at"]) - dt.datetime.now().astimezone()).total_seconds()
        self.assertTrue(85 <= delta <= 90)
        self.assertIn("next round", self.cli("ls", node))
        self.cli("rm", node, "r")
        self.cli("rm", node, "s")
        self.cli("rm", node, "s", code=1)
        self.cli("add", node, "--every", "10r", code=2)
        self.cli("add", node, "x", "--every", "oops", "hello.sh", code=2)
        with open(os.path.join(node, "wf", "routines.json"), "w") as f:
            f.write("{")
        p = self.cli_result("ls", node, code=3)
        self.assertTrue(p.stderr.startswith("aos7-routines: 不確定："))
    def test_error_path(self):
        help_result = self.cli_result("--help")
        self.assertEqual(help_result.stderr, "")
        self.assertLessEqual(len(help_result.stdout.splitlines()), 24)
        node = os.path.join(self.root, "empty")
        os.mkdir(node)
        def one_line(p):
            self.assertNotIn("\n", p.stderr.strip())
            self.assertIn("aos7-routines: ", p.stderr)
            self.assertIn("。", p.stderr)
        for args in [("bogus",), ("add", node, "--every", "10r"),
                     ("add", node, "x", "--every", "oops", "hello.sh"),
                     ("add", node, "x", "--at", "oops", "hello.sh"),
                     ("add", node, "x", "--every", "", "hello.sh"),
                     ("add", node, "x", "--every", "1s", "hello.sh", "--timeout", "oops")]:
            with self.subTest(args=args):
                one_line(self.cli_result(*args, code=2))
                self.assertEqual(os.listdir(node), [])
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS7_")}
        one_line(self.cli_result(code=2, env=env))
        env.update({"AOS7_" + k: "x" for k in ("ROOT", "NODE", "NODE_ID", "TASK", "TID", "RUN")})
        one_line(self.cli_result(code=2, env=env))
        p = self.cli_result("rm", node, "missing", code=1)
        one_line(p)
        self.assertIn("清單是空的，沒有 missing", p.stderr)
        self.assertEqual(os.listdir(node), [])
        self.put(node, "routines", [])
        p = self.cli_result("rm", node, "missing", code=1)
        one_line(p)
        self.assertIn("清單裡沒有 missing", p.stderr)
        self.assertFalse(os.path.exists(os.path.join(node, "wf", "schedule.json.lock")))
    def test_ls_run_lock_busy_is_unknown(self):
        """astra 審：ls --run 遇鎖忙不能退 0 說「沒有到期」，要退 3 一行「不確定：」。"""
        import fcntl
        node = self.setup_node()
        self.put(node, "routines", [dict(name="r", every="1s", inst="hello.sh")])
        with open(os.path.join(node, "wf", "routines.json.lock"), "a") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            p = self.cli_result("ls", node, "--run", code=3)
        self.assertTrue(p.stderr.startswith("aos7-routines: 不確定："), p.stderr)
        self.assertNotIn("\n", p.stderr.strip())
        self.assertEqual(self.count(node), 0)

    def test_ls_run_without_daemon(self):
        """新手第一次跑：不開 daemon，ls --run 只照時間做（秒型、schedule），r 型留給 daemon；再跑一次沒有到期的。"""
        node = self.setup_node()
        self.cli("add", node, "s", "--every", "1m", "hello.sh")
        self.cli("add", node, "r", "--every", "1r", "hello.sh")
        self.put(node, "schedule", [dict(name="once", at=(dt.datetime.now().astimezone()-dt.timedelta(seconds=1)).isoformat(), inst="hello.sh")])
        out = self.cli("ls", node, "--run")
        self.assertIn("routine s code 0", out)
        self.assertIn("schedule once code 0", out)
        self.assertEqual(self.count(node), 2)
        self.assertEqual(self.rows(node, "schedule"), [])
        r = {row["name"]: row for row in self.rows(node, "routines")}
        self.assertEqual((r["s"]["last_code"], r["r"]["last_round"]), ("0", ""))
        self.assertIn("沒有到期", self.cli("ls", node, "--run"))
        self.assertEqual(self.count(node), 2)
        self.step(node, 1, dt.datetime.now().astimezone())  # daemon 回合仍照常接手 r 型
        self.assertEqual(self.count(node), 3)
    def test_real_keep(self):
        node = self.setup_node([dict(name="routines", mode="keep", argv=[sys.executable, routines.ENTRY])])
        self.put(node, "routines", [dict(name="r", every="2r", inst="hello.sh")])
        for _ in range(12):
            self.itick()
            self.itock()
            time.sleep(0.1)  # 留任務完成同步 inst 的時間；MatrixCase cleanup 收程序
        self.wait_for(lambda: self.count(node) >= 3, 5)
        self.assertLessEqual(self.count(node), 6)
