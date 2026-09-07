# studio 流程包：一張單從接單走到交付，每一步查檔案、查信、查越權。

studio_flow_assert() {
  local got=$1 label=$2
  if [ "$got" = "True" ]; then ok "$label"; else fail "$label（$got）"; fi
}

studio_flow_call() {  # studio_flow_call <成員世界> <工具> <參數 JSON>；印工具回值（JSON 一行）
  python3 - "$HERE" "$1" "$2" "$3" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
from packs import studio
world = os.path.abspath(sys.argv[2])
ctx = Ctx(world, resolve_home(world, None))
out = studio.run(sys.argv[3], json.loads(sys.argv[4] or "{}"), ctx)
print(json.dumps(out, ensure_ascii=False, default=str))
PYEOF2
}

studio_flow_direct() {  # studio_flow_direct <成員世界> <文字>；直接投一封 user 信
  python3 - "$HERE" "$1" "$2" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import put_mail, resolve_home
put_mail(resolve_home(sys.argv[2], None), "user", sys.argv[3], "user")
PYEOF2
}

test_studio_flow() {
  local root studio out order_id task1 task2 got

  root=$(mktemp -d "$TEST_RUN_DIR/studioflow.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  export AOS_USER_DIR="$root/user"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":600000,"hours":8,"ticks":5000,"disk_mb":200,"mem_mb":512,"money_usd":5}' \
    >/dev/null 2>&1

  # preset 目前沒掛 studio 包，測試裡自己補上（真正的 preset 由主線改）。
  python3 - "$studio" <<'PYEOF2'
import json, os, sys
root = sys.argv[1]
for name in ("sales", "pm", "chief", "dev-a", "dev-b", "tester", "qa"):
    p = os.path.join(root, "kids", name, "tools.json")
    d = json.load(open(p, encoding="utf-8"))
    if "studio" not in d["packs"]:
        d["packs"].append("studio")
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
p = os.path.join(root, "tools.json")
d = json.load(open(p, encoding="utf-8"))
if "studio" not in d["packs"]:
    d["packs"].append("studio")
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2

  # 不在工作室裡：每個工具都回 ok:false
  got=$(python3 - "$HERE" "$TEST_RUN_DIR" <<'PYEOF2'
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import studio
solo = tempfile.mkdtemp(dir=sys.argv[2])
ctx = Ctx(solo, solo)
outs = [studio.run(name, {}, ctx) for name in
        ("order_accept", "plan_set", "task_assign", "task_report",
         "qa_run", "qa_verdict", "deliver", "order_status", "order_fail")]
print(all(o.get("ok") is False and o.get("error") for o in outs)
      and studio.on_system_prompt(ctx) == "")
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：不在工作室裡每個工具都回 ok:false"

  # 1. sales 接單
  "$AUSER" order "$studio" "做一支 todo.py" --budget '{"tokens":200000,"hours":1}' \
    --accept "加列刪都能用" --accept "unittest 全過" >/dev/null
  out=$(studio_flow_call "$studio/kids/sales" order_accept '{"note":"甲方很急"}')
  order_id=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("order_id") or "")')
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
order = json.load(open(os.path.join(root, "team", "orders", oid + ".json"), encoding="utf-8"))
pm = glob.glob(os.path.join(root, "kids", "pm", "inbox", "sales", "*.json"))
letter = json.load(open(pm[0], encoding="utf-8")) if pm else {}
reply = sorted(glob.glob(os.path.join(root, "kids", "sales", "outbox", "*.json")))
text = json.load(open(reply[-1], encoding="utf-8"))["content"] if reply else ""
unread = glob.glob(os.path.join(root, "kids", "sales", "inbox", "user", "order-*.json"))
read = glob.glob(os.path.join(root, "kids", "sales", "inbox", "user", "read", "order-*.json"))
print(out.get("ok") is True and oid.startswith("order-")
      and order["status"] == "received" and order["task"] == "做一支 todo.py"
      and order["acceptance"] == ["加列刪都能用", "unittest 全過"]
      and order["budget"]["tokens"] == 200000 and order["tasks"] == []
      and os.path.isdir(os.path.join(root, "team", "projects", oid))
      and len(pm) == 1 and oid in letter.get("content", "") and letter.get("from") == "sales"
      and "【確認單】" in text and oid in text and "加列刪都能用" in text and "下一步" in text
      and not unread and len(read) == 1)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：order_accept 開單、mkdir 專案、寄 pm、回甲方確認單、信搬進 read/"

  got=$(studio_flow_call "$studio/kids/sales" order_accept '{}' \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("ok") is False and "接過" in d.get("error",""))')
  studio_flow_assert "$got" "studio_flow：同一張單不會被接第二次"

  # 2. chief 定計畫（dev-a 不能定）
  got=$(studio_flow_call "$studio/kids/dev-a" plan_set \
        "{\"order_id\":\"$order_id\",\"architecture\":\"x\",\"tasks\":[{\"title\":\"t\"}]}" \
        | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("ok") is False and "plan_set" in d.get("error",""))')
  studio_flow_assert "$got" "studio_flow：dev-a 不能 plan_set（越權被擋）"

  out=$(studio_flow_call "$studio/kids/chief" plan_set "$(python3 -c '
import json, sys
print(json.dumps({"order_id": sys.argv[1], "architecture": "一支 todo.py 加一支 test_todo.py",
                  "tasks": [{"title": "寫 todo.py", "spec": "加、列、刪三個函式",
                             "owner": "dev-a", "files": ["todo.py"]},
                            {"title": "寫測試", "spec": "unittest 蓋三個函式",
                             "owner": "dev-b", "files": ["test_todo.py"]}]},
                 ensure_ascii=False))' "$order_id")")
  task1="$order_id-t1"
  task2="$order_id-t2"
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
order = json.load(open(os.path.join(root, "team", "orders", oid + ".json"), encoding="utf-8"))
t1 = json.load(open(os.path.join(root, "team", "tasks", oid + "-t1.json"), encoding="utf-8"))
t2 = json.load(open(os.path.join(root, "team", "tasks", oid + "-t2.json"), encoding="utf-8"))
mail = glob.glob(os.path.join(root, "kids", "pm", "inbox", "chief", "*.json"))
text = json.load(open(mail[0], encoding="utf-8"))["content"] if mail else ""
print(out.get("ok") is True and order["status"] == "planned"
      and order["tasks"] == [oid + "-t1", oid + "-t2"]
      and order["plan"]["architecture"].startswith("一支 todo.py")
      and t1["status"] == "assigned" and t1["owner"] == "dev-a" and t1["files"] == ["todo.py"]
      and t2["owner"] == "dev-b" and t2["order"] == oid
      and len(mail) == 1 and "【計畫】" in text and oid + "-t1" in text)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：plan_set 寫 plan、開兩個任務檔、寄 pm 摘要"

  # 3. pm 派工：dev-a 本來 0 tokens，task_assign 要自己撥
  out=$(studio_flow_call "$studio/kids/pm" task_assign "{\"task_id\":\"$task1\",\"tokens\":40000}")
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
book = json.load(open(os.path.join(root, "team", "budget.json"), encoding="utf-8"))
order = json.load(open(os.path.join(root, "team", "orders", oid + ".json"), encoding="utf-8"))
mail = glob.glob(os.path.join(root, "kids", "dev-a", "inbox", "pm", "*.json"))
text = json.load(open(mail[0], encoding="utf-8"))["content"] if mail else ""
print(out.get("ok") is True and out["to"] == "dev-a" and out["budget"]["granted"] == 40000
      and book["allocations"]["dev-a"]["tokens"] == 40000
      and book["grants"][-1]["from"] == "pm" and book["grants"][-1]["to"] == "dev-a"
      and order["status"] == "in_progress"
      and len(mail) == 1 and "【工作單】" in text and "加、列、刪" in text
      and "task_report" in text)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：task_assign 自動撥額度、寄整份 spec、單推進 in_progress"

  studio_flow_call "$studio/kids/pm" task_assign "{\"task_id\":\"$task2\"}" >/dev/null
  got=$(python3 -c '
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
print(b["allocations"]["dev-b"]["tokens"] == 50000)' "$studio/team/budget.json")
  studio_flow_assert "$got" "studio_flow：task_assign 沒給 tokens 就撥預設 50000"

  # 4. dev 回報，順便真的跑一次 unittest
  cat > "$studio/team/projects/$order_id/todo.py" <<'PYEOF2'
ITEMS = []


def add(x):
    ITEMS.append(x)
    return ITEMS


def ls():
    return list(ITEMS)


def rm(x):
    ITEMS.remove(x)
    return ITEMS
PYEOF2
  cat > "$studio/team/projects/$order_id/test_todo.py" <<'PYEOF2'
import unittest

import todo


class T(unittest.TestCase):
    def test_all(self):
        todo.ITEMS[:] = []
        todo.add("a")
        self.assertEqual(todo.ls(), ["a"])
        self.assertEqual(todo.rm("a"), [])
PYEOF2
  out=$(studio_flow_call "$studio/kids/dev-a" task_report "$(python3 -c '
import json, sys
print(json.dumps({"task_id": sys.argv[1], "summary": "加列刪寫好了",
                  "files": ["todo.py"], "test_cmd": "python3 -m unittest -v test_todo"},
                 ensure_ascii=False))' "$task1")")
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
task = json.load(open(os.path.join(root, "team", "tasks", oid + "-t1.json"), encoding="utf-8"))
pm = glob.glob(os.path.join(root, "kids", "pm", "inbox", "dev-a", "*.json"))
qa = glob.glob(os.path.join(root, "kids", "qa", "inbox", "dev-a", "*.json"))
text = json.load(open(pm[0], encoding="utf-8"))["content"] if pm else ""
test = task["tests"][-1]
print(out.get("ok") is True and out["test"]["exit"] == 0
      and task["status"] == "done" and task["files"] == ["todo.py"]
      and task["report"] == "加列刪寫好了" and len(task["tests"]) == 1
      and test["exit"] == 0 and "OK" in test["output"]
      and test["cwd"].endswith(os.path.join("team", "projects", oid))
      and len(test["output"]) <= 2000
      and len(pm) == 1 and len(qa) == 1 and "【任務完成】" in text and "exit=0" in text)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：task_report 記檔案、在專案目錄真的跑 unittest、寄 pm 與 qa"

  studio_flow_call "$studio/kids/dev-b" task_report \
    "{\"task_id\":\"$task2\",\"summary\":\"測試寫好了\",\"files\":[\"test_todo.py\"]}" >/dev/null

  # 5. qa 跑一次、判兩次
  out=$(studio_flow_call "$studio/kids/qa" qa_run \
        "{\"task_id\":\"$task1\",\"command\":\"python3 -m unittest test_todo\"}")
  got=$(printf '%s' "$out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is True and d["exit"] == 0 and "OK" in d["output"])')
  studio_flow_assert "$got" "studio_flow：qa_run 在專案目錄跑指令並回 exit"

  got=$(studio_flow_call "$studio/kids/qa" qa_verdict \
        "{\"task_id\":\"$task1\",\"passed\":true,\"evidence\":\"unittest 全過\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is True and d["status"] == "passed" and d["all_passed"] is False
      and d["order_status"] == "in_progress")')
  studio_flow_assert "$got" "studio_flow：qa_verdict 一項過，單還不推進"

  got=$(studio_flow_call "$studio/kids/pm" deliver "{\"order_id\":\"$order_id\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is False and "沒過驗收" in d.get("error", ""))')
  studio_flow_assert "$got" "studio_flow：還有任務沒過時 deliver 被擋"

  # 判過要有憑據：t2 還沒跑過任何測試，qa 直接判過會被擋；qa_run 跑過一次才能判
  got=$(studio_flow_call "$studio/kids/qa" qa_verdict \
        "{\"task_id\":\"$task2\",\"passed\":true,\"evidence\":\"測試檔在\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is False and "exit 0" in d.get("error", "") and d.get("tests") == [])')
  studio_flow_assert "$got" "studio_flow：沒跑過測試 qa_verdict 不能判過"
  studio_flow_call "$studio/kids/qa" qa_run \
        "{\"task_id\":\"$task2\",\"command\":\"python3 -m py_compile test_todo.py\"}" >/dev/null

  out=$(studio_flow_call "$studio/kids/qa" qa_verdict \
        "{\"task_id\":\"$task2\",\"passed\":true,\"evidence\":\"測試檔在\"}")
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
order = json.load(open(os.path.join(root, "team", "orders", oid + ".json"), encoding="utf-8"))
task = json.load(open(os.path.join(root, "team", "tasks", oid + "-t2.json"), encoding="utf-8"))
mail = glob.glob(os.path.join(root, "kids", "pm", "inbox", "qa", "*.json"))
print(out.get("ok") is True and out["all_passed"] is True and out["order_status"] == "qa"
      and order["status"] == "qa" and task["status"] == "passed"
      and task["qa"]["by"] == "qa" and len(mail) == 2)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：兩項都過時單推進 qa，並寄 pm"

  # 6. 交付（dev-a 不能交付）
  got=$(studio_flow_call "$studio/kids/dev-a" deliver "{\"order_id\":\"$order_id\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is False and "deliver" in d.get("error", "") and "pm" in d.get("error", ""))')
  studio_flow_assert "$got" "studio_flow：dev-a 不能 deliver（越權被擋）"

  out=$(studio_flow_call "$studio/kids/pm" deliver \
        "{\"order_id\":\"$order_id\",\"summary\":\"todo.py 與測試都好了\"}")
  got=$(python3 - "$studio" "$order_id" "$out" <<'PYEOF2'
import glob, json, os, sys
root, oid, out = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
order = json.load(open(os.path.join(root, "team", "orders", oid + ".json"), encoding="utf-8"))
final = os.path.join(root, "team", "files", "final", oid)
mail = glob.glob(os.path.join(root, "kids", "sales", "inbox", "pm", "*.json"))
text = json.load(open(mail[0], encoding="utf-8"))["content"] if mail else ""
print(out.get("ok") is True and order["status"] == "delivered"
      and sorted(out["files"]) == ["test_todo.py", "todo.py"]
      and os.path.isfile(os.path.join(final, "todo.py"))
      and os.path.isfile(os.path.join(final, "test_todo.py"))
      and isinstance(out["spent_tokens"], (int, float))
      and len(mail) == 1 and "【交付單】" in text and "todo.py" in text
      and "exit=0" in text and "整隊已花 tokens" in text
      and order["delivered"]["dir"].endswith(os.path.join("files", "final", oid)))
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：deliver 複製檔案、寄 sales 交付單（含清單、測試、整隊花費）"

  # 7. order_status 與 on_system_prompt
  got=$(studio_flow_call "$studio/kids/dev-b" order_status "{\"order_id\":\"$order_id\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
o = d["order"]
print(d.get("ok") is True and o["status"] == "delivered" and len(o["tasks"]) == 2
      and len(o["history"]) <= 3 and o["tasks"][0]["owner"] == "dev-a")')
  studio_flow_assert "$got" "studio_flow：order_status 回精簡現況與最近三條 history"

  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
from packs import studio
root = sys.argv[2]


def ctx_of(name):
    world = root if name == "owner" else os.path.join(root, "kids", name)
    return Ctx(world, resolve_home(world, None))


done = studio.on_system_prompt(ctx_of("dev-a"))          # 單已交付 → 空
orders = os.path.join(root, "team", "orders")
oid = sorted(os.listdir(orders))[0][:-5]
p = os.path.join(orders, oid + ".json")
d = json.load(open(p, encoding="utf-8"))
d["status"] = "in_progress"
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
t = os.path.join(root, "team", "tasks", oid + "-t1.json")
task = json.load(open(t, encoding="utf-8"))
task["status"] = "assigned"
json.dump(task, open(t, "w", encoding="utf-8"), ensure_ascii=False)
mine = studio.on_system_prompt(ctx_of("dev-a"))
other = studio.on_system_prompt(ctx_of("dev-b"))
print(done == "" and 1 <= len(mine.splitlines()) <= 3 and oid in mine
      and "你的任務" in mine and "加、列、刪" in mine
      and "你的任務" not in other and oid in other)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：on_system_prompt 兩三行摘要，交付完就不佔位置"

  # 8. order_fail
  got=$(studio_flow_call "$studio/kids/pm" order_fail \
        "{\"order_id\":\"$order_id\",\"reason\":\"甲方改主意\"}" \
        | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(d.get("ok") is True and d["status"] == "failed" and d["mailed_sales"] is True)')
  studio_flow_assert "$got" "studio_flow：order_fail 標 failed 並寄 sales"

  # 9. 走真的 agent 一格：假 server 照劇本叫 order_accept
  "$AUSER" order "$studio" "做第二支小工具" --budget '{"tokens":50000}' \
    --accept "跑得起來" >/dev/null
  studio_flow_direct "$studio/kids/sales" 'CALL order_accept {}'
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    "$AGENT" exec "$studio/kids/sales" >/dev/null 2>&1
    llm_pump "$root/llm" >/dev/null
    if [ "$(find "$studio/team/orders" -maxdepth 1 -name '*.json' | wc -l)" -ge 2 ]; then break; fi
  done
  got=$(python3 - "$studio" <<'PYEOF2'
import glob, json, os, sys
root = sys.argv[1]
orders = sorted(glob.glob(os.path.join(root, "team", "orders", "*.json")))
rows = [json.load(open(p, encoding="utf-8")) for p in orders]
fresh = [r for r in rows if r["task"] == "做第二支小工具"]
pm = glob.glob(os.path.join(root, "kids", "pm", "inbox", "sales", "*.json"))
print(len(orders) == 2 and len(fresh) == 1 and fresh[0]["status"] == "received" and len(pm) == 2)
PYEOF2
)
  studio_flow_assert "$got" "studio_flow：假 server 走真的 agent 一格也接得了單"

  "$AUSER" team stop "$studio" >/dev/null 2>&1
  unset AOS_USER_DIR
  unset AOS_LLM_DIR
  rm -rf "$root"
}

test_studio_flow

# task_assign 沒有 task_id：直接在單上開新任務（pm 先派 chief 去定架構就是這條路）
test_studio_flow_new_task() {
  local root studio got
  root=$(mktemp -d "$TEST_RUN_DIR/flownew.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  AOS_LLM_DIR="$root/llm" "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' >/dev/null 2>&1
  AOS_LLM_DIR="$root/llm" "$AUSER" order "$studio" "做 todo.py" --budget '{"tokens":500}' >/dev/null 2>&1
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import studio
root = sys.argv[2]
sales = Ctx(os.path.join(root, "kids", "sales"), os.path.join(root, "kids", "sales"))
r0 = studio.run("order_accept", {}, sales)
pm = Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm"))
r1 = studio.run("task_assign", {"to": "chief", "title": "定架構", "spec": "拆任務"}, pm)
r2 = studio.run("task_assign", {"task_id": "沒這個", "to": "chief", "spec": "再一個"}, pm)
order = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
mails = glob.glob(os.path.join(root, "kids", "chief", "inbox", "pm", "*.json"))
# chief 拆任務：接在 t1、t2 後面編 t3，自己手上那兩項定架構任務自動算 passed
chief = Ctx(os.path.join(root, "kids", "chief"), os.path.join(root, "kids", "chief"))
r3 = studio.run("plan_set", {"order_id": order["id"], "architecture": "一支檔", "tasks": [{"title": "寫程式", "owner": "dev-a", "spec": "首席寫的完整說明"}]}, chief)
order2 = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
t1 = json.load(open(os.path.join(root, "team", "tasks", r1["task_id"] + ".json"), encoding="utf-8"))
# pm 沒給 task_id、只說 to=dev-a：要派 plan_set 開給 dev-a 的 t3，不能再開 t4；短的 spec 不蓋掉首席的
r4 = studio.run("task_assign", {"to": "dev-a", "spec": "短"}, pm)
t3 = json.load(open(os.path.join(root, "team", "tasks", order["id"] + "-t3.json"), encoding="utf-8"))
order3 = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
print(r0.get("ok") is True and r1.get("ok") is True and r1["task_id"].endswith("-t1") and r1["to"] == "chief"
      and r2.get("ok") is True and r2["task_id"].endswith("-t2") and order["tasks"] == [r1["task_id"], r2["task_id"]]
      and order["status"] == "in_progress" and len(mails) == 2
      and r3.get("ok") is True and order2["tasks"] == [r1["task_id"], r2["task_id"], order["id"] + "-t3"]
      and t1["status"] == "passed"
      and r4.get("ok") is True and r4["task_id"] == order["id"] + "-t3" and len(order3["tasks"]) == 3
      and t3.get("assigned") and t3["spec"] == "首席寫的完整說明")
PYEOF2
)
  if [ "$got" = "True" ]; then ok "studio_flow：task_assign 沒 task_id 就開新任務；plan_set 接著編號並把定架構那項算 passed"; else fail "studio_flow：開新任務不對（$got）"; fi
  # task_report 帶的 test_cmd 沒過 → 不算完成、status 不動、回 ok:false 與輸出尾巴；過了才 done
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import studio
root = sys.argv[2]
order = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
tid = order["id"] + "-t3"
dev = Ctx(os.path.join(root, "kids", "dev-a"), os.path.join(root, "kids", "dev-a"))
bad = studio.run("task_report", {"task_id": tid, "summary": "全過了（其實沒有）", "files": ["x.py"], "test_cmd": "exit 3"}, dev)
t = json.load(open(os.path.join(root, "team", "tasks", tid + ".json"), encoding="utf-8"))
good = studio.run("task_report", {"task_id": tid, "summary": "真的過了", "files": ["x.py"], "test_cmd": "true"}, dev)
t2 = json.load(open(os.path.join(root, "team", "tasks", tid + ".json"), encoding="utf-8"))
print(bad.get("ok") is False and bad["test"]["exit"] == 3 and t["status"] == "assigned" and len(t["tests"]) == 1
      and good.get("ok") is True and t2["status"] == "done" and len(t2["tests"]) == 2)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "studio_flow：task_report 的測試沒過就不算完成，過了才 done"; else fail "studio_flow：測試沒過的回報沒被擋（$got）"; fi
  # qa_verdict 沒給 task_id：只有一個 done 的就當它；on_idle：手上有任務卻閒著，45 格後寄信提醒自己
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import studio
root = sys.argv[2]
order = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
qa = Ctx(os.path.join(root, "kids", "qa"), os.path.join(root, "kids", "qa"))
v = studio.run("qa_verdict", {"passed": True, "evidence": "看過了"}, qa)
t3 = json.load(open(os.path.join(root, "team", "tasks", order["id"] + "-t3.json"), encoding="utf-8"))
# dev-a 手上 t2 還是 assigned（chief 的第二個任務其實是 chief 的；改派給 dev-a 來測）
pm = Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm"))
studio.run("task_assign", {"task_id": order["id"] + "-t2", "to": "dev-a"}, pm)
dev = Ctx(os.path.join(root, "kids", "dev-a"), os.path.join(root, "kids", "dev-a"))
dev.state.update({"step": 10}); studio.on_idle(dev)            # 第一次只記時間
dev.state.update({"step": 30}); studio.on_idle(dev)            # 才 20 格，不提醒
box = os.path.join(root, "kids", "dev-a", "inbox", "studio")
none_yet = not os.path.isdir(box) or not [f for f in os.listdir(box) if f.endswith(".json")]
dev.state.update({"step": 60}); studio.on_idle(dev)            # 滿 45 格，提醒
mails = [f for f in os.listdir(box) if f.endswith(".json")] if os.path.isdir(box) else []
text = json.load(open(os.path.join(box, mails[0]), encoding="utf-8"))["content"] if mails else ""
first_nag_step = dev.state.get("studio_nag_step")
for step in (110, 160, 210, 260):                              # 三次都沒動靜→第四次改寄主管，之後不再吵
    dev.state.update({"step": step}); studio.on_idle(dev)
mails2 = [f for f in os.listdir(box) if f.endswith(".json")]
boss_box = os.path.join(root, "kids", "chief", "inbox", "dev-a")
boss = [f for f in os.listdir(boss_box) if f.endswith(".json")] if os.path.isdir(boss_box) else []
print(v.get("ok") is True and v["task_id"] == t3["id"] and t3["status"] == "passed"
      and none_yet and len(mails) == 1 and "-t2" in text and first_nag_step == 60
      and len(mails2) == 3 and len(boss) == 1 and "卡住" in json.load(open(os.path.join(boss_box, boss[0]), encoding="utf-8"))["content"])
PYEOF2
)
  if [ "$got" = "True" ]; then ok "studio_flow：qa_verdict 漏 task_id 就認唯一等驗的；閒著有任務 45 格提醒自己，三次沒動就交主管"; else fail "studio_flow：qa_verdict 預設／on_idle 提醒不對（$got）"; fi
  # qa 只驗不做：plan_set／task_assign 派給 qa 都被擋；tester 能 task_report 但 files 一定要有測試檔
  got=$(python3 - "$HERE" "$studio" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import studio
root = sys.argv[2]
order = json.load(open(glob.glob(os.path.join(root, "team", "orders", "*.json"))[0], encoding="utf-8"))
chief = Ctx(os.path.join(root, "kids", "chief"), os.path.join(root, "kids", "chief"))
pm = Ctx(os.path.join(root, "kids", "pm"), os.path.join(root, "kids", "pm"))
tester = Ctx(os.path.join(root, "kids", "tester"), os.path.join(root, "kids", "tester"))
r1 = studio.run("plan_set", {"order_id": order["id"], "architecture": "x", "tasks": [{"title": "寫測試", "owner": "qa"}]}, chief)
r2 = studio.run("task_assign", {"order_id": order["id"], "to": "qa", "spec": "寫測試"}, pm)
r3 = studio.run("task_assign", {"order_id": order["id"], "to": "tester", "spec": "寫測試"}, pm)
tid = r3.get("task_id") or ""
r4 = studio.run("task_report", {"task_id": tid, "summary": "寫好了", "files": ["x.py"]}, tester)
r5 = studio.run("task_report", {"task_id": tid, "summary": "寫好了", "files": ["test_x.py"]}, tester)
print(r1.get("ok") is False and "tester" in r1.get("error", "")
      and r2.get("ok") is False and "tester" in r2.get("error", "")
      and r3.get("ok") is True and tid.endswith("-t4")
      and r4.get("ok") is False and "test" in r4.get("error", "")
      and r5.get("ok") is True and r5["status"] == "done")
PYEOF2
)
  if [ "$got" = "True" ]; then ok "studio_flow：任務不能派給 qa；tester 回報一定要列測試檔"; else fail "studio_flow：qa 只驗／tester 規則不對（$got）"; fi
  rm -rf "$root"
}

test_studio_flow_new_task
