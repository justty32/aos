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
    --budget '{"tokens":1000,"hours":2,"ticks":100,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1

  checks="$root/checks.json"
  python3 - "$studio" "$checks" <<'PYEOF2'
import json, os, sys
root, output = sys.argv[1:3]
names = ["owner", "sales", "pm", "chief", "dev-a", "dev-b", "qa"]
roster = json.load(open(os.path.join(root, "team", "team.json"), encoding="utf-8"))
members = {m["name"]: m for m in roster["members"]}
worlds = {name: root if name == "owner" else os.path.join(root, "kids", name) for name in names}
checks = {}
checks["worlds"] = all(os.path.isfile(os.path.join(path, ".aos", "inst")) for path in worlds.values())
checks["roster"] = (set(members) == set(names) and members["chief"]["reports_to"] == "pm"
                    and members["owner"]["budget_pct"] == 10 and members["pm"]["budget_pct"] == 90)
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
                            for n in ("sales", "pm", "dev-a", "dev-b", "qa")))
checks["engine"] = all(json.load(open(os.path.join(path, "llm.json"), encoding="utf-8"))["engine"] == "local"
                       for path in worlds.values())
json.dump(checks, open(output, "w", encoding="utf-8"), ensure_ascii=False)
PYEOF2
  for item in \
    'worlds|studio：team new 建出七個世界' \
    'roster|studio：名冊、主管與 10/90 初始分配正確' \
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
r=team.run("team_grant", {"role":"dev-a", "amount":{"tokens":120,"ticks":7}}, ctx)
b=json.load(open(os.path.join(root,"team","budget.json"), encoding="utf-8"))
print(r.get("ok") is True and b["allocations"]["dev-a"]["tokens"] == 120
      and b["allocations"]["pm"]["tokens"] == 780 and len(b["grants"]) == 1)
PYEOF2
)
  studio_assert "$got" "studio：team_grant 從 PM 分額度並寫帳"

  status=$("$AUSER" team status "$studio" 2>&1)
  case "$status" in
    *"owner"*"sales"*"dev-a"*"今天花費"*"整隊剩餘"*) ok "studio：team status 印得出整隊欄位" ;;
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
