# aos-loop

`aos-loop - 以指定設定，定期執行一個 aos-exec 目標`（NAME，C-54 R1）

**一句話：`aos-loop [旗標] loop.json`——一次次跑 `exec`（目標＝`aos-exec -- 目標 參數...`；單子物件＝行程內跑），看它的結束碼決定下一步：0＝下一次、10＝正常停、其他非 0＝失敗。**
一個 lib（`lib/libaos-loop.a`，公開標頭 `aos/loop.hpp`）加一支薄薄的命令列（`bin/aos-loop`）。連 [aos-exec](../aos-exec/README.md) 的公開 API（它又帶進 inst、aos-util、aos-directive）；目標每次在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`，單子每次在自己行程內呼叫 aos-exec 的 `run_inst`。全家慣例見 [impls/README.md](../README.md)。

像一個只會看紅綠燈的工讀生：老闆給他一張紙「這件事最多做 20 次」。他每做一次就看結果的燈號——綠（0）就再做一次、
「收工」牌（10）就下班、紅（其他）就停手，在 stderr 留一句「第幾次、做什麼、燈號幾」，帶著那個燈號回去。
做滿 20 次也下班，什麼都不說。老闆中途喊停（SIGTERM），他把話轉給正在做事的人，等那人收好，再帶著「被喊停」的燈號（128＋N）回去。

```sh
cat loop.json              # {"exec": ["aos-fsm", "fsm.json"], "max": 20}
aos-loop loop.json         # 每次 `aos-exec -- aos-fsm fsm.json`（跑一次 fsm）；格退 10 → loop 以 0 結束
echo '{"exec": "idle", "max": 5}' > loop.json
aos-loop --max 2 loop.json # 每次 `aos-exec -- idle`，旗標蓋過 loop.json 的 max：只跑 2 次
```

規範：窗 N-06～N-09、N-17、N-32、N-33 在 [NORMS/05 窗](../../docs/NORMS/05-基礎設施-窗.md)，結束碼 N-43 在 [NORMS/01 總則](../../docs/NORMS/01-總則.md)，loop 的定位在 [NORMS/04 loop 與 daemon](../../docs/NORMS/04-基礎設施-loop與daemon.md)；慣例 CONVENTION P-06、P-19～P-22、P-36。本頁只寫用法與實作細節。
骨架是公開的 `aos::loop::Loop`（aos-daemon 繼承它）。
`exec` 可以直接放單子物件（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）：物件＝每次行程內 `run_inst`（`src/run/inline.cpp`），見下面「用法」的 `exec`。

## 用法

```
aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--enable-logs] 設定檔 [-- 參數...]
```

- **命令列**（`loop_cli`，aos-daemon 共用）：**唯一的位置參數就是設定檔**——必給、只能一個；可寫 `檔#/指標`＝讀那份檔裡那個位置的物件（aos-util 的 `load_cfg`）。
  旗標放設定檔前面、規則同 aos-exec（`--x V`／`--x=V`、重複給最後一個算、`--` 結束旗標；aos-util 的 `parse_cli`）；旗標名＝loop.json 的 key 名底線換連字號。
  不認得的旗標（含 `--cfg`）＝`FlagUnknown`；沒給、多給設定檔、旗標缺值＝`ArgumentsBad`（原因 `usage: aos-loop [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [--enable-logs] 設定檔.json [-- 參數...]（原因）`）；
  `--max`／`--interval-ms` 要是非負整數（只收 `[0-9]+`），不是＝`CfgBad`（不是 usage 錯）。
  `--enable-logs` 是不帶值的開關（寫 `--enable-logs=V`＝`ArgumentsBad`）：印 log（見下面「log」）。
