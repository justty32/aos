#!/usr/bin/env bash
# 打錯資料夾名字，aos run 靜默建出一個新世界；打到不可寫的路徑則報成 Permission denied
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
BASE=$(mktemp -d)
TYPO="$BASE/my-projekt"     # 使用者其實想打 my-project
echo "--- 目標路徑存在嗎： $([ -d "$TYPO" ] && echo yes || echo no)"
"$AOS" run "$TYPO" --step 1; echo "exit=$?"
echo "--- 跑完之後："
find "$BASE" | sort
echo
echo "--- 另一種打錯：根本不可寫的路徑"
"$AOS" run /nonexistent/zzz --step 1; echo "exit=$?"
echo
echo "EXPECT: 資料夾不存在時，aos run 應該說「這個資料夾不存在／不是一個 aos 世界」並以非 0 結束"
echo "ACTUAL: 它靜默 mkdir 出 $TYPO/.aos/{inbox,every,agents} 並印 'turn 1: idle'、exit=0；"
echo "        路徑不可寫時則報 'Permission denied'（真正原因是 /nonexistent 不存在）"
rm -rf "$BASE"
