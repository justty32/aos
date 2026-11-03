#!/bin/sh
# L2-08  `aos say --to` 成功訊息印出的「目的地」不是真實路徑
#
# 期待：印出實際收信的 say/ 目錄，或至少印出對方世界資料夾＋agent 名。
# 實際：把 <資料夾> 和 <agent 名> 直接黏成 "<folder>/<name>"，那個路徑不存在，
#       貼進 ls 只會得到 No such file or directory。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/a/.aos" "$ROOT/b/.aos"
(cd "$ROOT/a" && "$AOS" agent init --name a >/dev/null)
(cd "$ROOT/b" && "$AOS" agent init --name b >/dev/null)
(cd "$ROOT/a" && "$AOS" contact add b ../b >/dev/null)

OUT="$(cd "$ROOT/a" && "$AOS" say --to b "hi")"
echo "輸出原話： $OUT"

# 取括號裡的路徑
SHOWN=$(printf '%s' "$OUT" | sed -n 's/.*（\(.*\)）.*/\1/p')
echo "宣稱的目的地： $SHOWN"

if [ -e "$SHOWN" ]; then
  echo "PASS: 是真實路徑"
else
  echo "FAIL: 宣稱的目的地不存在（folder 與 agent 名被黏在一起）"
  echo "真正收到信的地方： $ROOT/b/.aos/agents/b/say/"
  ls "$ROOT/b/.aos/agents/b/say/"
  exit 1
fi
