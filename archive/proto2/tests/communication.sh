communication_setup() {
  local root=$1
  prep_agent "$root/A"
  prep_agent "$root/B"
  prep_agent "$root/P"
  prep_agent "$root/K"
  prep_agent "$root/X"
  prep_llm "$root/llm"
  python3 - "$root" <<'PYEOF2'
import json, os, sys
root = sys.argv[1]
for name in ("A", "B", "P", "K", "X"):
    home = os.path.join(root, name, "agent")
    tools = json.load(open(os.path.join(home, "tools.json"), encoding="utf-8"))
    tools["packs"] = ["mailbox", "communication"]
    tools["tools"] = []
    json.dump(tools, open(os.path.join(home, "tools.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
contacts = {"A": os.path.join(root, "A"), "B": os.path.join(root, "B"),
            "P": os.path.join(root, "P"), "K": os.path.join(root, "K"),
            "X": os.path.join(root, "X")}
for name in contacts:
    home = os.path.join(root, name, "agent")
    json.dump({other: path for other, path in contacts.items() if other != name},
              open(os.path.join(home, "contacts.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
PYEOF2
}

test_communication_send() {
  local root reply mail got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-send.XXXXXX")
  communication_setup "$root"
  reply=$(say_and_wait "$root/A" "$root/llm" \
    'CALL mail_send {"to":"B","content":"今天幾號？"}' 20) || true
  mail=$(find "$root/B/agent/inbox/A" -maxdepth 1 -name '*.json' 2>/dev/null | head -1)
  got=$(python3 - "$mail" <<'PYEOF2'
import json, os, sys
if not sys.argv[1]:
    print(False)
else:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(d.get("from") == "A" and d.get("to") == "B" and d.get("content") == "今天幾號？"
          and bool(d.get("time")) and d.get("thread") == os.path.splitext(os.path.basename(sys.argv[1]))[0])
PYEOF2
)
  if [ -n "$reply" ] && [ "$got" = "True" ]; then
    ok "communication：A 經假 server 寄信給 B，位置與格式正確"
  else
    fail "communication：mail_send 沒走完（reply=$reply mail=$mail got=$got）"
  fi
  rm -rf "$root"
}

test_communication_reply() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-reply.XXXXXX")
  communication_setup "$root"
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import glob, importlib.util, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
root = sys.argv[2]
spec = importlib.util.spec_from_file_location("communication", os.path.join(sys.argv[1], "packs", "communication.py"))
comm = importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
b = Ctx(os.path.join(root, "B"), resolve_home(os.path.join(root, "B"), None))
a = Ctx(os.path.join(root, "A"), resolve_home(os.path.join(root, "A"), None))
first = b.put_mail("A", "B", "原信", thread="thread-one")
mail_id = os.path.basename(first)
a.mark_read("B", mail_id)
result = comm.run("mail_reply", {"source":"B", "id":mail_id, "content":"收到"}, a)
paths = glob.glob(os.path.join(root, "B", "agent", "inbox", "A", "*.json"))
mail = json.load(open(paths[0], encoding="utf-8")) if paths else {}
print(result.get("reply_to") == mail_id and mail.get("reply_to") == mail_id
      and mail.get("thread") == "thread-one" and mail.get("content") == "收到")
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：mail_reply 帶 reply_to 並沿用 thread";
  else fail "communication：mail_reply 關係不對（$got）"; fi
  rm -rf "$root"
}

test_communication_broadcast() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-broadcast.XXXXXX")
  communication_setup "$root"
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import glob, importlib.util, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
root = sys.argv[2]; world = os.path.join(root, "A"); home = resolve_home(world, None)
spec = importlib.util.spec_from_file_location("communication", os.path.join(sys.argv[1], "packs", "communication.py"))
comm = importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
json.dump({"name":"P", "dir":os.path.join(root,"P")}, open(os.path.join(home,"parent.json"),"w"))
json.dump({"K":{"name":"K", "dir":os.path.join(root,"K")}}, open(os.path.join(home,"kids.json"),"w"))
result = comm.run("mail_broadcast", {"content":"集合"}, Ctx(world, home))
to_p = glob.glob(os.path.join(root,"P","agent","inbox","A","*.json"))
to_k = glob.glob(os.path.join(root,"K","agent","inbox","A","*.json"))
to_x = glob.glob(os.path.join(root,"X","agent","inbox","A","*.json"))
print(result == {"ok":True,"sent":["P","K"],"failed":[]} and bool(to_p) and bool(to_k) and not to_x)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：mail_broadcast 預設只寄父與直接小孩";
  else fail "communication：mail_broadcast 收件人不對（$got）"; fi
  rm -rf "$root"
}

test_communication_who() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-who.XXXXXX")
  communication_setup "$root"
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import importlib.util, json, os, shutil, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
root=sys.argv[2]; world=os.path.join(root,"A"); home=resolve_home(world,None)
spec=importlib.util.spec_from_file_location("communication",os.path.join(sys.argv[1],"packs","communication.py"))
comm=importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
json.dump({"name":"P","dir":os.path.join(root,"P")},open(os.path.join(home,"parent.json"),"w"))
json.dump({"K":{"name":"K","dir":os.path.join(root,"K")}},open(os.path.join(home,"kids.json"),"w"))
shutil.rmtree(os.path.join(root,"X"))
rows=comm.run("mail_who",{},Ctx(world,home)); alive=comm.run("mail_who",{"alive_only":True},Ctx(world,home))
by={r["name"]:r for r in rows}
print(by["P"]["relation"]=="parent" and by["K"]["relation"]=="kid"
      and by["X"]["exists"] is False and "X" not in {r["name"] for r in alive})
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：mail_who 列出關係、路徑與是否存在";
  else fail "communication：mail_who 結果不對（$got）"; fi
  rm -rf "$root"
}

test_communication_wait() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-wait.XXXXXX")
  communication_setup "$root"
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import glob, importlib.util, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
root=sys.argv[2]; world=os.path.join(root,"A"); home=resolve_home(world,None)
spec=importlib.util.spec_from_file_location("communication",os.path.join(sys.argv[1],"packs","communication.py"))
comm=importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
ctx=Ctx(world,home,loaded=[("communication",comm)],pack="communication")
registered=comm.run("mail_wait",{"id":"sent-1.json","note":"等日期"},ctx)
b=Ctx(os.path.join(root,"B"),resolve_home(os.path.join(root,"B"),None))
b.put_mail("A","B","今天是九月六日",reply_to="sent-1.json",thread="sent-1")
wake=ctx.collect_results(); side=glob.glob(os.path.join(home,"side","mail","*.json"))
print(registered.get("ok") is True and bool(registered.get("id")) and not ctx.pending()
      and bool(side) and "你等的那封回來了" in wake[0]["content"] and "等日期" in wake[0]["content"])
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：mail_wait 讓共用層收回信並喚醒";
  else fail "communication：mail_wait 提醒不對（$got）"; fi
  rm -rf "$root"
}

test_communication_missing_name() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-missing.XXXXXX")
  communication_setup "$root"
  got=$(python3 - "$HERE" "$root/A" <<'PYEOF2'
import importlib.util, os, sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
spec=importlib.util.spec_from_file_location("communication",os.path.join(sys.argv[1],"packs","communication.py"))
comm=importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
r=comm.run("mail_send",{"to":"沒這個人","content":"哈囉"},Ctx(sys.argv[2],resolve_home(sys.argv[2],None)))
print(r.get("ok") is False and r.get("error")=="通訊錄裡沒有這個人：沒這個人" and "hint" in r)
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：不存在的名字回白話錯誤";
  else fail "communication：不存在名字的錯誤不對（$got）"; fi
  rm -rf "$root"
}

test_communication_user_copy() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/communication-user.XXXXXX")
  communication_setup "$root"
  mkdir -p "$root/user"
  got=$(AOS_USER_DIR="$root/user" python3 - "$HERE" "$root/A" "$root/user" <<'PYEOF2'
import glob, importlib.util, json, os, sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
spec=importlib.util.spec_from_file_location("communication",os.path.join(sys.argv[1],"packs","communication.py"))
comm=importlib.util.module_from_spec(spec); spec.loader.exec_module(comm)
comm.on_reply(Ctx(sys.argv[2],resolve_home(sys.argv[2],None)),{"role":"assistant","content":"給人的答覆"})
paths=glob.glob(os.path.join(sys.argv[3],"inbox","A","*.json")); d=json.load(open(paths[0])) if paths else {}
print(d.get("from")=="A" and d.get("to")=="user" and d.get("content")=="給人的答覆")
PYEOF2
)
  if [ "$got" = "True" ]; then ok "communication：on_reply 在 AOS_USER_DIR 留一份使用者副本";
  else fail "communication：使用者副本不對（$got）"; fi
  rm -rf "$root"
}

test_communication_send
test_communication_reply
test_communication_broadcast
test_communication_who
test_communication_wait
test_communication_missing_name
test_communication_user_copy
