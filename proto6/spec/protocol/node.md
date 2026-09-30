# node：資料夾、任務與一格 tick

← [共用約定](README.md)｜行為正本：[inst](../base/inst.md)、[tick](../tick.md)、[設定](../agent/configuration.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-200．資料夾布局〔建議預設，未拍板〕

根目錄的正規化絕對路徑就是 node id。〔使用者方向 2026-09-30，第二十批進行順序〕本輪假設沒有 git（[B-632](../tick.md)）；下一步納入 git 時每個 node 是一個 git repo（草稿 [B-630](../tick.md)、P-205）。下表的「追蹤／ignore」是給下一步 git 用的分類，本輪只當作「受管狀態／暫存」的區分。以下名稱固定，其他內容按任務需要才建，不預建空表。kernel／agent 是裝了哪些任務的角色，不另設角色欄位。

| 路徑 | 用途／git |
|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑本 node 的 inst；追蹤；選檔順序依[inst 目標](../base/inst.md#inst-目標檔案或資料夾) |
| `.aos/tasks.json` | P-202 的任務註冊表；追蹤 |
| `config/` | 任務使用的正式設定；追蹤，領域格式由使用它的任務定義 |
| `state/` | 已消費收件、請求、結果與必要進度；追蹤，子結構由各協議篇定義 |
| `requests/`、`responses/` | node 根目錄的外部 JSON-RPC 請求／回應收件區；兩格都 ignore，各含發布用 `.tmp/`；細節由 messages 篇定義 |
| `work/` | 任務的暫存工作進度；ignore |
| `.aos/jobs/<id>/` | 替成員跑工具、打 LLM 的 once 工作；ignore。〔第二十批〕`aos-as` 的暫存 inst 也放這裡（`as-<seq>-<pid>.json`，P-212） |
| `.aos/attention/` | 本 node 的待處理事項，含 daemon 發現的 node 問題；ignore |
| `.aos/summary/` | 給上層讀的摘要；summary.json 追蹤、published.json ignore，見 P-307 |
| `.aos/outbox/` | 待 tick 投出的請求／回應；追蹤，見 P-206 |
| `.aos/alarms/` | 已投出、設了鬧鐘的待查紀錄；ignore，見 P-206 |
| `.aos/tick.lock` | 〔第十九批〕核心的鎖檔（[B-602](../tick.md)）；ignore |
| `.aos/tick/` | 〔第二十批〕核心的結束碼紀錄 `current.json`、`last.json` 與停格檔 `stop`（[B-633](../tick.md)、[B-620](../tick.md)），見 P-213；ignore，不隨還原、不被清理 |
| `.aos/tick-blocked` | 〔第十九批〕擋板檔；〔使用者方向 2026-09-30，第二十批〕本輪就啟用：擋之後各格，核心看到就不跑、daemon 看到就不開格（[B-620](../tick.md)、P-213）；任務或人手建、人手刪；ignore |
| `.aos/runner-stderr.log` | 〔第十七批，暫定〕runner 診斷，daemon 每格覆寫；ignore，輪替以後再定（[P-109](daemon.md)） |
| `public/` | 可供其他 node 存取的共用空間；是否追蹤由內容決定 |
| `.gitignore` | 至少含 `/requests/`、`/responses/`、`/work/`、`/.aos/jobs/`、`/.aos/attention/`、`/.aos/alarms/`、`/.aos/tick.lock`、`/.aos/tick/`、`/.aos/tick-blocked`、`/.aos/runner-stderr.log`、`/.aos/summary/published.json`；追蹤 |

〔第十九批〕鎖檔是 `.aos/tick.lock`，不在 git 管理目錄（[B-602](../tick.md)）。git 管理目錄以 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾；〔下一步納入 git 時補〕巢狀 tick 的排除寫在它的 `info/exclude`、存檔點記在 git 管理目錄的 `refs/aos/marks/`（P-205 草稿），都不在工作樹。待處理事項放 `.aos/attention/`，不隨還原，見 [ops](ops.md)。

〔使用者方向 2026-09-29，裁定「收件分兩格」〕請求在被問者的 `requests/<id>.json`，回應在發問者的 `responses/<id>.json`。回應仍投回發問者家，不改成由發問者去對方家取。

登記資料夾時先找 `.aos/inst.json`、沒有再找 `inst.json`，base 是 node 根；〔第十九批〕掛載行程的目標可以指定單檔 inst（[B-613](../daemon.md)、[P-118](daemon/channel.md)），base 是該檔所在資料夾。正本見[inst 目標](../base/inst.md#inst-目標檔案或資料夾)。不跑 `aos-tick` 就不必有本節完整布局。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

[node-inst.schema.json](schemas/node-inst.schema.json) 驗 [inst 正本](../base/inst.md) 的原始結構；引用內容、循環、選項值及展開後型別仍由 runner 驗證。`_metainfo` 沿第 1 版，不加 version；未知頂層／metainfo／選項額外鍵依 inst 忽略，是 P-002 的例外。

`user` 只准帳號或非負 UID，省略／空字串繼承，不吃指示詞。授權、切身分及整份 `$ref` 的身分核對依 [daemon P-108～110](daemon.md)；125／126／127 與 exit 的訊號編碼依正本，不改成 RPC 錯誤。

[正例](examples/node/inst.minimal.valid.json) 跑 aos-tick；[反例](examples/node/inst.user_directive.invalid.json) 的 user 指示詞不合法。

## P-202．任務註冊表〔建議預設，未拍板〕

檔案只用 `.aos/tasks.json`，schema：[node-tasks.schema.json](schemas/node-tasks.schema.json)。形狀為 `{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}`，順序只看 tasks 陣列位置。每項是 inst 的超集：inst 加以下欄位，也可用整份 `$ref`；指示詞、串流、cwd、envs 依 inst 展開，base 是 node 根。順序、類別、`methods` 的意思與載入檢查以 [B-620](../tick.md) 為正本；核心只看 `id`、inst 部分與 `user`，其餘欄位由系統級任務讀。

| 欄位 | 約束 |
|---|---|
| `id` | 共用 `ID`；本表唯一；〔第二十批〕跑的時候放進任務環境 `AOS_TASK_ID` |
| `kind` | `system`、`kernel`、`agent`、`custom`；〔暫定，第十八批〕或自訂的「類別.名稱」，類別限 `kernel`／`agent`／`custom`，名稱是小寫英數與 `_`、`-`（例如 `agent.review`）。〔第二十批〕`system` 標記系統級任務（[B-626](../tick.md)）；只是標記，不驗順序 |
| `methods` | 可省，預設空陣列；〔第十七批〕本任務處理的檔案請求 method（如 `agent.say`）。同一 method 只能由一項任務宣告，跨項重複由收件任務驗（[B-623](../tick.md)） |
| `user` | 〔第十九批，撤永遠禁止〕可省，照 [inst](../base/inst.md) 的 `user`；省略用 tick 的有效帳號。〔使用者方向 2026-09-30，第二十批疑點裁定 6〕帶了而且跟 tick 的帳號不同時那一項回 125、不切帳號；要切帳號在 argv 包 `aos-as`（P-212、[B-620](../tick.md)） |

〔暫定，第二十批〕`group`、`needs` 兩欄撤：前置改用 `aos-needs`（P-204、[B-621](../tick.md)）；組只在有 git 還原時才有意思，下一步納入 git 時再定（草稿：組由存檔點界定，P-205）。舊表還寫著這兩欄時照 P-007 當不認得的欄位忽略，意思也就沒了；要照舊分組或擋前置，改放存檔點、包 `aos-needs`。kernel、agent、custom 類任務的逾時與取消延後（[P-008](README.md#p-008)）。

沒人宣告的 method 由收件任務回 -32601（[B-623](../tick.md)），格式：原件複製到 `state/messages/requests/<id>.json`，錯誤回應用 -32601、`data.code:"method_not_found"`、`retryable:false`，放 `.aos/outbox/responses/<id>.json`，本格由投件任務投出、原件下一格刪（[B-623](../tick.md)）。`tasks` 可以是空陣列。

範例：最小 [正例](examples/node/tasks.minimal.valid.json) 登記普通程式；[帶 `user` 的正例](examples/node/tasks.user.valid.json) 格式照收（跟 tick 帳號不同時那一項回 125）；[包 `aos-as` 的正例](examples/node/tasks.as.valid.json) 用別的帳號跑；[標準任務表範本正例](examples/node/tasks.template.valid.json) 照 [B-629](../tick.md) 本輪（沒有 git）的順序。[methods 正例](examples/node/tasks.methods.valid.json) 宣告一個 method；[反例](examples/node/tasks.methods-duplicate.invalid.json) 是同一任務內重複宣告，schema 擋得到；跨任務重複 schema 驗不到，由收件任務驗。[自訂種類正例](examples/node/tasks.custom-kind.valid.json) 用 `agent.review`；[反例](examples/node/tasks.custom-kind.invalid.json) 想自訂 `system.x`，不接受。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

完整 argv：`aos-tick [--node <node>]`。〔使用者方向 2026-09-30，第十九批〕省略 `--node` 就用目前目錄；`<node>` 可以是資料夾，也可以是它的 `.aos/inst.json` 或 `inst.json` 路徑，一律正規化成資料夾（[B-602](../tick.md)），tick 在那裡跑，cwd 就是管轄區；指定時必須是 P-002 的 node id，不向父目錄猜找 repo。不看自己在哪個 cgroup（[B-627](../tick.md)）。以資料夾為執行目標時，inst 只需 `{"argv":["aos-tick"]}`，預設 cwd 正好是 node 根；若直接執行 `.aos/inst.json` 檔，base 不同，須明寫 `cwd:".."` 或 `--node`。tick 本身不找 inst。〔第二十批〕第十九批的 `--check`（全掛檢查）撤。

| 介面 | 約定 |
|---|---|
| tick 的 stdin | 不讀；inst 預設 `/dev/null` |
| tick 的 stdout | 原樣轉送任務 stdout，不另混入成功 JSON |
| tick 的 stderr | 任務 stderr 原樣轉送；tick 自己另印 `code: 說明`，有需要附 task id、退出碼或 signal；核心自己的代碼有 `config_invalid`、`user_mismatch`、`record_unwritable`、`stopped`（附停格檔裡的原因）、`blocked`（附擋板檔裡的原因） |
| 讀寫 | 核心讀 `.aos/tasks.json`、持鎖、寫 `.aos/tick/` 的紀錄、開格刪殘留的停格檔、每項後查停格檔（P-213）；投件、刪收件原件都是系統級任務的事（[B-629](../tick.md)）；任務直接讀寫檔案 |
| 身分 | 任務沿用 tick 的有效 UID、群組與資源範圍；〔第二十批〕帶了別的 `user` 的那一項回 125，要換帳號包 `aos-as`（P-212）。tick 自己不切 UID，直接呼叫也不會替你取得 inst 的身分 |
| 任務 cwd／argv | 依本項 inst 展開後執行；cwd 未給時為 node 根 |
| 任務 stdin | 預設 `/dev/null`；可用本項 inst 的 stdin 重導向 |
| 任務 stdout／stderr | 依 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不解析文字當完成證據 |
| 任務環境 | 繼承 tick 環境（含 daemon 開的格才有的通道變數，[B-612](../daemon.md)），加 `AOS_NODE_DIR`（node id）、`AOS_TICK_LOCK_FD`（鎖 fd 號碼，[B-602](../tick.md)）、〔第二十批〕`AOS_TICK_RECORD`（`.aos/tick/current.json` 的絕對路徑，寫不進時不設，P-213）；這一項專屬的 `AOS_TASK_ID`（任務表該項 `id` 字串，原樣）與 `AOS_TASK_INDEX`（這一項在 tasks 陣列的位置，十進位，從 0 起）。〔使用者方向 2026-09-30，第二十批命名〕整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`。再依 inst 套用 envs；都不是授權證據 |

任務直接開檔讀設定；改設定的時機與「tick 裡不改 config/」的軟性原則見 [A-102](../agent/configuration.md)。

無設定需求的程式沒有必讀的環境變數或必寫的回應封套；`true`、腳本與既有程式都能直接當任務。key 不由 tick 放入 argv 或任務環境；daemon／runner 的環境來源照 [身分篇](../base/identity-resources.md)，inst 的 `envs` 沿正本。

鎖（`.aos/tick.lock`、`AOS_TICK_LOCK_FD`）的行為以 [B-602](../tick.md) 為正本；每項一框（`aos-cg`）下一步納入 cgroup 時補（草稿 P-211）。

| tick 結束碼 | 意思 |
|---|---|
| `0` | 全部任務成功（含沒有工作／沒有變動）；只表示本格完成 |
| `1` | 至少一項失敗（非零、訊號、回 125 都算），或某項建了停格檔、後面沒跑，或有擋板檔、一項都沒跑也沒寫紀錄（[B-620](../tick.md)） |
| `2` | argv 或任務表不合法；尚未開任務 |
| `75` | 鎖被占用；本次沒有開任務、沒有寫紀錄，也不在程式內重試 |

〔使用者方向 2026-09-30，第二十批疑點裁定 1（改）〕停掉本格靠停格檔 `.aos/tick/stop`，不靠結束碼；任務回什麼碼都只是成功或失敗，沒有特別意思。〔建議預設〕被停下的格回 1：這格沒把表跑完，對呼叫者是「沒全部成功」；停格檔只管本格，所以不另設一個會讓 daemon 誤當成暫停訊號的碼，要知道是不是被停下就讀紀錄的 `stopped_after`。第十九批「標準配備」的 3（提交故障）與 125（格首看到擋板）撤。父程序以 wait 狀態辨識 tick 被訊號結束，不把 `128+N` 當訊號證據。inst 的文字 `exit` 編碼仍依 P-201。kernel、agent、custom 類任務的逾時與取消延後（[P-008](README.md#p-008)）。

## P-204．成敗與 aos-needs〔使用者方向 2026-09-29；第二十批改寫〕

tick 以可信 wait 的正常退出 0 判定任務成功；exec 失敗、非零或訊號皆失敗，不能把普通程式的 125 猜成沒跑。「沒事做」可不改檔回 0；在途工作存領域狀態，不用特殊退出碼當排程訊號；要停掉本格用停格檔（P-203、P-213）。前置的行為以 [B-621](../tick.md) 為正本。

〔建議預設，未拍板〕`aos-needs <前置任務 id…> -- <原指令…>`：普通程式，前置至少一個，`--` 必填。讀 `AOS_TICK_RECORD`，每個前置都在紀錄的 `tasks` 裡而且 `exit:0` 才 exec 原指令，結束碼就是原指令的。stdin、stdout、stderr 原樣交給原指令。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 前置都成功，已 exec 原指令 |
| `2` | 用法錯（沒有前置、少了 `--` 或原指令） |
| `125` | 沒跑：stderr 印 `needs_unmet: <id>`（前置不在紀錄或不是 0）或 `no_record`（沒有 `AOS_TICK_RECORD` 或讀不到） |

## P-205．〔下一步納入〕aos-git：開格、存檔點、收尾

〔使用者方向 2026-09-30，第二十批進行順序〕本條是草稿，**不是現行規則**；下一步把 git 納入時再定。行為草稿：開格與收尾 [B-630](../tick.md)，存檔點與組同在 B-630，管理範圍、落盤與故障 [B-622](../tick.md)，合併提交與 submodule [B-625](../tick.md)，沒有 git 時 [B-632](../tick.md)。本條只定格式。

- **argv**：`aos-git open`、`aos-git mark`、`aos-git close`，都在 node 根（cwd）跑、不收其他參數；三者都是系統級任務（`kind:"system"`）。在 tick 內靠繼承的鎖（B-602）；不在 tick 內時自己取同一把鎖，拿不到回 75。
- **git 參數**：aos 每次呼叫 git 都帶 `-c core.fsync=committed,reference`（最低 git 2.36）；作者用 repo 設定，不互動、不執行 git hooks。
- **commit 訊息**：`aos-tick <seq>`，`seq` 是結束碼紀錄的格數（P-213）；每格最多一個。〔第二十批〕第十九批的 `aos-tick group <first>..<last>`、`aos-tick unclaimed`、`aos-tick adopt` 撤。沒有紀錄時 `close` 不提交（B-630）。
- **存檔點**：暫存提交，記在 git 管理目錄的 `refs/aos/marks/<任務 id>`（任務 id 取 `AOS_TASK_ID`）；不在任何分支上，`close` 用完就刪，`open` 開格先清掉殘留的。
- **擋板檔**〔第十九批從 git 管理目錄搬出，沒有 git 也要用〕：`.aos/tick-blocked`，內容是 UTF-8 原因。
- **stderr 代碼**：`tick_blocked`、`no_git`、`git_failed`（附 git 的錯誤行）、`record_missing`。
- **結束碼**：`0` 成功（`close` 有組失敗、還原成功也是 0；沒 git 時照 B-632 也是 0）；`2` 用法錯；`75` 不在 tick 內又拿不到鎖。看到擋板，或還原、存檔點、commit、刪原件失敗時建停格檔（P-213）、回 1，並寫擋板（看到擋板時不重寫）。

〔第二十批疑點裁定 5〕第十九批的完成紀錄 `.aos/journal/<seq>.json`、`sent/`、`discarded/` 與 `node-journal` schema 撤，由結束碼紀錄取代（P-213、[B-632](../tick.md)）。

## P-206．收件、派送與發摘要〔使用者方向 2026-09-29〕

行為正本：收件 [B-623](../tick.md)（Q1）、派出、鬧鐘與發摘要 [B-624](../tick.md)（Q2）。本條只定檔案格式與 argv。

- **argv**〔第二十批，建議預設〕：`aos-inbox`、`aos-outbox`、`aos-publish`，都在 node 根（cwd）跑、不收其他參數，都是系統級任務。在 tick 內靠繼承的鎖，不在 tick 內自己取同一把鎖、拿不到回 75。結束碼：`0` 成功（含沒事做）；`1` 有件處理失敗（例如發布摘要失敗、投件 I/O 錯），或 `aos-inbox` 看到 `methods` 重複（這時另建停格檔，P-213）；`2` 用法錯。
- **消費副本**：收件原件逐 byte 複製到追蹤的 `state/messages/{requests,responses}/<id>.json`；領域狀態引用這份，不另做通用收據。下一格 `aos-inbox` 在上一格正常收尾時拿這份比對、刪原件（[B-623](../tick.md)；下一步納入 git 時改成比 HEAD 裡的）。
- **待送封套**：`.aos/outbox/{requests,responses}/<id>.json`，schema [msg-outbox](schemas/msg-outbox.schema.json)，內容 `{"version":1,"target_node":"/目標","message":{...},"alarm_ticks"?:N}`；message 是完整 JSON-RPC，ID 須與檔名相同。
- **`alarm_ticks`**（可省）〔第二十批，取代 `alarm_ms`〕：正整數，本 node 的格數，從投出那一格算。
- **`channel`**、**`urgent`**〔第十九批，可省，預設 false〕：`channel:true` 表示本格有通道時改經 daemon 送，只用在 `.aos/outbox/requests/`，回應寫了也照檔案投件；`urgent:true` 是急件，只在 `channel:true` 時可寫。行為見 [B-624](../tick.md)。
- **鬧鐘紀錄**：〔第十六批〕ignored 的 `.aos/alarms/req-<id>.json`（請求）或 `resp-<id>.json`（回應），因為請求和回應可以同 ID（P-301），分開才不撞名；內容 `{"version":1,"target_node":…,"path":投出的檔案路徑,"due_seq":到期格}`〔第二十批，`due_seq`＝投出那格的 `seq` 加 `alarm_ticks`〕。
- **stderr 診斷行**：`target_not_node: <node> <id>`、`target_not_writable: <node> <id>`、`request_not_handled: <node> <id>`、`alarm_skipped: <id>`（不知道 `seq`，沒設鬧鐘）。
- 工作與 LLM 的固定材料依據留 `state/work/<attempt_id>/`；其餘領域路徑見所屬篇。

範例：[最小封套](examples/messages/outbox.minimal.valid.json)、[設了鬧鐘的封套](examples/messages/outbox.alarm.valid.json)、[反例：`alarm_ticks` 為 0](examples/messages/outbox.alarm-zero.invalid.json)、[走通道的急件](examples/messages/outbox.channel-urgent.valid.json)、[反例：沒走通道卻標急件](examples/messages/outbox.urgent-no-channel.invalid.json)。

## P-207．加入普通設定與重要設定手改〔建議預設，未拍板〕

argv：`aos-config-add [--node <node_dir>] --from <source> --to <target>`；省略 node 用 cwd。source 是任意可讀路徑，相對呼叫 cwd；target 是 node/config/ 內檔案，相對 node、不准 ..／symlink 逃出。用呼叫者帳號，無自訂環境；stdin 不讀，stdout 成功印 target＋LF，stderr 印 `code: 說明`。提交訊息 `aos-config-add <target>`。

退出：0 已提交／無變動；2 參數／路徑／JSON 不合；75 busy；125 前置失敗（未寫目標）；1 寫入失敗且已還原；3 commit／還原故障，寫擋板檔（P-213），之後的格被擋。〔第二十批〕它不是任務表上的任務；在 tick 之外跑算外部世界（[B-602](../tick.md)）。本輪假設沒有 git，只做原子替換。

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

## P-211．〔下一步納入〕aos-cg：每項一框

〔使用者方向 2026-09-30，第二十批進行順序〕本條是草稿，**不是現行規則**；下一步把 cgroup 納入時再定。行為草稿：[B-202](../base/execution.md)；框的命名與委派見 [B-605](../daemon.md)。〔使用者方向 2026-09-30，第二十批追答 8〕它是普通程式，不是系統級任務。

- **argv**：`aos-cg [--] <原指令…>`。不收上限參數（上限歸 daemon 設在 node 框）。
- **框名**：本 node 框 `n-<h>` 下的 `task-<seq>-<pid>`，`seq` 取結束碼紀錄的格數（沒有紀錄時用 `0`），`pid` 是 aos-cg 自己的 PID；跟 `tick` 葉並列。
- **stdin、stdout、stderr**：原樣交給原指令；aos-cg 自己只在 stderr 印 `code: 說明`，代碼有 `cgroup_unavailable`（照 B-202 沒 cgroup 時的做法跑）、`frame_not_empty`。
- **環境**：原樣交給原指令，不另加變數。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 原指令正常結束；被訊號結束時 aos-cg 用同一個訊號結束自己，讓上一層 wait 看到的是訊號 |
| `2` | 用法錯（沒有原指令） |
| `1` | 框清不空（`frame_not_empty`）：另建停格檔（P-213），不讓後面的項在還有人寫檔時開跑 |
| `125` | 原指令沒開起來（exec 前失敗），照 inst |

## P-212．aos-as：切換帳號〔建議預設，未拍板〕

行為正本：[B-303](../base/identity-resources.md)；`spawn_as` 的參數與限制見 [B-609](../daemon.md)、[P-107](daemon/provision-and-runner.md)；runner 回報見 [P-110](daemon/provision-and-runner.md)。〔使用者方向 2026-09-30，第二十批追答 8〕它是普通程式，不是系統級任務。

- **argv**：`aos-as <帳號> [--] <原指令…>`；帳號是名稱或非負 UID。
- **暫存 inst**：ignored 的 `.aos/jobs/as-<seq>-<pid>.json`（`seq` 取結束碼紀錄的格數、沒有時用 `0`，`pid` 是 aos-as 自己的 PID），內容是一份 inst：`argv`、目前 cwd、目前的環境；結束後刪掉。
- **交給 helper 的 fd**：繼承到的鎖 fd（`AOS_TICK_LOCK_FD`）、一條回報 pipe 的寫端，〔建議預設〕另交自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走（`spawn_as` 附的 fd 從 2 個變 5 個，P-107 與 daemon-provision schema 要跟著改）；〔下一步納入 cgroup 時補〕自己在 `aos-cg` 的 `task-*` 框裡時另帶 `frame`＝那個框。
- **stderr 代碼**：`no_channel`、`helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`（daemon 的錯誤碼照轉）、`result_unknown`（回應成功但 pipe 沒回報就關了）。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 照 runner 回報：正常結束回同一碼；被訊號結束時用同一個訊號結束自己 |
| `2` | 用法錯 |
| `125` | 沒開起來或不知道結果：沒有通道變數、daemon 回錯、`result_unknown`；不寫 `exit`。`result_unknown` 時呼叫它的一方不能重跑 |

## P-213．每項結束碼紀錄、停格檔與擋板檔〔建議預設，未拍板〕

行為正本：[B-633](../tick.md)（紀錄）、[B-620](../tick.md)（停格檔）。schema：[node-tick-record](schemas/node-tick-record.schema.json)。

- **位置**：`.aos/tick/current.json`（本格）、`.aos/tick/last.json`（上一格），都 ignored；任務環境 `AOS_TICK_RECORD` 是 `current.json` 的絕對路徑。
- **內容**：`{"version":1,"seq":N,"started_at_ms":毫秒,"tasks":[{"id":…,"exit":碼}|{"id":…,"signal":號}],"ended":bool,"exit"?:碼,"stopped_after"?:"<id>"}`。
  - `seq`：本 node 的格數，共用 `TickSeq`（從 1 起）。
  - `tasks`：已跑完的項，照順序；`id` 是任務表該項的 `id` 字串；每項 `exit`（0～255）與 `signal`（1～64）二選一。沒跑到的不列。
  - `ended`：跑完或被停格檔停下時是 true，這時必須有 `exit`（這格 tick 的結束碼）；false 時不得有 `exit`、`stopped_after`。
  - `stopped_after`：被停格檔停下時，是哪一項跑完後停的，記那一項的 `id` 字串；只在 `ended:true` 時可有。
  - `started_at_ms`：只給人看，不參與計算。
- **寫法**：每次整份重寫（暫存檔→rename），不 fsync；只有核心寫。
- **停格檔**：`.aos/tick/stop`，ignored；任何內容都算（建議一行 UTF-8 原因，核心印在 stderr 的 `stopped:` 後面）。核心取鎖後、開第一項前刪掉殘留的；每項結束後檢查，存在就不開後面的項。跟擋板檔不同，它只管本格；格結束時還在，daemon 順帶暫停 node。
- **擋板檔**：`.aos/tick-blocked`，ignored；內容一行 UTF-8 原因（核心印在 `blocked:` 後面）。任務或人手建、人手刪；核心取鎖後看到就不跑、不寫紀錄、回 1；daemon 看到就不開格。

範例：[跑到一半](examples/node/tick-record.minimal.valid.json)、[被停格檔停下](examples/node/tick-record.ended.valid.json)；反例：[同一項同時有 exit 與 signal](examples/node/tick-record.exit-and-signal.invalid.json)、[ended 卻沒有 exit](examples/node/tick-record.ended-without-exit.invalid.json)、[沒收場卻記了 stopped_after](examples/node/tick-record.stopped-not-ended.invalid.json)。
