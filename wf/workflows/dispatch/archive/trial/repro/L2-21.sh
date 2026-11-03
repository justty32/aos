#!/bin/sh
# L2-21  `aos tool add` 把「執行檔不存在」誤報成「缺少表述」。
# L2-22  `aos run` 不拒絕重複旗標，靜默採用最後一個。
#
# L2-21 期待：退出碼 127 就直說 command not found／執行檔不存在。
#       實際：印「aos tool: 探測不到表述，請用 --description 手填；探測行程退出碼是 127」，
#             把使用者導去補 --description——照著做也不會成功，因為問題根本不在表述。
# L2-22 期待：`aos run --step 1 --step 2` 被拒絕（歧義參數）。
#       實際：完全不報錯，採用最後一個 --step 2，真的跑兩回合。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/w/.aos"
(cd "$ROOT/w" && "$AOS" agent init --name w >/dev/null)

echo "=== L2-21：登記一個不存在的執行檔 ==="
(cd "$ROOT/w" && "$AOS" tool add bad -- /definitely/not/here 2>&1) || true
echo "--- 照訊息說的補 --description 再試一次 ---"
(cd "$ROOT/w" && "$AOS" tool add bad --description "測試" -- /definitely/not/here 2>&1) || true
echo "--- tool ls ---"
(cd "$ROOT/w" && "$AOS" tool ls)
echo "（訊息叫你補 description；補了之後 bad 就這樣登記進去了——"
echo "  argv 指向一個根本不存在的執行檔，全程沒有任何驗證。"
echo "  也就是說隊長可以把一個保證失敗的工具交給隊員而毫不知情。）"

echo
echo "=== L2-22：重複旗標 ==="
BEFORE="$(cat "$ROOT/w/.aos/turn")"
OUT="$(cd "$ROOT/w" && "$AOS" run --step 1 --step 2 2>&1)"; echo "$OUT"
AFTER="$(cat "$ROOT/w/.aos/turn")"
RAN=$(printf '%s\n' "$OUT" | grep -c '^turn ')
echo "--- 推進了 $RAN 回合（turn 檔 $BEFORE -> $AFTER）---"
if [ "$RAN" -ne 1 ]; then
  echo "FAIL: 重複的 --step 沒被拒絕，靜默採用最後一個（--step 2），跑了 $RAN 回合"
  exit 1
fi
