make_hook_pack() {
  local home=$1
  mkdir -p "$home/packs"
  cat > "$home/packs/hooktest.py" <<'PYEOF2'
import os

PROMPT = "原本的 hooktest prompt。"
TOOLS = [{"name": "hook_ping", "description": "回 pong。",
          "parameters": {"type": "object", "properties": {}}}]


def record(ctx, name, value=True):
    path = os.path.join(ctx.home, "hook-events.json")
    data = ctx.read_json(path, {})
    data[name] = value
    ctx.write_json(path, data)


def run(name, args, ctx):
    return {"pong": True}


def on_idle(ctx):
    record(ctx, "idle")
    ctx.state["hook_state"] = "saved"


def on_act(ctx, tool, args, result, took_ms):
    record(ctx, "act", {"tool": tool, "args": args, "result": result,
                         "took_ms_ok": took_ms >= 0})


def on_reply(ctx, msg):
    record(ctx, "reply", msg.get("content") or "")


def on_result(ctx, kind, name, result):
    record(ctx, "result", {"kind": kind, "name": name,
                            "has_choices": bool(result.get("choices"))})


def on_system_prompt(ctx):
    record(ctx, "system")
    return "HOOK_SYSTEM_MARKER"
PYEOF2
  cat > "$home/packs/plain.py" <<'PYEOF2'
PROMPT = ""
TOOLS = []


def run(name, args, ctx):
    return {}
PYEOF2
}

