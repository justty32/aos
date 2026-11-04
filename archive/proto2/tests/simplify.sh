# 簡化輪：旁線生命週期、Ctx 解析與共用建世界。

test_simplify_side_lifecycle() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/simplify-side.XXXXXX")
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import os, sys, types
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
root=sys.argv[2]; world=os.path.join(root,"agent"); producer=os.path.join(root,"worker")
for path in (world, producer):
    os.makedirs(os.path.join(path,"requests")); os.makedirs(os.path.join(path,"results"))
os.makedirs(os.path.join(world,"outbox"))
events=[]
pack=types.SimpleNamespace(on_result=lambda ctx,kind,rid,result:
                           events.append((kind,rid,result)) or "結果已接回")
state={"state":"idle","step":1,"pending":[]}
ctx=Ctx(world,world,state,[("demo",pack)],"demo")
rid=ctx.send("demo",{"x":1},target=producer); ctx.sleep_until("demo",rid)
Ctx.write_json(os.path.join(producer,"results",rid+".json"),{"ok":True})
wake=ctx.collect_results()
side=Ctx.read_json(os.path.join(world,"side","demo",rid+".json"),{})
print(rid and not rid.endswith(".json"), state.get("sleeping") is None,
      state["pending"] == [], side == {"ok":True}, len(events)==1,
      wake[0]["content"].endswith("結果已接回"))
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "simplify：send→睡→共用層收結果→on_result→醒來"
  else
    fail "simplify：旁線成功流程不對（$got）"
  fi
  rm -rf "$root"
}

test_simplify_timeout_cancel() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/simplify-errors.XXXXXX")
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import glob, os, sys, time
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
world=os.path.join(sys.argv[2],"agent"); os.makedirs(os.path.join(world,"outbox"))
state={"step":2,"pending":[]}; ctx=Ctx(world,world,state,pack="none")
a=ctx.send("mail",{},mail_reply_to="never",timeout_s=0.02)
time.sleep(0.03); ctx.collect_results()
timeout=Ctx.read_json(os.path.join(world,"side","mail",a+".json"),{})
state["step"]=4
b=ctx.send("mail",{},mail_reply_to="later"); cancelled=ctx.cancel(b)
cancel=Ctx.read_json(os.path.join(world,"side","mail",b+".json"),{})
errors=[Ctx.read_json(p,{}) for p in glob.glob(os.path.join(world,"outbox","*.json"))]
print(timeout.get("kind_of_error")=="timeout", cancelled,
      cancel.get("kind_of_error")=="cancelled", len(errors)==2,
      all(row.get("error") is True for row in errors))
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "simplify：旁線逾時與取消都落 side 並回聊天錯誤"
  else
    fail "simplify：逾時或取消流程不對（$got）"
  fi
  rm -rf "$root"
}

test_simplify_missing_clock() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/simplify-clock.XXXXXX")
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import glob, os, sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx
world=os.path.join(sys.argv[2],"agent"); worker=os.path.join(sys.argv[2],"worker")
for path in (world,worker):
    os.makedirs(os.path.join(path,"requests")); os.makedirs(os.path.join(path,"results"))
os.makedirs(os.path.join(world,"outbox"))
state={"step":1,"pending":[]}; ctx=Ctx(world,world,state,pack="demo")
rid=ctx.send("demo",{},target=worker); state["step"]=2; ctx.collect_results()
side=Ctx.read_json(os.path.join(world,"side","demo",rid+".json"),{})
reply=Ctx.read_json(glob.glob(os.path.join(world,"outbox","*.json"))[0],{})
print(side.get("kind_of_error")=="no_clock", "目標沒有鐘在跑" in reply.get("content",""),
      reply.get("error") is True)
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "simplify：缺鐘會回聊天端一句人話"
  else
    fail "simplify：缺鐘回報不對（$got）"
  fi
  rm -rf "$root"
}

test_simplify_sleeping_question_steps() {
  local root world home asleep awake
  root=$(make_world simplify_sleep_steps); world="$root/agent"; home="$world/agent"
  python3 - "$HERE" "$world" <<'PYEOF2'
import sys,time
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
w=sys.argv[2];h=resolve_home(w,None);state=Ctx.read_json(h+"/state.json",{})
rid="never"
state.update({"state":"idle","question_active":True,"question_steps":3,
              "pending":[{"id":rid,"kind":"mail","pack":"none",
                          "since_ts":time.time(),"timeout_s":2}],
              "sleeping":{"kind":"mail","id":rid}})
Ctx.write_json(h+"/state.json",state)
PYEOF2
  agent_tick "$world"; agent_tick "$world"; agent_tick "$world"
  asleep=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("question_steps"),d.get("question_sleep_steps"),bool(d.get("sleeping")))' "$home/state.json")
  sleep 2.1; agent_tick "$world"
  awake=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("question_steps"),d.get("question_sleep_steps"),bool(d.get("sleeping")))' "$home/state.json")
  if [ "$asleep $awake" = "3 3 True 4 3 False" ]; then
    ok "simplify：旁線睡眠格不算題目動作，醒來後才續算"
  else
    fail "simplify：旁線睡眠仍算進題目（sleep=$asleep awake=$awake）"
  fi
  rm -rf "$root"
}

