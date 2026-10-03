"""astra-7 第四節 H-01～H-09 的回歸測試（notes/play/2026-10-03-astra-7-infra.md；重現情境照同名 -evidence/）。"""
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

import _proc
from test_astra5 import hook_env
from test_core import BIN, LIB, SLEEPER, CoreCase
from test_core_daemon import DaemonCase
import aos7_audit
import aos7_daemon
import aos7_fs
import aos7_task
import aos7_tick
import aos7_tock
from aos7_fs import read_json, read_jsonl, write_json

SITE = os.path.join(LIB, "audit_site")

# 第一次讀回確認時，假裝讀不到已經完整 append 的總結（evidence edges.py READ_HOOK）
READ_HOOK = """import os, sys
if os.path.basename(sys.argv[0]) == "aos7-tock":
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_tock as t
    _orig = t.logged_summary
    def checked(node, rnd, k=5):
        v = _orig(node, rnd, k)
        if v is not None and not os.path.exists(os.environ["HOOK_MARK"]):
            open(os.environ["HOOK_MARK"], "w").write("x")
            return None
        return v
    t.logged_summary = checked
"""

# 總結只 append 24 bytes 就返回（evidence followup.py readback_torn）
TORN_HOOK = """import os, sys, json
if os.path.basename(sys.argv[0]) == "aos7-tock":
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_fs
    _orig = aos7_fs.append_jsonl
    def torn(path, obj):
        if str(path).endswith("/rounds.jsonl") and not os.path.exists(os.environ["HOOK_MARK"]):
            with open(path, "ab") as f:
                f.write(json.dumps(obj).encode()[:24])
            open(os.environ["HOOK_MARK"], "w").write("x")
            return 0
        return _orig(path, obj)
    aos7_fs.append_jsonl = torn
"""

# HOOK_FAIL 檔在的期間，rounds.jsonl 一律寫不進去（持續 I/O 故障）
FAIL_HOOK = """import os, sys, errno
if os.path.basename(sys.argv[0]) == "aos7-tock":
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_fs
    _orig = aos7_fs.append_jsonl
    def failing(path, obj):
        if str(path).endswith("/rounds.jsonl") and os.path.exists(os.environ["HOOK_FAIL"]):
            raise OSError(errno.ENOSPC, "injected")
        return _orig(path, obj)
    aos7_fs.append_jsonl = failing
"""


class H01UnclosedRoundRecovery(DaemonCase):
    """H-01：tock 非零退出（讀回失敗、短寫、持續 I/O 錯）後，daemon 先把開著的回合恢復好才 tick 下一回合：
    ended 不重報、round 不缺號、持續故障時停在 error 不前進。"""

    def setup_one(self):
        node = self.mknode("n")
        write_json(os.path.join(node, ".aos", "spawn", "one.json"), {"name": "one", "argv": ["true"]})
        return node

    def run_hook(self, code, until_round=4, extra=None):
        node = self.setup_one()
        mark = os.path.join(self.root, "mark")
        self.start_daemon(env=dict(hook_env(self.root, code), HOOK_MARK=mark, **(extra or {})))
        self.wait_for(lambda: os.path.exists(mark), msg="沒注入到")
        self.wait_for(lambda: (read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0)
                      >= until_round and not read_json(os.path.join(node, ".aos", "round.json"))["open"])
        self.ctl("stop", "--kill")
        return node, read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))

    def check_rows(self, node, rows):
        rounds = [r["round"] for r in rows]
        self.assertEqual(rounds, list(range(1, len(rounds) + 1)), "round 缺號或重複：%r" % rounds)
        ended_in = [r["round"] for r in rows for e in r.get("ended") or [] if e["tid"] == "one-r1"]
        self.assertEqual(ended_in, [1], "one-r1 的 ended 重報或漏報")
        self.assertEqual(read_json(os.path.join(self.tdir(node, "one-r1"), "ended.json")), {"round": 1})

    def test_readback_failure_not_reported_twice(self):
        node, rows = self.run_hook(READ_HOOK)
        self.check_rows(node, rows)
        self.assertTrue(any(e["ev"] == "tock" and e.get("rc") == 1 for e in self.log()))

    def test_torn_append_round_not_lost(self):
        node, rows = self.run_hook(TORN_HOOK)
        self.check_rows(node, rows)

    def test_persistent_failure_holds_round(self):
        node = self.setup_one()
        fail = os.path.join(self.root, "fail")
        open(fail, "w").close()
        self.start_daemon(env=dict(hook_env(self.root, FAIL_HOOK), HOOK_FAIL=fail))
        self.wait_for(lambda: self.status().get("nodes", {}).get("n", {}).get("phase") == "error", msg="沒進 error")
        self.wait_for(lambda: sum(1 for e in self.log() if e["ev"] == "tock" and e.get("rc")) >= 3, msg="沒有重試")
        st = self.status()["nodes"]["n"]
        self.assertEqual(st["round"], 1)
        self.assertIn("沒關上", st["last_error"]["err"])
        rj = read_json(os.path.join(node, ".aos", "round.json"))
        self.assertEqual((rj["round"], rj["open"]), (1, True), "持續故障時開了新回合")
        os.remove(fail)
        self.wait_for(lambda: (read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0) >= 3)
        self.ctl("stop", "--kill")
        rows = read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))
        self.check_rows(node, rows)
        self.assertEqual(rows[0].get("incomplete"), "unclosed")


