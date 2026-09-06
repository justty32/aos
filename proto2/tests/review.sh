test_review_recent() {
  local root world home got
  root=$(make_world review_recent); world="$root/agent"; home="$world/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import datetime, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world, None)
os.makedirs(os.path.join(home,"ledger"), exist_ok=True)
now=datetime.datetime.now().replace(microsecond=0)
rows=[
 {"time":now.isoformat(),"step":16,"tool":"sh","took_ms":500,"ok":True,"round_steps":2,
  "llm_round":{"prompt_tokens":100,"completion_tokens":20,"reasoning_tokens":5,"cost":0.01}},
 {"time":now.isoformat(),"step":17,"tool":"sh","took_ms":700,"ok":False,"error_kind":"exit",
  "round_steps":3,"llm_round":{"prompt_tokens":200,"completion_tokens":20,"cost":0.02}},
 {"time":now.isoformat(),"step":18,"tool":"sh","took_ms":300,"ok":False,"error_kind":"exit",
  "round_steps":2,"llm_round":{"prompt_tokens":50,"completion_tokens":10,"cost":0.03}}]
with open(os.path.join(home,"ledger",now.date().isoformat()+".jsonl"),"w",encoding="utf-8") as f:
    for row in rows: f.write(json.dumps(row,ensure_ascii=False)+"\n")
os.makedirs(os.path.join(home,"outbox"), exist_ok=True)
json.dump({"content":"做完了"},open(os.path.join(home,"outbox","0019.json"),"w",encoding="utf-8"),ensure_ascii=False)
mod=load_pack(home,"review"); ctx=Ctx(world,home,{"step":20},[("review",mod)])
r=mod.run("review_recent",{"n_steps":5},ctx)
print(r["tool_calls"]==3, r["errors"]==2, r["total_tokens"]==405,
      r["total_cost"]==0.06, "連續呼叫 sh" in r["detours"], r["last_result"]["replied"])
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "review：review_recent 算近期次數、錯誤、token、錢、繞路和結果"
  else
    fail "review：review_recent 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_review_patterns() {
  local root world home got
  root=$(make_world review_patterns); world="$root/agent"; home="$world/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import datetime, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); now=datetime.datetime.now().replace(microsecond=0)
os.makedirs(os.path.join(home,"ledger"),exist_ok=True)
rows=[
 {"time":now.isoformat(),"tool":"cheap","task_key":"整理","args_mark":"a","ok":True,"took_ms":100,"round_steps":1,"llm_round":{"cost":0.01}},
 {"time":now.isoformat(),"tool":"costly","task_key":"研究","args_mark":"x","ok":False,"error_kind":"timeout","took_ms":1000,"round_steps":4,"llm_round":{"cost":0.40}},
 {"time":now.isoformat(),"tool":"costly","task_key":"研究","args_mark":"x","ok":False,"error_kind":"timeout","took_ms":1200,"round_steps":5,"llm_round":{"cost":0.50}}]
with open(os.path.join(home,"ledger",now.date().isoformat()+".jsonl"),"w",encoding="utf-8") as f:
    for row in rows: f.write(json.dumps(row,ensure_ascii=False)+"\n")
lesson="研究：原本平均 0.40 元／4 格 → 少抓全文 → 之後平均 0.50 元／5 格"
os.makedirs(os.path.join(home,"memory"),exist_ok=True)
open(os.path.join(home,"memory","lessons.md"),"w",encoding="utf-8").write(lesson+"\n")
mod=load_pack(home,"review"); ctx=Ctx(world,home,{"step":9},[("review",mod)])
r=mod.run("review_patterns",{},ctx)
marked=open(os.path.join(home,"memory","lessons.md"),encoding="utf-8").read()
print(r["expensive_tools"][0]["name"]=="costly", r["expensive_tasks"][0]["name"]=="研究",
      r["repeated_without_progress"][0]["name"]=="costly",
      r["repeated_errors"][0]["problem"]=="costly／timeout", "【無效】" in marked)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "review：review_patterns 按錢排工具與任務，也列打轉、錯誤和無效教訓"
  else
    fail "review：review_patterns 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_review_thoughts() {
  local root world home got
  root=$(make_world review_thoughts); world="$root/agent"; home="$world/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); path=os.path.join(home,"thoughts","think-1")
os.makedirs(path)
json.dump({"question":"要不要一次讀完？","usage":{"cost":0.03}},open(os.path.join(path,"meta.json"),"w",encoding="utf-8"),ensure_ascii=False)
open(os.path.join(path,"conclusion.md"),"w",encoding="utf-8").write("先讀索引，再讀需要的段落。")
json.dump([{"role":"assistant","content":"我會先讀索引，再讀需要的段落。"}],open(os.path.join(home,"prompts.json"),"w",encoding="utf-8"),ensure_ascii=False)
mod=load_pack(home,"review"); ctx=Ctx(world,home,{"step":3},[("review",mod)])
r=mod.run("review_thoughts",{"id":"think-1"},ctx)["thoughts"][0]
print(r["question"]=="要不要一次讀完？", r["conclusion"]=="先讀索引，再讀需要的段落。",
      r["cost"]==0.03, r["adopted"]=="有採用")
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "review：review_thoughts 只帶短結論、花費與採用結果"
  else
    fail "review：review_thoughts 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_lesson_add() {
  local root world got
  root=$(make_world review_lesson_add); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); mod=load_pack(home,"review")
