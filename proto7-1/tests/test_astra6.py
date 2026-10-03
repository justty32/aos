"""astra-6 第二節 G-01～G-10 的回歸測試（notes/play/2026-10-03-astra-6-infra.md；重現情境照同名 -evidence/）。"""
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest

import _proc
from test_astra5 import TICK_FREEZE, hook_env
from test_core import BIN, LIB, SLEEPER, CoreCase
from test_core_daemon import DaemonCase
import aos7_daemon
import aos7_fs
import aos7_mount
import aos7_task
from aos7_fs import read_json, read_jsonl, write_json

HERE = os.path.dirname(os.path.abspath(__file__))


class G01CtlReceiptPoison(DaemonCase):
    """G-01：daemon 控制檔的回條寫不進去（ctl-done/<名>.json 是資料夾），不能擋住同圈後面的 stop。"""

    def test_poisoned_receipt_does_not_block_stop(self):
        self.mknode("n")
        write_json(os.path.join(self.root, ".aosd", "paused.json"), {"paused": ["n"]})
        os.makedirs(os.path.join(self.root, ".aosd", "ctl-done", "000.json"))
        write_json(os.path.join(self.root, ".aosd", "ctl", "000.json"), {"op": "wake", "node": "n"})
        write_json(os.path.join(self.root, ".aosd", "ctl", "001.json"), {"op": "stop", "kill": True})
        p = self.start_daemon()
        self.assertEqual(p.wait(timeout=10), 0, "stop 被前一件壞回條擋住")
        self.assertTrue(read_json(os.path.join(self.root, ".aosd", "ctl-done", "001.json"))["result"]["ok"])
        self.assertTrue(os.path.isfile(os.path.join(self.root, ".aosd", "ctl-failed", "000.json")))
        self.assertEqual(os.listdir(os.path.join(self.root, ".aosd", "ctl")), [])
        errs = [e for e in self.log() if e["ev"] == "ctl-error"]
        self.assertEqual([e["file"] for e in errs], ["000.json"], errs)
        self.assertEqual(errs[0]["moved_to"], "ctl-failed/000.json")
        self.assertEqual(self.status()["last_ctl_error"]["file"], "000.json")

    def test_unmovable_failure_goes_last(self):
        d = aos7_daemon.Daemon(self.root)
        os.makedirs(os.path.join(d.aosd, "ctl-done", "000.json"))
        with open(os.path.join(d.aosd, "ctl-failed"), "w") as f:   # 連 ctl-failed/ 都建不了：只能留在 ctl/
            f.write("x")
        write_json(os.path.join(d.aosd, "ctl", "000.json"), {"op": "pause", "node": "n"})
        write_json(os.path.join(d.aosd, "ctl", "001.json"), {"op": "wake", "node": "n"})
        d.handle_ctl()
        self.assertEqual(d.ctl_stuck, {"000.json"})
        self.assertEqual(os.listdir(os.path.join(d.aosd, "ctl")), ["000.json"])
        write_json(os.path.join(d.aosd, "ctl", "0005.json"), {"op": "stop"})
        d.handle_ctl()   # 新來的、檔名排在後面的照樣先處理
        self.assertTrue(d.stopping)
        self.assertTrue(read_json(os.path.join(d.aosd, "ctl-done", "0005.json"))["result"]["ok"])


