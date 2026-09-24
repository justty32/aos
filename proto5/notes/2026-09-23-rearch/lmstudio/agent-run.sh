#!/usr/bin/env bash
# T9：daemon → kernel → agent → 真模型 → date → 真模型，一整圈。
# 用法：agent-run.sh [工作目錄]（預設 $T4 或 ./t4）。LM Studio 須先開好。
# 重跑沿用 D、K、agent-bob（記憶累積）；每次回音另存 runs/，只驗新增記憶。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
AOS=$(cd "$HERE/../../.." && pwd)
CLI=$AOS/cli
T4=$(realpath -m "${1:-${T4:-./t4}}")
D=$T4/D; K=$T4/K; AG=$T4/agent-bob
mkdir -p "$T4/runs"
# 同一工作目錄不得同時跑兩份；鎖在工作目錄內。
exec 9>"$T4/run.lock"
flock -n 9 || { echo '工作目錄正被使用' >&2; exit 1; }
RUN=$(mktemp -d "$T4/runs/run-XXXXXXXX")
exec > >(tee "$RUN/transcript.txt") 2>&1
export PYTHONDONTWRITEBYTECODE=1
now() { python3 -c 'import time; print(time.monotonic())'; }
since() { python3 -c 'import sys; print("%.3f" % (float(sys.argv[2])-float(sys.argv[1])))' "$1" "$2"; }
peek() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print(v if isinstance(v,str) else json.dumps(v))' "$1" "$2" 2>/dev/null || echo null; }
waitfor() {
  local what=$1 cmd=$2 lim=${3:-20} end=$((SECONDS+${3:-20}))
  until eval "$cmd"; do
    if (( SECONDS >= end )); then echo "逾時：$what（${lim}s）" >&2; return 1; fi
    sleep 0.1
  done
}
processes() { pgrep -fa 'aos-cpu|aos-daemon|aos-kernel|aos-agent|aos-llm-call' | grep -Ev '(zsh|bash|sh) -c|pgrep' || true; }
[ -z "$(processes | grep -F "$T4" || true)" ] || { echo '本次目錄已有執行中的行程'; exit 1; }
DPID=; BOOTED=0; STARTED=0
shutdown() {
  local ts te
  ts=$(now)
  if (( STARTED )); then
    echo '$ aos-agent stop agent-bob'
    AOS_K=$K "$CLI/aos-agent" stop "$AG" || return $?
    echo 'aos-agent stop 退出碼 0（stdout/stderr 空）'
    STARTED=0
  fi
  if (( BOOTED )); then
    echo '$ aos-kernel stop K'
    "$CLI/aos-kernel" stop "$K" || return $?
    waitfor 'phase=stopped' '[ "$(peek "$K/state.json" phase)" = stopped ]' || return $?
    waitfor 'daemon 孩子表清空' '[ "$(peek "$D/state.json" children)" = "{}" ]' || return $?
    BOOTED=0
  fi
  if [ -n "$DPID" ]; then
    echo '$ aos-daemon stop --home D'
    "$CLI/aos-daemon" stop --home "$D" || return $?
    waitfor 'daemon 退出' '! kill -0 "$DPID" 2>/dev/null' || return $?
    local rc=0
    wait "$DPID" || rc=$?
    echo "daemon 退出碼 $rc"
    DPID=
    [ "$rc" = 0 ] || return "$rc"
  fi
  te=$(now)
  echo "停機：$(since "$ts" "$te") 秒"
}
finish() {
  local rc=$?
  trap - EXIT
  if [ -n "$DPID" ]; then shutdown || rc=1; fi
  for name in agent llm; do
    echo "--- log/$name.err ---"
    if [ -f "$AG/log/$name.err" ]; then
      cp "$AG/log/$name.err" "$RUN/$name.err"
      cat "$RUN/$name.err"
      [ -s "$RUN/$name.err" ] || echo '（空檔）'
    else echo '（不存在）'; fi
  done
  local mine
  mine=$(processes | grep -F "$T4" || true)
  echo "pgrep（本次 $T4）：${mine:-空}"
  [ -z "$mine" ] || rc=1
  echo "結果退出碼 $rc；原始回音：$RUN"
  exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
T0=$(now)
echo "== LM Studio：$(date -Is) =="
curl -sf -m 5 localhost:1234/v1/models > "$RUN/models.json"
python3 - "$RUN/models.json" <<'PY'
import json,sys
assert any(m['id']=='google/gemma-4-e4b' for m in json.load(open(sys.argv[1]))['data']), '模型未載入'
print('google/gemma-4-e4b 已在模型清單')
PY
mkdir -p "$D" "$T4/llm-home" "$AG/prompts" "$AG/tools"
[ -f "$D/info.json" ] || echo '{"_metainfo":{"_type":"daemon","_version":1},"poll_ms":20,"restart_delay_ms":1000,"stop_wait_ms":5000,"kill_wait_ms":5000}' > "$D/info.json"
setsid "$CLI/aos-daemon" --home "$D" </dev/null >/dev/null 2>>"$T4/daemon.stderr" 9>&- &
DPID=$!
waitfor 'daemon state.pid' '[ "$(peek "$D/state.json" pid)" = "$DPID" ]' 10
if [ ! -f "$K/info.json" ]; then
  "$CLI/aos-kernel" init "$K"
  python3 - "$HERE/agent-kernel-info.template.json" "$K/info.json" "$CLI" "$T4/llm-home/llm.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1]))
for cpu in ('0','llm'):
    v['cpus'][cpu]['envs']['PATH']['$fmt']['$val']=sys.argv[3]+':${p}'
v['cpus']['llm']['envs']['AOS_LLM_CONFIG']=sys.argv[4]
json.dump(v,open(sys.argv[2],'w'),ensure_ascii=False,indent=2)
PY
fi
python3 - "$T4" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])
files={
 'llm-home/llm.json': {'_metainfo':{'_type':'llm_config','_version':1},'models':{'small':{'endpoint':'http://127.0.0.1:1234/v1','model':'google/gemma-4-e4b','timeout_ms':180000}}},
 'agent-bob/info.json': {'_metainfo':{'_type':'llm_agent','_version':1},'llm':{'model':'small','params':{'temperature':0,'max_tokens':2048},'timeout_ms':190000},'tools':['tools/base.json'],'tick':{'interval_ms':500}},
 'agent-bob/prompts/system.json': {'content':'你是繁體中文助理。每次需要知道現在時間，都必須重新呼叫 date 工具，不可沿用先前時間。收到工具結果後，最後用一句繁體中文回答使用者。'},
 'agent-bob/tools/base.json': [{'type':'function','function':{'name':'date','description':'取得現在的本機日期與時間','parameters':{'type':'object','properties':{},'required':[]}},'_meta':{'argv':['date','+%Y-%m-%d %H:%M:%S']}}],
}
for name,value in files.items():
    p=base/name
    if not p.exists(): p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