- **`設定檔 -- 參數...`**（使用者「aos-XXX ... ... -- ...，第一個...就是aos-XXX本身的旗標……第二個...就是目標檔案……後面就是純參數」）：
  設定檔之後接 `--`＝後面全是附加參數（那個 `--` 剝掉），**每次**接在 exec 後面：字串目標＝`[目標, 參數...]`、陣列＝接在最後、內嵌單子＝接在單子 `argv` 的最後
  （`argv` 要直接寫成陣列；是指示詞或沒寫＝`CfgBad`）；ctl 改不了它們。設定檔之後接的不是 `--`＝`ArgumentsBad`；設定檔之前的 `--` 是「旗標結束」（`aos-loop -- -odd.json -- 參數`）。
  跟 aos-exec 的差異：`aos-exec XXX args...` 的 XXX 後面全部原樣交給入口（`--` 也原樣、不剝）；所以 `aos-exec <loop 資料夾> -- 題` 會變成 `aos-loop <AOS_CF> -- 題`，aos-loop 在這裡剝掉 `--`、把「題」接到身體。
- **起跑時 旗標 ＞ 設定檔 ＞ 預設**（ctl 窗在跑的途中還能再蓋，見下面「窗」）。
- **loop.json**：`{"exec": aos-exec 的目標, "max": 最多幾次}`（使用者「exec，loop／daemon 的 run 也一起改 exec」，跟 fsm 格同名），選填 `interval_ms`、`ctl`、`state`（下面「窗」），其他 key 忽略（`body`、`_entry`…）。
  - `exec`（`parse_target`）＝**字串**（每次 `aos-exec -- <exec>`；`--` 讓 `-` 開頭的目標不被當旗標）或**陣列 `[目標, 參數...]`**（每次 `aos-exec -- 目標 參數...`；元素都要是字串、不能空）。
    相對路徑照 cwd 算、loop 不 cd 不轉；loop 不驗目標存不存在，那是那次 aos-exec 的錯。WS、`AOS_STACK` 由那次的 aos-exec 照它的規則定（沿用 `$AOS_WS`，沒設用 cwd）。每次重找入口，入口換了下一次就生效。
  - `exec` 寫成**物件＝單子**：每次在 aos-loop 自己行程內交給 aos-exec 的 `run_inst`（同 aos-exec 跑單子：先解指示詞、驗 10 個 key、inst 的 libaos 起、`timeout_ms`／`grace_ms`、訊號轉給整群）。
    跑的期間 `AOS_CF`＝設定檔的實際路徑、`AOS_CD`＝它的資料夾、`AOS_CO`＝`/exec`（設定檔寫 `檔#/指標` 時＝那個指標＋`/exec`），跑完還原；相對路徑（`cwd`、串流、`argv[0]`）從設定檔的資料夾算，
    單子裡的 `$ref` 從 `exec` 那格來自的檔的資料夾算；`AOS_WS`／`AOS_STACK` 照 loop 自己的，相對路徑以 loop 的 cwd 轉成絕對（`AOS_STACK` 結尾補 `/`，同 aos-exec；跑完還原；不驗、不建），不讀 `.env`。單子壞＝自己的錯一行（`EntryBad`／`DirectiveBad`／`LaunchFailed`，原因開頭「單子跑不起來：」）、退 1。
    被逾時收掉＝那次 143（失敗那行的「誰」＝`loop.json#/exec`）。`{"exec": "loop.json#/body", "body": 單子}` 照樣能用（字串目標，由那次的 aos-exec 跑）。沒有 `exec`＝`CfgBad`「沒有東西可跑」。
  - `max` 非負整數，**沒寫＝不限**；0＝一次都不跑、退 0（負的、`null`＝`CfgBad`）。
  - `interval_ms` 非負整數，沒寫＝0：一次結束到下一次開始至少隔幾毫秒。
- loop.json 帶 `"_entry": ["aos-loop", {"$env": "AOS_CF"}]` 時，`aos-exec loop.json` 就把 loop 跑起來（PATH 上要有 aos-loop 與 aos-exec；`_entry` 裡也可以放旗標）。
- 不讀 stdin；stdout 只印 log（下面「log」，沒給 `--enable-logs` 就不寫 stdout）。那次的 stdin／stdout／stderr 接 aos-loop 的。不管逾時（要逾時把 exec 寫成一張單子、加 `timeout_ms`，P-22）。

