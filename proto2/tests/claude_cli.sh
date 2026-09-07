# claude-cli：把 Claude Code 的 headless（`claude -p`）當成一台引擎——給有訂閱、沒 API key 的人用。
# 測試不碰真的 CLI，也不碰網路：擺一支**假的 claude**（把 argv、stdin、cwd 與 --mcp-config
# 指到的那份工具清單原樣記下來，印一段罐頭的 stream-json），引擎用 "bin" 指過去。要驗四件事：
# 指令列的旗標對不對（工具走 MCP、不再有 --json-schema）、掛上去的工具清單對不對、
# stdin 那段對話長得對不對、回來的有沒有翻成 OpenAI 的形狀。
# 另外單獨測一次 aos-mcp-tools 本人（拿 JSON-RPC 餵它，看 tools/list 與登記簿）。

cli_assert() {  # cli_assert <python 印出的 True/False> <名字>
  if [ "$1" = "True" ]; then ok "$2"; else fail "$2（$1）"; fi
}

cli_fake_bin() {  # cli_fake_bin <記錄資料夾> <退出碼>；印出假 claude 的路徑
  local rec=$1 code=$2 bin="$1/claude-$2"
  cat > "$bin" <<PYEOF2
#!/usr/bin/env python3
import json, os, sys
rec = "$rec"
code = $code
PYEOF2
  cat >> "$bin" <<'PYEOF2'
argv = sys.argv[1:]


def after(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


# --mcp-config 指到的那份工具清單，跑完就會被掃掉——先抄一份進記錄裡好驗。
specs = None
try:
    conf = json.loads(after("--mcp-config") or "{}")
    with open(conf["mcpServers"]["aos"]["args"][1], encoding="utf-8") as f:
        specs = json.load(f)
except (ValueError, KeyError, IndexError, OSError, TypeError):
    pass
seq = len([x for x in os.listdir(rec) if x.startswith("run-")]) + 1
with open(os.path.join(rec, "run-%02d.json" % seq), "w", encoding="utf-8") as f:
    json.dump({"argv": argv, "stdin": sys.stdin.read(), "cwd": os.getcwd(),
               "specs": specs}, f, ensure_ascii=False)
if code:
    sys.stderr.write("假 claude 故意壞掉：credit balance too low\n")
    sys.exit(code)
for line in [
    {"type": "system", "subtype": "init", "session_id": "sess-42",
     "tools": ["mcp__aos__say"],
     "mcp_servers": [{"name": "aos", "status": "connected"}]},
    # 真的 CLI 會把**一則**訊息拆成好幾個 assistant 事件（一個 block 一個），
    # 而且 thinking 也算一包——要照 message.id 收齊、把 thinking 丟掉。
    {"type": "assistant", "session_id": "sess-42", "message": {
        "id": "msg_1", "role": "assistant", "content": [
            {"type": "thinking", "thinking": "", "signature": "xx"}]}},
    {"type": "assistant", "session_id": "sess-42", "message": {
        "id": "msg_1", "role": "assistant", "content": [
            {"type": "text", "text": "我來叫工具"},
            {"type": "tool_use", "id": "toolu_9", "name": "mcp__aos__say",
             "input": {"text": "嗨"}}]}},
    # 第二則訊息（真的跑起來不會有，--max-turns 1 擋掉了）不該被收進來
    {"type": "assistant", "session_id": "sess-42", "message": {
        "id": "msg_2", "role": "assistant", "content": [
            {"type": "text", "text": "不該出現的第二則"}]}},
    {"type": "user", "session_id": "sess-42", "message": {
        "role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_9",
             "content": "已登記 say。這一輪到此為止"}]}},
    # 撞到 --max-turns 1 是**正常收工**：is_error 會是 true，但那一輪已經拿到了。
    {"type": "result", "subtype": "error_max_turns", "is_error": True,
     "session_id": "sess-42", "total_cost_usd": 0.0112, "num_turns": 1,
     "duration_ms": 900, "result": "",
     "usage": {"input_tokens": 11, "output_tokens": 7,
               "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0}},
]:
    print(json.dumps(line, ensure_ascii=False))
PYEOF2
  chmod +x "$bin"
  printf '%s\n' "$bin"
}

test_claude_cli() {
  local tmp rec llm bin badbin got day
  tmp=$(mktemp -d); rec="$tmp/rec"; llm="$tmp/llm"
  mkdir -p "$rec"
  bin=$(cli_fake_bin "$rec" 0)
  badbin=$(cli_fake_bin "$rec" 1)
  mk_engines "$llm" "[{\"name\": \"cheap\", \"api\": \"claude-cli\", \"bin\": \"$bin\",
    \"model\": \"haiku\", \"max_concurrent\": 2, \"params\": {\"effort\": \"low\"}},
   {\"name\": \"boom\", \"api\": \"claude-cli\", \"bin\": \"$badbin\", \"model\": \"sonnet\"},
   {\"name\": \"gone\", \"api\": \"claude-cli\", \"bin\": \"沒有這支執行檔\", \"model\": \"haiku\"}]"

  cat > "$llm/requests/0001.json" <<'PYEOF2'
{"requester": "team/one", "engine": "cheap",
 "messages": [
   {"role": "system", "content": "你是甲"},
   {"role": "user", "content": "算 3 加 4"},
   {"role": "assistant", "content": "我算一下",
    "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "add", "arguments": "{\"a\": 3, \"b\": 4}"}}]},
   {"role": "tool", "tool_call_id": "call_1", "content": "7"},
   {"role": "user", "content": "再說一句"}],
 "tools": [{"type": "function",
            "function": {"name": "say", "description": "說一句",
                         "parameters": {"type": "object",
                                        "properties": {"text": {"type": "string"}}}}}]}
PYEOF2
  llm_pump "$llm" >/dev/null

  # (a) 指令列：stream-json＋--verbose、--max-turns 1、MCP 那三個旗標，cwd 是 LLM 資料夾。
  got=$(python3 - "$rec/run-01.json" "$llm" <<'PYEOF2'
import json, os, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
a = r["argv"]


def after(flag):
    return a[a.index(flag) + 1] if flag in a else None


conf = json.loads(after("--mcp-config") or "{}")
server = conf.get("mcpServers", {}).get("aos", {})
print(a[0] == "-p" and "--no-session-persistence" in a
      # --safe-mode 會把 MCP 一起關掉，--bare 會把 OAuth 踢掉，兩支都不能出現
      and "--safe-mode" not in a and "--bare" not in a
      and after("--setting-sources") == "" and "--disable-slash-commands" in a
      and "--json-schema" not in a          # 舊那一套已經拆掉
      and after("--output-format") == "stream-json" and "--verbose" in a
      and after("--tools") == "" and after("--model") == "haiku"
      and after("--effort") == "low"
      and after("--allowedTools") == "mcp__aos__*"
      and after("--max-turns") == "1"
      and "--strict-mcp-config" in a
      and list(conf.get("mcpServers") or {}) == ["aos"]
      and os.path.basename(server.get("command") or "").startswith("python3")
      and os.path.basename(server.get("args", ["", ""])[0]) == "aos-mcp-tools"
      and os.path.isfile(server["args"][0])
      and server.get("env", {}).get("AOS_MCP_RECORD", "").endswith(".calls.jsonl")
      and os.path.realpath(r["cwd"]) == os.path.realpath(sys.argv[2]))
PYEOF2
)
  cli_assert "$got" "claude-cli：旗標走 MCP＋stream-json＋max-turns 1，--json-schema 沒了，cwd 對"

  # (b) 掛上去的工具清單：請求裡的 tools 原樣落在 specs 檔，parameters 翻得成 inputSchema。
  got=$(python3 - "$rec/run-01.json" "$llm" <<'PYEOF2'
import json, os, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
specs = r["specs"]
one = specs[0] if specs else {}
print(len(specs) == 1 and one["name"] == "say" and one["description"] == "說一句"
      and one["parameters"] == {"type": "object",
                                "properties": {"text": {"type": "string"}}}
      # 跑完就掃掉，不會在 side/cli 底下越堆越多
      and not [x for x in os.listdir(os.path.join(sys.argv[2], "side", "cli"))])
PYEOF2
)
  cli_assert "$got" "claude-cli：工具清單寫進 specs 檔給 MCP 掛，跑完順手掃掉"

  # (c) --system-prompt：只有請求的 system ＋ 一條規矩，**不再有文字版工具清單**。
  got=$(python3 - "$rec/run-01.json" <<'PYEOF2'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))["argv"]
sysp = a[a.index("--system-prompt") + 1]
print(sysp.startswith("你是甲")
      and "要叫工具就用工具，不要用文字描述" in sysp
      and "content 是給人看的話" in sysp
      and "你可以叫的工具" not in sysp and "say(" not in sysp
      and "json-schema" not in sysp)
PYEOF2
)
  cli_assert "$got" "claude-cli：--system-prompt 只剩 system 話＋規矩，工具清單不再用講的"

  # (d) stdin 那段對話：一則一段，assistant 的工具呼叫用 → 印，最後留空的【assistant】。
  got=$(python3 - "$rec/run-01.json" <<'PYEOF2'
import json, sys
text = json.load(open(sys.argv[1], encoding="utf-8"))["stdin"]
blocks = text.split("\n\n")
print(blocks == ["【user】算 3 加 4",
                 "【assistant】我算一下\n→ add {\"a\": 3, \"b\": 4}",
                 "【tool:add】7",
                 "【user】再說一句",
                 "【assistant】"]
      and "你是甲" not in text)
PYEOF2
)
  cli_assert "$got" "claude-cli：stdin 是渲染好的對話，system 不在裡面，結尾留【assistant】"

  # (e) 回來的翻成 OpenAI 形狀：tool_use → tool_calls（前綴剝掉）、usage 折好、花費記在 aos.cli。
  got=$(python3 - "$llm/results/0001.json" <<'PYEOF2'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["choices"][0]["message"]
u = d["usage"]
print(m["tool_calls"][0]["function"]["name"] == "say"
      and m["tool_calls"][0]["id"] == "toolu_9"
      and json.loads(m["tool_calls"][0]["function"]["arguments"]) == {"text": "嗨"}
      and m["content"] == "我來叫工具"        # thinking 丟掉、第二則訊息不收
      and len(m["tool_calls"]) == 1
      and d["choices"][0]["finish_reason"] == "tool_calls"
      and u["prompt_tokens"] == 14 and u["completion_tokens"] == 7
      and u["total_tokens"] == 21
      and u["prompt_tokens_details"]["cached_tokens"] == 3
      and d["aos"]["cli"]["session_id"] == "sess-42"
      and d["aos"]["cli"]["total_cost_usd"] == 0.0112
      and d["aos"]["cli"]["num_turns"] == 1
      and "cli" not in d)
PYEOF2
)
  cli_assert "$got" "claude-cli：tool_use 翻成 OpenAI 的 tool_calls，usage 折好、花費記在 aos.cli"

  day=$(date +%F)
  got=$(python3 - "$llm/usage/$day.json" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
row = book["by-model"]["|haiku"]
print(row["total_tokens"] == 21 and row["requests"] == 1 and row["errors"] == 0)
PYEOF2
)
  cli_assert "$got" "claude-cli：用量一樣進帳本（沒有 base_url，key 就是 |模型）"

  # (f) CLI 掛掉：退出碼非 0、一句 assistant 都沒有 → 一句 error，帳本記 errors。
  echo '{"engine": "boom", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0002.json"
  # (g) 找不到執行檔：不等逾時，當場講清楚。
  echo '{"engine": "gone", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0003.json"
  llm_pump "$llm" >/dev/null
  got=$(python3 - "$llm/results/0002.json" "$llm/results/0003.json" <<'PYEOF2'
import json, sys
bad = json.load(open(sys.argv[1], encoding="utf-8")).get("error") or ""
gone = json.load(open(sys.argv[2], encoding="utf-8")).get("error") or ""
print(bad.startswith("claude-cli 失敗（exit 1）") and "credit balance too low" in bad
      and "找不到 claude 執行檔" in gone and "沒有這支執行檔" in gone)
PYEOF2
)
  cli_assert "$got" "claude-cli：跑掛了與找不到執行檔都變成看得懂的一句 error"
  got=$(python3 - "$llm/usage/$day.json" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
print(sum(row.get("errors", 0) for row in book["by-model"].values()) == 2)
PYEOF2
)
  cli_assert "$got" "claude-cli：兩發失敗都記進帳本的 errors"

  kill_workers "$llm"
  rm -rf "$tmp"
}

