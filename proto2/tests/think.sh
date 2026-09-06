enable_think_pack() {
  python3 - "$1/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["packs"] = ["think"]
d["tools"] = []
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
}

test_think_engine_and_budget() {
  local root world home got
  root=$(make_world think_engine); world="$root/agent"; home="$world/agent"
  python3 - "$root/llm/engines.json" <<'PYEOF2'
import json, sys
p=sys.argv[1]; rows=json.load(open(p, encoding="utf-8")); rows[0]["role"]="thinker"
json.dump(rows, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world, None); state={"state":"idle", "step":2, "pending":[]}
ctx=Ctx(world, home, state); pack=load_pack(home, "think")
answer=pack.run("think", {"question":"三件事怎麼選？", "budget":{"max_tokens":1234}}, ctx)
request=state["pending"][0]["name"]
body=json.load(open(os.path.join(ctx.llm_dir(),"requests",request), encoding="utf-8"))
engines=ctx.read_json(os.path.join(ctx.llm_dir(),"engines.json"),[]); engines[0].pop("role",None)
ctx.write_json(os.path.join(ctx.llm_dir(),"engines.json"),engines)
own=ctx.read_json(os.path.join(home,"llm.json"),{}); own["engine"]="deepseek-flash"
ctx.write_json(os.path.join(home,"llm.json"),own)
pack.run("think", {"question":"沒有 thinker 怎麼辦？"}, ctx)
body2=json.load(open(os.path.join(ctx.llm_dir(),"requests",state["pending"][-1]["name"]),encoding="utf-8"))
print(answer["text"].startswith("開始想了 id="), body.get("engine") == "local",
      body.get("params") == {"max_tokens":1234}, state["pending"][0]["kind"] == "think",
      "thoughts/" in open(os.path.join(home,".gitignore"),encoding="utf-8").read().splitlines(),
      body2.get("engine") == "deepseek-flash" and body2.get("params",{}).get("max_tokens") == 6000)
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "think：優先選 thinker，沒有就沿用原 engine；帶 kind／max_tokens 且不進 git"
  else
    fail "think：引擎或預算請求不對（$got）"
  fi
  rm -rf "$root"
}

test_think_result_without_main_state_change() {
  local root world home got
  root=$(make_world think_result); world="$root/agent"; home="$world/agent"
  enable_think_pack "$home"
  python3 - "$HERE" "$world" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_packs, resolve_home, write_json
world=sys.argv[2]; home=resolve_home(world, None)
state={"state":"wait", "step":9, "busy":4, "request":"main-never.json", "wait_ticks":0,
       "pending":[], "started":"2026-09-06T00:00:00"}
loaded,_=load_packs(home); ctx=Ctx(world,home,state,loaded)
answer=dict(loaded)["think"].run("think", {"question":"公平怎麼定義？"}, ctx.for_pack("think"))
request=state["pending"][0]["name"]
ctx.write_json(os.path.join(ctx.llm_dir(),"results",request), {
  "choices":[{"message":{"role":"assistant","content":
    '{"conclusion":"先公開規則","reasons":["可檢查"],"action":"先說規則","risk":"有人不同意"}'}}],
  "aos":{"engine":"local","usage":{"prompt_tokens":11,"completion_tokens":7,"total_tokens":18}}})
write_json(os.path.join(home,"state.json"), state)
PYEOF2
  agent_tick "$world"
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
h=sys.argv[1]; s=json.load(open(os.path.join(h,"state.json"),encoding="utf-8"))
folders=glob.glob(os.path.join(h,"thoughts","*")); folder=folders[0] if folders else ""
m=json.load(open(os.path.join(folder,"meta.json"),encoding="utf-8")) if folder else {}
step=json.load(open(os.path.join(folder,"01.json"),encoding="utf-8")) if folder else {}
mail=glob.glob(os.path.join(h,"inbox","think","*.json"))
conclusion=open(os.path.join(folder,"conclusion.md"),encoding="utf-8").read().strip() if folder else ""
print(m.get("status") == "done", step.get("conclusion") == "先公開規則", conclusion == "先公開規則",
      len(mail) == 1, s.get("state") == "wait", s.get("request") == "main-never.json",
      s.get("busy") == 4, s.get("pending") == [])
PYEOF2
)
  if [ "$got" = "True True True True True True True True" ]; then
    ok "think：結果落 thoughts 並寄提醒，主線 wait／request／busy 沒被旁線改掉"
  else
    fail "think：收結果或主線隔離不對（$got）"
  fi
  rm -rf "$root"
}

