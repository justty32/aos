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
sys.path.insert(0, HERE)

import _proc  # noqa: E402
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
        """先收程序、再刪空間（N-55）。"""
        for p in self.procs:
            _proc.reap(p)
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
            p = _proc.track(None, subprocess.Popen(["sleep", "60"]))
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
        self.addCleanup(self.w.close)
        self.w.node("team")
        self.w.node("team/agents/amy")
        self.w.node("team/agents/bob")
        self.cfg = {"members": ["agents/amy", "agents/bob"], "stuck_rounds": 2,
                    "budget_tokens": 100, "cool_rounds": 2, "max_age": {"subd": 3}}
        self.kdir = self.w.task("team", "kernel-r1", state="born")
        self.w.mount(self.kdir, KERNEL_MOUNTS)

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

    def test_removed_member_still_resumed(self):
        """astra-2 二-7：kernel 自己 pause 的，對方被移出 members 也照樣到期 resume。"""
        d = self.w.task("team/agents/bob", "agent-r1")
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 0})
        ds, st = self.step({}, 1)
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 500})
        ds, st = self.step(st, 2)
        self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "pause")])
        self.cfg["members"] = ["agents/amy"]
        ds, st = self.step(st, 3)
        self.assertEqual(ds, [])
        ds, st = self.step(st, 4)
        self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "resume")])
        self.assertEqual(st["paused"], {})

    def test_removed_member_resume_clears_acc(self):
        """astra-3 三-1：移出成員到期 resume 後累計也歸零；用量不變時加回，不會被同一筆用量再 pause。"""
        d = self.w.task("team/agents/bob", "agent-r1")
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 0})
        ds, st = self.step({}, 1)
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 500})
        rnd = 2
        for _ in range(2):  # 移出、到期、加回，做兩次
            ds, st = self.step(st, rnd)
            self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "pause")])
            self.cfg["members"] = ["agents/amy"]
            ds, st = self.step(st, rnd + 1)
            ds, st = self.step(st, rnd + 2)
            self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/bob", "resume")])
            self.assertEqual(st["usage"]["team/agents/bob"]["acc"], 0)
            self.cfg["members"] = ["agents/amy", "agents/bob"]
            ds, st = self.step(st, rnd + 3)
            self.assertEqual(ds, [])
            fs.write_json(os.path.join(d, "usage.json"), {"tokens": 500 + 200 * (rnd // 4 + 1)})
            rnd += 4

    def test_broken_member_mount_does_not_kill_kernel(self):
        """astra-3 三-2：成員搬走、掛載斷了，寫名冊／寫成員 ctl 失敗只記一行、跳過那個成員，kernel 這輪照樣做完。"""
        import aos7_kernel
        node = fs.node_path(self.w.root, "team")
        env = {"node_id": "team", "node": node, "tid": "kernel-r1", "task": self.kdir, "root": self.w.root}
        fs.write_json(os.path.join(node, "kernel.json"), self.cfg)
        bob = self.w.task("team/agents/bob", "agent-r1")
        fs.write_json(os.path.join(bob, "progress.json"), {"steps": 1})
        aos7_kernel.one_round(env, 1)
        os.rename(os.path.join(self.w.root, "team/agents/amy"), os.path.join(self.w.root, "team/agents/moved-amy"))
        os.remove(os.path.join(self.w.root, "team/agents/bob/.aos/roster.json"))
        self.cfg["roles"] = {"agents/amy": "改了"}  # 名冊變了，要重寫
        fs.write_json(os.path.join(node, "kernel.json"), self.cfg)
        for r in range(2, 6):
            self.w.set_round("team/agents/bob", r)
            aos7_kernel.one_round(env, r)  # 不丟例外
        recs = fs.read_jsonl(os.path.join(self.kdir, "decisions.jsonl"))
        bad = [x for x in recs if x["rule"] == "roster"]
        self.assertTrue(bad and all(x["target"] == "team/agents/amy" and "skipped" in x for x in bad))
        self.assertEqual(fs.read_json(os.path.join(self.w.root, "team/agents/bob/.aos/roster.json"))["members"][0]["role"], "改了")
        self.assertIn(("stuck", "team/agents/bob:agent-r1"), [(x["rule"], x["target"]) for x in recs])
        self.assertEqual(fs.read_json(os.path.join(self.kdir, "kernel-state.json"))["round"], 5)
        # 寫成員 ctl 失敗也一樣：記 skipped，不丟例外
        from unittest import mock
        real = fs.write_json
        def flaky(path, obj):
            if path.endswith("ctl.json"):
                raise FileExistsError(17, "File exists", path)
            return real(path, obj)
        bob2 = self.w.task("team/agents/bob", "agent-r6")
        fs.write_json(os.path.join(bob2, "progress.json"), {"steps": 1})
        with mock.patch.object(fs, "write_json", flaky):
            for r in range(6, 10):
                self.w.set_round("team/agents/bob", r)
                aos7_kernel.one_round(env, r)
        recs = fs.read_jsonl(os.path.join(self.kdir, "decisions.jsonl"))
        self.assertTrue(any(x["target"] == "team/agents/bob:agent-r6" and "寫不進去" in x.get("skipped", "") for x in recs))

    def test_llm_wait_is_not_stuck(self):
        """R-3：progress 寫著 llm_since（在等 LLM）不算卡住；另設 llm_stuck_rounds 才管。"""
        d = self.w.task("team/agents/amy", "agent-r1")
        fs.write_json(os.path.join(d, "progress.json"), {"steps": 5, "state": "think", "llm_since": "t0"})
        st = {}
        for i in range(1, 8):
            self.w.set_round("team/agents/amy", i)
            ds, st = self.step(st, i)
            self.assertEqual(ds, [])
        self.cfg["llm_stuck_rounds"] = 10
        got = []
        for i in range(8, 13):
            self.w.set_round("team/agents/amy", i)
            ds, st = self.step(st, i)
            got += ds
        ds = got
        self.assertEqual([(x["target"], x["op"]) for x in ds], [("team/agents/amy:agent-r1", "restart")])
        self.assertIn("等 LLM", ds[0]["why"])

    def test_cap_pause_waits_for_config_change(self):
        """R-4：用量總和超過 cap_tokens → pause，冷卻不會 resume；人調高 cap_tokens 後才 resume。"""
        self.cfg.update(budget_tokens=10 ** 9, cap_tokens=300)
        d = self.w.task("team/agents/bob", "agent-r1")
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 100})
        ds, st = self.step({}, 1)
        self.assertEqual(ds, [])
        fs.write_json(os.path.join(d, "usage.json"), {"tokens": 400})
        ds, st = self.step(st, 2)
        self.assertEqual([(x["rule"], x["target"], x["op"]) for x in ds], [("cap", "team/agents/bob", "pause")])
        self.assertIn("要人改", ds[0]["why"])
        for i in range(3, 10):
            ds, st = self.step(st, i)
            self.assertEqual(ds, [])
        self.cfg["cap_tokens"] = 1000
        ds, st = self.step(st, 10)
        self.assertEqual([(x["rule"], x["op"]) for x in ds], [("cap", "resume")])

    def test_roster_written_to_members(self):
        """R-2 (b)：kernel 把成員名冊寫進每個成員的 .aos/roster.json（經過掛載點），沒變就不重寫。"""
        import aos7_kernel
        self.cfg["roles"] = {"agents/amy": "寫程式"}
        env = {"node_id": "team", "node": fs.node_path(self.w.root, "team"), "tid": "kernel-r1"}
        aos7_kernel.write_rosters(env, self.cfg, aos7_mount.resolver(self.kdir))
        for who in ("amy", "bob"):
            r = fs.read_json(os.path.join(self.w.root, "team/agents", who, ".aos", "roster.json"))
            self.assertEqual(r["members"], [
                {"node": "team/agents/amy", "inbox": "team/agents/amy/inbox", "role": "寫程式"},
                {"node": "team/agents/bob", "inbox": "team/agents/bob/inbox", "role": ""}])
        p = os.path.join(self.w.root, "team/agents/amy/.aos/roster.json")
        m = os.stat(p).st_mtime_ns
        time.sleep(0.01)
        aos7_kernel.write_rosters(env, self.cfg, aos7_mount.resolver(self.kdir))
        self.assertEqual(os.stat(p).st_mtime_ns, m)

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
        self.addCleanup(self.w.close)   # 最後跑：下面 track 的 kernel 程序先收（N-55）
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
        self.p = _proc.track(self, subprocess.Popen([os.path.join(BASE, "bin", "aos7-kernel")], env=env, cwd=self.node,
                                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))

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

    def test_kernel_asks_mounts_for_new_member(self):
        """M-6：kernel.json 加成員，kernel 自己寫加掛請求；tick 給了之後就看得到。"""
        self.w.node("team/agents/carol")
        d = self.w.task("team/agents/carol", "agent-r1")
        fs.write_json(os.path.join(d, "progress.json"), {"steps": 1})
        cfg = fs.read_json(os.path.join(self.node, "kernel.json"))
        cfg["members"].append("agents/carol")
        fs.write_json(os.path.join(self.node, "kernel.json"), cfg)
        self.tock(1)
        self.assertTrue(os.path.exists(os.path.join(self.kdir, "mount-req", aos7_mount.req_name("team/agents/carol/.aos") + ".json")))
        res = aos7_mount.serve(self.w.root, self.kdir, None)
        self.assertEqual([(r["path"], r["ok"]) for r in res], [("team/agents/carol/.aos", True)])
        snap = snapshot(self.w.root, "team", "kernel-r1", cfg, 2, aos7_mount.resolver(self.kdir))
        self.assertEqual(snap["members"]["team/agents/carol"]["tasks"][0]["tid"], "agent-r1")

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
        p = _proc.track(self, subprocess.Popen([os.path.join(BASE, "bin", "aos7-kernel"), "--rounds", "1"], env=env,
                                               cwd=self.node, stdout=subprocess.PIPE, text=True))
        self.assertIn("> 1", p.stdout.readline())   # 接前一任：第 1 回合已處理過
        self.assertEqual(p.wait(timeout=5), 0)       # 啟動前就到的第 2 回合 tock 照樣處理，然後 --rounds 1 結束
        p.stdout.close()
        st = fs.read_json(os.path.join(k2, "kernel-state.json"))
        self.assertEqual(st["round"], 2)
        # 前一任記下的 amy progress 被接過來（基準不是重新起算）
        self.assertIn("team/agents/amy:agent-r1", st["progress"])


if __name__ == "__main__":
    unittest.main()
