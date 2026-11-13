#!/bin/bash
# swap.sh - 停樹後把一棵 aos 樹的程式複本（lib／templates／knowledge／py／kernel）與十支 C++ 執行檔換成某個釘住 commit 的版本；先備份、抄到旁邊再改名，不含任何 kill／shutdown。
# 用法：swap.sh --ref <commit> [all | check backup copy stamp bin verify ...]（all＝六段依序；stamp＝用該 commit 的 extras/aos-home/copy_tree.py --stamp-only 替每夾寫 .aos-source.json）
# 路徑用環境變數改（預設見 common.sh）：TS_TREE TS_REPO TS_BUILD TS_BIN_ROOT TS_BACKUP_ROOT。退回用同夾的 rollback.sh。
# 只碰：樹裡已有的 lib templates knowledge py kernel 這幾夾、$TS_BIN_ROOT/<p>/bin/<p> 十支；agents defs teams kernels ws root daemon .stack env.sh 一律不碰。
[ -n "$BASH_VERSION" ] || { echo "swap.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
. "$HERE/common.sh"

REF=""; STEPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF=$2; shift 2 ;;
    -h|--help) sed -n 2,5p "$0"; exit 0 ;;
    all) STEPS+=(check backup copy stamp bin verify); shift ;;
    check|backup|copy|stamp|bin|verify) STEPS+=("$1"); shift ;;
    *) echo "swap.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$REF" ] || { echo "swap.sh: --ref <commit> is required" >&2; exit 2; }
