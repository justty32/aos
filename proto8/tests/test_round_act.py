"""test_round_act - agent-round 落地第 4 步：lib/agent/act（跑工具的格）（10-31 自 test_round.py 拆出，行為不變）。

act：兩個 tool_calls 吐兩則、順序對；AOS_ACT_MAX_PARALLEL=2 真的一起跑、順序仍對；pre_tool 退 10＝不跑、stdout 當 content；post_tool 取代；
  ToolUnknown／ArgumentsBad／工具退非 0 接成 tool 訊息；插話（queue 的 new/ 有信＋on_interrupt 說 interrupt）剩下的不跑、退 10；aos-tools 壞＝ToolsBad。
設計：proto8/thinking/2026-10-28-agent-round.md § 3、§ 4、文末「實作時代定」；2026-10-30-agent-lifecycle 結論 A、B-11。"""
import json, os, unittest

from round_common import Base, CLOCK, ACT, err_code  # noqa: E402

TOOL_SAY = """#!/usr/bin/env python3
# say - 測試用：把 arguments 的 text 印出來；有 code 就用那個結束碼；wait_for＝等 $AOS_WS/<那個名字> 出現（最多 3 秒）；touch＝建 $AOS_WS/<那個名字>
import json, os, sys, time
a = json.loads(sys.stdin.read() or "{}")
ws = os.environ["AOS_WS"]
if a.get("touch"):
    open(os.path.join(ws, a["touch"]), "w").close()
if a.get("wait_for"):
    end = time.time() + 3
    while not os.path.exists(os.path.join(ws, a["wait_for"])) and time.time() < end:
        time.sleep(0.02)
    print("saw" if os.path.exists(os.path.join(ws, a["wait_for"])) else "no")
print(a.get("text", ""), end="")
print("|" + os.environ["AOS_STACK"])
sys.exit(a.get("code", 0))
"""


def call(cid, name, **arguments):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def assistant(*calls):
    return json.dumps({"role": "assistant", "content": None, "tool_calls": list(calls)})


