---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T19:30:54+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# r09 停手：錘子活樹 AUC_L 40、H24 1→2 不退；白話進度已寫

照使用者 18:54 的指示，r09 已停手，之後只回答問題、不推進。

- 白話進度：/home/lorkhan/repo/arcagi/notes/rounds/r09/05-白話進度.md
- 總結：/home/lorkhan/repo/arcagi/notes/rounds/r09/04-總結簡報.md
- 代定清單（30 條）：/home/lorkhan/repo/arcagi/notes/rounds/r09/代定清單.md
- 曲線：/home/lorkhan/repo/arcagi/reports/curve-r09/README.md
- 活樹：/home/lorkhan/code/playground-arc1/ws/hammer/（README.md、./_view.sh、./ctl status；目前沒有程式在跑）
- 論壇總結帖：p-20261108-192944-ecb8（已加精華）

數字：
- 主樹 AUC_L 40；不學對照 32；手寫拆法對照 48。
- H24 逐 epoch：1,2,2,2,2,2,2,2,2，熔斷 0 次。H8 全程 0。llm_calls 0。
- M0 重現 r08 sha 7aebb3c73f28，過。
- M2 四中二：字面上過 (a)、(b)，(b) 打折。(a) 是樹自己升級的睡眠造詞積木帶來 H24 +1；(b) 的路由變更，功勞是 r08 手寫的 halves。
- 真蠟模 b27ca6d3 三段都沒擬合到，原因是 LLM 切的步跟空樹語言不對齊；這是 r10 的頭號題目。
- evaluation 沒重量：入口沒動，仍是 56/400。

v4：§5.1 的補丁本輪沒插，frozen.json 的 H24 規則也沒動，等使用者裁方向題（D-r9-26）。
commit 4944c3a，已 push。
