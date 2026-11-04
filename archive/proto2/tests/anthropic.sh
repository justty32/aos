# Anthropic 直連：引擎寫 "api": "anthropic" 就直接打 /v1/messages，不用 LiteLLM 之類的轉接器。
# 這裡起一台假的 Anthropic 伺服器（自己一個埠、跑完收掉），把收到的請求原樣記下來，
# 回一包罐頭 messages 回覆（一個 text 塊＋一個 tool_use 塊＋usage）。要驗兩頭：
# 送出去的有沒有翻成 Anthropic 那一味，回來的有沒有翻回 OpenAI 那一味（外面只認這個）。

anth_assert() {  # anth_assert <python 印出的 True/False> <名字>
  if [ "$1" = "True" ]; then ok "$2"; else fail "$2（$1）"; fi
}

anth_start_server() {  # anth_start_server <記錄資料夾>；設好 ANTH_PORT／ANTH_PID
  local rec=$1
  ANTH_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
  cat > "$rec/fake-anthropic.py" <<'PYEOF2'
import http.server, json, os, sys

REC = sys.argv[2]
REPLY = {
    "id": "msg_01", "type": "message", "role": "assistant",
    "model": "claude-haiku-4-5-20251001",
    "content": [{"type": "text", "text": "我來叫工具"},
                {"type": "tool_use", "id": "toolu_01", "name": "say",
                 "input": {"text": "嗨"}}],
    "stop_reason": "tool_use", "stop_sequence": None,
    "usage": {"input_tokens": 11, "output_tokens": 7,
              "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0},
}
BOOM = {"type": "error", "error": {"type": "invalid_request_error",
                                   "message": "model 不存在：boom-model"}}


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8")
        try:
            body = json.loads(raw)
        except ValueError:
            body = {}
        seq = len([x for x in os.listdir(REC) if x.startswith("req-")]) + 1
        with open(os.path.join(REC, "req-%02d.json" % seq), "w", encoding="utf-8") as f:
            json.dump({"path": self.path,
                       "headers": {k.lower(): v for k, v in self.headers.items()},
                       "body": body}, f, ensure_ascii=False)
        boom = body.get("model") == "boom-model"
        out = json.dumps(BOOM if boom else REPLY, ensure_ascii=False).encode("utf-8")
        self.send_response(400 if boom else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PYEOF2
  python3 "$rec/fake-anthropic.py" "$ANTH_PORT" "$rec" &
  ANTH_PID=$!
  python3 - "$ANTH_PORT" <<'PYEOF2'
import socket, sys, time
for _ in range(60):
    try:
        socket.create_connection(("127.0.0.1", int(sys.argv[1])), 0.2).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.05)
sys.exit(1)
PYEOF2
}

test_anthropic_wire() {
  local tmp rec llm got day
  tmp=$(mktemp -d); rec="$tmp/rec"; llm="$tmp/llm"
  mkdir -p "$rec"
  if ! anth_start_server "$rec"; then
    fail "假 Anthropic 伺服器起不來"
    rm -rf "$tmp"
    return
  fi
  ok "假 Anthropic 伺服器起來了"
  export ANTHROPIC_TEST_KEY=test-key-123
  mk_engines "$llm" "[{\"name\": \"cheap\", \"api\": \"anthropic\",
    \"base_url\": \"http://127.0.0.1:$ANTH_PORT\",
    \"model\": \"claude-haiku-4-5-20251001\",
    \"api_key_env\": \"ANTHROPIC_TEST_KEY\", \"max_concurrent\": 4,
    \"params\": {\"max_tokens\": 4096}},
   {\"name\": \"boom\", \"api\": \"anthropic\",
    \"base_url\": \"http://127.0.0.1:$ANTH_PORT\", \"model\": \"boom-model\",
    \"api_key_env\": \"ANTHROPIC_TEST_KEY\"}]"

  # 一發正常的：兩則 system、一輪工具往返、連著兩則 tool 結果（要併成同一輪 user）。
  cat > "$llm/requests/0001.json" <<'PYEOF2'
{"requester": "team/one", "engine": "cheap", "temperature": 0.2, "n": 1,
 "messages": [
   {"role": "system", "content": "你是甲"},
   {"role": "system", "content": "你也是乙"},
   {"role": "user", "content": "算 3 加 4"},
   {"role": "assistant", "content": "我算一下",
    "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "add", "arguments": "{\"a\": 3, \"b\": 4}"}}]},
   {"role": "tool", "tool_call_id": "call_1", "content": "7"},
   {"role": "tool", "tool_call_id": "call_1", "content": "順便再一則"}],
 "tools": [{"type": "function",
            "function": {"name": "say", "description": "說一句",
                         "parameters": {"type": "object",
                                        "properties": {"text": {"type": "string"}}}}}],
 "tool_choice": "auto"}
PYEOF2
  llm_pump "$llm" >/dev/null

  # (a) 送出去的那一包：header、路徑、system 抽到頂層、tools 換成 input_schema、
  #     連續同一邊的訊息併成一輪。
  got=$(python3 - "$rec/req-01.json" <<'PYEOF2'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
h, b = r["headers"], r["body"]
msgs = b.get("messages") or []
roles = [m["role"] for m in msgs]
last = msgs[-1]["content"] if msgs else []
print(r["path"] == "/v1/messages"
      and h.get("x-api-key") == "test-key-123"
      and h.get("anthropic-version") == "2023-06-01"
      and "authorization" not in h
      and b.get("system") == "你是甲\n\n你也是乙"
      and b.get("model") == "claude-haiku-4-5-20251001"
      and b.get("max_tokens") == 4096
      and b.get("temperature") == 0.2 and "n" not in b
      and b["tools"][0]["name"] == "say"
      and b["tools"][0]["input_schema"]["properties"]["text"]["type"] == "string"
      and b.get("tool_choice") == {"type": "auto"}
      and roles == ["user", "assistant", "user"]
      and msgs[1]["content"][1]["type"] == "tool_use"
      and msgs[1]["content"][1]["input"] == {"a": 3, "b": 4}
      and [c["type"] for c in last] == ["tool_result", "tool_result"]
      and last[0]["tool_use_id"] == "call_1" and last[0]["content"] == "7")
PYEOF2
)
  anth_assert "$got" "anthropic：送出去的是 /v1/messages，header、system、tools、併輪都對"

  # (b) 回來的那一包：翻回 OpenAI 形狀，usage 三個數字齊全。
  got=$(python3 - "$llm/results/0001.json" <<'PYEOF2'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["choices"][0]["message"]
u = d["usage"]
print(m["tool_calls"][0]["function"]["name"] == "say"
      and json.loads(m["tool_calls"][0]["function"]["arguments"]) == {"text": "嗨"}
      and m["tool_calls"][0]["type"] == "function"
      and m["content"] == "我來叫工具"
      and d["choices"][0]["finish_reason"] == "tool_calls"
      and u["prompt_tokens"] == 14 and u["completion_tokens"] == 7
      and u["total_tokens"] == 21
      and u["prompt_tokens_details"]["cached_tokens"] == 3
      and d["aos"]["engine"] == "cheap" and d["aos"]["usage"]["total_tokens"] == 21)
PYEOF2
)
  anth_assert "$got" "anthropic：結果是 OpenAI 形狀的 tool_calls／finish_reason／usage"

  # 帳本也要收得到（預算閘門看的就是這裡的 total_tokens）。
  day=$(date +%F)
  got=$(python3 - "$llm/usage/$day.json" "http://127.0.0.1:$ANTH_PORT|claude-haiku-4-5-20251001" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
row = book["by-model"][sys.argv[2]]
print(row["total_tokens"] == 21 and row["prompt_tokens"] == 14
      and row["requests"] == 1 and row["errors"] == 0
      and book["by-requester"]["team/one"]["total_tokens"] == 21)
PYEOF2
)
  anth_assert "$got" "anthropic：用量進了帳本的 by-model 與 by-requester"

  # (c) 錯的那一發：HTTP 400 加 Anthropic 的錯誤 body → {"error": "HTTP 400 ...訊息"}，
  #     完成標記寫 error true。標記會被下一格收走，所以先等它出現、看完再推格。
  echo '{"engine": "boom", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0002.json"
  "$LLM" exec "$llm" >/dev/null 2>&1
  local i=0
  while [ "$i" -lt 60 ] && [ ! -f "$llm/requests/running/0002.json.done" ]; do
    sleep 0.1; i=$((i + 1))
  done
  got=$(python3 - "$llm/requests/running/0002.json.done" "$llm/results/0002.json" <<'PYEOF2'
import json, os, sys
marker = json.load(open(sys.argv[1], encoding="utf-8")) if os.path.isfile(sys.argv[1]) else {}
res = json.load(open(sys.argv[2], encoding="utf-8"))
err = res.get("error") or ""
print(marker.get("error") is True and err.startswith("HTTP 400")
      and "invalid_request_error" in err and "model 不存在：boom-model" in err
      and "choices" not in res)
PYEOF2
)
  anth_assert "$got" "anthropic：HTTP 400 的錯誤 body 變成一句 error，完成標記記 error"
  llm_pump "$llm" >/dev/null
  if [ -f "$llm/requests/done/0002.json" ]; then
    ok "anthropic：出錯的請求一樣搬去 requests/done/"
  else
    fail "anthropic：出錯的請求沒搬去 requests/done/"
  fi

  kill_workers "$llm"
  kill "$ANTH_PID" 2>/dev/null
  wait "$ANTH_PID" 2>/dev/null
  unset ANTHROPIC_TEST_KEY
  rm -rf "$tmp"
}

