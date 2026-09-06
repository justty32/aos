# aos-mcp：同一支子行程走協定，再用自己的 daemon 跑一次真流程。
test_mcp() {
  local root report rc line kind words
  root=$(mktemp -d "$TEST_RUN_DIR/mcp.XXXXXX")
  report=$(python3 - "$HERE" "$root" <<'PYEOF2'
import http.server, json, os, subprocess, sys, threading, time

here, root = sys.argv[1:3]
daemon = os.path.join(root, "daemon")
dest = os.path.join(root, "play")
expected_llm = os.path.join(dest, "proto2", "examples", "llm")
env = dict(os.environ, AOS_DAEMON_DIR=daemon, AOS_LLM_DIR=expected_llm,
           PYTHONDONTWRITEBYTECODE="1")

class FakeLLM(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(size)
        body = json.dumps({
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                   "content": "測試成功"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2,
                      "total_tokens": 4},
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

fake = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeLLM)
threading.Thread(target=fake.serve_forever, daemon=True).start()
port = fake.server_address[1]
p = subprocess.Popen([sys.executable, os.path.join(here, "aos-mcp")],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, env=env)
checks = []
next_id = 0

def check(ok, text):
    checks.append((bool(ok), text))

def rpc(method, params=None, notification=False):
    global next_id
    req = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        req["params"] = params
    if not notification:
        next_id += 1
        req["id"] = next_id
    p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
    p.stdin.flush()
    if notification:
        return None
    line = p.stdout.readline()
    if not line:
        raise RuntimeError("MCP 沒回 JSON；stderr=" + p.stderr.read())
    return json.loads(line)

def tool(name, arguments=None):
    reply = rpc("tools/call", {"name": name, "arguments": arguments or {}})
    value = reply["result"]
    if value.get("isError"):
        raise RuntimeError(name + "：" + value["content"][0]["text"])
    return value["content"][0]["text"]

agent = llm = None
try:
    init = rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "1"}})
    check(init["result"]["protocolVersion"] == "2024-11-05"
          and init["result"]["capabilities"] == {"tools": {}},
          "mcp：initialize 回正確版本與 tools 能力")

    rpc("notifications/initialized", notification=True)
    pong = rpc("ping")
    check(pong.get("result") == {}, "mcp：notification 不回資料，ping 還接得上")

    listed = rpc("tools/list")["result"]["tools"]
    names = {x["name"] for x in listed}
    wanted = {"kernel_status", "kernel_start", "kernel_stop", "clock_register",
              "clock_unregister", "clock_pause", "clock_continue", "agent_say",
              "agent_listen", "agent_status", "agent_spawn", "agent_inbox_drop",
              "llm_usage", "llm_queue", "world_setup"}
    check(names == wanted, "mcp：tools/list 列出 15 個工具")

    made = json.loads(tool("world_setup", {"dest": dest, "engine": "local"}))
    agent, llm = made["agent"], made["llm"]
    with open(os.path.join(llm, "engines.json"), encoding="utf-8") as f:
        engines = json.load(f)
    engines[0]["base_url"] = "http://127.0.0.1:%s/v1" % port
    engines[0]["model"] = "m"
    with open(os.path.join(llm, "engines.json"), "w", encoding="utf-8") as f:
        json.dump(engines, f, ensure_ascii=False, indent=2)
    check(all(os.path.isabs(made[k]) for k in ("dest", "agent", "llm"))
          and os.path.isfile(os.path.join(agent, ".aos", "inst"))
          and json.load(open(os.path.join(llm, "defaults.json"), encoding="utf-8"))["engine"] == "local",
          "mcp：world_setup 從 git 複製範例、回絕對路徑並指定引擎")

    tool("kernel_start")
    status = json.loads(tool("kernel_status"))
    check(status["kernel"].get("pid"), "mcp：自己的 kernel 能啟動並查狀態")

    tool("clock_register", {"world": llm, "interval": 0.05})
    tool("clock_register", {"world": agent, "interval": 0.05})
    clocks = json.loads(tool("kernel_status"))["clocks"]
    check({x["dir"] for x in clocks} == {agent, llm}, "mcp：兩個世界都能 register")

    tool("agent_say", {"world": agent, "text": "請回一句測試成功"})
    heard = tool("agent_listen", {"world": agent, "timeout_s": 15})
    check("reply" in heard or "agent>" in heard, "mcp：say 後能從假 server 等到 listen")

    ast = json.loads(tool("agent_status", {"world": agent}))
    check(ast.get("step", 0) > 0 and ast.get("busy", 0) > 0,
          "mcp：agent_status 看得到已走過的格數")

    started = time.monotonic()
    quiet = tool("agent_listen", {"world": os.path.join(root, "quiet"), "timeout_s": 0.2})
    check("沒有新回覆" in quiet and time.monotonic() - started < 2,
          "mcp：listen 超時會回來，不會無限等")

    missing = rpc("no/such/method")
    check(missing.get("error", {}).get("code") == -32601,
          "mcp：不認得的方法回 method not found")
finally:
    if p.poll() is None:
        for world in (agent, llm):
            if world:
                try:
                    tool("clock_unregister", {"world": world})
                except Exception:
                    pass
        try:
            tool("kernel_stop")
            check(True, "mcp：測試自己的 kernel 能停止")
        except Exception:
            check(False, "mcp：測試自己的 kernel 沒停乾淨")
        p.stdin.close()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.terminate()
            p.wait(timeout=3)
    fake.shutdown()
    fake.server_close()

for good, text in checks:
    print(("OK" if good else "FAIL") + "\t" + text)
if not checks or not all(good for good, _ in checks):
    sys.exit(1)
PYEOF2
  )
  rc=$?
  while IFS=$'\t' read -r kind words; do
    [ -z "$kind" ] && continue
    if [ "$kind" = "OK" ]; then ok "$words"; else fail "$words"; fi
  done <<< "$report"
  if [ "$rc" != 0 ] && [ -z "$report" ]; then
    fail "mcp：整合測試中途退出（退出碼 $rc）"
  fi
  rm -rf "$root"
}

test_mcp
