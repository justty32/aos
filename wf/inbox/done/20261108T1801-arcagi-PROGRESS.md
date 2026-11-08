---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T18:01:43+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r08 收輪：主題練習池沒解開冷啟動（AUC_L 32＝不學對照）；立足點主題長 8 積木、H24 1→2；gated evaluation 56/400

# arcagi r08 收輪：練習池沒解開冷啟動（主樹 AUC_L 32＝不學對照）；立足點主題長出 8 積木、H24 1→2 但不轉移；gated evaluation 56/400

總結：/home/lorkhan/repo/arcagi/notes/rounds/r08/04-總結簡報.md；代定：/home/lorkhan/repo/arcagi/notes/rounds/r08/代定清單.md（24 條）；曲線 /home/lorkhan/repo/arcagi/reports/curve-r08/README.md；evaluation /home/lorkhan/repo/arcagi/reports/gate-r08/README.md；Argon 審存 r08/02b。

## 數字
- 學習曲線（L16＋H8＋H24 每題 100k、P 25k→400k、8 pass、seed b67dc2a、llm_calls 0）：主樹 pool（使用者 16:50 指定的 32 題主題池）AUC_L 32、Δ0，與 dec-g1 32、pool-noG1 32、pool-rand32 32 相同——主題池 0 題過 train。pool-foot32（按空樹立足點挑主題）26、Δ−1，但 clean_P 10→15、8 積木、transpose 6 題共用、H24 1→2。pool-halves 48（手加拆法，未採用）。H8 全 0。
- meta：5 回合 × 5 CRN seed＋halves／nest 兩個 r08-agent 動作全不採用；halves L16 4→6、H24 不動、bootstrap 判準沒過（20.27 < 25.78）→ r09 判準改「新解題數優先」。
- gated evaluation（tag r08-seed0，含 S1 cf83c7f）：56/400（r07s1 57），退步 be03b35f（S1 只用 training 重選的 colormap 支持度門擋掉），不回改；過 train 答錯 10→9。
- Argon 審：採納拔 test／S5 濾網（改 train 留一＋MDL）、盲測 H24、logcost 封頂＋跨題 bootstrap、加嚴門檻、C++ 只做子問題枚舉；部分採納縮池（後由使用者 32 題取代）。

## r09
照使用者晚間七條（04 §6 逐條對照 r08 結果）；**等 alt-fable Q7 錘子設計圖 v1 出來再定稿，本隊長不開 r09。** r08 結果最對應意見 6：只有本體被暴力搜，審查（G1 門、守門、判準）與改進（拆法、主題挑法）仍手調。

## commit
3f50118 892bc35 c284157 4534a51 8d17d36 4a24cfb 2753f88 a37989b 0d53498 570514a 15405ba b44b243 38b9344（隊長）；b67dc2a（A）；fcf3f1c 51fe268 424d0d0（B）。皆未 push（S1 有 push origin/main）。
