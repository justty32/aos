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

    def test_write_cannot_escape_node(self):
        from aos7_agent_tools import do_tool
        r = do_tool(self.w["amy"], {"tool": "write", "path": "../bob/x.txt", "text": "x"}, 1)
        self.assertIn("失敗", r)
        r = do_tool(self.w["amy"], {"tool": "send", "to": "../../etc", "body": "x"}, 1)
        self.assertIn("失敗", r)

    def test_send_only_through_mount(self):
        """S-23：沒掛給我的收信資料夾寄不到（amy 只掛了 bob 的 inbox）。"""
        from aos7_agent_tools import do_tool
        os.makedirs(os.path.join(self.tmp, "team", "agents", "carol", "inbox"))
        r = do_tool(self.w["amy"], {"tool": "send", "to": "team/agents/carol", "body": "x"}, 1)
        self.assertIn("沒掛載", r)
        self.assertEqual(os.listdir(os.path.join(self.tmp, "team", "agents", "carol", "inbox")), [])
        r = do_tool(self.w["amy"], {"tool": "send", "to": "team/agents/bob", "body": "x"}, 1)
        self.assertIn("send →", r)
        self.assertEqual(len(os.listdir(os.path.join(self.w["bob"]["node"], "inbox"))), 1)


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
