# proto8/impls：aos 的 C／C++ 實作（總入口）

**一句話：這一家小工具做的是同一件事——「在工作區起一個程式、等它、看它的結束碼」——由小到大疊起來：
`inst`（C lib，跑一次）→ `aos-exec`（在工作區執行一個資料夾程式）→ `aos-loop`（一次次跑）／`aos-fsm`（一次跑一格）→ `aos-daemon`（顧一群 loop）；
旁邊三個幫手：`aos-util`（全家共用的函式庫）、`aos-directive`（解 `$ref`／`$env`）、`aos-schema`（用 JSON Schema 驗 JSON）。**

## 現況

**提供九支命令列（C++）**：`aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon`、`aos-llm-kernel`、`aos-llm-send`、`aos-json`、`aos-post`、`aos-lock`（後兩支 10-29）。impls 是唯一實作（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」；fsm 和 tick 使用者選「fsm 也改用 C++、tick 先留 Python」）：`proto8/bin` 只剩 Python 的 `aos-tick`。`proto8/tests`（`tests/aos_bins.py`）與 `proto8/demo/run.sh` 直接跑各支的 `bin/`（要先照下面「建置」建好）。這頁與各專案 README 裡說「對齊 bin」「跟 Python 版的差異」的，是 Python 版還在時的對照。
`inst` 是 C 函式庫、不提供命令列；inst 單子的 JSON 解析不進 C 庫，放在 aos-exec 的 C++ 庫（`src/inst/`）；沒有 `aos-inst` 命令列。`aos-util`、`aos-directive`、`aos-schema` 以**函式庫**的形式留著；aos-directive、aos-schema 的 `bin/` 不算對外提供。各支的細節在各自的 README，這裡只列全家共通的現行行為：

