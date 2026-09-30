# node：資料夾、任務與一格 tick

← [共用約定](README.md)｜行為正本：[inst](../base/inst.md)、[tick](../tick.md)、[設定](../agent/configuration.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-200．資料夾布局〔建議預設，未拍板〕

根目錄的正規化絕對路徑就是 node id；標準配備的 git 走完整路線時，每個 node 是一個 git repo（沒有 git 時照 [B-632](../tick.md)）。以下名稱固定，其他內容按任務需要才建，不預建空表。kernel／agent 是裝了哪些任務的角色，不另設角色欄位。

| 路徑 | 用途／git |
|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑本 node 的 inst；追蹤；選檔順序依[inst 目標](../base/inst.md#inst-目標檔案或資料夾) |
| `.aos/tasks.json` | P-202 的任務註冊表；追蹤 |
| `config/` | 任務使用的正式設定；追蹤，領域格式由使用它的任務定義 |
| `state/` | 已消費收件、請求、結果與必要進度；追蹤，子結構由各協議篇定義 |
| `requests/`、`responses/` | node 根目錄的外部 JSON-RPC 請求／回應收件區；兩格都 ignore，各含發布用 `.tmp/`；細節由 messages 篇定義 |
| `work/` | 任務的暫存工作進度；ignore |
| `.aos/jobs/<id>/` | 替成員跑工具、打 LLM 的 once 工作；ignore |
| `.aos/attention/` | 本 node 的待處理事項，含 daemon 發現的 node 問題；ignore |
| `.aos/summary/` | 給上層讀的摘要；summary.json 追蹤、published.json ignore，見 P-307 |
| `.aos/outbox/` | 待 tick 投出的請求／回應；追蹤，見 P-206 |
| `.aos/alarms/` | 已投出、設了鬧鐘的待查紀錄；ignore，見 P-206 |
| `.aos/tick.lock` | 〔第十九批〕核心的鎖檔（[B-602](../tick.md)）；ignore |
| `.aos/tick-blocked` | 〔第十九批〕標準配備的擋板檔，見 P-205；ignore |
| `.aos/journal/` | 〔第十九批〕git 備援的檔案日誌（[B-632](../tick.md)），見 P-205；ignore |
| `.aos/runner-stderr.log` | 〔第十七批，暫定〕runner 診斷，daemon 每格覆寫；ignore，輪替以後再定（[P-109](daemon.md)） |
| `public/` | 可供其他 node 存取的共用空間；是否追蹤由內容決定 |
| `.gitignore` | 至少含 `/requests/`、`/responses/`、`/work/`、`/.aos/jobs/`、`/.aos/attention/`、`/.aos/alarms/`、`/.aos/tick.lock`、`/.aos/tick-blocked`、`/.aos/journal/`、`/.aos/runner-stderr.log`、`/.aos/summary/published.json`；追蹤 |

〔第十九批〕鎖檔是 `.aos/tick.lock`，不在 git 管理目錄（[B-602](../tick.md)）。git 管理目錄以 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾；巢狀 tick 的排除寫在它的 `info/exclude`（[B-628](../tick.md)）。待處理事項放 `.aos/attention/`，不隨 group 還原，見 [ops](ops.md)。

〔使用者方向 2026-09-29，裁定「收件分兩格」〕請求在被問者的 `requests/<id>.json`，回應在發問者的 `responses/<id>.json`。回應仍投回發問者家，不改成由發問者去對方家取。

登記資料夾時先找 `.aos/inst.json`、沒有再找 `inst.json`，base 是 node 根；〔第十九批〕掛載行程的目標可以指定單檔 inst（[B-613](../daemon.md)、[P-118](daemon/channel.md)），base 是該檔所在資料夾。正本見[inst 目標](../base/inst.md#inst-目標檔案或資料夾)。不跑 `aos-tick` 就不必有本節完整布局。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

[node-inst.schema.json](schemas/node-inst.schema.json) 驗 [inst 正本](../base/inst.md) 的原始結構；引用內容、循環、選項值及展開後型別仍由 runner 驗證。`_metainfo` 沿第 1 版，不加 version；未知頂層／metainfo／選項額外鍵依 inst 忽略，是 P-002 的例外。

`user` 只准帳號或非負 UID，省略／空字串繼承，不吃指示詞。授權、切身分及整份 `$ref` 的身分核對依 [daemon P-108～110](daemon.md)；125／126／127 與 exit 的訊號編碼依正本，不改成 RPC 錯誤。

[正例](examples/node/inst.minimal.valid.json) 跑 aos-tick；[反例](examples/node/inst.user_directive.invalid.json) 的 user 指示詞不合法。

## P-202．任務註冊表〔建議預設，未拍板〕

檔案只用 `.aos/tasks.json`，schema：[node-tasks.schema.json](schemas/node-tasks.schema.json)。形狀為 `{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}`，順序只看 tasks 陣列位置。每項是 inst 的超集：inst 加以下欄位，也可用整份 `$ref`；指示詞、串流、cwd、envs 依 inst 展開，base 是 node 根。順序、類別、`methods` 的意思與載入檢查以 [B-620](../tick.md) 為正本；〔第十九批〕核心只看 `id` 與 inst 部分，其餘欄位由標準配備讀。

| 欄位 | 約束 |
|---|---|
| `id` | 共用 `ID`；本表唯一 |
| `kind` | `system`、`kernel`、`agent`、`custom`；〔暫定，第十八批〕或自訂的「類別.名稱」，類別限 `kernel`／`agent`／`custom`，名稱是小寫英數與 `_`、`-`（例如 `agent.review`）。先 system，中段 kernel／agent 可交錯，最後 custom；自訂種類照點前的類別排 |
| `group` | 可省，共用 `ID`；相同名稱必須連續；省略是這一項自成一組，與任何具名組不同 |
| `needs` | 可省，預設空陣列；不重複的任務 ID，只能指向本表前項 |
| `methods` | 可省，預設空陣列；〔第十七批〕本任務處理的檔案請求 method（如 `agent.say`）。同一 method 只能由一項任務宣告 |
| `user` | 〔第十九批，撤永遠禁止〕可省，照 [inst](../base/inst.md) 的 `user`；省略用該 node 的執行帳號，帶了由標準配備的切換使用者落實（[B-620](../tick.md)） |

〔使用者方向 2026-09-30，第十九批〕`kind:system` 留給標準配備（[B-626](../tick.md)）；kernel、agent、custom 類任務的逾時與取消延後（[P-008](README.md#p-008)）。

沒人宣告的 method 由標準配備的收件回 -32601（[B-623](../tick.md)），格式：原件複製到 `state/messages/requests/<id>.json`，錯誤回應用 -32601、`data.code:"method_not_found"`、`retryable:false`，放 `.aos/outbox/responses/<id>.json`，提交訊息見 P-205。`tasks` 可以是空陣列。

範例：最小 [正例](examples/node/tasks.minimal.valid.json) 登記普通程式；〔第十九批〕[帶 `user` 的正例](examples/node/tasks.user.valid.json) 讓一項任務用別的帳號跑。[methods 正例](examples/node/tasks.methods.valid.json) 宣告一個 method；[反例](examples/node/tasks.methods-duplicate.invalid.json) 是同一任務內重複宣告，schema 擋得到；跨任務重複 schema 驗不到，由標準配備載入時驗。[自訂種類正例](examples/node/tasks.custom-kind.valid.json) 用 `agent.review`；[反例](examples/node/tasks.custom-kind.invalid.json) 想自訂 `system.x`，不接受。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

完整 argv：`aos-tick [--node <node>] [--check]`。〔使用者方向 2026-09-30，第十九批〕省略 `--node` 就用目前目錄；`<node>` 可以是資料夾，也可以是它的 `.aos/inst.json` 或 `inst.json` 路徑，一律正規化成資料夾（[B-602](../tick.md)），tick 在那裡跑，cwd 就是管轄區；指定時必須是 P-002 的 node id，不向父目錄猜找 repo。不看自己在哪個 cgroup（撤第十八批的框外拒跑，[B-627](../tick.md)）。以資料夾為執行目標時，inst 只需 `{"argv":["aos-tick"]}`，預設 cwd 正好是 node 根；若直接執行 `.aos/inst.json` 檔，base 不同，須明寫 `cwd:".."` 或 `--node`。tick 本身不找 inst。

`--check` 只做[全掛檢查](../tick.md)（B-630）：不取鎖、不跑任務，stdout 每塊一行 `<元件>=full|fallback`，缺的另印 `missing=<項目>`；結束碼 0 全掛（含走備援）、1 沒全掛、2 用法錯。

| 介面 | 約定 |
|---|---|
| tick 的 stdin | 一般不讀；inst 預設 `/dev/null`。〔第十九批〕例外是沒全掛時的 y／n 確認：stdin 與 stderr 都是終端機才讀一行（[B-630](../tick.md)） |
| tick 的 stdout | 原樣轉送任務 stdout，不另混入成功 JSON |
| tick 的 stderr | 任務 stderr 原樣轉送；tick 自己另印 `code: 說明`，有需要附 task id、退出碼或 signal |
| 讀寫 | 核心讀 `.aos/tasks.json`、持鎖；標準配備負責提交（或檔案日誌）、還原、投件、消費原件清理；任務直接讀寫檔案 |
| 身分 | 任務預設沿用 tick 的有效 UID、群組與資源範圍；〔第十九批〕帶了別的 `user` 的任務由標準配備的切換使用者經 helper 以那個帳號開，同樣繼承鎖 fd（[B-620](../tick.md)、[B-609](../daemon.md)）。tick 自己不切 UID，直接呼叫也不會替你取得 inst 的身分 |
| 任務 cwd／argv | 依本項 inst 展開後執行；cwd 未給時為 node 根 |
| 任務 stdin | 預設 `/dev/null`；可用本項 inst 的 stdin 重導向 |
| 任務 stdout／stderr | 依 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不解析文字當完成證據 |
| 任務環境 | 繼承 tick 環境（含 daemon 開的格才有的通道變數，[B-612](../daemon.md)），加 `AOS_NODE_DIR`（node id）與 `AOS_TICK_LOCK_FD`（鎖 fd 號碼，[B-602](../tick.md)），再依 inst 套用 envs；都不是授權證據 |

任務直接開檔讀設定；改設定的時機與「tick 裡不改 config/」的軟性原則見 [A-102](../agent/configuration.md)。

無設定需求的程式沒有必讀的環境變數或必寫的回應封套；`true`、腳本與既有程式都能直接當任務。key 不由 tick 放入 argv 或任務環境；daemon／runner 的環境來源照 [身分篇](../base/identity-resources.md)，inst 的 `envs` 沿正本。

鎖（`.aos/tick.lock`、`AOS_TICK_LOCK_FD`）的行為以 [B-602](../tick.md) 為正本；每個任務一層 `task-<序號>` 框與後代清空以 [B-202](../base/execution.md) 為正本（沒有 cgroup 時 [B-631](../tick.md)），命名見 [B-605](../daemon.md)。

| tick 結束碼 | 屬 | 意思 |
|---|---|---|
| `0` | 核心 | 全部任務成功（含沒有工作／沒有變動）；只表示本格完成 |
| `1` | 核心 | 至少一項（標準配備下是一組）失敗或跳過；需要的還原成功，後續獨立組已照表處理 |
| `2` | 核心 | argv 或任務表不合法，或全掛檢查有終端機時答 n（[B-630](../tick.md)）；尚未開任務 |
| `3` | 標準配備 | 開始處理後發生提交（含檔案日誌）／還原／後代清理等故障；停止後續組，寫擋板檔（P-205） |
| `75` | 核心 | 鎖被占用；本次沒有開任務，也不在程式內重試 |
| `125` | 標準配備 | 格首看到擋板檔，無法開始；沒有開任務 |

父程序以 wait 狀態辨識 tick 被訊號結束，不把 `128+N` 當訊號證據。inst 的文字 `exit` 編碼仍依 P-201。kernel、agent、custom 類任務的逾時與取消延後（[P-008](README.md#p-008)）。

## P-204．成敗、group 與 needs〔使用者方向 2026-09-29〕

group／needs 屬標準配備，順序、提交與失敗跳過完全依 [B-621](../tick.md#b-621group-與-needs)。tick 以可信 wait 的正常退出 0 判定任務成功；exec 失敗、非零或訊號皆失敗，不能把普通程式的 125 猜成沒跑。「沒事做」可不改檔回 0；在途工作存領域狀態，不用特殊退出碼當排程訊號。

## P-205．git 提交與恢復〔建議預設，未拍板〕

行為正本：基線、範圍、還原、落盤與故障停格依 [B-622](../tick.md)，合併提交與 submodule 依 [B-625](../tick.md)，沒有 git 時的檔案日誌依 [B-632](../tick.md)。本條只定格式。

- **git 參數**：aos 每次呼叫 git 都帶 `-c core.fsync=committed,reference`（最低 git 2.36）；作者用 repo 設定，不互動、不執行 git hooks。
- **commit 訊息**：`aos-tick group <first_task_id>..<last_task_id>`，單項兩端相同；替沒人宣告的 method 回 -32601 那次提交（[B-623](../tick.md)）用 `aos-tick unclaimed`；〔第十九批〕從備援換回 git 的第一個提交用 `aos-tick adopt`。
- **擋板檔**〔第十九批從 git 管理目錄搬出，沒有 git 也要用〕：`.aos/tick-blocked`，內容是 UTF-8 原因。
- **完成紀錄**〔第十九批，建議預設〕：`.aos/journal/<seq>.json`，`seq` 是從 1 起的十進位序號、補零到 12 位；內容 `{"version":1,"seq":N,"at_ms":毫秒,"tasks":[{"id":…,"exit":碼}],"consumed":[相對路徑…],"outbox":[相對路徑…]}`，`consumed` 列本組的消費副本、`outbox` 列本組的待送檔。schema：[node-journal](schemas/node-journal.schema.json)，[正例](examples/node/journal.minimal.valid.json)、[反例：seq 為 0](examples/node/journal.seq-zero.invalid.json)。投出後的待送副本放 `.aos/journal/sent/{requests,responses}/<id>.json`，失敗組的放 `.aos/journal/discarded/<組開始的 at_ms>/{requests,responses}/<id>.json`。

## P-206．收件與派送的提交邊界〔使用者方向 2026-09-29〕

行為正本：收件 [B-623](../tick.md)（Q1）、派出與鬧鐘 [B-624](../tick.md)（Q2）。本條只定檔案格式。

- **消費副本**：收件原件逐 byte 複製到追蹤的 `state/messages/{requests,responses}/<id>.json`；領域狀態引用這份，不另做通用收據。
- **待送封套**：`.aos/outbox/{requests,responses}/<id>.json`，schema [msg-outbox](schemas/msg-outbox.schema.json)，內容 `{"version":1,"target_node":"/目標","message":{...},"alarm_ms"?:N}`；message 是完整 JSON-RPC，ID 須與檔名相同。
- **`alarm_ms`**（可省）：正整數毫秒，從投出那一刻算。
- **`channel`**、**`urgent`**〔第十九批，可省，預設 false〕：`channel:true` 表示本格有通道時改經 daemon 送，只用在 `.aos/outbox/requests/`，回應寫了也照檔案投件；`urgent:true` 是急件，只在 `channel:true` 時可寫。行為見 [B-624](../tick.md)。
- **鬧鐘紀錄**：〔第十六批〕ignored 的 `.aos/alarms/req-<id>.json`（請求）或 `resp-<id>.json`（回應），因為請求和回應可以同 ID（P-301），分開才不撞名；記目標、投出的檔案路徑與到期時間。
- **stderr 診斷行**：`target_not_node: <node> <id>`、`target_not_writable: <node> <id>`、`request_not_handled: <node> <id>`。
- 工作與 LLM 的固定材料依據留 `state/work/<attempt_id>/`；其餘領域路徑見所屬篇。

範例：[最小封套](examples/messages/outbox.minimal.valid.json)、[設了鬧鐘的封套](examples/messages/outbox.alarm.valid.json)、[反例：`alarm_ms` 為 0](examples/messages/outbox.alarm-zero.invalid.json)、[走通道的急件](examples/messages/outbox.channel-urgent.valid.json)、[反例：沒走通道卻標急件](examples/messages/outbox.urgent-no-channel.invalid.json)。

## P-207．加入普通設定與重要設定手改〔建議預設，未拍板〕

argv：`aos-config-add [--node <node_dir>] --from <source> --to <target>`；省略 node 用 cwd。source 是任意可讀路徑，相對呼叫 cwd；target 是 node/config/ 內檔案，相對 node、不准 ..／symlink 逃出。用呼叫者帳號，無自訂環境；stdin 不讀，stdout 成功印 target＋LF，stderr 印 `code: 說明`。提交訊息 `aos-config-add <target>`。

退出：0 已提交／無變動；2 參數／路徑／JSON 不合；75 busy；125 前置失敗（未寫目標）；1 寫入失敗且已還原；3 commit／還原故障，依 P-205 擋新格。

〔第十九批依方案 A 縮短〕鎖、寫入與提交流程（含沒有 git 時只做原子替換）以及重要設定的手改流程，以 [A-102](../agent/configuration.md) 為正本。

## P-208．收件區權限〔建議預設，未拍板〕

〔第十九批依方案 A 縮短〕誰要開哪些權限、建立 node 時怎麼核對 LLM 與工具路線、kernel 對成員的觀察權，以 [B-506](../base/transport.md) 為正本；本條只列權限落點。

| 對象 | 落點 |
|---|---|
| daemon | `.aos/attention/` 的寫權 |
| node 帳號 | 根路徑可遍歷；repo 讀寫；`requests/`、`responses/` 可清理 |
| 投件者 | 必要父目錄的 traverse；`requests/` 或 `responses/` 及其 `.tmp/` 的寫與遍歷 |
| 只讀摘要的上層 | `.aos/summary/` 只授 traverse、`published.json` 只授 read（[P-307](messages.md)） |

共享群組、setgid 目錄與交出框用 helper 的固定動作 `group_create`、`group_add_member`、`chgrp`、`cgroup_delegate`（參數見 [P-107](daemon/provision-and-runner.md)）。

## P-209．待決與跨篇

見 [README P-008](README.md#p-008)。

## P-210．預設範本與恢復前驗證〔主編補〕

`aos node new N --template kernel` 的完整 `.aos/tasks.json`、設定與頂層建立順序由 [kernel 任務篇](kernel-tasks.md) 定；agent 範本由 [agent P-715](agent-tasks.md) 定。kernel 的唯讀驗證 argv 是 `aos-kernel-check --node N --validate-only`。

〔第十九批依方案 A 縮短〕建立與 `aos node resume` 恢復前驗證的步驟以 [A-102](../agent/configuration.md) 與 [H-036](../cli/walkthrough.md) 為正本；日常檢查與待辦標完成依 [ops P-609](ops.md)。
