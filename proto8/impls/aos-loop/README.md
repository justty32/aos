# aos-loop

`aos-loop - 以指定設定，定期執行一個 aos-exec 目標`（NAME，C-54 R1）

**一句話：`aos-loop [旗標] loop.json`——一次次跑 `exec`（目標＝`aos-exec -- 目標 參數...`；單子物件＝行程內跑），看它的結束碼決定下一步：0＝下一次、10＝正常停、其他非 0＝失敗。**
一個 lib（`lib/libaos-loop.a`，公開標頭 `aos/loop.hpp`）加一支薄薄的命令列（`bin/aos-loop`）。連 [aos-exec](../aos-exec/README.md) 的公開 API（它又帶進 inst、aos-util、aos-directive）；目標每次在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`，單子每次在自己行程內呼叫 aos-exec 的 `run_inst`（10-24）。全家慣例見 [impls/README.md](../README.md)。

像一個只會看紅綠燈的工讀生：老闆給他一張紙「這件事最多做 20 次」。他每做一次就看結果的燈號——綠（0）就再做一次、
「收工」牌（10）就下班、紅（其他）就停手，在 stderr 留一句「第幾次、做什麼、燈號幾」，帶著那個燈號回去。
做滿 20 次也下班，什麼都不說。老闆中途喊停（SIGTERM），他把話轉給正在做事的人，等那人收好，再帶著「被喊停」的燈號（128＋N）回去。

```sh
cat loop.json              # {"exec": ["aos-fsm", "fsm.json"], "max": 20}
aos-loop loop.json         # 每次 `aos-exec -- aos-fsm fsm.json`（跑一次 fsm）；格退 10 → loop 以 0 結束
echo '{"exec": "idle", "max": 5}' > loop.json
aos-loop --max 2 loop.json # 每次 `aos-exec -- idle`，旗標蓋過 loop.json 的 max：只跑 2 次
```

行為比照 Python 版 `proto8/bin/aos-loop`（10-20：骨架 `aos_loop.py`、窗 `aos_window.py`）；規則出處：CONVENTION P-06、P-19～P-22、P-36，NORMS N-06～N-09、N-17、N-32、N-33、N-43、N-60，ideas § 20、§ 22～§ 25。
**10-21 對齊 bin 版 10-20**：長出選填的 `interval_ms`、`ctl`、`state`，骨架開成公開的 `aos::loop::Loop`（aos-daemon 繼承它）。
**10-21 晚對齊 bin 版 10-21 傍晚**（ideas 10-21 § 8、§ 9）：命令列收旗標、設定檔可寫 `檔#/指標`；`run` 只收字串或 `[目標, 參數...]`（內嵌單子改寫 `loop.json#/body`）；
`max` 沒寫＝不限；每次一律在子行程裡呼叫 aos-exec 的 `run_cli`（原本「這個行程算入口、子行程 apply_env＋launch」與「物件＝行程內 run_inst」兩條都拿掉）。
**10-24 `exec` 又收單子物件**（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）：物件＝每次行程內 `run_inst`（`src/run/inline.cpp`），見下面「用法」的 `exec`。
舊的 10-16～17 那套（stdin 設定、ctl／state 窗、`inst`／`times`）已整個換掉，舊版在備份 `proto8/impls/backup/aos-impls-loop-fsm-daemon-2026-10-19-pre-rewrite.tar.gz`（10-23 已刪）。

## 用法

```
aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔
```

- **命令列**（`loop_cli`，aos-daemon 共用）：**唯一的位置參數就是設定檔**——必給、只能一個；可寫 `檔#/指標`＝讀那份檔裡那個位置的物件（aos-util 的 `load_cfg`）。
  旗標放設定檔前面、規則同 aos-exec（`--x V`／`--x=V`、重複給最後一個算、`--` 結束旗標；aos-util 的 `parse_cli`）；旗標名＝loop.json 的 key 名底線換連字號。
  不認得的旗標（含舊的 `--cfg`）＝`FlagUnknown`；沒給、多給設定檔、旗標缺值＝`ArgumentsBad`（原因 `usage: aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] 設定檔.json（原因）`）；
  命令列不再收 XXX（舊的 `aos-loop XXX` 寫法拿掉）。`--max`／`--interval-ms` 要是非負整數（只收 `[0-9]+`），不是＝`CfgBad`（不是 usage 錯，同 bin 版）。
