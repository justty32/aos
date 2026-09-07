# branch：共用旁線一次收齊，模型不必查「還差幾條」。

test_branch_lifecycle() {
  local root got
  root=$(make_world branch_lifecycle)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import json, os, sys
sys.path.insert(0,sys.argv[1])
from aos_agent import Ctx,resolve_home
from packs import branch
w=sys.argv[2]; h=resolve_home(w,None); state={"step":1,"pending":[]}
ctx=Ctx(w,h,state,[("branch",branch)],"branch")
r=branch.run("fork",{"directions":["支持","反對","邊界"]},ctx)
meta=Ctx.read_json(os.path.join(h,"branches",r["branch_id"],"meta.json"),{})
early=branch.run("join",{"branch_id":r["branch_id"]},ctx)
for n,item in enumerate(state["pending"],1):
    Ctx.write_json(os.path.join(item["result_dir"],item["result_name"]),{
      "choices":[{"message":{"content":"方向%d結論"%n}}],
      "aos":{"usage":{"total_tokens":n}}})
wake=ctx.collect_results()
joined=branch.run("join",{"branch_id":r["branch_id"]},ctx)
print(r["count"]==3, len(meta["lines"])==3 and len(state.get("pending",[]))==0,
      "還差" not in early.get("error",""), len(wake)==1 and "3 條分支都到齊" in wake[0]["content"],
      len(joined.get("branches",[]))==3 and joined["total_usage"]["total_tokens"]==6,
      state.get("sleeping") is None)
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "branch：fork 後睡著，共用層一次收齊再喚醒"
  else
    fail "branch：共用生命週期不對（$got）"
  fi
  rm -rf "$root"
}

test_branch_files() {
  local root got
  root=$(make_world branch_files)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import glob,json,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import branch
w=sys.argv[2];h=resolve_home(w,None);state={"pending":[]};ctx=Ctx(w,h,state,pack="branch")
r=branch.run("fork",{"directions":["甲","乙"]},ctx); root=os.path.join(h,"branches",r["branch_id"])
print(os.path.isfile(os.path.join(root,"base.json")),len(glob.glob(os.path.join(root,"[0-9][0-9]","prompts.json")))==2,
      all(set(x)>={"id","kind","pack","since_ts","timeout_s"} for x in state["pending"]),
      "branches" not in state)
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "branch：只留分支內容，不在 state 重複存 pending"
  else
    fail "branch：落檔不對（$got）"
  fi
  rm -rf "$root"
}

test_branch_adopt() {
  local root got
  root=$(make_world branch_adopt)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import branch
w=sys.argv[2];h=resolve_home(w,None);state={"pending":[]};ctx=Ctx(w,h,state,pack="branch")
r=branch.run("fork",{"directions":["甲","乙"]},ctx); bid=r["branch_id"]
for item in list(state["pending"]):
    branch.on_result(ctx,"branch",item["id"],{"choices":[{"message":{"content":"完成"}}]})
out=branch.run("adopt",{"branch_id":bid,"n":2},ctx)
prompts=Ctx.read_json(os.path.join(h,"prompts.json"),[])
print(out.get("n")==2, prompts[-1].get("content")=="完成", state.get("branch_depth")==1)
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "branch：adopt 仍能接手完成分支"
  else
    fail "branch：adopt 不對（$got）"
  fi
  rm -rf "$root"
}

test_branch_guards() {
  local root got
  root=$(make_world branch_guard)
  got=$(python3 - "$HERE" "$root/agent" <<'PYEOF2'
import sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import branch
w=sys.argv[2];h=resolve_home(w,None)
a=branch.run("fork",{"directions":["只一條"]},Ctx(w,h,{"pending":[]},pack="branch"))
b=branch.run("fork",{"directions":["甲","乙"]},Ctx(w,h,{"pending":[],"branch_depth":1},pack="branch"))
c=branch.run("fork",{"directions":["甲","乙"],"budget":{"per_branch_tokens":1500,"total_tokens":100}},Ctx(w,h,{"pending":[]},pack="branch"))
print("error" in a,"error" in b,"error" in c)
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "branch：方向數、巢狀與預算護欄仍在"
  else
    fail "branch：護欄不對（$got）"
  fi
  rm -rf "$root"
}

test_branch_lifecycle
test_branch_files
test_branch_adopt
test_branch_guards
