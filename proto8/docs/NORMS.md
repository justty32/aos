# proto8 規範

← [proto8](../README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜慣例：[CONVENTION.md](CONVENTION.md)｜程式：[impls/](../impls/README.md)（C++，唯一實作）、[bin/](../bin/README.md)（只剩 aos-tick）、[demo/](../demo/README.md)

**比起實作，更重要的是規範**（C-45）。四層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾；資料夾＝程式） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 慣例 | 我們自己人寫 aos agent 時照抄的標準形狀（P-05～P-42），**不要求別人守** | [CONVENTION.md](CONVENTION.md) |
| 程式 | 符合規範的實作與範例，**不要求一定用** | [proto8/impls](../impls/README.md)（C++，唯一實作：[aos-exec](../impls/aos-exec/README.md)、[aos-loop](../impls/aos-loop/README.md)、[aos-fsm](../impls/aos-fsm/README.md)、[aos-daemon](../impls/aos-daemon/README.md) 四支命令列，inst 是 C lib [inst](../impls/inst/README.md)、指示詞是 [aos-directive](../impls/aos-directive/README.md) 庫；刻意沒有 aos-inst 命令列）；例外 [proto8/bin](../bin/README.md) 只剩 `aos-tick`（Python）；[proto8/demo](../demo/README.md)（agent-bob、agent-ann、daemon、tick）。Python 版的其他幾支刪了（使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也改 C++、tick 先留 Python），舊的 lib 在 git 歷史 |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。作廢的條號只留在條號表；沒有實作的條文標「現無實作」。「+x 沒 `#!`」的檔三處（可執行檔入口、argv 陣列入口、單子 `argv[0]`）一律用 `/bin/sh` 跑（使用者「乙」，N-59 第 5 件、N-60）。各條怎麼定、改過什麼見[各批出處](NORMS/附錄2-各批出處.md)。

**命名**（規則在 [C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md)；只換名字、不改原意，不留舊名；舊名在歷史敘述裡照留）：

- **10-23 命名統合**（[thinking 2026-10-23-naming](../thinking/2026-10-23-naming.md)，使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」）：`children` → `loops`、state 窗的 `state` 欄 → `phase`、子項 `exited` → `done`／`stopped`、trace 的 `ms` → `elapsed_ms`、指示詞的位置只認 `#/`（沒有 `$at`）、錯誤代號照 C-54 三種寫法（`Usage` → `ArgumentsBad` 等）；N-17「兩套撞名不改名」與 C-54「代號照舊沿用」不再成立。使用者 10-23 逐條重看代定後再定三處：純文字檔帶 `.txt`（fsm 的 `state.txt`、daemon 小格的 `stderr.txt`、demo 的 `current.txt`／`plan.txt`）、`AOS_STACK` 預設 `$AOS_WS/.stack/`、題目資料夾 `new/`（認領搬 `cur/`、做完 `done/`，答案 `out/`）（N-57、N-13、N-39、N-28）。
- **要跑什麼＝`exec`**（10-23 晚使用者：「改，beats改runs，然後val寫要跑啥，通常不會用val，應該用run。」，衝突時選「只有 loop、daemon 用 run」；10-23 深夜：「fsm.json，現在是用val，幫我改成exec」，問到 loop／daemon 時：「exec，loop／daemon 的 run 也一起改 exec」）：「要跑什麼」那一格全體系一律叫 `exec`——fsm 格、loop／daemon（含子項、小格 loop.json）；`val` 只留給 C-55 的雙形；條文說「次」不說「拍」。
- **10-23 晚入口改名**（[thinking 2026-10-23-naming](../thinking/2026-10-23-naming.md)，使用者「改。然後_開頭=附註這個概念刪掉。」「不認得的key就是忽略」）：入口預設名是 `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key；使用者原話裡的 `_exec` 照留）；不認得的 key 一律忽略（C-48），`_` 開頭沒有特別意思。
- **10-23 晚命名方法**（[thinking 2026-10-23-naming-method](../thinking/2026-10-23-naming-method.md)，使用者「寫進去吧」）：ctl 的 `stopped`（N-06、N-07；跟 state 的 `phase: stopped` 同字）、state 窗的 `ctl_warning`（N-08、N-28）、`started_at_ticks`（N-32、N-17）。
- **10-25 state.json**（使用者 10-25「state.json中，runs改counter，at改成recorded_at」）：loop／daemon 的 state.json（N-17、N-32）這份 state 的時間叫 `recorded_at`；跑過幾次見下一條（`counter_runs`）。
- **10-25 計數改 `counter_*`**（使用者 10-25「計數這塊，幫我改成counter_*」）：計數一律 `counter_<被數的東西>`（[C-54 命名方法 R6](CONCEPTS/01-設計理念/C-54-命名方法.md)；規範層 N-17、N-32）。照改的欄位：loop／daemon state.json `counter_runs`；kernel-llm 的 queue.json `runs` → `counter_runs`、used.json `calls`／`tokens`／`all_calls`／`all_tokens` → `counter_calls`／`counter_tokens`／`counter_all_calls`／`counter_all_tokens`、served.jsonl `tokens`／`waited_runs` → `counter_tokens`／`counter_waited_runs`；信的 `hops` → `counter_hops`；lib 工具輸出的計數（ls、stat、view、json_read、json_edit、copy、memory 索引）與 demo 的紀錄（agent-kai、agent-gus、agent-hal compact、self-improve 的用量）同樣改 `counter_*`。
- **10-25 時間點一律 `<發生了什麼>_at`、上限一律 `max_*`**（使用者 10-25 已選 `recorded_at`，頂層問兩題（時間點規則要不要跟著改、上限要不要照 R6 改 `max_*`），使用者回「都好」；頂層代定（可翻案））：時間點＝`<發生了什麼>_at`，沒有單獨的 `at`（[C-54 命名方法 R3、R6](CONCEPTS/01-設計理念/C-54-命名方法.md)）。照改：fsm 的 trace.jsonl `at` → `started_at`（這格開始跑的時間）、信（send_message）`at` → `sent_at`、kernel-llm 的 served.jsonl `at` → `served_at`（kernel 處理這封信的時間）、claude／codex 互動畫面的 turns.jsonl `at` → `answered_at`、agent-kai 的 context.jsonl `at` → `sent_at`、self-improve 的 version.json／verdict.json／result.json `at` → `created_at`／`judged_at`／`finished_at`、aos-ai 的 runs.jsonl／up.json `at` → `finished_at`／`started_at`。沒用 `max_` 的上限照 R6 改：kernel-llm 的 kernel.json `budget.calls`／`budget.tokens` → `max_calls`／`max_tokens`（舊名＝`CfgBad`）、self-improve 的 budget.json `rounds`／`elapsed_ms`／`tokens` → `max_rounds`／`max_elapsed_ms`／`max_tokens`（舊名＝`BudgetBad`）、lib 工具參數 `limit` → `max_lines`（read）／`max_items`（ls）／`max_results`（memory）、agent-hal compact 給腦的 `keep_max` 與報告的 `keep_max`／`keep_final_max`／`keep_line_max` → `max_keep`／`max_keep_final`／`max_keep_line_chars`。

<!-- wf-nav -->
## 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）

每個主題都有自己的概念、規範、實作；各分檔第一行寫出三者在哪。**主題不是層**（10-22，[C-74](CONCEPTS/01-設計理念.md#分層10-22-使用者定)：層照誰依賴誰分）——基礎層＝資料夾程式與執行（核心 aos-exec）、inst、命令列與指示詞、loop、daemon、窗；標準庫＝組合子（fsm、tasks）；最上層＝agent、kernel；時空的時鐘 aos-tick 擱置、不歸層；設計理念、總則跨層。條號不重編，條文原樣搬過來（10-19 改寫的條在括號附「10-19 改」）。

| 主題 | 規範分檔 | 概念 | 實作 |
|---|---|---|---|
| 設計理念 | 沒有專屬的條（C-56 KISS 是最高原則，也是最後原則——先滿足需求與其他原則，最後回頭清掉多餘的，給的值照字面用、不藏暗規則；C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的，各條都照它；C-54 命名＋[縮寫表](CONCEPTS/abbr.json)） | [CONCEPTS 設計理念](CONCEPTS/01-設計理念.md) | — |
| 設計理念／時空 | [02-設計理念-時空.md](NORMS/02-設計理念-時空.md)：N-01～N-03 | [CONCEPTS 時空](CONCEPTS/02-設計理念-時空.md) | 時鐘＝[aos-tick](../bin/README.md)（Python；bin 只剩它）；打包（N-03）現無實作 |
| 總則（跨主題） | [01-總則.md](NORMS/01-總則.md)：N-05 先寫暫存再改名、N-18 實作分級、N-43 結束碼（0／10／其他非 0，10-19 改） | 出自 C-07、C-45、C-53 | [impls](../impls/README.md) |
| 基礎設施／inst | [03-基礎設施-inst.md](NORMS/03-基礎設施-inst.md)：N-04、N-25、N-27、N-30（10-19 改；沒有 aos-inst 命令列，inst 是 C lib，§ 20） | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md) | [inst](../impls/inst/README.md)（C lib；單子的 JSON 在 aos-exec 的 `src/inst/`，行程內跑單子是 [aos-exec](../impls/aos-exec/README.md) 的 `run_inst`） |
| 基礎設施／loop、daemon | [04-基礎設施-loop與daemon.md](NORMS/04-基礎設施-loop與daemon.md)：N-10（10-16 刪，條號留作錨點）、N-28、N-54（10-22 定稿；loop 不管、使用者自行承擔的四件寫在分檔開頭；10-29 daemon 拆兩個手把：名單搬到 `loops_ctl.json`／`loops_state.json`、選填信箱模式 `loops_mailbox`；10-30 補 exec 型子項 `execs`〔直接 aos-exec 一次、不包 aos-loop〕與手把的 `execs_added`／`execs_removed`，沒掛 daemon＝Linux 管） | 同上 | loop＝[aos-loop](../impls/aos-loop/README.md)；daemon＝[aos-daemon](../impls/aos-daemon/README.md)（C++） |
| 基礎設施／窗 | [05-基礎設施-窗.md](NORMS/05-基礎設施-窗.md)：N-06～N-09、N-11、N-13～N-17、N-32、N-33（ctl／state 已做；agent 這層只剩 N-13：內部狀態外顯成 `$AOS_STACK` 裡的檔；節奏 key 用 `max`、設定只認設定檔；N-13、N-17、N-32、N-33 定稿；10-29 N-14 改口（窗＝只看最新那份的固定檔，鎖、信箱不算窗）、N-15 鎖、N-16 投遞與有序投遞已定，N-07 補 daemon 的 `paused`；10-30 N-16 加註：agent 層的輸入叫 queue） | 同上 | ctl／state＝[aos-loop](../impls/aos-loop/README.md)（`src/engine/window.cpp`；aos-daemon 繼承它）；資料夾式信箱（N-16）是 LLM kernel 的信箱，[aos-kernel-llm](../impls/aos-kernel-llm/README.md)；鎖等其他窗現無實作 |
| 基礎設施／指示詞 | [06-基礎設施-命令列與指示詞.md](NORMS/06-基礎設施-命令列與指示詞.md)：N-45 指示詞 `$env` 與 `$ref`（10-19 晚改；`$ref` 位置只認 `#/`；`$path`、`$prefix`、寫法寬容） | 同上 | [aos-directive](../impls/aos-directive/README.md) 庫（`$env` 與 `$ref`；[aos-exec](../impls/aos-exec/README.md) 用） |
| 基礎設施／組合子（tasks、fsm；stdlib 地位） | [07-基礎設施-組合子.md](NORMS/07-基礎設施-組合子.md)：N-20、N-34（tasks，現無實作，仍草稿）、N-36、N-38、N-39、N-41（fsm，10-19 改；定稿；fsm 不管、使用者自行承擔的八件寫在分檔開頭） | 同上 | fsm＝[aos-fsm](../impls/aos-fsm/README.md)；tasks 現無實作 |
| kernel | [09-kernel.md](NORMS/09-kernel.md)：N-42 兩種兩支（10-16 使用者「不併」；打包 N-03 在時空） | [CONCEPTS kernel](CONCEPTS/04-kernel.md) | LLM kernel 第一版：[aos-kernel-llm](../impls/aos-kernel-llm/README.md)＋閘門 [aos-gate](../impls/aos-gate/README.md)；通用 kernel 現無實作 |
| 基礎設施／資料夾程式與執行 | [10-基礎設施-定義與工作區.md](NORMS/10-基礎設施-定義與工作區.md)：N-57 六個環境變數（含 `AOS_CF`、`AOS_CD`、`AOS_CO`）與入口四種、N-58 `aos-exec [旗標...] XXX [args...]`（旗標 `--ws`、`--dotenv-override`；使用者 10-26「N-58加上--dotenv-override。」）、N-59 aos-exec 只做這幾件事（找入口、export、cd、讀 `.env`（讀完才挑入口、一路往下每層讀）、exec 或行程內跑單子）、N-60 aos-exec 自己的錯退 1、N-61 找入口與種類判斷（補 `.json`、`js[$AOS_ENTRY]`、字串轉向、繞圈偵測）、N-62 `#/` 尋址；N-50 工具＝資料夾程式、不用 PATH；N-53 aos 的 agent 被外面的 loop 一次一次驅動；N-55 工作區位置＝`AOS_WS`；N-63 hub 型環境變數（`AOS_<名字>`＝資料夾、沒設＝`<名字>Missing`、預設繼承；10-30 補實例 `AOS_DAEMON`）；N-64 父子交代（選用，10-29） | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)（C-65～C-67）、[C-68～C-73](CONCEPTS/01-設計理念.md#資料夾程式與環境變數10-19-使用者定)、C-62（agent＝狀態機） | [aos-exec](../impls/aos-exec/README.md)（C++）、[demo](../demo/README.md) |
| agent | 沒有專屬的分檔；入口與工具、怎麼被驅動在資料夾程式與執行（N-50、N-53）；其餘用 fsm 組出來；整套慣例在 [CONVENTION](CONVENTION.md) | [CONCEPTS agent](CONCEPTS/05-agent.md) | [demo](../demo/README.md)（agent-bob、agent-ann） |
| 待定（不拆，每條標主題） | [08-待定.md](NORMS/08-待定.md) | | |

> **總則與設計理念**分兩份（設計理念只有概念、總則只有規範；總則＝跨主題的規範，設計理念＝概念）。10-15 使用者「隨你」：維持分開。時空放在設計理念下也定案（同日「隨你」）。

## 條號表與各批出處

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [附錄1-條號表.md](NORMS/附錄1-條號表.md) | 條號 → 檔（含作廢條號） |
| [附錄2-各批出處.md](NORMS/附錄2-各批出處.md) | 各批出處 |
