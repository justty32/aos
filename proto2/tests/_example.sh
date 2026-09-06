# 工具包測試範例：只動自己的 pack／test／doc 三個檔。
test_example_pack() {
  local root world home reply
  root=$(make_world example_pack)
  world="$root/agent"
  home="$world/agent"
  mkdir -p "$home/packs"
  cat > "$home/packs/example_pack.py" <<'PYEOF2'
PROMPT = "範例包：example_hello 會回一句招呼。"
TOOLS = [{"name": "example_hello", "description": "回一句招呼。",
          "parameters": {"type": "object", "properties": {}}}]


def run(name, args, ctx):
    return {"text": "掛勾範例成功"}
PYEOF2
  python3 - "$home/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["packs"] = ["example_pack"]
d["tools"] = []
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
  reply=$(say_and_wait "$world" "$root/llm" 'CALL example_hello' 20) || true
  if [ -n "$reply" ] && grep -q "掛勾範例成功" "$reply"; then
    ok "tests/_example.sh：假 server 叫得到一個自訂工具並收到結果"
  else
    fail "tests/_example.sh：自訂工具沒有走完（reply=$reply）"
  fi
  rm -rf "$root"
}

test_example_pack
