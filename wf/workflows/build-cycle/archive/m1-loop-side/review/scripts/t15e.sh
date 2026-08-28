#!/bin/bash
# 15e：確認 header 在批被取走／執行完之後不會被清掉 → 15c 的危險窗口是「永久」
. /tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/14f34f87-d061-439b-85fc-24ba3d3f51e0/scratchpad/m1-review/lens3/env.sh
W=$LAB/w15e; mkworld "$W"; LOG=$W/log; : > "$LOG"
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo A >> $LOG"]}]
EOF
"$AOS" exec "$W" >/dev/null 2>&1
H1=$(cat "$W/.aos/inst-head.json"); echo "turn1 後 header: $H1"
# 中間跑很多回合的「別的事」——但都是空轉（沒有投遞就不會改 header）
for i in 1 2 3 4 5; do "$AOS" exec "$W" >/dev/null 2>&1; done
echo "空轉 5 回合後 header: $(cat "$W/.aos/inst-head.json")  （相同＝窗口沒關）"
# 很久以後，一個全新的投遞恰好同名同內容
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo A >> $LOG"]}]
EOF
"$AOS" exec "$W" >/dev/null 2>&1; echo "  rc=$?"
echo "log（期望 A,A）: [$(tr '\n' ',' < "$LOG")]"
echo "inbox: [$(ls -A "$W/.aos/inst.tempd")]  turn=$(cat "$W/.aos/turn")"
echo
echo "對照：內容差一個字元就會正常執行"
cat > "$W/.aos/inst.tempd/1234-0.json" <<EOF
[{"argv":["/bin/sh","-c","echo B >> $LOG"]}]
EOF
"$AOS" exec "$W" >/dev/null 2>&1
echo "log: [$(tr '\n' ',' < "$LOG")]"