test_mcp_tools() {
  # aos-mcp-tools 自己：拿 JSON-RPC 一行一包餵進去，看它報得出工具、把呼叫記下來、
  # 不認得的通知吞掉、不認得的請求回 -32601。
  local tmp got
  tmp=$(mktemp -d)
  cat > "$tmp/specs.json" <<'PYEOF2'
[{"name": "say", "description": "說一句",
  "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                 "required": ["text"]}},
 {"name": "order_status", "description": "查訂單",
  "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}}}]
PYEOF2
  printf '%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' \
    '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
    '{"jsonrpc":"2.0","method":"notifications/沒聽過"}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"say","arguments":{"text":"hi"}}}' \
    '{"jsonrpc":"2.0","id":4,"method":"ping"}' \
    '{"jsonrpc":"2.0","id":5,"method":"沒這招"}' \
    | AOS_MCP_RECORD="$tmp/rec.jsonl" "$HERE/aos-mcp-tools" "$tmp/specs.json" > "$tmp/out.jsonl"

  got=$(python3 - "$tmp/out.jsonl" "$tmp/rec.jsonl" <<'PYEOF2'
import json, sys
rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
by_id = {r.get("id"): r for r in rows}
tools = by_id[2]["result"]["tools"]
rec = [json.loads(x) for x in open(sys.argv[2], encoding="utf-8") if x.strip()]
print(len(rows) == 5                       # 兩則通知不回話
      and by_id[1]["result"]["protocolVersion"] == "2024-11-05"
      and by_id[1]["result"]["serverInfo"]["name"] == "aos"
      and [t["name"] for t in tools] == ["say", "order_status"]
      and tools[0]["inputSchema"]["required"] == ["text"]   # parameters → inputSchema
      and "inputSchema" in tools[1] and "parameters" not in tools[1]
      and "已登記 say" in by_id[3]["result"]["content"][0]["text"]
      and "不要再叫工具" in by_id[3]["result"]["content"][0]["text"]
      and by_id[4]["result"] == {}
      and by_id[5]["error"]["code"] == -32601
      and rec == [{"name": "say", "arguments": {"text": "hi"}}])
PYEOF2
)
  cli_assert "$got" "aos-mcp-tools：tools/list 報得出工具、tools/call 只登記不執行"
  rm -rf "$tmp"
}

test_claude_cli
test_mcp_tools
