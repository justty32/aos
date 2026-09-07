# codex-cli：把 OpenAI Codex CLI 的 headless（`codex exec`）當成一台引擎——給有 ChatGPT
# 訂閱、沒有 API key 的人用。跟 claude-cli 不一樣的地方是工具：codex 是個 agent，工具得
# **真的掛上去**它才會發出真的工具呼叫，所以我們把請求裡的 tools 寫成 specs.json、用 -c 把
# aos-mcp-tools 掛成一台 MCP server；那台什麼都不做，只把被叫到的工具登記進一個檔。
#
# 測試不碰真的 codex，也不碰網路：擺一支**假的 codex**（把 argv／stdin／cwd 原樣記下來，
# 自己往登記檔 append 一行，再印一段罐頭 JSONL），引擎用 "bin" 指過去。要驗的是：
# 指令列那一串旗標與三個 mcp_servers 覆寫、stdin 那段 prompt、事件流有沒有翻成 OpenAI 形狀、
# 一直不收工的會不會被我們收掉、turn.failed 與找不到執行檔會不會變成看得懂的一句 error，
# 外加 aos-mcp-tools 自己單獨用 JSON-RPC 餵一遍。

cx_assert() {  # cx_assert <python 印出的 True/False> <名字>
  if [ "$1" = "True" ]; then ok "$2"; else fail "$2（$1）"; fi
}

cx_fake_bin() {  # cx_fake_bin <記錄資料夾> <ok|fail|forever>；印出假 codex 的路徑
  local rec=$1 mode=$2 bin="$1/codex-$2"
  cat > "$bin" <<PYEOF2
#!/usr/bin/env python3
import json, os, re, sys, time
rec = "$rec"
mode = "$mode"
PYEOF2
  cat >> "$bin" <<'PYEOF2'
argv = sys.argv[1:]
blob = " ".join(argv)
hit = re.search(r'AOS_MCP_RECORD="([^"]+)"', blob)
record = hit.group(1) if hit else ""
specs = ""
for one in argv:
    if one.startswith("mcp_servers.aos.args="):
        try:
            specs = json.loads(one.split("=", 1)[1])[1]
        except (ValueError, IndexError):
            specs = ""
seen = None
if specs:
    try:
        seen = json.load(open(specs, encoding="utf-8"))
    except (OSError, ValueError):
        seen = None
seq = len([x for x in os.listdir(rec) if x.startswith("run-")]) + 1
with open(os.path.join(rec, "run-%02d.json" % seq), "w", encoding="utf-8") as f:
    json.dump({"argv": argv, "stdin": sys.stdin.read(), "cwd": os.getcwd(),
               "specs": seen}, f, ensure_ascii=False)


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


emit({"type": "thread.started", "thread_id": "th-77"})
emit({"type": "turn.started"})
if mode == "fail":
    emit({"type": "turn.failed",
          "error": {"message": "usage limit reached，等下一個五小時窗口"}})
    sys.exit(0)
# 模型「真的叫了 MCP 工具」＝ MCP server 往登記檔 append 一行。這裡代它寫。
if record:
    with open(record, "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": "say", "arguments": {"text": "嗨"}},
                           ensure_ascii=False) + "\n")
emit({"type": "item.completed",
      "item": {"id": "it-1", "type": "mcp_tool_call", "server": "aos", "tool": "say",
               "arguments": "{\"text\": \"嗨\"}", "status": "completed"}})
emit({"type": "item.completed",
      "item": {"id": "it-2", "type": "agent_message", "text": "我來叫工具"}})
if mode == "forever":
    # 不收工的那種：一直吐東西，看外面會不會照規矩把我收掉。
    while True:
        emit({"type": "item.completed",
              "item": {"id": "it-x", "type": "agent_message", "text": "還在講"}})
        time.sleep(0.3)
emit({"type": "turn.completed",
      "usage": {"input_tokens": 1300, "cached_input_tokens": 1100,
                "cache_write_input_tokens": 0, "output_tokens": 9,
                "reasoning_output_tokens": 5}})
PYEOF2
  chmod +x "$bin"
  printf '%s\n' "$bin"
}