class G02MovedDuringStart(CoreCase):
    """G-02：tick 抓著 node fd 期間 node 被搬走（或換成符號連結）：不照舊路徑建掛載、runner 不走別的 node，
    起不來就受控失敗寫 exit.json（不留 born），新位置再 tick 會由 keep 重起。"""

    def freeze_tick(self, items):
        node = self.mknode("n", items)
        other = self.mknode("other")
        write_json(os.path.join(other, "sentinel.json"), {"unchanged": True})
        mark = os.path.join(self.root, "mark")
        env = dict(os.environ, **hook_env(self.root, TICK_FREEZE), HOOK_PROG="aos7-tick", HOOK_MARK=mark)
        p = _proc.track(self, subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-tick"), self.root, "n"],
                                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        self.wait_for(lambda: os.path.exists(mark), timeout=5)
        return node, other, p

    def finish(self, p, before_retick=lambda: None):
        os.kill(p.pid, signal.SIGCONT)
        out, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 0, err)
        moved = os.path.join(self.root, "moved")
        rj = read_json(os.path.join(moved, ".aos", "round.json"))
        self.assertEqual(rj["started"], ["x-r1"])
        d = self.tdir(moved, "x-r1")
        self.assertEqual(aos7_task.task_state(d), "ended", "任務停在 born")
        ex = read_json(os.path.join(d, "exit.json"))
        self.assertEqual(ex["code"], 127)
        self.assertIn("搬走", ex["error"])
        before_retick()
        self.assertEqual(self.prog("aos7-tick", self.root, "moved")["started"], ["x-r2"])   # 新位置 keep 重起
        self.wait_for(lambda: self.state(moved, "x-r2") == "live")
        return moved

    def test_rename_with_mount(self):
        node, other, p = self.freeze_tick([{"name": "x", "mode": "keep", "argv": SLEEPER, "mounts": {"box": "n/inbox"}}])
        os.rename(node, os.path.join(self.root, "moved"))
        # 宣告寫的是 n/inbox：新位置再 tick 時照宣告建它是對的；要看的是被打斷的那次 tick 有沒有建回舊 node
        self.finish(p, lambda: self.assertFalse(os.path.exists(node), "掛載把舊 node 建回來了"))

    def test_symlink_swap(self):
        node, other, p = self.freeze_tick([{"name": "x", "mode": "keep", "argv": SLEEPER}])
        os.rename(node, os.path.join(self.root, "moved"))
        os.symlink(other, node, target_is_directory=True)
        self.finish(p)
        self.assertFalse(os.path.exists(os.path.join(other, ".aos", "tasks")), "任務跑到 other 去了")
        self.assertEqual(read_json(os.path.join(other, "sentinel.json")), {"unchanged": True})

    def test_runner_follows_held_taskdir(self):
        """aos7-run 拿任務資料夾的 fd：node 在它起來前被搬走，pid／exit 照樣寫進新位置；讀不到 birth 也寫 exit。"""
        node = self.mknode("n")
        for tid, birth in (("ok", {"tid": "ok", "argv": ["true"]}), ("nobirth", None)):
            d = self.tdir(node, tid)
            os.makedirs(d)
            if birth:
                write_json(os.path.join(d, "birth.json"), birth)
        fds = {t: os.open(self.tdir(node, t), os.O_RDONLY | os.O_DIRECTORY) for t in ("ok", "nobirth")}
        nfd = os.open(node, os.O_RDONLY | os.O_DIRECTORY)
        moved = os.path.join(self.root, "moved")
        os.rename(node, moved)
        try:
            for t, fd in fds.items():
                subprocess.run([sys.executable, os.path.join(BIN, "aos7-run"), self.tdir(node, t), str(fd)],
                               cwd="/proc/self/fd/%d" % nfd, pass_fds=(fd, nfd), timeout=10)
        finally:
            for fd in list(fds.values()) + [nfd]:
                os.close(fd)
        self.assertFalse(os.path.exists(node))
        self.assertEqual(read_json(os.path.join(self.tdir(moved, "ok"), "exit.json"))["code"], 0)
        ex = read_json(os.path.join(self.tdir(moved, "nobirth"), "exit.json"))
        self.assertEqual(ex["code"], 127)
        self.assertEqual(aos7_task.task_state(self.tdir(moved, "nobirth")), "ended")


class G03DaemonRootMoved(DaemonCase):
    """G-03：daemon 的 root 被搬走：自己的 status／log 不照舊路徑建回來，當 root 消失照 stop 收尾。"""

    def test_root_rename(self):
        sub = os.path.join(self.root, "n", "sub")
        node = self.mknode("w", [{"name": "s", "mode": "keep", "argv": SLEEPER}], root=sub)
        p = self.start_daemon(sub)
        pid = self.wait_for(lambda: read_json(os.path.join(self.tdir(node, "s-r1"), "pid.json")))["pid"]
        os.rename(os.path.join(self.root, "n"), os.path.join(self.root, "m"))
        self.assertEqual(p.wait(timeout=15), 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, "n")), "舊根被建回來了")
        msub = os.path.join(self.root, "m", "sub")
        self.assertTrue(any(e["ev"] == "root-gone" for e in self.log(msub)))
        self.assertTrue(self.status(msub)["root_gone"])
        self.wait_for(lambda: not aos7_task.pid_alive(pid), timeout=5, msg="搬家後舊任務還活著（Q4）")


