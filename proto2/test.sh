#!/usr/bin/env bash
# proto2 煙霧測試：跑 aos exec 的四件事。有一項 FAIL 就退出 1。
HERE=$(cd "$(dirname "$0")" && pwd)
AOS="$HERE/aos"
FAILED=0

check() {  # check <名字> <期待退出碼> <實際退出碼> [額外條件說明]
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1（期待退出碼 $2，實際 $3）"; FAILED=1; fi
}

# 1. 檔案能執行
OUT=$("$AOS" exec "$HERE/examples/hello.sh"); RC=$?
check "檔案能執行" 0 "$RC"
case "$OUT" in
  *"hello from hello.sh"*) echo "ok   檔案的輸出有出來" ;;
  *) echo "FAIL 檔案的輸出不對：$OUT"; FAILED=1 ;;
esac

# 2. 資料夾能跑 insts.json，而且順序對、工作目錄是那個資料夾
OUT=$("$AOS" exec "$HERE/examples/folder"); RC=$?
check "資料夾能跑 insts.json" 0 "$RC"
FIRST=$(echo "$OUT" | sed -n 1p)
SECOND=$(echo "$OUT" | sed -n 2p)
case "$FIRST" in
  *"第一條"*) echo "ok   第一條先跑" ;;
  *) echo "FAIL 第一條沒有先跑：$FIRST"; FAILED=1 ;;
esac
if [ "$SECOND" = "$HERE/examples/folder" ]; then
  echo "ok   工作目錄是那個資料夾"
else
  echo "FAIL 工作目錄不對：$SECOND"; FAILED=1
fi

# 3. 中間一條失敗就停在那裡，回同一個退出碼
TMP=$(mktemp -d)
mkdir -p "$TMP/.aos"
cat > "$TMP/.aos/insts.json" <<'JSON'
[
  ["echo", "before"],
  ["sh", "-c", "exit 3"],
  ["echo", "after"]
]
JSON
OUT=$("$AOS" exec "$TMP"); RC=$?
check "中間失敗回同一個退出碼" 3 "$RC"
case "$OUT" in
  *after*) echo "FAIL 失敗後不該再跑下一條：$OUT"; FAILED=1 ;;
  *before*) echo "ok   失敗後就停住" ;;
  *) echo "FAIL 第一條沒跑到：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 4. 路徑不存在回 2
"$AOS" exec "$HERE/沒有這個東西" 2>/dev/null; RC=$?
check "路徑不存在回 2" 2 "$RC"

exit $FAILED