ctx=Ctx(world,home,{"step":1},[("review",mod)])
text="查文件：原本平均 0.12 元／8 格 → 先讀索引 → 之後平均 0.08 元／5 格"
r=mod.run("lesson_add",{"text":text},ctx)
bad=mod.run("lesson_add",{"text":"下次小心"},ctx)
print(r=={"lesson":text,"count":1,"archived":0}, "error" in bad,
      open(os.path.join(home,"memory","lessons.md"),encoding="utf-8").read().strip()==text)
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "review：lesson_add 只收一行帶數字的教訓"
  else
    fail "review：lesson_add 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_lessons_list() {
  local root world got
  root=$(make_world review_lessons_list); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); os.makedirs(os.path.join(home,"memory"),exist_ok=True)
lines=["工作%d：原本平均 1 元／2 格 → 改法%d → 之後平均 0.5 元／1 格"%(n,n) for n in range(25)]
open(os.path.join(home,"memory","lessons.md"),"w",encoding="utf-8").write("\n".join(lines)+"\n")
mod=load_pack(home,"review"); r=mod.run("lessons_list",{},Ctx(world,home,{},[("review",mod)]))
print(r["count"]==25, len(r["lessons"])==20, r["lessons"][0]==lines[-1], r["lessons"][-1]==lines[5])
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "review：lessons_list 只列最近 20 條，新的在前面"
  else
    fail "review：lessons_list 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_improve_prompt() {
  local root world got
  root=$(make_world review_improve_prompt); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); review=load_pack(home,"review"); fs=load_pack(home,"fs")
ctx=Ctx(world,home,{},[("review",review),("fs",fs)])
r=review.run("improve_prompt",{"pack":"fs","text":"一次只跑一條。"},ctx)
bad=review.run("improve_prompt",{"pack":"kids","text":"不生小孩。"},ctx)
print(r["chars"]==7, r["old_chars"]==0, r["notice"]=="下次走格才會生效",
      open(r["path"],encoding="utf-8").read()=="一次只跑一條。", "error" in bad)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "review：improve_prompt 只整份換掉已開啟工具包的覆蓋"
  else
    fail "review：improve_prompt 結果不對（$got）"
  fi
  rm -rf "$root"
}

