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

狀態：已改（回改隊 wfnode，分支 `loop9/wfnode`），重試見下段。

- [x] 第一次跑的預期輸出旁講一句：「未定 N 處」是給人／AI 之後填的，check 不管它，OK 不代表填完
- [x] 「導入判斷」在 init 輸出或 README 用一句白話說明（誰處理、新手要不要管）
- [x] README 說一句人第一次該讀 AGENTS.md 的哪一段（或只讀哪個檔）
- [x] examples/minimal/run.sh 標明會寫到哪裡（暫存目錄或 repo）
- [x] 新手要懂的詞壓到 ≤5（現在試用者數到 7：node、wf 樹、open 項、續行點、flavor、模板／AOS7_WF_HOME、導入判斷／佔位）

## 重試

### 第 1 輪（2026-10-09，回改隊 wfnode）

**改了什麼**

- 接口：`init` 不再印五行「已處理導入判斷」（工具自動處理的，人不必看）；改印「裝好了／空格 N 處＝之後慢慢補、check 不檢查它／下一步」，真有要人決定的段落才印「要你決定：N 段」。`check` 的 OK 行直接講「資料夾沒壞」並註明「（未定：…）」空格不在檢查範圍；open 項改說「待辦清單：AI 手上 N 件、等人做 N 件」；不 OK 時每類記號附一句該怎麼改。`state` 不給句子＝印出最新續行點（取代「cat 某檔」看成果）。`--help` 全改白話並附例子。
- README：第一次跑附逐行預期輸出與「OK 不等於空格都填好」；詞壓到三個（node、續行點、空格）；明說 AGENTS.md 與 `wf/` 給 AI 讀、人不必讀；flavor、AOS7_WF_HOME、導入判斷、待辦清單、run.sh（標明只寫暫存目錄、自動刪）移到分隔線下的進階段。
- 測試：兩處斷言跟著新字樣改，新增 `state` 不給句子的測試；模組 36 項綠。

**結果**（原始回報：[raw/wfnode-haiku-r1.md](raw/wfnode-haiku-r1.md)、[raw/wfnode-luna-r1.md](raw/wfnode-luna-r1.md)）

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 6（讀 1165 字 ≈ 2.9＋指令 5 行 ≈ 1.3＋卡點 2） | ≤10 | 是 |
| 對外指令 | 3（init／state／check） | ≤3 | 是 |
| 新概念（兩位取多） | 4（Haiku：node、續行點、空格、模板倉；luna 3） | ≤5 | 是 |
| 分數（兩位取差） | **7.4**（Haiku 7.4／luna 8.8） | ≥7 | 是 |
| **總判** | **過** | | |

兩位都跑通（check 印 OK），都答「ELI5 之後不複雜」。剩下的小卡點：Haiku 不確定要先 `cd` 到 repo 根（已在 README 補一句，未再重試）；luna 提到頂端「計畫」連結指向 notes（不影響第一次跑，未改）。
