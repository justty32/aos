"""test_aos_mcp - proto8/extras/ai_tools/bin/aos-mcp：把有 tool.json 的資料夾程式當 MCP tools（stdio JSON-RPC）。

不叫 claude：測試自己當 MCP client，一行一則送 JSON-RPC。設計：proto8/topdown/galtxt-a/plan/side-mcp.md。"""
import json, os, subprocess, tempfile, unittest
from pathlib import Path

from aos_bins import ROOT, path_with  # noqa: E402  （順便檢查 impls 建好了）

MCP = str(ROOT / "extras" / "ai_tools" / "bin" / "aos-mcp")
BASE = ROOT / "lib" / "base"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO")


def env_for(**extra):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra)
    return e


def session(args, msgs, env=None):
    """起 aos-mcp、送一串訊息 → (結束碼, 回覆陣列, stderr)。"""
    inp = "".join(json.dumps(m) + "\n" for m in msgs)
    r = subprocess.run([MCP] + args, input=inp, capture_output=True, text=True, env=env or env_for(), timeout=60)
    return r.returncode, [json.loads(l) for l in r.stdout.splitlines() if l.strip()], r.stderr


def req(i, method, params=None):
    return {"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}


INIT = [req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}),
        {"jsonrpc": "2.0", "method": "notifications/initialized"}]


class AosMcp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        self.ws.mkdir()
        self.stack = Path(self.tmp.name) / "stack"
        self.base = ["--ws", str(self.ws), "--stack", str(self.stack)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_matches_tool_json_and_metainfo(self):
        code, out, _ = session(self.base + [str(BASE / "clock"), str(BASE / "math")], INIT + [req(2, "tools/list")])
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 2)                       # 通知不回
        self.assertEqual(out[0]["result"]["capabilities"], {"tools": {}})
        tools = {t["name"]: t for t in out[1]["result"]["tools"]}
        self.assertEqual(set(tools), {"clock", "math"})
        tj = json.loads((BASE / "math" / "tool.json").read_text())
        self.assertEqual(tools["math"]["inputSchema"], tj["parameters"])
        self.assertEqual(tools["math"]["description"], tj["description"])
        self.assertEqual(tools["math"]["annotations"],
                         {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False})

    def test_tools_dir_expands(self):
        agent = Path(self.tmp.name) / "agent" / "tools"
        agent.mkdir(parents=True)
        (agent / "clock").symlink_to(BASE / "clock")
        (agent / "junk").mkdir()                            # 沒 tool.json 的不列
        code, out, _ = session(self.base + [str(agent.parent)], INIT + [req(2, "tools/list")])
        self.assertEqual([t["name"] for t in out[1]["result"]["tools"]], ["clock"])

    def test_call_ok_and_record(self):
        code, out, _ = session(self.base + [str(BASE / "math")],
                               INIT + [req(2, "tools/call", {"name": "math", "arguments": {"expr": "123456789*987654321"}})])
        res = out[1]["result"]
        self.assertFalse(res["isError"])
        self.assertEqual(res["content"][0]["text"].strip(), str(123456789 * 987654321))
        rec = [json.loads(l) for l in (self.stack / "calls.jsonl").read_text().splitlines()]
        self.assertEqual((rec[0]["name"], rec[0]["code"]), ("math", 0))
        self.assertTrue((self.stack / "math").is_dir())     # 小格 <stack>/<名>/

    def test_call_error_is_iserror(self):
        code, out, _ = session(self.base + [str(BASE / "math")],
                               INIT + [req(2, "tools/call", {"name": "math", "arguments": {"expr": "1/0"}})])
        res = out[1]["result"]
        self.assertTrue(res["isError"])
        self.assertTrue(res["content"][0]["text"].startswith("math: ExprBad"))

    def test_read_uses_ws(self):
        (self.ws / "a.txt").write_text("hello\n")
        _, out, _ = session(self.base + [str(BASE / "read")],
                            INIT + [req(2, "tools/call", {"name": "read", "arguments": {"path": "a.txt"}})])
        self.assertEqual(out[1]["result"]["content"][0]["text"], "hello\n")

    def test_ws_and_stack_from_env(self):
        e = env_for(AOS_WS=str(self.ws), AOS_STACK=str(self.stack))
        _, out, _ = session([str(BASE / "clock")], INIT + [req(2, "tools/call", {"name": "clock"})], env=e)
        self.assertFalse(out[1]["result"]["isError"])
        self.assertTrue((self.stack / "calls.jsonl").exists())

    def test_timeout_kills(self):
        slow = Path(self.tmp.name) / "slow"
        slow.mkdir()
        (slow / "tool.json").write_text('{"description": "slow", "parameters": {"type": "object", "properties": {}}}')
        (slow / "_entry").write_text("#!/bin/sh\nsleep 30\n")
        (slow / "_entry").chmod(0o755)
        _, out, _ = session(self.base + ["--timeout-s", "0.5", str(slow)],
                            INIT + [req(2, "tools/call", {"name": "slow"})])
        res = out[1]["result"]
        self.assertTrue(res["isError"])
        self.assertIn("CommandFailed slow 逾時", res["content"][0]["text"])

    def test_protocol_errors(self):
        _, out, _ = session(self.base + [str(BASE / "clock")],
                            INIT + [req(2, "tools/call", {"name": "nope"}), req(3, "resources/list"), req(4, "ping")])
        self.assertEqual(out[1]["error"]["code"], -32602)
        self.assertEqual(out[2]["error"]["code"], -32601)
        self.assertEqual(out[3]["result"], {})

    def test_own_errors(self):
        for args, code in (([], "ArgumentsBad"), (["--ws", "/nonexistent", str(BASE / "clock")], "WsMissing"),
                           (self.base + [self.tmp.name], "ToolMissing")):
            rc, _, err = session(args, [])
            self.assertEqual(rc, 1)
            self.assertTrue(err.startswith("aos-mcp: " + code), err)


if __name__ == "__main__":
    unittest.main()
