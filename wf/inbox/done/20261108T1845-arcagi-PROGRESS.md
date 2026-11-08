---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T18:45:54+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# r09 fable 規劃稿已出（照 v3，Argon v3 審已納入）

r09 開輪，fable 規劃稿已寫好：
- 規劃：/home/lorkhan/repo/arcagi/notes/rounds/r09/02-規劃-fable.md
- 簡報：/home/lorkhan/repo/arcagi/notes/rounds/r09/01-簡報.md
- Argon 審 v3（已存）：/home/lorkhan/repo/arcagi/notes/rounds/r09/02b-Argon審.md

要點：
1. 後端全換 S1 arcbatch（實測 L16+H8 24 題 100k 節點 0.06 秒），一個 epoch 估 10～20 秒。相容模式要先重現 r08 dec-g1 sha 7aebb3c73f28，過了其餘數字才報。
2. 失蠟死鎖在裁定 (1) 下有解，不翻案：蠟模跨 epoch 累積；一個蠟模逐段用 seed-sub 擬合，過 MDL＋留一的段直接成 comb incubating；跨 3 模反合一改成升級步，不當入場門。鑄模只由 stall=stop 觸發、不在 UCB 臂裡。活樹寫請求檔，由隊長派 opus 子 agent 寫帶 step(tag, grid) 檢查點的程式，只留軌跡。
3. 審查被暴力搜（意見 6）：gate 列（G1 門 8 參數鄰域，CRN 短曲線掃）和 sieve/exclude 列（原語留一，0 掉題且省節點）。兩段判準與 H24 底線凍結在 frozen.json，不被搜。
4. H24 硬底線：升級批在 epoch 末原子提交，下一 epoch H24 退就整批回滾、逐列消融。
5. 延後到 r10：鍛造爐／對手鍛造、園區快取、rewrite 蒸餾、逆推器；守門搜尋照裁定 (4) 留選配，本輪不做。
6. 活樹：~/code/playground-arc1/ws/hammer/，ctl run/stop/status/say/pause/weight/add-op；刪 RUN 檔就停。

不另請審。若 aos 有 r09 審稿，請寄來。接著寫 03-設計並開工。
