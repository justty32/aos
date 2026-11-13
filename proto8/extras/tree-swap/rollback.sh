#!/bin/bash
# rollback.sh - 把 swap.sh 換過的樹複本與十支 C++ 執行檔還原成它換之前的備份；樹要停著，不含任何 kill／shutdown。
# 用法：rollback.sh [--backup <備份夾>] [all | tree | bin]（不給 --backup＝$TS_BACKUP_ROOT/LAST 指的那份；不給段＝all）
[ -n "$BASH_VERSION" ] || { echo "rollback.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
. "$HERE/common.sh"

B=""; WHAT=all
while [ $# -gt 0 ]; do
  case "$1" in
    --backup) B=$2; shift 2 ;;
    all|tree|bin) WHAT=$1; shift ;;
    -h|--help) sed -n 2,3p "$0"; exit 0 ;;
    *) echo "rollback.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done
ts_refuse_agent_env
[ -n "$B" ] || { [ -f "$TS_BACKUP_ROOT/LAST" ] || ts_red "no $TS_BACKUP_ROOT/LAST"; B=$(cat "$TS_BACKUP_ROOT/LAST"); }
[ -f "$B/META" ] || ts_red "$B/META missing"
TREE=$(sed -n 's/^tree=//p' "$B/META"); BIN_ROOT=$(sed -n 's/^bin_root=//p' "$B/META"); FOLDERS=$(sed -n 's/^folders=//p' "$B/META")
TS_TREE=$TREE
echo "backup=$B tree=$TREE bin_root=$BIN_ROOT folders=[$FOLDERS] what=$WHAT"

ts_t0
ts_require_stopped
if [ "$WHAT" != bin ]; then
  new="$TREE/.tree-swap-rb-new"; old="$TREE/.tree-swap-rb-old"
  [ -e "$new" ] || [ -e "$old" ] && ts_red "$new or $old already exists; look, then remove by hand"
  mkdir -p "$new" "$old"
  for d in $FOLDERS; do cp -a "$B/tree/$d" "$new/$d"; done
  for d in $FOLDERS; do
    [ -e "$TREE/$d" ] && mv -T "$TREE/$d" "$old/$d"
    mv -T "$new/$d" "$TREE/$d"
  done
  rm -rf "$new" "$old"
  for d in $FOLDERS; do diff -rq "$B/tree/$d" "$TREE/$d" >/dev/null || ts_red "after rollback $TREE/$d still differs from backup"; done
  echo "rollback tree: $FOLDERS restored and identical to backup"
fi
if [ "$WHAT" != tree ]; then
  for p in $TS_BINS; do
    dst="$BIN_ROOT/$p/bin/$p"
    cp -a "$B/bin/$p" "$dst.tree-swap-rb"
    mv -f "$dst.tree-swap-rb" "$dst"
    cmp -s "$B/bin/$p" "$dst" || ts_red "after rollback $dst differs from backup"
  done
  echo "rollback bin: 10 binaries restored and identical to backup"
fi
ts_t1 rollback
