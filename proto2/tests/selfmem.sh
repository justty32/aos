# self 與 memory 工具包。

selfmem_has() {
  case "$1" in *"$2=1"*) return 0 ;; *) return 1 ;; esac
}

test_selfmem_self_tools() {
  local root world home got
  root=$(make_world selfmem_self)
  world="$root/agent"; home="$world/agent"
  got=$(python3 - "$HERE" "$world" "$home" "$root/llm" <<'PYEOF2'
import datetime, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack

world, home, llm = sys.argv[2:5]
ctx = Ctx(world, home)
pack = load_pack(home, "self")

status = pack.run("self_status", {}, ctx)
status_ok = (status["history_tokens"] == status["history_chars"] // 3
             and status["history_pct"] == round(status["history_chars"] * 100 / 80000, 1))
time_result = pack.run("self_time", {}, ctx)
time_ok = set(time_result) == {"now", "started", "uptime_s"} and "T" in time_result["now"]

engines_path = os.path.join(llm, "engines.json")
engines = json.load(open(engines_path, encoding="utf-8"))
engine = engines[0]
engine["price"] = {"input": 1, "output": 2, "reasoning": 3, "cached": 0.5}
ctx.write_json(engines_path, engines)
day = datetime.date.today().isoformat()
key = "%s|%s" % (engine["base_url"], engine["model"])
ctx.write_json(os.path.join(llm, "usage", day + ".json"), {key: {
    "prompt_tokens": 1000000, "completion_tokens": 500000,
    "completion_tokens_details.reasoning_tokens": 100000,
    "prompt_cache_hit_tokens": 200000, "requests": 4}})
cost = pack.run("self_cost", {"day": day}, ctx)
cost_ok = (cost == {"prompt_tokens": 1000000, "completion_tokens": 500000,
                    "requests": 4, "cost_usd": 2.0})
engines[0].pop("price")
ctx.write_json(engines_path, engines)
no_price = pack.run("self_cost", {"day": day}, ctx)
null_ok = no_price["cost_usd"] is None
print("status=%d time=%d cost=%d null=%d" %
      (status_ok, time_ok, cost_ok, null_ok))
PYEOF2
)
  if selfmem_has "$got" status; then ok "selfmem：self_status 有估 token 與記憶門檻百分比"; else fail "self_status 不對：$got"; fi
  if selfmem_has "$got" cost; then ok "selfmem：self_cost 依四種單價算出這台引擎的花費"; else fail "self_cost 不對：$got"; fi
  if selfmem_has "$got" null; then ok "selfmem：self_cost 遇到沒有 price 的引擎回 null"; else fail "self_cost 無單價不對：$got"; fi
  if selfmem_has "$got" time; then ok "selfmem：self_time 只回現在、開機時間與秒數"; else fail "self_time 不對：$got"; fi
  rm -rf "$root"
}