- **起跑時 旗標 ＞ 設定檔 ＞ 預設**（ctl 窗在跑的途中還能再蓋，見下面「窗」）。
- **loop.json**：`{"exec": aos-exec 的目標, "max": 最多幾次}`（10-23 統合一度改叫 `val`、同晚改回 `run`（使用者「只有 loop、daemon 用 run」），深夜再改 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」），跟 fsm 格同名），選填 `interval_ms`、`ctl`、`state`（下面「窗」），其他 key 忽略（`body`、`_entry`…）。
  - `exec`（`parse_target`）＝**字串**（每次 `aos-exec -- <exec>`；`--` 讓 `-` 開頭的目標不被當旗標）或**陣列 `[目標, 參數...]`**（每次 `aos-exec -- 目標 參數...`；元素都要是字串、不能空）。
    相對路徑照 cwd 算、loop 不 cd 不轉；loop 不驗目標存不存在，那是那次 aos-exec 的錯。WS、`AOS_STACK` 由那次的 aos-exec 照它的規則定（沿用 `$AOS_WS`，沒設用 cwd）。每次重找入口，入口換了下一次就生效。
  - `exec` 寫成**物件＝單子**（10-24；10-21～10-23 是 `CfgBad`）：每次在 aos-loop 自己行程內交給 aos-exec 的 `run_inst`（同 aos-exec 跑單子：先解指示詞、驗 10 個 key、inst 的 libaos 起、`timeout_ms`／`grace_ms`、訊號轉給整群）。
    跑的期間 `AOS_CF`＝設定檔的實際路徑、`AOS_CD`＝它的資料夾、`AOS_CO`＝`/exec`（設定檔寫 `檔#/指標` 時＝那個指標＋`/exec`），跑完還原；相對路徑（`cwd`、串流、`argv[0]`）從設定檔的資料夾算，
    單子裡的 `$ref` 從 `exec` 那格來自的檔的資料夾算；`AOS_WS`／`AOS_STACK` 照 loop 自己的，相對路徑以 loop 的 cwd 轉成絕對（`AOS_STACK` 結尾補 `/`，同 aos-exec；跑完還原；不驗、不建。10-24 審後補：原本原樣給，`AOS_STACK=st aos-loop cfg/loop.json` 的單子會寫到 `cfg/st/`），不讀 `.env`。單子壞＝自己的錯一行（`EntryBad`／`DirectiveBad`／`LaunchFailed`，原因開頭「單子跑不起來：」）、退 1。
    被逾時收掉＝那次 143（失敗那行的「誰」＝`loop.json#/exec`）。`{"exec": "loop.json#/body", "body": 單子}` 照樣能用（字串目標，由那次的 aos-exec 跑）。沒有 `exec`＝`CfgBad`「沒有東西可跑」。
  - `max` 非負整數，**沒寫＝不限**（10-21 前是 10）；0＝一次都不跑、退 0（負的、`null`＝`CfgBad`）。
  - `interval_ms` 非負整數，沒寫＝0：一次結束到下一次開始至少隔幾毫秒。