RACE_HOOK = """import os, sys, signal
if os.path.basename(sys.argv[0]) == "aos7-tick" and sys.argv[-1] == "n/inner":
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_task
    _real = aos7_task.subroot_running
    def checked(sp):
        r = _real(sp)
        open(os.environ["HOOK_MARK"], "w").write(str(r))
        os.kill(os.getpid(), signal.SIGSTOP)
        return r
    aos7_task.subroot_running = checked
"""


class H02SubrootClaim(DaemonCase):
    """H-02：owner.json 只由拿到 daemon.lock 的子 daemon 寫；搶輸的啟動者什麼都不寫，同 tick 第二項宣告同一子根不起。"""

    DAEMON = ["aos7-daemon", "$AOS7_SUBROOT"]

    def test_same_tick_second_claim_refused(self):
        sub = os.path.join(self.root, "n", "sub")
        node = self.mknode("n", [{"name": "first", "argv": self.DAEMON, "subroot": "n/sub", "allow_stop": False},
                                 {"name": "second", "argv": self.DAEMON, "subroot": "n/sub", "allow_stop": True}])
        self.assertEqual(self.tick("n")["started"], ["first-r1"])
        errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
        self.assertTrue(any("已經有別的任務認領" in e for e in errs), errs)
        st = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "status.json")))
        ow = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "owner.json")))
        pid = read_json(os.path.join(self.tdir(node, "first-r1"), "pid.json"))["pid"]
        self.assertEqual((ow["tid"], ow["allow_stop"], ow["daemon_pid"]), ("first-r1", False, st["pid"]))
        self.assertEqual(st["pid"], pid)
        os.kill(pid, signal.SIGTERM)
        self.wait_for(lambda: self.state(node, "first-r1") == "ended")

    def test_loser_of_lock_race_writes_nothing(self):
        """固定競態（evidence edges.py claim_race）：second 的 tick 試鎖時沒人拿；first 的子 daemon 先拿到鎖，second 才起。"""
        sub = os.path.join(self.root, "n", "inner", "sub")
        n = self.mknode("n", [{"name": "first", "argv": self.DAEMON, "subroot": "n/inner/sub", "allow_stop": False}])
        inner = self.mknode("n/inner", [{"name": "second", "argv": self.DAEMON, "subroot": "n/inner/sub",
                                         "allow_stop": True}])
        mark = os.path.join(self.root, "mark")
        env = dict(os.environ, **hook_env(self.root, RACE_HOOK), HOOK_MARK=mark)
        second = _proc.track(self, subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-tick"), self.root, "n/inner"],
                                                     env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        self.wait_for(lambda: os.path.exists(mark))
        self.tick("n")
        st = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "status.json")))
        before = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "owner.json")))
        self.assertEqual(before["tid"], "first-r1")
        os.kill(second.pid, signal.SIGCONT)
        second.communicate(timeout=10)
        ex = self.wait_for(lambda: read_json(os.path.join(self.tdir(inner, "second-r1"), "exit.json")))
        self.assertEqual(ex["code"], 1)   # 搶輸鎖的子 daemon 退出
        self.assertEqual(read_json(os.path.join(sub, ".aosd", "owner.json")), before, "敗者改了 owner")
        self.assertEqual(read_json(os.path.join(sub, ".aosd", "status.json"))["pid"], st["pid"])
        write_json(os.path.join(sub, ".aosd", "ctl", "stop.json"), {"op": "stop", "kill": True})
        r = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "ctl-done", "stop.json")))
        self.assertFalse(r["result"]["ok"], r)   # first 沒允許外部 stop
        os.kill(st["pid"], signal.SIGTERM)
        self.wait_for(lambda: self.state(n, "first-r1") == "ended")


