#!/bin/sh
# 一鍵跑全部範例＋測試。不要 -e：讓失敗的範例往下跑完，最後一起報。
set -u
cd "$(dirname "$0")/.."

TMP_HOME="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_HOME"
}
trap cleanup EXIT INT TERM
export AOS_HOME="$TMP_HOME"

chmod +x proto/*.sh proto/examples/*/run.sh 2>/dev/null

PASS=""
FAIL=""

for d in proto/examples/*/; do
  name="$(basename "$d")"
  script="${d}run.sh"
  if [ ! -f "$script" ]; then
    continue
  fi
  echo "############################################################"
  echo "== 跑範例：$name =="
  echo "############################################################"
  if sh "$script"; then
    echo ">> $name：過"
    PASS="$PASS $name"
  else
    echo ">> $name：沒過"
    FAIL="$FAIL $name"
  fi
  echo
done

echo "############################################################"
echo "== 跑測試（proto/tests/） =="
echo "############################################################"
TEST_STATUS="skip"
if [ -d proto/tests ] && find proto/tests -name 'test_*.py' 2>/dev/null | grep -q .; then
  TEST_OUT="$(python3 -m unittest discover -s proto/tests -t . 2>&1)"
  TEST_RC=$?
  echo "$TEST_OUT"
  if [ "$TEST_RC" -eq 0 ]; then
    TEST_STATUS="green"
  else
    TEST_STATUS="red"
  fi
else
  echo "還沒有測試"
fi

echo
echo "############################################################"
echo "== 總表 =="
echo "############################################################"
echo "範例："
for n in $PASS; do
  echo "  過   $n"
done
for n in $FAIL; do
  echo "  沒過 $n"
done
if [ -z "$PASS$FAIL" ]; then
  echo "  （沒有範例可跑）"
fi

echo "測試："
case "$TEST_STATUS" in
  skip) echo "  還沒有測試" ;;
  green) echo "  全綠" ;;
  red) echo "  有紅的（看上面的輸出）" ;;
esac

if [ -n "$FAIL" ] || [ "$TEST_STATUS" = "red" ]; then
  exit 1
fi
exit 0