- loop.json 帶 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]` 時，`aos-exec loop.json` 就把 loop 跑起來（PATH 上要有 aos-loop 與 aos-exec；`_entry` 裡也可以放旗標）。
- 不讀 stdin、不寫 stdout（那次的 stdin／stdout／stderr 接 aos-loop 的）。不管逾時（要逾時把 exec 寫成一張單子、加 `timeout_ms`，P-22）。

### 指示詞（10-23 晚）

使用者「aos 讀的 JSON 全部支援」（N-45）：loop.json 與 ctl 裡也能寫 `$ref`／`$env`（寫法同 [aos-directive](../aos-directive/README.md)）。**只解 loop 自己讀的格**（C-52；`resolve_keys`）：

- loop.json：整份先換一層（整份是 `{"$ref": "real.json"}` 也行），再把 `exec`、`max`、`interval_ms`、`ctl`、`state` 整個解（`exec` 換一層後是物件＝單子，裡面不解，留到每次跑的時候 `run_inst` 解，10-24 `resolve_exec`）；相對 `$ref` 從設定檔所在的資料夾算（整份換過的從那份檔的；設定檔是捷徑＝實際的資料夾，同 aos-exec 與內嵌單子的 `AOS_CD`——10-24 審後統一成 `config_file`，原本這裡不解捷徑）。
  其他 key（`body`、`_entry`…）不碰：`loop.json#/body` 由那次的 aos-exec 自己解，body 裡的 `$env` 沒設照舊是那次的錯。
- ctl：整份先換一層，再把 `paused`、`stopped`、`max`、`interval_ms`、`seq` 整個解（aos-daemon 多解 `loops`、`loops_added`、`loops_removed`）；相對 `$ref` 從 ctl 所在的資料夾算。
- 解不開（變數沒設、讀不到、指不到、繞圈）：設定檔＝自己的錯 `DirectiveBad`、退 1；ctl＝整份不採用、原因進 `ctl_warning`。

```json
{"exec": ["aos-fsm", {"$env": "FSM"}], "max": {"$ref": "common.json#/max"}, "state": "state.json"}
```

### 窗（`ctl`、`state`，10-20）

`"ctl": "ctl.json"`、`"state": "state.json"`＝兩扇窗的檔名，放在 `$AOS_STACK` 底下（寫了卻沒設 `AOS_STACK`＝`StackMissing`；沒寫＝不開、不提醒，N-09）。

- **ctl**（誰都能寫、loop 只讀；每跑一次讀一次）：認 `paused`（不起下一次、每秒再看）、`stopped`（不起下一次、以 0 結束；10-23 晚改名，原 `stop`）、`max`、`interval_ms`（跑的途中蓋過旗標與 loop.json，後到先贏）、`seq`（state 回音 `ctl_seq`）；
  其他 key 忽略。讀到壞的（讀不了、不是 JSON 物件、型別不對、指示詞解不開）整份不採用、維持上一份好的、原因寫進 state 的 `ctl_warning`（N-08）；檔不在＝還沒人寫，不算問題。
- **state**（只有自己寫；先寫 `.state.json` 再改名，N-05）：只在兩次之間寫（心跳只在兩次之間跳）：
  `{"kind": "state", "phase": running／waiting／paused／done／stopped, "counter_runs", "max", "interval_ms", "paused", "ctl_seq", "ctl_warning", "pid", "started_at_ticks", "boot_id", "recorded_at"}`，
  `counter_runs`＝跑過幾次、`started_at_ticks`＝/proc/<pid>/stat 第 22 欄、`recorded_at`＝這份 state 的時間（ISO 8601 UTC 到毫秒，例 `2026-10-23T01:58:45.123+00:00`）；
  10-23 統合前 `phase` 叫 state、`runs` 叫 lap（10-23 統合後一度叫 beats，同晚改 runs）、`started_at_ticks` 叫 started、`at` 叫 beat（那時是 epoch 秒）（[10-23 命名統合](../../thinking/2026-10-23-naming.md)）；10-25 `runs` 改 `counter`、`at` 改 `recorded_at`（使用者 10-25「state.json中，runs改counter，at改成recorded_at」），同日 `counter` 再改 `counter_runs`（使用者「計數這塊，幫我改成counter_*」）。
  **10-23 壓測後**（使用者「都修都處理」，[thinking](../../thinking/2026-10-23-daemon-bench.md)）：沒有 `exec`（只有 aos-daemon 會這樣）時一輪只讀一次 ctl、只 tend 一次、只寫一份 `waiting`（不寫 `running`），
  `recorded_at` 的間隔穩定在 `interval_ms`＋tend 的時間；子類別在一輪裡做很久的工作時用 `beat()`（離上一份滿 1 秒或還沒寫過就再寫一份）。
  `$AOS_STACK` 資料夾不在＝state 寫不了＝`WriteFailed`、退 1、那次沒跑，**不自己建**（建 stack 只在 aos-exec 做，N-59 第 1 件；經 aos-exec 跑時它已經建好）。
  結束時多 `code`（`done`＝自己跑完或失敗、`stopped`＝ctl 叫停、收到訊號或自己的錯）；`max` 不限時是 `null`。欄位與順序同 bin 版。

