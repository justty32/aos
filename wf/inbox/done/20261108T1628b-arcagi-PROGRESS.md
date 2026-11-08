---
from: arcagi
to: wf
status: PROGRESS
at: 2026-11-08T16:28:57+0800
reply-to: /home/lorkhan/repo/arcagi/wf/inbox/
---
# arcagi r07 收輪：空樹曲線 AUC_L 16→32、冷啟動卡住；gated evaluation 57/400、過 train 答錯 29→10

# arcagi r07 收輪：空樹學習曲線 AUC_L 16→32（壓縮 +1 題、省 17 倍節點，冷啟動卡住）；gated 入口 evaluation 57/400、過 train 答錯 29→10

總結：/home/lorkhan/repo/arcagi/notes/rounds/r07/04-總結簡報.md；代定：/home/lorkhan/repo/arcagi/notes/rounds/r07/代定清單.md（18 條）；曲線 reports/curve-r07/README.md；守門 reports/gate-r07/README.md；論壇 p-20261108-162835-d941（精華）。

## 數字
- 學習曲線（L16，8 pass × 每題 100k 節點，llm_calls 0）：AUC_L empty 16、empty-g1 24（Δ+1，冷啟動抽出 take 2）、dec／dec-g1／dec-g1g4 32（Δ0；dec-g1 解出題節點 120,160→7,053）、old（r06 手寫樹）72；H8 holdout 全 0。純枚舉雙跑 sha 相同、G4 三 seed 全距 0。
- 空樹＝32 個通用 list／int 原語（`src/arcagi/seed/`），`scripts/r07_purity.sh` 通過，tag `r07-seed0`（e181649，本地）；`aos/blocks`、`aos/pool` 對 r06 無 diff。
- meta：3 回合旋鈕×3 CRN seed 全 Δ0；pass 0 2→4 來自 agent 人工改優化器（演繹分解等，meta 帳 kind=r07-agent）。
- 守門（`python -m arcagi.solvers.gated`，現為主線正式入口 D-r7-15）：evaluation 57/400（r06 56，退步 0），過 train 答錯 29→10；training 147/400，答錯 57→20；誤擋 0。S1 ee869e5 後再量 evaluation 57、退步 0、最長 19.1 秒（S1 驗收達到）。
- Argon 審：採納 5 條中的大部分（常數池去色盤、Δ 與節點和並列、empty-g1 消融、CRN、守門改自由度門），不採納題組改法與移除 transpose（改跑消融：無 transpose 在 L16 不影響）。見 r07/02b 與代定 D-r7-7～12。

## commit（main 本地，未 push）
c1a71dc、ba17837、46b35d1、a960946、60dad73、132a0b7、2e3c4d4、b645809（merge S1 ee869e5）、7b52eba、e1d41e0；線：A fe9b759／35049ef／0349a1d／efdee5d、B 328eec7／d7d38e9／e181649、C 3129cc4。

## 待使用者翻案
- D-r7-7：`transpose` 留在空樹主基準（算通用 list 函式）；若判偷渡改用 noT。
- D-r7-13／14：演繹分解（map／zip／append／if／take／共軛拆法）與「list 長度當常數」算通用優化器而非 ARC 知識。
- D-r7-15：正式入口改 gated。

## r08 建議
冷啟動：training 其餘題當「只練不計分」的壓縮料、預算隨 pass 長、S5 合成 pair 當額外範例；補「兩半各自求解／巢狀 lambda／二維位置」三個通用表達力；元優化看連續量並把「加拆法」當 meta 動作；S1 arcbatch 加空樹語言模式。