class H03AuditTornTail(CoreCase):
    """H-03：writes.jsonl 尾端有半行時，audit hook 先補換行；兩次寫入兩筆都讀得到。"""

    def test_two_writes_after_torn_tail(self):
        node = self.mknode("n")
        tdir = self.tdir(node, "t-r1")
        os.makedirs(tdir)
        write_json(os.path.join(tdir, "birth.json"), {"tid": "t-r1", "mounts": {}})
        with open(os.path.join(tdir, "writes.jsonl"), "w") as f:
            f.write('{"broken":')
        env = dict(os.environ, AOS7_AUDIT="1", AOS7_TASK=tdir, AOS7_NODE=node, AOS7_ROOT=self.root, PYTHONPATH=SITE)
        code = "open('first.txt','w').write('1'); open('second.txt','w').write('2')"
        subprocess.run([sys.executable, "-c", code], cwd=node, env=env, check=True, timeout=10)
        recs, bad = read_jsonl(os.path.join(tdir, "writes.jsonl"), with_bad=True)
        self.assertEqual([os.path.basename(r["path"]) for r in recs], ["first.txt", "second.txt"])
        self.assertEqual(bad, 1)   # 半行原樣留著、只算一行壞的
        sc = aos7_audit.scan(self.root)
        self.assertEqual((sc["writes"], sc["bad_lines"]), (2, 1))


class H04Utf8TornLine(CoreCase):
    """H-04：半個 UTF-8 字元只壞那一行；read_jsonl 與 audit.scan 不丟例外、不回空清單。"""

    def test_read_jsonl_skips_torn_utf8(self):
        path = os.path.join(self.root, "x.jsonl")
        with open(path, "wb") as f:
            f.write(b'{"a": 1}\n{"text":"' + "中".encode()[:2])
        aos7_fs.append_jsonl(path, {"b": "後"})
        self.assertEqual(read_jsonl(path), [{"a": 1}, {"b": "後"}])
        self.assertEqual(read_jsonl(path, with_bad=True), ([{"a": 1}, {"b": "後"}], 1))
        self.assertEqual(aos7_fs.tail_jsonl(path, 5), [{"a": 1}, {"b": "後"}])

    def test_audit_scan_survives_torn_utf8(self):
        tdir = os.path.join(self.root, "n", ".aos", "tasks", "t-r1")
        os.makedirs(tdir)
        write_json(os.path.join(tdir, "birth.json"), {"tid": "t-r1"})
        with open(os.path.join(tdir, "writes.jsonl"), "wb") as f:
            f.write(b'{"op":"open","path":"/x","ok":false}\n{"path":"' + "中".encode()[:2] + b"\n"
                    b'{"op":"open","path":"/y","ok":true}\n')
        sc = aos7_audit.scan(self.root)
        self.assertEqual((sc["writes"], sc["bad_lines"], len(sc["bad"])), (2, 1, 1))


PROGRESS = ("import os,json;from pathlib import Path;p=Path(os.environ['AOS7_TASK']);p.mkdir(parents=True,exist_ok=True);"
            "(p/'progress.json').write_text(json.dumps({'cwd':os.getcwd(),'node':os.environ['AOS7_NODE']}))")


class H05LateMoveHandoff(CoreCase):
    """H-05：tick 的檢查都過了、正要 Popen aos7-run 時 node 被搬走：runner 發現 AOS7_* 已不是抓著的資料夾，
    受控拒絕（exit 127 寫到新位置），任務不會照舊路徑把 node 建回來。"""

    def test_move_right_before_runner(self):
        node = self.mknode("n", [{"name": "x", "mode": "keep", "argv": [sys.executable, "-c", PROGRESS]}])
        moved = os.path.join(self.root, "moved")
        real, hit = aos7_task.subprocess.Popen, []

        def move(args, *a, **kw):
            if len(args) > 1 and str(args[1]).endswith("/aos7-run") and not hit:
                os.rename(node, moved)
                hit.append(True)
            return real(args, *a, **kw)
        with mock.patch.object(aos7_task.subprocess, "Popen", move):
            res = aos7_tick.tick(self.root, "n")
        self.assertEqual(res["started"], ["x-r1"])
        ex = self.wait_for(lambda: read_json(os.path.join(self.tdir(moved, "x-r1"), "exit.json")))
        self.assertEqual(ex["code"], 127)
        self.assertIn("AOS7_", ex["error"])
        time.sleep(0.2)
        self.assertFalse(os.path.exists(node), "舊 node 被建回來了")
        self.assertIsNone(read_json(os.path.join(self.tdir(moved, "x-r1"), "progress.json")))
        self.assertEqual(self.tick("moved")["started"], ["x-r2"])   # 新位置由 keep 重起，路徑一致
        pr = self.wait_for(lambda: read_json(os.path.join(self.tdir(moved, "x-r2"), "progress.json")))
        self.assertEqual((pr["cwd"], pr["node"]), (moved, moved))


