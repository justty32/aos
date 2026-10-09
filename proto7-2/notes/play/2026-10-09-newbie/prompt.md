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

狀態：**已改**（2026-10-09 回改隊，分支 `loop9/prompt`）；重試見下段。

- [x] 第一次跑的示範要讓「收起來」看得出效果（現在只省 6%，新手以為跑錯），或在輸出旁說明為什麼只省一點
- [x] `$` 寫法在 README 只露出新手第一份清單要用的 1～2 種，其他收到「進階」
- [x] 範例 node 的 wf/ 結構寫一句「這是 wfnode 裝的，本包只讀」或連到 wfnode README

## 重試

回改隊（Opus）照 U 隊任務模板出題，目標加碼為「跑通第一次跑＋照 README 自己寫一份清單讀自建檔並 render 成功」；同兩位新手、只准讀 README 與 `--help`、在 `/tmp` 暫存目錄操作。

改了什麼（第 1 輪前）：第一次跑改用新範例 `prompts/first.json` 讀 7800 字週報 `docs/weekly.md`，預設門檻就收，回條 106 對 2606 token；README 只留「三個概念」（node、prompt.json、讀檔）＋「自己寫第一份清單」，其餘 `$` 寫法、門檻、回條欄位、退出碼、wf 範例全收到「進階」並標「第一次用到這裡就夠了」，註明 `wf/` 是 wfnode 裝的、本包只讀；`--help` 補每個參數的說明。

第 2 輪前再改：回條只看兩件事並白話解釋 token；說明 `litellm`／`model` 是信封、可在清單頂層換模型；「自己寫」補一句路徑從 node 算起與完整指令。第 2 輪後順手把「`--help`」改成「`aos7-prompt render --help`」（Haiku 卡點 2，未再試）。

| 輪 | Haiku 分數 | luna 分數 | 取差 | 概念（取多） | 指令 | 分鐘（人估） | 過 | 原始回報 |
|---|---|---|---|---|---|---|---|---|
| 1 | 7.2 | 8.6 | 7.2 | 6（Haiku：多算 tokens_est、expand） | 2 | ≈2 | 否（概念） | [haiku](raw/prompt-haiku-r1.md)／[luna](raw/prompt-luna-r1.md) |
| 2 | 7.8 | 8.4 | **7.8** | **4** | **2** | ≈2 | **是** | [haiku](raw/prompt-haiku-r2.md)／[luna](raw/prompt-luna-r2.md) |

ELI5 之後還複雜嗎：兩輪兩位都答**否**。剩下的小意見（不擋）：進階段 `$` 寫法擠一段、失敗回條沒範例、`expand` 輸出很長。