class G04OwnerClaim(DaemonCase):
    """G-04：子根已有 daemon 拿著 daemon.lock：第二個任務不起、不改 owner.json，記 tasks_error。"""

    def test_running_subroot_keeps_owner(self):
        node = self.mknode("lab", [{"name": "d", "mode": "keep", "argv": SLEEPER, "subroot": "lab/sub"}])
        self.assertEqual(self.tick("lab")["started"], ["d-r1"])
        opath = os.path.join(node, "sub", ".aosd", "owner.json")
        first = {"node": "lab", "tid": "d-r1", "allow_stop": False, "at": "t"}
        write_json(opath, first)   # astra-7 H-02：owner.json 由拿到鎖的子 daemon 寫；這裡模擬 d-r1 的子 daemon
        with open(os.path.join(node, "sub", ".aosd", "daemon.lock"), "w") as lk:   # 模擬 d-r1 起的子 daemon 在跑
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.tock("lab")
            write_json(os.path.join(node, ".aos", "spawn", "second.json"),
                       {"name": "other", "argv": SLEEPER, "subroot": "lab/sub", "allow_stop": True})
            self.assertEqual(self.tick("lab")["started"], [])
            errs = read_json(os.path.join(node, ".aos", "round.json"))["tasks_error"]
            self.assertTrue(any("已經有 daemon 在跑" in e and "d-r1" in e for e in errs), errs)
            self.assertEqual(read_json(opath), first)
            self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "second.json")))
        self.tock("lab")
        write_json(os.path.join(node, ".aos", "spawn", "third.json"),
                   {"name": "other", "argv": SLEEPER, "subroot": "lab/sub", "allow_stop": True})
        started = self.tick("lab")["started"]   # 鎖放了：照常起（owner.json 等它的子 daemon 拿到鎖才改）
        self.assertEqual(len(started), 1)
        self.assertEqual(read_json(opath), first)

    def test_real_second_daemon(self):
        """真的兩個 daemon：n 的 first 起 n/inner/sub；n/inner 的 second 宣告同一子根，不能改掉現役 owner。"""
        sub = os.path.join(self.root, "n", "inner", "sub")
        self.mknode("n", [{"name": "first", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_SUBROOT"],
                           "subroot": "n/inner/sub", "allow_stop": False}])
        self.start_daemon()
        st = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "status.json")))
        before = read_json(os.path.join(sub, ".aosd", "owner.json"))
        inner = self.mknode("n/inner", [{"name": "second", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_SUBROOT"],
                                         "subroot": "n/inner/sub", "allow_stop": True}])
        self.wait_for(lambda: any("已經有 daemon 在跑" in e for r in read_jsonl(os.path.join(inner, ".aos", "rounds.jsonl"))
                                  for e in r.get("tasks_error") or []), msg="second 沒被拒")
        self.assertEqual(read_json(os.path.join(sub, ".aosd", "owner.json")), before)
        self.assertEqual(read_json(os.path.join(sub, ".aosd", "status.json"))["pid"], st["pid"])
        write_json(os.path.join(sub, ".aosd", "ctl", "stop.json"), {"op": "stop", "kill": True})
        r = self.wait_for(lambda: read_json(os.path.join(sub, ".aosd", "ctl-done", "stop.json")))
        self.assertFalse(r["result"]["ok"], r)   # first 沒允許外部 stop


class G05ReloadValidates(CoreCase):
    """G-05：reload 先用第 4 節完整檢查驗原項目；mode／from_round／max_live 型別不對整個不執行、不 kill。"""

    def check(self, key, value):
        node = self.mknode("n", [{"name": "x", "mode": "keep", "argv": SLEEPER}])
        self.tick("n")
        pid = self.wait_for(lambda: read_json(os.path.join(self.tdir(node, "x-r1"), "pid.json")))["pid"]
        self.tock("n")
        write_json(os.path.join(node, ".aos", "tasks.json"),
                   {"tasks": [{"name": "x", "mode": "keep", "argv": SLEEPER + ["new"], key: value}]})
        write_json(os.path.join(self.tdir(node, "x-r1"), "ctl.json"), {"op": "restart", "reload": True})
        self.assertEqual(self.tick("n")["started"], [])
        r = read_json(os.path.join(self.tdir(node, "x-r1"), "ctl-done.json"))["result"]
        self.assertFalse(r["ok"], r)
        self.assertIn(key, r["msg"])
        self.assertIn("沒 kill", r["msg"])
        self.assertTrue(aos7_task.pid_alive(pid))
        self.assertFalse(os.path.exists(os.path.join(node, ".aos", "spawn", "restart-x-r1.json")))

    def test_mode(self):
        self.check("mode", "nonsense")

    def test_from_round(self):
        self.check("from_round", "bad")

    def test_max_live(self):
        self.check("max_live", "bad")


