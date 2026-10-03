"""astra-5 第二節 F-01～F-11 的回歸測試（notes/play/2026-10-03-astra-5-infra.md；重現情境照同名 -evidence/）。"""
import errno
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import types
import unittest
from unittest import mock

import _proc
from test_core import BIN, LIB, SLEEPER, CoreCase
from test_core_daemon import DaemonCase
import aos7_agent
import aos7_daemon
import aos7_daemon_timeline
import aos7_fs
import aos7_kernel
import aos7_kernel_rules as rules
import aos7_mount
import aos7_task
from aos7_fs import read_json, read_jsonl, write_json

# 主程序 fork 出一個孫程序（同群組、環境沒動）睡著，自己馬上結束；孫程序 pid 寫到 $AOS7_TASK/kid
FORKER = ["python3", "-c", "import os,time\npid=os.fork()\nif pid==0:\n    %stime.sleep(60)\n    os._exit(0)\n"
          "open(os.path.join(os.environ['AOS7_TASK'],'kid'),'w').write(str(pid))\n"]


def hook_env(root, code):
    """在 root/hook/sitecustomize.py 放 code，回帶 PYTHONPATH 的環境（只給要注入故障的子程序）。"""
    d = os.path.join(root, "hook")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sitecustomize.py"), "w") as f:
        f.write(code)
    return {"PYTHONPATH": d, "HOOK_LIB": LIB}


class F01StopSweep(DaemonCase):
    """F-01：主程序已結束、孫程序還活著；正常 SIGTERM daemon 也要收掉（同群組、環境相符；setsid 的靠環境）。"""

    def check(self, setsid):
        argv = list(FORKER)
        argv[2] = argv[2] % ("os.setsid();" if setsid else "")
        node = self.mknode("a", [{"name": "f", "mode": "keep", "argv": argv}])
        d = self.start_daemon()
        kidf = os.path.join(self.tdir(node, "f-r1"), "kid")
        self.wait_for(lambda: os.path.exists(os.path.join(self.tdir(node, "f-r1"), "exit.json")) and os.path.exists(kidf))
        with open(kidf) as f:
            kid = int(f.read())
        self.assertTrue(aos7_task.pid_alive(kid))
        d.send_signal(signal.SIGTERM)
        self.assertEqual(d.wait(timeout=15), 0)
        self.wait_for(lambda: not aos7_task.pid_alive(kid), timeout=3, msg="stop 後孫程序還活著")
        self.assertTrue(any(e["ev"] == "stop-sweep" and e["groups"] >= 1 for e in self.log()))

    def test_fork_same_group(self):
        self.check(False)

    def test_fork_setsid(self):
        self.check(True)


