#!/bin/sh
# 用法：make_letters.sh <worktree> <outdir>：產生一封真實的「辦好了」回信與一封卡住回信（卡住內文取自 brain 的 stuck_reply）
set -e
WT="$1"; OUT="$2"; M="python3 $WT/proto7-2/modules/mail/aos7-mail"
R=$(mktemp -d /tmp/mt-trial/root.XXXX); export AOS_MAIL_ROOT=$R
$M send you bob '你好，請用一句話說你會做什麼' >/dev/null 2>&1
$M read bob >/dev/null
printf '%s\n' '我是 bob，會讀你寄來的信、請 AI 幫忙回答，再把答案回信給你。' > $R/ok.md
$M done bob 1 DONE '我會讀你的信，請 AI 幫忙，再回信給你' $R/ok.md >/dev/null
$M send you bob '幫我寫一首短詩' >/dev/null 2>&1
$M read bob >/dev/null
cat > $R/stuck.md <<'B'
這封信「幫我寫一首短詩」辦到一半，問 AI 時被打斷（例如程式被關掉），等了約 1 分鐘還是不知道 AI 回了沒有，所以先停下這封，後面的信照常辦。系統不會自己重問。
怎麼辦：
① 什麼都不做：這封就停在這裡，不影響別的信。
② 再寄一次這封信：會從頭重新問 AI。現在用的是假 AI，不花錢。

細節見 `modules/up/ADVANCED.md` 的〈卡住的回信〉。
B
$M done bob 1 BLOCKED '「幫我寫一首短詩」問 AI 時被打斷，先停下' $R/stuck.md >/dev/null
cp $R/you/inbox/*-DONE.md "$OUT/done.md"; cp $R/you/inbox/*-BLOCKED.md "$OUT/blocked.md"
rm -rf "$R"
