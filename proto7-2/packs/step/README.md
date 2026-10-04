# step 任務包（步驟表直譯器）第一版

← [proto7-2](../../README.md)｜[核心 spec](../../spec.md)｜細部規則：[spec.md](spec.md)｜依據：[第六輪綜合](../../../proto7/notes/thinking/2026-10-04-r6-synthesis.md)、[第五輪骨架](../../../proto7/notes/thinking/2026-10-04-r5-synthesis.md) §4

**一個普通 `keep` 任務照步驟表一步步派子工作（`once`），子工作把結果寫到槽外，直譯器靠結果檔推進、被殺後接回同一嘗試。** 通用任務包（原則 5、8）：不帶 LLM、帳、資源；daemon／tick 核心零新增，只用核心公開的檔（tasks.json 拿表鎖三態寫、槽 birth／exit、round.json、tock.json、槽 ctl.json、daemon 的 wake 控制檔）。

| 項目 | 內容 |
|---|---|
| 分類 | 通用任務包（`layer: kernel`），單 node |
| 接法 | A 普通 keep 任務：`{"name": "step-<job>", "mode": "keep", "argv": ["python3", "<proto7-2>/packs/step/bin/aos7-step", "run", "jobs/<job>"]}` |
| 預設 | 不裝就不存在；選項預設見 spec §5 |
| 依賴 | 工具包（`aos7_taskside.wait_tock`、`aos7_ctl`）、核心 `aos7_fs`（`edit_json`、`fact`） |
| 程式 | `aos7_step.py`（直譯器、檢查器、人手指令）、`aos7_step_result.py`（子工作包裝程式）、`bin/aos7-step`、`bin/aos7-step-result` |
| 範例 | `examples/csv/`（CSV→JSON→統計報表，兩步都冪等）、`examples/backup/`（dump→verify→rotate→notify，rotate 不冪等） |
| 測試 | `tests/`（`python3 proto7-2/tests/run_all.py packs/step/tests`；run_all 預設不收 `packs/`，要明確給路徑） |

## 四個組件（契約卡，細節在 spec.md）

**直譯器 `aos7-step run <工作資料夾>`**
- 職責：每收到一次 tock 讀框架、查槽外結果、推進 `pc`；一次最多登記一個子工作的 `once`。框架 `frame.json` 只放接續狀態與把手。
- 前置條件：自己是 `max_live: 1` 的 keep（同一工作同時只有一個直譯器，核心保證 keep 不雙開）；步驟表過了檢查器；`frame.json`、`results/` 只有本包寫；改 tasks.json 的人都拿表鎖。
- 保證：同一嘗試不派第二次；同一結果只推進一次；證據不足停在 `unknown`，不自動重送（除非步宣告冪等且選了 `on_unknown: resend`）；壞表拒寫；框架壞了不前進、記錯、等人；耐性用本地回合（pause 時不走）；工作進行中步驟表被改＝停（版本固定）。
- 明確不管：子工作做的事對不對、外部效果（只看結果檔與它宣告的產物）；人手改 `frame.json`／`results/`；派工以外的資源、帳、鄰居。

**子工作包裝程式 `aos7-step-result`**
- 職責：跑實際命令、等它結束、檢查宣告的產物，原子發布一份結果檔（帶 job／inst／step／request／attempt 與核心 `slot#run`）。退出碼照抄命令的。
- 前置條件：由直譯器登記的 once 起（argv 由直譯器展開）；結果檔路徑這次嘗試獨有。
- 保證：結果檔要嘛完整、要嘛不存在（rename）；不覆寫已有的結果；被殺就沒有結果（不假報）。
- 明確不管：命令本身的冪等與副作用；結果寫好之後才發生的事。

**結果檔 `results/<step>/<attempt>.json`**：工作交付的依據；`exit.json` 只是旁證。到工作結案（`aos7-step close`）才清。

**檢查器 `aos7-step check <steps.json>`**：結構錯誤＋三條（等結束只等有限工作；重試要冪等或先查回條；時間值標線——v1 只有本地回合）。不執行、不改檔；有錯退出碼 1。

## 人手指令

- `aos7-step status <工作資料夾>`：印框架摘要（`pc`、等誰、停在哪、最近錯誤）。
- `aos7-step resume <工作資料夾> [--resend]`：清掉停住（`halt`）。結果已到就照結果走；`--resend` 用同一個 request、新 attempt 重派（人負責）。
- `aos7-step close <工作資料夾>`：工作已結束才可以：清 `results/`，框架標 `closed`。

## 界線

- 框架與 tasks.json 不是同一筆交易（spec §4 的派工窗口）；第一版不做交易，跨回合說不清的一律 `unknown`。
- 回合耐性是「這個 node 的回合」，不是牆鐘；`until_round` 是啟動准入，不是完成期限，本包不用它。
- 核心只保證 once 最多一次、once 槽報完再留一回合；本包不依賴槽留多久，只依賴自己的結果檔。
