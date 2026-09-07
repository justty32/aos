# 小型工作室 preset、整隊 CLI、預算工具與四段轉信。

studio_assert() {
  local got=$1 label=$2
  if [ "$got" = "True" ]; then ok "$label"; else fail "$label"; fi
}

studio_pump() { # studio_pump <根世界> <llm> [輪數]
  local i=0 max=${3:-16}
  while [ "$i" -lt "$max" ]; do
    "$AOS" "$1" >/dev/null 2>&1
    llm_pump "$2" >/dev/null
    i=$((i + 1))
  done
}

studio_wait_mail() { # studio_wait_mail <根世界> <llm> <收件人 home> <來源>
  local i=0
  while [ "$i" -lt 30 ]; do
    if find "$3/inbox/$4" "$3/inbox/$4/read" -maxdepth 1 -name '*.json' 2>/dev/null | grep -q .; then
      return 0
    fi
    "$AOS" "$1" >/dev/null 2>&1
    llm_pump "$2" >/dev/null
    i=$((i + 1))
  done
  return 1
}

studio_direct() { # studio_direct <成員世界> <文字>
  python3 - "$HERE" "$1" "$2" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import put_mail, resolve_home
put_mail(resolve_home(sys.argv[2], None), "user", sys.argv[3], "user")
PYEOF2
}

