# 新手試用：wfnode（工作流樹 node）

← [總表](README.md)｜受測：`proto7-2/modules/wfnode/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/wfnode-haiku.md](raw/wfnode-haiku.md)、[raw/wfnode-luna.md](raw/wfnode-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 10 | ≤10 | 是 |
| 對外指令 | 3（init／state／check） | ≤3 | 是 |
| 新概念（兩位取多） | 7 | ≤5 | 否 |
| 分數（兩位取差） | 6.8 | ≥7 | 否 |
| **總判** | **不過**（概念、分數） | | |

跑通情況：兩位都跑通：check 印 OK、state 寫進續行點。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 8 | 9 |
| 容易理解 | 5 | 8 |
| 複雜的藏起來 | 6 | 8 |
| 外層簡單但全面 | 7 | 8 |
| 要背的少 | 8 | 9 |
| 平均 | 6.8 | 8.4 |

## 卡點（新手視角，依嚴重度）

1. init 印「未定 97 處」，緊接著 check 說「剩 0 處」並 OK——新手以為 OK＝都填好了，不知道「未定」check 不管（Haiku）
2. init 輸出「已處理導入判斷」五行，看不懂「導入判斷」是什麼、是我要處理還是工具處理完了（Haiku）
3. `cat AGENTS.md` 後又連到 STRUCTURE／WORKFLOWS／INDEX 一堆檔，人不知道先讀哪個（Haiku）
4. 「看成果」要跑 examples/minimal/run.sh，怕它寫進 repo，沒跑（Haiku）
5. open 項「只列還沒做完的」，沒說怎麼知道哪些沒做完（Haiku）

## ELI5

這是幫 AI 助手準備「工作筆記資料夾」的小工具。第一次 init 一次，目錄和入口都放好。每次收工用一句話告訴它「停在哪、下一步做什麼」，下次開工先看這句就知道從哪接。check 看到 OK 就表示資料夾沒壞。

## ELI5 之後還複雜嗎

是。指令只有三個，但「未定」「導入判斷」「open 項」「續行點」這幾個詞 ELI5 帶不過去，init 一跑就印出來。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 第一次跑的預期輸出旁講一句：「未定 N 處」是給人／AI 之後填的，check 不管它，OK 不代表填完
- [ ] 「導入判斷」在 init 輸出或 README 用一句白話說明（誰處理、新手要不要管）
- [ ] README 說一句人第一次該讀 AGENTS.md 的哪一段（或只讀哪個檔）
- [ ] examples/minimal/run.sh 標明會寫到哪裡（暫存目錄或 repo）
- [ ] 新手要懂的詞壓到 ≤5（現在試用者數到 7：node、wf 樹、open 項、續行點、flavor、模板／AOS7_WF_HOME、導入判斷／佔位）
