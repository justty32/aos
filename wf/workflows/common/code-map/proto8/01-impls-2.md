← [入口](../proto8.md)｜涵蓋：`proto8/impls/` 的 `aos-loop`、`aos-fsm`、`aos-daemon`、`aos-post`、`aos-lock`｜上一份：[01-impls](01-impls.md)｜下一份：[01-impls-3](01-impls-3.md)

行為細節以各專案 README 為準。路徑相對於該段標題的資料夾。建置檔（`CMakeLists.txt`、`vcpkg.json`、`.gitignore`）見 [01-impls](01-impls.md) 的共通段。

## `impls/aos-loop/`（一次次跑；骨架 `aos::loop::Loop` 是公開的，aos-daemon 繼承它）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/loop.hpp` | 公開介面：擋訊號、兩次之間取訊號、`parse_target`（`exec` 是字串、`[目標, 參數...]` 或單子物件）、`Loop` |
| `src/main.cpp` | 命令列 `aos-loop [旗標] loop.json [-- 參數...]` |
| `src/engine/loop.cpp` | 每次怎麼走、`log_line`（`--enable-logs`） |
| `src/engine/window.cpp` | 窗：`read_ctl`（ctl 指令 `cmd`／`max`／`interval_ms`／`seq`，比內容判新舊）、`write_state`（有變才寫）＋子類別的 `write_more` |
| `src/engine/config.cpp` | `resolve_keys`（設定檔與 ctl 的指示詞，daemon、fsm 共用）、`Loop` 建構子（旗標 ＞ 設定檔 ＞ 預設；`ctl`／`state` 沒寫＝`ctl.json`／`state.json`、`null`＝不開，11-04）、`parse_target`、`resolve_exec`、`place_inline`、`loop_cli`、`add_args` |
| `src/engine/engine.hpp` | engine 的內部標頭 |
| `src/run/run.cpp`、`src/run/run.hpp` | `run_once`：目標交給 `run_folder`、單子交給 `run_inline` |
| `src/run/folder.cpp` | fork 子行程呼叫 aos-exec 的 `run_cli`、轉訊號 |
| `src/run/inline.cpp` | 行程內跑單子：設 `AOS_CF`／`AOS_CD`／`AOS_CO`、相對 `AOS_WS`／`AOS_STACK` 轉絕對、`run_inst` |
| `src/run/signals.cpp` | 整支程式壽命擋訊號、兩次之間取出 |
| `src/common/common.hpp` | 內部共用標頭 |

## `impls/aos-fsm/`（一次跑一格）

| 檔 | 負責什麼 |
|---|---|
| `src/main.cpp` | 跑一格：`run_once` → `next_for` 查表 → 查到寫 state 退 0、查不到以格的碼退；訊號照表寫完再 128＋N |
| `src/table/table.cpp`、`src/table/table.hpp` | `read_table`（解指示詞、單子記 `exec_bases`）、`check`（開跑查整張表，壞＝`CfgBad`）、`pick`、`next_for`（`next` 是字串或 `{結束碼: 狀態名}`） |
| `src/state/state.cpp`、`src/state/state.hpp` | `stage.txt`（11-04 前叫 `state.txt`）的讀（去頭尾 Unicode 空白、`StateBad`）與原子寫 |
| `src/common/common.hpp` | 內部共用標頭 |

## `impls/aos-daemon/`（顧一群 proc）

