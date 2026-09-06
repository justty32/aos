# think：送出就睡，共用層接回；沒有狀態輪詢工具。

think_ctx() {
  :
}

test_think_request() {
  local root got
  root=$(make_world think_request)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import json,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import think
w=sys.argv[2];h=resolve_home(w,None);state={"step":2,"pending":[]};ctx=Ctx(w,h,state,pack="think")
engines=Ctx.read_json(os.path.join(ctx.llm_dir(),"engines.json"),[]);engines[0]["role"]="thinker"
Ctx.write_json(os.path.join(ctx.llm_dir(),"engines.json"),engines)
r=think.run("think",{"question":"三件事怎麼選？","budget":{"max_tokens":1234}},ctx)
item=state["pending"][0]; body=Ctx.read_json(item["request_path"],{})
print(r["text"].startswith("開始想了 id="),item["kind"]=="think",item["id"]==state["sleeping"]["id"],
      body.get("engine")=="local",body.get("params")=={"max_tokens":1234},
      all(t["name"]!="think_status" and t["name"]!="conclude" for t in think.TOOLS))
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "think：選 thinker、帶預算、送出就睡，輪詢與 conclude 工具已刪"
  else
    fail "think：送出契約不對（$got）"
  fi
  rm -rf "$root"
}

test_think_result() {
  local root got
  root=$(make_world think_result)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import glob,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import think
w=sys.argv[2];h=resolve_home(w,None);state={"state":"idle","step":1,"pending":[]}
ctx=Ctx(w,h,state,[("think",think)],"think")
r=think.run("think",{"question":"公平怎麼定義？"},ctx); item=state["pending"][0]
Ctx.write_json(os.path.join(item["result_dir"],item["result_name"]),{
 "choices":[{"message":{"content":'{"conclusion":"先公開規則","action":"先說規則","risk":"有人不同意"}'}}],
 "aos":{"usage":{"total_tokens":18,"completion_tokens":7}}})
wake=ctx.collect_results(); folder=os.path.join(h,"thoughts",r["thought_id"])
meta=Ctx.read_json(os.path.join(folder,"meta.json"),{}); step=Ctx.read_json(os.path.join(folder,"01.json"),{})
side=glob.glob(os.path.join(h,"side","think","*.json"))
print(meta.get("status")=="done",step.get("conclusion")=="先公開規則",
      len(side)==1,len(wake)==1 and "先公開規則" in wake[0]["content"],
      state.get("sleeping") is None and state["pending"]==[])
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "think：共用層收結果、落 side 與 thoughts、直接喚醒"
  else
    fail "think：收結果不對（$got）"
  fi
  rm -rf "$root"
}

test_think_steps() {
  local root got
  root=$(make_world think_steps)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import json,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import think
w=sys.argv[2];h=resolve_home(w,None);state={"step":1,"pending":[]}
ctx=Ctx(w,h,state,[("think",think)],"think")
r=think.run("think_steps",{"question":"怎麼公平分披薩？"},ctx); bodies=[]; wakes=[]
for text in ("第一步","第二步","第三步"):
    item=state["pending"][0]; bodies.append(Ctx.read_json(item["request_path"],{}))
    Ctx.write_json(os.path.join(item["result_dir"],item["result_name"]),{
      "choices":[{"message":{"content":json.dumps({"conclusion":text},ensure_ascii=False)}}],
      "aos":{"usage":{"completion_tokens":4,"total_tokens":4}}})
    wakes += ctx.collect_results()
meta=Ctx.read_json(os.path.join(h,"thoughts",r["thought_id"],"meta.json"),{})
u2=bodies[1]["messages"][-1]["content"];u3=bodies[2]["messages"][-1]["content"]
print(meta.get("step")==3 and meta.get("status")=="done",len(wakes)==1,
      "第一步" in u2,"第二步" in u3 and "第一步" not in u3,state["pending"]==[])
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "think_steps：三步自動接力，只在最後喚醒一次"
  else
    fail "think_steps：接力不對（$got）"
  fi
  rm -rf "$root"
}

test_think_timeout() {
  local root got
  root=$(make_world think_timeout)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import glob,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import think
w=sys.argv[2];h=resolve_home(w,None);state={"step":5,"pending":[]}
ctx=Ctx(w,h,state,[("think",think)],"think")
r=think.run("think",{"question":"等不到怎麼辦？","budget":{"wait_steps":1}},ctx)
state["step"]=6;wake=ctx.collect_results()
meta=Ctx.read_json(os.path.join(h,"thoughts",r["thought_id"],"meta.json"),{})
errors=[Ctx.read_json(p,{}) for p in glob.glob(os.path.join(h,"outbox","*.json"))]
print(meta.get("status")=="error",not wake,len(errors)==1 and errors[0].get("error") is True,
      state["pending"]==[])
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "think：逾時由共用層回聊天錯誤，不再自己輪詢"
  else
    fail "think：逾時不對（$got）"
  fi
  rm -rf "$root"
}

test_think_critique_read() {
  local root got
  root=$(make_world think_critique)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import json,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import think
w=sys.argv[2];h=resolve_home(w,None);state={"pending":[]};ctx=Ctx(w,h,state,[("think",think)],"think")
r=think.run("critique",{"draft":"草稿"},ctx);item=state["pending"][0]
items=[{"problem":"漏洞%d"%n,"why":"原因","fix":"修法"} for n in range(1,5)]
Ctx.write_json(os.path.join(item["result_dir"],item["result_name"]),{
 "choices":[{"message":{"content":json.dumps({"items":items},ensure_ascii=False)}}]})
ctx.collect_results(); listed=think.run("thoughts_list",{},ctx); read=think.run("thought_read",{"id":r["thought_id"]},ctx)
print("漏洞1" in read["conclusion"],"漏洞3" in read["conclusion"],"漏洞4" not in read["conclusion"],
      listed[0]["id"]==r["thought_id"],len(read["steps"])==1)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "think：critique、清單與重讀仍可用"
  else
    fail "think：critique 或查詢不對（$got）"
  fi
  rm -rf "$root"
}

test_think_request
test_think_result
test_think_steps
test_think_timeout
test_think_critique_read