### log

使用者 11-02「daemon和loop他們就是把log輸出到stdout」「要給argv讓使用者選擇是否要印出」，11-02 晚「aos-loop和aos-daemon他們印出的log感覺都沒啥用，應該要改成默認不印」（[thinking 11-02 state 窗](../../thinking/2026-11-02-state-window.md)）：

- **每跑完一次在 stdout 印一行 JSON**（不論那次怎麼結束：0、10、失敗、被訊號停掉）：`{"started_at": 這次開始（ISO 8601 UTC 到毫秒）, "counter_runs": 第幾次, "code": 結束碼, "signal": 訊號或 null, "elapsed_ms": 毫秒}`。結束不另印；`exec` 起不來（單子壞、fork 失敗）那次沒有結果、不印。沒有 `exec`（aos-daemon 純監工）不印每圈的行。
- **預設不印，`--enable-logs` 才印**。不寫任何 log 檔（loop.json 沒有 `log` key）；要存檔就在外面接（`aos-loop loop.json >> log.jsonl`）。
- 身體的 stdout 跟 log 同一條（那次繼承 aos-loop 的 stdout）；混在一起由使用者自己處理（11-02 晚使用者「stdin/out/err都可以任意指定」）。
- 一行一次 `write`（不經 stdio 緩衝）。印不了（stdout 是關掉的管子 EPIPE…）＝之後都不印、照跑、不退出：寫的那一下用 `pthread_sigmask` 擋著 SIGPIPE，寫失敗就把排著的 SIGPIPE 吃掉（零逾時的 `sigtimedwait`）再還原遮罩——**不改 SIGPIPE 的處置**（改成忽略會被 exec 的那次繼承，改了身體的行為）。stdout 是滿了的管子（讀的人不讀）時會卡在那一下，同一般程式寫 stdout。

### 指示詞

使用者「aos 讀的 JSON 全部支援」（N-45）：loop.json 與 ctl 裡也能寫 `$ref`／`$env`（寫法同 [aos-directive](../aos-directive/README.md)）。**只解 loop 自己讀的格**（C-52；`resolve_keys`）：

- loop.json：整份先換一層（整份是 `{"$ref": "real.json"}` 也行），再把 `exec`、`max`、`interval_ms`、`ctl`、`state` 整個解（`exec` 換一層後是物件＝單子，裡面不解，留到每次跑的時候 `run_inst` 解，`resolve_exec`）；相對 `$ref` 從設定檔所在的資料夾算（整份換過的從那份檔的；設定檔是捷徑＝實際的資料夾，同 aos-exec 與內嵌單子的 `AOS_CD`，`config_file`）。
  其他 key（`body`、`_entry`…）不碰：`loop.json#/body` 由那次的 aos-exec 自己解，body 裡的 `$env` 沒設是那次的錯。
- ctl：整份先換一層，再把 `cmd`、`max`、`interval_ms`、`seq` 整個解；相對 `$ref` 從 ctl 所在的資料夾算。
- 解不開（變數沒設、讀不到、指不到、繞圈）：設定檔＝自己的錯 `DirectiveBad`、退 1；ctl＝整份不採用、原因進 `ctl_warning`。

```json
{"exec": ["aos-fsm", {"$env": "FSM"}], "max": {"$ref": "common.json#/max"}, "state": "state.json"}
```

### 窗（`ctl`、`state`）

語意照 [NORMS/05 窗](../../docs/NORMS/05-基礎設施-窗.md)（N-06～N-09、N-17、N-32）；下面是這支的具體行為。

