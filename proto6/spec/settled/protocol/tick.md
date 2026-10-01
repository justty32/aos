# tick：工作資料夾、任務表與一格 tick

← [整理區](../README.md)｜[共用約定](../../protocol/README.md)｜行為正本：[inst](../../base/inst.md)、[tick](../tick.md)、[設定](../../agent/configuration.md)｜[慣例](../conventions.md)｜[tick 暫緩區](../deferred/tick.md)｜[使用者裁定](../../../notes/2026-09-29-verdicts.md)

本篇只定格式：資料夾裡的檔名、JSON、argv、環境變數、結束碼。行為一律以 [tick](../tick.md) 等主規格為正本，這裡寫到行為只留一句加條號。

- 本篇寫的 `.aos/…` 都是環境變數 `AOS_DIRNAME` 沒設時的樣子；設成別的名字就換那個名字，設成空字串就直接放在資料夾本身（[C-09](../conventions.md)）。
- 結束碼照 aos 慣例（[C-08](../conventions.md)）：0＝預料之中、1＝通用錯誤（含 argv 用法錯）、其他碼是各程式特別指定的。
- **改名**〔使用者 2026-10-01〕：本篇原是 `protocol/node.md`（「node：資料夾、任務與一格 tick」），2026-10-01 改成 `protocol/tick.md`，叫「tick 協議」；跟 [tick.md](../tick.md) 的關係就像 [daemon/core.md](../daemon/core.md) 對 [protocol/daemon/core.md](daemon/core.md)：一個寫行為、一個寫格式。schema 跟著改名：`node-tasks` → `tick-tasks`、`node-tick-record` → `tick-record`、`node-inst` → `inst`；範例資料夾 `examples/node/` → `examples/tick/`。
- 本篇講的**工作資料夾**（英文 `tick dir`）就是 `aos-tick` 這一格的 cwd，原本寫 node 的地方都改了；暫緩區講上下層的「上層 node／下層 node」與舊 RPC 名稱（`node.take`、`node.send`…）照舊。

## P-200．資料夾布局〔建議預設，未拍板〕

工作資料夾用它正規化的絕對路徑來認〔使用者 2026-10-01〕：要指名某個工作資料夾的地方（例如佇列訊息的 `to`、摘要的 `node_id`，都在依賴暫緩區的條文裡）就寫這個絕對路徑；暫緩區與舊欄位名裡的「node id」指的也是它。下表的名稱固定；其他內容按任務需要才建，不預建空表。kernel、agent 是「裝了哪些任務」決定的角色，不另設角色欄位。

有 git 時每個工作資料夾是一個 git repo，表中「追蹤／ignore」就是 git 的分類；aos 只提交與還原 aos 範圍（[B-630](../tick/git.md)），ignore 的核心檔一律固定排除（[B-622](../tick/git.md)）。沒有 git 時這只是「受管狀態／暫存」的區分（[B-632](../tick/git.md)）。

