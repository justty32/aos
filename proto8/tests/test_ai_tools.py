"""test_ai_tools - proto8/ai_tools：aos-ai 命令列（起 agent、丟題、前景跑、背景 daemon、邊界）與給 agent-dan 掛的三個工具。

不叫真模型、不叫 claude：腦一律是假腦（agent-dan 內建）或下面照規則回的假 server。設計：proto8/thinking/2026-10-24-ai-tools.md。"""
import http.server, json, os, subprocess, tempfile, threading, time, unittest
from pathlib import Path

from aos_bins import ROOT  # noqa: F401  （順便檢查 impls 建好了）

AI = str(ROOT / "ai_tools" / "bin" / "aos-ai")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_AI_ROOT",
         "AOS_AI_JSON_EDITOR")


def ai(root, *args, env=None, stdin=None, timeout=60):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e.update(env or {})
    r = subprocess.run([AI, "--root", root] + list(args), capture_output=True, text=True, env=e, input=stdin,
                       timeout=timeout)
    return r.returncode, (json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None), r.stderr


class RuleBrain:
    """假的 OpenAI 相容 server：tools 裡有 ask_agent 的（老闆）先叫 ask_agent，拿到結果再交答案；沒有的（被問的那隻）直接答。"""

    def __init__(self):
        brain = self
        self.requests = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                brain.requests.append(body)
                names = [t["function"]["name"] for t in body.get("tools", [])]
                last = body["messages"][-1]
                if "ask_agent" in names and last["role"] == "user":
                    msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "ask_agent",
                                        "arguments": json.dumps({"name": "helper", "question": "1+1=?"})}}]}
                elif last["role"] == "tool":
                    msg = {"role": "assistant", "content": "boss got: " + last["content"]}
                else:
                    msg = {"role": "assistant", "content": "helper says 2"}
                data = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


class AiToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        ai(self.root, "daemon", "down")
        self.tmp.cleanup()

    def test_spawn_ask_run_answer(self):
        code, res, _ = ai(self.root, "spawn", "dan")
        self.assertEqual(code, 0)
        self.assertEqual(res["tools"], ["clock", "math"])
        code, res, _ = ai(self.root, "ask", "dan", "--id", "q1", "幾點了")
        self.assertEqual(res["id"], "q1.txt")
        code, res, _ = ai(self.root, "run", "dan")
        self.assertTrue(res["ok"])
        self.assertEqual([a["id"] for a in res["answers"]], ["q1.txt"])
        self.assertIn("FAKE ANSWER to: 幾點了", res["answers"][0]["text"])
        code, res, _ = ai(self.root, "status", "dan")
        self.assertEqual((res["fsm_state"], res["done"], res["new"]), ("idle", ["q1.txt"], []))
        self.assertEqual(res["last_run"]["code"], 0)
        code, res, _ = ai(self.root, "answer", "dan", "q1")
        self.assertIn("FAKE ANSWER", res["text"])
        code, res, _ = ai(self.root, "trace", "dan", "-n", "1")
        self.assertEqual(res["trace"][0]["code"], 10)          # 最後一格 idle 沒題退 10

    def test_question_from_stdin_and_duplicate(self):
        ai(self.root, "spawn", "dan")
        code, res, _ = ai(self.root, "ask", "dan", "--id", "q1", "-", stdin="從 stdin 來的題目")
        self.assertEqual(Path(res["path"]).read_text(encoding="utf-8"), "從 stdin 來的題目\n")
        code, _, err = ai(self.root, "ask", "dan", "--id", "q1", "again")
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("aos-ai: QuestionExists "), err)

    def test_boundary(self):
        for args, want in ((["spawn", "../x"], "NameBad"), (["spawn", "A"], "NameBad"),
                           (["run", "nobody"], "AgentMissing"), (["exec", "--ws", "/", "x"], "PathBad"),
                           (["spawn", "x", "--from", "no-such"], "TemplateMissing"), (["bogus"], "CommandUnknown"),
                           (["status", "--nope", "1"], "FlagUnknown")):
            code, _, err = ai(self.root, *args)
            self.assertEqual(code, 1, args)
            self.assertTrue(err.startswith("aos-ai: %s " % want), (args, err))
        ai(self.root, "spawn", "dan")
        code, _, err = ai(self.root, "edit", "dan", "../../../etc/passwd")
        self.assertTrue(err.startswith("aos-ai: PathBad "), err)
        code, _, err = ai(self.root, "edit", "dan", "agent/fsm.json")
        self.assertTrue(err.startswith("aos-ai: EditorMissing "), err)

    def test_failure_is_data_with_hint(self):
        ai(self.root, "spawn", "dan")
        ai(self.root, "ask", "dan", "--id", "q1", "hi")
        code, res, _ = ai(self.root, "run", "dan", env={"AOS_BRAIN_URL": "http://127.0.0.1:9/v1"})
        self.assertEqual(code, 0)                                # 跑的結果是資料
        self.assertFalse(res["ok"])
        self.assertIn("BrainFailed", [e.get("code") for e in res["errors"]])
        self.assertIn("AOS_BRAIN_URL", res["hint"])
        self.assertEqual((res["fsm_state"], res["waiting"]), ("think", ["q1.txt"]))   # 停在 think 等人（P-20）
        code, res, _ = ai(self.root, "run", "dan")               # 拿掉壞的腦再跑：接著做同一題
        self.assertTrue(res["ok"])
        self.assertEqual([a["id"] for a in res["answers"]], ["q1.txt"])

    def test_background_start_wait_stop(self):
        ai(self.root, "spawn", "bg")
        code, res, err = ai(self.root, "start", "bg", "--interval-ms", "200")
        self.assertTrue(res and res["ok"], err)
        self.assertEqual(res["background"]["phase"], "running")
        code, _, err = ai(self.root, "run", "bg")
        self.assertTrue(err.startswith("aos-ai: AgentBusy "), err)
        ai(self.root, "ask", "bg", "--id", "q1", "hello")
        code, res, err = ai(self.root, "wait", "bg", "q1", "--timeout", "20")
        self.assertTrue(res and "FAKE ANSWER to: hello" in res["text"], err)
        code, res, _ = ai(self.root, "stop", "bg")
        self.assertTrue(res["ok"])
        code, res, _ = ai(self.root, "daemon", "down")
        self.assertFalse(res["running"])
        ctl = json.loads((Path(self.root) / "daemon" / ".stack" / "ctl.json").read_text())
        self.assertEqual((ctl["loops_added"], ctl["stopped"]), ({}, True))

    def test_dan_tools_ask_agent(self):
        """② 老闆 agent 掛 ask_agent，腦叫它 → 起一隻 helper、問、拿答案，再交答案。"""
        brain = RuleBrain()
        try:
            code, res, err = ai(self.root, "spawn", "boss", "--tool", "ask_agent", "--tool", "agent_status")
            self.assertIn("ask_agent", res["tools"], err)
            ai(self.root, "ask", "boss", "--id", "q1", "請 helper 算 1+1")
            code, res, err = ai(self.root, "run", "boss", env={"AOS_BRAIN_URL": brain.url})
            self.assertTrue(res["ok"], (res, err))
            text = res["answers"][0]["text"]
            self.assertIn("boss got:", text)
            self.assertIn("helper says 2", text)
            helper = Path(self.root) / "agents" / "boss" / "ws" / "agents" / "helper"   # 子 agent 放老闆工作區的 agents/
            self.assertTrue((helper / "ws" / "done").is_dir())
            self.assertEqual(len(brain.requests), 3)               # 老闆兩次、helper 一次
        finally:
            brain.close()

    def test_tool_error_is_json(self):
        """工具收到不合的參數：印 {"ok": false, "error"}、退 0，腦看得到、能自己修。"""
        ai(self.root, "spawn", "boss", "--tool", "spawn_agent")
        tool = Path(self.root) / "agents" / "boss" / "agent" / "tools" / "spawn_agent"
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(AOS_WS=self.root, PATH=str(ROOT / "ai_tools" / "bin") + os.pathsep + e["PATH"])
        r = subprocess.run([str(tool / "_entry")], input='{"name": "Bad Name"}', capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0)
        res = json.loads(r.stdout)
        self.assertFalse(res["ok"])
        self.assertIn("NameBad", res["error"])


if __name__ == "__main__":
    unittest.main()