- **aos-exec**：`aos-exec [--ws WS] XXX [args...]`（旗標在 XXX 前；旗標解析在 aos-util 的 `aos/cli.hpp`）。每走進一個資料夾就 cd、讀那裡的 `.env`、旗標蓋回，讀完才照 `$AOS_ENTRY` 挑入口（旗標 ＞ `.env` ＞ 原本環境 ＞ 預設）。`.env` 是 dotenv 基礎子集（`export `、`=` 兩邊空白、引號、空白＋`#` 註解、去頭尾空白——值的空白照 python-dotenv 認 Unicode 空白、行首只認 ASCII；aos-util 的 `aos/text.hpp` 管 Unicode 空白與 UTF-8 檢查），預設不蓋已有的，不帶值的旗標 `--dotenv-override` 才蓋（只管這一跳；`parse_cli` 收開關表）。資料夾與沒 `argv` 的 JSON 物件都一路往下、環境變數六個（含 `AOS_CO`）、字串轉向＝全新的一跳；入口是 inst 單子時在行程內交給 `inst`（C lib）跑。公開 API 是 `run_cli`＋`run_inst`＋`argv0`（`aos/exec.hpp`）。
- **aos-loop、aos-fsm、aos-daemon**：命令列都是「旗標＋唯一一個設定檔（可寫 `檔#/指標`）」，都是「小庫＋薄命令列」（ideas § 23「重寫吧，fsm一起做」）。全家「要跑什麼」這一格一律叫 `exec`（fsm 是每一格的；使用者「fsm.json，現在是用val，幫我改成exec」「exec，loop／daemon 的 run 也一起改 exec」）；`val` 只用在 C-55「值長成物件時原值放 `val`」（ctl 的 `paused`／`stopped` 雙形那類）。`exec` 是字串或 `[目標, 參數...]`＝每次在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`；是物件＝單子，在自己行程內呼叫 aos-exec 的 `run_inst` 跑（aos-loop 的 `run_once`／`src/run/inline.cpp`），跑的期間 `AOS_CF`／`AOS_CD`／`AOS_CO` 設成單子的位置（設定檔、它的資料夾、`/exec` 或 `/states/<名>/exec`），單子裡的指示詞跑的時候才解（`resolve_exec`）（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking](../thinking/2026-10-24-exec-relative.md#10-24-exec-直接放單子)）。讀設定檔與 ctl 時解指示詞（只解自己讀的格；aos-directive 的 `resolve_shallow`、aos-loop 開出的 `resolve_keys`；解不開：設定檔 `DirectiveBad` 退 1、ctl 不採用；[thinking](../thinking/2026-10-23-daemon-ctl-ref.md)）。aos-loop 有 `interval_ms`／`ctl`／`state` 窗、`max` 沒寫＝不限、`$AOS_STACK` 不在＝`WriteFailed`、不自己建。aos-fsm 借 aos-loop 的 `run_once` 跑一格、開跑時查整張表（表壞 `CfgBad`）、state 在但讀不了 `StateBad`、trace 沒有 `timed_out`。
- **aos-daemon**：繼承 aos-loop 的 `Loop`（ideas § 25）；子 loop 經 aos-exec 起（exec 成 PATH 上的 aos-loop），寫小格時把字串子項包成 `{"exec": …}`、給子項的單子補 `cwd`、相對 `$ref` 轉絕對。收子項不等（送 SIGTERM 後照常巡、那列 `stopping`、滿 10 秒才 SIGKILL）；表用雜湊找名字、沒有 `exec` 時一圈一份 state（不寫 `running`）、起子項前先寫一份 state、小格只建一層（使用者「都修都處理」，[thinking](../thinking/2026-10-23-daemon-bench.md)）。**兩個手把、兩扇狀態窗**（10-29 拆窗，[medium-plan § 四](../thinking/2026-10-29-medium-plan.md)）：`ctl.json`／`state.json` 只管 loop 面向（同 aos-loop），名單的手把是 `loops_ctl.json`（`loops`、`loops_added`、`loops_removed`、`seq`）、子項表在 `loops_state.json`（daemon.json 的 `loops_ctl`／`loops_state`，沒寫＝這兩個檔名、`null`＝不開）；兩份 ctl 每圈各自讀、各自採用，ctl `paused`／`stopped` 的那圈不調表；`ctl.json` 寫了 `loops*`＝不採用、過渡期 `ctl_warning` 提醒搬家。擋子項名字跟自己的窗撞名（起來時 `CfgBad` 退 1、loops_ctl 撞＝不採用）。期望表＝loops_ctl 的 `loops` 或 daemon.json 的＋added－removed；`loops` 要拆檔寫 `{"$ref": [檔, …]}`（aos-directive 的 `$ref` 陣列：幾份照順序合成一份）；loops_state 的 `loops` 超過 100 列自動切成 `{"$ref": ["loops_state_loops/<雜湊>.json", …]}`。**信箱模式**（10-29，medium-plan § 四 3）：daemon.json 寫 `loops_mailbox`（路徑）＝名單的增減改成一封封 N-16 的信（連 aos-post 的庫）、`loops_ctl` 不開（兩個都明寫＝`CfgBad`）；每圈（`paused`／`stopped` 那圈不認領）全部認領（起來時 `cur/` 的殘骸排前面重做）、照名字順序逐封套進期望表（body 的 `loops_added`／`loops_removed`）、套完才對一次表、信收掉，有 `reply_to` 的好信回 `{"applied": true}`；壞信丟掉、原因進 loops_state 的 `letter_warning`、不回；期望表＝daemon.json＋重起時接回的＋信，接回的留到有信 `loops_removed` 它。
- **指示詞與 argv**（ideas 10-20 D1～D15）：`$ref` 的位置只認 `#/`、argv 陣列裡可放指示詞、argv[0] 帶 `/` 又 exec 不了交給 aos-exec、`$path`（字串拼接）／`$prefix`、寫法寬容；`$fmt` 未定、沒做。
- **LLM kernel**（[thinking](../thinking/2026-10-24-llm-kernel.md)；使用者「LLM kernel，也就是把brain這塊弄成一個請求，而不是直接打API，請求會被丟到某個地方，由kernel排隊跑」）：[aos-llm-send](aos-llm-send/README.md)（`aos-llm-send 單子.json`：把單子寄進 `$AOS_KERNEL` 信箱、等回信、stdout／stderr／碼原樣交回、收到訊號撤信）、[aos-llm-kernel](aos-llm-kernel/README.md)（`aos-llm-kernel kernel.json`：給 loop／daemon 一次次拍，收拾、排隊、`slots` 封各 fork 一個子行程交給 `run_inst`、回信、`served.jsonl`；單子的 `_metainfo.time_ms` 同級時短的先，使用者「_metainfo好了之後，讓kernel實際去用用看」）。信箱與信的格式在 aos-llm-kernel 的公開標頭 `aos/llm_kernel.hpp`，閘門連它。10-29（N-15、N-16 的 10-29 補）：kernel 鎖整個信箱的 flock 檔叫 `<信箱>/.flock`（原叫 `.lock`，`.lock/` 留給 N-15 的資料夾鎖，舊名不認）；閘門寄的 `letter.json` 多信封三欄 `kind: "letter"`、`sender`（`$AOS_WS`，沒設＝`$HOME`）、`sent_at`，kernel 不檢查也不擋，`inst`／`env`／`priority` 過渡期照舊在頂層；回信（`done/`＋`reply.json`）照舊；信裡寄信人那個 flock 檔 10-29 改名 `sender.flock`（原 `sender.lock`，同一個理由，舊名不認）。token 回報與額度（照 rewrite-order 第 3 題推薦，使用者「都按建議做」）：kernel 跑信時給 `AOS_KERNEL_REPORT`，腦願意就寫 usage；kernel.json 的 `budget` 設 `max_calls`／`max_tokens` 每窗上限，到頂回 `BudgetMissing` 或等下一窗。
- **aos-json**（嘗試，[thinking](../thinking/2026-10-24-aos-json.md)；使用者「做一套方便修改json的工具集，配合指示詞」）：[aos-json](aos-json/README.md)（`aos-json 子命令 [旗標...] 檔#/指標 [值]`：讀、改 aos 的 JSON 設定，認得 `$ref`／`$env`，可穿過 `$ref` 改被參照的檔、只重寫有變的那一塊、寫之前先驗形狀），另有兩個給腦掛的工具 `tools/json/`、`tools/json_edit/`。庫 `lib/libaos-json.a` 沒有公開標頭（沒人連它）。
- **投遞與鎖**（10-29，[medium-plan § 二、§ 三、§ 五](../thinking/2026-10-29-medium-plan.md)；NORMS N-15、N-16 的 10-29 補）：[aos-post](aos-post/README.md)（`aos-post 子命令 [旗標...] 信箱 [信號]`：N-16 標準投遞——`init`、`send`、`claim`、`claim-all`、`check`、`finish`〔`--keep`、`--reply`〕、`withdraw`；`send --ordered`＝有順序的投遞，`order.lock/`＋`order.json`）、[aos-lock](aos-lock/README.md)（`aos-lock 子命令 [旗標...] 目標`：N-15 的鎖——`acquire`〔`--lease-ms`、`--note`、`--wait-ms`、`--pid`〕、`release`、`show`；名牌 `holder.json`、判死活看 pid＋`started_at_ticks`＋`boot_id`、收屍）。兩支都是「庫＋薄命令列」，公開標頭 `aos/post.hpp`、`aos/lock.hpp`（aos-daemon 的信箱模式要連 aos-post）；aos-post 連 aos-lock。
- **使用者看得到的名字**（使用者「都先幫我統合」，對照表見 [thinking/2026-10-23-naming](../thinking/2026-10-23-naming.md)；C-54 命名方法）：state 的 `phase`、`counter_runs`、`started_at_ticks`、`recorded_at`（時間值一律 ISO 8601 UTC 到毫秒，例 `2026-10-23T01:58:45.123+00:00`）；daemon 子項 `done`（自己結束）／`stopped`（daemon 收掉）；fsm trace 的 `started_at`、`elapsed_ms`；訊息裡說「第 N 次」（不說「第 N 圈」）；錯誤代號照 C-54 收成 `…Missing`／`…Unknown`／`…Bad`／動作＋`Failed`（下面代號表是現行的）。純文字檔帶 `.txt`（aos-fsm 的 `$AOS_STACK/state.txt`、暫存 `.state.txt`；aos-daemon 小格的 `stderr.txt`）；`AOS_STACK` 預設 `$AOS_WS/.stack/`；demo 題目資料夾 `new/`（認領搬 `cur/`）。計數一律 `counter_*`、時間點 `<發生了什麼>_at`、上限 `max_*`（使用者 10-25「state.json中，runs改counter，at改成recorded_at」「計數這塊，幫我改成counter_*」，回頂層兩題「都好」，頂層代定、可翻案）：aos-llm-kernel 的 queue.json `counter_runs`（`seen_at_runs`＝第幾次看到，是時間點）、used.json `counter_calls`／`counter_tokens`／`counter_all_calls`／`counter_all_tokens`、served.jsonl `counter_tokens`／`counter_waited_runs`／`served_at`、kernel.json `budget.max_calls`／`budget.max_tokens`。不留舊名：讀到舊名的 used.json＝`UsedBad`、queue.json＝`QueueBad`、kernel.json＝`CfgBad`。庫裡的名字：aos-loop 的 `run_once`、`struct Run`、`src/run/`、`Defaults::need_exec`、`Loop::has_exec_`／`exec_`，aos-fsm 的 `Cell::exec`；其餘內部變數、結構欄位沒跟著改名（例 `runs_`）。

