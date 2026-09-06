test_branch_pack() {
  local root world home opened branch_id got before after
  root=$(make_world branch_pack)
  world="$root/agent"
  home="$world/agent"
  python3 - "$home/tools.json" "$home/prompts.json" <<'PYEOF2'
import json, sys
tools, prompts = sys.argv[1:3]
d = json.load(open(tools, encoding="utf-8"))
d["packs"] = ["branch"]
d["tools"] = []
json.dump(d, open(tools, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
history = [
    {"role": "user", "content": "週末怎麼安排？"},
    {"role": "assistant", "content": "", "tool_calls": [{
        "id": "call_fork", "type": "function",
        "function": {"name": "fork", "arguments": "{}"},
    }]},
]
json.dump(history, open(prompts, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2

  opened=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, resolve_home, write_json
world = sys.argv[2]; home = resolve_home(world, None)
state = {"state":"idle", "step":1, "busy":0, "request":"", "pending":[]}
loaded, _ = load_packs(home)
ctx = Ctx(world, home, state, loaded).for_pack("branch")
pack = dict(loaded)["branch"]
answer = pack.run("fork", {"directions":["放鬆休息", "戶外探索", "處理生活雜事"]}, ctx)
write_json(os.path.join(home, "state.json"), state)
print(json.dumps(answer, ensure_ascii=False))
PYEOF2
)
  branch_id=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["branch_id"])' "$opened")

  got=$(python3 - "$root" "$branch_id" <<'PYEOF2'
import glob, json, os, sys
root, branch_id = sys.argv[1:3]
home = os.path.join(root, "agent", "agent")
requests = sorted(glob.glob(os.path.join(root, "llm", "requests", "*.json")))
state = json.load(open(os.path.join(home, "state.json"), encoding="utf-8"))
base = json.load(open(os.path.join(home, "branches", branch_id, "base.json"), encoding="utf-8"))
parts = glob.glob(os.path.join(home, "branches", branch_id, "[0-9][0-9]", "prompts.json"))
bodies = [json.load(open(p, encoding="utf-8")) for p in requests]
print(len(requests), len(parts), len(state["branches"][branch_id]["pending"]),
      len(base), all(b.get("params",{}).get("max_tokens") == 1500 for b in bodies),
      all("tools" not in b for b in bodies))
PYEOF2
)
  if [ "$got" = "3 3 3 2 True True" ]; then
    ok "branch：fork 三條會快照記憶並丟三個 branch 請求"
  else
    fail "branch：fork 落檔或請求不對（$got）"
  fi

  got=$(python3 - "$HERE" "$world" "$branch_id" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, read_json, resolve_home
world, branch_id = sys.argv[2:4]; home = resolve_home(world, None)
state = read_json(os.path.join(home, "state.json"), {})
loaded, _ = load_packs(home); pack = dict(loaded)["branch"]
print(json.dumps(pack.run("join", {"branch_id":branch_id},
      Ctx(world, home, state, loaded).for_pack("branch")), ensure_ascii=False))
PYEOF2
)
  if [ "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["waiting"])' "$got")" = "[1, 2, 3]" ]; then
    ok "branch：join 沒齊時會說還差三條"
  else
    fail "branch：join 沒齊的回覆不對（$got）"
  fi

  llm_pump "$root/llm" >/dev/null
  agent_tick "$world"
  got=$(python3 - "$HERE" "$world" "$branch_id" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, read_json, resolve_home
world, branch_id = sys.argv[2:4]; home = resolve_home(world, None)
state = read_json(os.path.join(home, "state.json"), {})
loaded, _ = load_packs(home); pack = dict(loaded)["branch"]
answer = pack.run("join", {"branch_id":branch_id}, Ctx(world, home, state, loaded).for_pack("branch"))
print(len(answer.get("branches",[])), answer.get("text","").count("方向 "),
      len(state["branches"][branch_id]["pending"]), len(state["branches"][branch_id]["done"]),
      all(row.get("summary") == "done" for row in answer.get("branches",[])))
PYEOF2
)
  if [ "$got" = "3 3 0 3 True" ]; then
    ok "branch：假 server 回三條後，join 一次拿到三段總結"
  else
    fail "branch：三條結果沒收齊（$got）"
  fi

  got=$(python3 - "$HERE" "$world" "$branch_id" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, read_json, resolve_home, write_json
world, branch_id = sys.argv[2:4]; home = resolve_home(world, None)
state = read_json(os.path.join(home, "state.json"), {})
loaded, _ = load_packs(home); pack = dict(loaded)["branch"]
ctx = Ctx(world, home, state, loaded).for_pack("branch")
answer = pack.run("adopt", {"branch_id":branch_id, "n":2}, ctx)
main = read_json(os.path.join(home, "prompts.json"), [])
part = read_json(os.path.join(home, "branches", branch_id, "02", "prompts.json"), [])
write_json(os.path.join(home, "prompts.json"), main + [{"role":"tool", "content":"舊主線 adopt 結果"}])
pack.on_system_prompt(ctx)
cleaned = read_json(os.path.join(home, "prompts.json"), [])
write_json(os.path.join(home, "state.json"), state)
print("error" not in answer, main == part, cleaned == part,
      cleaned[-1].get("content") == "done", state.get("branch_depth") == 1)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "branch：adopt 會用選中分支的整段記憶取代主線"
  else
    fail "branch：adopt 沒接手完整分支（$got）"
  fi

  before=$(find "$root/llm/requests" -maxdepth 1 -name '*.json' | wc -l)
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, read_json, resolve_home
world = sys.argv[2]; home = resolve_home(world, None)
state = read_json(os.path.join(home, "state.json"), {})
loaded, _ = load_packs(home); pack = dict(loaded)["branch"]
answer = pack.run("fork", {"directions":["方向甲", "方向乙"]},
                  Ctx(world, home, state, loaded).for_pack("branch"))
print(answer.get("error") or "")
PYEOF2
)
  after=$(find "$root/llm/requests" -maxdepth 1 -name '*.json' | wc -l)
  if echo "$got" | grep -q "不能在分支裡再 fork" && [ "$before" = "$after" ]; then
    ok "branch：巢狀 fork 被拒絕，也沒偷丟請求"
  else
    fail "branch：巢狀 fork 沒被擋下（$got，$before->$after）"
  fi
  rm -rf "$root"
}

test_branch_pack
