# 暫緩區：tick 協議先不做的條

← [暫緩區](../README.md)｜[tick 暫緩區](../tick.md)｜[現行 tick 協議](../../protocol/tick.md)｜[慣例](../../conventions.md)

> **這篇整篇在暫緩區**（2026-10-01）。[tick 協議](../../protocol/tick.md)裡先不做的條（P-207 整條、P-206 的 `aos-publish` 那列、P-212 `aos-as` 整條、P-204 `aos-tick-check-task` 整條、P-205 `aos-git` 整條、P-206 `aos-mq` 整條）搬到這裡，原文照留，條號保留、不重用。行為那側見 [tick 暫緩區](../tick.md)。

## P-207．加入普通設定〔建議預設，未拍板〕

> **暫緩**（2026-10-01）：使用者 2026-10-01 裁定 `aos-config-add` 搬暫緩區。它是 2026-09-29 規劃、從沒寫過程式的指令。行為那段見 [tick 暫緩區「暫緩：B-625 加入普通設定」](../tick.md#暫緩b-625-加入普通設定aos-config-add)。下面原文照 2026-10-01 搬家前的樣子留著，結束碼 75、125 回來時要照 [C-08](../../conventions.md) 重看。

行為以 B-625「改設定」為正本（搬家後在 [tick 暫緩區](../tick.md#暫緩b-625-加入普通設定aos-config-add)）（持鎖、原子替換）；kernel／agent 的領域設定另見 [A-102](../../../agent/configuration.md)。本條只定格式。

- **argv**：`aos-config-add [--dir <工作資料夾>] --from <source> --to <target>`；省略 `--dir` 用 cwd〔使用者 2026-10-01：node 改稱工作資料夾，旗標原叫 `--node <node_dir>`〕。取的鎖是同一把 `.aos/tick.lock`（[B-602](../../tick.md)）。
- `source` 是任意可讀路徑，相對呼叫者的 cwd；`target` 是工作資料夾 `config/` 內的檔案，相對工作資料夾，不准用 `..` 或 symlink 逃出。
- 用呼叫者的帳號跑，沒有自訂環境。
- stdin 不讀；stdout 成功時印 `target`＋LF；stderr 印 `code: 說明`。
- 它不是任務表上的任務；在 tick 之外跑算外部世界（[B-602](../../tick.md)）。

| 結束碼 | 意思 |
|---|---|
| `0` | 已替換，或內容相同、沒寫 |
| `1` | 寫入失敗，或參數、路徑、JSON 不合；目標仍是舊版 |
| `75` | 鎖被占（busy，特別指定的碼） |
| `125` | 前置失敗（例如有擋板檔），沒寫目標（特別指定的碼） |

不自己提交：`config/` 不在 aos 範圍（[B-630](../git.md)、[B-625](../../tick/recovery.md)），要留歷史就自己 `git commit`。

依據：第十九批依方案 A 縮短；第二十批（不在任務表上、沒有 git）；astra 審整理區必-5（撤掉 git 殘句）。

## 暫緩：P-206 aos-publish 那列（發摘要）

> **暫緩**（2026-10-01）：使用者 2026-10-01 第五批裁定 `aos-publish` 搬暫緩區，總結這一格成 JSON 的 `aos-summarize` 也不做。行為那段見 [tick 暫緩區「暫緩：B-624 發布摘要」](../tick.md#暫緩b-624-發布摘要aos-publish)。原條 [P-206](../../protocol/tick.md) 的 `aos-mq get`／`post` 還在正式篇。條號保留、不重用。

原文（2026-10-01 搬家前，P-206「argv 與結束碼」表的那一列與相關句）：

| 程式 | 任務 id（範本） | 做什麼 |
|---|---|---|
| `aos-publish` | `summary` | 發布摘要 |

- 原文跟 `aos-mq` 共用一段：「三者都是系統級任務，都在工作資料夾（cwd）跑、不收其他參數。在 tick 內靠繼承的鎖；不在 tick 內時自己取同一把鎖，拿不到回 75。」結束碼 `1` 包含「發布摘要失敗」。回來時要照 [C-08](../../conventions.md) 重看 75。
- 發布檔 `published.json` 的格式與權限在 [P-307](../../../protocol/messages.md)（整理區外，就地標了暫緩）；收件區權限 P-208 的「只讀摘要的上層」那列也跟它有關。

## P-212．aos-as：切換帳號〔建議預設，未拍板〕

> **暫緩**（2026-10-01 第十三批）〔使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」〕：原文照 2026-10-01 搬家前的樣子留著，條號保留、不重用。它靠 helper（[B-303](../helper.md)）、daemon 通道與「鎖 fd 傳給任務」（[tick 暫緩區](../tick.md#暫緩b-602-完整互斥的其餘細節)），三樣都在暫緩區。現行切帳號只在 daemon 設定檔做（帳號模組 `modules.account`，[plan m3m 模組五](../../../../plan/m3m-daemon-modules/06-模組五-帳號.md#模組五帳號modulesaccount)），單位是 daemon 的一項，不在一格裡面中途換。

普通程式，不是系統級任務。行為正本：[B-303](../helper.md)；`spawn_as` 的參數與限制見 [B-609](../daemon/helper-actions.md)、[P-107](../protocol/daemon/provision-and-runner.md)；runner 回報見 [P-110](../protocol/daemon/provision-and-runner.md)。

- **argv**：`aos-as <帳號> [--] <原指令…>`；帳號是名稱或非負 UID。
- **暫存 inst**：ignored 的 `.aos/jobs/as-<seq>-<pid>.json`，結束後刪掉。`seq` 取結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current/record.json`）的格數（沒有紀錄時用 `0`），`pid` 是 aos-as 自己的 PID。內容是一份 inst：`argv`、目前 cwd、`envs`＝`{"$opt":"clear","$val":目前的環境}` 但不含 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`（由 runner 補，[B-609](../daemon/helper-actions.md)）；stdin／stdout／stderr 都寫成繼承。
- **交給 helper 的 fd**，共 5 個（見 P-107）：

  | 順序 | fd |
  |---|---|
  | 1 | 繼承到的鎖 fd（`AOS_TICK_LOCK_FD`） |
  | 2 | 回報 pipe 的寫端 |
  | 3～5 | 〔建議預設〕自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走 |

  自己在 `aos-cg` 的 `task-*` 框裡時（有 cgroup），另帶 `frame`＝那個框；沒 cgroup 時帶了 daemon 回 `unsupported`（[B-609](../daemon/helper-actions.md)）。

- **stderr 代碼**：`not_available`（〔建議預設，未拍板〕helper 動作關閉，[B-609](../daemon/helper-actions.md)）、`no_channel`、`helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`（daemon 的錯誤碼照轉）、`result_unknown`（回應成功但 pipe 沒回報就關了）。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 照 runner 回報：正常結束回同一碼；被訊號結束時用同一個訊號結束自己 |
| `1` | 用法錯 |
| `125` | 沒開起來或不知道結果（特別指定的碼）：沒有通道變數、daemon 回錯、`result_unknown`；不寫 `exit`。`result_unknown` 時呼叫它的一方不能重跑 |

依據：〔使用者方向 2026-09-30〕第二十批追答 8。

## P-204．aos-tick-check-task〔使用者方向 2026-09-29；第二十批改寫；使用者 2026-10-01 第五批改寫〕

> **暫緩**（2026-10-01 第十六批）〔使用者 2026-10-01 第十六批追答：「6.aos-tick-check-task這個先放進暫緩。」〕原文照搬家前的樣子留著；裡面的停格檔 `tick/stop` 已改名 `tick/tasks-blocked`（P-213），回來時要照新規定重寫。

任務的成敗怎麼算以 [B-620](../../tick.md)「跑每一項」為正本；要停掉本格用停格檔（P-213）。

**`aos-tick-check-task`**〔使用者 2026-10-01〕：普通程式，自己是任務表上的一項，檢查指定的項有沒有跑好，沒跑好就建停格檔。行為以 [B-621](../tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task) 為正本。原本的包裝 `aos-needs <前置…> -- <原指令…>`（回 125）2026-10-01 由它取代。

- argv：`aos-tick-check-task [<任務 id…>]`；不寫 id＝檢查本格到目前為止跑過的每一項。不包別的指令。
- 讀本格紀錄 `$AOS_TICK_CWD/<狀態資料夾>/tick/current/`（P-213；展開 `record.json` 的 `$ref` 後看 `tasks`；狀態資料夾照 `AOS_DIRNAME`，[C-09](../../conventions.md)）。紀錄裡的 `id` 跟參數比字串。
- 〔使用者 2026-10-01 第八批：紀錄只記不是 0 的〕寫了 id：有任一個出現在紀錄的 `tasks`（失敗清單）裡＝建停格檔 `<狀態資料夾>/tick/stop`（P-213），內容一行原因，建議 `check_failed: <id>`；都沒出現＝當成功、什麼都不做（不分辨「還沒跑」，照 POC 默認一切正常，使用者把它排在那些項後面）。不寫 id：`tasks` 不是空的就建停格檔，空的就什麼都不做。
- stdin 不讀、stdout 不印。

| 結束碼 | 意思 |
|---|---|
| `0` | 檢查完：都跑好了（沒動作），或有沒跑好的、已建停格檔——停格是預料之中（[C-08](../../conventions.md)） |
| `1` | 自己的錯：沒有 `AOS_TICK_CWD`、紀錄讀不到等；照 POC 總原則默認正常，出事讓程式自然丟錯 |

## P-205．aos-git：開格、存檔點、收尾〔使用者方向 2026-09-30；格式為建議預設〕

> **暫緩**（2026-10-01 第十七批）〔使用者 2026-10-01 第十七批：「git這塊先不要進範本。」〕原文照搬家前的樣子留著。

本條只定格式。行為正本：開格、存檔點、收尾與 aos 範圍 [B-630](../git.md)；能不能用、呼叫參數、固定排除、故障 [B-622](../git.md)；沒有 git 時 [B-632](../git.md)。

- **argv**：三者都是系統級任務（`kind:"system"`），都在工作資料夾（cwd）跑。

| argv | 做什麼 |
|---|---|
| `aos-git open` | 上一格沒正常收尾就還原；清殘留；打本格第一個存檔點 |
| `aos-git mark [<路徑…>]` | 打存檔點；剛結束那組有失敗就先還原。帶路徑＝把使用者任務自己的檔加進 aos 範圍，從這點起到本格結束；路徑相對工作資料夾〔使用者 2026-09-30 同意照暫定〕。`AOS_DIRNAME` 空字串時整個工作資料夾本來就在 aos 範圍，帶不帶路徑都一樣（[B-630](../git.md)） |
| `aos-git close` | 處理最後一組、提交、刪本格存檔點 |

- **在 tick 內**：靠繼承的鎖。不在 tick 內回 125、印 `not_in_tick`，不自己取鎖。這個判法靠「鎖 fd 傳給任務」，那段在[暫緩區](../tick.md#暫緩b-602-完整互斥的其餘細節)；最簡鎖不傳 fd，回來之前還沒有判法（[B-622](../git.md)）。
- **git 參數**（每次呼叫都帶，[B-622](../git.md)）：`-c core.fsync=committed,reference`（存檔點改帶 `core.fsync=none`）、`-c gc.auto=0`、`-c maintenance.auto=false`、`-c core.hooksPath=/dev/null`、`-c commit.gpgSign=false`、`-c safe.directory=<工作資料夾>`；呼叫前清掉繼承的 `GIT_*`。最低 git 2.36。
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

〔第二十批疑點裁定 5〕第十九批的完成紀錄 `.aos/journal/<seq>.json`、`sent/`、`discarded/` 與 `node-journal` schema 撤，由結束碼紀錄取代（P-213、[B-632](../git.md)）。

## P-206．系統訊息佇列 aos-mq 與發摘要〔使用者方向 2026-09-30，astra 審整理區同日定案〕

> **暫緩**（2026-10-01 第十八批）〔使用者 2026-10-01 第十八批：「1. 都按你建議 2.好 3.對，我就不想了。」〕原文照搬家前的樣子留著（`aos-publish` 那列第五批已另搬，見本篇「暫緩：P-206 aos-publish 那列」）。

本條只定檔案格式與 argv。行為正本：取 [B-623](../mq.md)；送 [B-624](../mq.md)。**發摘要 `aos-publish` 那列 2026-10-01 搬到[暫緩區](tick.md#暫緩p-206-aos-publish-那列發摘要)**〔使用者 2026-10-01 第五批〕，標題的「與發摘要」只是舊名，條號不變。佇列裡的訊息可以是請求或回應物件〔使用者方向 2026-09-30，修正輪暫定的裁定〕。檔案收件區 `requests/`、`responses/` 的格式屬普通程式，不在本條。

### argv 與結束碼〔建議預設〕

| 程式 | 任務 id（範本） | 做什麼 |
|---|---|---|
| `aos-mq get` | `mq-get` | 用 `node.take` 取本工作資料夾佇列裡的訊息，取到空為止 |
| `aos-mq post` | `mq-post` | 把 `.aos/mq/post/` 的訊息一件一件用 `node.send` 送出 |

兩者都是系統級任務，都在工作資料夾（cwd）跑、不收其他參數。在 tick 內靠繼承的鎖；不在 tick 內時自己取同一把鎖，拿不到回 75。「在不在 tick 內」靠暫緩區的「鎖 fd 傳給任務」（[tick 暫緩區](../tick.md#暫緩b-602-完整互斥的其餘細節)）；最簡鎖下，任務在 tick 內去取鎖一定拿不到，這段要等它回來再對。

| 結束碼 | 意思 |
|---|---|
| `0` | 成功（含沒事做、本格沒有通道） |
| `1` | 有件處理失敗（例如 `node.take` 回錯、寫檔 I/O 錯）；或用法錯 |
| `75` | 不在 tick 內又拿不到鎖（特別指定的碼） |

〔建議預設，未拍板〕daemon 訊息部件關閉：`aos-mq get` 回 0；`aos-mq post` 有待送件回 1，stderr 印 `post_failed: <to> <id> not_available`，失敗檔 `error.code` 為 `not_available`；沒件回 0。行為見 [B-614](../daemon/messaging.md)、[B-624](../mq.md)，RPC 錯誤碼見 [P-119](daemon/channel.md)。

### 要送的訊息

`.aos/mq/post/<id>.req.json`（請求）或 `<id>.resp.json`（回應）（追蹤），`<id>` 是訊息的 ID；請求與回應各用一個後綴，同一個工作資料夾同一格送出同 ID 的請求與回應不會撞檔名〔使用者 2026-09-30 同意照暫定〕。`message` 是請求物件就得用 `.req.json`、是回應物件就得用 `.resp.json`。〔暫定〕形狀是 `node.send` 的 params 去掉 `token`、加 `version`：

```json
{"version":1,"to":"/目標工作資料夾","message":{...},"urgent"?:true}
```

| 欄位 | 約束 |
|---|---|
| `version` | 必填，1 |
| `to` | 必填；收件 tick 的工作資料夾絕對路徑（P-200；暫緩區叫 node id） |
| `message` | 必填；一份請求或回應物件（[P-301](../../../protocol/messages.md)），它的 `id` 要跟檔名去掉後綴的部分相同；序列化後最多 196608 bytes（[P-119](daemon/channel.md)） |
| `urgent` | 可省，布林，預設 false；true＝急件 |

schema 還沒補：舊的待送封套 [msg-outbox](../../../protocol/schemas/msg-outbox.schema.json) 是檔案投件的格式（`target_node`、`alarm_ticks`、`channel`），已不適用，列在 [README 待放入](../../readme/01-收錄判準對外依賴與待放入.md#待放入)。鬧鐘紀錄 `.aos/alarms/` 隨鬧鐘撤（[B-624](../mq.md)）。

### 送不出去的失敗紀錄

`.aos/mq/failed/<id>.req.json` 或 `<id>.resp.json`（ignore，檔名同原檔）〔使用者 2026-09-30 同意照暫定〕：`mq-post` 把送不了的那份原檔搬過來，內容是原檔的欄位再加一個 `error:{"code":"<代碼>"}`。沒有 schema。下一格 `mq-post` 開始送之前整個清掉（[B-624](../mq.md)）。

### stderr 診斷行

| 行 | 意思 |
|---|---|
| `post_failed: <to> <id> <code>` | 送不了、已移除（[B-624](../mq.md)） |
| `no_channel` | 本格沒有通道，什麼都沒做 |

依據：第十九批（經通道送、急件）；第二十批（系統級任務的 argv）；astra 審整理區同日定案（`aos-mq`；檔案收件、投件、鬧鐘撤出 aos）。

**P-207（加入普通設定，`aos-config-add`）2026-10-01 整條搬到[暫緩區](tick.md)。** 使用者 2026-10-01 裁定：這個指令從沒寫過程式，先不做；要改 `config/` 就自己改。條號保留、不重用。

## P-211．aos-cg：每項一框〔使用者方向 2026-09-30，第二十批追答 8；格式為建議預設〕

> **暫緩**（2026-10-02 第二十三批）〔使用者 2026-10-02 第二十三批：「aos-cg搬進暫緩區。」〕：原在 [tick 協議](../../protocol/tick.md)，原文照留。

普通程式，不是系統級任務。行為正本：[B-634](../cg.md)；框的樹與命名見 [B-605](../daemon/cgroup.md)。

- **argv**：`aos-cg [--] <原指令…>`。不收上限參數（上限歸舊 daemon 設在工作資料夾的框，暫緩區 [B-605](../daemon/cgroup.md) 叫 node 框）。
- **框名**：本工作資料夾的框 `n-<h>` 下的 `task-<seq>-<pid>`，`seq` 取結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current/record.json`）的格數（沒有紀錄時用 `0`），`pid` 是 aos-cg 自己的 PID；跟 `tick` 葉並列。
- **stdin、stdout、stderr**：原樣交給原指令；aos-cg 自己只在 stderr 印 `code: 說明`，代碼有 `cgroup_unavailable`（照 B-634 沒 cgroup 時的做法跑）、`frame_not_empty`。
- **環境**：原樣交給原指令，不另加變數。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 原指令正常結束；被訊號結束時 aos-cg 用同一個訊號結束自己，讓上一層 wait 看到的是訊號 |
| `1` | 用法錯（沒有原指令）；或框清不空（`frame_not_empty`）：另建停格檔（P-213），不讓後面的項在還有人寫檔時開跑 |
| `125` | 原指令沒開起來（exec 前失敗），照 inst（特別指定的碼） |
