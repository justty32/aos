# 共用：照 templates/kernel/llm-kernel 抄一台 llm kernel 到 d-mailkern/run/<名>/llm，kernel.json 換成只有假腦（不碰 127.0.0.1:4000），起／收這台。由 llmk_*.sh source。
source $(dirname ${BASH_SOURCE[0]})/common.sh
SRC=$A/src/proto8
llmk_setup() {   # llmk_setup DIR [kernel.json 的額外頂層鍵，JSON 片段，例 "\"budget\": {...},"]
  local K=$1; rm -rf $K; mkdir -p $K/eps
  cp -r $SRC/templates/kernel/llm-kernel $K/def
  cat > $K/eps/fk <<"P"
#!/usr/bin/env python3
# 假端點：照 endpoint 的 mode／delay_s／tokens 回答；每次被叫記一行到 calls.log（數重複呼叫）。
import json, os, sys, time
a = json.load(sys.stdin); ep = a.get("endpoint", {}); mode = ep.get("mode", "ok")
log = os.path.join(os.path.dirname(os.path.realpath(__file__)), "calls.log")
with open(log, "a") as f: f.write(json.dumps({"pid": os.getpid(), "mode": mode, "t": time.time(), "msg": a["request"]["messages"][-1].get("content")}) + "\n")
time.sleep(float(ep.get("delay_s", 0)))
if mode == "hang": time.sleep(3600)
if mode == "fail": print("fk: error: Boom simulated failure", file=sys.stderr); sys.exit(1)
if mode == "failjson": print(json.dumps({"error": {"code": "EndpointFailed", "msg": "simulated 503", "retry": True}})); sys.exit(1)
if mode == "badjson": print("this is not json"); sys.exit(0)
t = int(ep.get("tokens", 0))
print(json.dumps({"message": {"role": "assistant", "content": "FK " + str(a["request"]["messages"][-1].get("content"))}, "usage": {"total_tokens": t}, "model": "fk"}))
P
  chmod +x $K/eps/fk
  cat > $K/def/kernel.json <<J
{"description": "audit kernel, fake endpoints only", "slots": 4, ${2} "exec": {"\$env": "AOS_HOME", "\$path": "/lib/tools/base/llm_fake"}, "endpoint": "fake",
 "endpoints": {
  "fake": {"exec": {"\$env": "AOS_HOME", "\$path": "/lib/tools/base/llm_fake"}, "speed": "fast", "cost": "free"},
  "tok":  {"exec": "$K/eps/fk", "tokens": 100},
  "slow": {"exec": "$K/eps/fk", "delay_s": 6, "tokens": 10},
  "fail": {"exec": "$K/eps/fk", "mode": "fail"},
  "failjson": {"exec": "$K/eps/fk", "mode": "failjson"},
  "badjson": {"exec": "$K/eps/fk", "mode": "badjson"},
  "hang": {"exec": "$K/eps/fk", "mode": "hang"},
  "once": {"exec": "$K/eps/fk", "budget": {"max_calls": 1}}}}
J
  ! grep -qE "localhost|127\.0\.0\.1|:4000|:1234" $K/def/kernel.json || { echo "REFUSE: real endpoint in kernel.json"; return 1; }
}
llmk_start() {   # llmk_start DIR
  local K=$1; mkdir -p $K/stack
  ( cd $K && setsid $CLEAN aos-exec --stack $K/stack $K/def >>$K/daemon.log 2>>$K/daemon.err & )
  for i in $(seq 150); do [ -f $K/stack/procs_state.json ] && grep -q "\"pid\"" $K/stack/procs_state.json && [ -d $K/stack/requests/new ] && break; sleep 0.1; done
  python3 -c "import json;print(json.load(open(\"$K/stack/procs_state.json\"))[\"pid\"])" > $K/daemon.pid
  [ "$(readlink /proc/$(cat $K/daemon.pid)/cwd)" = "$K/def" ] || echo "WARN: daemon cwd $(readlink /proc/$(cat $K/daemon.pid)/cwd)"
}
llmk_stop() { stop_daemon $1; }
ask() {   # ask DIR ENDPOINT TEXT [timeout]
  echo "{\"endpoint\": \"$2\", \"request\": {\"messages\": [{\"role\": \"user\", \"content\": \"$3\"}]}}" | T=${4:-30} c env AOS_LLM_KERNEL=$1/stack aos-llm ask; echo "ask-exit=$?"
}
