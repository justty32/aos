"""aos7-agent 與 aos7_llm 的測試：純標準庫、離線、不跑 daemon（手動寫 tock.json 推時間）。"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import shutil
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BASE, "lib"))

import aos7_agent  # noqa: E402
import aos7_llm  # noqa: E402
import aos7_mount  # noqa: E402
from aos7_fs import read_json, write_json  # noqa: E402

AGENT = os.path.join(BASE, "bin", "aos7-agent")


def make_world(tmp, max_ping=6):
    """root 底下兩個 node（amy 先開口）＋各一個任務資料夾；回 {名字: ctx}。"""
    ctxs = {}
    for name in ("amy", "bob"):
        nid = "team/agents/" + name
        node = os.path.join(tmp, nid)
        os.makedirs(os.path.join(node, "inbox"), exist_ok=True)
        write_json(os.path.join(node, ".aos", "timeline.json"), {"interval_ms": 100})
        write_json(os.path.join(node, "agent.json"),
                   {"name": name, "persona": "測試用 %s" % name, "llm": "fake", "max_ping": max_ping})
        tid = "agent-r1"
        task = os.path.join(node, ".aos", "tasks", tid)
        other = "bob" if name == "amy" else "amy"
        write_json(os.path.join(task, "birth.json"),
                   {"tid": tid, "name": "agent", "node": nid, "round": 1,
                    "mounts": aos7_mount.make(tmp, task, {other: "team/agents/%s/inbox" % other})})
        ctxs[name] = {"root": tmp, "node": node, "node_id": nid, "task": task, "tid": tid}
    write_json(os.path.join(ctxs["amy"]["node"], "goal.json"),
               {"say_first": {"to": "team/agents/bob", "body": "ping 1"}})
    return ctxs


def env_of(ctx):
    env = dict(os.environ)
    env.update(AOS7_ROOT=ctx["root"], AOS7_NODE=ctx["node"], AOS7_NODE_ID=ctx["node_id"],
               AOS7_TASK=ctx["task"], AOS7_TID=ctx["tid"])
    return env


class FakeLLM(unittest.TestCase):
    def test_say_first_and_ping(self):
        cfg = {"llm": "fake", "max_ping": 6}
        r = aos7_llm.think(cfg, {"say_first": {"to": "x", "body": "ping 1"}}, [], "me")
        self.assertEqual(r["plan"], [{"tool": "send", "to": "x", "body": "ping 1"}])
        self.assertGreater(r["tokens"], 0)
        r = aos7_llm.think(cfg, None, [{"from": "a/b", "body": "ping 3"}], "me")
        self.assertEqual(r["plan"], [{"tool": "send", "to": "a/b", "body": "ping 4"}])
        r = aos7_llm.think(cfg, None, [{"from": "a/b", "body": "ping 6"}], "me")
        self.assertEqual(r["plan"][0]["tool"], "write")
        self.assertEqual(aos7_llm.think(cfg, None, [{"from": "a", "body": "hi"}], "me")["plan"], [{"tool": "none"}])

    def test_parse_plan(self):
        p = aos7_llm.parse_plan
        self.assertEqual(p('```json\n[{"tool": "none"}]\n```'), [{"tool": "none"}])
        self.assertEqual(p('<think>嗯 [x]</think>好的：{"tool": "none"}'), [{"tool": "none"}])
        self.assertIsNone(p("我不知道"))

    def test_unreachable_endpoint_falls_back(self):
        r = aos7_llm.think({"llm": {"url": "http://127.0.0.1:9/v1", "model": "m", "timeout_s": 2}}, None, [], "me")
        self.assertEqual(r["plan"], [{"tool": "none"}])
        self.assertIn("呼叫失敗", r["note"])


class StepByStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.w = make_world(self.tmp, max_ping=2)
        patcher = mock.patch("aos7_agent.log")  # 單步測不要把 stdout 洗版
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_three_tocks_per_letter(self):
        amy, bob = self.w["amy"], self.w["bob"]
        sa, sb = aos7_agent.load_state(amy), aos7_agent.load_state(bob)
        sa = aos7_agent.on_tock(amy, sa, 1)
        self.assertEqual(sa["state"], "think")
        self.assertEqual(sa["plan"][0]["body"], "ping 1")
        sb = aos7_agent.on_tock(bob, sb, 1)
        self.assertEqual(sb["state"], "idle")
        sa = aos7_agent.on_tock(amy, sa, 2)
        self.assertEqual(sa["state"], "act")
        self.assertTrue(os.path.exists(os.path.join(amy["node"], "goal.done.json")))
        self.assertEqual(len(os.listdir(os.path.join(bob["node"], "inbox"))), 1)
        sa = aos7_agent.on_tock(amy, sa, 3)
        self.assertEqual(sa["state"], "idle")
        for r in (3, 4, 5):
            sb = aos7_agent.on_tock(bob, sb, r)
        self.assertEqual(sb["state"], "idle")
        self.assertEqual(len(os.listdir(os.path.join(bob["node"], "inbox", "done"))), 1)
        for r in (6, 7, 8):  # amy 收到 ping 2＝上限 → write
            sa = aos7_agent.on_tock(amy, sa, r)
        with open(os.path.join(amy["node"], "work", "done.txt"), encoding="utf-8") as f:
            self.assertIn("ping 2", f.read())
        self.assertEqual(read_json(os.path.join(amy["task"], "usage.json"))["calls"], 2)
        self.assertEqual(read_json(os.path.join(amy["task"], "progress.json"))["round"], 8)

    def test_restart_mid_think_and_mid_act(self):
        amy = self.w["amy"]
        st = aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        st["plan"] = None  # 假裝 LLM 呼叫到一半被 kill
        aos7_agent.save(amy, st)
        new = dict(amy, tid="agent-r5", task=os.path.join(os.path.dirname(amy["task"]), "agent-r5"))
        write_json(os.path.join(new["task"], "birth.json"),
                   {"tid": "agent-r5", "name": "agent", "restart_of": "agent-r1",
                    "mounts": aos7_mount.make(self.tmp, new["task"], {"bob": "team/agents/bob/inbox"})})
        st2 = aos7_agent.recover(new, aos7_agent.load_state(new))
        self.assertEqual(st2["from"], "agent-r1")
        self.assertEqual(st2["plan"][0]["tool"], "send")
        st2["state"], st2["pc"] = "act", 0
        aos7_agent.recover(new, st2)  # act 補做一次
        self.assertEqual(len(os.listdir(os.path.join(self.w["bob"]["node"], "inbox"))), 1)

    def test_wake_after_idle_rounds_unless_done(self):
        """agent.json 的 wake：閒了 N 回合沒信就自己想一次；unless 的檔在就不醒；goal.json 不被當成用掉。"""
        bob = self.w["bob"]
        cfg = read_json(os.path.join(bob["node"], "agent.json"))
        cfg["wake"] = {"rounds": 3, "unless": "work/DONE.md"}
        write_json(os.path.join(bob["node"], "agent.json"), cfg)
        st = aos7_agent.load_state(bob)
        for r in (1, 2):
            st = aos7_agent.on_tock(bob, st, r)
            self.assertEqual(st["state"], "idle")
        st = aos7_agent.on_tock(bob, st, 3)
        self.assertEqual(st["state"], "think")
        self.assertIn("wake", st["goal"])
        st = aos7_agent.on_tock(bob, aos7_agent.on_tock(bob, st, 4), 5)
        self.assertEqual(st["state"], "idle")
        os.makedirs(os.path.join(bob["node"], "work"), exist_ok=True)
        write_json(os.path.join(bob["node"], "work", "DONE.md"), {})
        for r in range(6, 12):
            st = aos7_agent.on_tock(bob, st, r)
            self.assertEqual(st["state"], "idle")

    def test_memory_has_history_and_files(self):
        from aos7_agent_tools import do_tool, memory
        amy = self.w["amy"]
        do_tool(amy, {"tool": "send", "to": "team/agents/bob", "body": "hi"}, 1)
        do_tool(amy, {"tool": "write", "path": "work/a.py", "text": "x = 1"}, 1)
        m = memory(amy["node"], 5)
        self.assertEqual(m["recent_letters"][-1]["body"], "hi")
        self.assertEqual(m["my_files"], {"work/a.py": "x = 1"})

    def test_memory_keeps_each_peer(self):
        """R-13：跟 ci 互丟很多封時，視窗外的 rita 仍留最近一封（不被擠掉）。"""
        from aos7_agent_tools import memory
        node = self.w["amy"]["node"]
        write_json(os.path.join(node, "inbox", "done", "1.json"), {"from": "t/rita", "at": "2026-01-01T00:00:01", "body": "我是 rita"})
        write_json(os.path.join(node, "inbox", "done", "2.json"), {"from": "t/rita", "at": "2026-01-01T00:00:02", "body": "OK"})
        for i in range(10):
            write_json(os.path.join(node, "inbox", "done", "c%02d.json" % i),
                       {"from": "t/ci", "at": "2026-01-01T00:01:%02d" % i, "body": "PASS %d" % i})
        m = memory(node, 3)["recent_letters"]
        self.assertEqual([h["body"] for h in m], ["OK", "PASS 7", "PASS 8", "PASS 9"])

    def test_memory_reads_only_tail(self):
        """astra-3 三-3：memory 只讀尾端（sent.jsonl 從檔尾往回讀、inbox/done 依檔名取最後幾封），不讀全歷史。"""
        import aos7_agent_tools
        from aos7_fs import tail_jsonl
        node = self.w["amy"]["node"]
        path = os.path.join(node, "sent.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{壞行\n")
            for i in range(3000):
                f.write(json.dumps({"to": "t/bob", "at": "2026-01-01T%05d" % i, "body": "x" * (i % 50)}) + "\n")
        self.assertEqual([x["at"][-5:] for x in tail_jsonl(path, 3, block=64)], ["02997", "02998", "02999"])
        self.assertEqual(len(tail_jsonl(path, 5000, block=64)), 3000)
        self.assertEqual(tail_jsonl(path, 0), [])
        for i in range(300):
            write_json(os.path.join(node, "inbox", "done", "%019d-t_ci.json" % i),
                       {"from": "t/ci", "at": "2026-01-01T%05d" % (i * 10 + 5), "body": "r%d" % i})
        reads = []
        real_read = aos7_agent_tools.read_json
        with mock.patch.object(aos7_agent_tools, "read_json", lambda p, *a: reads.append(p) or real_read(p, *a)):
            m = aos7_agent_tools.memory(node, 2)["recent_letters"]
        self.assertEqual([h["at"][-5:] for h in m], ["02995", "02998", "02999"])  # 最近 2 封＋ci 補一封
        self.assertEqual(len(reads), aos7_agent_tools.LOOKBACK)  # 300 封只讀最後 LOOKBACK 封

    def test_save_letter_verbatim(self):
        """R-15 (b)：save 不經 LLM，把收到的信（code: true 取第一段 ``` 程式碼）原樣存成檔；信帶 file 給 prompt。"""
        from aos7_agent_tools import do_tool, read_letters
        amy = self.w["amy"]
        code = "def f(x):\n    return x  # 原樣\n"
        body = "dur.py PASS 36/36（第 2 次測試），寄件者 t/coder。通過的完整原始碼：\n```python\n%s\n```\n" % code
        write_json(os.path.join(amy["node"], "inbox", "123-t_ci.json"), {"from": "t/ci", "body": body})
        self.assertEqual(read_letters(amy["node"], ["123-t_ci.json"])[0]["file"], "123-t_ci.json")
        sys_, user = aos7_llm.build_prompt({}, None, read_letters(amy["node"], ["123-t_ci.json"]), "x")
        self.assertIn('"save"', sys_)
        self.assertEqual(json.loads(user)["letters"][0]["file"], "123-t_ci.json")
        r = do_tool(amy, {"tool": "save", "letter": "123-t_ci.json", "path": "work/dur.py", "code": True}, 1)
        self.assertTrue(r.startswith("save"), r)
        with open(os.path.join(amy["node"], "work", "dur.py"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), code.strip())
        # 搬到 done/ 之後照樣找得到；不帶 code 存整封
        from aos7_agent_tools import move_done
        move_done(amy["node"], ["123-t_ci.json"])
        do_tool(amy, {"tool": "save", "letter": "123-t_ci.json", "path": "work/all.txt"}, 1)
        with open(os.path.join(amy["node"], "work", "all.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), body)
        for bad in ({"letter": "../x.json", "path": "a"}, {"letter": "nope.json", "path": "a"},
                    {"letter": "123-t_ci.json", "path": "../../x"}, {"letter": "123-t_ci.json"}):
            self.assertIn("失敗", do_tool(amy, dict(bad, tool="save"), 1))

    def test_write_cannot_escape_node(self):
        from aos7_agent_tools import do_tool
        r = do_tool(self.w["amy"], {"tool": "write", "path": "../bob/x.txt", "text": "x"}, 1)
        self.assertIn("失敗", r)
        r = do_tool(self.w["amy"], {"tool": "send", "to": "../../etc", "body": "x"}, 1)
        self.assertIn("失敗", r)

    def test_send_unmounted_goes_to_outbox_then_mount(self):
        """S-23、M-6：沒掛的對象，信先放 outbox、寫加掛請求；tick 給了之後，下個 tock 寄出。"""
        from aos7_agent_tools import do_tool
        amy = self.w["amy"]
        carol_in = os.path.join(self.tmp, "team", "agents", "carol", "inbox")
        os.makedirs(carol_in)
        r = do_tool(amy, {"tool": "send", "to": "team/agents/carol", "body": "hi"}, 1)
        self.assertIn("outbox", r)
        self.assertEqual(os.listdir(carol_in), [])
        self.assertEqual(len(os.listdir(os.path.join(amy["node"], "outbox"))), 1)
        req = read_json(os.path.join(amy["task"], "mount-req", "team_agents_carol_inbox.json"))
        self.assertEqual(req["path"], "team/agents/carol/inbox")
        st = aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)   # 還沒掛：信留著
        self.assertEqual(len([n for n in os.listdir(os.path.join(amy["node"], "outbox")) if n.endswith(".json")]), 1)
        res = aos7_mount.serve(self.tmp, amy["task"], ["team/agents/"])            # 下一個 tick 審核
        self.assertTrue(res[0]["ok"], res)
        aos7_agent.on_tock(amy, st, 2)
        self.assertEqual(read_json(os.path.join(carol_in, os.listdir(carol_in)[0]))["body"], "hi")
        self.assertFalse([n for n in os.listdir(os.path.join(amy["node"], "outbox")) if n.endswith(".json")])
        r = do_tool(amy, {"tool": "send", "to": "team/agents/carol", "body": "again"}, 3)   # 掛上後直接寄
        self.assertIn("send →", r)
        self.assertEqual(len(os.listdir(carol_in)), 2)

    def test_send_to_deleted_inbox_fails_softly(self):
        """astra-2 二-5：已掛的收件夾被刪掉或搬走，send 失敗、信放 outbox/failed/ 記原因，agent 不死。"""
        from aos7_agent_tools import do_tool
        amy = self.w["amy"]
        shutil.rmtree(os.path.join(self.w["bob"]["node"], "inbox"))
        r = do_tool(amy, {"tool": "send", "to": "team/agents/bob", "body": "x"}, 1)
        self.assertIn("失敗", r)
        failed = os.path.join(amy["node"], "outbox", "failed")
        self.assertIn("不在了", read_json(os.path.join(failed, os.listdir(failed)[0]))["failed"]["why"])
        # 整條路（goal 先開口 → think → act）也不丟例外
        os.rename(self.w["bob"]["node"], os.path.join(self.tmp, "moved"))
        st = aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        st = aos7_agent.on_tock(amy, st, 2)
        self.assertEqual(st["state"], "act")
        self.assertIn("失敗", st["last"])
        self.assertEqual(len(os.listdir(failed)), 2)

    def test_tool_exception_does_not_kill_agent(self):
        amy = self.w["amy"]
        st = aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        with mock.patch("aos7_agent_tools.do_tool", side_effect=RuntimeError("boom")):
            st = aos7_agent.on_tock(amy, st, 2)
        self.assertIn("工具失敗", st["last"])

    def test_progress_says_waiting_llm(self):
        """R-3：think 一開始就在 progress.json 寫 llm_since；想完後的 progress 沒有它。"""
        amy = self.w["amy"]
        seen = {}
        real = aos7_llm.think

        def spy(*a, **k):
            seen.update(read_json(os.path.join(amy["task"], "progress.json")))
            return real(*a, **k)
        with mock.patch("aos7_llm.think", side_effect=spy):
            aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        self.assertEqual(seen["state"], "think")
        self.assertTrue(seen["llm_since"])
        self.assertNotIn("llm_since", read_json(os.path.join(amy["task"], "progress.json")))

    def test_roster_goes_into_prompt(self):
        """R-2 (b)：node 的 .aos/roster.json（kernel 寫的成員名冊）每次 think 都放進 prompt。"""
        amy = self.w["amy"]
        ros = {"by": "team", "members": [{"node": "team/agents/bob", "inbox": "team/agents/bob/inbox", "role": "審稿"}]}
        write_json(os.path.join(amy["node"], ".aos", "roster.json"), ros)
        got = {}
        real = aos7_llm.build_prompt

        def spy(*a, **k):
            s, u = real(*a, **k)
            got["user"] = json.loads(u)
            return s, u
        with mock.patch("aos7_llm.build_prompt", side_effect=spy):
            aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        self.assertEqual(got["user"]["roster"], ros)

    def test_refused_mount_moves_letter_to_failed(self):
        from aos7_agent_tools import do_tool
        amy = self.w["amy"]
        os.makedirs(os.path.join(self.tmp, "other", "inbox"))
        do_tool(amy, {"tool": "send", "to": "other", "body": "x"}, 1)
        res = aos7_mount.serve(self.tmp, amy["task"], ["team/agents/"])
        self.assertFalse(res[0]["ok"])
        aos7_agent.on_tock(amy, aos7_agent.load_state(amy), 1)
        self.assertEqual(len(os.listdir(os.path.join(amy["node"], "outbox", "failed"))), 1)
        r = do_tool(amy, {"tool": "send", "to": "other", "body": "y"}, 2)   # 被拒過：直接失敗
        self.assertIn("被拒", r)
        self.assertEqual(os.listdir(os.path.join(self.tmp, "other", "inbox")), [])

class TwoProcesses(unittest.TestCase):
    def test_ping_pong_to_limit(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        w = make_world(tmp, max_ping=6)
        procs = {n: subprocess.Popen([sys.executable, AGENT], env=env_of(c), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT) for n, c in w.items()}
        try:
            for r in range(1, 31):
                for c in w.values():
                    write_json(os.path.join(c["task"], "tock.json"), {"round": r, "at": "test"})
                end = time.monotonic() + 5
                while any((read_json(os.path.join(c["task"], "state.json"), {}) or {}).get("round") != r
                          for c in w.values()):
                    self.assertLess(time.monotonic(), end, "第 %d 回合等不到 agent 跟上" % r)
                    time.sleep(0.01)
                if os.path.exists(os.path.join(w["amy"]["node"], "work", "done.txt")):
                    break
            self.rounds_used = r  # ping 1～6 共 6 封信＋最後 write，實測 11 回合：寄件者 act 那回合送出，收件者下個 tock 才進 think、再下個 tock 才 act 回信
            self.assertTrue(os.path.exists(os.path.join(w["amy"]["node"], "work", "done.txt")))
            bodies = []
            for c in w.values():
                done = os.path.join(c["node"], "inbox", "done")
                bodies += [read_json(os.path.join(done, n))["body"] for n in os.listdir(done)]
            self.assertEqual(sorted(bodies), ["ping %d" % i for i in range(1, 7)])
            for c in w.values():
                st = read_json(os.path.join(c["task"], "state.json"))
                self.assertIn(st["state"], ("idle", "think", "act"))
                self.assertGreaterEqual(read_json(os.path.join(c["task"], "usage.json"))["calls"], 3)
                self.assertEqual(read_json(os.path.join(c["task"], "progress.json"))["round"], st["round"])
        finally:
            for p in procs.values():
                p.send_signal(signal.SIGTERM)
            for n, p in procs.items():
                out, _ = p.communicate(timeout=5)
                self.assertEqual(p.returncode, 0, out.decode("utf-8", "replace"))
                self.assertIn("SIGTERM", out.decode("utf-8"))


class RoundsFlag(unittest.TestCase):
    def test_rounds_n_exits(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        c = make_world(tmp)["bob"]
        p = subprocess.Popen([sys.executable, AGENT, "--rounds", "2"], env=env_of(c), stdout=subprocess.PIPE)
        for r in (1, 2):
            write_json(os.path.join(c["task"], "tock.json"), {"round": r})
            time.sleep(0.15)
        out, _ = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0)
        self.assertIn("處理完 2 次", out.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