每個專案是一個獨立的 CMake 專案（照 [dcap](../../../dcap/README.md) 的慣例），差異記在各自的 README。這一頁講「全家一樣的東西」，各專案的 README 只講自己。

## 地圖與依賴

```
 aos-llm-send     寄信：單子＋整份環境＋priority → $AOS_KERNEL 信箱 new/，等 done/ 的回信、原樣交回      src/{send,wait,common}
     │ 連 aos-llm-kernel 的公開標頭（信箱與信的格式）
 aos-llm-kernel  一次：鎖信箱 → 收拾 → 排隊 → 額度到頂就回錯／停 → 認領 slots 封、各 fork 一個子行程 run_inst → 回信、served.jsonl、used.json   src/{letter,queue,serve,budget,common}
     │ 連 aos-loop 的公開 API（擋訊號、resolve_keys；跑單子＝aos-exec 的 run_inst）
 aos-daemon   一個 loop＋子 loop 的表：$AOS_STACK/<名字>/ 小格、loops_ctl 增減（或信箱模式 loops_mailbox）、loops_state 表（loops、execs 兩張；execs＝直接 aos-exec 一次的子項，10-30）、不自動重起、adopt   src/{daemon,child,common}
     │ 繼承 aos-loop 的 Loop；信箱模式連 aos-post 的庫（aos/post.hpp）；子 loop＝fork 後子行程呼叫 run_cli(-- 小格/loop.json#/_entry)，exec 成 PATH 上的 aos-loop
 aos-fsm      一次跑一格：$AOS_STACK/state.txt → 跑那格 → 照 next 換（字串＝碼 0 才換；物件＝照碼查，10-30）；trace.jsonl   src/{table,state,common}
     │ 跑一格借 aos-loop 的 run_once（aos/loop.hpp）
 aos-loop     一次次跑 exec：0 下一次、10 停、其他非 0 失敗；轉訊號、收完 128＋N；interval_ms、ctl／state 窗  src/{run,engine,common}
     │ 每次：fork 子行程呼叫 aos-exec 的 run_cli({"--", 目標, 參數...})（等同起一支 aos-exec）
 aos-exec     [--ws WS] XXX——定工作區、走進去（cd、讀 .env）、挑入口、備六個 AOS_*、開跑   src/{cli,find,env,inst,launch,common}
     │        可執行檔／argv 陣列＝exec；inst 單子＝行程內交給 libaos、留著當監工
     │ 靜態連 inst（inst-static）、aos-directive、aos-util
     ▼
 inst         純 C 的 libaos：fork＋exec、等、限時收掉。零 malloc、給 FFI     include/aos.h、src/inst_*.c

 aos-util       全家共用：錯誤、三扇門（stdin／stdout／stderr）、旗標（aos/cli.hpp，另有較早的 aos/flags.hpp）、路徑與原子寫入、子程序、訊號
                ← aos-exec、aos-directive、aos-schema 都連它（aos-loop、aos-fsm 經 aos-exec 連到）
 aos-directive  解 JSON 裡的 {"$ref": 檔[#/指標]}、{"$env": 變數}，可帶 $path（字串拼接）、$prefix（lib＋bin） ← aos-exec 連它（單子、argv 陣列、JSON .env key 的指示詞）；aos-loop 也連（設定檔與 ctl）
 aos-schema     用 JSON Schema（draft-07）驗 JSON（lib＋bin）                  ← 獨立，只連 aos-util
 aos-json       讀、改 aos 的 JSON 設定：檔#/指標、穿 $ref、只重寫變的那塊、check（lib＋bin＋tools/）  ← 連 aos-directive、aos-util；test_tool 要 aos-exec 的 bin/
 aos-post       投遞（N-16 信箱）：寄、認領、check、finish（--reply）、撤回；send --ordered（lib＋bin，公開 aos/post.hpp）  ← 連 aos-lock、aos-util；aos-daemon 的信箱模式連它
 aos-lock       鎖（N-15）：mkdir .lock/、名牌 holder.json、判死活、收屍（lib＋bin，公開 aos/lock.hpp）  ← 只連 aos-util
```