test_ctx_mail() {
  local root sender target got
  root=$(make_world hooks_mail)
  sender="$root/agent"
  target="$root/target"
  prep_agent "$target"
  got=$(python3 - "$HERE" "$sender" "$target" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
sender, target = sys.argv[2:4]
ctx = Ctx(sender, resolve_home(sender, None))
p1 = ctx.put_mail(target, "path", "走路徑", thread="t1")
ctx.add_contact("bob", target)
p2 = ctx.put_mail("bob", "named", "走名字", tag=7)
m1 = json.load(open(p1, encoding="utf-8"))
m2 = json.load(open(p2, encoding="utf-8"))
print(m1 == {"from": "agent", "to": "target", "time": m1["time"],
             "content": "走路徑", "thread": "t1"},
      m2 == {"from": "agent", "to": "bob", "time": m2["time"],
             "content": "走名字", "tag": 7},
      ctx.put_mail("nobody", "x", "找不到") is None,
      not glob.glob(os.path.join(resolve_home(target, None), "inbox", "**", "*.tmp"), recursive=True))
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "hooks：put_mail 可走世界路徑或通訊錄，格式固定且原子寫"
  else
    fail "hooks：put_mail 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_parent_contacts() {
  local root world home got
  root=$(make_world hooks_family)
  world="$root/agent"; home="$world/agent"
  "$AUSER" spawn "$world" kid "小孩" >/dev/null 2>&1
  got=$(python3 - "$world" "$home" <<'PYEOF2'
import json, os, sys
world, home = sys.argv[1:3]
kid = os.path.join(home, "kids", "kid")
parent = json.load(open(os.path.join(kid, "parent.json"), encoding="utf-8"))
pc = json.load(open(os.path.join(home, "contacts.json"), encoding="utf-8"))
kc = json.load(open(os.path.join(kid, "contacts.json"), encoding="utf-8"))
kids = json.load(open(os.path.join(home, "kids.json"), encoding="utf-8"))
print(parent == {"name": "agent", "dir": world}, pc.get("kid") == kid,
      kc.get("agent") == world, kids.get("kid", {}).get("dir") == kid)
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "hooks：spawn 寫 parent.json、雙向 contacts 與 kids.json"
  else
    fail "hooks：父子名冊不對（$got）"
  fi
  rm -rf "$root"
}

test_side_results() {
  local root world home got
  root=$(make_world hooks_side)
  world="$root/agent"; home="$world/agent"
  make_hook_pack "$home"
  python3 - "$home/tools.json" <<'PYEOF2'
import json, sys
p=sys.argv[1]; d=json.load(open(p, encoding="utf-8")); d["packs"]=["hooktest", "plain"]
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
  python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, resolve_home, write_json
world=sys.argv[2]; home=resolve_home(world, None)
state={"state":"wait", "step":5, "busy":2, "request":"main-never.json",
       "wait_ticks":0, "pending":[], "started":"2026-09-06T00:00:00"}
loaded, _ = load_packs(home)
ctx=Ctx(world, home, state, loaded)
ctx.for_pack("hooktest").llm_request({"echo":True, "messages":[]}, kind="handled")
ctx.for_pack("plain").llm_request({"echo":True, "messages":[]}, kind="plain")
write_json(os.path.join(home, "state.json"), state)
PYEOF2
  llm_pump "$root/llm" >/dev/null
  agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
h=sys.argv[1]
s=json.load(open(os.path.join(h,"state.json"), encoding="utf-8"))
e=json.load(open(os.path.join(h,"hook-events.json"), encoding="utf-8"))
m=glob.glob(os.path.join(h,"inbox","plain","*.json"))
mail=json.load(open(m[0], encoding="utf-8")) if m else {}
print(s["state"] == "wait", s["request"] == "main-never.json", s["busy"] == 2,
      e.get("result",{}).get("kind") == "handled", bool(m), mail.get("request","").startswith("agent-plain-"),
      s.get("pending") == [])
PYEOF2
)
  if [ "$got" = "True True True True True True True" ]; then
    ok "hooks：side 結果分給原 pack；沒 on_result 就進 inbox，主線 wait 不受影響"
  else
    fail "hooks：side 結果分流不對（$got）"
  fi
  rm -rf "$root"
}

test_all_hooks_and_override() {
  local root world home reply got request
  root=$(make_world hooks_all)
  world="$root/agent"; home="$world/agent"
  make_hook_pack "$home"
  mkdir -p "$home/prompt-overrides"
  printf 'OVERRIDE_MARKER\n' > "$home/prompt-overrides/hooktest.md"
  python3 - "$home/tools.json" <<'PYEOF2'
import json, sys
p=sys.argv[1]; d=json.load(open(p, encoding="utf-8")); d["packs"]=["hooktest"]; d["tools"]=[]
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
  reply=$(say_and_wait "$world" "$root/llm" 'CALL hook_ping' 20) || true
  request=$(find "$root/llm/requests/done" -maxdepth 1 -name '*.json' | sort | head -1)
  got=$(python3 - "$home/hook-events.json" "$request" "$home/state.json" <<'PYEOF2'
import json, sys
e=json.load(open(sys.argv[1], encoding="utf-8")); q=json.load(open(sys.argv[2], encoding="utf-8"))
s=json.load(open(sys.argv[3], encoding="utf-8"))
system=q["messages"][0]["content"]
print(all(k in e for k in ("idle","act","reply","system")), e.get("act",{}).get("tool") == "hook_ping",
      "OVERRIDE_MARKER" in system, "原本的 hooktest prompt" not in system,
      "HOOK_SYSTEM_MARKER" in system, s.get("hook_state") == "saved")
PYEOF2
)
  if [ -n "$reply" ] && [ "$got" = "True True True True True True" ]; then
    ok "hooks：on_idle／on_act／on_reply／on_system_prompt 與 prompt override 都生效"
  else
    fail "hooks：一般掛勾或 prompt override 不對（reply=$reply，$got）"
  fi
  rm -rf "$root"
}

test_clock_without_daemon() {
  local root got
  root=$(make_world hooks_clock)
  got=$(env -u AOS_DAEMON_DIR python3 - "$HERE" "$root/agent" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
ctx=Ctx(sys.argv[2], resolve_home(sys.argv[2], None))
print(ctx.register_clock(".") == (False, "沒設 AOS_DAEMON_DIR"),
      ctx.unregister_clock(".") == (False, "沒設 AOS_DAEMON_DIR"),
      ctx.pause_clock(".") == (False, "沒設 AOS_DAEMON_DIR"),
      ctx.continue_clock(".") == (False, "沒設 AOS_DAEMON_DIR"))
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "hooks：四個時鐘接口沒設 AOS_DAEMON_DIR 時回固定白話錯誤"
  else
    fail "hooks：時鐘接口的缺設定回覆不對（$got）"
  fi
  rm -rf "$root"
}

test_missing_template() {
  local root world
  root=$(make_world hooks_template); world="$root/agent"
  "$AUSER" spawn "$world" kid "小孩" --template no-such-template >/dev/null 2>&1
  if [ -f "$world/agent/kids/kid/state.json" ] && [ -f "$world/agent/kids/kid/tools.json" ]; then
    ok "hooks：template 目錄不存在時 spawn 照常"
  else
    fail "hooks：不存在的 template 擋住 spawn"
  fi
  rm -rf "$root"
}

test_ctx_mail
test_parent_contacts
test_side_results
test_all_hooks_and_override
test_clock_without_daemon
test_missing_template