`"ctl": "ctl.json"`、`"state": "state.json"`＝兩扇窗的檔名，放在 `$AOS_STACK` 底下（寫了卻沒設 `AOS_STACK`＝`StackMissing`；沒寫或寫 `null`＝不開、不提醒）。

- **ctl**（誰都能寫、loop 只讀；每跑一次讀一次、暫停中每秒讀一次）：**一道指令**（使用者「還是用指令吧，不然大家不好理解。但是loop就不要用mailbox那套，就是誰能寫ctl.json就能控制。」，[thinking 11-03 ctl-commands](../../thinking/2026-11-03-ctl-commands.md)）：
  `{"cmd": "pause"／"resume"／"stop", "max", "interval_ms", "seq"}`，都選填。`pause`＝這次跑完不起下一次、phase `paused`；`resume`＝解除；`stop`＝這次跑完以 0 結束、phase `stopped`（壓過同一道裡的其他東西）；
  `max`／`interval_ms` 寫了＝從現在起用它、寫 `null`＝回旗標／loop.json 的值、沒寫＝不動；`seq` 只回音（state 的 `ctl_seq`＝最後一道照做的指令的 `seq`）。三個動詞冪等。其他 key 忽略（`paused`／`stopped` 也是）。
  **新舊比內容**：解完的那份跟上一次讀到的一樣＝同一道、不再做；不一樣才照做一次。所以檔留著沒事、loop 不刪不改它；兩個人先後寫、loop 還沒讀＝後寫的算、前一道就沒了。
  **起來第一次讀到的當基準線、不執行**——殘留的 `{"cmd": "stop"}` 不會讓新起的馬上退，不用誰去清；代價是起來之前寫好的指令不算（要一起來就暫停見下面 state）。檔不見了＝沒有新指令，之後再寫的一律算新的（實作時代定）。
  讀到新的壞的（讀不了、不是 JSON 物件、型別不對、`cmd` 不認得、指示詞解不開）整份不採用、維持原狀、原因寫進 state 的 `ctl_warning`；照做了一道好的才清回 null。基準線那份壞的不提醒（實作時代定）。
- **state**（只有自己寫；先寫 `.state.json` 再改名，N-05）：只在兩次之間寫，**而且有變才寫**（[thinking 11-02 state 窗](../../thinking/2026-11-02-state-window.md)）：
  `{"phase": running／waiting／paused／done／stopped, "counter_runs", "max", "interval_ms", "paused", "ctl_seq", "ctl_warning", "pid", "started_at_ticks", "boot_id", "updated_at"}`，
  `counter_runs`＝跑過幾次（寫那一刻的快照）、`started_at_ticks`＝/proc/<pid>/stat 第 22 欄、`updated_at`＝這份寫出去的那一刻（ISO 8601 UTC 到毫秒，例 `2026-10-23T01:58:45.123+00:00`；最後一欄）（使用者 10-25「計數這塊，幫我改成counter_*」）。
  **有變才寫**：每次要寫先組好一份（不含 `updated_at`），跟上一份寫出去的比，**`counter_runs` 不算變動**（比的時候排除；使用者 11-02「對」），**`phase` 在 running／waiting 之間換也不算**（11-02 晚使用者「running/waiting確實不該算變動」；寫出去的照帶當下的）——一樣就不碰檔，不一樣才加 `updated_at` 寫。
  啟動後第一份、結束那份（帶 `code`）一定寫。會變的：進出 paused／stopped／done（有身體的 loop 跑著睡著來回時窗停在第一份）、讀到新的 ctl（`ctl_seq`、`max`、`interval_ms`、`paused`）、`ctl_warning` 變。
  **沒有心跳**（11-02 使用者「心跳這塊就直接看pid就好」）：睡著時窗不動；判活著看 `pid`＋`started_at_ticks`＋`boot_id`（N-17），不看檔案的更新時間。nap 最多睡 1 秒是為了讀 ctl、不是心跳。
  沒有 `exec`（只有 aos-daemon 會這樣）時一輪只讀一次 ctl、只 tend 一次、最多寫一份 `waiting`（不寫 `running`），睡著的 daemon 窗不動（使用者「都修都處理」，[thinking](../../thinking/2026-10-23-daemon-bench.md)）。
  **起來先暫停**（代定，使用者四態「休眠但是可以隨時叫醒繼續跑指令或繼續暫停」）：開了 state 窗、`$AOS_STACK` 裡已有一份舊的 state.json 而且它的 `paused` 是 `true`＝起來先暫停（第一份 state 就是 `paused`，等 `{"cmd": "resume"}`）；其他欄位不接（`counter_runs` 從 0、`max`／`interval_ms` 回設定）。
  `$AOS_STACK` 資料夾不在＝state 寫不了＝`WriteFailed`、退 1、那次沒跑，**不自己建**（建 stack 只在 aos-exec 做，N-59 第 1 件；經 aos-exec 跑時它已經建好）。
  結束時多 `code`（`done`＝自己跑完或失敗、`stopped`＝ctl 的 `stop`、收到訊號或自己的錯）；`max` 不限時是 `null`。