| 專案 | 是什麼 | 產物 | 現況 | README |
|---|---|---|---|---|
| aos-exec | 命令列：`aos-exec [--ws WS] XXX [args...]`，在工作區執行一個 aos 程式（`.env`、含行程內跑 inst 單子）；庫有公開 API（`run_cli`、`run_inst`、`argv0`） | `lib/libaos-exec.a`、`bin/aos-exec` | **提供** | [aos-exec](aos-exec/README.md) |
| aos-loop | 命令列：`aos-loop [旗標] loop.json`，一次次跑 `exec`；庫有公開 API（跑一次、骨架 `Loop`、`loop_cli`） | `lib/libaos-loop.a`、`bin/aos-loop` | **提供** | [aos-loop](aos-loop/README.md) |
| aos-fsm | 命令列：`aos-fsm [旗標] fsm.json`，一次跑一格 | `lib/libaos-fsm.a`、`bin/aos-fsm` | **提供** | [aos-fsm](aos-fsm/README.md) |
| inst | C 函式庫 libaos：起一個程式、等它結束、告訴你結果 | `lib/libinst.so`（FFI）、`lib/libinst.a` | 庫（不讀 JSON、沒有命令列） | [inst](inst/README.md) |
| aos-util | 全家共用的 C++ 函式庫 | `lib/libaos-util.a` | 庫 | [aos-util](aos-util/README.md) |
| aos-directive | 指示詞 `$ref`／`$env`（可帶 `$path`（字串拼接）、`$prefix`） | `lib/libaos-directive.a`、`bin/aos-directive` | 庫（bin 不對外提供） | [aos-directive](aos-directive/README.md) |
| aos-schema | JSON Schema 驗證 | `lib/libaos-schema.a`、`bin/aos-schema` | 庫（bin 不對外提供；aos-exec 不連） | [aos-schema](aos-schema/README.md) |
| aos-llm-kernel | 命令列：`aos-llm-kernel [旗標] kernel.json`，LLM kernel 跑一次（挑信、跑、回信）；庫有公開標頭 `aos/llm_kernel.hpp`（信箱與信） | `lib/libaos-llm-kernel.a`、`bin/aos-llm-kernel` | **提供** | [aos-llm-kernel](aos-llm-kernel/README.md) |
| aos-llm-send | 命令列：`aos-llm-send [旗標] 單子.json`，把單子寄給 kernel、等回信、原樣交回 | `lib/libaos-llm-send.a`、`bin/aos-llm-send` | **提供** | [aos-llm-send](aos-llm-send/README.md) |
| aos-json | 命令列：`aos-json 子命令 [旗標...] 檔#/指標 [值]`，讀、改 aos 的 JSON 設定（認得 `$ref`／`$env`）；另有給腦掛的工具 `tools/json/`、`tools/json_edit/`；庫沒有公開標頭 | `lib/libaos-json.a`、`bin/aos-json` | **提供**（嘗試） | [aos-json](aos-json/README.md) |
| aos-daemon | 命令列：`aos-daemon [旗標] daemon.json`，顧一群子 loop（經 aos-exec 起） | `lib/libaos-daemon.a`、`bin/aos-daemon` | **提供** | [aos-daemon](aos-daemon/README.md) |
| aos-post | 命令列：`aos-post 子命令 [旗標...] 信箱 [信號]`，N-16 投遞（含有順序的投遞）；庫有公開標頭 `aos/post.hpp` | `lib/libaos-post.a`、`bin/aos-post` | **提供**（10-29） | [aos-post](aos-post/README.md) |
| aos-lock | 命令列：`aos-lock 子命令 [旗標...] 目標`，N-15 的鎖；庫有公開標頭 `aos/lock.hpp` | `lib/libaos-lock.a`、`bin/aos-lock` | **提供**（10-29） | [aos-lock](aos-lock/README.md) |

## 從哪開始讀

1. **aos-util**（最小）：全家的共同語彙——`aos::Error`、`aos::Json`、三扇門、旗標（`aos/cli.hpp`）、路徑、子程序、訊號。讀完它，別的專案裡沒解釋的名字都在這。
2. **inst**（C）：一個 `.h` 三個 `.c`，從 `src/inst_exec.c` 的 `aos_inst_start` 由上往下讀。
3. **aos-exec**：先看 `src/cli/cli.cpp` 的 `run_cli`（解旗標 → 一跳跳走 → 開跑），再看 `src/find/find.cpp` 的 `hop`（定工作區 → 走進去讀 `.env` → 挑入口 → 判種類），
   其餘照 README 的元素表進資料夾；inst 單子怎麼交給 libaos 在 `src/inst/`。
