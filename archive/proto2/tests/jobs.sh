# jobs：長工作也走 Ctx 旁線。

test_jobs_missing_clock() {
  local root got
  root=$(make_world jobs_missing)
  got=$(env -u AOS_DAEMON_DIR python3 - "$HERE" "$root/agent" <<'PYEOF2'
import glob,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import jobs
w=sys.argv[2];h=resolve_home(w,None);r=jobs.run("run_long",{"command":"echo no"},Ctx(w,h,pack="jobs"))
mail=Ctx.read_json(glob.glob(h+"/outbox/*.json")[0],{})
print(r.get("ok") is False,mail.get("error") is True,"沒有鐘" in mail.get("content",""))
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "jobs：缺鐘直接回聊天錯誤"
  else
    fail "jobs：缺鐘錯誤不對（$got）"
  fi
  rm -rf "$root"
}

test_jobs_lifecycle() {
  local root world home daemon got
  root=$(make_world jobs_lifecycle);world="$root/agent";home="$world/agent";daemon="$root/daemon"
  AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import jobs
w=sys.argv[2];h=resolve_home(w,None);state={"step":1,"pending":[]}
ctx=Ctx(w,h,state,[("jobs",jobs)],"jobs")
r=jobs.run("run_long",{"command":"printf 'one\ntwo\n'; printf 'warn\n' >&2","name":"demo"},ctx)
Ctx.write_json(os.path.join(h,"state.json"),state)
assert r.get("ok") and state.get("sleeping",{}).get("kind")=="jobs"
PYEOF2
  AOS_DAEMON_DIR="$daemon" "$AOS" "$home/jobs/demo" >/dev/null 2>&1
  got=$(AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import glob,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import jobs
w=sys.argv[2];h=resolve_home(w,None);state=Ctx.read_json(os.path.join(h,"state.json"),{})
ctx=Ctx(w,h,state,[("jobs",jobs)],"jobs");wake=ctx.collect_results()
rows=jobs.run("jobs_list",{},ctx);peek=jobs.run("job_peek",{"name":"demo","lines":1},ctx)
side=glob.glob(os.path.join(h,"side","jobs","*.json"))
print(len(wake)==1 and "demo 做完" in wake[0]["content"],len(side)==1,
      rows[0]["state"]=="done" and rows[0]["exit"]==0,
      peek["stdout"]=="two" and peek["stderr"]=="warn",state.get("sleeping") is None)
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "jobs：完成後只由共用層搬結果、喚醒並可查輸出"
  else
    fail "jobs：完成流程不對（$got）"
  fi
  rm -rf "$root"
}

test_jobs_cancel() {
  local root world daemon got
  root=$(make_world jobs_cancel);world="$root/agent";daemon="$root/daemon"
  got=$(AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import glob,os,sys
sys.path.insert(0,sys.argv[1]); from aos_agent import Ctx,resolve_home
from packs import jobs
w=sys.argv[2];h=resolve_home(w,None);state={"step":1,"pending":[]}
ctx=Ctx(w,h,state,[("jobs",jobs)],"jobs")
jobs.run("run_long",{"command":"sleep 30","name":"stopme"},ctx)
r=jobs.run("job_cancel",{"name":"stopme"},ctx)
side=Ctx.read_json(glob.glob(os.path.join(h,"side","jobs","*.json"))[0],{})
rows=jobs.run("jobs_list",{},ctx)
print(r.get("state")=="cancelled",side.get("kind_of_error")=="cancelled",
      state["pending"]==[],rows[0]["state"]=="cancelled")
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "jobs：取消也走共用 cancelled 結果"
  else
    fail "jobs：取消不對（$got）"
  fi
  rm -rf "$root"
}

test_jobs_missing_clock
test_jobs_lifecycle
test_jobs_cancel
