#!/bin/bash
# build.sh - 在 repo 外用 git archive 把某個 commit 的 proto8 抄到 $TS_BUILD、編出 swap.sh 要的十支 C++ 執行檔，並寫 BUILD_REF；不碰 repo 工作樹、不碰樹。
# 用法：build.sh --ref <commit>（$TS_BUILD 預設 ~/code/swap-1113/src；已存在就拒絕，要重編先自己移走）
[ -n "$BASH_VERSION" ] || { echo "build.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
. "$HERE/common.sh"
REF=""
while [ $# -gt 0 ]; do
  case "$1" in --ref) REF=$2; shift 2 ;; -h|--help) sed -n 2,3p "$0"; exit 0 ;; *) echo "build.sh: unknown arg $1" >&2; exit 2 ;; esac
done
[ -n "$REF" ] || { echo "build.sh: --ref <commit> is required" >&2; exit 2; }
REF=$(git -C "$TS_REPO" rev-parse --verify "$REF^{commit}")
[ -e "$TS_BUILD" ] && ts_red "$TS_BUILD exists; move it away first"
case "$(realpath -m "$TS_BUILD")/" in "$(realpath "$TS_REPO")"/*) ts_red "TS_BUILD is inside the repo; build outside it" ;; esac
mkdir -p "$TS_BUILD"
git -C "$TS_REPO" archive "$REF" proto8 | tar -x -C "$TS_BUILD"
for p in $TS_BINS; do
  ts_t0
  cmake -S "$TS_BUILD/proto8/impls/$p" -B "$TS_BUILD/proto8/impls/$p/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$TS_BUILD/proto8/impls/$p/build" -j8 2>&1 | tail -1
  [ -x "$TS_BUILD/proto8/impls/$p/bin/$p" ] || ts_red "no binary for $p"
  ts_t1 "$p"
done
echo "$REF" > "$TS_BUILD/BUILD_REF"
echo "build: 10 binaries from $REF in $TS_BUILD"
