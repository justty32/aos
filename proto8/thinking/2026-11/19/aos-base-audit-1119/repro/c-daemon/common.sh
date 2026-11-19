# Shared helpers for c-daemon repro scripts: start/stop a scratch daemon under c-daemon/run/, query its table.
# Usage: ~/.aos/scratch/aos-base-audit-1119/bin/clean bash ~/.aos/scratch/aos-base-audit-1119/c-daemon/repro/<x>.sh
ME=$HOME/.aos/scratch/aos-base-audit-1119/c-daemon

mkd() { # mkd NAME [interval_ms] [extra top-level json] -> sets D (root) S (stack), writes daemon.json
  D=$ME/run/$1; S=$D/stack; rm -rf "$D"; mkdir -p "$S"
  printf '%s\n' "{\"interval_ms\": ${2:-50}, \"procs\": {}${3:+, $3}}" > "$D/daemon.json"
}

tpid() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pid'])" "$S/procs_state.json" 2>/dev/null; }

startd() { # start daemon for $D/$S; real pid (from procs_state.json) recorded in $D/daemon.pid and $ME/mypids.txt
  local before p i
  before=$(tpid)
  ( cd "$D" && AOS_STACK=$S exec setsid aos-daemon --enable-logs "$D/daemon.json" >>"$D/daemon.log" 2>>"$D/daemon.err" </dev/null ) &
  for i in $(seq 200); do
    p=$(tpid)
    if [ -n "$p" ] && [ "$p" != "$before" ] && [ "$p" != None ] && kill -0 "$p" 2>/dev/null; then
      echo "$p" > "$D/daemon.pid"; echo "$p daemon $D" >> "$ME/mypids.txt"; return 0; fi
    sleep 0.05
  done
  echo "daemon did not come up"; tail -5 "$D/daemon.err"; return 1
}

dpid() { cat "$D/daemon.pid"; }
ctl() { timeout 20 aos-daemon-ctl -d "$S" "$@"; }
shut() { timeout 40 aos-daemon-ctl -d "$S" shutdown; }

rows() { python3 - "$S" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]+"/procs_state.json"))
for n,r in d["procs"].items():
    print(" ", n, r.get("phase"), "pid=%s"%r.get("pid"), "code=%s"%r.get("code"), "sig=%s"%r.get("signal"),
          "hit=%s"%r.get("limit_hit"), "sus=%s"%r.get("limit_suspect"), "reason=%s"%r.get("reason"))
PY
}
row() { python3 -c "import json,sys;r=json.load(open(sys.argv[1]))['procs'].get(sys.argv[2]);print(json.dumps(r) if r else 'NOROW')" "$S/procs_state.json" "$1"; }
phase() { python3 -c "import json,sys;r=json.load(open(sys.argv[1]))['procs'].get(sys.argv[2]);print(r['phase'] if r else 'NOROW')" "$S/procs_state.json" "$1" 2>/dev/null; }
ppid_of() { python3 -c "import json,sys;r=json.load(open(sys.argv[1]))['procs'].get(sys.argv[2]);print(r['pid'] if r else '')" "$S/procs_state.json" "$1" 2>/dev/null; }
waitphase() { # waitphase NAME PHASE [timeout_s]
  local t=$(( ${3:-10} * 20 )) i
  for i in $(seq $t); do [ "$(phase "$1")" = "$2" ] && return 0; sleep 0.05; done
  echo "  (timeout waiting $1=$2, now $(phase "$1"))"; return 1
}
alive() { kill -0 "$1" 2>/dev/null && echo alive || echo dead; }
now() { date +%s.%N; }
since() { python3 -c "import sys,time;print('%.2f'%(time.time()-float(sys.argv[1])))" "$1"; }
killmine() { # killmine SIG PID : only if its cwd is under $ME
  local c; c=$(readlink "/proc/$2/cwd" 2>/dev/null)
  case "$c" in "$ME"*) kill "-$1" "$2" ;; *) echo "  refuse kill $2 cwd=$c" ;; esac
}
mkscript() { # mkscript PATH BODY... : write an sh script with a comment header
  local p=$1; shift; printf '#!/bin/sh\n# repro body\n%s\n' "$*" > "$p"; chmod +x "$p"
}