### 結束碼

| 情況 | 結束碼 | stderr |
|---|---|---|
| 那次退 0 | 下一次 | — |
| 那次退 10 | **0** | 不寫 |
| 那次退其他非 0（含被訊號停掉 128＋N、單子逾時被收掉＝143） | **那個碼** | 一行 `aos-loop: 第 N 次 誰 失敗，結束碼 C`（誰＝exec 的目標字串：字串 exec 原樣、陣列＝第一個元素；例 `loop.json#/body`；單子＝「設定檔名#指標」，例 `loop.json#/exec`） |
| 跑滿 `max` | 0 | 不寫（N-43） |
| 收到 SIGINT／SIGTERM／SIGHUP | **128＋N**（等那次結束之後） | 不寫 |
| 自己的錯（含 exec 的單子壞、起不來） | 1 | 一行 `aos-loop: 代號 原因` |

那次找不到入口、單子壞等（那一層 aos-exec 的錯）：stderr 先有一行 `aos-exec: 代號 原因`，那次的碼是 1，接著是 loop 那行「第 N 次 … 結束碼 1」——每層只說自己的（P-21）。所以字串目標指到的單子壞不是 loop 自己的錯，每次都會照跑一次 aos-exec、各自報。

### 訊號

整支程式的壽命都擋著 SIGINT／SIGTERM／SIGHUP（P-36「先收好自己起的子程式、寫好狀態再結束，結束碼非 0」）：

- **跑到一半收到**：轉給那次——`kill` 給那個子行程（那次的 aos-exec；它跟 aos-loop 同一個行程群組；不另設 SIGKILL 期限）；
  那次是單子時由那次的 aos-exec（監工）再轉給整群、過 `grace_ms` 還沒結束就 SIGKILL 整群。等那次結束，**不起下一次**，以 128＋第一個收到的訊號結束。
- **兩次之間收到**（含睡 interval、paused 的時候）：不起下一次，直接 128＋N（有開 state 窗就寫 `stopped`、`code`）。
- 在終端機按 Ctrl-C：那次的子行程跟 aos-loop 同群組，會直接收到一次、再收到 aos-loop 轉的一次（兩次）；單子的子程式自成群組，只收到那次的 aos-exec 轉的。

## 元素

```
 main ──▶ block_signals ──▶ loop_cli ──▶ Loop(opts, 設定檔, Defaults) ──▶ Loop::serve：每次 signal_got ──▶ read_ctl ──▶ tend ──▶ 停不停 ──▶ 睡（nap）或 run_once ──▶ write_state
                                                                                                                                   │
                                                          run_once(Target) ─┬▶ 目標：run_folder：fork 子行程 ──▶ aos::exec::run_cli({"--", 目標, 參數...})；等它、轉訊號
                                                                            └▶ 單子：run_inline：設 AOS_CF／CD／CO ──▶ aos::exec::run_inst（行程內）──▶ 還原
```