### 結束碼

| 情況 | 結束碼 | stderr |
|---|---|---|
| 那次退 0 | 下一次 | — |
| 那次退 10 | **0** | 不寫 |
| 那次退其他非 0（含被訊號停掉 128＋N、單子逾時被收掉＝143） | **那個碼** | 一行 `aos-loop: 第 N 次 誰 失敗，結束碼 C`（誰＝exec 的目標字串：字串 exec 原樣、陣列＝第一個元素；例 `loop.json#/body`；單子＝「設定檔名#指標」，例 `loop.json#/exec`） |
| 跑滿 `max` | 0 | 不寫（N-43） |
| 收到 SIGINT／SIGTERM／SIGHUP | **128＋N**（等那次結束之後） | 不寫 |
| 自己的錯（含 exec 的單子壞、起不來，10-24） | 1 | 一行 `aos-loop: 代號 原因` |

那次找不到入口、單子壞等（那一層 aos-exec 的錯）：stderr 先有一行 `aos-exec: 代號 原因`，那次的碼是 1，接著是 loop 那行「第 N 次 … 結束碼 1」——
跟 Python 版每次都叫一次 `aos-exec` 子程序一樣，每層只說自己的（P-21）。所以單子壞不是 loop 自己的錯，每次都會照跑一次 aos-exec、各自報。

### 訊號

整支程式的壽命都擋著 SIGINT／SIGTERM／SIGHUP（P-36「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）：

- **跑到一半收到**：轉給那次——`kill` 給那個子行程（那次的 aos-exec；它跟 aos-loop 同一個行程群組，同 Python 版的 `subprocess.call`；不另設 SIGKILL 期限）；
  那次是單子時由那次的 aos-exec（監工）再轉給整群、過 `grace_ms` 還沒結束就 SIGKILL 整群。等那次結束，**不起下一次**，以 128＋第一個收到的訊號結束。
- **兩次之間收到**（含睡 interval、paused 的時候）：不起下一次，直接 128＋N（有開 state 窗就寫 `stopped`、`code`）。
- 在終端機按 Ctrl-C：那次的子行程跟 aos-loop 同群組，會直接收到一次、再收到 aos-loop 轉的一次（兩次）；單子的子程式自成群組，只收到那次的 aos-exec 轉的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Loop(opts, 設定檔, Defaults) ──▶ Loop::serve：每次 signal_got ──▶ read_ctl ──▶ tend ──▶ 停不停 ──▶ 睡（nap）或 run_once ──▶ write_state
                                                                                                                                   │
                                                          run_once(Target) ─┬▶ 目標：run_folder：fork 子行程 ──▶ aos::exec::run_cli({"--", 目標, 參數...})；等它、轉訊號
                                                                            └▶ 單子（10-24）：run_inline：設 AOS_CF／CD／CO ──▶ aos::exec::run_inst（行程內）──▶ 還原
