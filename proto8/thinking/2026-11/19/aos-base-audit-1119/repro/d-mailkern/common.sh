# 共用函式：在 d-mailkern/run/<名> 起一台只帶 stack 的暫存 daemon、等它開門、收它（只用 shutdown 或自己記的 pid）。由各 repro 腳本 source。
A=$HOME/.aos/scratch/aos-base-audit-1119
D=$A/d-mailkern
CLEAN=$A/bin/clean
RUN=$D/run
mkdir -p $RUN
c() { timeout ${T:-60} $CLEAN "$@"; }   # 經 clean 跑一個 aos 指令
start_daemon() {   # start_daemon DIR [daemon.json 內容]
  local dir=$1; mkdir -p $dir/stack
  [ -n "$2" ] && echo "$2" > $dir/daemon.json
  [ -f $dir/daemon.json ] || echo "{\"interval_ms\": 50, \"procs\": {}}" > $dir/daemon.json
  ( cd $dir && AOS_STACK_X=1 setsid $CLEAN env AOS_STACK=$dir/stack aos-daemon --enable-logs $dir/daemon.json >>$dir/daemon.log 2>>$dir/daemon.err & echo $! > $dir/daemon.pid )
  for i in $(seq 100); do [ -f $dir/stack/procs_state.json ] && grep -q "\"pid\"" $dir/stack/procs_state.json && { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[\"pid\"])" $dir/stack/procs_state.json > $dir/daemon.pid; return 0; }; sleep 0.1; done
  echo "daemon did not start: $(cat $dir/daemon.err)"; return 1
}
stop_daemon() { c aos-daemon-ctl -d $1/stack shutdown >/dev/null 2>&1; for i in $(seq 100); do kill -0 $(cat $1/daemon.pid) 2>/dev/null || return 0; sleep 0.1; done; echo "daemon $1 still alive"; }
ctl() { local d=$1; shift; c aos-daemon-ctl -d $d/stack "$@"; }
row() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]+\"/stack/procs_state.json\"));print(json.dumps(d[\"procs\"].get(sys.argv[2])))" $1 $2; }