| 檔 | 做什麼 |
|---|---|
| `include/aos/loop.hpp` | 公開介面：`Run`（`code`、`signal`、`elapsed_ms`、`received`；沒有 `timed_out`）、`block_signals`、`take_signal`、`Target`（含 `inst`、`cf`、`co`、`ref_base`、`label()`）、`parse_target`（收字串、陣列、物件）、`resolve_exec`、`place_inline`、`pointer_escape`、`config_file`、`run_once(Target)`、`loop_cli`、`Loop(opts, spec, defaults)`（骨架，`tend`／`finish`／`info`／`check_ctl`／`write_more` 五個掛鉤給子類別：`tend()` 不帶參數、看 `paused_`／`stopping_`；`check_ctl` 可填 `ctl_note_`＝採用了但 `ctl_warning` 提醒一句；`write_more`＝每寫一份 state 之後寫子類別自己的窗，沒開 state 也呼叫——aos-daemon 用）、`Defaults`（`max` 預設 nullopt＝不限）、`write_window`、`heartbeat`、`resolve_keys`（aos-daemon、aos-fsm 共用）；代號 `aos::loop::code::*`（沿用 aos-exec 的＋`StackMissing`） |
| `src/common/common.hpp` | `using` |
| `src/run/run.hpp` | run 元素的內部介面：`the_signals`、`run_folder`、`run_inline` |
| `src/run/run.cpp` | `run_once`：目標＝組好 `-- 目標 參數...` 交給 `run_folder`；單子＝交給 `run_inline` |
| `src/run/inline.cpp` | `run_inline`：`AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置、相對的 `AOS_WS`／`AOS_STACK` 轉成絕對（跑完都還原）、行程內 `aos::exec::run_inst`、錯誤原因前面加「單子跑不起來：」、量毫秒 |
| `src/run/folder.cpp` | `run_folder`：擋 SIGCHLD、開 signalfd、fork；子行程解開訊號、呼叫 `aos::exec::run_cli`、`_exit` 它的碼；這邊等它、期間把三個訊號 kill 給它、量毫秒 |
| `src/run/signals.cpp` | `block_signals`（`sigprocmask`）、`take_signal`（`sigtimedwait` 不等） |
| `src/engine/engine.hpp` | engine 元素的內部介面：`is_nat` |
| `src/engine/config.cpp` | `resolve_keys`（設定檔、ctl 的指示詞：整份換一層、自己讀的格整個解）；`Loop` 的建構子：`load_cfg` 讀設定檔（`檔#/指標`）、解指示詞、旗標蓋上、驗 `exec`／`max`／`interval_ms`／`ctl`／`state`、算兩扇窗的路徑；`parse_target`、`resolve_exec`、`place_inline`、`config_file`（設定檔的實際路徑）、`loop_cli` |
| `src/engine/loop.cpp` | `Loop::serve`／`main_loop`（每次怎麼走；失敗那行的「誰」＝`exec_.target`）、`end`、`nap`（`sigtimedwait` 睡、收到訊號就醒）、`signal_got`、`say` |
| `src/engine/window.cpp` | 窗：`read_ctl`、`write_state`（有變才寫、`counter_runs` 與 running／waiting 互換不算；寫不了丟 `StateError`）、`log_line`（stdout 一行、擋 SIGPIPE）、`write_window`、`proc_fields` |
| `src/main.cpp` | 命令列：`block_signals` → `loop_cli` → `Loop` → `serve`；出錯印「aos-loop: 代號 原因」 |

## 實作注意