test_codex_cli() {
  local tmp rec llm bin failbin foreverbin got day specs
  tmp=$(mktemp -d); rec="$tmp/rec"; llm="$tmp/llm"
  mkdir -p "$rec"
  bin=$(cx_fake_bin "$rec" ok)
  failbin=$(cx_fake_bin "$rec" fail)
  foreverbin=$(cx_fake_bin "$rec" forever)
  mk_engines "$llm" "[{\"name\": \"cheap\", \"api\": \"codex-cli\", \"bin\": \"$bin\",
    \"model\": \"gpt-5.6-luna\", \"max_concurrent\": 2, \"params\": {\"effort\": \"low\"}},
   {\"name\": \"boom\", \"api\": \"codex-cli\", \"bin\": \"$failbin\", \"model\": \"gpt-5.6-luna\"},
   {\"name\": \"slow\", \"api\": \"codex-cli\", \"bin\": \"$foreverbin\", \"model\": \"gpt-5.6-luna\",
    \"grace\": 0.5},
   {\"name\": \"gone\", \"api\": \"codex-cli\", \"bin\": \"沒有這支執行檔\", \"model\": \"gpt-5.6-luna\"}]"

  cat > "$llm/requests/0001.json" <<'PYEOF2'
{"requester": "team/one", "engine": "cheap",
 "messages": [
   {"role": "system", "content": "你是甲"},
   {"role": "user", "content": "算 3 加 4"},
   {"role": "assistant", "content": "我算一下",
    "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "add", "arguments": "{\"a\": 3, \"b\": 4}"}}]},
   {"role": "tool", "tool_call_id": "call_1", "content": "7"},
   {"role": "user", "content": "請叫 say 說 hi"}],
 "tools": [{"type": "function",
            "function": {"name": "say", "description": "說一句",
                         "parameters": {"type": "object",
                                        "properties": {"text": {"type": "string"}},
                                        "required": ["text"]}}},
           {"type": "function",
            "function": {"name": "order_status", "description": "查訂單",
                         "parameters": {"type": "object",
                                        "properties": {"order_id": {"type": "string"}}}}}]}
PYEOF2
  llm_pump "$llm" >/dev/null

  # (a) 指令列：旗標、模型、-C 是 LLM 資料夾、effort、mcp_servers 那幾個覆寫都解得開。
  got=$(python3 - "$rec/run-01.json" "$llm" "$HERE" <<'PYEOF2'
import json, os, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
a = r["argv"]


def after(flag):
    return a[a.index(flag) + 1] if flag in a else None


def override(prefix):
    for one in a:
        if one.startswith(prefix):
            return one.split("=", 1)[1]
    return None


cmd = json.loads(override("mcp_servers.aos.command=") or "null")
args = json.loads(override("mcp_servers.aos.args=") or "null")
env = override("mcp_servers.aos.env=") or ""
print(a[0] == "exec" and "--ephemeral" in a and "--skip-git-repo-check" in a
      and "--json" in a and after("-s") == "read-only"
      and after("-m") == "gpt-5.6-luna"
      and os.path.realpath(after("-C") or "") == os.path.realpath(sys.argv[2])
      and 'model_reasoning_effort="low"' in a
      and os.path.basename(cmd or "").startswith("python")
      and isinstance(args, list) and len(args) == 2
      and os.path.realpath(args[0]) == os.path.realpath(
          os.path.join(sys.argv[3], "aos-mcp-tools"))
      and args[1].endswith(".specs.json")
      and env.startswith("{AOS_MCP_RECORD=\"") and env.endswith(".record.jsonl\"}")
      and 'mcp_servers.aos.default_tools_approval_mode="auto"' in a)
PYEOF2
)
  cx_assert "$got" "codex-cli：指令列旗標、模型、-C、effort 與三個 mcp_servers 覆寫都對"

  # (b) 給 MCP server 的工具清單：OpenAI 的 tools 原樣搬過去（parameters 不改名，
  #     改名成 inputSchema 是 aos-mcp-tools tools/list 時才做的事）。
  got=$(python3 - "$rec/run-01.json" <<'PYEOF2'
import json, sys
specs = json.load(open(sys.argv[1], encoding="utf-8"))["specs"]
print(isinstance(specs, list) and [s["name"] for s in specs] == ["say", "order_status"]
      and specs[0]["description"] == "說一句"
      and specs[0]["parameters"]["required"] == ["text"])
PYEOF2
)
  cx_assert "$got" "codex-cli：請求裡的 tools 變成一份 specs.json 交給 MCP server"

  # (c) stdin：【系統】那一塊有 system 話與「工具要真的叫」的規矩，後面接渲染好的對話。
  got=$(python3 - "$rec/run-01.json" <<'PYEOF2'
import json, sys
text = json.load(open(sys.argv[1], encoding="utf-8"))["stdin"]
blocks = text.split("\n\n")
print(blocks[0] == "【系統】你是甲"
      and "要叫工具就真的叫 MCP 工具" in blocks[1]
      and blocks[2:] == ["【user】算 3 加 4",
                         "【assistant】我算一下\n→ add {\"a\": 3, \"b\": 4}",
                         "【tool:add】7",
                         "【user】請叫 say 說 hi",
                         "【assistant】"])
PYEOF2
)
  cx_assert "$got" "codex-cli：stdin 是【系統】＋規矩＋渲染好的對話"

  # (d) 回來的翻成 OpenAI 形狀：tool_calls 來自登記檔，usage 含思考 token，thread 記在 aos.cli。
  got=$(python3 - "$llm/results/0001.json" <<'PYEOF2'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["choices"][0]["message"]
u = d["usage"]
print(m["tool_calls"][0]["function"]["name"] == "say"
      and m["tool_calls"][0]["id"] == "call_1"
      and m["tool_calls"][0]["type"] == "function"
      and json.loads(m["tool_calls"][0]["function"]["arguments"]) == {"text": "嗨"}
      and m["content"] == "我來叫工具"
      and d["choices"][0]["finish_reason"] == "tool_calls"
      and u["prompt_tokens"] == 1300
      and u["prompt_tokens_details"]["cached_tokens"] == 1100
      and u["completion_tokens"] == 14
      and u["completion_tokens_details"]["reasoning_tokens"] == 5
      and u["total_tokens"] == 1314
      and u["reasoning_output_tokens"] == 5
      and d["aos"]["cli"]["thread_id"] == "th-77"
      and d["aos"]["cli"]["killed"] is False
      and d["aos"]["cli"]["recorded"] == 1 and d["aos"]["cli"]["streamed"] == 1
      and d["aos"]["cli"]["usage"]["input_tokens"] == 1300
      and "cli" not in d)
PYEOF2
)
  cx_assert "$got" "codex-cli：結果是 OpenAI 形狀的 tool_calls／usage，thread 記在 aos.cli"

  # (e) 成功就把 side/codex/ 的小抄收乾淨。
  specs=$(ls "$llm/side/codex" 2>/dev/null | wc -l)
  if [ "$specs" = "0" ]; then ok "codex-cli：成功之後 side/codex/ 的小抄清乾淨了"
  else fail "codex-cli：side/codex/ 還留著 $specs 個檔"; fi

  day=$(date +%F)
  got=$(python3 - "$llm/usage/$day.json" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
row = book["by-model"]["|gpt-5.6-luna"]
print(row["total_tokens"] == 1314 and row["requests"] == 1 and row["errors"] == 0
      and book["by-requester"]["team/one"]["total_tokens"] == 1314)
PYEOF2
)
  cx_assert "$got" "codex-cli：用量一樣進帳本（沒有 base_url，key 就是 |模型）"

  # (f) 一直不收工的：第一批工具登記進來之後我們自己收掉它，有什麼算什麼。
  echo '{"engine": "slow", "messages": [{"role": "user", "content": "叫工具"}]}' \
    > "$llm/requests/0004.json"
  llm_pump "$llm" 200 >/dev/null
  got=$(python3 - "$llm/results/0004.json" <<'PYEOF2'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["choices"][0]["message"]
print("error" not in d
      and m["tool_calls"][0]["function"]["name"] == "say"
      and d["choices"][0]["finish_reason"] == "tool_calls"
      and d["aos"]["cli"]["killed"] is True)
PYEOF2
)
  cx_assert "$got" "codex-cli：不收工的被我們收掉，工具呼叫照樣拿得到"

  # (g) turn.failed → 一句 error；(h) 找不到執行檔 → 當場講清楚，不等逾時。
  echo '{"engine": "boom", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0002.json"
  echo '{"engine": "gone", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0003.json"
  llm_pump "$llm" >/dev/null
  got=$(python3 - "$llm/results/0002.json" "$llm/results/0003.json" <<'PYEOF2'
import json, sys
bad = json.load(open(sys.argv[1], encoding="utf-8")).get("error") or ""
gone = json.load(open(sys.argv[2], encoding="utf-8")).get("error") or ""
print(bad.startswith("codex-cli 失敗：") and "usage limit reached" in bad
      and "找不到 codex 執行檔" in gone and "沒有這支執行檔" in gone)
PYEOF2
)
  cx_assert "$got" "codex-cli：turn.failed 與找不到執行檔都變成看得懂的一句 error"
  got=$(python3 - "$llm/side/codex" <<'PYEOF2'
import os, sys
names = sorted(os.listdir(sys.argv[1])) if os.path.isdir(sys.argv[1]) else []
print(names == ["0002.record.jsonl", "0002.specs.json"])
PYEOF2
)
  cx_assert "$got" "codex-cli：失敗那發的小抄留在 side/codex/ 給人看"
  got=$(python3 - "$llm/usage/$day.json" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
print(sum(row.get("errors", 0) for row in book["by-model"].values()) == 2)
PYEOF2
)
  cx_assert "$got" "codex-cli：兩發失敗都記進帳本的 errors"

  kill_workers "$llm"
  rm -rf "$tmp"
}

test_aos_mcp_tools() {
  local tmp out got
  tmp=$(mktemp -d)
  cat > "$tmp/specs.json" <<'PYEOF2'
[{"name": "say", "description": "說一句",
  "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                 "required": ["text"]}},
 {"name": "order_status", "description": "查訂單",
  "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}}}]
PYEOF2
  out=$({
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
    printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized"}'
    printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/沒聽過的"}'
    printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
    printf '%s\n' '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"say","arguments":{"text":"hi"}}}'
    printf '%s\n' '{"jsonrpc":"2.0","id":4,"method":"ping"}'
    printf '%s\n' '{"jsonrpc":"2.0","id":5,"method":"沒這個方法"}'
  } | AOS_MCP_RECORD="$tmp/rec.jsonl" "$HERE/aos-mcp-tools" "$tmp/specs.json" 2>/dev/null)
  printf '%s\n' "$out" > "$tmp/out.jsonl"
  got=$(python3 - "$tmp/out.jsonl" "$tmp/rec.jsonl" <<'PYEOF2'
import json, sys
rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
by = {r.get("id"): r for r in rows}
tools = by[2]["result"]["tools"]
text = by[3]["result"]["content"][0]["text"]
rec = [json.loads(x) for x in open(sys.argv[2], encoding="utf-8") if x.strip()]
print(len(rows) == 5                                     # 兩則通知都沒有回覆
      and by[1]["result"]["protocolVersion"] == "2024-11-05"
      and by[1]["result"]["capabilities"] == {"tools": {}}
      and [t["name"] for t in tools] == ["say", "order_status"]
      and tools[0]["inputSchema"]["required"] == ["text"]   # parameters → inputSchema
      and "parameters" not in tools[0]
      and text.startswith("已登記 say；") and "不要再叫工具" in text
      and by[3]["result"].get("isError") is None
      and by[4]["result"] == {}
      and by[5]["error"]["code"] == -32601
      and rec == [{"name": "say", "arguments": {"text": "hi"}}])
PYEOF2
)
  cx_assert "$got" "aos-mcp-tools：JSON-RPC 該回的都回了，工具呼叫只登記不執行"
  rm -rf "$tmp"
}

test_codex_cli
test_aos_mcp_tools