class Act(Base):
    def setUp(self):
        super().setUp()
        say = self.tmp / "say"
        say.mkdir()
        (say / "_entry").write_text(TOOL_SAY)
        (say / "_entry").chmod(0o755)
        (say / "_tooldef.json").write_text('{"description": "say", "parameters": {"type": "object"}}')
        (self.agent / "tools.json").write_text(json.dumps({"tools": {"say": {"path": str(say)}, "clock": {"path": CLOCK}}}))

    def hook(self, point, script, registered=False):
        """掛一個 sh 寫的掛勾：registered＝登記進 parts.json，否則放固定名字 hook/<點>/。"""
        d = (self.tmp / "hooks" / point) if registered else (self.agent / "hook" / point)
        d.mkdir(parents=True)
        (d / "_entry").write_text("#!/bin/sh\n" + script)
        (d / "_entry").chmod(0o755)
        if registered:
            p = self.agent / "parts.json"
            reg = json.loads(p.read_text()) if p.exists() else {"parts": {}}
            reg["parts"]["hook/" + point] = {"path": str(d), "env": {"HOOK_SAYS": "註冊檔的 env"}}
            p.write_text(json.dumps(reg, ensure_ascii=False))

    def act(self, stdin, env=None):
        return self.cell(ACT, stdin, env)

    def test_two_calls_in_order(self):
        r = self.act(assistant(call("a", "say", text="一\n"), call("b", "clock")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([(m["role"], m["tool_call_id"]) for m in out], [("tool", "a"), ("tool", "b")])
        self.assertEqual(out[0]["content"], "一\n|%s/say/\n" % self.stack)           # 工具的小格＝$AOS_STACK/<名>/
        self.assertRegex(out[1]["content"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n$")

    def test_no_tool_calls(self):
        r = self.act(json.dumps({"role": "assistant", "content": "答"}))
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_parallel_runs_together_order_kept(self):
        calls = assistant(call("a", "say", wait_for="mark", text="A\n"), call("b", "say", touch="mark", text="B\n"))
        r = self.act(calls, {"AOS_ACT_MAX_PARALLEL": "2"})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b"])
        self.assertTrue(out[0]["content"].startswith("saw\nA\n"), out[0])          # a 等到了 b 建的檔＝真的一起跑
        os.unlink(self.ws / "mark")
        r = self.act(calls)                                                     # 依序：a 先跑、等不到
        self.assertTrue(self.lines(r.stdout)[0]["content"].startswith("no\nA\n"))
        r = self.act(calls, {"AOS_ACT_MAX_PARALLEL": "x"})
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "ParallelBad"))

    def test_tool_problems_go_back_to_brain(self):
        r = self.act(assistant(call("a", "nope"), {"id": "b", "type": "function", "function": {"name": "say", "arguments": "{x"}},
                               call("c", "say", text="壞了", code=3)))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = [m["content"] for m in self.lines(r.stdout)]
        self.assertTrue(out[0].startswith("act: ToolUnknown nope（能叫的：clock、say）"), out[0])
        self.assertTrue(out[1].startswith("act: ArgumentsBad say："), out[1])
        self.assertEqual(out[2], "壞了|%s/say/\n(工具 say 結束碼 3)\n" % self.stack)

    def test_pre_tool_10_skips(self):
        self.hook("pre_tool", 'read c; case "$c" in *\\"b\\"*) echo "policy 不准"; exit 10;; esac; exit 0\n')
        r = self.act(assistant(call("a", "say", text="A\n"), call("b", "say", touch="ran_b", text="B\n")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual(out[0]["content"], "A\n|%s/say/\n" % self.stack)
        self.assertEqual(out[1], {"role": "tool", "tool_call_id": "b", "content": "policy 不准\n"})
        self.assertFalse((self.ws / "ran_b").exists())                          # 真的沒跑

    def test_pre_tool_other_code_fails(self):
        self.hook("pre_tool", "exit 3\n")
        r = self.act(assistant(call("a", "say", touch="ran_a")))
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "HookFailed"))
        self.assertFalse((self.ws / "ran_a").exists())

    def test_post_tool_replaces(self):
        self.hook("post_tool", 'read m; case "$m" in *\\"a\\"*) printf \'{"role": "tool", "tool_call_id": "a", "content": "%s"}\\n\' "$HOOK_SAYS";; esac\n',
                  registered=True)
        r = self.act(assistant(call("a", "say", text="長長的"), call("b", "say", text="B")))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual(out[0], {"role": "tool", "tool_call_id": "a", "content": "註冊檔的 env"})   # 取代，且拿到註冊檔的 env
        self.assertEqual(out[1]["content"], "B|%s/say/\n" % self.stack)          # stdout 空＝原樣

    def test_interrupt(self):
        new = self.stack / "queue" / "new"
        new.mkdir(parents=True)
        (new / "000000000009.x").mkdir()                                       # act 只看名字，不讀信
        calls = assistant(call("a", "say", text="A"), call("b", "say", touch="ran_b"), call("c", "clock"))
        r = self.act(calls)                                                     # 沒掛 on_interrupt＝wait
        self.assertEqual((r.returncode, len(self.lines(r.stdout))), (0, 3), r.stderr)
        os.unlink(self.ws / "ran_b")
        self.hook("on_interrupt", 'read n; [ "$n" = 000000000009.x ] && echo interrupt\n')
        r = self.act(calls)
        self.assertEqual(r.returncode, 10, r.stderr)
        out = self.lines(r.stdout)
        self.assertEqual([m["tool_call_id"] for m in out], ["a", "b", "c"])
        self.assertEqual(out[0]["content"], "A|%s/say/\n" % self.stack)
        self.assertEqual(out[1]["content"], "act: Interrupted 有新題（000000000009.x），這個工具沒跑\n")
        self.assertFalse((self.ws / "ran_b").exists())
        os.rmdir(new / "000000000009.x")                                        # new/ 空了＝不問、全跑
        r = self.act(calls)
        self.assertEqual((r.returncode, len(self.lines(r.stdout))), (0, 3))

    def test_own_errors(self):
        (self.agent / "tools.json").write_text("{壞")
        r = self.act(assistant(call("a", "say")))
        self.assertEqual((r.returncode, r.stdout, err_code("act", r.stderr)), (1, "", "ToolsBad"))
        for stdin, code in (("x", "MessageBad"), ('{"tool_calls": [{"id": "a"}]}', "MessageBad")):
            r = self.act(stdin)
            self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, code))
        r = self.cell(ACT, assistant(call("a", "say")), args=["agent"])          # 相對路徑不收
        self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, "AgentBad"))
        (self.agent / "parts.json").write_text(json.dumps({"parts": {"hook/pre_tool": {"path": str(self.tmp / "nope")}}}))
        (self.agent / "tools.json").write_text("{}")
        r = self.act(assistant(call("a", "say")))
        self.assertEqual((r.returncode, err_code("act", r.stderr)), (1, "PartsBad"))   # 登記了但壞＝不當沒掛


if __name__ == "__main__":
    unittest.main()
