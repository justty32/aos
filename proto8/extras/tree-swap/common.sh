# common.sh - tree-swap 腳本共用：預設路徑、「樹在跑」偵測（只看 daemon／loop）、計時（被 source，不單獨跑）
# 線換 11-13 晚；規格見 wf/workflows/dispatch/aos-teams/06「停樹換檔的做法」。

[ -n "$BASH_VERSION" ] || { echo "tree-swap: not bash, refuse" >&2; exit 2; }

TS_TREE=${TS_TREE:-$HOME/aos-home}
TS_REPO=${TS_REPO:-$HOME/repo/aos}
TS_BIN_ROOT=${TS_BIN_ROOT:-$TS_REPO/proto8/impls}       # ~/.local/bin/aos-* 指到 <這裡>/<p>/bin/<p>；只有 build.sh --install 和 rollback.sh（舊備份裡有 bin/ 時）會寫
TS_BACKUP_ROOT=${TS_BACKUP_ROOT:-$HOME/.aos/saves/tree-swap}
TS_FOLDERS_ALL="lib templates knowledge py kernel"      # 只換樹裡已經有的那幾夾
TS_BINS="aos-daemon aos-directive aos-exec aos-fsm aos-json aos-llm aos-lock aos-loop aos-post"

ts_red() { echo "RED: $*" >&2; exit 3; }
ts_t0() { TS_T0=$(date +%s.%N); }
ts_t1() { awk -v a="$TS_T0" -v b="$(date +%s.%N)" -v n="$1" 'BEGIN{printf "[%s %.2fs]\n", n, b-a}'; }

# 「樹在跑」只看 aos 自己的 daemon 和 loop（使用者 11-15 換樹兩次被擋：編譯中開了畫面、剩兩個 wl-copy；「乾，好煩喔，到底爲啥要檢查這麼多啊」，同意改成只看 daemon）。
# 判法跟 aos-daemon-ctl 一樣（proto8/py/daemon_ctl/poke.py 的 check_alive）：樹裡每個 .stack 底下的 state.json 記著 pid＋started_at_ticks＋boot_id，
# 三樣對得上 /proc 而且不是殭屍＝還活著。root、ws 的 daemon 和每隻 agent 的 loop 都有這個檔。tmux、claude、wl-copy、全景頁、殼的環境變數和 cwd 一律不看。
# 印出還活著的；有就回 0。
ts_tree_busy() {
  python3 -I - "$1" <<'PY'
import json, os, sys
tree = os.path.realpath(sys.argv[1])
try:
    boot = open("/proc/sys/kernel/random/boot_id").read().strip()
except OSError:
    boot = None
found = False
for root, dirs, files in os.walk(tree):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__") and not d.startswith(".tree-swap")]
    if "state.json" not in files or ".stack" not in root.split(os.sep):
        continue
    path = os.path.join(root, "state.json")
    try:
        st = json.load(open(path))
        pid, ticks = st["pid"], st["started_at_ticks"]
        if st.get("boot_id") != boot or type(pid) is not int or pid <= 0:
            continue
        stat = open("/proc/%d/stat" % pid).read()
        f = stat[stat.rindex(")") + 1:].split()
        if f[0] in ("Z", "X") or int(f[19]) != ticks:
            continue
        comm = open("/proc/%d/comm" % pid).read().strip()
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        continue
    print("  pid %d %s (%s)" % (pid, comm, os.path.relpath(path, tree)))
    found = True
sys.exit(0 if found else 1)
PY
}

ts_require_stopped() {
  local out
  if out=$(ts_tree_busy "$TS_TREE"); then
    echo "$out" >&2
    ts_red "tree $TS_TREE is still running (aos daemon/loop above); stop the tree first, nothing was changed"
  fi
  echo "ok: no aos daemon or loop of tree $TS_TREE is alive"
}

# 樹裡現有、要換的夾
ts_folders() {
  local d out=""
  for d in $TS_FOLDERS_ALL; do [ -d "$TS_TREE/$d" ] && out="$out $d"; done
  echo $out
}

# 不刪（使用者 11-14）：每次跑在 $TS_BACKUP_ROOT/run-<時間>-<pid>-<what>/ 放這次的暫存夾與換下來的夾，結束時列出來。
ts_run_dir() { TS_RUN="$TS_BACKUP_ROOT/run-$(date +%Y%m%d-%H%M%S)-$$-$1"; mkdir -p "$TS_RUN"; }
# ts_keep_dir NAME [-n]：$TS_RUN/NAME（已有就加 -2、-3…）；-n＝只回路徑不建（給 mv -T 當目的地）
ts_keep_dir() {
  local d="$TS_RUN/$1" i=2
  while [ -e "$d" ]; do d="$TS_RUN/$1-$i"; i=$((i+1)); done
  [ "${2:-}" = -n ] || mkdir -p "$d"
  echo "$d"
}
ts_kept_report() {
  local rc=$? d
  [ -n "${TS_RUN:-}" ] && [ -d "$TS_RUN" ] || return $rc
  if [ -z "$(ls -A "$TS_RUN")" ]; then echo "kept: nothing (empty run folder $TS_RUN)"; return $rc; fi
  echo "kept (nothing is deleted; remove by hand when you decide): $TS_RUN $(du -sh "$TS_RUN" | cut -f1)"
  for d in "$TS_RUN"/*; do echo "  $(du -sh "$d" | cut -f1)	$d"; done
  return $rc
}