class F02ArchiveRace(CoreCase):
    """F-02：讀者列到舊路徑、還沒開檔時 tock 把任務搬到 tasks-old/：要到新位置重讀，不能當成「沒有」或 0。"""

    def fixture(self):
        node = os.path.join(self.root, "n")
        aos = os.path.join(node, ".aos")
        old, own = os.path.join(aos, "tasks", "worker-r1"), os.path.join(aos, "tasks", "worker-r3")
        write_json(os.path.join(aos, "timeline.json"), {"interval_ms": 100, "keep_ended_rounds": 0})
        write_json(os.path.join(aos, "round.json"), {"round": 3, "open": True, "started": []})
        for d, r in ((old, 1), (own, 3)):
            write_json(os.path.join(d, "birth.json"), {"name": "worker", "tid": os.path.basename(d), "round": r})
        write_json(os.path.join(old, "exit.json"), {"code": 0})
        write_json(os.path.join(old, "ended.json"), {"round": 1})
        write_json(os.path.join(old, "usage.json"), {"tokens": 1234})
        write_json(os.path.join(old, "state.json"), {"state": "act", "round": 2, "steps": 9, "pc": 4})
        write_json(os.path.join(old, "kernel-state.json"), dict(rules.empty_state(), sentinel="inherited"))
        env = {"root": self.root, "node": node, "node_id": "n", "task": own, "tid": "worker-r3"}
        return node, aos, old, env

    def race(self, module, target, call):
        """target 檔第一次被讀之前跑一次真的 aos7-tock（把 worker-r1 搬走），再放行讀取。"""
        real = aos7_fs.read_json
        fired = []

        def hooked(path, *a, **kw):
            if str(path) == target and not fired:
                fired.append(True)
                self.prog("aos7-tock", self.root, "n")
            return real(path, *a, **kw)
        with mock.patch.object(module, "read_json", hooked):
            out = call()
        self.assertTrue(fired)
        return out

    def test_agent_state(self):
        node, aos, old, env = self.fixture()
        st = self.race(aos7_agent, os.path.join(old, "state.json"), lambda: aos7_agent.load_state(env))
        self.assertTrue(os.path.isdir(os.path.join(aos, "tasks-old", "worker-r1")))
        self.assertEqual((st["state"], st["steps"], st["from"]), ("act", 9, "worker-r1"))

    def test_kernel_state(self):
        node, aos, old, env = self.fixture()
        st = self.race(aos7_fs, os.path.join(old, "kernel-state.json"), lambda: aos7_kernel.load_state(env))
        self.assertEqual((st.get("sentinel"), st.get("inherited_from")), ("inherited", "worker-r1"))

    def test_usage_total(self):
        node, aos, old, env = self.fixture()
        snap = self.race(aos7_fs, os.path.join(old, "usage.json"), lambda: rules.snapshot_node(aos))
        self.assertEqual(snap["usage_total"], 1234)
        self.assertFalse([t for t in snap["tasks"] if t["tid"] == "worker-r1"][0]["alive"])

    def test_vanished_is_unknown_not_zero(self):
        node, aos, old, env = self.fixture()
        real = aos7_fs.read_json

        def hooked(path, *a, **kw):
            if str(path) == os.path.join(old, "usage.json"):
                shutil.rmtree(old)   # 讀到一半整個不見（不是搬走）：讀不齊
            return real(path, *a, **kw)
        with mock.patch.object(aos7_fs, "read_json", hooked):
            snap = rules.snapshot_node(aos)
        self.assertIsNone(snap["usage_total"])
        self.assertEqual(snap["unknown"], ["worker-r1"])
        # 規則遇到 unknown：不更新基準、不 pause、不歸零
        st = {"usage": {"m": {"last": 1234, "acc": 50}}, "paused": {}, "progress": {}, "issued": {}}
        snap2 = {"round": 5, "node_id": "k", "self_tid": "k-r1", "self_tasks": [],
                 "members": {"m": dict(snap, paused_by_daemon=False)}}
        out, new = rules.run_rules({"members": ["m"], "budget_tokens": 10}, st, snap2)
        self.assertEqual(out, [])
        self.assertEqual(new["usage"]["m"], {"last": 1234, "acc": 50})