- **每次在子行程裡呼叫 aos-exec 的 `run_cli`、不 exec 一支 aos-exec**（使用者 § 20「aos-loop,daemon……可以隨意使用……aos-exec的公開api」），不必在 PATH 上找 aos-exec。
  aos-exec 在挑入口之前讀 `.env`、每走一層都 cd 和 setenv，所以整段都在子行程裡做；子行程等同那一層 aos-exec，它的錯照 aos-exec 的格式說（`aos-exec: 代號 原因`）、碼 1。
  fork 時 aos-loop 只有一條執行緒，子行程裡做 C++ 配置、setenv 不會撞鎖。
- **PATH 不動**、原樣傳給那次；那次裡要再叫 `aos-exec`、`aos-fsm`，它們要本來就在 PATH 上（demo 的做法：各支的 `bin/` 都放 PATH）。
- **單子物件在行程內 `run_inst`**：逾時、整群收、轉訊號由 `run_inst` 做，跟 aos-exec 跑單子同一套。在行程內 setenv 三個 `AOS_*` 再還原是安全的：aos-loop 單執行緒，`run_inst` 的工人執行緒在它回來前就 join 了。
- **`Run` 是公開 API**：aos-fsm 也用 `run_once` 跑一格（格的 `exec` 跟 loop.json 的 `exec` 同一套寫法、同名）；
  沒有 `timed_out`（loop 看不到格裡有沒有逾時；字串目標的單子逾時＝那次的 aos-exec 以 143 正常結束；單子物件行程內跑時 `code` 143、`signal` 15）；`received` 給「收完這次再以 128＋N 結束」用。
- **整支程式擋著三個訊號**：不擋的話 SIGTERM 一來 aos-loop 先死、那次變孤兒繼續跑。

## 錯誤代號

自己出錯：stderr 一行 **`aos-loop: 代號 原因`**、退 1（同 aos-exec 的格式，N-60／P-21）。

| 代號 | 什麼時候 |
|---|---|
| `ArgumentsBad`（共用） | 沒給、多給設定檔；旗標缺值 |
| `FlagUnknown`（共用） | 不認得的旗標（含 `--cfg`） |
| `CfgMissing`（共用） | 設定檔不在；`#/` 指標指不到 |
| `CfgBad`（共用） | 設定檔讀不了、不是 JSON；不是物件；`#` 後面不是 `/`；沒有 `exec`；`exec` 不是字串、非空字串陣列或物件；`max`／`interval_ms` 不是非負整數（`"3"`、`2.5`、`true`、`null`、負的都不行；旗標 `--max`／`--interval-ms` 不是 `[0-9]+`）；`ctl`／`state` 不是非空字串 |
| `DirectiveBad`（共用） | 設定檔裡 loop 讀的格的指示詞解不開（變數沒設、`$ref` 讀不到、指不到、繞圈）；exec 的單子裡的指示詞跑的時候解不開 |
| `EntryBad`（共用） | exec 的單子形狀不對（`argv` 不是非空字串陣列、型別不對…；同 aos-exec） |
| `StackMissing` | 寫了 `ctl` 或 `state` 卻沒設 `AOS_STACK` |
| `WriteFailed`（共用） | state 窗寫不了（含 `$AOS_STACK` 資料夾不在） |
| `LaunchFailed`（共用） | fork 失敗；exec 的單子起不來（找不到程式、cwd 不在、串流開不了） |
| `Internal`（共用） | 準備轉送訊號（signalfd）失敗、照理不會發生的例外 |

## 建置與測試

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

`ctest` 跑 `test_cli`（`tests/test_cli.py`，78 組，約 15 秒；看 log 的案例 `run`／`start`／`run_loop` 給 `log=True`＝加 `--enable-logs`）：

