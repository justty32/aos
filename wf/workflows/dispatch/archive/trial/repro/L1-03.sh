#!/usr/bin/env bash
# 「idle／等待訊息」同時代表「做完了」「做到一半還有 pending 工具」「已經放棄在空轉」
# 三種完全不同的處境，aos state 分不出來。
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
export PATH="$(dirname "$AOS"):$PATH"      # 不加這行會踩到 L1-01
W=$(mktemp -d); mkdir -p "$W/.aos"; cd "$W"
printf 'alpha\nbeta\n' > note.txt
"$AOS" agent init --name w >/dev/null

echo "=== 情境 0：什麼都還沒說 ==="
"$AOS" state

echo "=== 情境 1：說了話但還沒有人推世界（未讀） ==="
"$AOS" say "讀 note.txt 然後告訴我裡面有幾行"
"$AOS" state
echo "未讀封數： $(ls .aos/agents/w/say 2>/dev/null | wc -l)"

echo "=== 情境 2：推 2 回合，讓它提出工具呼叫但還沒收到結果（做到一半） ==="
timeout 300 "$AOS" run . --step 2 > run.log 2>&1; cat run.log
echo "--- pending.json（非空＝手上還有沒收回的工具呼叫）："
cat .aos/agents/w/pending.json
echo "--- 此時 aos state："
"$AOS" state

echo "=== 情境 3：再推 6 回合讓它做完／或空轉 ==="
timeout 600 "$AOS" run . --step 6 >> run.log 2>&1; tail -6 run.log
echo "--- pending.json："; cat .aos/agents/w/pending.json
echo "--- 此時 aos state："; "$AOS" state
echo "--- 世界層 state.json（aos state 不印這個）："; cat .aos/state.json

echo
echo "EXPECT: 「還沒開始」「有未讀等著」「做完了」「卡住在空轉」要能從 aos state 分辨"
echo "ACTUAL: 情境 2（手上有 pending 工具）確實會顯示 status=tool／等工具結果——這一段是好的。"
echo "        但情境 0（什麼都沒發生）、情境 1（有未讀）、情境 3（做完了 或 放棄後空轉）三者的輸出完全一樣："
echo "        status=idle、detail=等待訊息，只差一個 turn 數字。A 隊實測推滿 45 回合、0 個檔案被改，"
echo "        全程 state 就是這個 idle／等待訊息，使用者無從分辨『它做完了』和『它早就放棄了』。"
echo "        status=thinking／處理本回合 只在 step 執行的那一瞬間存在，A 隊整場 11 次取樣全部落在 idle。"
echo "        會動的 phase／running[] 只寫在世界層 .aos/state.json，而 aos state 從不印它。"
rm -rf "$W"
