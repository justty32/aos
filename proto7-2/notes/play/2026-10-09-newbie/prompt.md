# 新手試用：prompt（拼 prompt 包）

← [總表](README.md)｜受測：`proto7-2/packs/prompt/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/prompt-haiku.md](raw/prompt-haiku.md)、[raw/prompt-luna.md](raw/prompt-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 5 | ≤10 | 是 |
| 對外指令 | 2（render／expand） | ≤3 | 是 |
| 新概念（兩位取多） | 11 | ≤5 | 否 |
| 分數（兩位取差） | 6.8 | ≥7 | 否 |
| **總判** | **不過**（概念、分數） | | |

跑通情況：兩位都跑通：render 印 rendered、expand 印回原文。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 9 | 8 |
| 容易理解 | 6 | 7 |
| 複雜的藏起來 | 6 | 8 |
| 外層簡單但全面 | 7 | 8 |
| 要背的少 | 6 | 9 |
| 平均 | 6.8 | 8.0 |

## 卡點（新手視角，依嚴重度）

1. 範例 node 裡的 wf/AGENTS.md、SESSION-LOG、inbox/ 三樣東西沒說約定，看不懂 node 為什麼這樣分（Haiku）
2. 示範 tokens_est 206 對 tokens_est_full 220，只省 6%，以為「收起來」會省很多，懷疑自己跑錯（Haiku）
3. prompt.json 有 `$opt`／`$val`／`$ref`／`$fmt`／`$env` 加 tail／latest／append 等七八種寫法，要自己寫清單時得先學（兩位都提）

## ELI5

這是把很多份文件拼成一封給 AI 看的信的小工具。你寫一張清單說要給 AI 看哪些檔，它每次照清單現讀現拼。太長的段落先收起來只留編號，要看原文再用 expand 叫出來。

## ELI5 之後還複雜嗎

是（兩位都說是）。指令只有兩個，但清單裡的 `$` 寫法多，自己動手寫第一份清單時就要學一整套小語言。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 第一次跑的示範要讓「收起來」看得出效果（現在只省 6%，新手以為跑錯），或在輸出旁說明為什麼只省一點
- [ ] `$` 寫法在 README 只露出新手第一份清單要用的 1～2 種，其他收到「進階」
- [ ] 範例 node 的 wf/ 結構寫一句「這是 wfnode 裝的，本包只讀」或連到 wfnode README
