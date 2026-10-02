"""收屍／cgroup 模組驗收（plan m3m-daemon-modules.md 模組二）。真的開 bin/aos-daemon。

本檔：子樹、收屍、開機（Tree、Reap、Startup）。

要有委派的 cgroup v2：daemon 一律用 `systemd-run --user --scope -p Delegate=yes` 包起來開（scope 就是它的子樹根）。
這台拿不到（沒有 systemd-run、使用者層 systemd 沒在跑、沒有 cgroup.kill……）整組跳過，不算失敗。
「沒委派好時回 1」那條直接開 daemon，只在測試自己所在的 cgroup 寫不進去時才跑（WSL 的 /init.scope 就是）。

都用暫存資料夾、短週期、假 inst；等條件一律用 monotonic 計時的 wait_for，時限寬鬆。
收尾時對 scope 的根寫 cgroup.kill，連 daemon 帶殘留一起清掉。
"""
import os
import unittest

import aos_daemon_cgroup
from _util import PY
from _daemon_util import DAEMON, INHERIT, sh
from _cgroup_util import CG, CgCase, alive, cat, procs


# 留一個背景程序、記下它的 pid 就結束
LEAVE = "sleep 1000 & echo $! >> bg; exit 0"
# 用 setsid 跳出 session 再 double fork 的殘留
LEAVE_SETSID = "(setsid sh -c 'sleep 1000 & echo $! >> bg' &); sleep 0.2; exit 0"


class Tree(CgCase):

    def test_tree_and_names(self):
        # daemon 在 <根>/daemon；每項一個 i-<h>；根開了 controller；開框時印對照、在任何 exit= 之前
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "jobs/b.json")
        p, out, _ = self.boot({"a.json": {}, "jobs/b.json": {}}, 30000, modules=CG)
        self.wait_for(lambda: self.results(out, "a.json") and self.results(out, "jobs/b.json"), timeout=10)
        names = {aos_daemon_cgroup.frame_name(i) for i in ("a.json", "jobs/b.json")}
        dirs = {n for n in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, n))}
        self.assertEqual(dirs, names | {"daemon"})
        self.assertEqual(procs(os.path.join(self.root, "daemon")), [p.pid])
        self.assertEqual(procs(self.root), [])
        ctl = cat(os.path.join(self.root, "cgroup.subtree_control")).split()
        self.assertIn("memory", ctl)
        self.assertIn("pids", ctl)
        t = self.texts(out)
        for inst in ("a.json", "jobs/b.json"):
            line = "inst=%s cgroup=%s" % (inst, aos_daemon_cgroup.frame_name(inst))
            self.assertIn(line, t)
            self.assertLess(t.index(line), min(i for i, x in enumerate(t) if " exit=" in x))
        self.assertEqual(aos_daemon_cgroup.frame_name("a.json"),
                         "i-" + __import__("hashlib").sha256(b"a.json").hexdigest()[:16])

    def test_limits_written(self):
        self.inst({"argv": ["true"]}, "a.json")
        self.inst({"argv": ["true"]}, "b.json")
        p, out, _ = self.boot({"a.json": {"cgroup": {"memory.max": "64M", "pids.max": "50"}}, "b.json": {}},
                              30000, modules=CG)
        self.wait_for(lambda: self.results(out, "a.json"), timeout=10)
        self.assertEqual(cat(os.path.join(self.frame("a.json"), "memory.max")), str(64 * 1024 * 1024))
        self.assertEqual(cat(os.path.join(self.frame("a.json"), "pids.max")), "50")
        self.assertEqual(cat(os.path.join(self.frame("b.json"), "memory.max")), "max")    # 沒寫不設限

    def test_pids_max_applies(self):
        # 上限真的作用在任務上：pids.max=5，開 10 個 sleep 會有失敗的
        self.inst(sh("cat /sys/fs/cgroup$(sed -n 's/^0:://p' /proc/self/cgroup)/pids.max > seen; "
                     "for i in 1 2 3 4 5 6 7 8 9 10; do sleep 5 & done 2>/dev/null; exit 0"), "a.json")
        p, out, _ = self.boot({"a.json": {"cgroup": {"pids.max": "5"}}}, 30000, modules=CG)
        self.wait_for(lambda: self.results(out, "a.json"), timeout=10)
        self.assertEqual(self.read("seen").strip(), "5")
        self.assertGreater(int(cat(os.path.join(self.frame("a.json"), "pids.events")).split()[1]), 0)   # max <次數>