test_anthropic_translate() {
  # 純 python 的單元檢查：三輪對話（user → assistant 開工具 → 工具結果 → assistant）
  # 兩個翻譯函式各走一遍，不碰網路。
  local got
  got=$(python3 - "$HERE/aos-llm" <<'PYEOF2'
import json, sys, types

path = sys.argv[1]
# aos-llm 沒有副檔名、結尾直接 sys.exit(main())，所以把最後那句拿掉再 exec 進來。
src = open(path, encoding="utf-8").read().replace("\nsys.exit(main())\n", "\n")
mod = types.ModuleType("aosllm")
mod.__file__ = path
exec(compile(src, path, "exec"), mod.__dict__)

body = {
    "model": "claude-sonnet-5", "max_tokens": 1024, "temperature": 0.1, "stop": "END",
    "seed": 7,
    "messages": [
        {"role": "system", "content": "你是助理"},
        {"role": "user", "content": "查天氣"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "call_9", "type": "function",
                         "function": {"name": "weather",
                                      "arguments": "{\"city\": \"台北\"}"}}]},
        {"role": "tool", "tool_call_id": "call_9", "content": "晴"},
        {"role": "assistant", "content": "台北是晴的"},
    ],
    "tools": [{"type": "function",
               "function": {"name": "weather", "description": "查天氣",
                            "parameters": {"type": "object",
                                           "properties": {"city": {"type": "string"}}}}}],
    "tool_choice": {"type": "function", "function": {"name": "weather"}},
}
sent = mod.to_anthropic(body)
msgs = sent["messages"]
first = [
    sent["system"] == "你是助理",
    sent["max_tokens"] == 1024 and sent["temperature"] == 0.1,
    sent["stop_sequences"] == ["END"] and "stop" not in sent and "seed" not in sent,
    sent["tool_choice"] == {"type": "tool", "name": "weather"},
    sent["tools"] == [{"name": "weather", "description": "查天氣",
                       "input_schema": {"type": "object",
                                        "properties": {"city": {"type": "string"}}}}],
    [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"],
    msgs[0]["content"] == [{"type": "text", "text": "查天氣"}],
    msgs[1]["content"] == [{"type": "tool_use", "id": "call_9", "name": "weather",
                            "input": {"city": "台北"}}],
    msgs[2]["content"] == [{"type": "tool_result", "tool_use_id": "call_9",
                            "content": "晴"}],
    msgs[3]["content"] == [{"type": "text", "text": "台北是晴的"}],
]

reply = {"id": "msg_9", "model": "claude-sonnet-5", "stop_reason": "end_turn",
         "content": [{"type": "thinking", "thinking": "想一下"},
                     {"type": "text", "text": "台北是晴的"}],
         "usage": {"input_tokens": 30, "output_tokens": 8,
                   "cache_read_input_tokens": 10, "cache_creation_input_tokens": 2}}
back = mod.from_anthropic(reply)
msg = back["choices"][0]["message"]
second = [
    msg["content"] == "台北是晴的" and msg["reasoning_content"] == "想一下",
    "tool_calls" not in msg,
    back["choices"][0]["finish_reason"] == "stop",
    back["usage"]["prompt_tokens"] == 42 and back["usage"]["completion_tokens"] == 8,
    back["usage"]["total_tokens"] == 50,
    back["usage"]["cache_read_input_tokens"] == 10,
    mod.from_anthropic({"stop_reason": "max_tokens", "content": []})
        ["choices"][0]["finish_reason"] == "length",
    mod.from_anthropic({"stop_reason": "tool_use", "content": []})
        ["choices"][0]["finish_reason"] == "tool_calls",
    # strip_think 對 Anthropic 沒事幹（沒有 <think>），但不能炸。
    mod.strip_think(back)["choices"][0]["message"]["content"] == "台北是晴的",
    mod.api_of({"api": "anthropic"}) == "anthropic" and mod.api_of({}) == "openai",
]
print(all(first) and all(second))
PYEOF2
)
  anth_assert "$got" "anthropic：兩個翻譯函式對三輪對話（含工具往返）都翻得對"
}

test_anthropic_wire
test_anthropic_translate