```

| 檔 | 做什麼 |
|---|---|
| `include/aos/loop.hpp` | 公開介面：`Run`（`code`、`signal`、`elapsed_ms`、`received`；沒有 `timed_out`）、`block_signals`、`take_signal`、`Target`（10-24 多 `inst`、`cf`、`co`、`ref_base`、`label()`）、`parse_target`（10-24 收物件）、`resolve_exec`、`place_inline`、`pointer_escape`（10-24）、`config_file`（10-24 審後）、`run_once(Target)`、`loop_cli`、`Loop(opts, spec, defaults)`（骨架，`tend`／`finish`／`info`／`check_ctl` 四個掛鉤給子類別）、`Defaults`（`max` 預設 nullopt＝不限）、`write_window`、`heartbeat`、`resolve_keys`（10-23 晚；aos-daemon、aos-fsm 共用）；代號 `aos::loop::code::*`（沿用 aos-exec 的＋`StackMissing`） |
| `src/common/common.hpp` | `using` |
| `src/run/run.hpp` | run 元素的內部介面：`the_signals`、`run_folder`、`run_inline` |
| `src/run/run.cpp` | `run_once`：目標＝組好 `-- 目標 參數...` 交給 `run_folder`；單子＝交給 `run_inline`（10-24） |
| `src/run/inline.cpp` | `run_inline`（10-24）：`AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置、相對的 `AOS_WS`／`AOS_STACK` 轉成絕對（跑完都還原）、行程內 `aos::exec::run_inst`、錯誤原因前面加「單子跑不起來：」、量毫秒 |
| `src/run/folder.cpp` | `run_folder`：擋 SIGCHLD、開 signalfd、fork；子行程解開訊號、呼叫 `aos::exec::run_cli`、`_exit` 它的碼；這邊等它、期間把三個訊號 kill 給它、量毫秒 |
| `src/run/signals.cpp` | `block_signals`（`sigprocmask`）、`take_signal`（`sigtimedwait` 不等） |
| `src/engine/engine.hpp` | engine 元素的內部介面：`is_nat` |
| `src/engine/config.cpp` | `resolve_keys`（設定檔、ctl 的指示詞：整份換一層、自己讀的格整個解，10-23 晚）；`Loop` 的建構子：`load_cfg` 讀設定檔（`檔#/指標`）、解指示詞、旗標蓋上、驗 `exec`／`max`／`interval_ms`／`ctl`／`state`、算兩扇窗的路徑；`parse_target`、`resolve_exec`、`place_inline`、`config_file`（設定檔的實際路徑，10-24 審後）、`loop_cli` |
| `src/engine/loop.cpp` | `Loop::serve`／`main_loop`（每次怎麼走；失敗那行的「誰」＝`exec_.target`）、`end`、`nap`（`sigtimedwait` 睡、收到訊號就醒）、`signal_got`、`say` |
| `src/engine/window.cpp` | 窗：`read_ctl`、`write_state`（寫不了丟 `StateError`）、`beat`（10-23：離上一份滿 1 秒就再寫）、`write_window`、`heartbeat` |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Loop` → `serve`；出錯印「aos-loop: 代號 原因」 |

## 為什麼這樣做

- **每次在子行程裡呼叫 aos-exec 的 `run_cli`、不 exec 一支 aos-exec**：使用者 § 20「aos-loop,daemon……可以隨意使用……aos-exec的公開api」；呼叫 `run_cli` 就是同一件事，也不必在 PATH 上找 aos-exec。
  10-21 起 aos-exec 要在挑入口之前讀 `.env`、每走一層都 cd 和 setenv，原本「aos-loop 這邊算好入口、子行程只做 `apply_env`＋`launch`」拆不開了，整段搬進子行程。
  子行程等同那一層 aos-exec，所以它的錯照 aos-exec 的格式說（`aos-exec: 代號 原因`）、碼 1。
  fork 時 aos-loop 只有一條執行緒，子行程裡做 C++ 配置、setenv 不會撞鎖。
- **`exec` 只收目標**（10-21 plan L11、ideas § 9）：loop 不知道那次是什麼（C-52），單子交給那次的 aos-exec 跑；逾時、整群收、轉訊號都由它做。
  〔10-24 改：使用者「不過exec本來就應該要可以直接放內嵌單子吧」——物件＝單子、行程內 `run_inst`（逾時、整群收、轉訊號由 `run_inst` 做，跟 aos-exec 跑單子同一套）。
  在行程內 setenv 三個 `AOS_*` 再還原是安全的：aos-loop 單執行緒，`run_inst` 的工人執行緒在它回來前就 join 了。〕
- **`Run` 的欄位同 fsm 的 trace 一行**：aos-fsm 也用 `run_once` 跑一格（格的 `exec` 跟 loop.json 的 `exec` 同一套寫法、同名，10-23 深夜起），所以開成公開 API；
  沒有 `timed_out`（loop 看不到格裡有沒有逾時；單子逾時＝那次的 aos-exec 以 143 正常結束；10-24 起單子物件行程內跑時 `code` 143、`signal` 15）；`received` 給「收完這次再以 128＋N 結束」用。
- **整支程式擋著三個訊號**：不擋的話 SIGTERM 一來 aos-loop 先死、那次變孤兒繼續跑（Python 版 10-19 晚以前就是這樣；§ 24 起兩版一樣轉訊號）。

## 錯誤代號

自己出錯：stderr 一行 **`aos-loop: 代號 原因`**、退 1（同 aos-exec 的格式，N-60／P-21）。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`（共用） | 沒給、多給設定檔；旗標缺值 |
| `FlagUnknown`（共用） | 不認得的旗標（含 `--cfg`） |
| `CfgMissing`（共用） | 設定檔不在；`#/` 指標指不到 |
| `CfgBad`（共用） | 設定檔讀不了、不是 JSON；不是物件；`#` 後面不是 `/`；沒有 `exec`；`exec` 不是字串、非空字串陣列或物件（10-21～10-23 物件也不行）；`max`／`interval_ms` 不是非負整數（`"3"`、`2.5`、`true`、`null`、負的都不行；旗標 `--max`／`--interval-ms` 不是 `[0-9]+`）；`ctl`／`state` 不是非空字串 |
| `DirectiveBad`（共用） | 設定檔裡 loop 讀的格的指示詞解不開（變數沒設、`$ref` 讀不到、指不到、繞圈；10-23 晚）；exec 的單子裡的指示詞跑的時候解不開（10-24） |
| `EntryBad`（共用） | exec 的單子形狀不對（`argv` 不是非空字串陣列、型別不對…；10-24，同 aos-exec） |
| `StackMissing` | 寫了 `ctl` 或 `state` 卻沒設 `AOS_STACK` |
| `WriteFailed`（共用） | state 窗寫不了（含 `$AOS_STACK` 資料夾不在） |
| `LaunchFailed`（共用） | fork 失敗；exec 的單子起不來（找不到程式、cwd 不在、串流開不了；10-24） |
| `Internal`（共用） | 準備轉送訊號（signalfd）失敗、照理不會發生的例外 |

