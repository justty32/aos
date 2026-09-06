# toolsmith：自製 shell 工具與自己的 pack 骨架。

enable_toolsmith() {
  python3 - "$1/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["packs"] = ["toolsmith"]
d["tools"] = []
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
}

test_toolsmith_direct() {
  local root world home got
  root=$(make_world toolsmith_direct)
  world="$root/agent"; home="$world/agent"
  enable_toolsmith "$home"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, resolve_home, tool_specs

world = sys.argv[2]
home = resolve_home(world, None)
loaded, extra = load_packs(home)
pack = dict(loaded)["toolsmith"]
ctx = Ctx(world, home, {}, loaded).for_pack("toolsmith")
added = pack.run("tool_add", {
    "name": "echo_json", "description": "印出收到的 JSON",
    "parameters": {"word": {"type": "string"}},
    "command": "python3 -c 'import sys; print(sys.stdin.read())'"}, ctx)
tried = pack.run("tool_try", {"name": "echo_json", "args": {"word": "哈囉"}}, ctx)
listed = pack.run("tool_list", {}, ctx)
loaded2, extra2 = load_packs(home)
specs = tool_specs(loaded2, extra2)
removed = pack.run("tool_remove", {"name": "echo_json"}, ctx)
conf = json.load(open(os.path.join(home, "tools.json"), encoding="utf-8"))
print(added.get("ok") is True)
print(tried.get("exit") == 0 and json.loads(tried.get("stdout")) == {"word": "哈囉"})
print(any(x.get("name") == "echo_json" and x.get("from") == "custom" for x in listed))
schema = next(x["parameters"] for x in specs if x.get("name") == "echo_json")
print(schema.get("type") == "object" and "word" in schema.get("properties", {}))
print(removed.get("ok") is True and not conf.get("tools"))
PYEOF2
)
  if [ "$(printf '%s\n' "$got" | sed -n '1p')" = "True" ]; then ok "toolsmith：tool_add 寫入自製工具"; else fail "toolsmith：tool_add 失敗（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '2p')" = "True" ]; then ok "toolsmith：tool_try 當格收到 args JSON 並跑成功"; else fail "toolsmith：tool_try 失敗（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '3p')" = "True" ]; then ok "toolsmith：tool_list 列出 custom、描述與 command"; else fail "toolsmith：tool_list 失敗（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '4p')" = "True" ]; then ok "toolsmith：不完整 parameters 會補成 object schema"; else fail "toolsmith：parameters 沒補好（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '5p')" = "True" ]; then ok "toolsmith：tool_remove 移除自製工具"; else fail "toolsmith：tool_remove 失敗（$got）"; fi
  rm -rf "$root"
}

test_toolsmith_next_turn() {
  local root world home reply added_req got today
  root=$(make_world toolsmith_turn)
  world="$root/agent"; home="$world/agent"
  enable_toolsmith "$home"
  reply=$(say_and_wait "$world" "$root/llm" \
    'CALL tool_add {"name":"today","description":"印今天日期","command":"date +%F"}' 30) || true
  added_req=$(python3 - "$root/llm" <<'PYEOF2'
import glob, json, os, sys
for p in glob.glob(os.path.join(sys.argv[1], "requests", "done", "*.json")):
    d = json.load(open(p, encoding="utf-8"))
    names = [x.get("function", {}).get("name") for x in d.get("tools", [])]
    if "today" in names:
        print("yes")
        break
PYEOF2
)
  if [ -n "$reply" ] && [ "$added_req" = "yes" ]; then
    ok "toolsmith：add 後下一格送給模型的 tools 有 today"
  else
    fail "toolsmith：today 沒在下一格出現（reply=$reply，request=$added_req）"
  fi

  reply=$(say_and_wait "$world" "$root/llm" $'CALL tool_list\nCALL today' 40) || true
  today=$(date +%F)
  got=$(python3 - "$home/prompts.json" <<'PYEOF2'
import json, sys
msgs = json.load(open(sys.argv[1], encoding="utf-8"))
rows = []
for msg in msgs:
    if msg.get("role") != "tool":
        continue
    try:
        value = json.loads(msg.get("content") or "")
    except (TypeError, ValueError):
        continue
    if isinstance(value, list) and any(x.get("name") == "today" and x.get("from") == "custom" for x in value):
        rows.append("listed")
print("yes" if rows else "no")
PYEOF2
)
  if [ -n "$reply" ] && grep -q "$today" "$reply"; then ok "toolsmith：模型叫得到新造的 today"; else fail "toolsmith：模型沒叫到 today（reply=$reply）"; fi
  if [ "$got" = "yes" ]; then ok "toolsmith：模型用 tool_list 看得到 today"; else fail "toolsmith：模型的 tool_list 沒看到 today"; fi

  reply=$(say_and_wait "$world" "$root/llm" 'CALL tool_remove {"name":"today"}' 30) || true
  got=$(python3 - "$home/tools.json" "$root/llm" <<'PYEOF2'
import glob, json, os, sys
conf = json.load(open(sys.argv[1], encoding="utf-8"))
requests = sorted(glob.glob(os.path.join(sys.argv[2], "requests", "done", "*.json")), key=os.path.getmtime)
last = json.load(open(requests[-1], encoding="utf-8")) if requests else {}
names = [x.get("function", {}).get("name") for x in last.get("tools", [])]
print(not any(x.get("name") == "today" for x in conf.get("tools", [])) and "today" not in names)
PYEOF2
)
  if [ -n "$reply" ] && [ "$got" = "True" ]; then ok "toolsmith：remove 後下一格清單沒有 today"; else fail "toolsmith：remove 沒生效（reply=$reply，$got）"; fi
  rm -rf "$root"
}

test_toolsmith_pack_skeleton() {
  local root world home got
  root=$(make_world toolsmith_pack)
  world="$root/agent"; home="$world/agent"
  enable_toolsmith "$home"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, resolve_home

world = sys.argv[2]
home = resolve_home(world, None)
loaded, _ = load_packs(home)
pack = dict(loaded)["toolsmith"]
ctx = Ctx(world, home, {}, loaded).for_pack("toolsmith")
added = pack.run("tool_add", {"pack": "made_here"}, ctx)
loaded2, _ = load_packs(home)
path = os.path.join(home, "packs", "made_here.py")
conf = json.load(open(os.path.join(home, "tools.json"), encoding="utf-8"))
print(added.get("ok") is True and os.path.isfile(path) and "made_here" in conf.get("packs", []))
print("made_here" in dict(loaded2))
removed = pack.run("tool_remove", {"pack": "made_here"}, ctx)
conf2 = json.load(open(os.path.join(home, "tools.json"), encoding="utf-8"))
print(removed.get("ok") is True and "made_here" not in conf2.get("packs", []) and os.path.isfile(path))
PYEOF2
)
  if [ "$(printf '%s\n' "$got" | sed -n '1p')" = "True" ]; then ok "toolsmith：pack 模式在自己 home 寫骨架並啟用"; else fail "toolsmith：pack 骨架沒寫好（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '2p')" = "True" ]; then ok "toolsmith：新 pack 骨架下一次可載入"; else fail "toolsmith：新 pack 骨架載不起來（$got）"; fi
  if [ "$(printf '%s\n' "$got" | sed -n '3p')" = "True" ]; then ok "toolsmith：關 pack 不刪自己的骨架檔"; else fail "toolsmith：關 pack 的結果不對（$got）"; fi
  rm -rf "$root"
}

test_toolsmith_direct
test_toolsmith_next_turn
test_toolsmith_pack_skeleton
