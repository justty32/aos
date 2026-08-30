#!/bin/sh
# L2-05  訊息不帶寄件人：boss 分不出哪封是 w1 的回報、哪封是 w2 的、哪封是使用者的新指令。
#
# 期待：投遞會記下寄件人（世界＋agent 名），boss 收到時看得到 from。
# 實際：`aos::agent::say()` 只把**純文字**寫成 say/<時間戳>-<pid>-<序號>.md，
#       檔名只有時間戳與寄件行程的 pid，內容一個位元組都沒有寄件人；
#       step 讀進去時就是 history.json 裡一則 {"role":"user","content":"<原文>"}，
#       跟使用者親手打的 `aos say` 完全無法區分。
#       → 沒有 from 欄 = 沒有回信地址 = 「收回報」只能靠寄件人自己在正文裡自報家門。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

for w in boss w1 w2; do
  mkdir -p "$ROOT/$w/.aos"
  (cd "$ROOT/$w" && "$AOS" agent init --name "$w" >/dev/null)
done
(cd "$ROOT/w1" && "$AOS" contact add boss ../boss >/dev/null)
(cd "$ROOT/w2" && "$AOS" contact add boss ../boss >/dev/null)

# 三個不同來源，各寄一封給 boss
(cd "$ROOT/w1"   && "$AOS" say --to boss "完成了" >/dev/null)   # 來自 w1
(cd "$ROOT/w2"   && "$AOS" say --to boss "完成了" >/dev/null)   # 來自 w2
(cd "$ROOT/boss" && "$AOS" say            "完成了" >/dev/null)   # 來自使用者本人

echo "=== boss 信箱裡的三封信 ==="
for f in "$ROOT/boss/.aos/agents/boss/say/"*.md; do
  echo "--- $(basename "$f") ---"
  echo "內容： $(cat "$f")"
done

echo
echo "=== 有任何一封記下寄件人嗎？ ==="
if grep -rlq -e w1 -e w2 -e 使用者 "$ROOT/boss/.aos/agents/boss/say/"; then
  echo "PASS: 找得到寄件人"
else
  echo "FAIL: 三封信內容一模一樣，沒有任何 from 欄；boss 無從得知誰寄的、也無從回信"
  exit 1
fi