| 路徑 | 用途 | 分類 |
|---|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑這個工作資料夾的 inst，給 `aos-exec` 用（`aos-tick` 不看它）；選檔順序依 [inst 目標](../../base/inst.md#inst-目標檔案或資料夾) | 追蹤 |
| `.aos/tasks.json` | 任務註冊表（P-202），只有這一個位置（`AOS_DIRNAME` 空字串時是 `tasks.json`）；`aos-tick` 認資料夾就看它在不在（P-203） | 追蹤 |
| `config/` | 任務使用的正式設定；領域格式由使用它的任務定義 | 追蹤 |
| `state/` | 已消費收件、請求、結果與必要進度；子結構由各協議篇定義 | 追蹤 |
| `requests/`、`responses/` | 檔案收件區，各含發布用 `.tmp/`；由普通程式收與寫，aos 不管（[B-623](../tick/mq.md)） | ignore |
| `work/` | 任務的暫存工作進度 | ignore |
| `.aos/jobs/<id>/` | 替成員跑工具、打 LLM 的 once 工作；`aos-as` 的暫存 inst（`as-<seq>-<pid>.json`，P-212）也放這裡 | ignore |
| `.aos/attention/` | 本工作資料夾的待處理事項，含 daemon 發現的問題 | ignore |
| `.aos/summary/` | 給上層讀的摘要，見 P-307 | `summary.json` 追蹤、`published.json` ignore |
| `.aos/mq/post/` | 要經系統訊息佇列送出的訊息（`<id>.req.json`／`<id>.resp.json`），見 P-206 | 追蹤 |
| `.aos/mq/get/` | 寄件帳號要能在這裡建檔，是 `node.send` 的授權判準（[B-614](../deferred/daemon/messaging.md)）；`aos-mq get` 要不要拿來放取出的訊息由它自己定 | 追蹤 |
| `.aos/mq/failed/` | `mq-post` 送不出去的失敗紀錄；下一格 `mq-post` 開始送之前清掉（[B-624](../tick/mq.md)），格式見 P-206 | ignore |
| `.aos/tick.lock` | 核心的鎖檔：不存在就建、tick 不刪；只有那一格的 tick 握著，不傳給任務（[B-602](../tick.md)） | ignore |
| `.aos/tick/` | 核心的結束碼紀錄 `current.json`、`last.json` 與停格檔 `stop`（[B-633](../tick.md)、[B-620](../tick.md)、P-213）；不隨還原、不被清理 | ignore |
| `.aos/tick-blocked` | 擋板檔：有它時核心不開格（[B-620](../tick.md)、P-213）。現行 daemon 照常叫，由 `aos-tick` 自己擋；舊 daemon 是有它就不開格（[B-607](../deferred/daemon/registration.md)，在暫緩區）〔astra 報告必修 1〕 | ignore |
| `.aos/runner-stderr.log` | 〔暫定〕runner 診斷，daemon 每格覆寫；輪替以後再定（[P-109](../deferred/protocol/daemon/provision-and-runner.md)，舊 daemon 的設計，在暫緩區） | ignore |
| `public/` | 可供其他工作資料夾存取的共用空間 | 看內容 |
| `.gitignore` | 至少列出上表所有 ignore 的路徑：`/requests/`、`/responses/`、`/work/`、`/.aos/jobs/`、`/.aos/attention/`、`/.aos/tick.lock`、`/.aos/tick/`、`/.aos/tick-blocked`、`/.aos/runner-stderr.log`、`/.aos/summary/published.json`、`/.aos/mq/failed/` | 追蹤 |

補充：

- **收件分兩處**〔慣例；第二十批起檔案收件與投件是普通程式，aos 不管，[B-623](../tick/mq.md)〕：請求放在被問者的 `requests/<id>.json`，回應放在發問者的 `responses/<id>.json`。
- **找 inst**：`aos-exec` 的目標是資料夾時先找 `.aos/inst.json`、沒有再找 `inst.json`，base 是那個資料夾；目標是單檔 inst 時 base 是該檔所在資料夾。正本見 [inst 目標](../../base/inst.md#inst-目標檔案或資料夾)。舊 daemon 的登記與掛載行程也照這套（[B-613](../deferred/daemon/channel.md)、[P-118](../deferred/protocol/daemon/channel.md)，在暫緩區）。
- **鎖檔與 git 管理目錄**：鎖檔 `.aos/tick.lock` 不在 git 管理目錄（[B-602](../tick.md)）。git 管理目錄用 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾。巢狀 tick 的排除寫在 git 管理目錄的 `info/exclude`、存檔點記在 `refs/aos/marks/<任務 id>`（P-205），都不在工作樹；不做救援 ref（[B-602](../tick.md)）。
- **事項**：待處理事項放 `.aos/attention/`，不隨還原，見 [ops](../../protocol/ops.md)。
- 不跑 `aos-tick` 的資料夾不必有完整布局。

依據：第十七批（runner 診斷）、第十九批（鎖檔、單檔掛載）、第二十批（結束碼紀錄、擋板檔裁定 a＋c、aos-as）、〔使用者方向 2026-09-29〕裁定「收件分兩格」、〔使用者方向 2026-09-30〕第二十批進行順序；astra 審整理區同日定案（`.aos/mq/post/`，撤 `.aos/alarms/`）。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

- **schema**：[inst.schema.json](../../protocol/schemas/inst.schema.json) 只驗 [inst 正本](../../base/inst.md) 的原始結構。引用內容、循環、選項值與展開後的型別，仍由 runner 驗。
- **版本**：`_metainfo` 沿第 1 版，不加 `version`。頂層、metainfo、選項裡不認得的鍵照 inst 忽略，這是 P-002 的例外。
- **沒有 `user`**〔使用者方向 2026-10-01〕：inst 頂層沒有 `user`（撤回，見 [inst](../../base/inst.md)）；寫了就是不認得的鍵，照上一條忽略，照目前身分跑。schema 也不再定義它。
- **結束碼**：125／126／127 與 `exit` 的訊號編碼照正本，不改成 RPC 錯誤；它們是 [C-08](../conventions.md) 說的「特別指定的碼」。

範例：[正例](../../protocol/examples/tick/inst.minimal.valid.json) 跑 aos-tick。

## P-202．任務註冊表〔建議預設，未拍板〕

任務表只有一個位置：工作資料夾的 `.aos/tasks.json`（`AOS_DIRNAME` 空字串時是 `tasks.json`）；`aos-tick` 的目標不能給檔（P-203）〔使用者 2026-10-01〕。schema 是 [tick-tasks.schema.json](../../protocol/schemas/tick-tasks.schema.json)。

```json
{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}
```

- 順序只看 `tasks` 陣列位置；`tasks` 可以是空陣列，維持陣列。
- 每項是 **inst 的超集**：一份 inst 加下面「每一項」表的欄位，也可以用整份 `$ref`。
- 頂層可以放每一項的預設與 `modules`（下面「頂層」表）〔使用者 2026-10-01〕。跑到某一項時，頂層預設＋這一項淺層合併（項寫了的鍵整個蓋過，`envs` 也整包換），合併結果當一份獨立的 inst 展開：`cwd` 以工作資料夾為中心，其他欄位以解出的 cwd 為中心。頂層 `cwd` 不改 tick 自己的 cwd。
- **指示詞展開時機**〔使用者 2026-10-01〕：讀表時只解到每一項那一層（整份、頂層七個預設欄位與 `modules` 的值、`tasks`、陣列元素各解一層，頂層其他鍵不解；`$ref` 以工作資料夾為中心，`$ref:""`／`#…` 指整份表）；值的內部跑到那一項、合併後才展開，這時 `$ref:""`／`#…` 指合併後的這一項。正本見 [B-620](../tick.md)「頂層預設」「指示詞什麼時候展開」；跟 daemon 設定檔的對照見 [C-11](../conventions.md)。
- 格式上外層與每項的 `_metainfo` 照寫；核心不擋，開格只做極簡檢查（有 `tasks` 陣列、每項解一層後是物件、合併頂層預設後有 `argv`，[B-620](../tick.md)）。
- 核心只看合併後的 inst 部分與 `id`；不看 `kind`、`modules`。順序、類別與讀表檢查以 [B-620](../tick.md) 為正本。

頂層：

| 欄位 | 約束 |
|---|---|
| `_metainfo` | 整份表的格式標記（`aos-tasks` 第 1 版）；不是預設 |
| `tasks` | 必填，陣列 |
| `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit` | 可省；每一項的預設，格式照 inst。項自己寫了就整個蓋過〔使用者 2026-10-01〕 |
| `modules` | 可省；tick 模組的設定，一個模組一個鍵，比照 daemon 設定檔的 `modules`（[P-120](daemon/core.md)）。目前沒有任何模組：核心照收不理、型別不查、不當預設合併；讀表時只解一層，內部留給模組自己展開〔使用者 2026-10-01〕 |

頂層的 `id`、`kind` 不是預設；頂層其他鍵當陌生鍵忽略。

每一項：

| 欄位 | 約束 |
|---|---|
| `id` | 可省；寫了是共用 `ID`。沒寫時，這一項的 id＝它在 `tasks` 陣列的位置轉字串（`"0"`、`"3"`）。紀錄、`AOS_TASK_ID`、`stopped_after` 都用它。默認不重複，核心不查 |
| `kind` | 可省。`system`、`kernel`、`agent`、`custom`；〔暫定〕或自訂的「類別.名稱」：類別限 `kernel`／`agent`／`custom`，名稱是小寫英數與 `_`、`-`（例如 `agent.review`）。`system` 標記系統級任務（[B-626](../tick.md)），只是標記，不驗順序；`system.x` 不接受（schema 擋，核心不擋） |

**不認得的鍵照收、核心忽略**（P-007；schema 不設 `additionalProperties:false`）。任務表先只定上表這些基本欄位；〔使用者方向 2026-10-01〕任務沒有 `user`（inst 頂層沒有，任務是 inst 的超集所以也沒有），寫了就是陌生鍵、照 tick 自己的帳號跑，要切帳號就在 argv 包 `aos-as`（P-212）。第十九批的 `group`、`needs` 不列入 schema，寫了就是陌生鍵。前置改用 `aos-needs`（P-204、[B-621](../tick/needs.md)），組改由存檔點劃分（P-205、[B-630](../tick/git.md)）。第十七批的 `methods` 2026-10-01 從規範拿掉，寫了也是陌生鍵。kernel、agent、custom 類任務的逾時與取消延後（[P-008](../../protocol/README.md#p-008)）。

誰驗哪些欄位見 [B-620](../tick.md)「誰驗什麼」：核心只做極簡檢查，其餘 schema 限制由工具或人工在 `aos-ctl resume` 前先驗（恢復前驗證，[B-625](../tick/recovery.md)；daemon 不代驗）〔astra 報告必修 2〕。

範例：

- 正例：[最小](../../protocol/examples/tick/tasks.minimal.valid.json)（登記普通程式）、[沒寫 `id` 與 `kind`](../../protocol/examples/tick/tasks.no-id.valid.json)（id 用位置字串）、[包 `aos-as`](../../protocol/examples/tick/tasks.as.valid.json)（用別的帳號跑）、[陌生鍵](../../protocol/examples/tick/tasks.unknown-key.valid.json)（帶 `group`、`needs` 照收）、[標準任務表範本](../../protocol/examples/tick/tasks.template.valid.json)（照 [B-629](../tick/template.md) 沒有 git 版）、[有 git 版範本](../../protocol/examples/tick/tasks.template-git.valid.json)（`aos-git` 開格、存檔點、收尾）、[`methods`](../../protocol/examples/tick/tasks.methods.valid.json) 與 [`methods` 裡重複](../../protocol/examples/tick/tasks.methods-duplicate.valid.json)（都當陌生鍵照收）、[自訂種類](../../protocol/examples/tick/tasks.custom-kind.valid.json)（`agent.review`）。
- 指示詞的正例：[整項 `$ref`](../../protocol/examples/tick/tasks.reference.valid.json)（讀表時解一層）、[`argv` 帶指示詞](../../protocol/examples/tick/tasks.directive.valid.json)（跑到那一項才展開）。
- 頂層預設與 `modules` 的正例〔使用者 2026-10-01〕：[頂層預設](../../protocol/examples/tick/tasks.defaults.valid.json)（B-620 的例子：頂層 `cwd`、`envs`、`stdout`，一項自己寫 cwd、一項整項 `$ref`）、[頂層給 `argv`](../../protocol/examples/tick/tasks.defaults-argv.valid.json)（項只寫 `id`）、[頂層 `modules`](../../protocol/examples/tick/tasks.modules.valid.json)（照收不理）。
- 反例：[自訂 `system.x`](../../protocol/examples/tick/tasks.custom-kind.invalid.json)、[某項沒 `argv`、頂層也沒有](../../protocol/examples/tick/tasks.no-argv.invalid.json)〔使用者 2026-10-01〕。

依據：〔暫定〕第十八批（自訂種類）、第十九批（撤 `user` 的永遠禁止）、〔使用者方向 2026-09-30〕第二十批（只定基本欄位、疑點裁定 6）；使用者 2026-10-01（`kind` 不填、`id` 可省、拿掉 `methods`、極簡檢查、不看 `user`；同日撤回 inst 與任務的 `user`；同日第二批：任務表只有一個位置、頂層預設、指示詞只解到 tasks、頂層 `modules`）。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

### argv

`aos-tick [<目標>]`

- 目標是位置參數，跟 `aos-exec` 一樣；沒有 `--node`、`--target` 這類旗標。`-h`／`--help` 印用法、回 0。
- **沒給**：用目前目錄。相對路徑一律轉成絕對路徑；不往上層目錄找。
- **是資料夾**：要有 `.aos/tasks.json`，它就是任務表；不看 `.aos/inst.json`。沒有：`no_tasks`、回 1。
- **是檔**：用法錯，`usage`、回 1，什麼都不建〔使用者 2026-10-01：拿掉「目標給檔就當任務表」，原規則記在[暫緩區撤回表](../deferred/tick.md#已撤回被取代)〕。
- **不存在**：`no_target`、回 1。
- `-` 開頭的參數（`-h`／`--help` 除外，含舊的 `--node`、暫緩的 `--firstdo-fsync`）、多給一個目標，都算用法錯：`usage`、回 1。目標本身以 `-` 開頭時寫成 `./-x`。`AOS_DIRNAME` 不合法（含 `/`、是 `.` 或 `..`，[C-09](../conventions.md)）也是 `usage`、回 1。
- 行為正本：[B-620](../tick.md)「認哪個資料夾」。tick 在工作資料夾裡跑，cwd 就是管轄區；它不看自己在哪個 cgroup（[B-627](../tick.md)）。
- 經 `aos-exec` 跑時：資料夾目標的 inst 只要 `{"argv":["aos-tick"]}`，預設 cwd 正好是那個資料夾。直接執行 `.aos/inst.json` 檔時 base 不同，要明寫 `cwd:".."` 或在 argv 給目標。
- 第十九批的 `--check`（全掛檢查）撤。

### tick 自己的介面

| 介面 | 約定 |
|---|---|
| stdin | 不讀；inst 預設 `/dev/null` |
| stdout | tick 自己不寫。任務的輸出照各自 inst 走（預設 `/dev/null`，明寫 inherit 才會跟 tick 共用） |
| stderr | tick 自己只印 `代碼: 說明` 一行（下表），或沒接住的錯的 traceback |
| 讀寫 | 讀任務表、持鎖、寫 `.aos/tick/` 的紀錄、開格刪殘留的停格檔、每項後查停格檔（P-213）。送收訊息是系統級任務的事（[B-629](../tick/template.md)）；任務自己直接讀寫檔案 |
| 身分 | tick 自己不切 UID；直接呼叫也不會替你取得 inst 的身分 |

核心自己的 stderr 代碼：

| 代碼 | 什麼時候 | 回 |
|---|---|---|
| `usage` | argv 用法錯（含目標是檔）、`AOS_DIRNAME` 不合法 | 1 |
| `no_target` | 目標不存在 | 1 |
| `no_tasks` | 目標是資料夾，底下沒有 `.aos/tasks.json` | 1 |
| `busy` | 拿不到 `.aos/tick.lock`：同資料夾上一格還沒跑完（[B-602](../tick.md)） | 0 |
| `blocked` | 有擋板檔；後面附擋板檔裡的原因 | 0 |
| `bad_table` | 任務表沒過極簡檢查（[B-620](../tick.md)） | 1 |
| `stopped` | 被停格檔停下；後面附停格檔裡的原因 | 0（照表跑完的那格） |
| `exec_failed` | 某項沒跑成：mkdir／cwd／重導向失敗（記 `exit:125`）、沒執行權（126）、找不到程式（127）；附那一項的 id | 不影響，照常跑下一項 |

舊碼表的 `config_invalid`、`user_mismatch`、`record_unreadable`、`record_unwritable` 不再有；它們的來由見 [tick 暫緩區](../deferred/tick.md)。

### 每項任務怎麼跑

| 介面 | 約定 |
|---|---|
| 身分 | 沿用 tick 的有效 UID、群組與資源範圍；任務沒有 `user`（寫了照陌生鍵）。要換帳號包 `aos-as`（P-212） |
| cwd／argv | 頂層預設＋本項合併成 inst、展開後執行（P-202）；合併後還是沒有 cwd 時是工作資料夾 |
| stdin | 預設 `/dev/null`；可用合併後 inst 的 stdin 重導向 |
| stdout／stderr | 照 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不把輸出文字當完成證據 |
| 環境 | 繼承 tick 的環境（含 `AOS_DIRNAME`，經 daemon 控制模組跑時還有 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`），加上下表的變數，再照 inst 套用 `envs`；`envs` 清空時下表的也不放。這些變數都不是授權證據 |

tick 給任務的環境變數。整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`（aos 全部的環境變數見 [C-10](../conventions.md)）：

| 變數 | 值 |
|---|---|
| `AOS_TICK_CWD` | 工作資料夾的絕對路徑，也就是這一格 tick 的 cwd。本格紀錄在 `$AOS_TICK_CWD/.aos/tick/current.json`（狀態資料夾名照 `AOS_DIRNAME`；空字串時是 `$AOS_TICK_CWD/tick/current.json`） |
| `AOS_TASK_ID` | 這一項的 id：任務表寫的 `id`；沒寫時是位置字串；不是字串時轉成字串 |
| `AOS_TASK_INDEX` | 這一項在 `tasks` 陣列的位置，十進位，從 0 起 |

其他：

- 沒有設定需求的程式不必讀任何環境變數，也不必寫回應封套；`true`、腳本與既有程式都能直接當任務。
- 任務直接開檔讀設定；改設定的時機與「tick 裡不改 `config/`」的軟性原則見 [A-102](../../agent/configuration.md)。
- key 不由 tick 放進 argv 或任務環境；inst 的 `envs` 照正本。
- 鎖 fd 不傳給任務，沒有 `AOS_TICK_LOCK_FD`（[B-602](../tick.md)）；每項一框（`aos-cg`）見 P-211、[B-634](../tick/cg.md)。

### 結束碼

照 [C-08](../conventions.md)，`aos-tick` 只回 0 或 1，只講 tick 自己；任務怎麼結束只記進紀錄（P-213）。

| tick 結束碼 | 意思 |
|---|---|
| `0` | 預料之中：照表跑完（不管任務成敗）、被停格檔停下、`busy`、`blocked` |
| `1` | tick 自己出錯：`usage`、`no_target`、`no_tasks`、`bad_table`；tick 自用的檔讀不到、寫不進或格式壞（自然丟錯，traceback 進 stderr） |

- **停掉本格靠停格檔 `.aos/tick/stop`，不靠結束碼**；要知道是不是被停下，讀紀錄的 `stopped_after`。外層要分出 busy、blocked，看 stderr。
- 第十九批「標準配備」的 3（提交故障）與 125（格首看到擋板）撤；第二十批的 2（argv 或任務表不合法）、75（鎖被占）也撤（[tick 暫緩區](../deferred/tick.md)「已撤回／被取代」）。
- 父程序看 wait 狀態辨識 tick 被訊號結束，不把 `128+N` 當訊號證據。inst 的文字 `exit` 編碼仍照 P-201。
- kernel、agent、custom 類任務的逾時與取消延後（[P-008](../../protocol/README.md#p-008)）。

依據：〔使用者方向 2026-09-30〕第十九批（argv）、第二十批（環境變數命名、撤 `--check`）、第二十批疑點裁定 1（改：停格靠檔案）；使用者 2026-10-01（目標改成位置參數、結束碼照 C-08、`AOS_TICK_CWD` 取代 `AOS_NODE_DIR` 與 `AOS_TICK_RECORD`、`--firstdo-fsync` 暫緩；同日第二批：目標只能是資料夾）。

## P-204．aos-needs〔使用者方向 2026-09-29；第二十批改寫〕

任務的成敗怎麼算以 [B-620](../tick.md)「跑每一項」為正本；要停掉本格用停格檔（P-213）。

**`aos-needs`**〔建議預設，未拍板〕：普通程式，前置沒成功就不跑原指令。行為以 [B-621](../tick/needs.md) 為正本。

- argv：`aos-needs <前置任務 id…> -- <原指令…>`；前置至少一個，`--` 必填。
- 讀本格紀錄 `$AOS_TICK_CWD/.aos/tick/current.json`（P-213）；每個前置都在紀錄的 `tasks` 裡而且 `exit:0`，才 exec 原指令。
- stdin、stdout、stderr 原樣交給原指令。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 前置都成功，已 exec 原指令 |
| `1` | 用法錯（沒有前置、少了 `--` 或原指令） |
| `125` | 沒跑（特別指定的碼）。stderr 印 `needs_unmet: <id>`（前置不在紀錄或不是 0），或 `no_record`（沒有 `AOS_TICK_CWD` 或紀錄讀不到） |

## P-205．aos-git：開格、存檔點、收尾〔使用者方向 2026-09-30；格式為建議預設〕

本條只定格式。行為正本：開格、存檔點、收尾與 aos 範圍 [B-630](../tick/git.md)；能不能用、呼叫參數、固定排除、故障 [B-622](../tick/git.md)；沒有 git 時 [B-632](../tick/git.md)。

- **argv**：三者都是系統級任務（`kind:"system"`），都在工作資料夾（cwd）跑。

| argv | 做什麼 |
|---|---|
| `aos-git open` | 上一格沒正常收尾就還原；清殘留；打本格第一個存檔點 |
| `aos-git mark [<路徑…>]` | 打存檔點；剛結束那組有失敗就先還原。帶路徑＝把使用者任務自己的檔加進 aos 範圍，從這點起到本格結束；路徑相對工作資料夾〔使用者 2026-09-30 同意照暫定〕。`AOS_DIRNAME` 空字串時整個工作資料夾本來就在 aos 範圍，帶不帶路徑都一樣（[B-630](../tick/git.md)） |
| `aos-git close` | 處理最後一組、提交、刪本格存檔點 |

- **在 tick 內**：靠繼承的鎖。不在 tick 內回 125、印 `not_in_tick`，不自己取鎖。這個判法靠「鎖 fd 傳給任務」，那段在[暫緩區](../deferred/tick.md#暫緩b-602-完整互斥的其餘細節)；最簡鎖不傳 fd，回來之前還沒有判法（[B-622](../tick/git.md)）。
- **git 參數**（每次呼叫都帶，[B-622](../tick/git.md)）：`-c core.fsync=committed,reference`（存檔點改帶 `core.fsync=none`）、`-c gc.auto=0`、`-c maintenance.auto=false`、`-c core.hooksPath=/dev/null`、`-c commit.gpgSign=false`、`-c safe.directory=<工作資料夾>`；呼叫前清掉繼承的 `GIT_*`。最低 git 2.36。
- **commit 訊息**：`aos-tick <seq>`，`seq` 是結束碼紀錄的格數（P-213）；每格最多一個。可另加一行 `aos-failed: <存檔點 id…>`，只給人看。〔第二十批〕第十九批的 `aos-tick group <first>..<last>`、`aos-tick unclaimed`、`aos-tick adopt` 撤。
- **存檔點**：暫存提交，記在 git 管理目錄的 `refs/aos/marks/<任務 id>`（取 `AOS_TASK_ID`）；不在任何分支上，close 用完就刪，open 開格先清掉殘留的。不做救援 ref。
- **stderr 代碼**：

| 代碼 | 什麼時候 |
|---|---|
| `no_git` | git 不能用；只是警告，回 0 |
| `git_failed` | 還原、存檔點、commit 失敗（附 git 的錯誤行） |
| `record_missing` | 在 tick 內卻沒有結束碼紀錄 |
| `mark_id_invalid` | 任務 `id` 當不了 ref 名（例如以 `.lock` 結尾） |
| `not_in_tick` | 不在 tick 內 |

| 結束碼 | 意思 |
|---|---|
| `0` | 成功；含有組失敗但已還原、含 `no_git` |
| `1` | 故障：已寫擋板檔、建停格檔（P-213）；或用法錯 |
| `125` | 不在 tick 內（特別指定的碼） |

〔第二十批疑點裁定 5〕第十九批的完成紀錄 `.aos/journal/<seq>.json`、`sent/`、`discarded/` 與 `node-journal` schema 撤，由結束碼紀錄取代（P-213、[B-632](../tick/git.md)）。

## P-206．系統訊息佇列 aos-mq 與發摘要〔使用者方向 2026-09-30，astra 審整理區同日定案〕

本條只定檔案格式與 argv。行為正本：取 [B-623](../tick/mq.md)；送與發摘要 [B-624](../tick/mq.md)。佇列裡的訊息可以是請求或回應物件〔使用者方向 2026-09-30，修正輪暫定的裁定〕。檔案收件區 `requests/`、`responses/` 的格式屬普通程式，不在本條。

### argv 與結束碼〔建議預設〕

| 程式 | 任務 id（範本） | 做什麼 |
|---|---|---|
| `aos-mq get` | `mq-get` | 用 `node.take` 取本工作資料夾佇列裡的訊息，取到空為止 |
| `aos-mq post` | `mq-post` | 把 `.aos/mq/post/` 的訊息一件一件用 `node.send` 送出 |
| `aos-publish` | `summary` | 發布摘要 |

三者都是系統級任務，都在工作資料夾（cwd）跑、不收其他參數。在 tick 內靠繼承的鎖；不在 tick 內時自己取同一把鎖，拿不到回 75。「在不在 tick 內」靠暫緩區的「鎖 fd 傳給任務」（[tick 暫緩區](../deferred/tick.md#暫緩b-602-完整互斥的其餘細節)）；最簡鎖下，任務在 tick 內去取鎖一定拿不到，這段要等它回來再對。

| 結束碼 | 意思 |
|---|---|
| `0` | 成功（含沒事做、本格沒有通道） |
| `1` | 有件處理失敗（例如 `node.take` 回錯、發布摘要失敗、寫檔 I/O 錯）；或用法錯 |
| `75` | 不在 tick 內又拿不到鎖（特別指定的碼） |

〔建議預設，未拍板〕daemon 訊息部件關閉：`aos-mq get` 回 0；`aos-mq post` 有待送件回 1，stderr 印 `post_failed: <to> <id> not_available`，失敗檔 `error.code` 為 `not_available`；沒件回 0。行為見 [B-614](../deferred/daemon/messaging.md)、[B-624](../tick/mq.md)，RPC 錯誤碼見 [P-119](../deferred/protocol/daemon/channel.md)。

### 要送的訊息

`.aos/mq/post/<id>.req.json`（請求）或 `<id>.resp.json`（回應）（追蹤），`<id>` 是訊息的 ID；請求與回應各用一個後綴，同一個工作資料夾同一格送出同 ID 的請求與回應不會撞檔名〔使用者 2026-09-30 同意照暫定〕。`message` 是請求物件就得用 `.req.json`、是回應物件就得用 `.resp.json`。〔暫定〕形狀是 `node.send` 的 params 去掉 `token`、加 `version`：

```json
{"version":1,"to":"/目標工作資料夾","message":{...},"urgent"?:true}
```

| 欄位 | 約束 |
|---|---|
| `version` | 必填，1 |
| `to` | 必填；收件 tick 的工作資料夾絕對路徑（P-200；暫緩區叫 node id） |
| `message` | 必填；一份請求或回應物件（[P-301](../../protocol/messages.md)），它的 `id` 要跟檔名去掉後綴的部分相同；序列化後最多 196608 bytes（[P-119](../deferred/protocol/daemon/channel.md)） |
| `urgent` | 可省，布林，預設 false；true＝急件 |

schema 還沒補：舊的待送封套 [msg-outbox](../../protocol/schemas/msg-outbox.schema.json) 是檔案投件的格式（`target_node`、`alarm_ticks`、`channel`），已不適用，列在 [README 待放入](../README.md#待放入)。鬧鐘紀錄 `.aos/alarms/` 隨鬧鐘撤（[B-624](../tick/mq.md)）。

### 送不出去的失敗紀錄

`.aos/mq/failed/<id>.req.json` 或 `<id>.resp.json`（ignore，檔名同原檔）〔使用者 2026-09-30 同意照暫定〕：`mq-post` 把送不了的那份原檔搬過來，內容是原檔的欄位再加一個 `error:{"code":"<代碼>"}`。沒有 schema。下一格 `mq-post` 開始送之前整個清掉（[B-624](../tick/mq.md)）。

### stderr 診斷行

| 行 | 意思 |
|---|---|
| `post_failed: <to> <id> <code>` | 送不了、已移除（[B-624](../tick/mq.md)） |
| `no_channel` | 本格沒有通道，什麼都沒做 |

依據：第十九批（經通道送、急件）；第二十批（系統級任務的 argv）；astra 審整理區同日定案（`aos-mq`；檔案收件、投件、鬧鐘撤出 aos）。

## P-207．加入普通設定〔建議預設，未拍板〕

行為以 [B-625](../tick/recovery.md)「改設定」為正本（持鎖、原子替換）；kernel／agent 的領域設定另見 [A-102](../../agent/configuration.md)。本條只定格式。

- **argv**：`aos-config-add [--dir <工作資料夾>] --from <source> --to <target>`；省略 `--dir` 用 cwd〔使用者 2026-10-01：node 改稱工作資料夾，旗標原叫 `--node <node_dir>`〕。取的鎖是同一把 `.aos/tick.lock`（[B-602](../tick.md)）。
- `source` 是任意可讀路徑，相對呼叫者的 cwd；`target` 是工作資料夾 `config/` 內的檔案，相對工作資料夾，不准用 `..` 或 symlink 逃出。
- 用呼叫者的帳號跑，沒有自訂環境。
- stdin 不讀；stdout 成功時印 `target`＋LF；stderr 印 `code: 說明`。
- 它不是任務表上的任務；在 tick 之外跑算外部世界（[B-602](../tick.md)）。

| 結束碼 | 意思 |
|---|---|
| `0` | 已替換，或內容相同、沒寫 |
| `1` | 寫入失敗，或參數、路徑、JSON 不合；目標仍是舊版 |
| `75` | 鎖被占（busy，特別指定的碼） |
| `125` | 前置失敗（例如有擋板檔），沒寫目標（特別指定的碼） |

不自己提交：`config/` 不在 aos 範圍（[B-630](../tick/git.md)、[B-625](../tick/recovery.md)），要留歷史就自己 `git commit`。

依據：第十九批依方案 A 縮短；第二十批（不在任務表上、沒有 git）；astra 審整理區必-5（撤掉 git 殘句）。

## P-208．收件區權限〔建議預設，未拍板〕

誰要開哪些權限以 [B-506](../../base/transport.md) 為正本（其中 LLM 與工具路線的核對、kernel 對成員的觀察權是 kernel／agent 的使用例，不是基礎規則）；本條只列權限落點。

| 對象 | 落點 |
|---|---|
| daemon | `.aos/attention/` 的寫權 |
| 工作資料夾的帳號（跑 tick 的帳號） | 根路徑可遍歷；repo 讀寫；`requests/`、`responses/` 可清理 |
| 檔案投件的程式 | 必要父目錄的 traverse；`requests/` 或 `responses/` 及其 `.tmp/` 的寫與遍歷 |
| 寄件 tick 的帳號 | 收件 tick 的 `.aos/mq/get/` 寫與遍歷，以及上層各段的 traverse（[B-614](../deferred/daemon/messaging.md)） |
| 只讀摘要的上層 | `.aos/summary/` 只授 traverse、`published.json` 只授 read（[P-307](../../protocol/messages.md)） |

共享群組與 setgid 目錄，用 helper 的固定動作 `group_create`、`group_add_member`、`chgrp`（參數見 [P-107](../deferred/protocol/daemon/provision-and-runner.md)）。cgroup 框交給工作資料夾的帳號由舊 daemon 開格前自動做，不是佈建動作（[B-605](../deferred/daemon/cgroup.md)，在暫緩區）。

依據：第十九批依方案 A 縮短。

## P-209．待決與跨篇

見 [README P-008](../../protocol/README.md#p-008)。

## P-210．預設範本與恢復前驗證〔主編補〕

- `aos node new N --template kernel` 的完整 `.aos/tasks.json`、設定與頂層建立順序，由 [kernel 任務篇](../../protocol/kernel-tasks.md) 定；agent 範本由 [agent P-715](../../protocol/agent-tasks.md) 定。
- kernel 的唯讀驗證 argv：`aos-kernel-check --node N --validate-only`。
- 恢復前驗證的通用步驟以 [B-625](../tick/recovery.md) 為正本；裝了 kernel／agent 任務時的領域驗證與建立步驟見 [A-102](../../agent/configuration.md)、[H-036](../../cli/walkthrough.md)。日常檢查與待辦標完成照 [ops P-609](../../protocol/ops.md)。

依據：第十九批依方案 A 縮短。

## P-211．aos-cg：每項一框〔使用者方向 2026-09-30，第二十批追答 8；格式為建議預設〕

普通程式，不是系統級任務。行為正本：[B-634](../tick/cg.md)；框的樹與命名見 [B-605](../deferred/daemon/cgroup.md)。

- **argv**：`aos-cg [--] <原指令…>`。不收上限參數（上限歸舊 daemon 設在工作資料夾的框，暫緩區 [B-605](../deferred/daemon/cgroup.md) 叫 node 框）。
- **框名**：本工作資料夾的框 `n-<h>` 下的 `task-<seq>-<pid>`，`seq` 取結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current.json`）的格數（沒有紀錄時用 `0`），`pid` 是 aos-cg 自己的 PID；跟 `tick` 葉並列。
- **stdin、stdout、stderr**：原樣交給原指令；aos-cg 自己只在 stderr 印 `code: 說明`，代碼有 `cgroup_unavailable`（照 B-634 沒 cgroup 時的做法跑）、`frame_not_empty`。
- **環境**：原樣交給原指令，不另加變數。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 原指令正常結束；被訊號結束時 aos-cg 用同一個訊號結束自己，讓上一層 wait 看到的是訊號 |
| `1` | 用法錯（沒有原指令）；或框清不空（`frame_not_empty`）：另建停格檔（P-213），不讓後面的項在還有人寫檔時開跑 |
| `125` | 原指令沒開起來（exec 前失敗），照 inst（特別指定的碼） |

## P-212．aos-as：切換帳號〔建議預設，未拍板〕

> **依賴暫緩區**：這條整條靠 helper（[B-303](../deferred/helper.md)）、daemon 通道與「鎖 fd 傳給任務」（[tick 暫緩區](../deferred/tick.md#暫緩b-602-完整互斥的其餘細節)），三樣都在暫緩區，現行程式沒有 `aos-as`。格式先留在正式篇，等它們回來再對。

普通程式，不是系統級任務。行為正本：[B-303](../deferred/helper.md)；`spawn_as` 的參數與限制見 [B-609](../deferred/daemon/helper-actions.md)、[P-107](../deferred/protocol/daemon/provision-and-runner.md)；runner 回報見 [P-110](../deferred/protocol/daemon/provision-and-runner.md)。

- **argv**：`aos-as <帳號> [--] <原指令…>`；帳號是名稱或非負 UID。
- **暫存 inst**：ignored 的 `.aos/jobs/as-<seq>-<pid>.json`，結束後刪掉。`seq` 取結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current.json`）的格數（沒有紀錄時用 `0`），`pid` 是 aos-as 自己的 PID。內容是一份 inst：`argv`、目前 cwd、`envs`＝`{"$opt":"clear","$val":目前的環境}` 但不含 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`（由 runner 補，[B-609](../deferred/daemon/helper-actions.md)）；stdin／stdout／stderr 都寫成繼承。
- **交給 helper 的 fd**，共 5 個（見 P-107）：

  | 順序 | fd |
  |---|---|
  | 1 | 繼承到的鎖 fd（`AOS_TICK_LOCK_FD`） |
  | 2 | 回報 pipe 的寫端 |
  | 3～5 | 〔建議預設〕自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走 |

  自己在 `aos-cg` 的 `task-*` 框裡時（有 cgroup），另帶 `frame`＝那個框；沒 cgroup 時帶了 daemon 回 `unsupported`（[B-609](../deferred/daemon/helper-actions.md)）。

- **stderr 代碼**：`not_available`（〔建議預設，未拍板〕helper 動作關閉，[B-609](../deferred/daemon/helper-actions.md)）、`no_channel`、`helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`（daemon 的錯誤碼照轉）、`result_unknown`（回應成功但 pipe 沒回報就關了）。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 照 runner 回報：正常結束回同一碼；被訊號結束時用同一個訊號結束自己 |
| `1` | 用法錯 |
| `125` | 沒開起來或不知道結果（特別指定的碼）：沒有通道變數、daemon 回錯、`result_unknown`；不寫 `exit`。`result_unknown` 時呼叫它的一方不能重跑 |

依據：〔使用者方向 2026-09-30〕第二十批追答 8。

## P-213．每項結束碼紀錄、停格檔與擋板檔〔建議預設，未拍板〕

行為正本：紀錄 [B-633](../tick.md)；停格檔與擋板檔 [B-620](../tick.md)（擋板與停格檔的機制使用者之後會詳細設計，目前是〔暫定〕）。本條只定檔名與內容。

### 結束碼紀錄

- **位置**：`.aos/tick/current.json`（本格）、`.aos/tick/last.json`（上一格），都 ignored。任務從 `$AOS_TICK_CWD/.aos/tick/current.json` 讀本格紀錄（P-203）。
- **schema**：[tick-record](../../protocol/schemas/tick-record.schema.json)。
- **寫法**：只有核心寫；每次整份重寫（暫存檔→rename），預設不 fsync。斷電後可能倒退或壞掉，不保證（[B-633](../tick.md)）。

```json
{"version":1,"seq":N,"started_at_ms":毫秒,
 "tasks":[{"id":…,"exit":碼}|{"id":…,"signal":號}],
 "ended":bool,"exit"?:0,"stopped_after"?:"<id>"}
```

| 欄位 | 約束 |
|---|---|
| `seq` | 本資料夾的格數，共用 `TickSeq`（從 1 起）。沒有紀錄的格（busy、blocked、bad_table）不佔號 |
| `tasks` | 已跑完的項，照順序；`id` 是任務表那一項的 id（沒寫 id 時是位置字串，例如 `"3"`）；每項 `exit`（0～255）與 `signal`（1～64）二選一，照實記原碼。沒跑到的不列 |
| `ended` | 照表跑完或被停格檔停下時是 true，這時必須有 `exit`；false 時不得有 `exit`、`stopped_after`。tick 中途出錯或被殺時停在 false |
| `exit` | 這格 tick 的結束碼。有紀錄收尾時 tick 一定回 0，所以只會是 `0`（busy、blocked、bad_table 不寫紀錄） |
| `stopped_after` | 被停格檔停下時，是哪一項跑完後停的，記那一項的 id；只在 `ended:true` 時可有，這時 `exit` 也是 `0` |
| `started_at_ms` | 只給人看，不參與計算 |

schema 管得到的：`exit` 只收 0、`ended` 跟 `exit`／`stopped_after` 的搭配、每項 `exit` 與 `signal` 二選一。schema 管不到、由 [validate.py](../../protocol/examples/messages/validate.py) 補查的：`stopped_after` 是 `tasks` 的最後一項。

### 停格檔與擋板檔

| 檔 | 內容 | 行為 |
|---|---|---|
| `.aos/tick/stop`（停格檔，ignored） | 任何內容都算；建議一行 UTF-8 原因，核心印在 stderr 的 `stopped:` 後面 | 只停本格，這格照樣回 0，見 [B-620](../tick.md) |
| `.aos/tick-blocked`（擋板檔，ignored） | 一行 UTF-8 原因，核心印在 stderr 的 `blocked:` 後面 | 擋之後各格（不開格、回 0），見 [B-620](../tick.md) |

範例：正例 [跑到一半](../../protocol/examples/tick/tick-record.minimal.valid.json)、[全部成功](../../protocol/examples/tick/tick-record.done.valid.json)、[被停格檔停下](../../protocol/examples/tick/tick-record.stopped-exit-0.valid.json)、[有任務失敗照樣回 0](../../protocol/examples/tick/tick-record.exit-0-with-failure.valid.json)、[沒寫 id 的位置字串](../../protocol/examples/tick/tick-record.position-id.valid.json)；反例 [同一項同時有 exit 與 signal](../../protocol/examples/tick/tick-record.exit-and-signal.invalid.json)、[ended 卻沒有 exit](../../protocol/examples/tick/tick-record.ended-without-exit.invalid.json)、[沒收場卻記了 stopped_after](../../protocol/examples/tick/tick-record.stopped-not-ended.invalid.json)、[整格回 1](../../protocol/examples/tick/tick-record.stopped-exit-1.invalid.json)、[整格回 2](../../protocol/examples/tick/tick-record.exit-2.invalid.json)、[整格回 3](../../protocol/examples/tick/tick-record.exit-3.invalid.json)；補查反例 [停在不是最後一項](../../protocol/examples/tick/tick-record.stopped-not-last.invalid.json)。
