#!/bin/bash
# swap.sh - 停樹後把一棵 aos 樹的程式複本（lib／templates／knowledge／py／kernel）換成某個釘住 commit 的版本；先備份、抄到旁邊再改名，不含任何 kill／shutdown。
# 用法：swap.sh --ref <commit> [all | check backup copy stamp verify ...]（all＝五段依序；不給段＝check；stamp＝用該 commit 的 extras/aos-home/copy_tree.py --stamp-only 替每夾寫 .aos-source.json）
# C++ 不在這裡換（使用者 11-15「好，就這樣改。」）：樹在跑時用 build.sh --ref <commit> --install 換好；~/.local/bin/aos-* 指的就是 repo 的 impls/*/bin，裝了就生效。
# 路徑用環境變數改（預設見 common.sh）：TS_TREE TS_REPO TS_BACKUP_ROOT。退回用同夾的 rollback.sh。
# 只碰：樹裡已有的 lib templates knowledge py kernel 這幾夾；agents defs teams kernels ws root daemon .stack env.sh 一律不碰。
# 不刪任何東西（使用者 11-14「不刪，連自己剛建的暫存也不刪」）：每段解出來的暫存夾與換下來的舊夾都留在 $TS_BACKUP_ROOT/run-<時間>/，結束時印出留下哪些、各多大，由使用者決定刪不刪。
[ -n "$BASH_VERSION" ] || { echo "swap.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
. "$HERE/common.sh"

REF=""; STEPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF=$2; shift 2 ;;
    -h|--help) sed -n 2,6p "$0"; exit 0 ;;
    all) STEPS+=(check backup copy stamp verify); shift ;;
    check|backup|copy|stamp|verify) STEPS+=("$1"); shift ;;
    *) echo "swap.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$REF" ] || { echo "swap.sh: --ref <commit> is required" >&2; exit 2; }
[ ${#STEPS[@]} -gt 0 ] || STEPS=(check)

REF=$(git -C "$TS_REPO" rev-parse --verify "$REF^{commit}") || ts_red "ref not found in $TS_REPO"
FOLDERS=$(ts_folders)
ts_run_dir swap
trap ts_kept_report EXIT
echo "tree=$TS_TREE ref=$REF folders=[$FOLDERS]"

# 把 commit 的 proto8/<夾> 解到 $1（$1/<夾>）
extract() { mkdir -p "$1"; git -C "$TS_REPO" archive "$REF" $(for d in $FOLDERS; do echo "proto8/$d"; done) | tar -x -C "$1" --strip-components=1; }

last_backup() {
  [ -f "$TS_BACKUP_ROOT/LAST" ] || ts_red "no backup yet (run the backup step first)"
  local b; b=$(cat "$TS_BACKUP_ROOT/LAST")
  grep -qx "ref=$REF" "$b/META" && grep -qx "tree=$TS_TREE" "$b/META" \
    || ts_red "last backup $b was made for another ref/tree; run backup again"
  echo "$b"
}

step_check() {
  ts_require_stopped
  local tmp d out n_ch n_new n_only
  tmp=$(ts_keep_dir tmp-check); extract "$tmp"
  for d in $FOLDERS; do
    out=$(diff -rq -x __pycache__ -x .aos-source.json "$tmp/$d" "$TS_TREE/$d" || true)
    n_ch=$(grep -c '^Files' <<< "$out" || true)
    n_new=$(grep -c "^Only in $tmp" <<< "$out" || true)
    n_only=$(grep "^Only in $TS_TREE" <<< "$out" || true)
    echo "$d: changed=$n_ch new-entries=$n_new"
    if [ -n "$n_only" ]; then
      echo "$n_only" >&2
      ts_red "$d has files only in the tree (listed above); the swap would drop them. Move them out first"
    fi
  done
  git -C "$TS_REPO" cat-file -e "$REF:proto8/extras/aos-home/copy_tree.py" 2>/dev/null \
    || ts_red "$REF has no proto8/extras/aos-home/copy_tree.py (needed by the stamp step); pin a newer commit"
  echo "C++: not swapped here; install it while the tree runs: build.sh --ref $REF --install"
  echo "check: green"
}

step_backup() {
  ts_require_stopped
  local b d
  b="$TS_BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$b/tree"
  for d in $FOLDERS; do cp -a "$TS_TREE/$d" "$b/tree/$d"; done
  printf 'ref=%s\ntree=%s\nfolders=%s\ntime=%s\n' "$REF" "$TS_TREE" "$FOLDERS" "$(date -Is)" > "$b/META"
  echo "$b" > "$TS_BACKUP_ROOT/LAST"
  echo "backup: $b ($(du -sh "$b" | cut -f1))"
}

step_copy() {
  ts_require_stopped
  local b d new old
  b=$(last_backup)
  new="$TS_TREE/.tree-swap-new"; old="$TS_TREE/.tree-swap-old"
  [ -e "$new" ] || [ -e "$old" ] && ts_red "$new or $old already exists (a previous run died half way?); look, then move it away by hand"
  extract "$new"; mkdir -p "$old"
  for d in $FOLDERS; do
    mv -T "$TS_TREE/$d" "$old/$d"
    mv -T "$new/$d" "$TS_TREE/$d"
  done
  mv -T "$old" "$(ts_keep_dir old -n)"; mv -T "$new" "$(ts_keep_dir new-empty -n)"
  echo "copy: $FOLDERS now from $REF (backup $b; the replaced folders are kept in $TS_RUN/old)"
}

step_stamp() {
  ts_require_stopped
  local tmp
  last_backup >/dev/null
  tmp=$(ts_keep_dir tmp-stamp)
  git -C "$TS_REPO" archive "$REF" proto8/extras/aos-home proto8/py proto8/lib | tar -x -C "$tmp"
  python3 -I "$tmp/proto8/extras/aos-home/copy_tree.py" --stamp-only --ref "$REF" --repo "$TS_REPO" "$TS_TREE" $FOLDERS \
    || ts_red "copy_tree.py --stamp-only failed"
  echo "stamp: .aos-source.json written in $FOLDERS"
}

step_verify() {
  local tmp d bad=0
  tmp=$(ts_keep_dir tmp-verify); extract "$tmp"
  for d in $FOLDERS; do
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["commit"]==sys.argv[2] else 1)' "$TS_TREE/$d/.aos-source.json" "$REF" 2>/dev/null \
      || { echo "verify $d: .aos-source.json missing or not $REF"; bad=1; }
    if diff -rq -x __pycache__ -x .aos-source.json "$tmp/$d" "$TS_TREE/$d" >/dev/null; then echo "verify $d: same as $REF"; else echo "verify $d: DIFFERS"; bad=1; fi
  done
  [ $bad = 0 ] || ts_red "verify failed"
  echo "verify: green ($FOLDERS)"
}

for s in "${STEPS[@]}"; do
  ts_t0; "step_$s"; ts_t1 "$s"
done