- A 段：失敗碼、內嵌單子每次跑、跑滿 max 不寫 stderr、10／7、失敗那行的「誰」＝exec 的目標、自己的錯一行。
- B 段：`max` 沒寫＝不限／0／負的、欄位型別、字串 exec 走 aos-exec 的規則（AOS_WS／AOS_STACK／AOS_CF／AOS_CD／cd、JSON 入口、每次重找入口、入口不在＝那次碼 1）、沒給 `--enable-logs` 時不寫 stdout、PATH 原樣傳給那次、單子的 `$env`＋相對 cwd（`$env` 沒設＝那次 aos-exec 的錯）、逾時＝失敗（143）、被訊號停掉＝128＋N。
- C 段：訊號（SIGTERM 轉給字串 exec、SIGINT 轉給單子、SIGHUP 停掉那次，都是收完再 128＋N）。
- D 段：選填 key——state 欄位、沒開窗不寫檔、窗沒 AOS_STACK、interval 壞／有睡、ctl stop＋seq、ctl 的 max、壞 ctl、pause 再 resume、睡 interval 時收到訊號、stop 壓過其他、max／interval_ms 寫 null 回設定、殘留的 ctl 當基準線、cmd 不認得、同一道不重做、後寫的算、舊 state 的 paused＝起來先暫停（寫 ctl 的案例在身體第 n 次跑時寫，`count_then`）；`$ref` 從設定檔的資料夾算。
- E 段：命令列——usage 的各種寫法（沒給、多給、不認得、缺值、`--cfg`）、`--max`／`--interval-ms` 不是非負整數＝CfgBad、旗標蓋過 loop.json（`--max`、`--max=`、`--state`、`--ctl` 卻沒 AOS_STACK）、設定檔 `檔#/指標`（指不到、`#` 後沒 `/`、不是物件、讀不到）、exec 陣列（參數照接、`-` 開頭的目標、失敗那行的「誰」）、`aos-exec loop.json` 當入口（`_entry` 帶 `{"$env": "AOS_CF"}`）。
- F 段 1 組：`$AOS_STACK` 不在不建、`WriteFailed`、那次沒跑。
- G 段 5 組：設定檔的指示詞（`exec`／`max`／`state`、整份 `$ref`、exec 陣列元素）、解不開＝`DirectiveBad`（沒設、讀不到、繞圈；寫法不合原封不動＝`CfgBad`）、不讀的 key（body）不解、ctl 的 `$ref`（相對 ctl 的資料夾、整份 `$ref`）、ctl 解不開不採用。
- H 段 9 組：exec 直接放單子——每次跑與 `AOS_CF`／`AOS_CD`／`AOS_CO`／cwd、設定檔 `檔#/指標` 的 `AOS_CO`、指示詞跑的時候才解與 `$ref` 起點、exec 本身是 `$ref`、0／10／7、逾時 143、形狀壞（`EntryBad`／`DirectiveBad`／`LaunchFailed`）、SIGTERM 轉給單子、跑完 `AOS_CO` 還原。
- H2 段 3 組：相對 `AOS_STACK`／`AOS_WS` 轉成絕對、絕對的不動、捷徑設定檔的相對基準。
- I 段 9 組：log 一次一行（欄位、值、started_at 寫法）、跟身體的 stdout 交錯、失敗與被訊號停掉那次也印、`--enable-logs`（預設不印、不帶值、usage 有它）、stdout 是關掉的管子照跑完（身體的 SIGPIPE 沒被改成忽略）、max 0 沒有 log、睡 interval 時 state 不動（內容與 mtime；窗停在 running）、interval 0 時跑的期間只寫一份 running、running／waiting 來回只寫一份而 paused 照寫。
- J 段 5 組：`-- 參數`（字串目標、陣列、設定檔後面接的不是 `--`＝`ArgumentsBad`、`--` 後面沒東西）、單子 argv 接參數與 argv 是指示詞＝`CfgBad`、`-- -odd.json -- q`、端到端 `aos-exec <資料夾> -- 題`（資料夾的 `_entry` 是 loop 設定）、ctl／state 寫 null＝不開。

A～D 段寫內嵌單子的案例用 `{"exec": "loop.json#/body", "body": 單子}`。demo 的整合測試在 [aos-fsm](../aos-fsm/README.md) 的 `test_demo`。
