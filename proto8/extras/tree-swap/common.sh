# common.sh - tree-swap 三支腳本共用：預設路徑、「樹在跑」偵測、計時（被 source，不單獨跑）
# 線換 11-13 晚；規格見 wf/workflows/dispatch/aos-teams/06「停樹換檔的做法」。

[ -n "$BASH_VERSION" ] || { echo "tree-swap: not bash, refuse" >&2; exit 2; }

TS_TREE=${TS_TREE:-$HOME/aos-home}
TS_REPO=${TS_REPO:-$HOME/repo/aos}
TS_BUILD=${TS_BUILD:-$HOME/code/swap-1113/src}          # 內有 BUILD_REF 與 proto8/impls/<p>/bin/<p>
TS_BIN_ROOT=${TS_BIN_ROOT:-$TS_REPO/proto8/impls}       # ~/.local/bin/aos-* 指到 <這裡>/<p>/bin/<p>
TS_BACKUP_ROOT=${TS_BACKUP_ROOT:-$HOME/aos-saves/tree-swap}
TS_FOLDERS_ALL="lib templates knowledge py kernel"      # 只換樹裡已經有的那幾夾
TS_BINS="aos-daemon aos-directive aos-exec aos-fsm aos-json aos-llm aos-llm-kernel aos-lock aos-loop aos-post"

ts_red() { echo "RED: $*" >&2; exit 3; }
ts_t0() { TS_T0=$(date +%s.%N); }
ts_t1() { awk -v a="$TS_T0" -v b="$(date +%s.%N)" -v n="$1" 'BEGIN{printf "[%s %.2fs]\n", n, b-a}'; }

# 跑在某隻 agent 的殼裡（帶著它的 stack）就拒絕：那等於樹還在跑、而且是從樹裡下的。
ts_refuse_agent_env() {
  local v
  for v in AOS_STACK AOS_DAEMON AOS_KERNEL AOS_CLOCK AOS_WS; do
    [ -n "${!v:-}" ] && ts_red "$v is set ($v=${!v}): run from a plain terminal, not from inside a tree agent"
  done
  return 0
}

# 印出所有「屬於這棵樹」還活著的行程；有就回 0。
# 算法：自己的行程裡，(a) 環境的 AOS_STACK／AOS_DAEMON 落在樹底下，或 (b) cwd 在樹底下且是 aos／claude／python／node。
# 不看 AOS_HOME（使用者的 .zshrc 每個殼都設）。只略過本腳本自己與它直接生的子行程。
ts_tree_busy() {
  local tree pid d cwd comm cmd ppid hit l v found=1
  tree=$(realpath "$1")
  for d in /proc/[0-9]*; do
    pid=${d#/proc/}
    [ "$pid" = "$$" ] && continue
    [ -O "$d" ] || continue
    ppid=$(sed -E 's/.*\) [A-Za-z] ([0-9]+).*/\1/' "$d/stat" 2>/dev/null) || continue
    [ "$ppid" = "$$" ] && continue
    cwd=$(readlink "$d/cwd" 2>/dev/null) || continue
    comm=$(cat "$d/comm" 2>/dev/null) || continue
    hit=""
    case "$cwd/" in
      "$tree"/*) [[ "$comm" =~ ^(aos|claude|python|node) ]] && hit=cwd ;;
    esac
    if [ -z "$hit" ]; then
      while IFS= read -r l; do
        v=${l#*=}
        case "$v/" in "$tree"/*) hit=env ;; esac
      done < <(tr '\0' '\n' < "$d/environ" 2>/dev/null | grep -E '^AOS_(STACK|DAEMON)=')
    fi
    if [ -n "$hit" ]; then
      cmd=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null) || cmd=""
      echo "  pid $pid [$hit] $comm cwd=$cwd :: ${cmd:0:100}"
      found=0
    fi
  done
  return $found
}

ts_require_stopped() {
  local out
  if out=$(ts_tree_busy "$TS_TREE"); then
    echo "$out" >&2
    ts_red "tree $TS_TREE is still running (processes above); stop the tree first, nothing was changed"
  fi
  echo "ok: no process of tree $TS_TREE is alive"
}

# 樹裡現有、要換的夾
ts_folders() {
  local d out=""
  for d in $TS_FOLDERS_ALL; do [ -d "$TS_TREE/$d" ] && out="$out $d"; done
  echo $out
}
