← [入口](README.md)｜涵蓋：JSON 內部結構｜上一份 [02-argv](02-argv.md)｜下一份 [04-資料夾與固定名字](04-資料夾與固定名字.md)

# JSON 結構：命名守得住，型別判斷有暗規則

條文依據：C-48（值的雙形、不認得的 key 忽略）、C-54／R3～R7（固定格 `val`／`max`／`kind`／`code`／`signal`／`seq`／`phase`／`pid`，`counter_*`、`_at`、單位後綴）、C-55（純值長成物件、原值叫 `val`）、C-56（寫什麼就做什麼、不把規則藏進值裡）、C-72（JSON＝埋在檔裡的 table）、N-45（`$env`／`$ref`、`#/`）。

## 活著的 JSON 一覽（頂層 key）

| 檔 | 頂層 | 判定 |
|---|---|---|
| inst 單子 | `argv`、`cwd`、`envs`、`stdin`／`stdout`／`stderr`、`*_append`、`timeout_ms`、`grace_ms`（aos-exec 認 10 個） | 合。**但 `impls/aos-schema/examples/inst.schema.json` 列 17 個**（多 `id`、`cwd_mkdir`、`envs_clear`、`stdout_mkdir`、`stderr_mkdir`、`stderr_merge`、`flag`）——C lib 支援、aos-exec 靜默忽略。兩份「同一種單子」的 key 表不同，寫了 `envs_clear` 的人以為有效。中；[06 題 9](06-要使用者裁的題.md) |
| loop.json | `exec`、`max`、`interval_ms`、`ctl`、`state`（＋忽略 `_entry`、`body`） | 合 N-11。`ctl`／`state` 是選填旋鈕、沒預設名 → 被別人寫死（見 [04](04-資料夾與固定名字.md)） |
| ctl.json | `cmd`、`max`、`interval_ms`、`seq` | 合 11-03 ctl-commands |
| state.json | `phase`、`counter_runs`、`max`、`interval_ms`、`paused`、`ctl_seq`、`ctl_warning`、`code`、`pid`、`started_at_ticks`、`boot_id`、`updated_at` | 合 R3～R7 |
| daemon.json | loop.json＋`procs`、`adopt`、`procs_ctl`、`procs_state`、`procs_ctl_mailbox` | 「loop.json 的超集」但 **`interval_ms` 預設 200、loop 是 0**（低；加註或統一）。**proc 的型別靠「多寫一個 key」**（見下） |
| procs_ctl／procs_state | `procs`、`procs_added`…、`seq`；state 多 `mailbox_warning`、每列 `pid`／`phase`／`code`／`signal`／`stack`／`ws` | 合 R7「主題在前」。>100 列用 `$ref` 陣列切檔（合 N-28） |
| fsm.json | `start`、`states.<名>.{exec,next}` | 合 N-36；`next` 物件寫法合 C-55 雙形 |
| tools.json | `tools.<名>.{path,cache}` | 合 |
| `_tooldef`／`_metainfo` | OpenAI function 去 name／`summary`、`time_ms: 數字\|{val,max}`… | 內容合 C-55（`val` 用對地方）；**檔名**見 [04](04-資料夾與固定名字.md) |
| cli.json | `kind`、`flags`、`print_flags`、`tools_flags`、`timeout_ms`、`tools` | 合。`kind` 在信與 state 裡 11-02／03 已刪，這裡還在用（這是另一件事「CLI 種類」，不算二義） |
| eca.json | `kind`、`ws`、`template` | `template`＝定義資料夾，別處叫 XXX／`AOS_CD`／「定義」——同義不同名（低）。aos-agent 規劃退場它 |
| letter.json（aos-post） | `sender`、`sent_at`、`reply_to`、`in_reply_to`、`body` | 合 N-16。**kernel／閘門的信把 `inst`／`env`／`priority` 放頂層、沒包進 `body`**（程式註解「過渡期」）。中；kernel 重寫時改，先加註 |
| kernel.json、queue.json、used.json、served.jsonl、holder.json、order.json | `mailbox`、`slots`、`budget.{max_calls,max_tokens,window}`、`counter_*`、`*_at` | 合 |
| roster.json、heap index.json | `members`、`groups`、`max_*`；heap 的 `created`／`updated` | heap **沒守 `_at`**（低）；兩份都沒活主人 |
| sandbox.json | `commands`、`ro`、`rw`、`env`、`net`、`mem_mb`、`cpu_s`、`procs`、`file_mb` | `env` 是名單、`procs` 是上限數——跟 daemon 的 `procs` 同字不同義（低；加註） |

