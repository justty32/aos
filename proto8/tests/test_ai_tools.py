"""test_ai_tools - proto8/extras/ai_tools：aos-ai 命令列（起 agent、丟題、前景跑、背景 daemon、邊界）與給 agent 掛的工具。

不叫真模型、不叫 claude：腦一律是假腦（agent-nia 的 endpoint/fake）或下面照規則回的假 server（把 spawn 出來的 nia 的
endpoint/default 換成 lib/endpoint/openai）。10-30 起 aos-ai 走 queue（ask＝寄信進 ws/.stack/queue/、答案看 history；
thinking 2026-10-30-agent-lifecycle 第 4 步、隊長代定甲）：預設範本 agent-nia；舊協議的 agent-dan 只剩「生成 fsm 格」那案，
題目手放 ws/new/。設計：proto8/thinking/2026-10-24-ai-tools.md。"""
import http.server, json, os, re, subprocess, tempfile, threading, time, unittest
from pathlib import Path

from aos_bins import ROOT, EXEC, path_with  # noqa: E402  （順便檢查 impls 建好了）
from dead_brain import DEAD  # noqa: E402  （腦壞了＝連上去馬上被拒的網址）

AI = str(ROOT / "extras" / "ai_tools" / "bin" / "aos-ai")
SIG = re.compile(r"^\d{12}\.\d{20}\.\d+\.\d+$")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_AI_ROOT",
         "AOS_AI_JSON_EDITOR")


def ai(root, *args, env=None, stdin=None, timeout=60):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e.update(env or {})
    r = subprocess.run([AI, "--root", root] + list(args), capture_output=True, text=True, env=e, input=stdin,
                       timeout=timeout)
    return r.returncode, (json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None), r.stderr


def openai_brain(root, name):
    """spawn 出來的 nia 改問 OpenAI 相容的腦（網址從 AOS_BRAIN_URL 來，ai(..., env=) 給）。"""
    p = Path(root) / "agents" / name / "agent" / "parts.json"
    reg = json.loads(p.read_text())
    reg["parts"]["endpoint/default"] = {"path": str(ROOT / "lib" / "endpoint" / "openai"), "env": {"AOS_BRAIN_MODEL": "m"}}
    p.write_text(json.dumps(reg))


def aos_exec(target, ws, env=None):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run([EXEC, "--ws", ws, target], capture_output=True, text=True, env=e, timeout=60)


class ToolBrain:
    """假 server：題目來了先叫 shout（生成出來的工具），拿到結果就把它當答案。"""

    def __init__(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                last = body["messages"][-1]
                if last["role"] == "user":
                    msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "s1", "type": "function",
                           "function": {"name": "shout", "arguments": json.dumps({"text": "hi"})}}]}
                else:
                    msg = {"role": "assistant", "content": "tool said " + last["content"]}
                data = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