test_think_steps_three_requests() {
  local root world got
  root=$(make_world think_steps); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); state={"state":"wait","step":3,"pending":[]}
ctx=Ctx(world,home,state); pack=load_pack(home,"think")
answer=pack.run("think_steps", {"question":"怎麼公平分披薩？"}, ctx)
tid=answer["thought_id"]; requests=[]; bodies=[]
for text in ("第一步秘密", "第二步結論", "第三步答案"):
    name=next(iter(state["think_requests"]))
    requests.append(name)
    bodies.append(json.load(open(os.path.join(ctx.llm_dir(),"requests",name),encoding="utf-8")))
    pack.on_result(ctx,"think",name,{"choices":[{"message":{"content":json.dumps({"conclusion":text},ensure_ascii=False)}}],
                                     "aos":{"usage":{"completion_tokens":4,"total_tokens":4}}})
folder=os.path.join(home,"thoughts",tid); meta=json.load(open(os.path.join(folder,"meta.json"),encoding="utf-8"))
u2=bodies[1]["messages"][-1]["content"]; u3=bodies[2]["messages"][-1]["content"]
print(len(requests) == 3, all(os.path.isfile(os.path.join(folder,"%02d.json"%n)) for n in (1,2,3)),
      meta.get("status") == "done", "怎麼公平分披薩？" in u2 and "第一步秘密" in u2,
      "怎麼公平分披薩？" in u3 and "第二步結論" in u3 and "第一步秘密" not in u3)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "think_steps：固定走三個請求，下一步只帶原題與上一步短結論"
  else
    fail "think_steps：三步接力不對（$got）"
  fi
  rm -rf "$root"
}

test_conclude_only_adds_conclusion() {
  local root world home reply got
  root=$(make_world think_conclude); world="$root/agent"; home="$world/agent"
  enable_think_pack "$home"
  python3 - "$home" <<'PYEOF2'
import json, os, sys
h=sys.argv[1]; d=os.path.join(h,"thoughts","fixed"); os.makedirs(d)
json.dump({"id":"fixed","kind":"think_steps","question":"原問題","status":"done","step":1,
           "usage":{"total_tokens":9},"final":{"conclusion":"公平輪流選","action":"抽籤決定先後","risk":"切片大小不同"}},
          open(os.path.join(d,"meta.json"),"w",encoding="utf-8"),ensure_ascii=False)
json.dump({"step":1,"conclusion":"隱藏過程不能進記憶"},open(os.path.join(d,"01.json"),"w",encoding="utf-8"),ensure_ascii=False)
open(os.path.join(d,"conclusion.md"),"w",encoding="utf-8").write("公平輪流選\n")
PYEOF2
  reply=$(say_and_wait "$world" "$root/llm" 'CALL conclude {"thought_id":"fixed"}' 20) || true
  got=$(python3 - "$home/prompts.json" <<'PYEOF2'
import json, sys
rows=json.load(open(sys.argv[1],encoding="utf-8")); tools=[r for r in rows if r.get("role")=="tool"]
text=tools[-1].get("content","") if tools else ""
print("公平輪流選" in text, "抽籤決定先後" in text, "隱藏過程不能進記憶" not in json.dumps(rows,ensure_ascii=False))
PYEOF2
)
  if [ -n "$reply" ] && [ "$got" = "True True True" ]; then
    ok "think：conclude 只把最後結論、動作、風險與用量接進主線記憶"
  else
    fail "think：conclude 把逐步內容帶進記憶或沒走完（reply=$reply，$got）"
  fi
  rm -rf "$root"
}

