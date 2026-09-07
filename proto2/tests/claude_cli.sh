# claude-cli：把 Claude Code 的 headless（`claude -p`）當成一台引擎——給有訂閱、沒 API key 的人用。
# 測試不碰真的 CLI，也不碰網路：擺一支**假的 claude**（把 argv 與 stdin 原樣記下來，
# 印一包罐頭的 --output-format json），引擎用 "bin" 指過去。要驗三件事：
# 指令列的旗標對不對、stdin 那段對話長得對不對、回來的有沒有翻成 OpenAI 的形狀。

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
seq = len([x for x in os.listdir(rec) if x.startswith("run-")]) + 1
with open(os.path.join(rec, "run-%02d.json" % seq), "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv[1:], "stdin": sys.stdin.read(), "cwd": os.getcwd()},
              f, ensure_ascii=False)
if code:
    sys.stderr.write("假 claude 故意壞掉：credit balance too low\n")
    sys.exit(code)
print(json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "session_id": "sess-42", "total_cost_usd": 0.0112, "num_turns": 1,
    "stop_reason": "tool_use", "duration_ms": 900,
    "result": "{\"content\":\"我來叫工具\",\"tool_calls\":[{\"name\":\"say\",\"arguments\":{\"text\":\"嗨\"}}]}",
    "structured_output": {"content": "我來叫工具",
                          "tool_calls": [{"name": "say", "arguments": {"text": "嗨"}}]},
    "usage": {"input_tokens": 11, "output_tokens": 7,
              "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0},
}, ensure_ascii=False))
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

  # (a) 指令列：旗標、模型、schema、工具清單寫進 --append-system-prompt，cwd 是 LLM 資料夾。
  got=$(python3 - "$rec/run-01.json" "$llm" <<'PYEOF2'
import json, os, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
a = r["argv"]


def after(flag):
    return a[a.index(flag) + 1] if flag in a else None


schema = json.loads(after("--json-schema") or "{}")
sysp = after("--append-system-prompt") or ""
print(a[0] == "-p" and "--safe-mode" in a and "--no-session-persistence" in a
      and "--bare" not in a
      and after("--output-format") == "json"
      and after("--tools") == "" and after("--model") == "haiku"
      and after("--effort") == "low"
      and schema["required"] == ["content", "tool_calls"]
      and schema["properties"]["tool_calls"]["items"]["required"] == ["name", "arguments"]
      and sysp.startswith("你是甲")
      and "你可以叫的工具（只能從這裡挑）" in sysp
      and '- say({"type":"object","properties":{"text":{"type":"string"}}}) — 說一句' in sysp
      and "回覆一定要符合 json-schema" in sysp
      and os.path.realpath(r["cwd"]) == os.path.realpath(sys.argv[2]))
PYEOF2
)
  cli_assert "$got" "claude-cli：指令列旗標、模型、json-schema、工具清單與 cwd 都對"

  # (b) stdin 那段對話：一則一段，assistant 的工具呼叫用 → 印，最後留空的【assistant】。
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

  # (c) 回來的翻成 OpenAI 形狀，usage 三個數字齊全，session_id／花費記在 aos.cli。
  got=$(python3 - "$llm/results/0001.json" <<'PYEOF2'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["choices"][0]["message"]
u = d["usage"]
print(m["tool_calls"][0]["function"]["name"] == "say"
      and m["tool_calls"][0]["id"] == "call_1"
      and json.loads(m["tool_calls"][0]["function"]["arguments"]) == {"text": "嗨"}
      and m["content"] == "我來叫工具"
      and d["choices"][0]["finish_reason"] == "tool_calls"
      and u["prompt_tokens"] == 14 and u["completion_tokens"] == 7
      and u["total_tokens"] == 21
      and d["aos"]["cli"]["session_id"] == "sess-42"
      and d["aos"]["cli"]["total_cost_usd"] == 0.0112
      and "cli" not in d)
PYEOF2
)
  cli_assert "$got" "claude-cli：結果是 OpenAI 形狀的 tool_calls／usage，花費記在 aos.cli"

  day=$(date +%F)
  got=$(python3 - "$llm/usage/$day.json" <<'PYEOF2'
import json, sys
book = json.load(open(sys.argv[1], encoding="utf-8"))
row = book["by-model"]["|haiku"]
print(row["total_tokens"] == 21 and row["requests"] == 1 and row["errors"] == 0)
PYEOF2
)
  cli_assert "$got" "claude-cli：用量一樣進帳本（沒有 base_url，key 就是 |模型）"

  # (d) CLI 掛掉：退出碼非 0 → 一句 error，帳本記 errors。
  echo '{"engine": "boom", "messages": [{"role": "user", "content": "哈"}]}' \
    > "$llm/requests/0002.json"
  # (e) 找不到執行檔：不等逾時，當場講清楚。
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

test_claude_cli
