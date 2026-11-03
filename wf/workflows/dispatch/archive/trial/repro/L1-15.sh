#!/usr/bin/env bash
# 路徑不存在，錯誤訊息卻指向權限
set -u
AOS=${AOS:-/home/lorkhan/repo/simple_tools/aos/build/bin/aos}
echo "--- /nonexistent 存在嗎： $([ -e /nonexistent ] && echo yes || echo no)"
"$AOS" run /nonexistent/zzz --step 1; echo "exit=$?"
"$AOS" deliver /nonexistent/zzz -- echo hi; echo "exit=$?"
echo
echo "EXPECT: 「/nonexistent/zzz 不存在」或「不是一個 aos 世界」"
echo "ACTUAL: 「無法建立 /nonexistent/zzz/.aos/inbox: Permission denied」——把 ENOENT 報成權限問題，"
echo "        使用者會跑去 chmod／sudo，而真正該做的是檢查路徑打錯了。"
echo "        （對比 L1-09：路徑打錯但父目錄可寫時，它反而靜默建出一個新世界、exit 0。）"