class F03ScanError(CoreCase):
    """F-03：一次 ESTALE／EIO 看不到 node，不能當它消失而 kill 上面的活任務；確定不存在才走 Q4。"""

    def setUp(self):
        super().setUp()
        self.node = os.path.join(self.root, "n")
        write_json(os.path.join(self.node, ".aos", "timeline.json"), {"interval_ms": 100})
        self.d = aos7_daemon.Daemon(self.root)
        os.makedirs(self.d.aosd, exist_ok=True)
        self.d.paused.add("n")   # 真的 Timeline，但 paused：不跑動作
        self.d.scan()
        self.addCleanup(self.stop_daemon_obj)
        tid = aos7_task.start_task(self.root, "n", {"name": "s", "argv": SLEEPER}, 1)
        self.pid = self.wait_for(lambda: read_json(os.path.join(aos7_task.task_dir(self.node, tid), "pid.json")))
        self.d.live_of("n", self.d.timelines["n"])

    def stop_daemon_obj(self):
        """先讓時間線與收 node 的背景 thread 都結束（它們會寫 log），之後才輪到刪空間（N-55）。"""
        self.d.stop(False)
        for t in list(self.d.timelines.values()) + self.d.reapers:
            t.join(5)

    def assert_kept(self):
        self.assertIn("n", self.d.timelines)
        self.assertEqual(self.d.io_errors, 1)
        self.assertTrue(any(e["ev"] == "scan-error" for e in read_jsonl(os.path.join(self.d.aosd, "log.jsonl"))))
        time.sleep(0.3)
        self.assertTrue(aos7_task.pid_alive(self.pid["pid"]), "看不到就被 kill 了")
        self.d.guard(self.d.scan)   # 恢復後重掃：還在
        self.assertIn("n", self.d.timelines)

    def test_estale_scandir(self):
        real = os.scandir

        def faulty(path):
            if os.fspath(path) == self.node:
                raise OSError(errno.ESTALE, "simulated stale handle", self.node)
            return real(path)
        with mock.patch("os.scandir", faulty):
            self.d.guard(self.d.scan)
        self.assert_kept()

    def test_eio_timeline_stat(self):
        real = os.stat
        tl = os.path.join(self.node, ".aos", "timeline.json")

        def faulty(path, *a, **kw):
            if os.fspath(path) == tl:
                raise OSError(errno.EIO, "simulated I/O error")
            return real(path, *a, **kw)
        with mock.patch("os.stat", faulty):
            self.d.guard(self.d.scan)
        self.assert_kept()

    def test_really_gone_still_killed(self):
        shutil.rmtree(self.node)
        self.d.guard(self.d.scan)
        self.assertNotIn("n", self.d.timelines)
        self.wait_for(lambda: not aos7_task.pid_alive(self.pid["pid"]), msg="確定消失卻沒收")
        self.assertEqual(self.d.io_errors, 0)