test_studio() {
  local root studio checks out order_file got status reply
  root=$(mktemp -d "$TEST_RUN_DIR/studio.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  export AOS_USER_DIR="$root/user"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1

  checks="$root/checks.json"
  python3 - "$studio" "$checks" <<'PYEOF2'
import json, os, sys
root, output = sys.argv[1:3]
names = ["owner", "sales", "pm", "chief", "dev-a", "dev-b", "tester", "qa"]
roster = json.load(open(os.path.join(root, "team", "team.json"), encoding="utf-8"))
members = {m["name"]: m for m in roster["members"]}
worlds = {name: root if name == "owner" else os.path.join(root, "kids", name) for name in names}
checks = {}
checks["worlds"] = all(os.path.isfile(os.path.join(path, ".aos", "inst")) for path in worlds.values())
checks["roster"] = (set(members) == set(names) and members["chief"]["reports_to"] == "pm"
                    and members["owner"]["budget_pct"] == 10 and members["pm"]["budget_pct"] == 85
                    and members["sales"]["budget_pct"] == 5)
checks["team_files"] = (os.path.isdir(os.path.join(root, "team", "projects"))
                        and all(os.path.isfile(os.path.join(root, "team", name))
                                for name in ("team.json", "budget.json", "progress.md")))
checks["contacts"] = True
for name, world in worlds.items():
    contacts = json.load(open(os.path.join(world, "contacts.json"), encoding="utf-8"))
    expected = set(names) - {name}
    if name == "sales": expected.add("user")
    checks["contacts"] &= set(contacts) == expected
checks["clocks"] = (members["owner"]["clock"] == "own" and members["chief"]["clock"] == "own"
                    and all(members[n]["clock"] == "shared:owner"
                            for n in ("sales", "pm", "dev-a", "dev-b", "tester", "qa")))
checks["engine"] = all(json.load(open(os.path.join(path, "llm.json"), encoding="utf-8"))["engine"] == "local"
                       for path in worlds.values())
json.dump(checks, open(output, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  for item in \
    'worlds|studio：team new 建出八個世界' \
    'roster|studio：名冊、主管與 10/5/85 初始分配正確' \
    'team_files|studio：team 共用區、三個主檔都在' \
    'contacts|studio：全員雙向通訊錄，只有 sales 有 user' \
    'clocks|studio：owner/chief own，其餘 shared owner' \
    'engine|studio：--engine 一次蓋掉全隊引擎'; do
    studio_assert "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$checks" "${item%%|*}")" "${item#*|}"
  done

  "$AUSER" order "$studio" "做 todo.py" --budget '{"tokens":500,"hours":1}' \
    --accept "加列刪都能用" >/dev/null
  order_file=$(find "$studio/kids/sales/inbox/user" -maxdepth 1 -name 'order-*.json' | head -1)
  got=$(python3 - "$order_file" <<'PYEOF2'
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
b=json.loads(d["content"])
print(d["from"] == "user" and d["to"] == "sales" and b["order"] == "做 todo.py"
      and b["budget"]["tokens"] == 500 and b["acceptance"] == ["加列刪都能用"]
      and b["out_of_scope"] == [])
PYEOF2
)
  studio_assert "$got" "studio：order 落進 sales inbox，固定格式正確"

  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import team
root=sys.argv[2]
ctx=Ctx(os.path.join(root,"kids","pm"), os.path.join(root,"kids","pm"))
r=team.run("team_grant", {"role":"dev-a", "amount":{"tokens":120,"ticks":70}}, ctx)
b=json.load(open(os.path.join(root,"team","budget.json"), encoding="utf-8"))
print(r.get("ok") is True and b["allocations"]["dev-a"]["tokens"] == 120
      and b["allocations"]["pm"]["tokens"] == 730
      and b["allocations"]["dev-a"]["ticks"] == 70 and len(b["grants"]) == 1)
PYEOF2
)
  studio_assert "$got" "studio：team_grant 從 PM 分額度並寫帳"

  status=$("$AUSER" team status "$studio" 2>&1)
  case "$status" in
    *"INFLIGHT"*"owner"*"sales"*"dev-a"*"在途：主線"*"今天花費"*"整隊剩餘"*) ok "studio：team status 印得出整隊欄位與在途筆數" ;;
    *) fail "studio：team status 輸出不全（$status）" ;;
  esac

  # 用共用假 server 真走工具呼叫。每段用 user 提示假模型要叫哪個工具；實際信都由 communication 寄。
  "$AUSER" say "$studio" 'CALL mail_send {"to":"pm","content":"訂單轉交 PM"}' >/dev/null 2>&1
  studio_wait_mail "$studio" "$root/llm" "$studio/kids/pm" sales || true
  studio_direct "$studio/kids/pm" $'CALL say {}\nCALL mail_send {"to":"dev-a","content":"工作單交 dev-a"}'
  studio_wait_mail "$studio" "$root/llm" "$studio/kids/dev-a" pm || true
  studio_direct "$studio/kids/dev-a" $'CALL say {}\nCALL mail_send {"to":"pm","content":"dev-a 已完成"}'
  studio_wait_mail "$studio" "$root/llm" "$studio/kids/pm" dev-a || true
  got=$(python3 - "$studio" <<'PYEOF2'
import glob, json, os, sys
r=sys.argv[1]
def has(path, text):
    paths=glob.glob(path)
    folder=os.path.dirname(path)
    paths += glob.glob(os.path.join(folder,"read","*.json"))
    for p in paths:
        d=json.load(open(p, encoding="utf-8"))
        if text in str(d.get("content") or ""): return True
    return False
a=has(os.path.join(r,"kids","pm","inbox","sales","*.json"), "訂單轉交")
b=has(os.path.join(r,"kids","dev-a","inbox","pm","*.json"), "工作單")
c=has(os.path.join(r,"kids","pm","inbox","dev-a","*.json"), "已完成")
if a and b and c:
    print("True")
else:
    prompts=json.load(open(os.path.join(r,"kids","pm","prompts.json"),encoding="utf-8"))
    trace=[]
    for m in prompts:
        calls=[x.get("function",{}).get("name") for x in m.get("tool_calls",[])]
        if calls or m.get("role")=="tool": trace.append("%s:%s:%s"%(m.get("role"),calls,(m.get("content") or "")[:160]))
    print("sales-pm=%s pm-dev=%s dev-pm=%s trace=%s" % (a,b,c,"|".join(trace[-8:])))
PYEOF2
)
  studio_assert "$got" "studio：假 server 走完 sales→pm→dev→pm 四段信（$got）"

  # team_grant 是硬閘門：dev-a 用滿 120 token 後，不再叫 LLM，改報 chief。
  llm_pump "$root/llm" >/dev/null
  python3 - "$root/llm/usage/$(date +%Y-%m-%d).json" <<'PYEOF2'
import json,os,sys
p=sys.argv[1];d=json.load(open(p,encoding="utf-8")) if os.path.isfile(p) else {}
d.setdefault("by-requester",{})["studio/dev-a"]={"total_tokens":120}
json.dump(d,open(p,"w",encoding="utf-8"),ensure_ascii=False)
root=os.path.dirname(os.path.dirname(os.path.dirname(p)))
state=os.path.join(root,"studio","kids","dev-a","state.json")
s=json.load(open(state,encoding="utf-8"));s.pop("budget_block",None)
json.dump(s,open(state,"w",encoding="utf-8"),ensure_ascii=False)
PYEOF2
  studio_direct "$studio/kids/dev-a" "這題會被額度擋住"
  for _ in 1 2 3 4 5; do
    "$AGENT" exec "$studio/kids/dev-a" >/dev/null 2>&1
    if python3 -c 'import json,sys;print(bool(json.load(open(sys.argv[1])).get("budget_block")))' \
      "$studio/kids/dev-a/state.json" | grep -q True; then break; fi
    llm_pump "$root/llm" >/dev/null
  done
  got=$(python3 - "$studio" <<'PYEOF2'
import glob,json,os,sys
r=sys.argv[1];h=os.path.join(r,"kids","dev-a")
s=json.load(open(os.path.join(h,"state.json"),encoding="utf-8"))
mail=glob.glob(os.path.join(r,"kids","chief","inbox","budget","*.json"))
print(str(s.get("budget_block","")).startswith("own:tokens") and bool(mail)
      and "額度用完" in json.load(open(mail[-1],encoding="utf-8")).get("content",""))
PYEOF2
)
  studio_assert "$got" "studio：角色用滿 team_grant 後硬停並報主管"

  python3 - "$studio/kids/sales/outbox/9999.json" <<'PYEOF2'
import json, os, sys
os.makedirs(os.path.dirname(sys.argv[1]), exist_ok=True)
json.dump({"role":"assistant","content":"sales 交付單"}, open(sys.argv[1],"w",encoding="utf-8"), ensure_ascii=False)
PYEOF2
  reply=$("$AUSER" listen "$studio" --once)
  case "$reply" in *"sales 交付單"*) ok "studio：listen 工作室根就是看 sales 回覆" ;; *) fail "studio：listen 沒看 sales（$reply）" ;; esac

  "$AUSER" team stop "$studio" >/dev/null 2>&1
  got=$(python3 -c 'import json,sys; print(all(not m["active"] for m in json.load(open(sys.argv[1]))["members"]))' \
        "$studio/team/team.json")
  studio_assert "$got" "studio：team stop 標整隊停止並保留檔案"
  unset AOS_USER_DIR
  unset AOS_LLM_DIR
}

