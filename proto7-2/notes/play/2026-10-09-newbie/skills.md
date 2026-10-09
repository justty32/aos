# 新手試用：skills（skill 索引／挑選／掛載）

← [總表](README.md)｜受測：`proto7-2/modules/skills/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/skills-haiku.md](raw/skills-haiku.md)、[raw/skills-luna.md](raw/skills-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 9 | ≤10 | 是 |
| 對外指令 | 5（index／pick／mount＋第一次跑必用 aos7-budget init／ledger） | ≤3 | 否 |
| 新概念（兩位取多） | 10 | ≤5 | 否 |
| 分數（兩位取差） | 5.4 | ≥7 | 否 |
| **總判** | **不過**（指令、概念、分數） | | |

跑通情況：兩位都跑通：三行索引、pick 挑出 aos-inbox、必用表。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 6 | 8 |
| 容易理解 | 5 | 8 |
| 複雜的藏起來 | 4 | 8 |
| 外層簡單但全面 | 7 | 8 |
| 要背的少 | 5 | 9 |
| 平均 | 5.4 | 8.2 |

## 卡點（新手視角，依嚴重度）

1. pick 之前要先開「帳」、起「帳任務」，README 只說「一律經 llmcall 記帳」，沒說帳是什麼（Haiku）
2. 照抄 `sed ... grant.json` 改使用者與額度，不知道 grant 還有哪些欄位、100000 是什麼單位（Haiku）
3. 「空間根（有 .aosd/ 的那層）」沒解釋 .aosd 是什麼（Haiku）
4. 沒說清楚要在 repo 根跑，在 proto7-2 下跑路徑多一層失敗（luna）

## ELI5

資料夾裡放很多「說明書」。index 把每本的名字和一句話抄成目錄，pick 讓 AI 看題目挑一本，mount 把挑中的借給某個任務用。用 AI 挑之前要先開一本記帳本。

## ELI5 之後還複雜嗎

是（兩位都說是）。三個指令本身好懂，但第一次跑就被迫碰 budget／grant／帳任務／llmcall，這些 ELI5 帶不過去。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 第一次跑先給一個不經帳的路徑（例如只跑 index＋本機挑選），把帳、grant、ledger 留到「接 AI 挑」那段
- [ ] 若帳非得出現，在第一次跑旁一句白話說帳是什麼、grant 的 100000 是 token
- [ ] 第一次跑開頭明寫「在 repo 根執行」（luna 走錯）
- [ ] 新手要懂的詞壓到 ≤5（現在數到 10）