class F04StaleHolder(DaemonCase):
    """F-04：daemon 被 kill -9 時舊動作還拿著 action.lock；新 daemon 的動作等鎖逾時，認出舊世代＋同一程序就 SIGKILL 它。"""

    HOLD = ("import os,sys,time\nsys.path.insert(0,%r)\nimport aos7_fs\n"
            "with aos7_fs.action_lock(%r, %r) as ok:\n    open(%r,'w').write('held')\n    time.sleep(60)\n")

    def test_new_daemon_reaps_old_holder(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 100, "action_timeout_s": 0.3})
        write_json(os.path.join(self.root, ".aosd", "gen.json"), {"gen": 5})
        mark = os.path.join(self.root, "held")
        holder = _proc.track(self, subprocess.Popen([sys.executable, "-c", self.HOLD % (LIB, self.root, node, mark)],
                                                    env=dict(os.environ, AOS7_GEN="5")))
        self.wait_for(lambda: os.path.exists(mark))
        self.assertEqual(read_json(os.path.join(node, ".aos", "action.owner.json"))["gen"], 5)
        self.start_daemon()   # gen 6
        self.wait_for(lambda: (read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0) >= 2,
                      timeout=10, msg="新 daemon 一直卡在舊持有者的鎖上")
        self.assertEqual(holder.wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(any(e["ev"] == "stale-holder-kill" and e["pid"] == holder.pid for e in self.log()))
        self.assertTrue(os.path.exists(os.path.join(node, ".aos", "action.lock")))   # 不 unlink 鎖檔

    def test_not_same_process_not_killed(self):
        node = self.mknode("a")
        victim = _proc.track(self, subprocess.Popen(["sleep", "30"]))
        write_json(os.path.join(node, ".aos", "action.owner.json"),
                   {"pid": victim.pid, "gen": 1, "starttime": aos7_fs.proc_starttime(victim.pid) + 1})
        self.assertIsNone(aos7_fs.reap_stale_owner(node, 2))   # 啟動時間不符：pid 被重用了，不打
        write_json(os.path.join(node, ".aos", "action.owner.json"),
                   {"pid": victim.pid, "gen": 2, "starttime": aos7_fs.proc_starttime(victim.pid)})
        self.assertIsNone(aos7_fs.reap_stale_owner(node, 2))   # 同世代：不是舊 daemon 的
        self.assertIsNone(victim.poll())


TOCK_STALL = """import os, sys, time
if os.path.basename(sys.argv[0]) == "aos7-tock" and not os.path.exists(os.environ["HOOK_MARK"]):
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_fs
    _orig = aos7_fs.append_jsonl
    def _stall(path, obj):
        _orig(path, obj)
        if path.endswith("/rounds.jsonl"):
            open(os.environ["HOOK_MARK"], "w").write(str(os.getpid()))
            time.sleep(60)   # 總結寫完、ended.json 與 round.json 還沒寫：等 daemon 逾時 SIGKILL
    aos7_fs.append_jsonl = _stall
"""


class F05SummaryOnce(DaemonCase):
    """F-05：同一回合的總結只寫一行；寫完總結就被殺的 tock，補做時只收尾，round.json 標 incomplete。"""

    def test_same_round_replay(self):
        node = self.mknode("a", [{"name": "done", "argv": ["/bin/true"]}])
        self.tick()
        self.wait_for(lambda: os.path.exists(os.path.join(self.tdir(node, "done-r1"), "exit.json")))
        first = self.tock()
        # 模擬「append 之後就被 kill」：round.json 還開著、ended.json 沒寫
        r = read_json(os.path.join(node, ".aos", "round.json"))
        write_json(os.path.join(node, ".aos", "round.json"), dict(r, open=True, tock_at=None))
        os.remove(os.path.join(self.tdir(node, "done-r1"), "ended.json"))
        # 摘要之後才結束的任務：重做不能替它寫 ended.json（它要在下一回合被報）
        late = self.tdir(node, "late-r1")
        write_json(os.path.join(late, "birth.json"), {"tid": "late-r1", "name": "late", "round": 1})
        write_json(os.path.join(late, "exit.json"), {"code": 0})
        again = self.tock()
        self.assertTrue(again["replayed"])
        self.assertEqual(again["ended"], first["ended"])
        rows = read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))
        self.assertEqual([x["round"] for x in rows], [1])
        rj = read_json(os.path.join(node, ".aos", "round.json"))
        self.assertEqual((rj["open"], rj["replayed"], rj["incomplete"]), (False, True, "tock"))
        self.assertTrue(os.path.exists(os.path.join(self.tdir(node, "done-r1"), "ended.json")))
        self.assertFalse(os.path.exists(os.path.join(late, "ended.json")))
        self.tick()
        nxt = self.tock()
        tids = [e["tid"] for e in nxt["ended"]]
        self.assertIn("late-r1", tids)        # 沒漏
        self.assertNotIn("done-r1", tids)     # 也沒重報

    def test_timeout_after_summary(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 100, "action_timeout_s": 0.4})
        write_json(os.path.join(node, ".aos", "spawn", "one.json"), {"name": "one", "argv": ["/bin/true"]})
        mark = os.path.join(self.root, "mark")
        self.start_daemon(env=dict(hook_env(self.root, TOCK_STALL), HOOK_MARK=mark))
        rj = os.path.join(node, ".aos", "round.json")
        self.wait_for(lambda: (read_json(rj, {}) or {}).get("round", 0) >= 3, timeout=15)
        rows = read_jsonl(os.path.join(node, ".aos", "rounds.jsonl"))
        rounds = [x["round"] for x in rows]
        self.assertEqual(len(rounds), len(set(rounds)), rounds)   # 同回合不寫兩行
        reported = [e["tid"] for x in rows for e in x.get("ended", [])]
        self.assertEqual(reported.count("one-r1"), 1, rows)       # 下一回合也不重報
        logs = [e for e in self.log() if e["ev"] == "tock" and e.get("replay")]
        self.assertTrue(logs and logs[0].get("replayed"), self.log())
        self.assertTrue(os.path.exists(mark))