PY
BOOTED=1
"$CLI/aos-kernel" boot "$K" --daemon "$D"
waitfor 'kernel running' '[ "$(peek "$K/state.json" phase)" = running ]' 10
"$CLI/aos-kernel" ls "$K"
echo '$ AOS_K=$K aos-agent start agent-bob'
TS=$(now)
AOS_K=$K "$CLI/aos-agent" start "$AG"
STARTED=1
TE=$(now)
echo "aos-agent start 退出碼 0（stdout/stderr 空）；start：$(since "$TS" "$TE") 秒"
python3 -u - "$AG" "$RUN" <<'PY'
import datetime,json,os,sys,time
from pathlib import Path
ag,run=map(Path,sys.argv[1:])
def read(name,default):
    try: return json.loads((ag/name).read_text())
    except FileNotFoundError: return default
history=read('prompts/history.json',[])
state=read('state.json',{'state':'idle'})
assert state['state']=='idle' and not state.get('batch') and not state.get('waits'), '既有 agent 尚未 idle 或門關著'
assert not (ag/'input.json').exists(), '尚有未消費的輸入'
base=len(history)
started=time.monotonic()
events=[]
def event(label,st,n):
    e={'time':datetime.datetime.now().astimezone().isoformat(timespec='milliseconds'),'seconds':round(time.monotonic()-started,3),'event':label,'state':st,'history_len':n}
    events.append(e)
    print(json.dumps(e,ensure_ascii=False),flush=True)
    (run/'events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n')
event('投件前','idle',base)
(ag/'input.json.tmp').write_text(json.dumps('現在幾點？請用工具查。',ensure_ascii=False))
os.replace(ag/'input.json.tmp',ag/'input.json')
event('投件','idle',base)
previous=('idle',base)
while time.monotonic()-started < 300:
    st=read('state.json',{'state':'idle'})
    history=read('prompts/history.json',[])
    current=(st['state'],len(history))
    if current!=previous:
        event('state 變化' if current[0]!=previous[0] else '記憶增長',*current)
        previous=current
    tail=history[base:]
    if st['state']=='idle' and len(tail)>=4:
        assert [m['role'] for m in tail]==['user','assistant','tool','assistant'], '本次訊息順序不符'
        calls=tail[1].get('tool_calls',[])
        assert len(calls)==1 and calls[0]['function']['name']=='date'
        assert tail[2]['tool_call_id']==calls[0]['id'] and tail[2]['content'].strip()
        assert not tail[3].get('tool_calls') and tail[3].get('content','').strip(), '最後回覆不是非空純文字'
        assert not st.get('batch') and not st.get('errors'), '仍有當批或失敗'
        (run/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n')
        print('--- 最後記憶全文 ---')
        print((run/'history.json').read_text())
        print('投件→idle 整圈：%.3f 秒' % (time.monotonic()-started))
        break
    time.sleep(.05)
else:
    print(json.dumps(st,ensure_ascii=False,indent=2))
    raise SystemExit('逾時：300 秒內未完成工具整圈')
PY
shutdown
TF=$(now)
echo "起 daemon→停完：$(since "$T0" "$TF") 秒"