4. **aos-loop** → **aos-fsm** → **aos-daemon**：同樣先 `main.cpp`（各二三十行），再看 aos-loop 的 `src/run/`（跑一次：fork 子行程呼叫 aos-exec 的 `run_cli`）
   與 `src/engine/`（骨架 `Loop`：讀設定、每次讀 ctl、睡、跑一次、寫 state）；aos-daemon 是 `Loop` 的子類別，子 loop 在 `src/child/`。
5. aos-directive、aos-schema 各自獨立，用到再看。

每個專案的 README 章節順序都一樣：一句話＋比喻＋例子 → 用法 → 元素（資料夾地圖）→ 流程（從 main 往下）→ 為什麼這樣做 →
公開介面 → 跟 Python 版的差異 → 建置與測試 → 已知限制（沒有的章節就省）。每個原始檔開頭都有一段白話：它是哪個元素的哪一塊、對應 Python 版哪個函數。

## 慣例（全家一樣；新專案照這張做）

### 命名

| 東西 | 規則 | 例 |
|---|---|---|
| 專案＝資料夾＝CMake 函式庫 target＝vcpkg manifest 的 name | `aos-<短名>` | `aos-loop` |
| 函式庫產物 | `lib/lib<專案名>.a`（STATIC） | `lib/libaos-loop.a` |
| 執行檔 target／產物 | `<專案名>_main` → `bin/<專案名>` | `aos-loop_main` → `bin/aos-loop` |
| namespace | `aos::<短名>`，整個專案一層、不分子 namespace（看檔案在哪個資料夾就知道是哪個元素）；aos-util、aos-directive 直接 `aos` | `aos::loop::Engine` |
| 公開標頭 | 只有一個：`include/aos/<短名>.hpp`；好幾個：`include/aos/<短名>/*.hpp`；沒有要給別人用的就沒有 `include/` | `aos/inst.hpp`、`aos/loop/engine.hpp` |
| 元素 | `src/<元素>/`，元素的標頭跟資料夾同名 `src/<元素>/<元素>.hpp`，裡面列「幾塊 → 哪個檔」 | `src/table/table.hpp` |
| 跨元素共用 | `src/common/common.hpp`（型別別名、自己的錯誤代號） | |
| 入口 | `src/main.cpp`：只把元素串起來，不做事 | |
| 錯誤代號 | 常數 `code::Xxx`，字串＝跟 Python 版同名的 CamelCase（照 C-54：`…Missing`／`…Unknown`／`…Bad`／動作＋`Failed`） | `code::CfgBad` |
| 測試 | `tests/compare.py`（跟 Python 版逐案比）、`tests/test_cli.py`（命令列黑箱）、`tests/test_lib.*`（函式庫）、`tests/test_ffi.py`；ctest 名＝檔名去掉副檔名 | |

例外：`inst` 是純 C 專案，沿用 dcap 的 C 模板：資料夾 `inst`、target `inst`／`inst-static`、標頭 `aos.h`、函數 `aos_inst_*`。

### 寫法（不要太難）

- 好懂 > 巧妙 > 效能。普通函數、普通 struct、if／for；一個函數做一件事、短；名字直白。
- 不用：模板技巧、巨集魔法、多層繼承（daemon 繼承 loop 反覆跑的引擎這一層是設計，到此為止）、`std::function`／`std::variant` 包閉包、
  ranges 管線、縮寫函式模板（`const auto&` 參數）、`std::exception_ptr`。要「一定收尾再丟例外」就寫 `try { } catch (...) { 收尾; throw; } 收尾;`。
- 每個 `if` 都加 `{}`；少用三元運算子（寫成 if）；少用 `auto`（型別寫出來）。
- C++：4 格縮排、120 欄；C（inst）：`clang-format --style=LLVM`、一行一件事（不在 if 條件裡賦值、不串長的 `&&`）。
- `Json`（nlohmann `ordered_json`）常拿來當「可能是 null」的值用（Python 遺風）：`Json last_code_`＝null 或數字。

### 錯誤

每支工具出錯都丟 `aos::Error{code, msg}`（aos-util 的 `aos/error.hpp`）；`main` 接到就 `aos::emit_error`：stderr 一行
`{"error": {"code", "msg"}}`、退出 1。**例外：aos-exec** 印的是一行 **`aos-exec: 代號 原因`**（例 `aos-exec: EntryMissing 入口不存在：nope`）、退出 1——
照 proto8 N-60／P-21「程式名: 原因」，代號放原因開頭給測試認。**aos-loop、aos-fsm 同格式**（`aos-loop: 代號 原因`、`aos-fsm: 代號 原因`）。`code` 看是哪種錯（跟 Python 版同名），`msg` 給人看（字面不保證）。
**一個代號只定義一次**：兩支以上會吐的放 aos-util 的 `aos::code`；只有一支會吐的放那支自己的 `code`；每支在自己的 `code` 裡
`using namespace aos::code;`，程式裡一律寫 `code::Xxx`。全家的代號：

