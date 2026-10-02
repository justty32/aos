# 人手打的操作 CLI：出事時看哪裡

← [CLI 入口](README.md)｜[指令總表](commands.md)｜[規格入口](../README.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - 停格檔 `tick/stop`：第十六批改名 `tick/tasks-blocked`（每項任務之前看、整格最後由 tick 刪；紀錄欄位 `stopped_after` 改 `blocked_before`）；擋板檔 `tick-blocked` 只看存不存在、不讀原因、存在就靜靜回 0（[B-620](../settled/tick.md)、[B-636](../settled/tick/tasks-blocked.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit/08-1001-node模組與統一更新.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

## H-037．除錯指南〔使用者方向 2026-09-30，第十八批；寫法為工程預設〕

本頁只教人「從哪裡查起」，不定新規則；各處寫什麼、何時寫，以連到的條文為準。想一次看完，用 `aos work trace ID`（[H-004](commands.md) 第 55 列），它會照下面的站自動串起來，讀不到的站標「看不到」。〔第十九批〕懷疑「標準配備走的是完整路還是備援」，先跑 `aos node check`（第 58 列）；每格 stderr 的 `standard: cgroup=… git=…` 也印同樣的資訊（[B-630](../settled/deferred/git.md)）。

### 六個地方

| # | 地方 | 怎麼看 | 裡面有什麼 | 規則在哪 |
|---|---|---|---|---|
| 1 | daemon 的即時狀態 | `aos node show T`、`aos node ls`（含掛載行程的診斷）、`aos daemon info` | 有沒有登記、paused、running、pending；`registration_id`；`mount`（是不是掛載行程）、`parent_override`（上層是不是覆蓋出來的）；最近一格 `last_tick`（outcome、exit_code、`tick_seq`）；掛載行程（原 once）做完的診斷（會自動淘汰，也可 `aos mount clear`） | [B-601](../settled/deferred/daemon/runtime.md)、[B-610](../settled/deferred/daemon/channel.md)、[P-106](../settled/deferred/protocol/daemon/registration.md) |
| 2 | 待辦事項 | `aos attend ls`／`show`；原檔在 node 的 `.aos/attention/{open,done}/` 與 daemon 的 `state_dir/attention/` | 設定壞了、runner 沒開始、tick 壞掉停格、程序清不乾淨、helper 不見、標準配備本身跑不起來（`standard-incomplete`）等要人處理的事 | [S-405](../scheduling/operations.md)、[P-601](../protocol/ops.md) |
| 3 | node 的 git 歷史 | `aos node log N [--all]`、`git -C N show <OID>` | 每格每組提交（`aos-tick group …`）、標準配備回 -32601 的提交（`aos-tick unclaimed`）、維護提交；已消費的收件原件在 `state/messages/`，待送封套在 `.aos/outbox/`。沒有 git 的 node 沒有歷史，改看 `.aos/journal/`（完成紀錄，已投出的副本在 `sent/`，失敗組的在 `discarded/`，[B-632](../settled/deferred/git.md)） | [B-622](../settled/deferred/git.md)、[P-205](../settled/protocol/tick.md)、[P-206](../settled/protocol/tick.md) |
| 4 | tick 擋板與停格 | `.aos/tick-blocked`；`last_tick` 的 exit_code 3 | 提交／還原故障的原因；看到擋板時下一格回 125、不碰工作樹，要人修好、移除擋板 | [P-203](../settled/protocol/tick.md)、[B-607](../settled/deferred/daemon/registration.md) |
| 5 | 工作區 | 追蹤的 `state/work/<前綴>-<attempt_id>/`；ignored 的 `.aos/jobs/<前綴>-<attempt_id>/`（`inst.json`、`request.json`、`result.json`、`usage.json`、`launch-started`、`stdout.bin`／`stderr.bin`）與 `inst.json.err` | 工作材料、完整結果、用量；掛載行程單檔的 `.err` 表示 runner 根本沒啟動；有 `launch-started` 卻沒結果，就是 unknown，不會自動重跑 | [P-402](../protocol/work.md)、[S-401](../scheduling/operations.md) |
| 6 | 投件與診斷輸出 | 收件區 `requests/`、`responses/`；`.aos/alarms/`；`.aos/runner-stderr.log`；daemon 自己的 stdout／stderr | 對方還沒取走的原件；設了鬧鐘的待查紀錄；tick 印的 `request_not_handled`、`target_not_writable` 等投件錯誤、`standard: …` 那一行與任務 stderr（每格覆寫）；daemon 寫不進 node 時的警告 | [B-624](../settled/deferred/mq.md)、[P-206](../settled/protocol/tick.md)、[P-109](../settled/deferred/protocol/daemon/provision-and-runner.md) |

### 三套 ID 怎麼對

| ID | 誰配、長什麼樣 | 出現在哪 | 怎麼接到下一套 |
|---|---|---|---|
| 請求 ID（RPC id） | 發件者配，同 ID 同內容才算重送 | 檔名：`requests/<id>.json`、`responses/<id>.json`、`state/messages/{requests,responses,meta}/<id>.json`、`.aos/outbox/…/<id>.json`、`.aos/alarms/req-<id>.json`／`resp-<id>.json`；欄位：agent 的 `input_id`（原 `agent.say` 的 id）、回話的 `in_reply_to`、取消的 `request_id` | 工作材料 `state/work/<前綴>-<attempt_id>/request.json` 與 meta 記著它屬於哪個請求 ID；一個請求可以有多次嘗試（例如 429 重試） |
| attempt ID | 配出這次嘗試的 node 配；目錄名前面加那個 node 路徑的 sha256 前 16 碼（[P-402](../protocol/work.md)），檔案內容裡的 `attempt_id` 不加 | `state/work/<前綴>-<attempt_id>/`、`.aos/jobs/<前綴>-<attempt_id>/`；掛載行程（once）的 node_id 就是 `.aos/jobs/<前綴>-<attempt_id>/inst.json`；work-result 與用量檔的 `attempt_id` | 拿掛載行程的 node_id 去 `aos node show` 或 `aos node ls` 找那格的 `last_tick` |
| 格的識別：`boot_id`、`registration_id`、`tick_seq` | daemon 配：每次啟動一個 `boot_id`、每次登記一個 `registration_id`（重啟後重新登記也換新）、同一次登記內每開一格 `tick_seq` 加 1 | `aos daemon info`；`node.wake` 的回應；`node.show`／`node.ls` 最上層的 `registration_id` 與 `last_tick.tick_seq`；kernel 的 `state/kernel/schedule.json` | 同一格的提交在 `aos node log` 裡；一格可以沒有或有多筆提交。`registration_id` 相同、`tick_seq` 比 wake 時大且 outcome 不是 running，才是「新的一格做完了」（[B-607](../settled/deferred/daemon/registration.md)） |

### 常見症狀從哪查起

| 症狀 | 先看 | 再看 |
|---|---|---|
| 說了話沒回 | 1 的 `last_tick`：對方有沒有被叫醒、這格 exit_code | 6 的收件區原件還在不在；3 的 `state/messages/`；2 有沒有事項 |
| 投件後石沉大海 | 6 的 `runner-stderr.log`（`target_not_writable`、`request_not_handled`） | 發件 node 的 `.aos/outbox/` 還有沒有；有設鬧鐘就看 `.aos/alarms/` |
| 工具或 LLM 結果一直沒回 | 5 的 `result.json`、`inst.json.err`、`launch-started` | 1 的掛載診斷；結果不明就是 unknown，照 [S-401](../scheduling/operations.md) 放著 |
| node 不再開格 | 4 的擋板；1 的 paused | 2 的事項；`aos node log` 最後一筆 |
| 設定改了沒生效 | 2 的 `config_invalid` 事項；`aos agent config check` | 3 的提交有沒有進去；daemon 設定要看 [B-608](../settled/deferred/daemon/reload.md) 是否要重開 |
| 想經通道送訊息、掛行程，卻報 `no_channel` 或被拒 | 那一格的環境有沒有 `AOS_DAEMON_SOCKET` 與 `AOS_TICK_TOKEN`：只有 daemon 開的格才有，人手、cron 跑的沒有；任務的 `envs` 用了 `clear` 也會被清掉（[B-612](../settled/deferred/daemon/channel.md)） | `token_invalid`：拿了上一格的憑證、或 daemon 重啟過；`forbidden`：寄件帳號對收件 `requests/` 沒寫權，或覆蓋上層只有一方同意；`mailbox_full`：收件方一直沒取，改走檔案收件（[B-614](../settled/deferred/daemon/messaging.md)） |
| 標準配備是不是在走備援 | `aos node check`；tick stderr 的 `standard: cgroup=… git=…` | cgroup 備援下沒有總量上限與 OOM 判定、後代收不乾淨；git 備援下沒有還原與歷史（[B-631](../settled/deferred/cg.md)、[B-632](../settled/deferred/git.md)）；想走完整路，cgroup 首推 `systemd-run --user --scope -p Delegate=yes`（[B-605](../settled/deferred/daemon/cgroup.md)） |