test_simplify_ctx_resolution() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/simplify-path.XXXXXX")
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import json, os, sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx
root=sys.argv[2]; world=os.path.join(root,"a"); other=os.path.join(root,"b")
os.makedirs(os.path.join(world,".aos")); os.makedirs(os.path.join(other,".aos")); os.makedirs(os.path.join(other,"body"))
open(os.path.join(other,".aos","inst"),"w").write("aos-agent exec . --home body\n")
Ctx.write_json(os.path.join(world,"contacts.json"),{"bob":"../b"})
ctx=Ctx(world,world)
print(ctx.world_of("bob")==other, ctx.world_of("../b")==other, ctx.world_of(other)==other,
      ctx.home_of("bob")==os.path.join(other,"body"), ctx.depth()==0,
      ctx.clock_of(other)=={"kind":"none","state":"missing"})
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "simplify：world_of 三種輸入與 home／clock／depth 都由 Ctx 解"
  else
    fail "simplify：Ctx 路徑解析不對（$got）"
  fi
  rm -rf "$root"
}

test_simplify_create_world() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/simplify-new.XXXXXX")
  "$AUSER" new "$root/plain" --template chat --home agent --clock none >/dev/null 2>&1
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import os, sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx, create_world
root=sys.argv[2]; direct=os.path.join(root,"direct")
os.makedirs(os.path.join(root,"llm"))
create_world(direct,home="agent",template="chat")
parent=os.path.join(root,"parent"); create_world(parent,home="agent",template="chat")
home=os.path.join(parent,"agent"); ctx=Ctx(parent,home)
ok,msg=ctx.spawn("kid","孩子",packs=[])
worlds=[os.path.join(root,"plain"),direct,os.path.join(home,"kids","kid")]
required=(".aos/inst",".gitignore")
homes=[os.path.join(worlds[0],"agent"),os.path.join(worlds[1],"agent"),worlds[2]]
files=("tools.json","system-prompt.json","prompts.json","llm.json","state.json")
print(ok, all(all(os.path.isfile(os.path.join(w,p)) for p in required) for w in worlds),
      all(all(os.path.isfile(os.path.join(h,p)) for p in files) for h in homes))
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "simplify：new、create_world、spawn 建出的基礎世界一致"
  else
    fail "simplify：共用建世界不一致（$got）"
  fi
  rm -rf "$root"
}

test_simplify_agent_limits() {
  local root world home got
  root=$(make_world simplify_limits); world="$root/agent"; home="$world/agent"
  python3 - "$home/llm.json" <<'PYEOF2'
import json,sys
p=sys.argv[1];d=json.load(open(p,encoding="utf-8"));d["max_steps_per_question"]=1
json.dump(d,open(p,"w",encoding="utf-8"),ensure_ascii=False)
PYEOF2
  "$AUSER" say "$world" "會繞路的題目" >/dev/null 2>&1
  agent_tick "$world"; agent_tick "$world"; agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob,json,os,sys
h=sys.argv[1];s=json.load(open(os.path.join(h,"state.json"),encoding="utf-8"))
rows=[json.load(open(p,encoding="utf-8")) for p in glob.glob(os.path.join(h,"outbox","*.json"))]
print(s.get("limit_pause") is True,s.get("question_steps")==1,
      any("跑了 1 格" in r.get("content","") and r.get("error") is True for r in rows))
PYEOF2
)
  "$AUSER" say "$world" "繼續" >/dev/null 2>&1; agent_tick "$world"; agent_tick "$world"
  RESUMED=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("state")=="wait" and d.get("question_steps")==1)' "$home/state.json")
  if [ "$got $RESUMED" = "True True True True" ]; then
    ok "simplify：每題格數硬上限會停，使用者回話後可再走"
  else
    fail "simplify：每題硬上限不對（$got resumed=$RESUMED）"
  fi
  rm -rf "$root"
}

test_simplify_daily_limit() {
  local root world home got day
  root=$(make_world simplify_daily); world="$root/agent"; home="$world/agent"; day=$(date +%Y-%m-%d)
  python3 - "$home/llm.json" "$root/llm/usage/$day.json" <<'PYEOF2'
import json,os,sys
p=sys.argv[1];d=json.load(open(p,encoding="utf-8"));d["max_tokens_per_day"]=5
json.dump(d,open(p,"w",encoding="utf-8"),ensure_ascii=False)
os.makedirs(os.path.dirname(sys.argv[2]),exist_ok=True)
json.dump({"by-model":{},"by-requester":{"agent":{"total_tokens":5}}},open(sys.argv[2],"w",encoding="utf-8"))
PYEOF2
  "$AUSER" say "$world" "今天到頂" >/dev/null 2>&1; agent_tick "$world"; agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob,json,os,sys
h=sys.argv[1];s=json.load(open(os.path.join(h,"state.json"),encoding="utf-8"))
rows=[json.load(open(p,encoding="utf-8")) for p in glob.glob(os.path.join(h,"outbox","*.json"))]
print(s.get("limit_kind")=="tokens" and s.get("limit_pause") is True,
      any("今天用量到頂" in r.get("content","") for r in rows))
PYEOF2
)
  if [ "$got" = "True True" ]; then
    ok "simplify：每日 token 硬上限會在叫 LLM 前擋住"
  else
    fail "simplify：每日 token 上限不對（$got）"
  fi
  rm -rf "$root"
}

test_simplify_side_lifecycle
test_simplify_timeout_cancel
test_simplify_missing_clock
test_simplify_sleeping_question_steps
test_simplify_ctx_resolution
test_simplify_create_world
test_simplify_agent_limits
test_simplify_daily_limit
