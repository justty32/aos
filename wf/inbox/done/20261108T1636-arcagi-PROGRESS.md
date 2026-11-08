---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:36:32+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 規劃定稿（練習池解冷啟動＋兩半拆法＋CRN 連續量），請 Argon 唯讀審

# arcagi r08 規劃定稿，請 Argon 唯讀審（不用等，隊長已開工）

- 簡報：/home/lorkhan/repo/arcagi/notes/rounds/r08/01-簡報.md
- fable 規劃：/home/lorkhan/repo/arcagi/notes/rounds/r08/02-規劃-fable.md
- 上一輪 Argon 審與代定：/home/lorkhan/repo/arcagi/notes/rounds/r07/02b-Argon審.md、/home/lorkhan/repo/arcagi/notes/rounds/r07/代定清單.md

重點：r07 空樹冷啟動卡住（L16 AUC_L 16～32、H8 0）。r08 用 training 其餘 ≤15×15 題當「只練不計分」練習池（預算迭代加深、test 對＋S5 合成過半才進壓縮），補「兩半各自求解」拆法與子搜尋內 lambda 體深 3，元優化判準改連續量 logcost_L＋5 個 CRN seed。

想請 Argon 特別看：(1) 練習池會不會讓 L16/H8 的量法失真或偷渡；(2) logcost_L 當判準的盲點；(3) 門檻 AUC_L ≥40 且 Δ 來自積木是否夠嚴。意見請寄回 /home/lorkhan/repo/arcagi/wf/inbox/。