test_selfmem_who() {
  local root world home got
  root=$(make_world selfmem_who)
  world="$root/agent"; home="$world/agent"
  "$AUSER" spawn "$world" kid "小孩" >/dev/null 2>&1
  got=$(python3 - "$HERE" "$world" "$home" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack

world, home = sys.argv[2:4]
pack = load_pack(home, "self")
parent = pack.run("self_who", {}, Ctx(world, home))
kid_world = os.path.join(home, "kids", "kid")
kid = pack.run("self_who", {}, Ctx(kid_world, kid_world))
print(parent["name"] == "agent" and parent["parent"] is None
      and parent["clock"] == "own" and parent["kids"] == {"count": 1, "names": ["kid"]}
      and kid["parent"] == world and kid["clock"] == "shared" and kid["llm_dir"] is not None)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "selfmem：self_who 用 parent／kids 說清楚父子與 shared 鐘"; else fail "self_who 不對：$got"; fi
  rm -rf "$root"
}

test_selfmem_memory_tools() {
  local root world home got
  root=$(make_world selfmem_tools)
  world="$root/agent"; home="$world/agent"
  got=$(python3 - "$HERE" "$world" "$home" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack

world, home = sys.argv[2:4]
ctx = Ctx(world, home, {"step": 7})
pack = load_pack(home, "memory")
history = [{"role": "user", "content": "第%d則內容" % n} for n in range(5)]
ctx.write_json(os.path.join(home, "prompts.json"), history)

listed = pack.run("memory_list", {"offset": 1, "count": 2}, ctx)
list_ok = [x["index"] for x in listed["items"]] == [1, 2] and listed["items"][0]["role"] == "user"

first = pack.run("memory_summarize_old", {"keep_recent": 2}, ctx)
summarize_ok = (len(first["old_messages"]) == 3 and "memory_replace_old" in first["next"]
                and len(json.load(open(os.path.join(home, "prompts.json"), encoding="utf-8"))) == 5)
second = pack.run("memory_replace_old", {"summary": "前三則的摘要"}, ctx)
now = json.load(open(os.path.join(home, "prompts.json"), encoding="utf-8"))
replace_ok = (second == {"replaced": 3, "remaining": 3}
              and now[0]["content"] == "（前面的對話摘要）前三則的摘要"
              and "pending_summary" not in ctx.state)

ctx.write_json(os.path.join(home, "prompts.json"), history[:4])
forgot = pack.run("memory_forget", {"from": 1, "to": 2}, ctx)
left = json.load(open(os.path.join(home, "prompts.json"), encoding="utf-8"))
forget_ok = forgot == {"forgotten": 2, "remaining": 2} and [x["content"] for x in left] == ["第0則內容", "第3則內容"]

saved = pack.run("note_save", {"title": "模型 設定", "text": "引擎要用 deepseek-flash"}, ctx)
note_name = os.path.basename(saved.get("path") or "")
save_ok = note_name.startswith("模型-設定-") and os.path.isfile(saved.get("path") or "")
found = pack.run("note_find", {"keyword": "deepseek"}, ctx)
find_ok = bool(len(found["notes"]) == 1 and found["notes"][0]["name"] == note_name
               and found["notes"][0]["matches"])
read = pack.run("note_read", {"name": note_name}, ctx)
read_ok = read["name"] == note_name and "deepseek-flash" in read["content"]

one = pack.run("self_note", {"text": "回答要短。"}, ctx)
two = pack.run("self_note", {"text": "先講結果。"}, ctx)
self_note_ok = one["lines"] == 1 and two["lines"] == 2
system = pack.on_system_prompt(ctx)
system_ok = system.endswith("回答要短。\n先講結果。")
archives = glob.glob(os.path.join(home, "memory", "forgotten", "*.json"))
replace_ok = replace_ok and len(archives) >= 1
forget_ok = forget_ok and len(archives) >= 2
print("list=%d summarize=%d replace=%d forget=%d save=%d find=%d read=%d selfnote=%d system=%d" %
      (list_ok, summarize_ok, replace_ok, forget_ok, save_ok, find_ok, read_ok,
       self_note_ok, system_ok))
PYEOF2
)
  if selfmem_has "$got" list; then ok "selfmem：memory_list 依 offset／count 列角色與預覽"; else fail "memory_list 不對：$got"; fi
  if selfmem_has "$got" summarize; then ok "selfmem：memory_summarize_old 回舊原文但不先改記憶"; else fail "memory_summarize_old 不對：$got"; fi
  if selfmem_has "$got" replace; then ok "selfmem：memory_replace_old 備份原文並換成摘要"; else fail "memory_replace_old 不對：$got"; fi
  if selfmem_has "$got" forget; then ok "selfmem：memory_forget 含頭含尾忘掉並備份"; else fail "memory_forget 不對：$got"; fi
  if selfmem_has "$got" save; then ok "selfmem：note_save 把標題與內容存成 Markdown"; else fail "note_save 不對：$got"; fi
  if selfmem_has "$got" find; then ok "selfmem：note_find 找到檔名與命中行"; else fail "note_find 不對：$got"; fi
  if selfmem_has "$got" read; then ok "selfmem：note_read 讀回找到的筆記"; else fail "note_read 不對：$got"; fi
  if selfmem_has "$got" selfnote; then ok "selfmem：self_note 只能逐行追加"; else fail "self_note 不對：$got"; fi
  if selfmem_has "$got" system; then ok "selfmem：self-note 會接進 system prompt"; else fail "self-note prompt 不對：$got"; fi
  rm -rf "$root"
}

test_selfmem_two_turn_summary() {
  local root world home reply got
  root=$(make_world selfmem_turns)
  world="$root/agent"; home="$world/agent"
  python3 - "$home/tools.json" "$home/prompts.json" <<'PYEOF2'
import json, sys
tools = json.load(open(sys.argv[1], encoding="utf-8"))
tools["packs"].append("memory")
json.dump(tools, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
history = [{"role": "user", "content": "要被摘要的舊話 %d" % n} for n in range(25)]
json.dump(history, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
  reply=$(say_and_wait "$world" "$root/llm" \
    'CALL memory_summarize_old {"keep_recent": 2} 然後 CALL memory_replace_old {"summary": "濃縮完成"}' 30) || true
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
home = sys.argv[1]
history = json.load(open(os.path.join(home, "prompts.json"), encoding="utf-8"))
state = json.load(open(os.path.join(home, "state.json"), encoding="utf-8"))
print(history[0].get("content") == "（前面的對話摘要）濃縮完成",
      "pending_summary" not in state,
      bool(glob.glob(os.path.join(home, "memory", "forgotten", "*.json"))))
PYEOF2
)
  if [ -n "$reply" ] && [ "$got" = "True True True" ]; then
    ok "selfmem：模型分兩格拿舊原文、寫摘要、再換掉舊記憶"
  else
    fail "兩格摘要沒走完：reply=$reply got=$got"
  fi
  rm -rf "$root"
}

test_selfmem_thresholds() {
  local root world home got
  root=$(make_world selfmem_nudge)
  world="$root/agent"; home="$world/agent"
  python3 - "$home/tools.json" "$home/prompts.json" <<'PYEOF2'
import json, sys
tools = json.load(open(sys.argv[1], encoding="utf-8")); tools["packs"] = ["memory"]
json.dump(tools, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump([{"role": "user", "content": "長" * 41000}], open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
h=sys.argv[1]; s=json.load(open(os.path.join(h,"state.json"), encoding="utf-8"))
print(len(glob.glob(os.path.join(h,"inbox","self","*.json"))) == 1,
      s.get("nudged_at_step") == 0, s.get("state") == "llm")
PYEOF2
)
  if [ "$got" = "True True True" ]; then ok "selfmem：記憶超過 40000 字就往 inbox/self 提醒一次"; else fail "40000 字提醒不對：$got"; fi
  rm -rf "$root"

  root=$(make_world selfmem_trim)
  world="$root/agent"; home="$world/agent"
  python3 - "$home/tools.json" "$home/prompts.json" <<'PYEOF2'
import json, sys
tools = json.load(open(sys.argv[1], encoding="utf-8")); tools["packs"] = ["memory"]
json.dump(tools, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
history = [{"role": "user", "content": ("第%d" % n) + "長" * 21000} for n in range(4)]
json.dump(history, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
h=sys.argv[1]; p=json.load(open(os.path.join(h,"prompts.json"), encoding="utf-8"))
a=glob.glob(os.path.join(h,"memory","forgotten","*.json"))
old=json.load(open(a[0], encoding="utf-8")) if a else []
print(len(p) == 3, p[0].get("content") == "（前面 2 則太長被截掉了）",
      len(old) == 2, not glob.glob(os.path.join(h,"inbox","self","*.json")))
PYEOF2
)
  if [ "$got" = "True True True True" ]; then ok "selfmem：記憶超過 80000 字就備份並硬砍最舊一半"; else fail "80000 字硬砍不對：$got"; fi
  rm -rf "$root"
}

test_selfmem_self_tools
test_selfmem_who
test_selfmem_memory_tools
test_selfmem_two_turn_summary
test_selfmem_thresholds