[ ${#STEPS[@]} -gt 0 ] || STEPS=(check)

ts_refuse_agent_env
REF=$(git -C "$TS_REPO" rev-parse --verify "$REF^{commit}") || ts_red "ref not found in $TS_REPO"
FOLDERS=$(ts_folders)
echo "tree=$TS_TREE ref=$REF folders=[$FOLDERS] bin_root=$TS_BIN_ROOT build=$TS_BUILD"

# 把 commit 的 proto8/<夾> 解到 $1（$1/<夾>）
extract() { mkdir -p "$1"; git -C "$TS_REPO" archive "$REF" $(for d in $FOLDERS; do echo "proto8/$d"; done) | tar -x -C "$1" --strip-components=1; }

last_backup() {
  [ -f "$TS_BACKUP_ROOT/LAST" ] || ts_red "no backup yet (run the backup step first)"
  local b; b=$(cat "$TS_BACKUP_ROOT/LAST")
  grep -qx "ref=$REF" "$b/META" && grep -qx "tree=$TS_TREE" "$b/META" && grep -qx "bin_root=$TS_BIN_ROOT" "$b/META" \
    || ts_red "last backup $b was made for another ref/tree/bin_root; run backup again"
  echo "$b"
}

check_build() {
  local bref
  [ -f "$TS_BUILD/BUILD_REF" ] || ts_red "$TS_BUILD/BUILD_REF missing (build with build.sh)"
  bref=$(cat "$TS_BUILD/BUILD_REF")
  git -C "$TS_REPO" diff --quiet "$bref" "$REF" -- proto8/impls \
    || ts_red "C++ was built from $bref but proto8/impls differs at $REF; rebuild with build.sh --ref $REF"
  echo "ok: C++ build ref $bref has the same proto8/impls as $REF"
}

step_check() {
  ts_require_stopped
  local p tmp d out n_ch n_new n_only
  check_build
  for p in $TS_BINS; do
    [ -x "$TS_BUILD/proto8/impls/$p/bin/$p" ] || ts_red "built binary missing: $TS_BUILD/proto8/impls/$p/bin/$p"
    [ -d "$TS_BIN_ROOT/$p/bin" ] || ts_red "target dir missing: $TS_BIN_ROOT/$p/bin"
  done
  n_ch=0; for p in $TS_BINS; do cmp -s "$TS_BUILD/proto8/impls/$p/bin/$p" "$TS_BIN_ROOT/$p/bin/$p" || n_ch=$((n_ch+1)); done
  echo "bins: $n_ch of 10 differ"
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/tree-swap-check.XXXXXX"); extract "$tmp"
  for d in $FOLDERS; do
    out=$(diff -rq -x __pycache__ -x .aos-source.json "$tmp/$d" "$TS_TREE/$d" || true)
    n_ch=$(grep -c '^Files' <<< "$out" || true)
    n_new=$(grep -c "^Only in $tmp" <<< "$out" || true)
    n_only=$(grep "^Only in $TS_TREE" <<< "$out" || true)
    echo "$d: changed=$n_ch new-entries=$n_new"
    if [ -n "$n_only" ]; then
      echo "$n_only" >&2; rm -rf "$tmp"
      ts_red "$d has files only in the tree (listed above); the swap would drop them. Move them out first"
    fi
  done
  rm -rf "$tmp"
  git -C "$TS_REPO" cat-file -e "$REF:proto8/extras/aos-home/copy_tree.py" 2>/dev/null \
    || ts_red "$REF has no proto8/extras/aos-home/copy_tree.py (needed by the stamp step); pin a newer commit"
  echo "check: green"
}

step_backup() {
  ts_require_stopped
  local b d p
  b="$TS_BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$b/tree" "$b/bin"
  for d in $FOLDERS; do cp -a "$TS_TREE/$d" "$b/tree/$d"; done
  for p in $TS_BINS; do cp -a "$TS_BIN_ROOT/$p/bin/$p" "$b/bin/$p"; done
  printf 'ref=%s\ntree=%s\nbin_root=%s\nfolders=%s\ntime=%s\n' "$REF" "$TS_TREE" "$TS_BIN_ROOT" "$FOLDERS" "$(date -Is)" > "$b/META"
  echo "$b" > "$TS_BACKUP_ROOT/LAST"
  echo "backup: $b ($(du -sh "$b" | cut -f1))"
}

step_copy() {
  ts_require_stopped
  local b d new old
  b=$(last_backup)
  new="$TS_TREE/.tree-swap-new"; old="$TS_TREE/.tree-swap-old"
  [ -e "$new" ] || [ -e "$old" ] && ts_red "$new or $old already exists (a previous run died half way?); look, then remove by hand"
  extract "$new"; mkdir -p "$old"
  for d in $FOLDERS; do
    mv -T "$TS_TREE/$d" "$old/$d"
    mv -T "$new/$d" "$TS_TREE/$d"
  done
  rm -rf "$new" "$old"
  echo "copy: $FOLDERS now from $REF (backup $b)"
}

step_stamp() {
  ts_require_stopped
  local tmp
  last_backup >/dev/null
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/tree-swap-stamp.XXXXXX")
  git -C "$TS_REPO" archive "$REF" proto8/extras/aos-home proto8/py proto8/lib | tar -x -C "$tmp"
  python3 -I "$tmp/proto8/extras/aos-home/copy_tree.py" --stamp-only --ref "$REF" --repo "$TS_REPO" "$TS_TREE" $FOLDERS \
    || { rm -rf "$tmp"; ts_red "copy_tree.py --stamp-only failed"; }
  rm -rf "$tmp"
  echo "stamp: .aos-source.json written in $FOLDERS"
}

step_bin() {
  ts_require_stopped
  local b p dst
  b=$(last_backup)
  check_build
  for p in $TS_BINS; do
    dst="$TS_BIN_ROOT/$p/bin/$p"
    cp "$TS_BUILD/proto8/impls/$p/bin/$p" "$dst.tree-swap-new"
    chmod 755 "$dst.tree-swap-new"
    mv -f "$dst.tree-swap-new" "$dst"
  done
  echo "bin: 10 binaries replaced (backup $b)"
}

step_verify() {
  local tmp d p bad=0
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/tree-swap-verify.XXXXXX"); extract "$tmp"
  for d in $FOLDERS; do
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["commit"]==sys.argv[2] else 1)' "$TS_TREE/$d/.aos-source.json" "$REF" 2>/dev/null \
      || { echo "verify $d: .aos-source.json missing or not $REF"; bad=1; }
    if diff -rq -x __pycache__ -x .aos-source.json "$tmp/$d" "$TS_TREE/$d" >/dev/null; then echo "verify $d: same as $REF"; else echo "verify $d: DIFFERS"; bad=1; fi
  done
  rm -rf "$tmp"
  for p in $TS_BINS; do cmp -s "$TS_BUILD/proto8/impls/$p/bin/$p" "$TS_BIN_ROOT/$p/bin/$p" || { echo "verify bin $p: DIFFERS"; bad=1; }; done
  [ $bad = 0 ] || ts_red "verify failed"
  echo "verify: green (folders and 10 bins)"
}

for s in "${STEPS[@]}"; do
  ts_t0; "step_$s"; ts_t1 "$s"
done