class F06Isolation(CoreCase):
    """F-06：壞項目、壞回條、壞 interval、壞 tock.json 都只影響自己，健康的照起。"""

    def test_numeric_name_first(self):
        node = self.mknode("a", [{"name": 123, "argv": ["/bin/true"]}, {"name": "ok", "argv": ["/bin/true"]}])
        for r in (1, 2, 3):
            out = self.tick()
            self.assertIn("ok-r%d" % r, out["started"])
            self.tock()
        self.assertTrue(any("123" in e for e in read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]))

    def test_poison_batch(self):
        node = self.mknode("a", [{"name": "regular", "argv": ["/bin/true"]}])
        write_json(os.path.join(node, ".aos", "spawn", "b.json"),
                   {"batch": [{"name": "prefix", "argv": ["/bin/true"]}, {"name": 7, "argv": ["/bin/true"]},
                              {"name": "suffix", "argv": ["/bin/true"]}, 5]})
        out = self.tick()
        self.assertEqual(sorted(out["started"]), ["prefix-r1", "regular-r1", "suffix-r1"])
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "b.json")))
        errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
        self.assertEqual(len(errs), 2, errs)

    def test_ctl_receipt_dir(self):
        node = self.mknode("a", [{"name": "ok", "argv": ["/bin/true"]}])
        bad = self.tdir(node, "old-r1")
        write_json(os.path.join(bad, "birth.json"), {"tid": "old-r1", "name": "old", "round": 1})
        write_json(os.path.join(bad, "exit.json"), {"code": 0})
        os.makedirs(os.path.join(bad, "ctl-done.json"))
        write_json(os.path.join(bad, "ctl.json"), {"op": "bogus"})
        for r in (1, 2):
            out = self.tick()
            self.assertIn("ok-r%d" % r, out["started"])
            summary = self.tock()
            self.assertEqual(summary["round"], r)
        rec = [c for c in summary["ctl"] if c["tid"] == "old-r1"]
        self.assertTrue(rec and rec[0]["ok"] is False and "err" in rec[0], summary["ctl"])

    def test_interval_huge_int(self):
        node = self.mknode("a")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 10 ** 309})
        tl = aos7_daemon_timeline.Timeline(types.SimpleNamespace(root=self.root), "a")
        self.assertEqual(tl.interval(), 1.0)
        self.assertEqual(tl.last_error["prog"], "timeline")

    def test_wait_tock_non_object(self):
        tdir = os.path.join(self.root, "t")
        for bad in ([1], 2):
            write_json(os.path.join(tdir, "tock.json"), bad)
            p = subprocess.run([sys.executable, os.path.join(BIN, "aos7-wait-tock"), "--task", tdir, "--timeout", "0.2"],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual((p.returncode, p.stderr), (1, ""))   # 當沒有、等到逾時，不是 AttributeError
        self.assertIsNone(aos7_fs.wait_tock(tdir, 0, timeout=0.05))


class F07MountReceipt(CoreCase):
    """F-07：加掛已生效但回條寫不進去：請求留著、記錯、不連坐；修好後重處理是冪等的，補回條、刪請求。"""

    def test_receipt_dir(self):
        node = self.mknode("a")
        os.makedirs(os.path.join(self.root, "b", "inbox"))
        tdir = self.tdir(node, "t-r1")
        write_json(os.path.join(tdir, "birth.json"), {"tid": "t-r1", "name": "t", "round": 1, "mounts": {}})
        aos7_mount.request(tdir, "b/inbox")
        name = aos7_mount.req_name("b/inbox")
        aos7_mount.request(tdir, "a")   # 同一輪另一個請求
        os.makedirs(os.path.join(tdir, "mount-done", name + ".json"))
        res = aos7_mount.serve(self.root, tdir, None)
        by = {r["path"]: r for r in res}
        self.assertIn("receipt_error", by["b/inbox"])
        self.assertTrue(by["a"]["ok"])
        self.assertTrue(os.path.exists(os.path.join(tdir, "mount-req", name + ".json")))   # 請求留著
        self.assertTrue(os.path.islink(os.path.join(tdir, "mnt", name)))                  # 加掛已生效
        os.rmdir(os.path.join(tdir, "mount-done", name + ".json"))
        res = aos7_mount.serve(self.root, tdir, None)
        self.assertEqual([(r["path"], r["ok"], r["msg"]) for r in res], [("b/inbox", True, "已經掛了")])
        self.assertTrue(read_json(os.path.join(tdir, "mount-done", name + ".json"))["result"]["ok"])
        self.assertFalse(os.path.exists(os.path.join(tdir, "mount-req", name + ".json")))


class F08SubrootFirstScan(DaemonCase):
    """F-08：子根已宣告、還沒有 `.aosd/`：父 daemon 第一次掃描也不能先收裡面的 node（三次冷啟動）。"""

    def test_three_cold_starts(self):
        for i in range(3):
            root = os.path.join(self.root, "r%d" % i)
            child = os.path.join(root, "n", "child")
            self.mknode("n", [{"name": "kid", "mode": "keep", "argv": SLEEPER, "subroot": "n/child"}], root=root)
            self.mknode("n", [{"name": "leaf", "mode": "keep", "argv": SLEEPER}], root=child)
            d = self.start_daemon(root)
            self.wait_for(lambda: os.path.isdir(os.path.join(child, ".aosd")))
            time.sleep(0.3)
            adopted = [e["node"] for e in self.log(root) if e["ev"] == "node+"]
            self.assertEqual(adopted, ["n"], "第 %d 次：父收了子根裡的 node" % i)
            self.assertFalse(os.path.exists(os.path.join(child, "n", ".aos", "tasks")))
            d.send_signal(signal.SIGTERM)
            d.wait(timeout=15)


TICK_FREEZE = """import os, sys, signal
if os.path.basename(sys.argv[0]) == os.environ["HOOK_PROG"]:
    sys.path.insert(0, os.environ["HOOK_LIB"])
    import aos7_fs
    name = "write_json" if os.environ["HOOK_PROG"] == "aos7-tick" else "append_jsonl"
    suffix = "/.aos/round.json" if name == "write_json" else "/.aos/rounds.jsonl"
    _orig = getattr(aos7_fs, name)
    def _hold(path, obj):
        if path.endswith(suffix) and not os.path.exists(os.environ["HOOK_MARK"]):
            open(os.environ["HOOK_MARK"], "w").write(str(os.getpid()))
            os.kill(os.getpid(), signal.SIGSTOP)
        return _orig(path, obj)
    setattr(aos7_fs, name, _hold)
"""


class F09GoneMidAction(CoreCase):
    """F-09：tick／tock 拿到鎖之後、寫 round／總結之前 node 被刪或搬走：不在舊路徑建出鬼目錄；搬走的寫到新位置。"""

    def run_case(self, prog, change):
        node = self.mknode("n")
        write_json(os.path.join(node, ".aos", "round.json"), {"round": 1, "open": True, "started": [], "ctl": [],
                                                              "mounts": []})
        mark = os.path.join(self.root, "mark")
        env = dict(os.environ, **hook_env(self.root, TICK_FREEZE), HOOK_PROG=prog, HOOK_MARK=mark)
        p = _proc.track(self, subprocess.Popen([sys.executable, os.path.join(BIN, prog), self.root, "n"], env=env,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        self.wait_for(lambda: os.path.exists(mark), timeout=5)
        moved = os.path.join(self.root, "moved")
        if change == "delete":
            shutil.rmtree(node)
        else:
            os.rename(node, moved)
        os.kill(p.pid, signal.SIGCONT)
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0, err)
        self.assertFalse(os.path.exists(node), "舊路徑被建回來了")
        res = json.loads(out.strip().splitlines()[-1])
        if change == "delete":
            self.assertTrue(res.get("gone"), res)
        else:
            rj = read_json(os.path.join(moved, ".aos", "round.json"))
            if prog == "aos7-tick":
                self.assertEqual((rj["round"], rj["open"]), (2, True))
            else:
                self.assertEqual(rj["open"], False)
                self.assertEqual([x["round"] for x in read_jsonl(os.path.join(moved, ".aos", "rounds.jsonl"))], [1])

    def test_tick_delete(self):
        self.run_case("aos7-tick", "delete")

    def test_tick_rename(self):
        self.run_case("aos7-tick", "rename")

    def test_tock_delete(self):
        self.run_case("aos7-tock", "delete")

    def test_tock_rename(self):
        self.run_case("aos7-tock", "rename")


class F10CtlFlood(DaemonCase):
    """F-10：一萬個 wake 不能一次佔住主迴圈：每圈有件數／時間預算，順序照檔名，status 照常更新。"""

    def test_budget_per_loop(self):
        d = aos7_daemon.Daemon(self.root)
        cdir = os.path.join(d.aosd, "ctl")
        for i in range(aos7_daemon.CTL_BATCH + 50):
            write_json(os.path.join(cdir, "w%05d.json" % i), {"op": "wake", "node": "a"})
        d.handle_ctl()
        left = sorted(os.listdir(cdir))
        self.assertTrue(d.ctl_backlog)
        self.assertGreaterEqual(len(left), 50)
        done = sorted(os.listdir(os.path.join(d.aosd, "ctl-done")))
        self.assertEqual(done[-1] < left[0], True)   # 處理過的都在沒處理的前面（照檔名）
        while os.listdir(cdir):
            d.handle_ctl()
        self.assertFalse(d.ctl_backlog)

    def test_status_moves_during_flood(self):
        self.mknode("a")
        self.start_daemon()
        self.wait_for(lambda: self.status().get("nodes", {}).get("a"))
        self.ctl("pause", "a")
        cdir = os.path.join(self.root, ".aosd", "ctl")
        tmp = os.path.join(self.root, "flood")
        os.makedirs(tmp)
        for i in range(5000):
            with open(os.path.join(tmp, "f%05d.json" % i), "w") as f:
                f.write('{"op": "wake", "node": "a"}')
        for n in sorted(os.listdir(tmp)):
            os.rename(os.path.join(tmp, n), os.path.join(cdir, n))
        ats = set()
        while os.listdir(cdir):
            ats.add(self.status().get("at"))
            time.sleep(0.02)
        self.assertGreater(len(ats), 2, "洪水期間 status 沒更新")


class F11ProcHelper(unittest.TestCase):
    """F-11／N-55：reap 先 terminate、逾時才 kill；不理 SIGTERM 的程序也收得掉，之後才刪空間。"""

    def test_reap_stubborn(self):
        p = subprocess.Popen([sys.executable, "-c", "import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                              "print('ready', flush=True)\ntime.sleep(60)"], stdout=subprocess.PIPE)
        _proc.track(self, p, grace=0.3)
        p.stdout.readline()
        t0 = time.monotonic()
        _proc.reap(p, grace=0.3)
        self.assertEqual(p.returncode, -signal.SIGKILL)
        self.assertLess(time.monotonic() - t0, 3)

    def test_cleanup_order(self):
        """addCleanup 後進先出：先登記的 rmtree 最後跑，Popen 後 track 的 reap 先跑。"""
        seen = []
        case = unittest.TestCase()
        p = None
        case.addCleanup(lambda: seen.append(p.poll()))   # 「rmtree」：跑的時候程序要已經收掉
        p = subprocess.Popen(["sleep", "30"])
        _proc.track(case, p)
        case.doCleanups()
        self.assertEqual(seen, [-signal.SIGTERM])


if __name__ == "__main__":
    unittest.main()