| 代號 | 誰吐 | 什麼時候 |
|---|---|---|
| `ArgumentsBad` | 每支命令列（含 aos-exec、aos-loop、aos-fsm、aos-daemon） | 參數用錯（位置參數、旗標少了值、aos-schema 參數不是剛好一個）；aos-exec、aos-loop、aos-fsm、aos-daemon：旗標缺值、沒給 XXX／設定檔、設定檔多給、不帶值的旗標寫成 `--x=V` |
| `FlagUnknown` | aos-exec、aos-loop、aos-fsm、aos-daemon（`aos/cli.hpp`）；`aos/flags.hpp` 也有（目前沒有程式叫它） | 不認得的旗標 |
| `InputBad` | aos-schema、aos-directive（aos-util 讀 stdin）；libaos（`aos_inst_strerror`） | stdin 一份 JSON 都解不出來；libaos 的輸入 `in`／`out` 是 NULL、`argv` 空 |
| `InputExtra` | aos-schema、aos-directive（aos-util 讀 stdin） | stdin 有好幾份 JSON |
| `CfgMissing` | aos-loop、aos-fsm、aos-daemon（`load_cfg`） | 設定檔（loop.json、fsm.json、daemon.json）不在；`#/` 指不到 |
| `CfgBad` | aos-loop、aos-fsm、aos-daemon | 設定檔讀不了、不是 JSON、`#` 後不是 `/`；不是物件、某個 key 型別不對、必填沒寫；aos-fsm 開跑時查整張表不合（`start`／`next` 不在表上、`next` 空字串或頭尾有空白、物件 `next` 的 key 不對或沒有 `"0"`／`"*"`、格的形狀不對）；aos-daemon：子項名字跟自己的 ctl／state／loops_ctl／loops_state 撞名、`loops_ctl`／`loops_state` 不是檔名或 null |
| `StateBad` | aos-fsm | `$AOS_STACK/state.txt` 在但讀不了（沒權限、是資料夾、不是 UTF-8） |
| `SchemaMissing` | aos-schema | SCHEMA檔 不在 |
| `WriteFailed` | aos-loop、aos-fsm、aos-daemon | state 窗寫不了；aos-fsm：`trace.jsonl`、`.state.txt` 寫不了；aos-daemon：loops_state 窗、子項的 loop.json 寫不了 |
| `MkdirFailed` | aos-daemon、aos-exec | 資料夾建不了（aos-exec：`AOS_STACK`；aos-daemon：子項的小格、信箱模式的信箱〔`$AOS_STACK` 不在也算，不替人建〕） |
| `LaunchFailed` | inst、aos-loop、aos-daemon、aos-exec | 子程序起不來（執行檔不在、fork 失敗；aos-exec 還有 exec 失敗、libaos 起不來；aos-daemon：小格的 stderr 開不了；aos-loop／aos-fsm／aos-daemon 的 `exec` 單子起不來也是） |
| `Internal` | 每支 | 照理不會發生的例外 |
| `DirectiveBad` | aos-directive（aos-exec 原樣透傳） | 指示詞解不開：`$env` 沒設、`$ref` 讀不到（含指到資料夾）／不是 JSON、指不到、繞圈（寫法不合不算錯，ideas 10-20 D13～D15） |
| `WsMissing`、`EntryMissing`、`EntryBad` | aos-exec | 見 [aos-exec](aos-exec/README.md)；aos-loop／aos-fsm／aos-daemon 的 `exec` 單子形狀不對也是 `EntryBad`（原因開頭「單子跑不起來：」） |
| `DotenvBad` | aos-exec | `.env` 在但讀不到（權限、是資料夾、壞掉的捷徑）；`.env` 壞（格式不合〔含引號沒收尾、引號裡有 `\`、單引號裡有 `${`、引號後有雜字、`=` 後空白再接 `#`〕、`${名字}` 沒設、不是 UTF-8）；JSON 的 `.env` key 指示詞解不開、名字不合。只印位置、不印值 |
| `CwdMissing`、`OpenFailed`、`CommandMissing`、`CommandBad`、`WaitFailed`、`KillFailed`、`PathConflict`、`PathNotAbsolute` | libaos（`aos_inst_strerror`；aos-exec 跑 inst 單子起不來時放在 `LaunchFailed` 的原因開頭） | 見 [inst](inst/README.md) |
| `StackMissing` | aos-loop（定義在 `aos/loop.hpp`）、aos-fsm、aos-daemon | 要 `AOS_STACK` 卻沒設（loop 開了窗、fsm、daemon） |
| `StateUnknown` | aos-fsm | state 檔裡的狀態不在表上。見 [aos-fsm](aos-fsm/README.md) |
| `MailboxMissing`、`PriorityBad`、`LetterMissing`、`ReplyBad` | aos-llm-send（定義在 `aos/llm_kernel.hpp`） | 沒設 `AOS_KERNEL` 或不是資料夾；priority 寫壞；信在信箱裡不見了；回信讀不懂 |
| `LockFailed`、`QueueBad`、`UsedBad` | aos-llm-kernel | 信箱被另一個 kernel 鎖著；`$AOS_STACK/queue.json` 讀不懂；`$AOS_STACK/used.json`（用量帳）讀不懂 |
| `LetterBad`、`DeadlineMissed`、`BudgetMissing`、`RunFailed` | aos-llm-kernel 寫進回信、aos-llm-send 印出來 | 信讀不懂或 priority 壞；輪到之前時限已過；這一窗額度用完；上一次 kernel 跑到一半死了沒回信 |
| `CommandUnknown`、`FileMissing`、`FileBad`、`SpecBad`、`PointerMissing`、`ValueMissing`、`ValueBad`、`TargetBad`、`FollowMissing`、`CheckFailed` | aos-json（`src/common/common.hpp`；印法同 aos-exec：`aos-json: 代號 原因`） | 見 [aos-json](aos-json/README.md)；它也吐全家共用的 `ArgumentsBad`、`FlagUnknown`、`WriteFailed`、`Internal` 與 `DirectiveBad` |
| `MailboxMissing`、`LetterMissing`、`LetterBad`、`WithdrawFailed`、`OrderBad`、`CommandUnknown` | aos-post（`aos/post.hpp`；前三個跟 aos-llm-send／aos-llm-kernel 同名同義、`CommandUnknown` 同 aos-json，各定一份；印法 `aos-post: 代號 原因`） | 信箱或四格不在；信不在 `cur/`；`check` 到壞信；撤不了（不在 `new/`）；`order.json` 讀不懂；不認得的子命令。見 [aos-post](aos-post/README.md) |
| `LockMissing`、`HolderBad`、`CommandUnknown` | aos-lock（`aos/lock.hpp`；印法 `aos-lock: 代號 原因`） | `release` 的鎖不在；`show` 的名牌不在或讀不懂；不認得的子命令。見 [aos-lock](aos-lock/README.md) |
| `DirectiveFormBad`、`ExecBad` | aos-json 的 `check` 印在 stdout（問題，不是 aos-json 自己的錯） | 帶 `$ref`／`$env` 但寫法不合（aos 會原封不動留著）；`exec` 形狀不對 |
| `SchemaBad` | aos-schema | schema 不合 draft-07、`$ref` 指不到 |

ctl 壞不是錯（不採用、記在 state 的 `ctl_warning`）。

### 命令列：設定、旗標、三扇門、指示詞

> **aos-exec、aos-loop、aos-fsm、aos-daemon 的命令列不照這一節**：不讀 stdin 設定，設定只認設定檔（loop.json、fsm.json、daemon.json 是唯一的位置參數，可寫 `檔#/指標`；ideas § 22「捨棄舊的」、ideas 10-21 § 9），
> 不寫結果 JSON（結果＝結束碼），錯誤一行「程式名: 代號 原因」。**旗標**（ideas 10-21 § 1～§ 3）：旗標寫在位置參數前面，`--x V` 或 `--x=V`、重複給最後一個算、`--` 結束旗標、
> 第一個不是旗標的參數起原樣；不認得＝`FlagUnknown`、缺值＝`ArgumentsBad`。規則在 aos-util 的 `aos/cli.hpp`（`parse_cli`、`load_cfg`；對應 bin 的 `aos_flags.py`）：
> aos-exec 有 `--ws` 與不帶值的 `--dotenv-override`；aos-loop、aos-daemon 有 `--max`、`--interval-ms`、`--ctl`、`--state`（旗標 ＞ 設定檔 ＞ 預設）；aos-fsm 目前沒有旗標。
> 下面是較早那代（aos-schema、aos-directive 的 bin）的規矩。

- **設定只從 stdin 讀一份 JSON**（`aos::read_stdin`）：空的＝`{}`、多份＝`InputExtra`、解不出來＝`InputBad`、壞掉的尾巴丟掉。
  沒有 TARGET、沒有 `-`：任何位置參數＝`ArgumentsBad`（跟 Python 版刻意不同）。
- **旗標＝純量 key 原名**（`aos::parse_flags`）：`--timeout_ms 100`、`--stop_on_end true`（底線；不收減號寫法）。每個旗標都要帶值；
  值先當 JSON 解、解不了當字串；蓋過 stdin 的同名欄位。清單由各專案的欄位表自動產生；陣列、物件（`argv`、`envs`、`inst`、舊 daemon 的子項表）不鏡射。
  `--` 後面整段：aos-inst 拿去蓋 `argv`；loop、daemon 不收（`ArgumentsBad`）。
- **指示詞**（aos-directive）：stdin 與每個旗標值裡的 `{"$ref": 檔}`、`{"$env": 變數}` 先解開再驗欄位。
- **結果 stdout 一行 JSON、退出 0**（`aos::emit`，排版同 Python `json.dumps`，key 照原順序）；**出錯 stderr 一行、退出 1**。
  子程式回非 0 不算錯（那是結果）。
- **找兄弟執行檔**（`aos::sibling_tool`）：自己是 `impls/X/bin/X`，要叫 Y 就叫 `impls/Y/bin/Y`，不看 PATH。

### 目錄（照 dcap，三處偏離）

```
<專案>/
  CMakeLists.txt    include(../cmake/settings.cmake) → project() → 兄弟專案 → 函式庫 → if(PROJECT_IS_TOP_LEVEL) 執行檔＋測試
  vcpkg.json        nlohmann-json（aos-schema 再加 json-schema-validator）
  include/aos/...   公開標頭（有要給別人用的才有）
  src/              除 main.cpp 全進函式庫；一個元素一個資料夾
  tests/            compare.py／test_cli.py／test_lib.*（＋資料）
  bin/ lib/ build/  產物與建置目錄（不進 git）
```

跟 dcap 不同的三點（使用者拍板）：函式庫 **STATIC**（不是 SHARED）、執行檔 **`-static-pie` 全靜態**（啟動不必動態載入 libstdc++；代價是執行檔較大、glibc 有安全更新要重建）、**兄弟專案用 `add_subdirectory` 一起編**
（它們的 `lib/*.a` 會輸出到各自的資料夾，所以建 aos-fsm 也會更新 `../aos-loop/lib/`、`../aos-exec/lib/`——可接受）。

### 建置

每個專案都一樣：

```sh
cmake -B build && cmake --build build && ctest --test-dir build
```

- 共通的 CMake 設定在 [`cmake/settings.cmake`](cmake/settings.cmake)（vcpkg toolchain 的找法、Release、`compile_commands.json`、PIC、
  `-static-pie` 與 sanitizer 例外），各專案 `project()` 之前 `include` 它。只有 `set()`，沒有函數、沒有巨集。
- nlohmann-json 走 vcpkg（toolchain 自動找 `~/dev/vcpkg`，或設 `VCPKG_ROOT`）；每個專案一份 `vcpkg.json`（可接受的重複）。
- 要用兄弟專案就 `add_subdirectory`，包在 `if(NOT TARGET ...)` 裡（同一個 build 裡好幾個專案都要它，只 add 一次）：
  ```cmake
  if(NOT TARGET aos-util)
    add_subdirectory(../aos-util aos-util-build)
  endif()
  target_link_libraries(你的target PRIVATE aos-util)
  ```
- 依賴順序：inst → aos-util → aos-directive → aos-exec → aos-loop → aos-fsm、aos-daemon、aos-llm-kernel → aos-llm-send；aos-schema 獨立（庫留著，沒人連）；aos-json 連 aos-util、aos-directive，它的 `test_tool` 要 aos-exec 的 `bin/`，所以排在 aos-exec 後面；aos-lock 只連 aos-util、aos-post 連 aos-lock（10-29）、aos-daemon 連 aos-post（10-29 信箱模式；它的 `test_demo` 跑 demo/daemon-2 要 aos-post 的 `bin/`），所以 aos-lock、aos-post 排在 aos-daemon 前面。
  一次全建（aos-fsm、aos-daemon 的 `test_demo` 要前面幾支的 `bin/` 先建好，所以照這個順序）：
  ```sh
  for p in inst aos-util aos-directive aos-schema aos-exec aos-json aos-loop aos-fsm aos-lock aos-post aos-daemon aos-llm-kernel aos-llm-send; do (cd $p && cmake -B build && cmake --build build && ctest --test-dir build) || break; done
  ```
- Sanitizer：`cmake -B build-asan -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined"`（`settings.cmake` 看到 `-fsanitize` 就不加 `-static-pie`）。
  帶 sanitizer 的 `.a` 會蓋掉共用的 `lib/`，建完記得重建正常版。
- clangd 看 `build/compile_commands.json`（會自己去 `build/` 找）。

### 測試

| 檔 | 做什麼 | ctest 名 | 誰有 |
|---|---|---|---|
| `tests/test_cli.py` | 命令列黑箱：餵 stdin 或設定檔、看退出碼與輸出 | `test_cli` | aos-util、aos-directive（57 組）、aos-schema（12 案）、aos-exec（56 組）、aos-loop（40 組）、aos-fsm（29 組）、aos-daemon（51 案，unittest）、aos-llm-kernel（42 案，unittest）、aos-llm-send（18 案，unittest；測試自己當 kernel）、aos-json（126 個）、aos-post（unittest，含 20 寄信人並發、有順序的投遞 50 寄信人與收屍）、aos-lock（unittest，含搶鎖、kill -9 後收屍、boot_id、lease） |
| `tests/test_demo.py` | 整合：proto8/demo 在 impls 線跑，看結束碼 0、stderr 空、答案寫出來 | `test_demo` | aos-fsm（agent-bob、agent-ann）、aos-daemon（demo/daemon、demo/daemon-2） |
| `tests/test_tool.py` | 給腦掛的工具經 aos-exec 跑（假 OpenAI 端點） | `test_tool` | aos-json（30 個；aos-exec 的 `bin/` 沒建＝跳過） |
| `tests/test_lib.*` | 函式庫 | `test_lib`、`test_lib_*` | inst（C；另一份 `test_lib_nopidfd` 走輪詢退路）、aos-schema、aos-util（7 條，含代號 `cli`） |
| `tests/test_ffi.py` | Python ctypes 載 `.so` | `test_ffi` | inst |

## 新專案照這張清單

1. 資料夾 `aos-<短名>`；`CMakeLists.txt` 照 [aos-directive 的](aos-directive/CMakeLists.txt)（最短的一份）改名字；`vcpkg.json` 抄一份改 name／description。
2. namespace `aos::<短名>`；`src/common/common.hpp` 放 `using aos::Error; using aos::Json;` 與自己的 `code`（`using namespace aos::code;` ＋獨有的）。
3. 先用一句話說清楚這支程式是什麼，從那句話裡的元素拆 `src/<元素>/`，每個元素一個同名 `.hpp` 列「幾塊 → 哪個檔」；跨元素共用的進 `common/`；
   全家都要的進 aos-util。`main.cpp` 只串。
4. 命令列：`aos::parse_flags` ＋ `aos::read_stdin` ＋ `aos::resolve` ＋ 欄位表；結果 `aos::emit`、錯誤 `aos::emit_error`。
5. README 照上面的章節順序；只講自己，共通的連回這一頁。
6. 測試：有 Python 版就 `tests/compare.py`；命令列黑箱 `tests/test_cli.py`；ctest 名＝檔名。
7. 每個檔開頭一段白話（哪個元素的哪一塊、對應 Python 哪個函數）；寫法照「寫法（不要太難）」。
