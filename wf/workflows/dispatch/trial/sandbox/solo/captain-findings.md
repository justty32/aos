# 隊長自測的發現草稿（待與 A/B/C/D 去重後編號）

證據來自 `captain-probe.sh` / `captain-probe2.sh`，世界在 `sandbox/solo/cap/`。

| 暫號 | kind | sev | 現象 |
|---|---|---|---|
| CAP-1 | bug | 2 | `aos say --help` 把字串 `--help` 當成訊息投給 agent（`.aos/agents/cap/say/` 多一個檔），不印任何 usage，exit=0 |
| CAP-2 | bug | 1 | `aos deliver --help` → `無法讀取 --help`，exit=1；它把 `--help` 當 inst.json 檔名 |
| CAP-3 | bug | 2 | `aos run /tmp/typo-xyz --step 1` 靜默**建出**一個新世界並印 `turn 1: idle`、exit=0；打錯路徑不會有錯誤 |
| CAP-4 | bug | 1 | `aos run /nonexistent/zzz --step 1` 報 `Permission denied`，但真正原因是路徑不存在 |
| CAP-5 | awkward | 3 | 說了 3 句話之後 `aos state` 仍是 `idle`／`等待訊息`／`turn 0`／`updated_at` 沒動；`listen --once` 印空；`log.md` 0 bytes。使用者看不到自己剛說的話，也看不到有幾封未讀 |
| CAP-6 | awkward | 3 | `aos agent init` 成功時**一個字都不印**：不說 agent 叫什麼、建在哪、用哪顆 CPU／哪個模型，也不說「下一步請另開視窗跑 aos run」 |
| CAP-7 | awkward | 2 | `aos state` 只印 agent 的 `status.json`（4 欄），不印世界的 `state.json`（`phase`／`running[]`／`turn`）。想知道「有沒有 run 在推、這回合在跑什麼」只能自己 `cat .aos/state.json` |
| CAP-8 | bug | 1 | `--help` 的 exit code 四種都有：`run`/`llm`/`tool` 0、`listen`/`state`/`talk` 2、`deliver` 1、`say` 0（且送出訊息） |
| CAP-9 | spec-gap | 2 | `aos state --help`／`aos talk --help` 印 `usage: aos state `（後面空的），沒有任何選項；`aos agent talk` 有 `--interface pi`，頂層 `talk` 完全沒提 |
| CAP-10 | spec-gap | 3 | lmstudio 的 `engine.json` 只有 `{"engine":"lmstudio"}`，**不記模型**。實際用哪個模型由跑 `aos run` 那個 shell 的 `AOS_LLM_MODEL` 決定；兩個視窗環境不同＝兩顆腦，世界檔案裡看不出來 |
| CAP-11 | bug | 2 | `echo hi \| AOS_LLM_MODEL=no/such-model aos llm` **正常回一段答案、exit=0**；打錯模型名不會有任何提示，使用者不知道回答自己的是誰 |
| CAP-12 | spec-gap | 2 | `agent init` 預設只裝 `cat`／`ls`／`sh`：沒有 write／edit、沒有 `make`、沒有 `git`。要當 coding agent 只能全部走 `sh -lc` 逃生口 |
| CAP-13 | awkward | 1 | 頂層 `aos --help` 說 tool 是「登記／列出／移除」，但 `aos tool list` 是 usage error（真名是 `ls`／`rm`） |
| CAP-14 | bug | 3 | 在 repo 內任何子資料夾跑 `aos agent init`，`find_folder` 往上找到 repo 根的 `.aos/`，agent 被靜默建到 repo 根、名字取自 repo 根的資料夾名，沒有任何提示。必須先 `mkdir .aos` 才會建在原地 |
