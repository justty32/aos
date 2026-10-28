"""test_dan - 跑 demo/agent-dan（會用工具的問答 agent）：假 server 照劇本回 tool_calls／答案，驗 tools 陣列、history 接法、叫工具出的問題回給腦、環境壞了停住、重跑接著做。

設計：proto8/thinking/2026-10-23-tool-calls.md。連真模型的那個（test_real_model）localhost:4000 連不上就 skip。"""
import http.server, json, os, re, subprocess, tempfile, threading, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()   # aos-* 那幾支的錯誤代號照舊檢查；agent-dan 自己的那行在下面 dan_errors 檢查

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
DAN = str(ROOT / "demo" / "agent-dan")
REAL_URL = "http://localhost:4000/v1"
CODES = ("BrainFailed", "ReplyBad", "ToolUnknown", "ArgumentsBad", "ToolFailed", "StackMissing",
         "QuestionMissing", "HistoryBad")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def dan_errors(stderr):
    """stderr 裡 agent-dan 的每一行都要是「agent-dan: 代號 原因」，代號在表上；回代號清單。"""
    found = []
    for line in stderr.splitlines():
        if line.startswith("agent-dan:"):
            m = re.match(r"agent-dan: ([A-Z][A-Za-z]+) \S", line)
            assert m and m.group(1) in CODES, "agent-dan 的錯誤行格式不對：%r" % line
            found.append(m.group(1))
    return found


def call(cid, name, arguments):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def tool_reply(*calls):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}]}