class G06ReloadDynMount(CoreCase):
    """G-06：動態加掛被 tasks.json 同名宣告接管後改標宣告來源；之後刪掉宣告再 reload 就真的拿掉，diff 看得到。"""

    def test_promote_then_remove(self):
        node = self.mknode("n", [{"name": "x", "mode": "keep", "argv": SLEEPER}])
        self.tick("n")
        self.wait_for(lambda: read_json(os.path.join(self.tdir(node, "x-r1"), "pid.json")))
        self.tock("n")
        name = aos7_mount.req_name("n/dyn")
        aos7_mount.request(self.tdir(node, "x-r1"), "n/dyn")
        self.tick("n")
        self.tock("n")
        self.assertTrue(read_json(os.path.join(self.tdir(node, "x-r1"), "birth.json"))["mounts"][name]["dyn"])

        def reload(tid, mounts):
            write_json(os.path.join(node, ".aos", "tasks.json"),
                       {"tasks": [{"name": "x", "mode": "keep", "argv": SLEEPER, "mounts": mounts}]})
            write_json(os.path.join(self.tdir(node, tid), "ctl.json"), {"op": "restart", "reload": True})
            new = self.tick("n")["started"][0]
            self.tock("n")
            return new, read_json(os.path.join(self.tdir(node, tid), "ctl-done.json"))["result"], \
                read_json(os.path.join(self.tdir(node, new), "birth.json"))["mounts"]

        t2, r1, m1 = reload("x-r1", {name: "n/static"})
        self.assertEqual(m1[name]["to"], "n/static")
        self.assertNotIn("dyn", m1[name], "被宣告接管後還標 dyn")
        t3, r2, m2 = reload(t2, {})
        self.assertNotIn(name, m2, "刪掉宣告後還留著")
        self.assertEqual(r2["diff"]["mounts"], {"old": {name: "n/static"}, "new": {}})

    def test_undeclared_dyn_still_carried(self):
        node = self.mknode("n", [{"name": "x", "mode": "keep", "argv": SLEEPER}])
        self.tick("n")
        self.wait_for(lambda: read_json(os.path.join(self.tdir(node, "x-r1"), "pid.json")))
        self.tock("n")
        name = aos7_mount.req_name("n/dyn")
        aos7_mount.request(self.tdir(node, "x-r1"), "n/dyn")
        self.tick("n")
        self.tock("n")
        write_json(os.path.join(self.tdir(node, "x-r1"), "ctl.json"), {"op": "restart", "reload": True})
        new = self.tick("n")["started"][0]
        m = read_json(os.path.join(self.tdir(node, new), "birth.json"))["mounts"]
        self.assertTrue(m[name]["dyn"])


ATEXIT_PARENT = """import json, os, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
k = os.fork()
if k == 0:
    time.sleep(60)
    os._exit(0)
open(sys.argv[1], "w").write(json.dumps({"parent": os.getpid(), "child": k}))
time.sleep(60)
"""
ATEXIT_HELPER = """import os, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import _proc
p = _proc.track(None, subprocess.Popen([sys.executable, sys.argv[2], sys.argv[3]], start_new_session=True),
                grace=0.1, group=True)
while not os.path.exists(sys.argv[3]):
    time.sleep(0.01)
# 正常結束 interpreter：走 atexit（Ctrl-C 時同一條路）
"""


class G07AtexitKeepsOptions(CoreCase):
    """G-07：_proc 的 atexit 沿用每筆登記的 group／grace：真的走 interpreter exit 時，同群組的孫程序也收掉。"""

    def test_interpreter_exit(self):
        parent, helper, ready = (os.path.join(self.root, x) for x in ("parent.py", "helper.py", "ready.json"))
        with open(parent, "w") as f:
            f.write(ATEXIT_PARENT)
        with open(helper, "w") as f:
            f.write(ATEXIT_HELPER)
        p = _proc.track(self, subprocess.Popen([sys.executable, helper, HERE, parent, ready]))
        t0 = time.monotonic()
        self.assertEqual(p.wait(timeout=10), 0)
        took = time.monotonic() - t0
        ids = read_json(ready)
        for pid in ids.values():
            self.addCleanup(lambda x=pid: os.kill(x, signal.SIGKILL) if aos7_task.pid_alive(x) else None)
        self.wait_for(lambda: not aos7_task.pid_alive(ids["child"]), timeout=2, msg="atexit 漏了同群組的孫程序")
        self.assertFalse(aos7_task.pid_alive(ids["parent"]))
        self.assertLess(took, 2.5, "atexit 沒用登記的 grace=0.1")