## 同一概念、不同 key（違 R4 一詞一義）

| 概念 | 寫法 | 嚴重度／建議 |
|---|---|---|
| 環境 | inst `envs`（要設的物件）、kernel 信 `env`（整份）、sandbox `env`（放行名單）、JSON `.env` key | 低；加註；sandbox 可改 `env_allow` |
| 逾時 | `timeout_ms`（inst、loop、cli.json）vs `timeout_s`（lib 工具參數）vs `--timeout-s`／`--timeout` | 低～中；單位後綴有就不算錯，但同體系 ms／s 混用要定一句（[02](02-argv.md)） |
| 檔案位置 | aos-json `target`、lib json_read `path`＋`pointer`、impls json_edit `file`、lib json_edit `path` | 低；**兩對同名工具各寫一份**（見 [04](04-資料夾與固定名字.md)），合併時順手統一 |
| 定義資料夾 | `template`（eca.json）、XXX、`AOS_CD`、規劃 daemon 表新欄 `exec` | 低；規劃用 `exec` 是對的（＝add 時交給 aos-exec 的目標） |

## 型別靠暗規則（違 C-56）

- **daemon proc 的三種寫法**：字串、陣列＝exec 型；只有 `exec`（可加 `ws`、`stack`）的物件＝exec 型；**物件裡多任何一個其他 key＝loop 型**。所以 `{"exec": "fsm.json"}` 只跑一次，想一直跑得加 `"interval_ms": 0`——這正是 C-56 說的「要人記的暗規則」。aos-daemon-ctl 因此**一定替 loop 型補 `ctl`／`state`** 好讓 daemon 認得（`bin/aos-daemon-ctl:132`）。**高**（會咬人、違最高原則）。建議：物件＝loop 型、字串／陣列＝exec 型，不看 key 多少；`{"exec": X}` 就是用預設跑的 loop。[06 題 3](06-要使用者裁的題.md)。
- aos-eca.json 存在＝這個 stack 是 eca；`<kind>/` 小格名來自 `kind` 值：規劃退場，不追。

## JSON 與資料夾重複表達同一件事（C-51「可互通，但別濫用」）

| 兩邊 | 判定 |
|---|---|
| daemon `procs` 表（每列有 `stack`）＋ `procs/<名>/` 子資料夾 | **不算濫用**：表是名單（含不在預設位置的 stack），資料夾是預設位置；adopt、`where` 都以表為準。aos_human 反過來用資料夾推 daemon 才是暗路（[01](01-環境變數.md)） |
| `procs_state.json` 的 `$ref` 陣列＋ `procs_state_procs/` | 合 N-28 切檔；資料夾名從檔名推出來（低、不動） |
| tools.json 登記＋定義裡 `tools/<名>` symlink | 使用者 11-01「兩者可以共存」。不動 |
| `.env` 檔 vs JSON `.env` key | 同一條機制的兩面（C-72），格式不同是因為載體不同。合 |
| `_entry` 檔 vs `js["_entry"]`；`$AOS_ENTRY` 走資料夾 vs 走 key；`#/` | **這是 C-51／C-72 真正落地的三處**，守住了 |

## 指標與指示詞

- `#/` 用處一致：入口路徑、`$ref` 檔名、argv[0]、loop／fsm／daemon／kernel／aos-json 的設定檔參數、daemon 的 `小格/loop.json#/_entry`、aos-grow CALLER、`$path`。`AOS_CO` 同一種指標不帶 `#`（N-57 定）。aos-tick 的 FILE 不切 `#`（它是 txt，合）。
- `$env`／`$ref` 只在 aos 自己讀的 JSON 解（N-45）；sandbox 自己解一份（含 `$path`／`$prefix`），跟 aos-directive 兩份實作。低；加註。
- `_entry` 值的四種（單子、陣列、字串、沒 `argv` 的物件）＋資料夾裡三種寫法（sh 檔、JSON 陣列檔、loop.json／fsm.json 裡的 key `["aos-loop",{"$env":"AOS_CF"}]`）並存：合 C-73，是刻意的靈活。但範本用哪一種沒人定（demo 用 JSON 陣列檔、fixtures 用 sh）。低；CONVENTION 可挑一種當範本寫法。