class H06RunnerPreStartIO(CoreCase):
    """H-06：runner 起程序前的 I/O 失敗（out.log 是資料夾）寫 exit 127；連 exit 都沒寫成時，tock 照 runner.json 判 lost。"""

    def test_out_log_is_directory(self):
        node = self.mknode("n", [{"name": "x", "mode": "keep", "argv": ["true"]}])
        real, ps = aos7_task.subprocess.Popen, []

        def spawn(args, *a, **kw):
            if len(args) > 1 and str(args[1]).endswith("/aos7-run"):
                os.mkdir(os.path.join(args[2], "out.log"))
                p = real(args, *a, **kw)
                ps.append(p)
                return p
            return real(args, *a, **kw)
        with mock.patch.object(aos7_task.subprocess, "Popen", spawn):
            self.assertEqual(aos7_tick.tick(self.root, "n")["started"], ["x-r1"])
        self.assertEqual(ps[0].wait(5), 1)
        ex = read_json(os.path.join(self.tdir(node, "x-r1"), "exit.json"))
        self.assertEqual(ex["code"], 127)
        self.assertIn("out.log", ex["error"])
        self.tock("n")
        self.assertEqual(self.tick("n")["started"], ["x-r2"])   # keep 照常重起

    def test_runner_died_without_exit_is_lost(self):
        node = self.mknode("n")
        d = self.tdir(node, "x-r1")
        os.makedirs(d)
        write_json(os.path.join(d, "birth.json"), {"tid": "x-r1", "name": "x", "argv": ["true"]})
        p = subprocess.Popen(["true"])
        self.wait_for(lambda: not aos7_task.pid_alive(p.pid))   # 殭屍：還沒被 wait，starttime 讀得到
        write_json(os.path.join(d, "runner.json"), {"pid": p.pid, "starttime": aos7_fs.proc_starttime(p.pid)})
        p.wait()
        self.assertEqual(self.state(node, "x-r1"), "lost")
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 1, "open": True})
        r = self.tock("n")
        self.assertEqual([(e["tid"], e.get("lost")) for e in r["ended"]], [("x-r1", True)])
        # runner 還活著的照舊算 born（剛起）
        live = _proc.track(self, subprocess.Popen(["sleep", "30"]))
        d2 = self.tdir(node, "y-r2")
        os.makedirs(d2)
        write_json(os.path.join(d2, "birth.json"), {"tid": "y-r2"})
        write_json(os.path.join(d2, "runner.json"), {"pid": live.pid, "starttime": aos7_fs.proc_starttime(live.pid)})
        self.assertEqual(self.state(node, "y-r2"), "born")