| 檔 | 負責什麼 |
|---|---|
| `src/main.cpp` | 命令列 `aos-daemon [旗標] daemon.json [-- 參數...]` |
| `src/daemon/daemon.cpp`、`src/daemon/daemon.hpp` | 名單 `procs`：`read_procs`、`is_once`（看寫法判 exec 型）、`adopt`（接回）、`tend`、`reconcile`、`halt`／`term`／`hold`／`look`／`start`、`check_running`（11-05 `DaemonRunning`；B 線改 flock 鎖 stack 資料夾）、`unrel`（11-05 表上相對 daemon stack 的路徑拼回）、`ctl_slept`（11-05 sleep／wake）、`cell_of`、`exec_of`（列上的 `exec` 欄，11-04 晚）、`def_of`（列上的 `def` 欄＝定義資料夾，11-04）、`finish`（收工；還在跑的 loop 型留成 `sleeping`）、`fail_reason`（11-05 晚：loop 型退非 0 留 `stopped` 的 reason）、`run_body`／`info`（11-05 晚：身體由 daemon 自己在 tend 最後跑，失敗記一行下一圈再跑、state 的 `body_code`） |
| `src/daemon/windows.cpp` | `procs_ctl.json` 的讀與驗（`read_procs_ctl`、`check_lists`、`check_once`；11-05 多認 `procs_slept`／`procs_woken`）、`procs_state.json` 的寫（`write_more`：11-04 起頂層回報 `procs_loop`／`procs_exec`／`procs_stderr`／`procs_ctl_mailbox`、超過 100 列切 `write_parts`、`clean_parts`） |
| `src/daemon/mailbox.cpp` | 信箱 `procs_ctl_mailbox`：`open_mailbox`（`cur/` 殘骸照 aos-post 的 `sort_letters` 排）、`take_letters`（`take_all`、`see`）、`apply_letter`（`procs_added`／`removed`／`stopped`／`started`／11-05 `slept`／`woken`）、`done_letters`（`reply`、`done`） |
| `src/child/child.cpp`、`src/child/child.hpp` | 子項：建小格、寫小格的 `loop.json`（三個檔名 `CellNames`＝daemon.json 的 `procs_loop`／`procs_exec`／`procs_stderr`，11-04）、`spawn`／`spawn_exec`、`launch`（setsid、`AOS_STACK`、`AOS_WS`、`AOS_DAEMON`）、`Child` 與狀態列（`row`：…`stack`、`exec`、`def`、`ws`?、11-05 `reason`；路徑存相對 daemon stack）、`rel_to`／`rel_spec`／`daemon_ref`／`rel_refs`（11-05 相對化；小格 loop.json 的 exec 寫成 `$env AOS_DAEMON` 指示詞） |
| `src/common/common.hpp` | 內部共用標頭 |

## `impls/aos-post/`（投遞：信箱，IPC 的語法糖）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/post.hpp` | 公開介面：`Mailbox`（`tmp`／`fresh`／`cur`／`archive`）、`SendOpts`、`Seen`、`init`／`open`／`send`／`take`／`take_all`／`first_in_cur`／`see`／`reply`／`done`／`regret`、`reply_to_rel`／`reply_to_abs`（11-05）、`check_name`／`is_ordered`／`sort_letters`（處理順序：有序在前）；aos-daemon、aos-llm-kernel、aos-llm 連它 |
| `src/main.cpp` | 命令列 `aos-post init\|send\|take\|take-all\|see\|done\|regret [旗標] 信箱 [信件名稱]`；沒東西退 10 |
| `src/mailbox/mailbox.cpp` | 信箱路徑、`init`、`open`；信件名稱規則 `check_name`、`is_ordered`、`sort_letters`；`reply_to_rel`／`reply_to_abs`（信封的 `reply_to` 存相對信箱根、讀時拼回，11-05）；common 小工具的實作 |
| `src/send/send.cpp` | `send`（入口檢查：`tmp/`、`new/` 可寫、`reply_to`、自己給的名字；`tmp/` 寫好 rename 進 `new/`；sender 用 aos-util 的 `identity`）、`--ordered`（經 aos-lock 拿 `order.lock/` 編序號） |
| `src/take/take.cpp` | `take`／`take_all`（`cur/` 沒有就建）、`first_in_cur`、`see`、`reply`、`done`（`--keep` 進 `archive/`）、`regret` |
| `src/common/common.hpp` | 內部標頭：`is_dir`、`need_dir`、`make_dir`、`names_in`、`drop`、`move` |

## `impls/aos-lock/`（鎖資料夾＋名牌）

| 檔 | 負責什麼 |
|---|---|
| `include/aos/lock.hpp` | 公開介面：`Holder`、`Seen`、`STALE_MS`、`try_acquire`／`acquire`／`release`、`look`、`reapable`；aos-post 連它 |
| `src/main.cpp` | 命令列 `aos-lock acquire\|release\|show [旗標] 目標`；拿不到／沒有鎖退 10 |
| `src/holder/holder.cpp` | 名牌：`holder_of`（身分用 aos-util 的 `identity`）、`to_json`、`look`、`reapable`（boot_id、pid＋ticks、殭屍、租約、名牌壞） |
| `src/lock/lock.cpp` | `lock_dir_of`、寫名牌、收屍 `reap`、`try_acquire`、`acquire`（每 20 毫秒）、`release` |
| `src/common/common.hpp` | 內部標頭：`now_ms`、`parse_at` |