test_review_triggers() {
  local root1 root2 root3 root4 got
  root1=$(make_world review_trigger_idle); root2=$(make_world review_trigger_cost)
  root3=$(make_world review_trigger_task); root4=$(make_world review_trigger_tool)
  got=$(python3 - "$HERE" "$root1/agent" "$root2/agent" "$root3/agent" "$root4/agent" <<'PYEOF2'
import datetime, glob, json, os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
def loaded(world):
    home=resolve_home(world,None); mod=load_pack(home,"review")
    return home,mod,Ctx(world,home,{"step":0},[("review",mod)])
home,mod,ctx=loaded(sys.argv[2])
for n in range(10): mod.on_act(ctx,"sh",{}, {},1)
for step in range(3): ctx.state["step"]=step; mod.on_idle(ctx)
mod.on_idle(ctx)
normal=glob.glob(os.path.join(home,"inbox","self","*.json"))
home2,mod2,ctx2=loaded(sys.argv[3]); now=datetime.datetime.now().replace(microsecond=0)
os.makedirs(os.path.join(home2,"ledger"),exist_ok=True)
open(os.path.join(home2,"ledger",now.date().isoformat()+".jsonl"),"w",encoding="utf-8").write(
    json.dumps({"time":now.isoformat(),"tool":"think","llm_round":{"cost":1.5}})+"\n")
conf=json.load(open(os.path.join(home2,"llm.json"),encoding="utf-8")); conf["review"]={"daily_cost":1.0}
json.dump(conf,open(os.path.join(home2,"llm.json"),"w",encoding="utf-8"),ensure_ascii=False)
mod2.on_idle(ctx2); mod2.on_idle(ctx2)
cost=glob.glob(os.path.join(home2,"inbox","self","*.json"))
home3,mod3,ctx3=loaded(sys.argv[4]); os.makedirs(os.path.join(home3,"ledger"),exist_ok=True)
task_rows=[]
for n,cost_value in ((1,0.1),(2,0.1),(3,0.25)):
    task_rows.append({"time":(now+datetime.timedelta(seconds=n)).isoformat(),"tool":"sh",
                      "task_key":"查檔","task_id":"t%d"%n,"llm_round":{"cost":cost_value}})
open(os.path.join(home3,"ledger",now.date().isoformat()+".jsonl"),"w",encoding="utf-8").write(
    "".join(json.dumps(row)+"\n" for row in task_rows))
mod3.on_idle(ctx3); task=glob.glob(os.path.join(home3,"inbox","self","*.json"))
home4,mod4,ctx4=loaded(sys.argv[5]); os.makedirs(os.path.join(home4,"ledger"),exist_ok=True)
tool_rows=[{"time":(now+datetime.timedelta(seconds=n)).isoformat(),"tool":"think","llm_round":{"cost":0.06}}
           for n in range(3)]
open(os.path.join(home4,"ledger",now.date().isoformat()+".jsonl"),"w",encoding="utf-8").write(
    "".join(json.dumps(row)+"\n" for row in tool_rows))
conf4=json.load(open(os.path.join(home4,"llm.json"),encoding="utf-8")); conf4["review"]={"tool_cost":{"think":0.05}}
json.dump(conf4,open(os.path.join(home4,"llm.json"),"w",encoding="utf-8"),ensure_ascii=False)
mod4.on_idle(ctx4); tool=glob.glob(os.path.join(home4,"inbox","self","*.json"))
print(len(normal)==1, json.load(open(normal[0],encoding="utf-8"))["content"]=="該回顧了",
      len(cost)==1, "今天花費超過" in json.load(open(cost[0],encoding="utf-8"))["reason"],
      len(task)==1, "同類平均兩倍" in json.load(open(task[0],encoding="utf-8"))["reason"],
      len(tool)==1, "連續三次" in json.load(open(tool[0],encoding="utf-8"))["reason"])
PYEOF2
)
  if [ "$got" = "True True True True True True True True" ]; then
    ok "review：idle、每日、任務與工具四種門檻都會提醒，且不重寄"
  else
    fail "review：提醒規則不對（$got）"
  fi
  rm -rf "$root1" "$root2" "$root3" "$root4"
}

test_lesson_archive() {
  local root world got
  root=$(make_world review_archive); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import datetime, glob, os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); os.makedirs(os.path.join(home,"memory"),exist_ok=True)
lines=["工作%d：原本平均 1 元／2 格 → 改法%d → 之後平均 0.5 元／1 格"%(n,n) for n in range(100)]
open(os.path.join(home,"memory","lessons.md"),"w",encoding="utf-8").write("\n".join(lines)+"\n")
mod=load_pack(home,"review"); ctx=Ctx(world,home,{},[("review",mod)])
new="新工作：原本平均 2 元／9 格 → 少繞路 → 之後平均 1 元／5 格"
r=mod.run("lesson_add",{"text":new},ctx)
kept=open(os.path.join(home,"memory","lessons.md"),encoding="utf-8").read().splitlines()
archive=glob.glob(os.path.join(home,"memory","lessons-archive","*.md"))
old=open(archive[0],encoding="utf-8").read().splitlines() if archive else []
print(r["archived"]==20, r["count"]==81, len(kept)==81, len(old)==20, old[0]==lines[0], kept[-1]==new)
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "review：第 101 條會歸檔最舊 20 條，現役仍低於上限"
  else
    fail "review：教訓歸檔不對（$got）"
  fi
  rm -rf "$root"
}

test_review_prompt_effect() {
  local root world got
  root=$(make_world review_prompt); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home, system_text
world=sys.argv[2]; home=resolve_home(world,None); os.makedirs(os.path.join(home,"memory"),exist_ok=True)
lesson="查檔：原本平均 0.2 元／6 格 → 先讀索引 → 之後平均 0.1 元／3 格"
open(os.path.join(home,"memory","lessons.md"),"w",encoding="utf-8").write(lesson+"\n")
review=load_pack(home,"review"); fs=load_pack(home,"fs"); loaded=[("review",review),("fs",fs)]
ctx=Ctx(world,home,{},loaded); old=system_text(ctx,loaded)
review.run("improve_prompt",{"pack":"fs","text":"FS_OVERRIDE_MARKER"},ctx)
new=system_text(ctx,loaded)
print("檔案與短指令" in old, "FS_OVERRIDE_MARKER" in new,
      "檔案與短指令" not in new, lesson in new)
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "review：packs-api 的 prompt override 生效，最近教訓也進 system prompt"
  else
    fail "review：prompt override 或教訓注入不對（$got）"
  fi
  rm -rf "$root"
}

test_review_recent
test_review_patterns
test_review_thoughts
test_lesson_add
test_lessons_list
test_improve_prompt
test_review_triggers
test_lesson_archive
test_review_prompt_effect
