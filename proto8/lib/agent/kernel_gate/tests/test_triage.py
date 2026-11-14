# 驗 kernel_gate/triage：直接餵事件看放行／拒／留與帳；再用真的 aos-post、aos-exec 與框架站跑 tick，看站照它轉寄、回拒信、留著並通知。
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

GATE = Path(__file__).resolve().parents[1]
PROTO8 = GATE.parents[2]
BINS = [PROTO8 / "impls" / name / "bin" for name in ("aos-post", "aos-exec", "aos-directive")]


class TriageTest(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get("KERNEL_TEST_TMP", "/tmp")
        self.root = Path(subprocess.check_output(
            ["mktemp", "-d", str(Path(scratch) / "kernel-triage-test.XXXXXX")], text=True).strip()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        r = self.root
        self.home, self.repo, self.code = r / "aos-home", r / "repo", r / "code"
        self.daemon = self.home / "ws" / ".stack"
        self.stack = self.daemon / "procs" / "boss"
        self.cell = self.stack / "hooks" / "kernel_gate"
        self.agents = self.home / "agents"
        for d in (self.cell, self.agents / "opus-kernel", self.home / "lib" / "x", self.repo / "wf" / "temp" / "ok-a" / "defs" / "sol",
                  self.code / "kf-1114" / "defs" / "w", self.code / "other" / "d", r / "tmp" / "evil"):
            d.mkdir(parents=True)
        self.rules = {
            "protect": ["eca_main", "boss", "llm-gpt", "_sweeper"],
            "names": ["ok-*", "xiaosi"],
            "defs": [str(self.agents / "opus-kernel")],
            "def_roots": [str(self.repo / "wf" / "temp" / "ok-*"), str(self.code / "*-1114")],
            "ws_roots": [str(self.repo / "wf" / "temp"), str(self.code / "*-1114")],
            "deny_roots": [str(self.home / "lib"), str(self.home / "py"), str(self.home / "knowledge")],
            "home_roots": [str(self.repo), str(self.home), str(self.code)],
            "daemon": str(self.daemon),
        }
        (self.cell / "triage.json").write_text(json.dumps(self.rules))
        table = {"procs": {
            "ok-a": {"phase": "running", "def": "../../agents/opus-kernel", "exec": "../../agents/opus-kernel",
                     "ws": "../../../repo/wf/temp/ok-a", "stack": "procs/ok-a"},
            "sol-1": {"phase": "running", "def": "../../../repo/wf/temp/ok-a/defs/sol", "exec": "../../../repo/wf/temp/ok-a/defs/sol",
                      "ws": "../../../repo/wf/temp/ok-a/sol", "stack": "procs/sol-1"},
            "stray": {"phase": "running", "def": "../../agents/opus-kernel", "ws": "../../../repo", "stack": "procs/stray"},
        }}
        (self.daemon / "procs_state.json").write_text(json.dumps(table))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PYTHONDONTWRITEBYTECODE="1", TEST_HOME=str(self.home),
                        PATH=os.pathsep.join([str(b) for b in BINS] + [os.environ["PATH"]]))

    def judge(self, body, decision=None, letter="L"):
        event = {"event": "after_verdict", "hook": "triage", "stack": str(self.cell), "letter": letter,
                 "sender": "/s", "body": body, "verdict": "pass", "error": None, "next": None, "decision": decision}
        p = subprocess.run([str(GATE / "triage")], input=json.dumps(event), text=True, capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        return out.get("verdict", "pass"), out

    def add(self, name, d, ws, **more):
        return {"procs_added": {name: dict({"exec": str(d), "def": str(d), "ws": str(ws)}, **more)}}

    def log(self):
        return [json.loads(x) for x in (self.cell / "triage.jsonl").read_text().splitlines()]

    def test_01_add_known_def_or_ok_area_passes(self):
        t = self.repo / "wf" / "temp"
        self.assertEqual(self.judge(self.add("ok-b", self.agents / "opus-kernel", t / "ok-b"))[0], "pass")
        self.assertEqual(self.judge(self.add("sol-2", t / "ok-a" / "defs" / "sol", t / "ok-a" / "sol"))[0], "pass")
        self.assertEqual(self.judge(self.add("w", self.code / "kf-1114" / "defs" / "w", self.code / "kf-1114" / "ws"))[0], "pass")
        # aos-agent 帶 envs 的寫法：exec 是 aos-exec 的命令列，目標是相對 AOS_DAEMON 的指示詞
        env_exec = {"argv": ["aos-exec", "--", {"$env": "TEST_HOME", "$path": "/agents/opus-kernel"}], "envs": {"A": "1"}}
        body = {"procs_added": {"ok-c": {"exec": env_exec, "def": str(self.agents / "opus-kernel"), "ws": str(t / "ok-c")}}}
        self.assertEqual(self.judge(body)[0], "pass")
        rows = self.log()
        self.assertEqual([r["verdict"] for r in rows], ["pass"] * 4)
        self.assertEqual(set(rows[0]), {"at", "letter", "from", "verdict", "why", "what"})
        self.assertEqual((rows[0]["letter"], rows[0]["from"], rows[0]["what"]), ("L", "/s", "added ok-b"))

    def test_02_add_refused(self):
        t = self.repo / "wf" / "temp"
        cases = [
            self.add("x", self.home / "lib" / "x", t / "x"),                         # def 在 aos-home/lib
            self.add("x", self.agents / "opus-kernel", self.home / "knowledge"),     # ws 在 knowledge
            self.add("x", self.root / "tmp" / "evil", t / "x"),                      # repo 外的怪地方
            self.add("x", self.agents / "opus-kernel", t / "x", as_written={"def": str(self.home / "py")}),
            self.add("eca_main", self.agents / "opus-kernel", t / "x"),              # 受保護的名字
            self.add("x", self.agents / "opus-kernel", t / "x", stack=str(self.root / "tmp" / "s")),
        ]
        for body in cases:
            verdict, out = self.judge(body)
            self.assertEqual(verdict, "refuse", body)
            self.assertEqual(out["error"]["code"], "GateRefused")
        self.assertIn("is inside", self.log()[0]["why"])
        self.assertIn("is outside", self.log()[2]["why"])
        self.assertIn("protected", self.log()[4]["why"])

    def test_03_add_held(self):
        t = self.repo / "wf" / "temp"
        cases = [
            self.add("x", self.home / "agents" / "other", t / "x"),                  # 不認得的定義
            self.add("x", self.agents / "opus-kernel", self.repo / "proto8"),        # ws 不在 temp
            self.add("x", self.code / "other" / "d", self.code / "other"),           # ~/code 但不是 -1114
            {"procs_added": {"x": {"exec": "rel/def", "ws": str(t / "x")}}},         # 相對路徑
            {"procs_added": {"x": {"exec": {"argv": ["sh", "-c", "x"]}, "ws": str(t / "x")}}},
            self.add("x", self.agents / "opus-kernel", t / "x", stack=str(self.daemon / "procs" / "ok-a")),
            {"procs_removed": ["ok-a"]},
            {"ping": True},
            "not an object",
        ]
        for body in cases:
            self.assertEqual(self.judge(body)[0], "hold", body)

    def test_04_stop_start_sleep_wake(self):
        self.assertEqual(self.judge({"procs_stopped": ["ok-a"]})[0], "pass")
        self.assertEqual(self.judge({"procs_woken": ["xiaosi", "ok-zz"]})[0], "pass")
        self.assertEqual(self.judge({"procs_slept": ["sol-1"]})[0], "pass")          # ok-a 的子 agent（表上的 def／ws 在 ok 區）
        self.assertEqual(self.judge({"procs_started": ["stray"]})[0], "hold")        # 表上有，但 ws 不在 temp
        self.assertEqual(self.judge({"procs_started": ["nobody"]})[0], "hold")
        verdict, out = self.judge({"procs_stopped": ["ok-a", "llm-gpt"]})
        self.assertEqual(verdict, "refuse")
        self.assertIn("llm-gpt is protected", out["error"]["msg"])
        self.assertEqual(self.judge({"procs_removed": ["_sweeper"]})[0], "refuse")
        self.assertEqual(self.judge({"procs_stopped": ["ok-a"], "procs_removed": ["ok-a"]})[0], "hold")

    def test_05_decided_pass_is_left_alone_and_no_rules_holds(self):
        p = subprocess.run([str(GATE / "triage")], text=True, capture_output=True, env=self.env, input=json.dumps(
            {"stack": str(self.cell), "letter": "L", "body": {"procs_removed": ["_sweeper"]}, "decision": "pass"}))
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        self.assertFalse((self.cell / "triage.jsonl").exists())
        (self.cell / "triage.json").unlink()
        self.assertEqual(self.judge({"procs_stopped": ["ok-a"]})[0], "hold")
        self.assertIn("triage.json unreadable", self.log()[0]["why"])

    def test_06_through_the_station(self):
        # 真站：kernel.json 只掛 triage；三封信各走放行、拒、留，留的那封通知 agent 的 queue。
        ctl, sender, queue = self.root / "ctl", self.root / "sender", self.stack / "queue"
        for box in (ctl, sender, queue, self.cell / "requests"):
            subprocess.run(["aos-post", "init", str(box)], check=True, env=self.env, capture_output=True)
        (self.cell / "kernel.json").write_text(json.dumps(
            {"next": str(ctl), "hooks": {"triage": {"event": "after_verdict", "condition": "pass", "handler": str(GATE / "triage")}}}))
        t = self.repo / "wf" / "temp"
        for name, body in (("a", self.add("ok-b", self.agents / "opus-kernel", t / "ok-b")),
                           ("b", self.add("x", self.home / "lib" / "x", t / "x")),
                           ("c", self.add("x", self.home / "agents" / "other", t / "x"))):
            subprocess.run(["aos-post", "send", "--reply-to", str(sender), str(self.cell / "requests"), name],
                           input=json.dumps(body), text=True, check=True, env=self.env, capture_output=True)
        event = {"event": "on_clock", "hook": "kernel_gate", "stack": str(self.stack), "first": False}
        p = subprocess.run([str(GATE / "tick")], input=json.dumps(event), text=True, capture_output=True,
                           env=dict(self.env, AOS_STACK=str(self.cell)))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(x.name for x in (ctl / "new").iterdir()), ["a"])
        answer = json.loads(next((sender / "new").iterdir()).joinpath("letter.json").read_text())
        self.assertEqual((answer["in_reply_to"], answer["body"]["error"]["code"]), ("b", "GateRefused"))
        held = json.loads((self.cell / "hold.json").read_text())["held"]
        self.assertEqual([h["letter"] for h in held], ["c"])
        notice = json.loads(next((queue / "new").iterdir()).joinpath("letter.json").read_text())["body"]["content"]
        self.assertIn("- letter c", notice)
        self.assertEqual([r["verdict"] for r in self.log()], ["pass", "refuse", "hold"])
        # agent 表態 pass：站重判、triage 不再說話（帳不多一行），信轉出去
        (self.cell / "decisions").mkdir(exist_ok=True)
        (self.cell / "decisions" / "c.json").write_text('{"verdict": "pass"}')
        p = subprocess.run([str(GATE / "tick")], input=json.dumps(event), text=True, capture_output=True,
                           env=dict(self.env, AOS_STACK=str(self.cell)))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(x.name for x in (ctl / "new").iterdir()), ["a", "c"])
        self.assertEqual(len(self.log()), 3)


if __name__ == "__main__":
    unittest.main()
