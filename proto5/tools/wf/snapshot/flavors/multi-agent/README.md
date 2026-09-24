# multi-agent flavor 包 — 多 agent 協作

← [repo README](../../README.md)（導航中樞）

給「工作橫跨多個資料夾、多條線同時跑」的專案。搭配 [`template/`](../../template/) 這個**共用 kernel** 一起用，管**多 agent 協作的三件事**：

| | 工作流 |
|---|---|
| **通訊**——誰跟誰說什麼 | [inbox](workflows/inbox/README.md) |
| **資源**——誰現在可以動螢幕／那台裝置 | [resources](workflows/resources.md) |
| **分工**——誰負責哪塊、誰驗收 | [dispatch](workflows/dispatch/README.md) |

其中 inbox 補上 kernel 缺的**活狀態第三軸**：等**別資料夾的 agent**（kernel 只有「我自己的進度」`SESSION-LOG.md` 與「等使用者」`WAIT_USER.md`）。

**信像 email，不像聊天**：沒有推播、沒有 ack、沒有重試，寄出就接受「對方可能晚很久才讀」。但**回報不是可選的**——接了事就得回終局狀態。

## 並發假設（先確認這三條成立）

| 假設 | 意思 | 不成立會怎樣 |
|------|------|-------------|
| **單一收件 agent** | 一個 `inbox/` 只有一個 agent 在收 | 兩個 agent 同時收會重複辦同一封、或搶著 `mv` 進 `done/` |
| **單機、同一檔案系統** | 寄信＝往對方資料夾寫檔，兩邊看得到同一個路徑 | 跨機要先靠 git／同步工具把檔案送到，本包不管傳輸 |
| **沒有鎖，只有慣例** | 信檔名帶時間戳＋寄件者，**多個寄件者同時投遞也安全**；獨佔資源另外用 `mkdir` 鎖 | 不照 [resources](workflows/resources.md) 取鎖就搶資源，兩邊觀測都不可信 |

## 和內建即時通道的分工

| | agent 工具內建的即時通道（例：Claude Code 的 SendMessage / ListAgents）| 本包 |
|---|---|---|
| 通道 | **快**：同機、同時在線的 agent 即時對話 | **慢**：寫一個檔就走人 |
| 對方要在線嗎 | 要 | 不用，下次開機才讀也行 |
| 跨機 / 跨時間 | 不行 | 行（信是檔案，跟著 repo 走）|
| 留得下來嗎 | 不留 | 進版控，日後 `git log` 查得到 |
| **資源鎖** | 內建通道沒有 | `mkdir` 原子鎖＋固定取得順序 |
| **領地登記** | 內建通道沒有 | claims 表：一個目錄同時只准一條線寫 |

