"""kernel 測試：純函式規則（擺檔案→快照→run_rules）與 bin/aos7-kernel 整合（手寫 tock.json）。"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BASE, "lib"))

import aos7_fs as fs  # noqa: E402
import aos7_mount  # noqa: E402
from aos7_kernel_rules import run_rules, snapshot, task_state  # noqa: E402


class World:
    """在暫存資料夾擺出 root/.aosd 與各 node；活任務用自己起的 sleep 子程序。"""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="aos7k-")
        os.makedirs(os.path.join(self.root, ".aosd", "ctl"))
        self.procs = []

    def close(self):
        for p in self.procs:
            p.kill()
            p.wait()
        shutil.rmtree(self.root, ignore_errors=True)

    def node(self, nid, rnd=1):
        d = fs.node_path(self.root, nid)
        fs.write_json(os.path.join(d, ".aos", "timeline.json"), {"interval_ms": 100})
        self.set_round(nid, rnd)
        return d

    def set_round(self, nid, rnd):
        fs.write_json(os.path.join(fs.node_path(self.root, nid), ".aos", "round.json"),
                      {"round": rnd, "open": False})

    def task(self, nid, tid, name=None, rnd=1, state="live"):
        d = os.path.join(fs.node_path(self.root, nid), ".aos", "tasks", tid)
        fs.write_json(os.path.join(d, "birth.json"),
                      {"tid": tid, "name": name or tid.split("-r")[0], "node": nid, "round": rnd})
        if state == "live":
            p = subprocess.Popen(["sleep", "60"])
            self.procs.append(p)
            fs.write_json(os.path.join(d, "pid.json"), {"pid": p.pid, "pgid": p.pid})
        elif state == "ended":
            fs.write_json(os.path.join(d, "exit.json"), {"code": 0})
        return d

    def mount(self, tdir, decl):
        """照 tick 的做法替任務資料夾建掛載點、寫回 birth.json（S-23）。"""
        b = fs.read_json(os.path.join(tdir, "birth.json"))
        b["mounts"] = aos7_mount.make(self.root, tdir, decl)
        fs.write_json(os.path.join(tdir, "birth.json"), b)


KERNEL_MOUNTS = {"daemon": ".aosd", "amy": "team/agents/amy/.aos", "bob": "team/agents/bob/.aos"}


class RuleTest(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.w.node("team")
        self.w.node("team/agents/amy")
        self.w.node("team/agents/bob")
        self.cfg = {"members": ["agents/amy", "agents/bob"], "stuck_rounds": 2,
                    "budget_tokens": 100, "cool_rounds": 2, "max_age": {"subd": 3}}
        self.kdir = self.w.task("team", "kernel-r1", state="born")
        self.w.mount(self.kdir, KERNEL_MOUNTS)

    def tearDown(self):
        self.w.close()

    def step(self, state, rnd):
        snap = snapshot(self.w.root, "team", "kernel-r1", self.cfg, rnd, aos7_mount.resolver(self.kdir))
        return run_rules(self.cfg, state, snap)

    def test_task_state(self):
        self.assertEqual(task_state(self.w.task("team", "a-r1")), "live")
        self.assertEqual(task_state(self.w.task("team", "b-r1", state="ended")), "ended")
        self.assertEqual(task_state(self.w.task("team", "c-r1", state="born")), "live")
        d = self.w.task("team", "d-r1", state="born")
        fs.write_json(os.path.join(d, "pid.json"), {"pid": 2 ** 22 + 12345})
        self.assertEqual(task_state(d), "lost")

    def test_stuck_restart_counts_member_rounds(self):
        d = self.w.task("team/agents/amy", "agent-r1")
        fs.write_json(os.path.join(d, "progress.json"), {"steps": 5})
        st = {}
        ds, st = self.step(st, 1)                  # 第一次看到：當基準
        self.assertEqual(ds, [])
        ds, st = self.step(st, 2)                  # 成員回合沒前進：不算
        self.assertEqual(st["progress"]["team/agents/amy:agent-r1"]["same"], 0)
        self.w.set_round("team/agents/amy", 2)
        ds, st = self.step(st, 3)
        self.assertEqual(ds, [])
        self.w.set_round("team/agents/amy", 3)
        ds, st = self.step(st, 4)
        self.assertEqual([(x["rule"], x["target"], x["op"]) for x in ds],
                         [("stuck", "team/agents/amy:agent-r1", "restart")])
        ds, st = self.step(st, 5)                  # 已下過，不重下
        self.assertEqual(ds, [])

    def test_stuck_resets_on_change_and_ignores_no_progress(self):
        d = self.w.task("team/agents/amy", "agent-r1")
        self.w.task("team/agents/bob", "agent-r1")  # 沒 progress.json：不管
        st = {}
        for i in range(1, 6):
            fs.write_json(os.path.join(d, "progress.json"), {"steps": i})
            self.w.set_round("team/agents/amy", i)
            self.w.set_round("team/agents/bob", i)
            ds, st = self.step(st, i)
            self.assertEqual(ds, [])

    def test_budget_pause_then_resume(self):
        d = self.w.task("team/agents/bob", "agent-r1")
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 50, "calls": 1})
        st = {}
        ds, st = self.step(st, 1)                  # 基準 50
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 120, "calls": 2})
        ds, st = self.step(st, 2)                  # +70
        self.assertEqual(ds, [])
        ended = self.w.task("team/agents/bob", "old-r1", state="ended")
        fs.write_json(os.path.join(ended, "usage.json"), {"tokens": 40})
        ds, st = self.step(st, 3)                  # +40（結束的任務也算）→ 110 > 100
        self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "pause")])
        ds, st = self.step(st, 4)
        self.assertEqual(ds, [])
        ds, st = self.step(st, 5)                  # 過 cool_rounds=2
        self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "resume")])
        self.assertEqual(st["usage"]["team/agents/bob"]["acc"], 0)

    def test_budget_skips_own_node(self):
        self.cfg["members"] = ["."]
        d = self.w.task("team", "agent-r1")
        st = {}
        ds, st = self.step(st, 1)
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 999})
        ds, st = self.step(st, 2)
        self.assertEqual(ds, [])

    def test_age_kill(self):
        self.w.task("team", "subd-r2", rnd=2)
        self.w.task("team", "other-r1", rnd=1)
        st = {}
        ds, st = self.step(st, 5)                  # 5-2=3，不超過
        self.assertEqual(ds, [])
        ds, st = self.step(st, 6)
        self.assertEqual([(x["rule"], x["target"], x["op"]) for x in ds],
                         [("age", "team:subd-r2", "kill")])
        ds, st = self.step(st, 7)
        self.assertEqual(ds, [])

    def test_unmounted_member_is_invisible(self):
        """S-23：成員的 .aos 沒掛給 kernel，就看不到它、也不會對它下決定。"""
        self.w.mount(self.kdir, {})
        d = self.w.task("team/agents/amy", "agent-r1")
        fs.write_json(os.path.join(d, "progress.json"), {"steps": 5})
        snap = snapshot(self.w.root, "team", "kernel-r1", self.cfg, 1, aos7_mount.resolver(self.kdir))
        self.assertEqual((snap["members"]["team/agents/amy"]["exists"],
                          snap["members"]["team/agents/amy"]["mounted"]), (False, False))
        st = {}
        for r in range(1, 6):
            self.w.set_round("team/agents/amy", r)
            ds, st = self.step(st, r)
            self.assertEqual(ds, [])

    def test_existing_ctl_not_overridden(self):
        d = self.w.task("team", "subd-r1", rnd=1)
        fs.write_json(os.path.join(d, "ctl.json"), {"op": "restart", "by": "human"})
        ds, _ = self.step({}, 9)
        self.assertEqual(ds, [])


class IntegrationTest(unittest.TestCase):
    """起真的 bin/aos7-kernel，手寫 tock.json 驅動。"""

    def setUp(self):
        self.w = World()
        self.node = self.w.node("team")
        self.w.node("team/agents/amy")
        fs.write_json(os.path.join(self.node, "kernel.json"),
                      {"members": ["agents/amy"], "stuck_rounds": 1, "budget_tokens": 10,
                       "cool_rounds": 1, "max_age": {"subd": 1}})
        self.kdir = self.w.task("team", "kernel-r1", state="born")
        self.w.mount(self.kdir, KERNEL_MOUNTS)
        self.agent = self.w.task("team/agents/amy", "agent-r1")
        self.subd = self.w.task("team", "subd-r1", rnd=1)
        fs.write_json(os.path.join(self.agent, "progress.json"), {"steps": 1})
        fs.write_json(os.path.join(self.agent, "usage.json"), {"tokens": 0})
        env = fs.env_with_bin()
        env.update(AOS7_ROOT=self.w.root, AOS7_NODE=self.node, AOS7_NODE_ID="team",
                   AOS7_TASK=self.kdir, AOS7_TID="kernel-r1")
        self.p = subprocess.Popen([os.path.join(BASE, "bin", "aos7-kernel")], env=env, cwd=self.node,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def tearDown(self):
        if self.p.poll() is None:
            self.p.kill()
        self.p.wait()
        self.p.stdout.close()
        self.w.close()

    def tock(self, rnd):
        """寫 tock.json，等 kernel 把這回合寫進 kernel-state.json。"""
        fs.write_json(os.path.join(self.kdir, "tock.json"), {"round": rnd, "at": fs.now()})
        end = time.monotonic() + 5
        while time.monotonic() < end:
            st = fs.read_json(os.path.join(self.kdir, "kernel-state.json")) or {}
            if st.get("round") == rnd:
                return
            time.sleep(0.02)
        self.fail("kernel 沒處理第 %d 回合的 tock" % rnd)

    def test_kernel_process(self):
        self.tock(1)
        self.w.set_round("team/agents/amy", 2)
        fs.write_json(os.path.join(self.agent, "usage.json"), {"tokens": 50})
        self.tock(2)   # stuck(1 回合沒變)→restart；預算 +50→pause；subd 2-1=1 未超
        ctl = fs.read_json(os.path.join(self.agent, "ctl.json"))
        self.assertEqual((ctl["op"], ctl["by"]), ("restart", "team:kernel-r1"))
        dctl = [fs.read_json(os.path.join(self.w.root, ".aosd", "ctl", n))
                for n in sorted(os.listdir(os.path.join(self.w.root, ".aosd", "ctl")))]
        self.assertEqual([(c["op"], c["node"]) for c in dctl], [("pause", "team/agents/amy")])
        self.tock(3)   # resume；subd 3-1=2>1 → kill
        self.assertEqual(fs.read_json(os.path.join(self.subd, "ctl.json"))["op"], "kill")
        ops = [(d["rule"], d["op"]) for d in fs.read_jsonl(os.path.join(self.kdir, "decisions.jsonl"))]
        self.assertEqual(ops, [("stuck", "restart"), ("budget", "pause"),
                               ("budget", "resume"), ("age", "kill")])
        self.p.send_signal(signal.SIGTERM)
        self.assertEqual(self.p.wait(timeout=5), 0)

    def test_restart_inherits_state_and_rounds_flag(self):
        self.tock(1)
        self.p.send_signal(signal.SIGTERM)
        self.p.wait(timeout=5)
        # 模擬 restart：新任務資料夾 kernel-r2，birth 帶 restart_of
        k2 = os.path.join(self.node, ".aos", "tasks", "kernel-r2")
        fs.write_json(os.path.join(k2, "birth.json"),
                      {"tid": "kernel-r2", "name": "kernel", "node": "team", "round": 2,
                       "restart_of": "kernel-r1"})
        self.w.mount(k2, KERNEL_MOUNTS)   # restart 的新任務照原宣告重新掛
        fs.write_json(os.path.join(k2, "tock.json"), {"round": 2})
        env = fs.env_with_bin()
        env.update(AOS7_ROOT=self.w.root, AOS7_NODE=self.node, AOS7_NODE_ID="team",
                   AOS7_TASK=k2, AOS7_TID="kernel-r2")
        p = subprocess.Popen([os.path.join(BASE, "bin", "aos7-kernel"), "--rounds", "1"], env=env,
                             cwd=self.node, stdout=subprocess.PIPE, text=True)
        self.assertIn("> 1", p.stdout.readline())   # 接前一任：第 1 回合已處理過
        self.assertEqual(p.wait(timeout=5), 0)       # 啟動前就到的第 2 回合 tock 照樣處理，然後 --rounds 1 結束
        p.stdout.close()
        st = fs.read_json(os.path.join(k2, "kernel-state.json"))
        self.assertEqual(st["round"], 2)
        # 前一任記下的 amy progress 被接過來（基準不是重新起算）
        self.assertIn("team/agents/amy:agent-r1", st["progress"])


if __name__ == "__main__":
    unittest.main()