class G08TornSummary(CoreCase):
    """G-08：rounds.jsonl 尾端是沒寫完的半行：tock 先補換行再寫完整總結，確認提交後才寫 ended、關回合。"""

    def test_torn_tail_then_tock(self):
        node = self.mknode("n", [{"name": "one", "mode": "keep", "argv": ["true"]}])
        self.tick("n")
        self.wait_for(lambda: os.path.exists(os.path.join(self.tdir(node, "one-r1"), "exit.json")))
        rl = os.path.join(node, ".aos", "rounds.jsonl")
        with open(rl, "w") as f:   # 上次 tock append 到一半被殺：只留 JSON 前 24 字元
            f.write(json.dumps({"round": 1, "tick_at": "x", "ended": []})[:24])
        r = self.tock("n")
        self.assertEqual([e["tid"] for e in r["ended"]], ["one-r1"])
        rows = read_jsonl(rl)
        self.assertEqual([x["round"] for x in rows], [1])
        self.assertEqual([e["tid"] for e in rows[0]["ended"]], ["one-r1"])
        self.assertTrue(any(e["phase"] == "rounds.jsonl" for e in rows[0]["errors"]))
        self.assertTrue(os.path.exists(os.path.join(self.tdir(node, "one-r1"), "ended.json")))
        self.assertFalse(read_json(os.path.join(node, ".aos", "round.json"))["open"])
        self.tick("n")
        self.tock("n")
        self.assertEqual([x["round"] for x in read_jsonl(rl)], [1, 2])

    def test_read_jsonl_skips_bad_line(self):
        path = os.path.join(self.root, "x.jsonl")
        with open(path, "w") as f:
            f.write('{"a": 1}\n{"bro')
        self.assertEqual(aos7_fs.append_jsonl(path, {"b": 2}), 5)
        self.assertEqual(read_jsonl(path), [{"a": 1}, {"b": 2}])
        self.assertEqual(aos7_fs.append_jsonl(path, {"c": 3}), 0)


class G09SweepIdentity(CoreCase):
    """G-09（技術選型，文件）：stop-sweep 以 NODE＋TID 認程序、不比 ROOT；不同 NODE、沒有 TID 的不收。"""

    def test_node_tid_not_root(self):
        node = self.mknode("n")
        ps = {}
        for name, nd, root, tid in (("owned", node, self.root, "a"), ("other_root", node, "/elsewhere", "b"),
                                    ("foreign", os.path.join(self.root, "zz"), self.root, "c"),
                                    ("no_tid", node, self.root, None)):
            env = dict(os.environ, AOS7_NODE=nd, AOS7_ROOT=root)
            if tid:
                env["AOS7_TID"] = tid
            ps[name] = _proc.track(self, subprocess.Popen(["sleep", "30"], env=env, start_new_session=True))
        time.sleep(0.05)
        aos7_task.sweep_nodes([node])
        time.sleep(0.05)
        alive = {k: p.poll() is None for k, p in ps.items()}
        self.assertEqual(alive, {"owned": False, "other_root": False, "foreign": True, "no_tid": True})


class G10UnverifiedHolder(DaemonCase):
    """G-10：舊持鎖者身分無法驗證（owner.starttime 是 null）：照樣不殺，但 status 的 last_error 與 log 說明原因與恢復方法；
    補回身分後自動回收。"""

    HOLD = ("import os,sys,time\nsys.path.insert(0,%r)\nimport aos7_fs\n"
            "with aos7_fs.action_lock(%r, %r) as ok:\n    open(%r,'w').write('held')\n    time.sleep(60)\n")

    def test_unverified_then_repaired(self):
        node = self.mknode("n")
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 100, "action_timeout_s": 0.2})
        write_json(os.path.join(self.root, ".aosd", "gen.json"), {"gen": 1})
        mark = os.path.join(self.root, "held")
        holder = _proc.track(self, subprocess.Popen([sys.executable, "-c", self.HOLD % (LIB, self.root, node, mark)],
                                                    env=dict(os.environ, AOS7_GEN="1")))
        self.wait_for(lambda: os.path.exists(mark))
        opath = os.path.join(node, ".aos", "action.owner.json")
        ow = read_json(opath)
        write_json(opath, dict(ow, starttime=None))
        self.start_daemon()
        ev = self.wait_for(lambda: [e for e in self.log() if e["ev"] == "stale-holder-unverified"], msg="沒說明")[0]
        self.assertEqual(ev["pid"], holder.pid)
        self.assertIn("starttime", ev["why"])
        self.assertIn("action.lock", ev["hint"])
        err = self.wait_for(lambda: (self.status().get("nodes", {}).get("n", {}).get("last_error") or {}).get("err"))
        self.assertIn("stale-holder-unverified", err)
        self.assertIsNone(holder.poll(), "身分不明還是殺了")
        write_json(opath, ow)
        self.wait_for(lambda: (read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0) >= 1,
                      msg="補回身分後沒回收")
        self.assertEqual(holder.wait(timeout=5), -signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
