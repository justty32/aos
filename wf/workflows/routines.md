# routines — 常規事務（固定循環的例行）

← [WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

記「每隔一段時間該做的事」，由 [tick](tick.md) 心跳在到期時投遞。live 清單的真源是
`.aos/heartbeat/routines.json`，不是本檔；它使用 `wf-table/1` 資料檔契約。

**何時用**：① **登記**——你說「這是常規事務，幫我加進 routine」「登記例行」；
② **執行**——agent 收到 `aos tick` 投來的 `ask`。
**何時不用**：臨時、指定時刻、做一次就沒了的 → [schedule](schedule.md)。重活（深度巡檢、調查）不在心跳回合裡跑。

## Done when

- **登記**：`aos routine add` 成功，且 `aos routine ls` 看得到項目與下次到期。
- **執行**：`aos tick` 已投遞到期項、更新 `last_run` 並寫入 log；收到 `ask` 的 agent 已完成判斷與可做的部分。

## 流程

### A. 登記（使用者請求時）

1. 問清三件事：**多久一次**、**誰處理**（agent 判斷，或 argv 直接執行）、**做什麼**。
2. 呼叫 `aos routine add`。`--every` 只收 `Nd`／`Nh`／`Nm`／`Ns`；需要判斷的內容用 `--ask`：

   ```sh
   aos routine add --every 7d --ask "檢查工作流文件；有問題時判斷怎麼處理" --note "每週巡檢"
   ```

3. 能直接執行、無須 agent 判斷的內容放在 `--` 後：

   ```sh
   aos routine add --every 7d --note "每週檢視" -- git status --short
   ```

4. `[folder]` 可省略；省略時從 cwd 往上找最近含 `.aos/` 的目錄。回一句確認，**不當場做**。

### B. 執行（tick 心跳到期時）

1. `aos tick` 讀取清單、判現在時間與到期項；agent 不判時間、不比對清單，也不更新 `last_run`。
2. 到期的 argv 由 tick 投進 inbox；到期的 `ask` 由 tick 透過 `aos say` 交給資料夾裡的 agent。
3. agent 只在收到 `ask` 時判斷並做。守**鐵律 2（授權來源）**：使用者親自登記在清單的項目即有授權；唯讀的直接做；不可逆的即使登記了，情況有變也先問。
4. `aos tick` 投遞後更新該列 `last_run` 並寫一行 log。重活記一行 open、另開 session，不塞在心跳回合裡。

## 時機分區

live 時機資料只存在 `.aos/heartbeat/routines.json`；本檔不留副本。給人查看一律跑
`aos routine ls`，它會印出目前項目與下次到期。

## 間隔登記表

live 間隔資料同樣只存在 `.aos/heartbeat/routines.json`。用 `aos routine ls` 查、
`aos routine rm <id>` 刪；到期判定與 `last_run` 更新都由 `aos tick` 負責。

## 交接

- 到期項卡在使用者 → [WAIT_USER](../WAIT_USER.md) 一行；跨 session 的未完進度 → [SESSION-LOG](../SESSION-LOG.md) 一行 open。
- 一次性的定時請求 → [schedule](schedule.md)。做常規事務時撞到的坑 → [common/gotchas](common/gotchas.md)。