test_studio

# team why／team tail：一個人在旁邊看整隊時要的兩件事。
test_studio_watch() {
  local root studio checks why line_count only tail_out
  root=$(mktemp -d "$TEST_RUN_DIR/studiowatch.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":200000,"hours":8,"ticks":500,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1

  # 假一點狀態：pm 在等一發排在第二的請求、有一封 chief 的未讀信；dev-a 額度用完凍住；
  # qa 睡著等回信；chief 手上有一張 assigned 的任務；dev-b 留一段有工具的對話。
  python3 - "$root" <<'PYEOF2'
import json, os, sys, time
root = sys.argv[1]
studio, llm = os.path.join(root, "studio"), os.path.join(root, "llm")
def wr(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False)
wr(os.path.join(llm, "requests", "aaa-first.json"), {"priority": 5, "messages": []})
wr(os.path.join(llm, "requests", "pm-req.json"), {"priority": 1, "messages": []})
wr(os.path.join(studio, "kids/pm/state.json"),
   {"state": "wait", "step": 120, "busy": 80, "request": "pm-req.json", "wait_ticks": 41})
wr(os.path.join(studio, "kids/pm/inbox/chief/x1.json"), {"from": "chief", "content": "問一下"})
wr(os.path.join(studio, "kids/dev-a/state.json"),
   {"state": "llm", "step": 300, "busy": 200, "budget_block": "own:tokens", "frozen_ticks": 120})
wr(os.path.join(studio, "kids/qa/state.json"),
   {"state": "idle", "step": 400, "busy": 250, "question_sleep_steps": 300,
    "sleeping": {"kind": "mail", "id": "pm-mail-20260907-123456"}})
wr(os.path.join(studio, "team/tasks/order-20260907-123456-000001-t3.json"),
   {"id": "order-20260907-123456-000001-t3", "owner": "chief", "status": "assigned",
    "title": "定架構"})
wr(os.path.join(llm, "usage", time.strftime("%Y-%m-%d") + ".json"),
   {"by-requester": {"studio/dev-a": {"total_tokens": 12345}}})
wr(os.path.join(studio, "kids/dev-b/state.json"), {"state": "act", "step": 66, "busy": 40})
wr(os.path.join(studio, "kids/dev-b/prompts.json"), [
    {"role": "user", "content": "請做 todo.py"},
    {"role": "assistant", "content": "我先看一下現在的檔案。",
     "tool_calls": [{"id": "c1", "function": {"name": "read",
                                              "arguments": '{"path": "team/projects/todo.py"}'}}]},
    {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true, "text": "還是空的"}'},
    {"role": "assistant", "content": "那我直接寫一份。",
     "tool_calls": [{"id": "c2", "function": {"name": "write",
                                              "arguments": '{"path": "team/projects/todo.py"}'}}]},
    {"role": "tool", "tool_call_id": "c2", "content": '{"ok": true, "bytes": 30}'},
])
PYEOF2

  why=$("$AUSER" team why "$studio" 2>&1)
  line_count=$(printf '%s\n' "$why" | grep -c .)
  if [ "$line_count" = "9" ]; then
    ok "studio：team why 一行一個人（八行加一行抬頭）"
  else
    fail "studio：team why 行數不對（$line_count）：$why"
  fi

  checks="$root/why.json"
  printf '%s\n' "$why" > "$root/why.txt"
  python3 - "$root/why.txt" "$checks" <<'PYEOF2'
import json, sys
lines = [l for l in open(sys.argv[1], encoding="utf-8").read().splitlines() if l.strip()]
rows = {l.split()[0]: l for l in lines[1:]}
checks = {}
checks["names"] = set(rows) == {"owner", "sales", "pm", "chief", "dev-a", "dev-b", "tester", "qa"}
checks["wait"] = ("llm→wait" in rows["pm"] and "等 LLM 回" in rows["pm"]
                  and "第 2 位" in rows["pm"] and "已等 41 格" in rows["pm"]
                  and "未讀 1 封（chief 1）" in rows["pm"])
checks["frozen"] = ("凍住" in rows["dev-a"] and "tokens 用完" in rows["dev-a"]
                    and "已用 12k" in rows["dev-a"] and "等撥款 120 格" in rows["dev-a"])
checks["sleep"] = ("睡" in rows["qa"] and "等 mail" in rows["qa"] and "已 300 格" in rows["qa"])
checks["task"] = ("閒" in rows["chief"] and "任務" in rows["chief"]
                  and "-t3（assigned）" in rows["chief"])
checks["tokens"] = "tokens 剩 170k" in rows["pm"] and "tokens 剩 20k" in rows["owner"]
checks["width"] = all(len(l) <= 110 for l in lines)
json.dump(checks, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  for item in \
    'names|studio：team why 八個人都印到' \
    'wait|studio：team why 等 LLM 的人印出排隊名次、等幾格與未讀來源' \
    'frozen|studio：team why 凍住的人印出額度用完與等撥款幾格' \
    'sleep|studio：team why 睡著的人印出在等哪一封、睡幾格' \
    'task|studio：team why 閒著的人印出手上那張任務與狀態' \
    'tokens|studio：team why 每行都帶剩下的 tokens' \
    'width|studio：team why 每行不超過 110 字'; do
    studio_assert "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$checks" "${item%%|*}")" "${item#*|}"
  done

  only=$("$AUSER" team why "$studio" --member pm 2>&1)
  line_count=$(printf '%s\n' "$only" | grep -c .)
  case "$line_count:$only" in
    "2:"*"llm→wait"*) ok "studio：team why --member 只印那一個人" ;;
    *) fail "studio：team why --member 不對（$only）" ;;
  esac
  "$AUSER" team why "$studio" --member 沒這個人 >/dev/null 2>&1
  check "studio：team why 認不得的成員回 2" 2 "$?"

  tail_out=$("$AUSER" team tail "$studio" dev-b -n 2 2>&1)
  case "$tail_out" in
    *"dev-b"*"state=act"*"step=66"*) ok "studio：team tail 抬頭有成員、狀態與格數" ;;
    *) fail "studio：team tail 抬頭不對（$tail_out）" ;;
  esac
  case "$tail_out" in
    *"模型說：我先看一下"*"→ read"*"工具回："*"← read: "*"還是空的"*)
      ok "studio：team tail 印得出模型說、工具呼叫與工具回" ;;
    *) fail "studio：team tail 少了模型說／工具回（$tail_out）" ;;
  esac
  case "$tail_out" in
    *"那我直接寫一份"*"← write: "*) ok "studio：team tail -n 2 兩輪都印到" ;;
    *) fail "studio：team tail 沒印滿兩輪（$tail_out）" ;;
  esac
  tail_out=$("$AUSER" team tail "$studio" tester 2>&1)
  case "$tail_out" in
    *"還沒有模型回合"*) ok "studio：team tail 沒對話過的人印一句話不當機" ;;
    *) fail "studio：team tail 空對話沒處理好（$tail_out）" ;;
  esac
  "$AUSER" team tail "$studio" 沒這個人 >/dev/null 2>&1
  check "studio：team tail 認不得的成員回 2" 2 "$?"
  unset AOS_LLM_DIR
}

test_studio_watch