test_think_timeout() {
  local root world got
  root=$(make_world think_timeout); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import glob, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); state={"state":"idle","step":5,"pending":[]}
ctx=Ctx(world,home,state); pack=load_pack(home,"think")
answer=pack.run("think",{"question":"等不到怎麼辦？","budget":{"wait_steps":1}},ctx)
state["step"]=6; pack.on_idle(ctx)
meta=json.load(open(os.path.join(home,"thoughts",answer["thought_id"],"meta.json"),encoding="utf-8"))
mail=glob.glob(os.path.join(home,"inbox","think","*.json"))
print(meta.get("status") == "timeout", len(mail) == 1, state.get("think_requests") == {})
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "think：超過 budget.wait_steps 後標成 timeout 並只提醒一次"
  else
    fail "think：逾時標記不對（$got）"
  fi
  rm -rf "$root"
}

test_think_keeps_best_when_last_step_empty() {
  local root world got
  root=$(make_world think_best); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); state={"state":"wait","step":1,"pending":[]}
ctx=Ctx(world,home,state); pack=load_pack(home,"think")
answer=pack.run("think_steps",{"question":"最後一格用完怎麼辦？"},ctx)
for text in ("第一步可用", "第二步是目前最好", ""):
    name=next(iter(state["think_requests"]))
    pack.on_result(ctx,"think",name,{"choices":[{"message":{"content":text}}],
                                     "aos":{"usage":{"completion_tokens":2}}})
meta=json.load(open(os.path.join(home,"thoughts",answer["thought_id"],"meta.json"),encoding="utf-8"))
out=pack.run("conclude",{"thought_id":answer["thought_id"]},ctx)
print(meta.get("status") == "budget_exceeded", out.get("conclusion") == "第二步是目前最好")
PYEOF2
)
  if [ "$got" = "True True" ]; then
    ok "think_steps：最後一格只有隱藏思考、正文空白時保留上一個可用結論"
  else
    fail "think_steps：空白尾步沒有保住目前最好結論（$got）"
  fi
  rm -rf "$root"
}

test_critique_and_thought_readers() {
  local root world got
  root=$(make_world think_critique); world="$root/agent"
  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import json, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, load_pack, resolve_home
world=sys.argv[2]; home=resolve_home(world,None); state={"state":"idle","step":1,"pending":[]}
ctx=Ctx(world,home,state); pack=load_pack(home,"think")
answer=pack.run("critique",{"draft":"這是一份草稿"},ctx); name=next(iter(state["think_requests"]))
items=[{"problem":"漏洞%d"%n,"why":"重要%d"%n,"fix":"修法%d"%n} for n in range(1,5)]
pack.on_result(ctx,"think",name,{"choices":[{"message":{"content":json.dumps({"items":items},ensure_ascii=False)}}],
                                 "aos":{"usage":{"total_tokens":8}}})
done=pack.run("conclude",{"thought_id":answer["thought_id"]},ctx)
listed=pack.run("thoughts_list",{},ctx); read=pack.run("thought_read",{"id":answer["thought_id"]},ctx)
print("漏洞1" in done.get("conclusion",""), "漏洞3" in done.get("conclusion",""),
      "漏洞4" not in done.get("conclusion",""), listed[0].get("id") == answer["thought_id"],
      read.get("question") == "這是一份草稿" and len(read.get("steps",[])) == 1)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "think：critique 最多三條，thoughts_list／thought_read 可重查"
  else
    fail "think：critique 或思考查詢不對（$got）"
  fi
  rm -rf "$root"
}

test_think_engine_and_budget
test_think_result_without_main_state_change
test_think_steps_three_requests
test_conclude_only_adds_conclusion
test_think_timeout
test_think_keeps_best_when_last_step_empty
test_critique_and_thought_readers
