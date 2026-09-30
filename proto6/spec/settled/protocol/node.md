# node：資料夾、任務與一格 tick

← [整理區](../README.md)｜[共用約定](../../protocol/README.md)｜行為正本：[inst](../../base/inst.md)、[tick](../tick.md)、[設定](../../agent/configuration.md)｜[使用者裁定](../../../notes/2026-09-29-verdicts.md)

本篇只定格式：資料夾裡的檔名、JSON、argv、環境變數、結束碼。行為一律以 [tick](../tick.md) 等主規格為正本，這裡寫到行為只留一句加條號。

## P-200．資料夾布局〔建議預設，未拍板〕

node 根目錄的正規化絕對路徑就是 node id。下表的名稱固定；其他內容按任務需要才建，不預建空表。kernel、agent 是「裝了哪些任務」決定的角色，不另設角色欄位。

本輪假設沒有 git（[B-632](../tick.md)）。表中「追蹤／ignore」是留給下一步 git 用的分類，本輪只當「受管狀態／暫存」的區分；下一步納入 git 時每個 node 是一個 git repo（草稿 [B-630](../tick.md)、P-205）。

| 路徑 | 用途 | 分類 |
|---|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑本 node 的 inst；選檔順序依 [inst 目標](../../base/inst.md#inst-目標檔案或資料夾) | 追蹤 |
| `.aos/tasks.json` | 任務註冊表（P-202） | 追蹤 |
| `config/` | 任務使用的正式設定；領域格式由使用它的任務定義 | 追蹤 |
| `state/` | 已消費收件、請求、結果與必要進度；子結構由各協議篇定義 | 追蹤 |
| `requests/`、`responses/` | 檔案收件區，各含發布用 `.tmp/`；由普通程式收與寫，aos 不管（[B-623](../tick.md)） | ignore |
| `work/` | 任務的暫存工作進度 | ignore |
| `.aos/jobs/<id>/` | 替成員跑工具、打 LLM 的 once 工作；`aos-as` 的暫存 inst（`as-<seq>-<pid>.json`，P-212）也放這裡 | ignore |
| `.aos/attention/` | 本 node 的待處理事項，含 daemon 發現的 node 問題 | ignore |
| `.aos/summary/` | 給上層讀的摘要，見 P-307 | `summary.json` 追蹤、`published.json` ignore |
| `.aos/mq/post/` | 要經系統訊息佇列送出的訊息，見 P-206 | 追蹤 |
| `.aos/tick.lock` | 核心的鎖檔（[B-602](../tick.md)） | ignore |
| `.aos/tick/` | 核心的結束碼紀錄 `current.json`、`last.json` 與停格檔 `stop`（[B-633](../tick.md)、[B-620](../tick.md)、P-213）；不隨還原、不被清理 | ignore |
| `.aos/tick-blocked` | 擋板檔：有它時 daemon 不開格、核心也不跑（[B-607](../daemon.md)、[B-620](../tick.md)、P-213） | ignore |
| `.aos/runner-stderr.log` | 〔暫定〕runner 診斷，daemon 每格覆寫；輪替以後再定（[P-109](daemon/provision-and-runner.md)） | ignore |
| `public/` | 可供其他 node 存取的共用空間 | 看內容 |
| `.gitignore` | 至少列出上表所有 ignore 的路徑：`/requests/`、`/responses/`、`/work/`、`/.aos/jobs/`、`/.aos/attention/`、`/.aos/tick.lock`、`/.aos/tick/`、`/.aos/tick-blocked`、`/.aos/runner-stderr.log`、`/.aos/summary/published.json` | 追蹤 |

補充：

- **收件分兩處**〔慣例；第二十批起檔案收件與投件是普通程式，aos 不管，[B-623](../tick.md)〕：請求放在被問者的 `requests/<id>.json`，回應放在發問者的 `responses/<id>.json`。
- **找 inst**：登記資料夾時先找 `.aos/inst.json`、沒有再找 `inst.json`，base 是 node 根。掛載行程的目標可以是單檔 inst（[B-613](../daemon.md)、[P-118](daemon/channel.md)），base 是該檔所在資料夾。正本見 [inst 目標](../../base/inst.md#inst-目標檔案或資料夾)。
- **鎖檔與 git 管理目錄**：鎖檔 `.aos/tick.lock` 不在 git 管理目錄（[B-602](../tick.md)）。git 管理目錄用 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾。〔下一步納入 git 時補〕巢狀 tick 的排除寫在它的 `info/exclude`、存檔點記在 git 管理目錄的 `refs/aos/marks/`（P-205 草稿），都不在工作樹。
- **事項**：待處理事項放 `.aos/attention/`，不隨還原，見 [ops](../../protocol/ops.md)。
- 不跑 `aos-tick` 的 node 不必有完整布局。

依據：第十七批（runner 診斷）、第十九批（鎖檔、單檔掛載）、第二十批（結束碼紀錄、擋板檔裁定 a＋c、aos-as）、〔使用者方向 2026-09-29〕裁定「收件分兩格」、〔使用者方向 2026-09-30〕第二十批進行順序；astra 審整理區同日定案（`.aos/mq/post/`，撤 `.aos/alarms/`）。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

- **schema**：[node-inst.schema.json](../../protocol/schemas/node-inst.schema.json) 只驗 [inst 正本](../../base/inst.md) 的原始結構。引用內容、循環、選項值與展開後的型別，仍由 runner 驗。
- **版本**：`_metainfo` 沿第 1 版，不加 `version`。頂層、metainfo、選項裡不認得的鍵照 inst 忽略，這是 P-002 的例外。
- **`user`**：只准帳號名稱或非負 UID；省略或空字串＝繼承；不吃指示詞。
- **授權與結束碼**：授權、切身分與整份 `$ref` 的身分核對依 [daemon P-108～110](daemon/provision-and-runner.md)。125／126／127 與 `exit` 的訊號編碼照正本，不改成 RPC 錯誤。

範例：[正例](../../protocol/examples/node/inst.minimal.valid.json) 跑 aos-tick；[反例](../../protocol/examples/node/inst.user_directive.invalid.json) 的 `user` 用了指示詞，不合法。

## P-202．任務註冊表〔建議預設，未拍板〕

任務表只有一個檔：`.aos/tasks.json`，schema 是 [node-tasks.schema.json](../../protocol/schemas/node-tasks.schema.json)。

```json
{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}
```

- 順序只看 `tasks` 陣列位置；`tasks` 可以是空陣列。
- 每項是 **inst 的超集**：一份 inst 加下表的欄位，也可以用整份 `$ref`。指示詞、串流、cwd、envs 照 inst 展開，base 是 node 根。
- 核心只看 `id`、inst 部分與 `user`；其餘欄位由系統級任務讀。順序、類別、`methods` 的意思與載入檢查以 [B-620](../tick.md) 為正本。

| 欄位 | 約束 |
|---|---|
| `id` | 共用 `ID`；本表唯一；跑的時候放進任務環境 `AOS_TASK_ID` |
| `kind` | `system`、`kernel`、`agent`、`custom`；〔暫定〕或自訂的「類別.名稱」：類別限 `kernel`／`agent`／`custom`，名稱是小寫英數與 `_`、`-`（例如 `agent.review`）。`system` 標記系統級任務（[B-626](../tick.md)），只是標記，不驗順序；`system.x` 不接受 |
| `methods` | 可省，預設空陣列；給檔案收件程式讀的宣告：本任務處理哪些檔案請求 method（如 `agent.say`）。同一項內重複 schema 擋得到；跨項重複與意思由收件程式定，aos 不管（[B-623](../tick.md)） |
| `user` | 可省，照 [inst](../../base/inst.md) 的 `user`；省略＝tick 的有效帳號。帶了而且跟 tick 的帳號不同時，那一項回 125、不切帳號；要切帳號就在 argv 包 `aos-as`（P-212、[B-620](../tick.md)） |

**不認得的鍵照收、核心忽略**（P-007；schema 不設 `additionalProperties:false`）。任務表先只定上表這些基本欄位；第十九批的 `group`、`needs` 不列入 schema，寫了就是陌生鍵。前置改用 `aos-needs`（P-204、[B-621](../tick.md)），組下一步納入 git 時再定（草稿 P-205）。kernel、agent、custom 類任務的逾時與取消延後（[P-008](../../protocol/README.md#p-008)）。

誰驗哪些欄位見 [B-620](../tick.md)「誰驗什麼」：核心只驗四件事，其餘 schema 限制由恢復前驗證擋。

範例：

- 正例：[最小](../../protocol/examples/node/tasks.minimal.valid.json)（登記普通程式）、[帶 `user`](../../protocol/examples/node/tasks.user.valid.json)（格式照收；跟 tick 帳號不同時那一項回 125）、[包 `aos-as`](../../protocol/examples/node/tasks.as.valid.json)（用別的帳號跑）、[陌生鍵](../../protocol/examples/node/tasks.unknown-key.valid.json)（帶 `group`、`needs` 照收）、[標準任務表範本](../../protocol/examples/node/tasks.template.valid.json)（照 [B-629](../tick.md) 本輪沒有 git 的順序）、[methods](../../protocol/examples/node/tasks.methods.valid.json)（宣告一個 method）、[自訂種類](../../protocol/examples/node/tasks.custom-kind.valid.json)（`agent.review`）。
- 反例：[同一項內重複宣告 method](../../protocol/examples/node/tasks.methods-duplicate.invalid.json)、[自訂 `system.x`](../../protocol/examples/node/tasks.custom-kind.invalid.json)。

依據：第十七批（`methods`）、〔暫定〕第十八批（自訂種類）、第十九批（撤 `user` 的永遠禁止）、〔使用者方向 2026-09-30〕第二十批（只定基本欄位、疑點裁定 6）。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

### argv

`aos-tick [--node <node>]`

- 省略 `--node` 就用目前目錄。
- `<node>` 可以是資料夾，也可以是它的 `.aos/inst.json` 或 `inst.json`，一律正規化成資料夾（[B-602](../tick.md)）；tick 在那裡跑，cwd 就是管轄區。
- 指定時必須是 P-002 的 node id；不往父目錄猜找 repo。
- tick 本身不找 inst，也不看自己在哪個 cgroup（[B-627](../tick.md)）。
- 用資料夾當執行目標時，inst 只要 `{"argv":["aos-tick"]}`，預設 cwd 正好是 node 根。直接執行 `.aos/inst.json` 檔時 base 不同，要明寫 `cwd:".."` 或 `--node`。
- 第十九批的 `--check`（全掛檢查）撤。

### tick 自己的介面

| 介面 | 約定 |
|---|---|
| stdin | 不讀；inst 預設 `/dev/null` |
| stdout | 原樣轉送任務的 stdout，不另混入成功 JSON |
| stderr | 任務的 stderr 原樣轉送；tick 自己另印 `code: 說明`，需要時附 task id、退出碼或 signal |
| 讀寫 | 讀 `.aos/tasks.json`、持鎖、寫 `.aos/tick/` 的紀錄、開格刪殘留的停格檔、每項後查停格檔（P-213）。送收訊息是系統級任務的事（[B-629](../tick.md)）；任務自己直接讀寫檔案 |
| 身分 | tick 自己不切 UID；直接呼叫也不會替你取得 inst 的身分 |

核心自己的 stderr 代碼：

| 代碼 | 什麼時候 |
|---|---|
| `config_invalid` | 任務表不合法 |
| `user_mismatch` | 某項的 `user` 跟 tick 帳號不同 |
| `record_unwritable` | 本格結束碼紀錄寫不進、失效（[B-633](../tick.md)） |
| `record_unreadable` | 舊的兩份紀錄都讀不懂 |
| `stopped` | 被停格檔停下；後面附停格檔裡的原因 |
| `blocked` | 有擋板檔；後面附擋板檔裡的原因 |

### 每項任務怎麼跑

| 介面 | 約定 |
|---|---|
| 身分 | 沿用 tick 的有效 UID、群組與資源範圍；帶了別的 `user` 的那一項回 125，要換帳號包 `aos-as`（P-212） |
| cwd／argv | 照本項 inst 展開後執行；cwd 沒給時是 node 根 |
| stdin | 預設 `/dev/null`；可用本項 inst 的 stdin 重導向 |
| stdout／stderr | 照 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不把輸出文字當完成證據 |
| 環境 | 繼承 tick 的環境（含 daemon 開的格才有的通道變數，[B-612](../daemon.md)），加上下表的變數，再照 inst 套用 `envs`。這些變數都不是授權證據 |

tick 給任務的環境變數。整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`：

| 變數 | 值 |
|---|---|
| `AOS_NODE_DIR` | node id |
| `AOS_TICK_LOCK_FD` | 鎖 fd 的號碼（[B-602](../tick.md)） |
| `AOS_TICK_RECORD` | `.aos/tick/current.json` 的絕對路徑；本格紀錄失效後開的項不設（[B-633](../tick.md)） |
| `AOS_TASK_ID` | 任務表該項的 `id` 字串，原樣 |
| `AOS_TASK_INDEX` | 這一項在 `tasks` 陣列的位置，十進位，從 0 起 |

其他：

- 沒有設定需求的程式不必讀任何環境變數，也不必寫回應封套；`true`、腳本與既有程式都能直接當任務。
- 任務直接開檔讀設定；改設定的時機與「tick 裡不改 `config/`」的軟性原則見 [A-102](../../agent/configuration.md)。
- key 不由 tick 放進 argv 或任務環境；daemon／runner 的環境來源照[身分篇](../../base/identity-resources.md)，inst 的 `envs` 照正本。
- 鎖（`.aos/tick.lock`、`AOS_TICK_LOCK_FD`）的行為以 [B-602](../tick.md) 為正本；每項一框（`aos-cg`）下一步納入 cgroup 時補（草稿 P-211）。

### 結束碼

| tick 結束碼 | 意思 |
|---|---|
| `0` | 全部任務成功（含沒有工作、沒有變動）；只表示本格完成 |
| `1` | 至少一項失敗（非零、訊號、回 125 都算）；或某項建了停格檔、後面沒跑；或有擋板檔、一項都沒跑也沒寫紀錄（[B-620](../tick.md)） |
| `2` | argv 或任務表不合法；還沒開任何任務 |
| `75` | 鎖被占用；沒開任務、沒寫紀錄，也不在程式內重試 |

- **停掉本格靠停格檔 `.aos/tick/stop`，不靠結束碼**；被停下的格為什麼回 1 見 [B-620](../tick.md)。
- 第十九批「標準配備」的 3（提交故障）與 125（格首看到擋板）撤。
- 父程序看 wait 狀態辨識 tick 被訊號結束，不把 `128+N` 當訊號證據。inst 的文字 `exit` 編碼仍照 P-201。
- kernel、agent、custom 類任務的逾時與取消延後（[P-008](../../protocol/README.md#p-008)）。

依據：〔使用者方向 2026-09-30〕第十九批（argv 與正規化）、第二十批（環境變數命名、撤 `--check`）、第二十批疑點裁定 1（改：停格靠檔案）。

## P-204．aos-needs〔使用者方向 2026-09-29；第二十批改寫〕

任務的成敗怎麼算以 [B-620](../tick.md)「跑每一項」為正本；要停掉本格用停格檔（P-213）。

**`aos-needs`**〔建議預設，未拍板〕：普通程式，前置沒成功就不跑原指令。行為以 [B-621](../tick.md) 為正本。

- argv：`aos-needs <前置任務 id…> -- <原指令…>`；前置至少一個，`--` 必填。
- 讀 `AOS_TICK_RECORD`；每個前置都在紀錄的 `tasks` 裡而且 `exit:0`，才 exec 原指令。
- stdin、stdout、stderr 原樣交給原指令。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 前置都成功，已 exec 原指令 |
| `2` | 用法錯（沒有前置、少了 `--` 或原指令） |
| `125` | 沒跑。stderr 印 `needs_unmet: <id>`（前置不在紀錄或不是 0），或 `no_record`（沒有 `AOS_TICK_RECORD` 或讀不到） |

## P-205．〔下一步納入〕aos-git：開格、存檔點、收尾

〔使用者方向 2026-09-30，第二十批進行順序〕本條是草稿，**不是現行規則**；下一步把 git 納入時再定。本條只定格式。行為草稿：

- 開格與收尾、存檔點與組：[B-630](../tick.md)
- 管理範圍、落盤與故障，合併提交與 submodule：[B-622](../tick.md)
- 沒有 git 時：[B-632](../tick.md)

格式草稿：

- **argv**：`aos-git open`、`aos-git mark`、`aos-git close`，都在 node 根（cwd）跑、不收其他參數；三者都是系統級任務（`kind:"system"`）。在 tick 內靠繼承的鎖（B-602）；不在 tick 內時自己取同一把鎖，拿不到回 75。
- **git 參數**：aos 每次呼叫 git 都帶 `-c core.fsync=committed,reference`（最低 git 2.36）；作者用 repo 設定，不互動、不執行 git hooks。
- **commit 訊息**：`aos-tick <seq>`，`seq` 是結束碼紀錄的格數（P-213）；每格最多一個。〔第二十批〕第十九批的 `aos-tick group <first>..<last>`、`aos-tick unclaimed`、`aos-tick adopt` 撤。沒有紀錄時 `close` 不提交（B-630）。
- **存檔點**：暫存提交，記在 git 管理目錄的 `refs/aos/marks/<任務 id>`（任務 id 取 `AOS_TASK_ID`）；不在任何分支上，`close` 用完就刪，`open` 開格先清掉殘留的。
- **擋板檔**〔第十九批從 git 管理目錄搬出，沒有 git 也要用〕：`.aos/tick-blocked`，內容是 UTF-8 原因。
- **stderr 代碼**：`tick_blocked`、`no_git`、`git_failed`（附 git 的錯誤行）、`record_missing`。
- **結束碼**：`0` 成功（`close` 有組失敗、還原成功也是 0；沒 git 時照 B-632 也是 0）；`2` 用法錯；`75` 不在 tick 內又拿不到鎖。看到擋板，或還原、存檔點、commit、刪原件失敗時建停格檔（P-213）、回 1，並寫擋板（看到擋板時不重寫）。

〔第二十批疑點裁定 5〕第十九批的完成紀錄 `.aos/journal/<seq>.json`、`sent/`、`discarded/` 與 `node-journal` schema 撤，由結束碼紀錄取代（P-213、[B-632](../tick.md)）。

## P-206．系統訊息佇列 aos-mq 與發摘要〔使用者方向 2026-09-30，astra 審整理區同日定案〕

本條只定檔案格式與 argv。行為正本：取 [B-623](../tick.md)；送與發摘要 [B-624](../tick.md)。檔案收件區 `requests/`、`responses/` 的格式屬普通程式，不在本條。

### argv 與結束碼〔建議預設〕

| 程式 | 任務 id（範本） | 做什麼 |
|---|---|---|
| `aos-mq get` | `mq-get` | 用 `node.take` 取本 node 佇列裡的訊息，取到空為止 |
| `aos-mq post` | `mq-post` | 把 `.aos/mq/post/` 的訊息一件一件用 `node.send` 送出 |
| `aos-publish` | `summary` | 發布摘要 |

三者都是系統級任務，都在 node 根（cwd）跑、不收其他參數。在 tick 內靠繼承的鎖；不在 tick 內時自己取同一把鎖，拿不到回 75。

| 結束碼 | 意思 |
|---|---|
| `0` | 成功（含沒事做、本格沒有通道） |
| `1` | 有件處理失敗（例如 `node.take` 回錯、發布摘要失敗、寫檔 I/O 錯） |
| `2` | 用法錯 |
| `75` | 不在 tick 內又拿不到鎖 |

### 要送的訊息

`.aos/mq/post/<id>.json`（追蹤），`<id>` 是訊息的請求 ID。〔暫定〕形狀是 `node.send` 的 params 去掉 `token`、加 `version`：

```json
{"version":1,"to":"/目標 node","message":{...},"urgent"?:true}
```

| 欄位 | 約束 |
|---|---|
| `version` | 必填，1 |
| `to` | 必填；收件 tick 的 node id |
| `message` | 必填；一份請求物件（[P-301](../../protocol/messages.md)），ID 要跟檔名相同；序列化後最多 196608 bytes（[P-119](daemon/channel.md)） |
| `urgent` | 可省，布林，預設 false；true＝急件 |

schema 還沒補：舊的待送封套 [msg-outbox](../../protocol/schemas/msg-outbox.schema.json) 是檔案投件的格式（`target_node`、`alarm_ticks`、`channel`），已不適用，列在 [README 待放入](../README.md#待放入)。鬧鐘紀錄 `.aos/alarms/` 隨鬧鐘撤（[B-624](../tick.md)）。

### stderr 診斷行

| 行 | 意思 |
|---|---|
| `post_failed: <to> <id> <code>` | 送不了、已移除（[B-624](../tick.md)） |
| `no_channel` | 本格沒有通道，什麼都沒做 |

依據：第十九批（經通道送、急件）；第二十批（系統級任務的 argv）；astra 審整理區同日定案（`aos-mq`；檔案收件、投件、鬧鐘撤出 aos）。

## P-207．加入普通設定〔建議預設，未拍板〕

行為以 [B-625](../tick.md)「改設定」為正本（本輪沒有 git：持鎖、原子替換）；kernel／agent 的領域設定另見 [A-102](../../agent/configuration.md)。本條只定格式。

- **argv**：`aos-config-add [--node <node_dir>] --from <source> --to <target>`；省略 `--node` 用 cwd。
- `source` 是任意可讀路徑，相對呼叫者的 cwd；`target` 是 `node/config/` 內的檔案，相對 node，不准用 `..` 或 symlink 逃出。
- 用呼叫者的帳號跑，沒有自訂環境。
- stdin 不讀；stdout 成功時印 `target`＋LF；stderr 印 `code: 說明`。
- 它不是任務表上的任務；在 tick 之外跑算外部世界（[B-602](../tick.md)）。

| 結束碼 | 意思 |
|---|---|
| `0` | 已替換，或內容相同、沒寫 |
| `1` | 寫入失敗；目標仍是舊版 |
| `2` | 參數、路徑或 JSON 不合 |
| `75` | 鎖被占（busy） |
| `125` | 前置失敗（例如有擋板檔），沒寫目標 |

〔下一步納入 git 時補〕寫完提交（訊息 `aos-config-add <target>`）、提交或還原故障回 3 並寫擋板（[tick](../tick.md) 篇末 B-622）。

依據：第十九批依方案 A 縮短；第二十批（不在任務表上、沒有 git）；astra 審整理區必-5（撤掉 git 殘句）。

## P-208．收件區權限〔建議預設，未拍板〕

誰要開哪些權限以 [B-506](../../base/transport.md) 為正本（其中 LLM 與工具路線的核對、kernel 對成員的觀察權是 kernel／agent 的使用例，不是基礎規則）；本條只列權限落點。

| 對象 | 落點 |
|---|---|
| daemon | `.aos/attention/` 的寫權 |
| node 帳號 | 根路徑可遍歷；repo 讀寫；`requests/`、`responses/` 可清理 |
| 檔案投件的程式 | 必要父目錄的 traverse；`requests/` 或 `responses/` 及其 `.tmp/` 的寫與遍歷 |
| 只讀摘要的上層 | `.aos/summary/` 只授 traverse、`published.json` 只授 read（[P-307](../../protocol/messages.md)） |

共享群組與 setgid 目錄，用 helper 的固定動作 `group_create`、`group_add_member`、`chgrp`（參數見 [P-107](daemon/provision-and-runner.md)）。〔下一步納入 cgroup 時補〕交出框用 `cgroup_delegate`，本輪回 `unsupported`。

依據：第十九批依方案 A 縮短。

## P-209．待決與跨篇

見 [README P-008](../../protocol/README.md#p-008)。

## P-210．預設範本與恢復前驗證〔主編補〕

- `aos node new N --template kernel` 的完整 `.aos/tasks.json`、設定與頂層建立順序，由 [kernel 任務篇](../../protocol/kernel-tasks.md) 定；agent 範本由 [agent P-715](../../protocol/agent-tasks.md) 定。
- kernel 的唯讀驗證 argv：`aos-kernel-check --node N --validate-only`。
- 恢復前驗證的通用步驟以 [B-625](../tick.md) 為正本；裝了 kernel／agent 任務時的領域驗證與建立步驟見 [A-102](../../agent/configuration.md)、[H-036](../../cli/walkthrough.md)。日常檢查與待辦標完成照 [ops P-609](../../protocol/ops.md)。

依據：第十九批依方案 A 縮短。

## P-211．〔下一步納入〕aos-cg：每項一框

〔使用者方向 2026-09-30，第二十批進行順序〕本條是草稿，**不是現行規則**；下一步把 cgroup 納入時再定。行為草稿：[B-202](../../base/execution.md)；框的命名與委派見 daemon 篇末「[下一步納入：cgroup](../daemon.md#下一步納入cgroup非現行規則)」。〔使用者方向 2026-09-30，第二十批追答 8〕它是普通程式，不是系統級任務。

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

普通程式，不是系統級任務。行為正本：[B-303](../helper.md)；`spawn_as` 的參數與限制見 [B-609](../daemon.md)、[P-107](daemon/provision-and-runner.md)；runner 回報見 [P-110](daemon/provision-and-runner.md)。

- **argv**：`aos-as <帳號> [--] <原指令…>`；帳號是名稱或非負 UID。
- **暫存 inst**：ignored 的 `.aos/jobs/as-<seq>-<pid>.json`，結束後刪掉。`seq` 取結束碼紀錄的格數（沒有紀錄時用 `0`），`pid` 是 aos-as 自己的 PID。內容是一份 inst：`argv`、目前 cwd、`envs`＝`{"$opt":"clear","$val":目前的環境}` 但不含 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`（由 runner 補，[B-609](../daemon.md)）；stdin／stdout／stderr 都寫成繼承。
- **交給 helper 的 fd**，共 5 個（見 P-107）：

  | 順序 | fd |
  |---|---|
  | 1 | 繼承到的鎖 fd（`AOS_TICK_LOCK_FD`） |
  | 2 | 回報 pipe 的寫端 |
  | 3～5 | 〔建議預設〕自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走 |

  〔下一步納入 cgroup 時補〕自己在 `aos-cg` 的 `task-*` 框裡時，另帶 `frame`＝那個框。

- **stderr 代碼**：`no_channel`、`helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`（daemon 的錯誤碼照轉）、`result_unknown`（回應成功但 pipe 沒回報就關了）。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 照 runner 回報：正常結束回同一碼；被訊號結束時用同一個訊號結束自己 |
| `2` | 用法錯 |
| `125` | 沒開起來或不知道結果：沒有通道變數、daemon 回錯、`result_unknown`；不寫 `exit`。`result_unknown` 時呼叫它的一方不能重跑 |

依據：〔使用者方向 2026-09-30〕第二十批追答 8。

## P-213．每項結束碼紀錄、停格檔與擋板檔〔建議預設，未拍板〕

行為正本：紀錄 [B-633](../tick.md)；停格檔與擋板檔 [B-620](../tick.md)（擋板檔在 daemon 那側見 [B-607](../daemon.md)）。本條只定檔名與內容。

### 結束碼紀錄

- **位置**：`.aos/tick/current.json`（本格）、`.aos/tick/last.json`（上一格），都 ignored。任務環境 `AOS_TICK_RECORD` 是 `current.json` 的絕對路徑。
- **schema**：[node-tick-record](../../protocol/schemas/node-tick-record.schema.json)。
- **寫法**：只有核心寫；每次整份重寫（暫存檔→rename）。哪幾步要 fsync、寫不進時怎麼辦，見 [B-633](../tick.md)。

```json
{"version":1,"seq":N,"started_at_ms":毫秒,
 "tasks":[{"id":…,"exit":碼}|{"id":…,"signal":號}],
 "ended":bool,"exit"?:碼,"stopped_after"?:"<id>"}
```

| 欄位 | 約束 |
|---|---|
| `seq` | 本 node 的格數，共用 `TickSeq`（從 1 起） |
| `tasks` | 已跑完的項，照順序；`id` 是任務表該項的 `id` 字串；每項 `exit`（0～255）與 `signal`（1～64）二選一。沒跑到的不列 |
| `ended` | 跑完、被停格檔停下或表壞時是 true，這時必須有 `exit`；false 時不得有 `exit`、`stopped_after` |
| `exit` | 這格 tick 的結束碼，只會是 `0`、`1`、`2`（75 不寫紀錄）。`2` 時 `tasks` 是空的 |
| `stopped_after` | 被停格檔停下時，是哪一項跑完後停的，記那一項的 `id` 字串；只在 `ended:true` 時可有，這時 `exit` 必須是 `1` |
| `started_at_ms` | 只給人看，不參與計算 |

schema 管得到的：`exit` 只收 0／1／2、有 `stopped_after` 時 `exit` 是 1、`exit` 2 時沒有任務。schema 管不到、由 [validate.py](../../protocol/examples/messages/validate.py) 補查的：`stopped_after` 是 `tasks` 的最後一項；`exit` 0 時每項都是 `exit:0`；`exit` 1 時有失敗的項或有 `stopped_after`。

### 停格檔與擋板檔

| 檔 | 內容 | 行為 |
|---|---|---|
| `.aos/tick/stop`（停格檔，ignored） | 任何內容都算；建議一行 UTF-8 原因，核心印在 stderr 的 `stopped:` 後面 | 只停本格，見 [B-620](../tick.md) |
| `.aos/tick-blocked`（擋板檔，ignored） | 一行 UTF-8 原因，核心印在 stderr 的 `blocked:` 後面 | 擋之後各格，見 [B-620](../tick.md)、[B-607](../daemon.md) |

範例：正例 [跑到一半](../../protocol/examples/node/tick-record.minimal.valid.json)、[全部成功](../../protocol/examples/node/tick-record.done.valid.json)、[被停格檔停下](../../protocol/examples/node/tick-record.ended.valid.json)；反例 [同一項同時有 exit 與 signal](../../protocol/examples/node/tick-record.exit-and-signal.invalid.json)、[ended 卻沒有 exit](../../protocol/examples/node/tick-record.ended-without-exit.invalid.json)、[沒收場卻記了 stopped_after](../../protocol/examples/node/tick-record.stopped-not-ended.invalid.json)、[整格回 3](../../protocol/examples/node/tick-record.exit-3.invalid.json)、[停下卻回 0](../../protocol/examples/node/tick-record.stopped-exit-0.invalid.json)、[表壞卻有任務](../../protocol/examples/node/tick-record.table-invalid-with-tasks.invalid.json)；補查反例 [停在不是最後一項](../../protocol/examples/node/tick-record.stopped-not-last.invalid.json)、[有任務失敗卻回 0](../../protocol/examples/node/tick-record.exit-0-with-failure.invalid.json)。
