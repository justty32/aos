"""test_eve - 跑 demo/agent-eve（agent 當工具：eve 的腦叫 pyfix，pyfix 是另一隻會改 Python 的 agent）。

假 server 照劇本回：同一個 URL 同時當 eve 和 pyfix 的腦，看 request 裡的 tools 有沒有 pyfix 分給兩份劇本。
設計：proto8/thinking/2026-10-24-agent-as-tool.md。不連真模型。"""
import http.server, json, os, re, subprocess, tempfile, threading, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
EVE = ROOT / "demo" / "agent-eve"
PYFIX = EVE / "tools" / "pyfix"
SUB_TOOLS = PYFIX / "agent" / "tools"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "PYFIX_DIR")

BUGGY = "def add(a, b):\n    return a - b\n"
TEST = ("import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n\nunittest.main()\n")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def call(cid, name, arguments):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def tool_reply(*calls):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}]}


def answer(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


class TwoBrains:
    """假的 OpenAI 相容 server：request 的 tools 裡有 pyfix＝eve 的腦（outer 劇本），否則＝pyfix 子 agent 的腦（inner 劇本）。
    劇本一項＝dict（200 回 JSON）或 (狀態碼, 字串)。"""

    def __init__(self, outer, inner):
        self.scripts = {"outer": list(outer), "inner": list(inner)}
        self.requests = {"outer": [], "inner": []}
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                who = "outer" if any(t["function"]["name"] == "pyfix" for t in body.get("tools", [])) else "inner"
                brain.requests[who].append(body)
                script = brain.scripts[who]
                item = script.pop(0) if script else (500, "劇本用完了")
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


FIX = [tool_reply(call("s1", "list_files", {})),
       tool_reply(call("s2", "read_file", {"path": "calc.py"})),
       tool_reply(call("s3", "run_python", {"args": ["test_calc.py"]})),
       tool_reply(call("s4", "edit_file", {"path": "calc.py", "old": "a - b", "new": "a + b"})),
       tool_reply(call("s5", "run_python", {"args": ["test_calc.py"]})),
       answer("原因：add 用了減號。改 calc.py 第 2 行成 a + b。測試通過。")]


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        (self.ws / "proj").mkdir()
        (self.ws / "proj" / "calc.py").write_text(BUGGY)
        (self.ws / "proj" / "test_calc.py").write_text(TEST)
        (self.ws / "new" / "q1.txt").write_text("proj/ 裡的測試沒過，幫我修好。")
        self.stack = self.ws / ".stack"

    def brains(self, outer, inner):
        b = TwoBrains(outer, inner)
        self.addCleanup(b.close)
        return b

    def eve(self, url, env=None):
        return run(EXEC, "--ws", "ws", str(EVE), env=dict(env or {}, AOS_BRAIN_URL=url), cwd=self.tmp, timeout=120)

    def history(self, stack):
        return [json.loads(l) for l in (stack / "history.jsonl").read_text().splitlines()]

    def test_delegate_and_fix(self):
        """eve 叫 pyfix → 子 agent 讀、跑、改、再跑、答 → eve 拿到答案＋diff 再答。"""
        b = self.brains([tool_reply(call("c1", "pyfix", {"task": "讓 test_calc.py 通過", "dir": "proj"})),
                         answer("修好了：add 的減號改成加號。")], FIX)
        r = self.eve(b.url, env={"AOS_BRAIN_MODEL": "outer-model"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ws / "proj" / "calc.py").read_text(), "def add(a, b):\n    return a + b\n")
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "修好了：add 的減號改成加號。\n")
        h = self.history(self.stack)
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        result = h[2]["content"]
        self.assertTrue(result.startswith("原因：add 用了減號。"), result)
        self.assertIn("--- 實際改動（diff）---\n--- a/calc.py\n+++ b/calc.py\n", result)
        self.assertIn("-    return a - b\n+    return a + b\n", result)
        # 子 agent 的現場：小格 runs/001，裡面它自己的工作區、stack、改之前的備份
        run1 = self.stack / "pyfix" / "runs" / "001"
        self.assertEqual((run1 / "before" / "calc.py").read_text(), BUGGY)
        self.assertEqual(os.listdir(run1 / "ws" / "done"), ["task.txt"])
        sub = self.history(run1 / "stack")
        self.assertEqual(sub[0], {"role": "user", "content": "讓 test_calc.py 通過"})
        tools = [m["content"] for m in sub if m["role"] == "tool"]
        self.assertIn("calc.py\ntest_calc.py", tools[0])
        self.assertTrue(tools[2].startswith("結束碼 1\n"), tools[2])
        self.assertEqual(tools[3], "改好了：calc.py\n")
        self.assertTrue(tools[4].startswith("結束碼 0\n"), tools[4])
        # 模型：外面設的蓋過 eve 的 .env（不蓋）；pyfix 用 --dotenv-override 叫子 agent，子 agent 用自己 .env 的
        self.assertEqual({q["model"] for q in b.requests["outer"]}, {"outer-model"})
        self.assertEqual({q["model"] for q in b.requests["inner"]}, {"chatgpt-gpt-6-luna-low"})
        # 兩個腦各看到自己的 system 與工具
        self.assertEqual(b.requests["inner"][0]["messages"][0]["content"],
                         (PYFIX / "agent" / "system.txt").read_text())
        self.assertEqual(sorted(t["function"]["name"] for t in b.requests["inner"][0]["tools"]),
                         ["edit_file", "list_files", "read_file", "run_python", "write_file"])

    def test_each_call_is_fresh(self):
        """同一題叫兩次 pyfix：各開一個小格（002），第二次的子 agent 只看到自己的題目、不帶第一次的對話。"""
        b = self.brains([tool_reply(call("c1", "pyfix", {"task": "第一件", "dir": "proj"})),
                         tool_reply(call("c2", "pyfix", {"task": "第二件", "dir": "proj"})),
                         answer("兩件都好了")],
                        [answer("第一件好了"), answer("第二件好了")])
        r = self.eve(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(self.stack / "pyfix" / "runs")), ["001", "002"])
        second = b.requests["inner"][1]["messages"]
        self.assertEqual([m["role"] for m in second], ["system", "user"])
        self.assertEqual(second[1]["content"], "第二件")
        tools = [m["content"] for m in self.history(self.stack) if m["role"] == "tool"]
        self.assertEqual(tools, ["第一件好了\n\n--- 實際改動（diff）---\n（沒有改任何檔）\n",
                                 "第二件好了\n\n--- 實際改動（diff）---\n（沒有改任何檔）\n"])

    def test_sub_agent_fails_outer_stops(self):
        """子 agent 的腦壞了：子 agent 停、pyfix 退 1、eve 停在 act（ToolFailed），題目留在 cur/。再跑一次開新小格做完。"""
        b = self.brains([tool_reply(call("c1", "pyfix", {"task": "修", "dir": "proj"})), answer("好了")],
                        [(500, "boom"), answer("修好了")])
        r = self.eve(b.url)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("pyfix-agent: BrainFailed", r.stderr)
        self.assertRegex(r.stderr, r"pyfix: AgentFailed 子 agent 結束碼 1（現場在 \S+/runs/001）")
        self.assertIn("agent-eve: ToolFailed pyfix 結束碼 1", r.stderr)
        self.assertEqual((self.stack / "state.txt").read_text(), "act\n")
        self.assertEqual(os.listdir(self.ws / "cur"), ["q1.txt"])
        r = self.eve(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(self.stack / "pyfix" / "runs")), ["001", "002"])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "好了\n")

    def test_dir_cannot_escape(self):
        """pyfix 的 dir 跑出工作區＝DirBad；子 agent 沒被叫。"""
        b = self.brains([tool_reply(call("c1", "pyfix", {"task": "修", "dir": "../"}))], [])
        r = self.eve(b.url)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("pyfix: DirBad", r.stderr)
        self.assertEqual(b.requests["inner"], [])

    def test_sub_tools_stay_inside(self):
        """子 agent 的工具：路徑出不去（回給模型、不算失敗）；edit_file 要剛好一次；run_python 會逾時。"""
        root = self.ws / "proj"
        env = {"PYFIX_DIR": str(root)}

        def t(name, args):
            r = run(str(SUB_TOOLS / name / "_entry"), input=json.dumps(args), env=env, cwd=SUB_TOOLS / name)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout

        (self.ws / "secret.txt").write_text("no")
        self.assertIn("跑出工作資料夾", t("read_file", {"path": "../secret.txt"}))
        self.assertIn("跑出工作資料夾", t("write_file", {"path": "../x.py", "content": "x"}))
        self.assertIn("跑出工作資料夾", t("list_files", {"dir": ".."}))
        self.assertFalse((self.ws / "x.py").exists())
        self.assertIn("出現 2 次", t("edit_file", {"path": "calc.py", "old": "b", "new": "c"}))
        self.assertIn("出現 0 次", t("edit_file", {"path": "calc.py", "old": "zzz", "new": "c"}))
        self.assertEqual(t("write_file", {"path": "sub/new.py", "content": "print(1)\n"}), "寫好了：sub/new.py（9 個字）\n")
        self.assertEqual(t("run_python", {"args": ["sub/new.py"]}), "結束碼 0\n1\n")
        (root / "spin.py").write_text("while True: pass\n")
        self.assertTrue(t("run_python", {"args": ["spin.py"], "timeout_s": 1}).startswith("逾時：跑超過 1 秒"))
        self.assertEqual(t("read_file", {"path": "calc.py"}), BUGGY)
        r = run(str(SUB_TOOLS / "read_file" / "_entry"), input="{}", cwd=self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^read_file: DirMissing ")


if __name__ == "__main__":
    unittest.main()
