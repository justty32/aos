#!/usr/bin/env python3
"""test_tool.py：腦用的兩個工具（tools/json、tools/json_edit）的測試（ctest 會跑）。只用標準庫。

    python3 tests/test_tool.py bin/aos-json

照 agent-dan 的 act.py 叫工具的方式跑：`aos-exec tools/<名>`、arguments 從 stdin 進、AOS_WS＝工作區。
要 ../aos-exec/bin/aos-exec 已經建好（沒建＝印一行說跳過、退 0）。json_edit 的腦是測試自己起的假 OpenAI 端點（照腳本回）。
"""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "bin", "aos-json"))
EXEC = os.path.join(ROOT, "..", "aos-exec", "bin", "aos-exec")
if not os.path.exists(EXEC):
    print("test_tool：跳過（%s 還沒建）" % EXEC)
    sys.exit(0)
PATH = os.pathsep.join([os.path.dirname(BIN), os.path.dirname(os.path.abspath(EXEC)), os.environ.get("PATH", "")])
failures = 0
count = 0


def check(name, got, want):
    global failures, count
    count += 1
    if got != want:
        failures += 1
        print("失敗 %s：\n  得到 %r\n  應該 %r" % (name, got, want))


# ---- 假腦：照腳本一則一則回，收到的請求記下來 ----
class Brain(http.server.BaseHTTPRequestHandler):
    script = []
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Brain.seen.append(body)
        reply = Brain.script.pop(0) if Brain.script else {"content": "沒腳本了"}
        data = json.dumps({"choices": [{"message": dict({"role": "assistant"}, **reply)}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Brain)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/v1" % server.server_address[1]


def call(name, args):
    return {"tool_calls": [{"id": "c%d" % len(Brain.seen), "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)}}]}


FSM = {"start": "idle", "states": {"idle": {"exec": "idle", "next": "think"},
                                   "think": {"exec": {"argv": ["python3", "brain.py"], "timeout_ms": 120000},
                                             "next": "act"}}}


def run(tool, args, files=None, url=URL, script=None):
    """在新工作區跑一次工具，回 (退出碼, stdout, stderr, 工作區裡 fsm.json 的值)。"""
    Brain.script, Brain.seen = list(script or []), []
    with tempfile.TemporaryDirectory() as ws, tempfile.TemporaryDirectory() as stack:
        for name, doc in (files or {"fsm.json": FSM}).items():
            with open(os.path.join(ws, name), "w") as f:
                f.write(json.dumps(doc, indent=2) if not isinstance(doc, str) else doc)
        env = dict(os.environ, PATH=PATH, AOS_WS=ws, AOS_STACK=stack + "/")
        env.pop("AOS_BRAIN_URL", None)
        if url:
            env["AOS_BRAIN_URL"] = url
        r = subprocess.run([EXEC, os.path.join(ROOT, "tools", tool)], input=args if isinstance(args, str) else json.dumps(args),
                           capture_output=True, text=True, env=env)
        try:
            with open(os.path.join(ws, "fsm.json")) as f:
                doc = json.load(f)
        except (OSError, ValueError):
            doc = None
        return r.returncode, r.stdout, r.stderr, doc


# ---- tools/json ----
rc, out, err, _ = run("json", {"cmd": "peek", "target": "fsm.json"})
check("json peek 頂層", (rc, out), (0, 'fsm.json {2} start, states\n  start: "idle"\n  states: {2} idle, think\n'))
rc, out, err, _ = run("json", {"cmd": "peek", "target": "fsm.json#/states/think", "depth": 2})
check("json peek 深一點", "timeout_ms: 120000" in out, True)
rc, out, err, doc = run("json", {"cmd": "set", "target": "fsm.json#/states/think/exec/timeout_ms", "value": 30000})
check("json set 單值", (rc, out, doc["states"]["think"]["exec"]["timeout_ms"]), (0, "ok\n", 30000))
rc, out, err, doc = run("json", {"cmd": "set", "target": "fsm.json#/states/act", "value": {"exec": "act", "next": "idle"}})
check("json set 整棵子樹", doc["states"]["act"], {"exec": "act", "next": "idle"})
rc, out, err, doc = run("json", {"cmd": "batch", "target": "fsm.json",
                                 "value": {"/start": "think", "/states/idle/next": "idle"}})
check("json batch", (doc["start"], doc["states"]["idle"]["next"]), ("think", "idle"))
rc, out, err, doc = run("json", {"cmd": "set", "target": "fsm.json#/states/think/exec", "value": []})
check("json set 形狀不對＝錯給腦看、不寫", (rc, out.startswith("錯：CheckFailed"), doc["states"]["think"]["exec"]["timeout_ms"]),
      (0, True, 120000))
rc, out, err, _ = run("json", {"cmd": "get", "target": "fsm.json#/nope"})
check("json 指不到＝錯給腦看", (rc, out.startswith("錯：PointerMissing")), (0, True))
rc, out, err, _ = run("json", {"cmd": "get", "target": "/etc/passwd"})
check("json 絕對路徑不收", (rc, out.startswith("錯：")), (0, True))
rc, out, err, _ = run("json", {"cmd": "get", "target": "../x.json"})
check("json .. 不收", (rc, out.startswith("錯：")), (0, True))
rc, out, err, _ = run("json", {"cmd": "set", "target": "fsm.json#/a"})
check("json set 沒 value", out.startswith("錯："), True)
rc, out, err, _ = run("json", "not json")
check("json stdin 壞＝自己的錯", (rc, err.startswith("json: ArgumentsBad")), (1, True))
rc, out, err, _ = run("json", {"cmd": "rm", "target": "fsm.json"})
check("json 不認得的 cmd", rc, 1)
rc, out, err, _ = run("json", {"cmd": "check", "target": "fsm.json"}, files={"fsm.json": {"exec": ""}})
check("json check 有問題", (rc, out.startswith("有問題：")), (0, True))

# ---- tools/json_edit：找到要修改的 key → 提供值 ----
want = {"file": "fsm.json", "want": "把 think 那格的逾時改成 30 秒"}
script = [call("peek", {"pointer": "/states"}),
          call("peek", {"pointer": "/states/think/exec"}),
          call("found", {"pointers": ["/states/think/exec/timeout_ms"]}),
          call("give", {"json": "30000"})]
rc, out, err, doc = run("json_edit", want, script=script)
check("json_edit 改好", (rc, doc["states"]["think"]["exec"]["timeout_ms"]), (0, 30000))
check("json_edit 印走過的路", out, "看過：/ → /states → /states/think/exec\n找到：/states/think/exec/timeout_ms\n"
                                  "改：fsm.json#/states/think/exec/timeout_ms = 30000\n")
first = Brain.seen[0]["messages"][1]["content"] if Brain.seen else ""
check("第一次只給頂層（摺起來、看不到 timeout_ms）", ("states: {2} idle, think" in first, "timeout_ms" in first), (True, False))
check("第二次帶 peek 結果", Brain.seen[1]["messages"][-1]["content"] if len(Brain.seen) > 1 else None,
      "fsm.json#/states {2} idle, think\n  idle: {2} exec, next\n  think: {2} exec, next\n")
give = Brain.seen[3]["messages"] if len(Brain.seen) > 3 else []
check("提供值那一步是新的對話、只看那一處", (len(give), "120000" in give[1]["content"] if give else None,
                                   "found" in json.dumps(give)), (2, True, False))
check("提供值只給 give", [t["function"]["name"] for t in Brain.seen[3]["tools"]] if len(Brain.seen) > 3 else None, ["give"])

rc, out, err, doc = run("json_edit", want, script=script[:3] + [call("give", {"json": "30 秒"}), call("give", {"json": "30000"})])
check("json_edit 值解不開＝讓腦重給", (rc, doc["states"]["think"]["exec"]["timeout_ms"]), (0, 30000))
check("  重給時有說錯在哪", "不是 JSON" in json.dumps(Brain.seen[4]["messages"], ensure_ascii=False) if len(Brain.seen) > 4 else None, True)

rc, out, err, doc = run("json_edit", want, script=[call("found", {"pointers": ["/states/think/exec"]}), call("give", {"json": "\"\""})])
check("json_edit 形狀不對＝沒改、退 0", (rc, "沒改：CheckFailed" in out, doc["states"]["think"]["exec"]["timeout_ms"]), (0, True, 120000))

rc, out, err, doc = run("json_edit", want, script=[call("found", {"pointers": ["/states/think/exec/grace_ms"]}),
                                                   call("give", {"json": "500"})])
check("json_edit 新加 key", doc["states"]["think"]["exec"].get("grace_ms"), 500)
check("  新 key 告訴腦還沒有", "還沒有這個位置" in Brain.seen[1]["messages"][1]["content"] if len(Brain.seen) > 1 else None, True)

os.environ["AOS_JSON_EDIT_MAX_ROUNDS"] = "2"
rc, out, err, _ = run("json_edit", want, script=[{"content": "我想想"}, call("peek", {"pointer": "/states"})])
check("json_edit 幾輪都沒交＝PointerMissing", (rc, err.startswith("json_edit: PointerMissing")), (1, True))
del os.environ["AOS_JSON_EDIT_MAX_ROUNDS"]
rc, out, err, _ = run("json_edit", want, url=None)
check("json_edit 沒設腦＝BrainMissing", (rc, err.startswith("json_edit: BrainMissing")), (1, True))
rc, out, err, _ = run("json_edit", want, url="http://127.0.0.1:1/v1")
check("json_edit 腦連不上＝BrainFailed", (rc, err.startswith("json_edit: BrainFailed")), (1, True))
rc, out, err, _ = run("json_edit", {"file": "fsm.json"})
check("json_edit stdin 少 want", (rc, err.startswith("json_edit: ArgumentsBad")), (1, True))
rc, out, err, _ = run("json_edit", {"file": "/etc/x.json", "want": "a"})
check("json_edit 絕對路徑＝沒改", (rc, out.startswith("沒改：")), (0, True))
rc, out, err, _ = run("json_edit", {"file": "nope.json", "want": "a"})
check("json_edit 檔不在＝沒改", (rc, out.startswith("沒改：FileMissing")), (0, True))

server.shutdown()
print("aos-json test_tool：%d 個，失敗 %d" % (count, failures))
sys.exit(1 if failures else 0)