class Reap(CgCase):

    def test_background_reaped(self):
        self.inst(sh(LEAVE), "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules=CG)
        self.wait_for(lambda: self.has(out, "inst=a.json reaped"), timeout=10)
        t = self.texts(out)
        first_exit = min(i for i, x in enumerate(t) if x.startswith("inst=a.json exit=0 "))
        self.assertLess(first_exit, t.index("inst=a.json reaped"))         # exit= 在前、reaped 在後
        (pid,) = self.bg()
        self.assertFalse(alive(pid))
        self.assertEqual(procs(self.frame("a.json")), [])

    def test_setsid_reaped(self):
        self.inst(sh(LEAVE_SETSID), "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules=CG)
        self.wait_for(lambda: self.has(out, "inst=a.json reaped"), timeout=10)
        (pid,) = self.bg()
        self.assertFalse(alive(pid))
        self.assertEqual(procs(self.frame("a.json")), [])

    def test_no_leftover_no_reaped(self):
        self.inst({"argv": ["true"]}, "a.json")
        p, out, _ = self.boot({"a.json": {}}, 100, modules=CG)
        self.wait_for(lambda: len(self.results(out, "a.json")) >= 3, timeout=10)
        self.assertFalse(any(x.endswith(" reaped") for x in list(out)))

    def test_cleared_before_next_run(self):
        # 每次跑先看上一次留的還在不在，再留一個新的；週期短也不會疊著
        check = 'for q in $(cat bg 2>/dev/null); do kill -0 $q 2>/dev/null && echo $q >> bad; done; '
        self.inst(sh(check + LEAVE), "a.json")
        p, out, _ = self.boot({"a.json": {}}, 50, modules=CG)
        self.wait_for(lambda: len(self.bg()) >= 4, timeout=10)
        self.assertFalse(self.exists("bad"))
        self.assertGreaterEqual(sum(1 for x in list(out) if x.endswith(" inst=a.json reaped")), 3)

    def test_pipe_held_by_leftover(self):
        # 殘留拿著 aos-exec 的 stdout（exec_out_path 收的那條 pipe）：照樣印 exit=、輸出照寫
        self.inst(sh("echo hi; sleep 1000 & echo $! >> bg; exit 0", stdout=INHERIT), "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules=CG, exec_out_path="out.log")
        self.wait_for(lambda: self.has(out, "inst=a.json reaped"), timeout=10)
        self.assertEqual(self.results(out, "a.json"), [0])
        self.wait_for(lambda: self.exists("out.log"))
        self.assertIn("hi", self.read("out.log"))
        (pid,) = self.bg()
        self.assertFalse(alive(pid))

    def test_exit_code_kept(self):
        self.inst(sh("sleep 1000 & exit 7"), "a.json")
        p, out, _ = self.boot({"a.json": {}}, 30000, modules=CG)
        self.wait_for(lambda: self.has(out, "inst=a.json reaped"), timeout=10)
        self.assertEqual(self.results(out, "a.json"), [7])


class Startup(CgCase):

    def test_restart_in_same_scope(self):
        # 同一個 scope 裡 daemon 被 kill -9 再開：第二個 daemon 在 <根>/daemon 裡，照樣拿上一層當根；
        # 上次留在框裡的程序開起來時先清掉
        self.inst(sh("sleep 1000 & echo $! >> bg; sleep 1000"), "a.json")
        cfg = self.config({"interval_ms": 30000, "modules": CG, "insts": {"a.json": {}}})
        script = ('"$0" "$1" --config "$2" & d=$!; while [ ! -s bg ]; do sleep 0.05; done; kill -9 $d; '
                  'wait $d; echo \'{"argv":["true"]}\' > a.json; exec "$0" "$1" --config "$2"')
        p, out, _ = self.start(cfg, argv=["sh", "-c", script, PY, DAEMON, cfg])
        self.wait_for(lambda: self.results(out, "a.json") == [0], timeout=15)
        (pid,) = self.bg()
        self.assertFalse(alive(pid))
        self.assertEqual(procs(self.frame("a.json")), [])
        self.assertEqual(sorted(os.listdir(self.root)).count("daemon"), 1)
        self.assertFalse(os.path.exists(os.path.join(self.root, "daemon", "daemon")))


if __name__ == "__main__":
    unittest.main()