沒有內建即時通道的工具（多數 coding agent 直接讀 AGENTS.md，例：Codex CLI、Gemini CLI）就整包用本包——信是檔案，不依賴任何工具功能。**同機、對方正開著、工具也有即時通道 → 用那個通道。** 跨機、跨時間、要留在版控裡，或要管資源與領地 → 用本包。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.multi-agent.md](WORKFLOWS.multi-agent.md) | 派發表片段（貼進專案的 `WORKFLOWS.md`）|
| [AGENTS.multi-agent.md](AGENTS.multi-agent.md) | 開場 bullet 片段（貼進專案的 `AGENTS.md`「開場與入口」）|
| [INDEX.multi-agent.md](INDEX.multi-agent.md) | 佈局表列片段（貼進專案的 `INDEX.md`「Repo 佈局」）|
| [workflows/inbox/](workflows/inbox/README.md) | 通訊工作流：流程、[協議](workflows/inbox/PROTOCOL.md)、[醒鐘策略](workflows/inbox/wake-policy.md)、[身份簿](workflows/inbox/ROSTER.md)、信件模板 |
| [workflows/team-model.md](workflows/team-model.md) | 誰來做：角色三層、聰明度分級、選人判準（子頁 [context](workflows/team-model/context.md)／[speed](workflows/team-model/speed.md)／[plans](workflows/team-model/plans.md)）|
| [workflows/resources.md](workflows/resources.md) | 獨佔資源鎖：`mkdir` 鎖、取得順序、限流、資源表 |
| [workflows/dispatch/](workflows/dispatch/README.md) | 派線工作流（資料夾型）：入口 [README](workflows/dispatch/README.md)＝流程／六條最容易錯的／兩層派線／領地表 |
| ↳ [dispatch/driving-cli-agents.md](workflows/dispatch/driving-cli-agents.md) | 啟動、驅動、監看一條外部 CLI agent 線，與收線七步 |
| ↳ [dispatch/lessons.md](workflows/dispatch/lessons.md) | 派線踩過的坑：預掃範圍、線推翻交接書、交接書自相矛盾、整檔改寫 |
| [workflows/TEMPLATE.handoff.md](workflows/TEMPLATE.handoff.md) | 交接書骨架（驗收條數寫死）|
| [tools/](tools/) | 單一收件匣：`inbox_send.sh`（原子投遞）、`inbox_read.sh`（唯讀輪詢）；五通道升級後才需要的：`inbox_mail.sh`（點對點／團隊／主題／`--up` 上游路由）、`inbox_poll.sh`（輪詢個人信箱＋團隊信箱＋訂閱主題＋自己的 orders，含 `--wait` 醒鐘）、`inbox_team.sh`（開團隊／加人／收線）、`notify_watch.sh`（長駐監看 `new/`）、`test_inbox.sh`（腳本自測）；`hook-settings-snippet.json`（hook 範例，Claude Code 格式）|
| `inbox/`、`inbox/done/` | **放信處**（空資料夾）：頂層＝未處理、`done/`＝已處理 |

## 怎麼合進 kernel

```sh
tools/wf-init.sh --target <專案> --flavor multi-agent
```

腳本做四件事：`workflows/` 底下整包落進專案 `workflows/`；`inbox/`（含 `done/`）與 `tools/` 落在**專案根**；三個片段貼進 `AGENTS.md` / `WORKFLOWS.md` / `INDEX.md` 的插入點；非侵入式佈局時改寫連結。

`inbox/` 與 `tools/` **一律留在專案根**，非侵入式佈局（其餘收進 `wf/`）也一樣——inbox 是給外部 agent 用的對外介面，位置要好猜；腳本要能被 hook 與別的 agent 直接呼叫。

通用步驟（含填 `{{}}`、處理〔模板說明〕、收尾 lint）見 [IMPORT.md](../../IMPORT.md)。`hook-settings-snippet.json` **要不要啟用由使用者決定**，本模板不會自動改任何工具設定檔。

## 版控取捨

預設**全部進版控**（最簡單，信與交接書都查得回）。信量大到吵時，改成只 commit 已處理的：

```gitignore
# 只有處理完的信進版控
/inbox/*.md
!/inbox/done/
/inbox/.inbox-send.*
```

交接書與 claims、ROSTER **一律進版控**——它們是「誰負責什麼」的證據，不是流水訊息。

## 移除本包要動的地方

| 檔案 | 動作 |
|------|------|
| `inbox/`（專案根）| 整個刪掉（先確認頂層沒未辦的信）|
| `tools/inbox_send.sh`、`tools/inbox_read.sh`、`tools/inbox_mail.sh`、`tools/inbox_poll.sh`、`tools/inbox_team.sh`、`tools/notify_watch.sh`、`tools/test_inbox.sh`、`tools/hook-settings-snippet.json` | 刪掉；若曾把 hook 合進工具設定檔（Claude Code 為例：`settings.json`），一併移除那段 |
| `workflows/inbox/`、`workflows/resources.md`、`workflows/dispatch/`、`workflows/team-model.md`＋`workflows/team-model/`、`workflows/TEMPLATE.handoff.md` | 刪掉（只移除其中一個工作流就刪對應那幾個）|
| `WORKFLOWS.md` | 刪「multi-agent flavor」表裡對應的列；整包移除就刪整節 |
| `AGENTS.md` | 刪「開場與入口」裡 `ls inbox/*.md` 那行 bullet |
| `INDEX.md` | 刪「Repo 佈局」表裡 `inbox/` 與 `tools/` 那兩列 |