def answer(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


class FakeBrain:
    """假的 OpenAI 相容 server：每次 POST /v1/chat/completions 回劇本的下一個；記下每個 request body。
    劇本一項＝dict（200 回 JSON）或 (狀態碼, 字串)。"""

    def __init__(self, script):
        self.script, self.requests = list(script), []
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                brain.requests.append(json.loads(body))
                item = brain.script.pop(0) if brain.script else (500, "劇本用完了")
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                if self.path != "/v1/chat/completions":
                    status, text = 404, "path " + self.path
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def brain(self, *script):
        b = FakeBrain(script)
        self.addCleanup(b.close)
        return b

    def ask(self, question="17*23 是多少？"):
        (self.ws / "new" / "q1.txt").write_text(question)

    def dan(self, url=None, timeout=60):
        env = {"AOS_BRAIN_URL": url} if url else {}
        return run(EXEC, "--ws", "ws", DAN, env=env, cwd=self.tmp, timeout=timeout)

    def history(self):
        return [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines()]

    def states(self):
        return [json.loads(l)["state"] for l in (self.stack / "trace.jsonl").read_text().splitlines()]

    def ls(self, d):
        p = self.ws / d
        return sorted(os.listdir(p)) if p.exists() else []

    def test_tools_then_answer(self):
        """(a) 兩輪：叫 math、clock → 答 391。"""
        b = self.brain(tool_reply(call("c1", "math", {"expr": "17*23"}), call("c2", "clock", {})), answer("391"))
        self.ask()
        r = self.dan(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(dan_errors(r.stderr), [])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "391\n")
        self.assertEqual((self.ls("cur"), self.ls("done")), ([], ["q1.txt"]))
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual([m["tool_call_id"] for m in h[2:4]], ["c1", "c2"])
        self.assertEqual(h[2]["content"], "391\n")
        self.assertRegex(h[3]["content"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n$")
        self.assertEqual(h[4], {"role": "assistant", "content": "391"})
        first, second = b.requests
        self.assertEqual(first["model"], "chatgpt-gpt-6-luna-low")       # 範本 .env 給的
        fns = [t["function"] for t in first["tools"]]
        self.assertEqual([f["name"] for f in fns], ["clock", "math"])
        for f in fns:
            spec = json.loads(Path(DAN, "tools", f["name"], "_tooldef.json").read_text())
            self.assertEqual((f["description"], f["parameters"]), (spec["description"], spec["parameters"]))
        self.assertEqual(first["messages"][0], {"role": "system", "content": Path(DAN, "system.txt").read_text()})
        self.assertEqual(first["messages"][1], {"role": "user", "content": "17*23 是多少？"})
        self.assertEqual(len(first["messages"]), 2)
        self.assertEqual([m["role"] for m in second["messages"]].count("tool"), 2)
        self.assertEqual(second["messages"][1:], h[:4])                 # system 不進 history
        self.assertEqual(self.states(), ["idle", "think", "act", "idle", "think", "act", "idle"])
        self.assertTrue((self.stack / "math").is_dir() and (self.stack / "clock").is_dir())

    def test_answer_without_tools(self):
        """(b) 不叫工具：一輪就答。"""
        b = self.brain(answer("直接答"))
        self.ask()
        r = self.dan(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "直接答\n")
        self.assertEqual(self.states(), ["idle", "think", "act", "idle"])
        self.assertEqual(len(b.requests), 1)

    def assert_back_to_brain(self, r, content):
        """叫工具出的問題回給腦（10-24 起）：那則 tool 訊息帶著錯、腦第二次看得到、照樣交答案。"""
        self.assertEqual(r.returncode, 0, r.stderr)
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertIn(content, h[2]["content"])
        self.assertEqual(self.b.requests[1]["messages"][1:4], h[:3])
        self.assertEqual((self.ls("cur"), self.ls("out"), self.ls("done")), ([], ["q1.txt"], ["q1.txt"]))
        return h

    def test_tool_failed(self):
        """(c) 工具退非 0：stdout 那行加結束碼回給腦、不停；人在 stderr 看得到。"""
        self.b = self.brain(tool_reply(call("c1", "math", {"expr": "1/0"})), answer("除以零，算不出來"))
        self.ask()
        r = self.dan(self.b.url)
        h = self.assert_back_to_brain(r, "math: ExprBad 除以零")
        self.assertTrue(h[2]["content"].endswith("(工具 math 結束碼 1)\n"), h[2]["content"])
        self.assertIn("agent-dan: ToolFailed math 結束碼 1（回給腦）", r.stderr)
        self.assertIn("math: ExprBad 除以零", r.stderr)          # 工具自己的 stderr 原樣往上

    def test_tool_unknown(self):
        """(d) 腦叫了 tools/ 裡沒有的工具：回給腦、附能叫的。"""
        self.b = self.brain(tool_reply(call("c1", "weather", {"city": "台北"})), answer("沒有天氣工具"))
        self.ask()
        self.assert_back_to_brain(self.dan(self.b.url), "act: ToolUnknown weather（能叫的：clock、math）")

    def test_tool_name_cannot_escape(self):
        """工具名帶 ../ 也當不認得（名字只認 tools.json 登記過的）。"""
        self.b = self.brain(tool_reply(call("c1", "../tools/math", {"expr": "1"})), answer("好"))
        self.ask()
        self.assert_back_to_brain(self.dan(self.b.url), "act: ToolUnknown ../tools/math")
        self.assertFalse((self.stack / "math").exists())

    def test_arguments_bad(self):
        self.b = self.brain(tool_reply({"id": "c1", "type": "function", "function": {"name": "math", "arguments": "{expr"}}),
                            answer("好"))
        self.ask()
        self.assert_back_to_brain(self.dan(self.b.url), "act: ArgumentsBad math：")

    def test_env_broken_still_stops(self):
        """環境壞了照舊停：aos-exec 不在 PATH（工具起不來）＝ToolFailed、退 1、history 不接。"""
        self.stack.mkdir()
        h = [{"role": "user", "content": "q"},
             {"role": "assistant", "content": None, "tool_calls": [call("c1", "math", {"expr": "1"})]}]
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m) + "\n" for m in h))
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(PATH="/usr/bin:/bin", AOS_WS=str(self.ws), AOS_STACK=str(self.stack) + "/")
        r = subprocess.run(["python3", "act.py"], cwd=DAN, env=e, capture_output=True, text=True)
        self.assertEqual((r.returncode, dan_errors(r.stderr)), (1, ["ToolFailed"]))
        self.assertIn("起不來", r.stderr)
        self.assertEqual(self.history(), h)

    def test_brain_failed_then_rerun(self):
        """(e) 腦 HTTP 500：停在 think、只接了題目；再跑一次接著做，不重複接題。"""
        b = self.brain((500, "boom"), answer("好了"))
        self.ask()
        r = self.dan(b.url)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("BrainFailed", dan_errors(r.stderr))
        self.assertEqual((self.stack / "state.txt").read_text(), "think\n")
        self.assertEqual([m["role"] for m in self.history()], ["user"])
        self.assertEqual(self.ls("cur"), ["q1.txt"])
        r = self.dan(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "好了\n")

    def test_brain_unreachable(self):
        self.ask()
        r = self.dan("http://127.0.0.1:9/v1")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("BrainFailed", dan_errors(r.stderr))
        self.assertEqual([m["role"] for m in self.history()], ["user"])

    def test_reply_bad(self):
        b = self.brain((200, "not json"), {"choices": []})
        self.ask()
        for _ in range(2):
            r = self.dan(b.url)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("ReplyBad", dan_errors(r.stderr))
            self.assertEqual([m["role"] for m in self.history()], ["user"])

    def test_question_missing_and_stack_missing(self):
        """直接叫 brain.py：沒題目、沒 AOS_STACK。"""
        self.stack.mkdir()
        r = run("python3", "brain.py", cwd=DAN, env={"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"})
        self.assertEqual((r.returncode, dan_errors(r.stderr)), (1, ["QuestionMissing"]))
        self.assertIn("agent-dan: QuestionMissing new/ 是空的", r.stderr)
        r = run("python3", "brain.py", cwd=DAN, env={"AOS_WS": str(self.ws)})
        self.assertEqual((r.returncode, dan_errors(r.stderr)), (1, ["StackMissing"]))
        r = run("python3", "act.py", cwd=DAN, env={"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"})
        self.assertEqual((r.returncode, dan_errors(r.stderr)), (1, ["HistoryBad"]))

    def test_rerun_only_answers_missing_calls(self):
        """(f) act 跑到一半被打斷（c1 有回、c2 沒回）：再跑 act 只補 c2，c1 不重跑。"""
        self.stack.mkdir()
        h = [{"role": "user", "content": "q"},
             {"role": "assistant", "content": None,
              "tool_calls": [call("c1", "math", {"expr": "2+3"}), call("c2", "math", {"expr": "4*5"})]},
             {"role": "tool", "tool_call_id": "c1", "content": "舊的\n"}]
        (self.stack / "history.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in h))
        r = run("python3", "act.py", cwd=DAN, env={"AOS_WS": str(self.ws), "AOS_STACK": str(self.stack) + "/"})
        self.assertEqual(r.returncode, 0, r.stderr)
        tools = [m for m in self.history() if m["role"] == "tool"]
        self.assertEqual([(m["tool_call_id"], m["content"]) for m in tools], [("c1", "舊的\n"), ("c2", "20\n")])

    def test_fake_brain(self):
        """(h) 不設 URL＝假腦：叫一次 clock，再答。"""
        self.ask("現在幾點？")
        r = self.dan()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (self.ws / "out" / "q1.txt").read_text()
        self.assertIn("FAKE ANSWER to: 現在幾點？", out)
        self.assertIn("clock said", out)
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(h[1]["tool_calls"][0]["function"]["name"], "clock")
        self.assertEqual(h[2]["tool_call_id"], "call_fake_1")

    def test_math_tool(self):
        """math 工具本身：只算算術，不吃別的。"""
        m = str(Path(DAN, "tools", "math", "_entry"))
        for expr, out in (("17*23", "391\n"), ("-(2+3)**2 % 7", "3\n"), ("7//2", "3\n")):
            r = run(m, input=json.dumps({"expr": expr}))
            self.assertEqual((r.returncode, r.stdout), (0, out), r.stderr)
        for stdin in ('{"expr": "__import__(\'os\')"}', '{"expr": "2**99999"}', "nope", "{}", '{"expr": "1/0"}'):
            r = run(m, input=stdin)
            self.assertEqual(r.returncode, 1, stdin)
            self.assertRegex(r.stderr, r"^math: ExprBad \S")
            self.assertEqual(r.stdout, r.stderr)                    # stdout 也印同一行（給腦看）

    def test_real_model(self):
        """(g) 真模型（本機 LiteLLM）：連不上就 skip。"""
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=2).read()
        except OSError as e:
            self.skipTest("LiteLLM 連不上：%s" % e)
        self.ask("請用工具算 17*23，並用工具查現在 UTC 幾點，最後用一句話回答。")
        r = self.dan(REAL_URL, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("391", (self.ws / "out" / "q1.txt").read_text())
        self.assertTrue(any(m["role"] == "tool" for m in self.history()))


if __name__ == "__main__":
    unittest.main()
