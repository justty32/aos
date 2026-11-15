#!/bin/bash
# build.sh - 用 git archive 把某個 commit 的 proto8 抄到 repo 外的 $TS_BUILD、編出九支 C++ 執行檔並寫 BUILD_REF；加 --install 就把編好的每支用 rename 換進 $TS_BIN_ROOT/<p>/bin/<p>（樹在跑也行）。
# 用法：build.sh --ref <commit> [--install]
#   不加 --install：只編、不換（拿來測）。$TS_BUILD 沒給就編到 ~/.aos/scratch/tree-swap/build-<時間>-<pid>/（不刪，留著）；給了而且已存在就拒絕。
#   --install：使用者 11-15「樹還在跑的時候不能在repo裏面編，我希望可以，這就是使用者自己承擔風險。或是編譯的時候走腳本，腳本會稍微檢查一下」——
#     九支全部編成功才換；每支先抄成 <bin>.build-new 再 mv（rename），跑著的行程留在舊的 inode 上照跑、下次起來才用新版，也不會撞到 text file busy；
#     換之前看 /proc/*/exe，有行程正在用那支就印一行 warning（只警告、不擋、不殺）。編失敗＝什麼都不換。
#   換樹（swap.sh）不再換 C++（使用者 11-15「好，就這樣改。」），C++ 一律平常用這支 --install 換。每支開始、結束各印一行（附秒數），編譯輸出寫進 $TS_BUILD/log/<p>.log，失敗時印最後 20 行。
[ -n "$BASH_VERSION" ] || { echo "build.sh: not bash, refuse" >&2; exit 2; }
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
. "$HERE/common.sh"
REF=""; INSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF=$2; shift 2 ;;
    --install) INSTALL=1; shift ;;
    -h|--help) sed -n 2,8p "$0"; exit 0 ;;
    *) echo "build.sh: unknown arg $1" >&2; exit 2 ;;
  esac
done
[ -n "$REF" ] || { echo "build.sh: --ref <commit> is required" >&2; exit 2; }
REF=$(git -C "$TS_REPO" rev-parse --verify "$REF^{commit}")
TS_BUILD=${TS_BUILD:-$HOME/.aos/scratch/tree-swap/build-$(date +%Y%m%d-%H%M%S)-$$}
[ -e "$TS_BUILD" ] && ts_red "$TS_BUILD exists; move it away first"
case "$(realpath -m "$TS_BUILD")/" in "$(realpath "$TS_REPO")"/*) ts_red "TS_BUILD is inside the repo; build outside it" ;; esac
mkdir -p "$TS_BUILD/log"
git -C "$TS_REPO" archive "$REF" proto8 | tar -x -C "$TS_BUILD"
N=$(wc -w <<< "$TS_BINS"); i=0; T_ALL=$SECONDS
echo "build: $N binaries from ${REF:0:9} in $TS_BUILD (about 1.5 min)"
for p in $TS_BINS; do
  i=$((i+1)); T=$SECONDS; log="$TS_BUILD/log/$p.log"
  echo "build $p ($i/$N): start"
  if ! { cmake -S "$TS_BUILD/proto8/impls/$p" -B "$TS_BUILD/proto8/impls/$p/build" -DCMAKE_BUILD_TYPE=Release \
         && cmake --build "$TS_BUILD/proto8/impls/$p/build" -j8; } > "$log" 2>&1; then
    tail -20 "$log" >&2; ts_red "build $p failed after $((SECONDS-T))s (log $log); nothing was replaced"
  fi
  [ -x "$TS_BUILD/proto8/impls/$p/bin/$p" ] || ts_red "no binary for $p (log $log); nothing was replaced"
  echo "build $p ($i/$N): done in $((SECONDS-T))s"
done
echo "$REF" > "$TS_BUILD/BUILD_REF"
echo "build: $N binaries from $REF done in $((SECONDS-T_ALL))s"
[ $INSTALL = 1 ] || exit 0

# --install：九支都編好了才走到這裡；逐支警告正在跑的、寫旁邊再 rename
in_use() {   # 印出正在用 $1 這支執行檔的 pid（看自己的行程的 /proc/*/exe）
  local want d e
  want=$(realpath "$1")
  for d in /proc/[0-9]*; do
    e=$(readlink "$d/exe" 2>/dev/null) || continue
    [ "$e" = "$want" ] && printf ' %s' "${d#/proc/}"
  done
  return 0
}
n=0
for p in $TS_BINS; do
  dst="$TS_BIN_ROOT/$p/bin/$p"
  [ -d "$TS_BIN_ROOT/$p/bin" ] || ts_red "target dir missing: $TS_BIN_ROOT/$p/bin (nothing more replaced; $n done)"
  if cmp -s "$TS_BUILD/proto8/impls/$p/bin/$p" "$dst"; then echo "install $p: same as before"; continue; fi
  if [ -e "$dst" ]; then
    pids=$(in_use "$dst")
    [ -n "$pids" ] && echo "warning: $p is running (pid$pids); those keep the old version until they restart"
  fi
  cp "$TS_BUILD/proto8/impls/$p/bin/$p" "$dst.build-new"; chmod 755 "$dst.build-new"
  mv -f "$dst.build-new" "$dst"
  n=$((n+1)); echo "install $p: replaced"
done
echo "install: $n binaries replaced in $TS_BIN_ROOT (built in $TS_BUILD, kept)"