class RuleBrain:
    """假的 OpenAI 相容 server：tools 裡有 ask_agent 的（老闆）先叫 ask_agent，拿到結果再交答案；沒有的（被問的那隻）直接答。"""

    def __init__(self, helper="helper"):
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
                                        "arguments": json.dumps({"name": helper, "question": "1+1=?"})}}]}
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
        code, res, _ = ai(self.root, "spawn", "nia")
        self.assertEqual(code, 0)
        self.assertTrue(res["from"].endswith("agent-nia"), res)               # 10-30 起預設範本
        self.assertEqual(res["tools"], ["clock", "math"])
        self.assertEqual(sorted(os.listdir(res["ws"])), [".stack"])           # 工作區不建 new/ out/
        code, res, _ = ai(self.root, "ask", "nia", "幾點了")
        qid = res["id"]
        self.assertRegex(qid, SIG)                                            # 信號由 aos-post 給
        code, res, _ = ai(self.root, "run", "nia")
        self.assertTrue(res["ok"], res)
        self.assertEqual((res["answered"], res["waiting"], res["loop_phase"]), ([qid], [], "done"))
        self.assertEqual(len(res["answers"]), 1)
        self.assertIn("FAKE ANSWER to: 幾點了", res["answers"][0]["text"])
        code, res, _ = ai(self.root, "status", "nia")
        self.assertEqual((res["fsm_state"], res["new"], res["cur"], res["counter_answers"]), ("idle", [], [], 1))   # nia 走 aos-round（fsm）、答完停在 idle
        self.assertEqual(res["last_run"]["code"], 0)
        self.assertIn("finished_at", res["last_run"])                      # 跑完的時間（10-25 前叫 at）
        code, res, _ = ai(self.root, "answer", "nia", qid)
        self.assertIn("FAKE ANSWER", res["text"])
        code, res, _ = ai(self.root, "answer", "nia")
        self.assertEqual(res["answers"][0]["asked"], ["幾點了"])
        code, res, _ = ai(self.root, "trace", "nia", "-n", "1")
        self.assertEqual((res["fsm_state"], res["trace"][0]["state"], res["trace"][0]["code"]), ("idle", "idle", 10))   # aos-round：最後一格 idle 沒信退 10

    def test_question_from_stdin_and_no_id(self):
        ai(self.root, "spawn", "nia")
        code, res, _ = ai(self.root, "ask", "nia", "-", stdin="從 stdin 來的題目")
        letter = json.loads((Path(res["path"]) / "letter.json").read_text(encoding="utf-8"))
        self.assertEqual(letter["body"], {"role": "user", "content": "從 stdin 來的題目"})
        code, _, err = ai(self.root, "ask", "nia", "--id", "q1", "again")    # --id 拿掉了（10-30）
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("aos-ai: FlagUnknown "), err)
        code, _, err = ai(self.root, "answer", "nia", res["id"])            # 還在 queue 的 new/
        self.assertTrue(err.startswith("aos-ai: AnswerMissing ") and "new/" in err, err)

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
        code, _, err = ai(self.root, "edit", "dan", "agent/loop.json")
        self.assertTrue(err.startswith("aos-ai: EditorMissing "), err)

    def test_failure_is_data_with_hint(self):
        ai(self.root, "spawn", "nia")
        openai_brain(self.root, "nia")
        code, q, _ = ai(self.root, "ask", "nia", "hi")
        code, res, _ = ai(self.root, "run", "nia", env={"AOS_BRAIN_URL": DEAD})
        self.assertEqual(code, 0)                                # 跑的結果是資料
        self.assertFalse(res["ok"])
        self.assertIn("BrainFailed", [e.get("code") for e in res["errors"]])
        self.assertIn("AOS_BRAIN_URL", res["hint"])
        self.assertEqual((res["waiting"], res["answers"]), ([q["id"]], []))   # 信留在 queue 的 cur/ 等人（P-20）
        brain = RuleBrain()
        try:
            code, res, _ = ai(self.root, "run", "nia", env={"AOS_BRAIN_URL": brain.url})   # 換好的腦再跑：接著做同一封
        finally:
            brain.close()
        self.assertTrue(res["ok"], res)
        self.assertEqual((res["answered"], [a["text"] for a in res["answers"]]), ([q["id"]], ["helper says 2"]))

    def test_background_start_wait_stop(self):
        ai(self.root, "spawn", "bg")
        code, res, err = ai(self.root, "start", "bg", "--interval-ms", "200")
        self.assertTrue(res and res["ok"], err)
        self.assertEqual(res["background"]["phase"], "running")
        code, _, err = ai(self.root, "run", "bg")
        self.assertTrue(err.startswith("aos-ai: AgentBusy "), err)
        code, q, err = ai(self.root, "ask", "bg", "hello")
        code, res, err = ai(self.root, "wait", "bg", q["id"], "--timeout", "20")
        self.assertTrue(res and "FAKE ANSWER to: hello" in res["text"], err)
        code, res, _ = ai(self.root, "stop", "bg")
        self.assertTrue(res["ok"])
        code, res, _ = ai(self.root, "daemon", "down")
        self.assertFalse(res["running"])
        ctl = json.loads((Path(self.root) / "daemon" / ".stack" / "ctl.json").read_text())
        lctl = json.loads((Path(self.root) / "daemon" / ".stack" / "loops_ctl.json").read_text())   # 10-29 daemon 拆窗
        self.assertEqual((lctl["loops_added"], ctl["stopped"], "loops_added" in ctl), ({}, True, False))

    def test_dan_tools_ask_agent(self):
        """② 老闆 agent 掛 ask_agent，腦叫它 → 起一隻 helper、問、拿答案，再交答案。"""
        brain = RuleBrain()
        try:
            code, res, err = ai(self.root, "spawn", "boss", "--tool", "ask_agent", "--tool", "agent_status")
            self.assertIn("ask_agent", res["tools"], err)
            openai_brain(self.root, "boss")
            ai(self.root, "ask", "boss", "請 helper 算 1+1")
            code, res, err = ai(self.root, "run", "boss", env={"AOS_BRAIN_URL": brain.url})
            self.assertTrue(res["ok"], (res, err))
            text = res["answers"][0]["text"]
            self.assertIn("boss got:", text)
            self.assertIn("FAKE ANSWER to: 1+1=?", text)            # helper＝預設範本 agent-nia（假腦）
            helper = Path(self.root) / "agents" / "boss" / "ws" / "agents" / "helper"   # 子 agent 放老闆工作區的 agents/
            self.assertTrue((helper / "ws" / ".stack" / "history.jsonl").is_file())
            self.assertEqual(len(brain.requests), 2)               # 老闆兩次（helper 是假腦，不問 server）
        finally:
            brain.close()

    def test_tool_error_is_one_line(self):
        """工具收到不合的參數：照 lib 契約 stderr 與 stdout 各一行「工具名: 代號 原因」、退 1（代號照 aos-ai 的）；
        停下還是回給腦由叫它的 agent 決定（10-24 遷移前是印 {"ok": false, "error"}、退 0）。"""
        ai(self.root, "spawn", "boss", "--tool", "spawn_agent")
        tool = Path(self.root) / "agents" / "boss" / "agent" / "tools" / "spawn_agent"
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(AOS_WS=self.root, PATH=str(ROOT / "extras" / "ai_tools" / "bin") + os.pathsep + e["PATH"])
        r = subprocess.run([str(tool / "_entry")], input='{"name": "Bad Name"}', capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("spawn_agent: NameBad "), r.stderr)
        self.assertEqual(r.stdout.strip(), r.stderr.strip())


    def test_tool_errors_back_to_brain(self):
        """spawn 出來的 agent（agent-nia 範本，lib/agent/act）工具退 1 那行回給腦、題目照樣答完。
        （10-24 真腦實測：遷移後工具錯退 1，老闆停在 act、重跑又叫同一個，卡住；lib 的 act 把工具的問題回給腦。）"""
        brain = RuleBrain(helper="Bad Name")
        try:
            code, res, err = ai(self.root, "spawn", "boss", "--tool", "ask_agent")
            self.assertTrue(res["ok"], err)
            openai_brain(self.root, "boss")
            ai(self.root, "ask", "boss", "請 helper 算 1+1")
            code, res, err = ai(self.root, "run", "boss", env={"AOS_BRAIN_URL": brain.url})
            self.assertTrue(res["ok"], (res, err))
            self.assertIn("boss got: ask_agent: NameBad ", res["answers"][0]["text"])
            self.assertIn("NameBad", [e.get("code") for e in res["errors"]])        # 工具那行 stderr 人在 errors 裡看得到
        finally:
            brain.close()
        code, _, err = ai(self.root, "spawn", "p2", "--tool-errors", "stop")      # 旗標拿掉了
        self.assertTrue(err.startswith("aos-ai: FlagUnknown "), err)
        self.assertFalse((Path(self.root) / "agents" / "p2").exists())

    # ---------- 生成（make）與概念（explain） ----------

    def test_make_loop_fsm_inst_func_run(self):
        """生成的 loop.json＋fsm.json、單子、函數資料夾，都能被 aos-exec／aos-loop／aos-fsm 真的跑起來。"""
        r = self.root
        code, res, err = ai(r, "make", "loop", "--exec", "fsm.json", "--max", "5", "--out", r + "/w/loop.json")
        self.assertTrue(res and res["ok"] and "exec" in res["notes"], err)
        code, res, err = ai(r, "make", "fsm", "--cell", 'a={"argv": ["sh", "-c", "echo A >> $AOS_STACK/log.txt"]}',
                            "--cell", 'b={"argv": ["sh", "-c", "exit 10"]}', "--out", r + "/w/fsm.json", "--no-notes")
        self.assertEqual(res["json"]["states"]["b"]["next"], "a", err)          # 照順序接成環
        self.assertNotIn("notes", res)
        p = aos_exec(r + "/w/loop.json", r)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((Path(r) / ".stack" / "log.txt").read_text(), "A\n")
        self.assertEqual([json.loads(l)["state"] for l in (Path(r) / ".stack" / "trace.jsonl").read_text().splitlines()], ["a", "b"])
        code, res, err = ai(r, "make", "inst", "--argv", "sh -c 'echo x'", "--out", r + "/i.json")
        self.assertEqual(res["json"]["argv"], ["sh", "-c", "'echo", "x'"], err)  # 字串照空白切；要精確寫 JSON 陣列
        code, res, err = ai(r, "make", "inst", "--argv", '["sh", "-c", "echo inst-ok"]', "--timeout-ms", "5000",
                            "--out", r + "/j.json")
        self.assertEqual(aos_exec(r + "/j.json", r).stdout, "inst-ok\n")
        code, res, err = ai(r, "make", "func", r + "/funcs/hello", "--summary", "打招呼", "--time-ms", "5")
        self.assertEqual(res["metainfo"], {"summary": "打招呼", "time_ms": 5}, err)
        self.assertIn("hello: hello from", aos_exec(r + "/funcs/hello", r).stdout)
        code, res, err = ai(r, "make", "daemon", "--loop", 'x={"exec": {"argv": ["true"]}, "max": 1}', "--max", "3",
                            "--interval-ms", "100", "--out", r + "/d/daemon.json")
        p = aos_exec(r + "/d/daemon.json", r, env={"AOS_STACK": r + "/dstack/"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads((Path(r) / "dstack" / "x" / "state.json").read_text())["phase"], "done")

    def test_make_metainfo_tool_json_and_bad(self):
        code, res, _ = ai(self.root, "make", "metainfo", "--summary", "s", "--time-ms", '{"val": 1, "max": 9}',
                          "--resource", "cpu,llm", "--side-effect", "false")
        self.assertEqual(res["json"], {"summary": "s", "time_ms": {"val": 1, "max": 9}, "side_effect": False,
                                       "resource": ["cpu", "llm"]})
        code, res, _ = ai(self.root, "make", "tool_json", "--description", "d", "--param", "expr:string:式子:required")
        self.assertEqual(res["json"]["parameters"]["required"], ["expr"])
        for args, want in ((["make", "metainfo", "--set", "priority=3"], "SpecBad"),
                           (["make", "fsm", "--cell", "a=x", "--next", "a=zz"], "SpecBad"),
                           (["make", "loop", "--max", "1"], "SpecBad"),
                           (["make", "tool_json", "--param", "x:str"], "SpecBad"),
                           (["make", "loop", "--exec", "x", "--out", "/tmp/aos-ai-outside.json"], "PathBad")):
            code, _, err = ai(self.root, *args)
            self.assertTrue(err.startswith("aos-ai: %s " % want), (args, err))
        ai(self.root, "make", "loop", "--exec", "x", "--out", self.root + "/l.json")
        code, _, err = ai(self.root, "make", "loop", "--exec", "y", "--out", self.root + "/l.json")
        self.assertTrue(err.startswith("aos-ai: FileExists "), err)
        code, res, _ = ai(self.root, "make", "loop", "--exec", "y", "--out", self.root + "/l.json", "--force")
        self.assertEqual(json.loads(Path(self.root, "l.json").read_text())["exec"], "y")

    def test_make_tool_and_cell_end_to_end(self):
        """生成一個工具＋一個 fsm 格掛進 agent-dan，腦（假 server）叫那個工具、新格每輪都跑。
        agent-dan 是舊協議（讀工作區的 new/）：題目手放 ws/new/（P-11 的 10-30 改口），aos-ai run 照樣從 history 拿答案。"""
        ai(self.root, "spawn", "dan", "--from", "agent-dan")
        code, res, err = ai(self.root, "make", "tool", "dan", "shout", "--description", "轉大寫",
                            "--param", "text:string:要轉的字:required", "--summary", "轉大寫", "--resource", "cpu")
        self.assertEqual(res["files"], ["_tooldef.json", "_entry", "_metainfo"], err)
        code, res, err = ai(self.root, "make", "cell", "dan", "log", "--after", "act",
                            "--exec", '{"argv": ["sh", "-c", "echo logged >> $AOS_STACK/log.txt"]}')
        self.assertTrue(res and res["ok"], err)
        fsm = json.loads((Path(self.root) / "agents/dan/agent/fsm.json").read_text())
        self.assertEqual((fsm["states"]["act"]["next"], fsm["states"]["log"]["next"]), ("log", "idle"))
        code, _, err = ai(self.root, "make", "cell", "dan", "log", "--exec", "x")
        self.assertTrue(err.startswith("aos-ai: CellExists "), err)
        brain = ToolBrain()
        try:
            new = Path(self.root) / "agents/dan/ws/new"
            new.mkdir(parents=True)
            (new / "q1.txt").write_text("喊一下\n")
            code, res, err = ai(self.root, "run", "dan", env={"AOS_BRAIN_URL": brain.url})
        finally:
            brain.server.shutdown()
            brain.server.server_close()
        self.assertTrue(res["ok"], (res, err))
        self.assertIn('tool said {"ok": true, "args": {"text": "hi"}}', res["answers"][0]["text"])  # 骨架照實回 args
        stack = Path(self.root) / "agents/dan/ws/.stack"
        self.assertEqual((stack / "log.txt").read_text(), "logged\nlogged\n")   # act 跑兩次（叫工具、交答案）
        self.assertTrue((stack / "shout").is_dir())                               # 工具有自己的小格

    def test_explain_concepts(self):
        code, res, _ = ai(self.root, "explain")
        for k in ("AOS_WS", "AOS_STACK", "AOS_ENTRY", "AOS_CF", "AOS_CD", "AOS_CO", "inst", "loop", "fsm", "daemon",
                  "window", "exit", "directive", "inline", "metainfo", "agent", "heap"):
            self.assertIn(k, res["concepts"])
        code, res, _ = ai(self.root, "explain", "ws")
        self.assertEqual(res["concept"], "AOS_WS")
        self.assertIn("出處", res["text"])
        code, _, err = ai(self.root, "explain", "nope")
        self.assertTrue(err.startswith("aos-ai: ConceptUnknown "), err)

    def test_explain_here_matches_aos_exec(self):
        """--here 算出來的六個值與種類，跟真的 aos-exec 給入口的一樣。"""
        r = Path(self.root)
        probe = "printenv | grep ^AOS_ | sort"
        (r / "p" / "_entry").mkdir(parents=True)
        (r / "p" / "_entry" / "run").write_text("#!/bin/sh\n" + probe + "\n")
        os.chmod(r / "p" / "_entry" / "run", 0o755)
        (r / "p" / "_entry" / ".env").write_text("AOS_ENTRY=run\n")
        (r / "j.json").write_text(json.dumps({"a": {"_entry": {"argv": ["sh", "-c", probe]}}}))
        (r / "k.json").write_text(json.dumps({"x": {".env": {"AOS_ENTRY": "go"}, "go": ["sh", "-c", probe]}}))
        (r / "ws").mkdir()
        for target, kind in (("p", "executable"), ("j.json#/a", "inst"), ("k.json#/x", "argv"), ("j", "bad")):
            p = aos_exec(str(r / target), str(r / "ws"))
            code, res, err = ai(self.root, "explain", "--here", str(r / target), "--ws", str(r / "ws"))
            self.assertEqual(res["entry"]["kind"], kind, (target, res))
            if kind == "bad":
                self.assertEqual(p.returncode, 1)
                continue
            real = dict(l.split("=", 1) for l in p.stdout.splitlines())
            for k in ("AOS_WS", "AOS_STACK", "AOS_CF", "AOS_CD", "AOS_CO"):
                self.assertEqual(res["env_at_start"][k], real[k], (target, k))
            if "AOS_ENTRY" in real:
                self.assertEqual(res["env_at_start"]["AOS_ENTRY"], real["AOS_ENTRY"])

    def test_dan_tools_make_and_explain(self):
        ai(self.root, "spawn", "boss", "--tool", "make_json", "--tool", "make_tool", "--tool", "explain_aos")
        tools = Path(self.root) / "agents" / "boss" / "agent" / "tools"
        e = {k: v for k, v in os.environ.items() if k not in CLEAR}
        e.update(AOS_WS=self.root, PATH=str(ROOT / "extras" / "ai_tools" / "bin") + os.pathsep + path_with(e["PATH"]))

        def call(tool, args):
            p = subprocess.run([str(tools / tool / "_entry")], input=json.dumps(args), capture_output=True, text=True, env=e)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)

        res = call("make_json", {"kind": "fsm", "spec": {"start": "a", "states": {"a": {"exec": "a", "next": "a"}}},
                                 "out": "gen/fsm.json"})
        self.assertTrue(res["ok"] and (Path(self.root) / "gen" / "fsm.json").is_file())
        p = subprocess.run([str(tools / "make_json" / "_entry")], input=json.dumps({"kind": "fsm", "spec": {"states": {}}}),
                           capture_output=True, text=True, env=e)
        self.assertEqual(p.returncode, 1)                                          # aos-ai 的錯照 lib 契約退 1
        self.assertTrue(p.stdout.startswith("make_json: SpecBad "), p.stdout)
        self.assertTrue(call("make_tool", {"name": "boss", "tool": "t1", "description": "d", "params": ["a:string"]})["ok"])
        self.assertTrue((tools / "t1" / "_tooldef.json").is_file())
        self.assertEqual(call("explain_aos", {"concept": "stack"})["concept"], "AOS_STACK")


if __name__ == "__main__":
    unittest.main()
