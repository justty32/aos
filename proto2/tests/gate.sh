# 工作室閘門（任務 D）：每格都守、0 額度＝0 上限、整隊凍住與甲方追加、busy 才算 ticks、
# 未讀信重提醒、壞工具呼叫救回／重送。

gate_direct() { # gate_direct <成員世界> <文字>；user 來源直接放一封信
  python3 - "$HERE" "$1" "$2" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import put_mail, resolve_home
put_mail(resolve_home(sys.argv[2], None), "user", sys.argv[3], "user")
PYEOF2
}

gate_state() { # gate_state <世界> <python 表達式，d 是 state.json>
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
    "$1/state.json" "$2" 2>/dev/null
}

test_gate() {
  local root studio got status before after reply world
  root=$(mktemp -d "$TEST_RUN_DIR/gate.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1

  # ② 0 額度＝0 上限：chief 沒分到 tokens、也沒事做→安靜凍著不喊；收到信才一格都不動（step 不加、信留著），並報主管 pm 一次
  "$AGENT" exec "$studio/kids/chief" >/dev/null 2>&1
  got=$(gate_state "$studio/kids/chief" 'd.get("budget_block")=="own:tokens" and "budget_told" not in d')
  if [ "$got" = "True" ] && [ ! -d "$studio/kids/pm/inbox/budget" ]; then
    ok "gate：0 額度但沒事做的人安靜凍著，不吵主管"
  else
    fail "gate：沒事做也喊了（$got）"
  fi
  gate_direct "$studio/kids/chief" "chief 你在嗎"
  before=$(gate_state "$studio/kids/chief" 'd["step"]')
  "$AGENT" exec "$studio/kids/chief" >/dev/null 2>&1
  "$AGENT" exec "$studio/kids/chief" >/dev/null 2>&1
  after=$(gate_state "$studio/kids/chief" 'd["step"]')
  got=$(gate_state "$studio/kids/chief" 'd.get("budget_block")=="own:tokens" and d.get("frozen_ticks")==3')
  if [ "$got" = "True" ] && [ "$before" = "$after" ] \
     && [ "$(find "$studio/kids/chief/inbox/user" -maxdepth 1 -name '*.json' | wc -l)" = "1" ]; then
    ok "gate：0 額度的成員整格凍住（step 不加、信留著）"
  else
    fail "gate：0 額度沒凍住（got=$got step $before→$after）"
  fi
  got=$(find "$studio/kids/pm/inbox/budget" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  if [ "$got" = "1" ]; then ok "gate：凍住只報主管一次"; else fail "gate：報主管的信 $got 封"; fi
  python3 - "$studio/kids/chief/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d["frozen_ticks"] = 300
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  "$AGENT" exec "$studio/kids/chief" >/dev/null 2>&1
  got=$(find "$studio/kids/pm/inbox/budget" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  if [ "$got" = "2" ]; then ok "gate：凍滿 300 格還沒人理就再喊一次"; else fail "gate：300 格再喊不對（$got 封）"; fi
  python3 - "$studio/kids/chief/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d["frozen_ticks"] = 3
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2

  # 主管 team_grant 後自然解凍，接著走原本的信
  python3 - "$HERE" "$studio" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import team
root = sys.argv[2]
ctx = Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm"))
r = team.run("team_grant", {"role": "chief", "amount": 100}, ctx)
assert r.get("ok") is True, r
PYEOF2
  "$AGENT" exec "$studio/kids/chief" >/dev/null 2>&1
  got=$(gate_state "$studio/kids/chief" '"budget_block" not in d and "frozen_ticks" not in d and d["state"]=="llm" and d["step"]=='"$after"'+1')
  if [ "$got" = "True" ]; then ok "gate：主管分了額度就解凍、接著處理那封信"; else fail "gate：解凍不對（$(cat "$studio/kids/chief/state.json")）"; fi

  # ⑥ ticks 只算 busy：team status 的 ticks 等於各人 busy 的和，不是 step
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import team_status_of
d = team_status_of(sys.argv[2])
print(all(r["today_spent"]["ticks"] == r["busy"] for r in d["members"])
      and d["spent"]["ticks"] == sum(r["busy"] for r in d["members"])
      and "in_flight" in d and all("in_flight" in r and "blocked" in r for r in d["members"]))
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：ticks 只算 busy 格，每列有在途與擋住欄"; else fail "gate：ticks／在途欄不對（$got）"; fi

  # ① 整隊用完→全隊凍住，只有 sales 開口；⑦ 甲方 team budget --add 追加後全隊解凍
  python3 - "$studio/team/budget.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; b = json.load(open(p, encoding="utf-8"))
b["total"]["hours"] = 0.000001
json.dump(b, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  gate_direct "$studio/kids/sales" "還在嗎"
  gate_direct "$studio/kids/pm" "還在嗎"
  before=$(find "$studio/kids/pm/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  "$AGENT" exec "$studio/kids/sales" >/dev/null 2>&1
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  after=$(find "$studio/kids/pm/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
  reply=$(grep -l "整隊額度用完" "$studio"/kids/sales/outbox/*.json 2>/dev/null | head -1)
  got=$(gate_state "$studio/kids/sales" 'd.get("budget_block")=="team:hours"')
  if [ "$got" = "True" ] && [ -n "$reply" ] && grep -q "team budget" "$reply" \
     && [ "$(gate_state "$studio/kids/pm" 'd.get("budget_block")')" = "team:hours" ] && [ "$before" = "$after" ]; then
    ok "gate：整隊用完全隊凍住，只有 sales 開口問甲方（含追加指令）"
  else
    fail "gate：整隊凍住不對（sales=$got reply=$reply pm=$(gate_state "$studio/kids/pm" 'd.get("budget_block")') outbox $before→$after）"
  fi
  status=$("$AUSER" team status "$studio" 2>&1)
  case "$status" in
    *"team:hours"*) ok "gate：team status 看得到被擋原因" ;;
    *) fail "gate：team status 沒印擋住原因（$status）" ;;
  esac
  "$AUSER" team budget "$studio" --add '{"hours": 5, "tokens": 500}' >/dev/null 2>&1; RC=$?
  got=$(python3 - "$studio/team/budget.json" <<'PYEOF2'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
print(abs(b["total"]["hours"] - 5.000001) < 1e-6 and b["total"]["tokens"] == 1500
      and b["allocations"]["owner"]["tokens"] == 600 and b["grants"][-1]["from"] == "user"
      and b["grants"][-1]["kind"] == "top_up")
PYEOF2
)
  if [ "$RC" = "0" ] && [ "$got" = "True" ]; then ok "gate：team budget --add 加總額、給 leader、記一筆"; else fail "gate：追加沒寫對（rc=$RC got=$got）"; fi
  "$AGENT" exec "$studio/kids/sales" >/dev/null 2>&1
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  if [ "$(gate_state "$studio/kids/sales" '"budget_block" in d')" = "False" ] \
     && [ "$(gate_state "$studio/kids/pm" '"budget_block" in d')" = "False" ]; then
    ok "gate：追加後全隊解凍"
  else
    fail "gate：追加後沒解凍（sales=$(cat "$studio/kids/sales/state.json")）"
  fi
  "$AUSER" team budget "$studio" --add '{"tokens": -1}' >/dev/null 2>&1; RC=$?
  check "gate：追加負數被擋" 2 "$RC"

  # ⑤ 已通知但未讀的信：idle 滿 30 格再提醒一次（preset 現在 inline_mail 全開，這段先把 pm 的關掉）
  python3 - "$studio/kids/pm/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d.pop("inline_mail", None)
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  python3 - "$HERE" "$studio" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
root = sys.argv[2]
Ctx(os.path.join(root, "kids", "sales"), os.path.join(root, "kids", "sales")).put_mail("pm", "sales", "訂單來了")
PYEOF2
  # pm 現在可能在 llm/wait；把它拉回 idle 空手狀態來測提醒
  python3 - "$studio/kids/pm/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.update({"state": "idle", "request": "", "pending": [], "step": 100})
d.pop("sleeping", None); d.pop("unread_told_step", None); d["announced"] = []
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1      # 第一次通知
  got=$(gate_state "$studio/kids/pm" 'd.get("unread_told_step")==100 and d["state"]=="llm"')
  python3 - "$studio/kids/pm/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.update({"state": "idle", "request": "", "step": 110})   # 假裝模型讀信失敗又回 idle，才過 10 格
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  got2=$(gate_state "$studio/kids/pm" 'd["state"]=="idle" and d.get("unread_told_step")==100')
  python3 - "$studio/kids/pm/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.update({"state": "idle", "request": "", "step": 130})   # 滿 30 格
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  got3=$(gate_state "$studio/kids/pm" 'd["state"]=="llm" and d.get("unread_told_step")==130')
  got4=$(python3 -c 'import json,sys; h=json.load(open(sys.argv[1])); print(any("提醒：你還有沒讀的信" in (m.get("content") or "") for m in h if m.get("role")=="user"))' "$studio/kids/pm/prompts.json")
  if [ "$got" = "True" ] && [ "$got2" = "True" ] && [ "$got3" = "True" ] && [ "$got4" = "True" ]; then
    ok "gate：已通知但沒讀的信，idle 滿 30 格會再提醒一次"
  else
    fail "gate：未讀提醒不對（$got $got2 $got3 $got4）"
  fi
  # 睡著等回信也照提醒、而且被叫醒（互等死結：PM 等 chief 回信、chief 等 PM 補額度）
  python3 - "$studio/kids/pm/state.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.update({"state": "idle", "request": "", "step": 170, "unread_told_step": 130,
          "sleeping": {"kind": "mail", "id": "pm-mail-x"},
          "pending": [{"id": "pm-mail-x", "kind": "mail", "pack": "communication",
                       "since_ts": 9999999999, "timeout_s": 600, "mail_reply_to": "nothing.json"}]})
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  got=$(gate_state "$studio/kids/pm" 'd["state"]=="llm" and d.get("unread_told_step")==170 and not d.get("sleeping") and len(d.get("pending"))==1')
  if [ "$got" = "True" ]; then ok "gate：睡著等回信時未讀提醒照發、叫醒它，旁線 pending 留著"; else fail "gate：睡著時的提醒不對（$(cat "$studio/kids/pm/state.json")）"; fi
  unset AOS_LLM_DIR

  # ③ 模型把工具呼叫寫成文字：認得的救回來當正式 tool_call 真的跑
  root=$(make_world gate_salvage)
  world="$root/agent"
  reply=$(say_and_wait "$world" "$root/llm" 'BROKEN 請叫 say' 20) || true
  got=$(python3 - "$world/agent/prompts.json" <<'PYEOF2'
import json, sys
h = json.load(open(sys.argv[1], encoding="utf-8"))
calls = [c for m in h if m.get("role") == "assistant" for c in (m.get("tool_calls") or [])]
print(bool(calls) and calls[0]["id"].startswith("salvaged") and calls[0]["function"]["name"] == "say"
      and json.loads(calls[0]["function"]["arguments"])["text"] == "救回來的"
      and not any("<tool_call>" in (m.get("content") or "") for m in h))
PYEOF2
)
  if [ "$got" = "True" ] && [ -f "$world/said.txt" ] && grep -q "救回來的" "$world/said.txt"; then
    ok "gate：寫成文字的工具呼叫救回來、真的跑了"
  else
    fail "gate：救回失敗（got=$got said=$(cat "$world/said.txt" 2>/dev/null)）"
  fi
  rm -rf "$root"

  # ③ 工具名: {參數} 寫在 plaintext 圍欄裡，也救得回來
  root=$(make_world gate_plaintext)
  world="$root/agent"
  reply=$(say_and_wait "$world" "$root/llm" 'PLAINTEXT 請叫 say' 20) || true
  if [ -f "$world/said.txt" ] && grep -q "純文字救回" "$world/said.txt"; then
    ok "gate：「工具名: {參數}」寫成文字也救回來跑了"
  else
    fail "gate：plaintext 形式沒救回（said=$(cat "$world/said.txt" 2>/dev/null)）"
  fi
  rm -rf "$root"

  # ③ 救不回來：同題重送一次，第二次正常就照常回話，壞文字不進記憶
  root=$(make_world gate_retry)
  world="$root/agent"
  reply=$(say_and_wait "$world" "$root/llm" 'GARBLED 隨便說' 20) || true
  got=$(python3 - "$world/agent/prompts.json" "$world/agent/state.json" <<'PYEOF2'
import json, sys
h = json.load(open(sys.argv[1], encoding="utf-8"))
s = json.load(open(sys.argv[2], encoding="utf-8"))
print(not any("<tool_call>" in (m.get("content") or "") for m in h)
      and any((m.get("content") or "") == "重送後正常" for m in h if m.get("role") == "assistant")
      and "protocol_retries" not in s)
PYEOF2
)
  if [ "$got" = "True" ] && [ -n "$reply" ] && grep -q "重送後正常" "$reply"; then
    ok "gate：救不回來的壞回覆同題重送一次，壞文字不進記憶"
  else
    fail "gate：重送不對（got=$got reply=$reply）"
  fi
  rm -rf "$root"
}

test_gate

# code 包：工作室成員家裡的 team/ 是 symlink，指到共用區也算「專案裡面」
test_gate_code_symlink() {
  local root studio got
  root=$(mktemp -d "$TEST_RUN_DIR/gatecode.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  AOS_LLM_DIR="$root/llm" "$AUSER" team new "$studio" --preset studio --engine local >/dev/null 2>&1
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import code
root = sys.argv[2]
world = os.path.join(root, "kids", "chief")
os.makedirs(os.path.join(root, "team", "projects", "todo"), exist_ok=True)
open(os.path.join(root, "team", "projects", "todo", "todo.py"), "w").write("print(1)\n")
ctx = Ctx(world, world)
inside = code._project(ctx, "team/projects/todo/todo.py")
try:
    code._project(ctx, "../pm/prompts.json"); outside = False
except ValueError:
    outside = True
print(os.path.isfile(inside) and outside)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：code 包認共用區 team/ 是裡面、別人家還是外面"; else fail "gate：code 包 symlink 判定不對（$got）"; fi
  rm -rf "$root"
}

test_gate_code_symlink

# 提效核心：工具白名單 only、信直接進 prompt inline_mail、額度自動撥 auto_grant、資產複製
test_gate_efficiency() {
  local root studio got
  root=$(mktemp -d "$TEST_RUN_DIR/gateeff.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' >/dev/null 2>&1
  # only：pm 的 tools.json 有白名單，送模型的工具只剩白名單裡有、而且真的載得到的
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import load_packs, tool_specs, tools_only, inline_sources
home = os.path.join(sys.argv[2], "kids", "pm")
loaded, extra = load_packs(home)
allof = {t["name"] for t in tool_specs(loaded, extra)}
sent = {t["name"] for t in tool_specs(loaded, extra, tools_only(home))}
print(sent <= set(tools_only(home)) and "team_grant" in sent and "inbox_read" in allof and "inbox_read" not in sent
      and inline_sources(home) == ["*"])
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：only 白名單只送列到的工具，inline_mail 有寫進成員 tools.json"; else fail "gate：only／inline_mail 不對（$got）"; fi
  # inline_mail：sales 寄給 pm 的信整封進記憶、當場搬進 read/，不再只通知
  python3 - "$HERE" "$studio" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
root = sys.argv[2]
Ctx(os.path.join(root, "kids", "sales"), os.path.join(root, "kids", "sales")).put_mail("pm", "sales", "整封信的內容在這裡")
PYEOF2
  "$AGENT" exec "$studio/kids/pm" >/dev/null 2>&1
  got=$(python3 - "$studio/kids/pm" <<'PYEOF2'
import json, os, sys
h = json.load(open(os.path.join(sys.argv[1], "prompts.json"), encoding="utf-8"))
s = json.load(open(os.path.join(sys.argv[1], "state.json"), encoding="utf-8"))
last = h[-1] if h else {}
print(last.get("role") == "user" and "[sales] 整封信的內容在這裡" in (last.get("content") or "")
      and "你有新信" not in (last.get("content") or "")
      and not os.listdir(os.path.join(sys.argv[1], "inbox", "sales")) == [] and s["state"] == "llm"
      and all(n == "read" for n in os.listdir(os.path.join(sys.argv[1], "inbox", "sales"))))
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：inline_mail 的信整封進 prompt、當場搬進 read/"; else fail "gate：inline_mail 不對（$got）"; fi
  # auto_grant：dev-a 0 額度收到信，閘門直接從 pm 撥 50000、當格解凍、記一筆 kind auto
  python3 - "$HERE" "$studio" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
root = sys.argv[2]
Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm")).put_mail("dev-a", "pm", "做這個")
PYEOF2
  "$AGENT" exec "$studio/kids/dev-a" >/dev/null 2>&1
  got=$(python3 - "$studio" <<'PYEOF2'
import json, os, sys
root = sys.argv[1]
b = json.load(open(os.path.join(root, "team", "budget.json"), encoding="utf-8"))
s = json.load(open(os.path.join(root, "kids", "dev-a", "state.json"), encoding="utf-8"))
g = b["grants"][-1] if b["grants"] else {}
print(g.get("kind") == "auto" and g.get("from") == "pm" and g.get("to") == "dev-a" and g["amount"]["tokens"] == 50000
      and b["allocations"]["dev-a"]["tokens"] == 50000 and "budget_block" not in s and s["state"] == "llm"
      and not os.path.isdir(os.path.join(root, "kids", "chief", "inbox", "budget")))
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：auto_grant 從 pm 自動撥 50000、當格解凍、不寄信"; else fail "gate：auto_grant 不對（$got）"; fi
  # 池子乾了：pm 與 owner 都沒剩 → 才寄主管，並替 sales 對甲方喊追加
  python3 - "$studio/team/budget.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]; b = json.load(open(p, encoding="utf-8"))
b["allocations"]["pm"]["tokens"] = 0; b["allocations"]["owner"]["tokens"] = 0; b["allocations"]["dev-b"]["tokens"] = 0
json.dump(b, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  python3 - "$HERE" "$studio" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
root = sys.argv[2]
Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm")).put_mail("dev-b", "pm", "做那個")
PYEOF2
  "$AGENT" exec "$studio/kids/dev-b" >/dev/null 2>&1
  got=$(python3 - "$studio" <<'PYEOF2'
import glob, json, os, sys
root = sys.argv[1]
s = json.load(open(os.path.join(root, "kids", "dev-b", "state.json"), encoding="utf-8"))
mail = glob.glob(os.path.join(root, "kids", "chief", "inbox", "budget", "*.json"))
out = sorted(glob.glob(os.path.join(root, "kids", "sales", "outbox", "*.json")))
last = json.load(open(out[-1], encoding="utf-8")) if out else {}
print(s.get("budget_block") == "own:tokens" and bool(mail) and "撥不出來" in (last.get("content") or "")
      and "team budget" in (last.get("content") or ""))
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：撥錢的池子乾了才寄主管，並替 sales 向甲方喊追加"; else fail "gate：池子乾了的路不對（$got）"; fi
  # 資產：preset 有 assets/ 就整包進 team/assets/
  if [ -d "$HERE/presets/studio/assets" ]; then
    if [ -d "$studio/team/assets" ] && [ "$(ls "$studio/team/assets" | wc -l)" -ge 1 ]; then ok "gate：preset 的 assets 複製進 team/assets"; else fail "gate：assets 沒複製"; fi
  fi
  unset AOS_LLM_DIR
  rm -rf "$root"
}

test_gate_efficiency

test_gate_llm_retry() {
  # 模型回錯（500、打不通、找不到執行檔）之後：以前直接回 idle、信已標讀、對話尾巴那句永遠沒人再送。
  # 現在：記一筆 llm_errors，20 格後重送；連錯 5 次放著並喊一次；新信來了整個重來。
  local root world home got
  root=$(make_world gate_retry)
  world="$root/agent"
  home=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from aos_agent import resolve_home; print(resolve_home(sys.argv[2], None))' "$HERE" "$world")
  say_and_wait "$world" "$root/llm" 'HTTP500 第一句' 20 >/dev/null || true
  got=$(python3 - "$home" <<'PYEOF2'
import json, os, sys
home = sys.argv[1]
s = json.load(open(os.path.join(home, "state.json"), encoding="utf-8"))
h = json.load(open(os.path.join(home, "prompts.json"), encoding="utf-8"))
print(s.get("state") == "idle" and s.get("llm_errors") == 1 and isinstance(s.get("llm_error_step"), int)
      and h and h[-1]["role"] == "user")
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：模型回錯後記一筆、對話尾巴留著那句沒人回"; else fail "gate：回錯沒記到（$got）"; fi
  # 還沒滿 20 格：不重送、閒著那幾格不算每題動作格；滿了：重送（state 走到 llm）
  agent_tick "$world"; agent_tick "$world"; agent_tick "$world"
  got=$(gate_state "$home" 'd.get("state")')
  if [ "$(gate_state "$home" 'd.get("question_steps")')" = "$(gate_state "$home" 'd.get("question_steps")')" ] \
     && [ "$(gate_state "$home" 'int(d.get("question_steps") or 0) < 5')" = "True" ]; then
    ok "gate：等重送那幾格不算每題動作格"
  else fail "gate：等重送燒掉了 question_steps（$(gate_state "$home" 'd.get("question_steps")')）"; fi
  python3 - "$home" <<'PYEOF2'
import json, os, sys
p = os.path.join(sys.argv[1], "state.json"); s = json.load(open(p, encoding="utf-8"))
s["step"] = int(s.get("llm_error_step") or 0) + 20; json.dump(s, open(p, "w", encoding="utf-8"))
PYEOF2
  agent_tick "$world"
  got="$got $(gate_state "$home" 'd.get("state")')"
  if [ "$got" = "idle llm" ]; then ok "gate：沒滿 20 格不重送、滿了就重送"; else fail "gate：重送時機不對（$got）"; fi
  # 連錯 5 次：放著、喊一次；新信來就再試
  python3 - "$home" <<'PYEOF2'
import json, os, sys
p = os.path.join(sys.argv[1], "state.json"); s = json.load(open(p, encoding="utf-8"))
s.update({"state": "idle", "llm_errors": 5, "llm_error_step": 0, "step": 100, "request": ""}); json.dump(s, open(p, "w", encoding="utf-8"))
PYEOF2
  agent_tick "$world"; agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
home = sys.argv[1]
s = json.load(open(os.path.join(home, "state.json"), encoding="utf-8"))
outs = [json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(home, "outbox", "*.json"))]
gave = [o for o in outs if "連續出錯" in (o.get("content") or "")]
print(s.get("state") == "idle" and s.get("llm_gave_up") is True and len(gave) == 1)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "gate：連錯 5 次就放著、只喊一次"; else fail "gate：放棄那段不對（$got）"; fi
  "$AUSER" say "$world" "新的一句" >/dev/null 2>&1
  agent_tick "$world"
  got=$(gate_state "$home" 'd.get("state") == "llm" and "llm_gave_up" not in d')
  if [ "$got" = "True" ]; then ok "gate：新信來了，放棄的那句跟著再試"; else fail "gate：新信沒讓它再試（$got）"; fi
  rm -rf "$root"
}

test_gate_llm_retry

test_gate_grant_retry() {
  # 個人額度凍住、喊過主管之後，天花板（max_per_member）抬高：以前要等 300 格才再試撥款，現在每 10 格試一次
  local root studio got
  root=$(mktemp -d "$TEST_RUN_DIR/gate_regrant.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1
  python3 - "$studio" <<'PYEOF2'
import json, os, sys
root = sys.argv[1]
p = os.path.join(root, "team", "team.json"); d = json.load(open(p, encoding="utf-8"))
d["auto_grant"] = {"from": ["pm"], "tokens": 50000, "max_per_member": 60000}   # dev-a 20000 + 50000 > 60000 → 撥不了
json.dump(d, open(p, "w", encoding="utf-8"))
p = os.path.join(root, "team", "budget.json"); b = json.load(open(p, encoding="utf-8"))
b["allocations"]["dev-a"]["tokens"] = 20000; json.dump(b, open(p, "w", encoding="utf-8"))
u = os.path.join(os.path.dirname(root), "llm", "usage"); os.makedirs(u, exist_ok=True)   # LLM 資料夾在 studio 旁邊
import datetime
day = datetime.date.today().isoformat()
json.dump({"by-requester": {"studio/dev-a": {"tokens": 25000, "prompt_tokens": 20000, "completion_tokens": 5000, "total_tokens": 25000, "requests": 1}}},
          open(os.path.join(u, day + ".json"), "w", encoding="utf-8"))
p = os.path.join(root, "kids", "dev-a", "state.json"); s = json.load(open(p, encoding="utf-8"))
s.update({"state": "act"}); json.dump(s, open(p, "w", encoding="utf-8"))
PYEOF2
  "$AGENT" exec "$studio/kids/dev-a" >/dev/null 2>&1
  got=$(gate_state "$studio/kids/dev-a" 'd.get("budget_block")=="own:tokens" and d.get("budget_told")=="own:tokens"')
  if [ "$got" = "True" ]; then ok "gate：撞天花板撥不了，凍住並喊主管"; else fail "gate：撞天花板那格不對（$got）"; fi
  python3 - "$studio" <<'PYEOF2'
import json, os, sys
p = os.path.join(sys.argv[1], "team", "team.json"); d = json.load(open(p, encoding="utf-8"))
d["auto_grant"]["max_per_member"] = 300000; json.dump(d, open(p, "w", encoding="utf-8"))
PYEOF2
  local i=0
  while [ "$i" -lt 12 ]; do "$AGENT" exec "$studio/kids/dev-a" >/dev/null 2>&1; i=$((i + 1)); done
  got=$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); print("budget_block" not in s and b["allocations"]["dev-a"]["tokens"] == 70000 and any(g.get("kind")=="auto" for g in b["grants"]))' \
    "$studio/kids/dev-a/state.json" "$studio/team/budget.json")
  if [ "$got" = "True" ]; then ok "gate：天花板抬高後 10 格內自動撥款解凍"; else fail "gate：抬高天花板沒解凍（$got）"; fi
  unset AOS_LLM_DIR
  rm -rf "$root"
}

test_gate_grant_retry