代號照 [10-23 命名統合](../../thinking/2026-10-23-naming.md)；統合前 `ArgumentsBad`／`FlagUnknown` 都叫 Usage、`CfgMissing`／`CfgBad` 叫 ReadFailed／JsonSyntax／FieldType。

## 跟 Python 版 `proto8/bin/aos-loop` 的差異

- 錯誤一行多了代號（Python 版 `aos-loop: 原因`）。
- 每次不叫 PATH 上的 `aos-exec`，在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`（效果一樣）。PATH 不動、原樣傳給那次（兩版的 aos 程式都不動 PATH，ideas § 24）；
  那次裡要再叫 `aos-exec`、`aos-fsm`，它們要本來就在 PATH 上（demo 的做法：四支的 `bin/` 都放 PATH）。
- state 窗寫不了：這版 `WriteFailed` 一行、退 1；Python 版是 traceback。
- 其他一樣：`proto8/tests/test_loop.py` 24 案拿這支跑全過（10-21 晚，方法見 [aos-exec](../aos-exec/README.md) 的「拿 proto8/tests 對照」）。

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

`ctest` 跑 `test_cli`（`tests/test_cli.py`，58 組，約 4 秒；10-24 審後加 H2 段 3 組：相對 `AOS_STACK`／`AOS_WS` 轉成絕對、絕對的不動、捷徑設定檔的相對基準（拿掉修正前兩組紅）；10-24 加 H 段 9 組：exec 直接放單子——每次跑與 `AOS_CF`／`AOS_CD`／`AOS_CO`／cwd、設定檔 `檔#/指標` 的 `AOS_CO`、指示詞跑的時候才解與 `$ref` 起點、exec 本身是 `$ref`、0／10／7、逾時 143、形狀壞（`EntryBad`／`DirectiveBad`／`LaunchFailed`）、SIGTERM 轉給單子、跑完 `AOS_CO` 還原，拿掉實作全紅；10-23 加 F 段 1 組：`$AOS_STACK` 不在不建、`WriteFailed`、那次沒跑；10-23 晚加 G 段 5 組：設定檔的指示詞（`exec`／`max`／`state`、整份 `$ref`、exec 陣列元素）、解不開＝`DirectiveBad`（沒設、讀不到、繞圈；寫法不合原封不動＝`CfgBad`）、不讀的 key（body）不解、ctl 的 `$ref`（相對 ctl 的資料夾、整份 `$ref`）、ctl 解不開不採用）。10-21 起 exec（當時叫 run）不收內嵌單子：A～D 段寫內嵌單子的案例由 `loop()` 小工具換成 `{"exec": "loop.json#/body", "body": 單子}`。
A 段從 `proto8/tests/test_exec.py` 移植 aos-loop 的案例（失敗碼、內嵌單子每次跑、跑滿 max 不寫 stderr、10／7、失敗那行的「誰」＝exec 的目標、自己的錯一行），
B 段是 `max` 沒寫＝不限／0／負的、欄位型別、字串 exec 走 aos-exec 的規則（AOS_WS／AOS_STACK／AOS_CF／AOS_CD／cd、JSON 入口、每次重找入口、入口不在＝那次碼 1）、
不寫 stdout、PATH 原樣傳給那次（§ 24）、單子的 `$env`＋相對 cwd（`$env` 沒設＝那次 aos-exec 的錯）、逾時＝失敗（143）、被訊號停掉＝128＋N，C 段是訊號（SIGTERM 轉給字串 exec、SIGINT 轉給單子、SIGHUP 停掉那次，都是收完再 128＋N），
D 段是 10-20 的選填 key（照 `proto8/tests/test_loop.py` 的 Windows 移植：state 欄位與心跳、沒開窗不寫檔、窗沒 AOS_STACK、interval 壞／有睡、ctl stopped＋seq、ctl 的 max、壞 ctl、paused 再放開、睡 interval 時收到訊號）與 `$ref` 從設定檔的資料夾算，
E 段是 10-21 傍晚的命令列（ideas § 9）：usage 的各種寫法（沒給、多給、不認得、缺值、`--cfg`）、`--max`／`--interval-ms` 不是非負整數＝CfgBad、旗標蓋過 loop.json（`--max`、`--max=`、`--state`、`--ctl` 卻沒 AOS_STACK）、
設定檔 `檔#/指標`（指不到、`#` 後沒 `/`、不是物件、讀不到）、exec 陣列（參數照接、`-` 開頭的目標、失敗那行的「誰」）、`aos-exec loop.json` 當入口（`_entry` 帶 `{"$env": "AOS_CF"}`）。
demo 的整合測試在 [aos-fsm](../aos-fsm/README.md) 的 `test_demo`。
