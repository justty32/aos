test_jobs_pack() {
  local root world home daemon job got
  root=$(make_world jobs_pack)
  world="$root/agent"
  home="$world/agent"
  daemon="$root/daemon"

  got=$(env -u AOS_DAEMON_DIR python3 - "$HERE" "$world" <<'PYEOF2'
import importlib.util, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
spec = importlib.util.spec_from_file_location("jobs", sys.argv[1] + "/packs/jobs.py")
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)
r = jobs.run("run_long", {"command": "echo no"}, Ctx(sys.argv[2], resolve_home(sys.argv[2], None)))
print(r.get("ok") is False and "AOS_DAEMON_DIR" in r.get("error", ""))
PYEOF2
)
  if [ "$got" = "True" ]; then
    ok "jobs：沒設 AOS_DAEMON_DIR 時 run_long 說清楚"
  else
    fail "jobs：沒 daemon 的錯誤不對（$got）"
  fi

  got=$(AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import importlib.util, json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
spec = importlib.util.spec_from_file_location("jobs", sys.argv[1] + "/packs/jobs.py")
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)
ctx = Ctx(sys.argv[2], resolve_home(sys.argv[2], None))
command = "printf 'one\\ntwo\\nthree\\n'; printf 'warn1\\nwarn2\\n' >&2"
r = jobs.run("run_long", {"command": command, "name": "demo"}, ctx)
job = os.path.join(ctx.home, "jobs", "demo")
inst = open(os.path.join(job, ".aos", "inst"), encoding="utf-8").read().splitlines()
saved = open(os.path.join(job, "cmd.sh"), encoding="utf-8").read()
print(r == {"ok": True, "name": "demo", "path": "jobs/demo"}, saved == command,
      len(inst) == 4, inst[1] == "timeout 3600 sh cmd.sh > stdout.log 2> stderr.log")
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "jobs：run_long 建好四行世界，cmd.sh 原樣保存"
  else
    fail "jobs：run_long 建出的世界不對（$got）"
  fi

  job="$home/jobs/demo"
  AOS_DAEMON_DIR="$daemon" "$AOS" "$job" >/dev/null 2>&1
  got=$(python3 - "$home" <<'PYEOF2'
import glob, json, os, sys
home = sys.argv[1]; job = os.path.join(home, "jobs", "demo")
r = json.load(open(os.path.join(job, "result.json"), encoding="utf-8"))
letters = glob.glob(os.path.join(home, "inbox", "jobs", "*.json"))
m = json.load(open(letters[0], encoding="utf-8")) if letters else {}
print(r["exit"] == 0, r["stdout_tail"] == "one\ntwo\nthree\n",
      r["stderr_tail"] == "warn1\nwarn2\n", m.get("from") == "jobs",
      "job demo 做完了" in m.get("content", ""))
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "jobs：aos-exec 推完後 result.json 與父的 jobs 信都正確"
  else
    fail "jobs：完成結果或寄信不對（$got）"
  fi

  got=$(AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import importlib.util, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
spec = importlib.util.spec_from_file_location("jobs", sys.argv[1] + "/packs/jobs.py")
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)
ctx = Ctx(sys.argv[2], resolve_home(sys.argv[2], None))
jobs.run("run_long", {"command": "sleep 30", "name": "stopme"}, ctx)
r = jobs.run("job_cancel", {"name": "stopme"}, ctx)
saved = ctx.read_json(os.path.join(ctx.home, "jobs", "stopme", "result.json"), {})
print(r == {"ok": True, "name": "stopme", "state": "cancelled"},
      saved.get("cancelled") is True, saved.get("exit") is None)
PYEOF2
)
  if [ "$got" = "True True True" ]; then
    ok "jobs：job_cancel 收鐘並寫 cancelled 結果"
  else
    fail "jobs：取消結果不對（$got）"
  fi

  got=$(AOS_DAEMON_DIR="$daemon" python3 - "$HERE" "$world" <<'PYEOF2'
import importlib.util, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
spec = importlib.util.spec_from_file_location("jobs", sys.argv[1] + "/packs/jobs.py")
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)
ctx = Ctx(sys.argv[2], resolve_home(sys.argv[2], None))
jobs.run("run_long", {"command": "sleep 30", "name": "still"}, ctx)
rows = jobs.run("jobs_list", {}, ctx)
states = {row["name"]: row["state"] for row in rows}
print(states == {"demo": "done", "still": "running", "stopme": "cancelled"},
      all(set(row) == {"name", "state", "exit", "seconds", "command"} for row in rows))
PYEOF2
)
  if [ "$got" = "True True" ]; then
    ok "jobs：jobs_list 分得出 running、done、cancelled"
  else
    fail "jobs：清單不對（$got）"
  fi

  got=$(python3 - "$HERE" "$world" <<'PYEOF2'
import importlib.util, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
spec = importlib.util.spec_from_file_location("jobs", sys.argv[1] + "/packs/jobs.py")
jobs = importlib.util.module_from_spec(spec); spec.loader.exec_module(jobs)
ctx = Ctx(sys.argv[2], resolve_home(sys.argv[2], None))
r = jobs.run("job_peek", {"name": "demo", "lines": 2}, ctx)
print(r.get("stdout") == "two\nthree", r.get("stderr") == "warn1\nwarn2")
PYEOF2
)
  if [ "$got" = "True True" ]; then
    ok "jobs：job_peek 只回指定的最後幾行"
  else
    fail "jobs：peek 不對（$got）"
  fi

  rm -rf "$root"
}

test_jobs_pack