class H07CtlFailedNoClobber(CoreCase):
    """H-07：ctl-failed 隔離檔的次級名稱也撞名時換名，不覆蓋舊的隔離檔。"""

    def test_suffix_collision_keeps_both(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        os.makedirs(os.path.join(d.aosd, "ctl-done", "x.json"))   # 回條寫不進去
        fdir = os.path.join(d.aosd, "ctl-failed")
        write_json(os.path.join(d.aosd, "ctl", "x.json"), {"op": "wake", "node": "n", "sequence": 0})
        d.handle_ctl()
        write_json(os.path.join(fdir, "x.json.42"), {"sentinel": "earlier failure"})
        write_json(os.path.join(d.aosd, "ctl", "x.json"), {"op": "wake", "node": "n", "sequence": 1})
        with mock.patch.object(aos7_daemon.time, "time_ns", return_value=42):
            d.handle_ctl()
        self.assertEqual(read_json(os.path.join(fdir, "x.json.42")), {"sentinel": "earlier failure"})
        self.assertEqual(read_json(os.path.join(fdir, "x.json"))["sequence"], 0)
        self.assertEqual(read_json(os.path.join(fdir, "x.json.42.1"))["sequence"], 1)
        self.assertEqual(d.last_ctl_error["moved_to"], "ctl-failed/x.json.42.1")
        self.assertEqual(os.listdir(os.path.join(d.aosd, "ctl")), [])


class H08Retention(DaemonCase):
    """H-08（技術選型）：預設只搬不刪；可選 keep_old_rounds、.aosd/retention.json；status.json 有 disk 粗估。"""

    def test_keep_old_rounds(self):
        node = self.mknode("n", [{"name": "j", "argv": ["true"]}])
        write_json(os.path.join(node, ".aos", "timeline.json"), {"keep_ended_rounds": 0, "keep_old_rounds": 2})
        purged = []
        for r in range(1, 9):
            self.tick("n")
            self.wait_for(lambda: self.state(node, "j-r%d" % r) == "ended")
            purged += self.tock("n").get("purged") or []
        old = sorted(os.listdir(aos7_task.old_dir(node)))
        self.assertLessEqual(len(old), 3, old)
        self.assertIn("j-r1", purged)
        self.assertNotIn("j-r1", old)

    def test_default_keeps_everything(self):
        node = self.mknode("n", [{"name": "j", "argv": ["true"]}])
        write_json(os.path.join(node, ".aos", "timeline.json"), {"keep_ended_rounds": 0})
        for r in range(1, 6):
            self.tick("n")
            self.wait_for(lambda: self.state(node, "j-r%d" % r) == "ended")
            self.tock("n")
        self.assertEqual(len(os.listdir(aos7_task.old_dir(node))), 4)   # r1～r4 都還在（只搬不刪）

    def test_retention_json(self):
        d = aos7_daemon.Daemon(self.root)
        self.addCleanup(os.close, d.rfd)
        for sub, k in (("ctl-done", 5), ("ctl-failed", 3)):
            for i in range(k):
                p = os.path.join(d.aosd, sub, "%d.json" % i)
                write_json(p, {"i": i})
                os.utime(p, (1000 + i, 1000 + i))
        for i in range(20):
            d.log(ev="x", i=i)
        d.retention()   # 沒有 retention.json：都不刪
        self.assertEqual(len(os.listdir(os.path.join(d.aosd, "ctl-done"))), 5)
        write_json(os.path.join(d.aosd, "retention.json"), {"ctl_done_max": 2, "ctl_failed_max": 1, "log_max_bytes": 100})
        d.retention()
        self.assertEqual(sorted(os.listdir(os.path.join(d.aosd, "ctl-done"))), ["3.json", "4.json"])
        self.assertEqual(os.listdir(os.path.join(d.aosd, "ctl-failed")), ["2.json"])
        self.assertTrue(os.path.exists(os.path.join(d.aosd, "log.1.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(d.aosd, "log.jsonl")))
        d.log(ev="y")
        self.assertEqual([e["ev"] for e in read_jsonl(os.path.join(d.aosd, "log.jsonl"))], ["y"])

    def test_status_disk(self):
        node = self.mknode("n", [{"name": "j", "argv": ["true"]}])
        self.start_daemon()
        disk = self.wait_for(lambda: self.status().get("disk", {}).get("nodes", {}).get("n"))
        self.assertIn("tasks_old", disk)
        self.assertGreater(self.status()["disk"]["aosd_bytes"], 0)
        self.ctl("stop", "--kill")


class H09RunnerFdContract(CoreCase):
    """H-09（技術選型）：aos7-run 第二參數是繼承的目錄 fd；無效時 stderr 說清楚、退出碼 2，不回退寫第一參數的路徑。"""

    def test_bad_fd_is_diagnosed(self):
        node = self.mknode("n")
        d = self.tdir(node, "x-r1")
        os.makedirs(d)
        write_json(os.path.join(d, "birth.json"), {"tid": "x-r1", "argv": ["true"]})
        reg = os.open(os.path.join(node, "waiter.py"), os.O_RDONLY)
        self.addCleanup(os.close, reg)
        for arg, fds in (("abc", ()), ("999", ()), (str(reg), (reg,))):
            p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-run"), d, arg], cwd=node, pass_fds=fds,
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 2, arg)
            self.assertIn("不是繼承來的任務資料夾 fd", p.stderr)
            self.assertFalse(os.path.exists(os.path.join(d, "exit.json")), arg)
            self.assertFalse(os.path.exists(os.path.join(d, "out.log")), arg)


if __name__ == "__main__":
    unittest.main()
