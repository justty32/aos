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

狀態：已改（回改隊，分支 `loop9/skills`）；重試見下段。

- [x] 第一次跑先給一個不經帳的路徑（例如只跑 index＋本機挑選），把帳、grant、ledger 留到「接 AI 挑」那段
- [x] 若帳非得出現，在第一次跑旁一句白話說帳是什麼、grant 的 100000 是 token
- [x] 第一次跑開頭明寫「在 repo 根執行」（luna 走錯）
- [x] 新手要懂的詞壓到 ≤5（現在數到 10）

## 重試

### 第 1 輪（2026-10-09，回改隊）

改了什麼：`pick` 在 node 沒有 `budget/llm/` 時改走**本機關鍵字挑選**（不問 AI、不經 llmcall、不碰帳），stderr 一行提示；有帳或給 `--budget` 才走原本的 AI＋記帳路。第一次跑縮成五行（`index`＋`pick`，`git rev-parse` 自找 repo 根，repo 子目錄裡跑也對）；README 只留三個詞（skill、目錄、pick），帳／必用表／掛載全移到「進階」；`--help` 補白話與退出碼。原始回報：[raw/skills-haiku-r1.md](raw/skills-haiku-r1.md)、[raw/skills-luna-r1.md](raw/skills-luna-r1.md)。

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 3（開頭＋第一次跑約 700 字 ≈ 1.8 分＋5 行指令 1.25 分＋卡點 0） | ≤10 | 是 |
| 對外指令 | 3（index／pick／mount；第一次跑只用 2 個，不再需要 aos7-budget） | ≤3 | 是 |
| 新概念（兩位取多） | 4（skill、目錄、pick、node） | ≤5 | 是 |
| 分數（兩位取差） | 7.4（Haiku 7.4／luna 8.6） | ≥7 | 是 |
| **總判** | **過** | | |

剩下的意見（不擋過關）：Haiku 仍答「ELI5 之後複雜」，理由是**進階段**的帳、帳任務、llmcall 詞多；luna 答「否」。Haiku 另提 `git rev-parse` 在 repo 外會失敗（README 已有一句替代寫法）。

審查（gpt-6-astra，read-only）3 條 P2 已修：bank.py 明給 `--budget budget/llm`（題庫一律走 AI，不落本機）；本機挑選的 log `call` 改成 `local-<題目＋目錄雜湊>`（重試統計不再把不同題當同一次）；README「換真 AI」改成另開新 node（開過的帳不能改 gateway）。
