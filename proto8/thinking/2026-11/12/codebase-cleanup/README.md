# 程式碼庫整理（11-12 晚，fable 領隊）：方案、批次表、做到哪、待裁

← [11-12 日索引](../README.md) ・ 前情：今晚的兩次拆檔（`aos-eca-turn` → `cmd/aos-eca/aos_eca/`、`lib/agent/cli_session.py` → 同層 `cli_*.py`）

## 使用者原文

11-12 晚：

> 「重構拆檔和tidy結束後，派fable領隊，去做整個程式碼庫的整理，架構弄乾淨些。」

施工中（頂層轉來）：

> 「盡量做」

頂層向他說過的做法（他沒有反對）：行為不變、只整理結構（模組邊界、重複的程式、放錯位置的東西、命名不一致），不加功能、不改工具對外的樣子；先出方案再動手、每批跑測試各自 commit；要動概念／規範條文或刪整塊的列給他裁；範圍 `proto8/`，`impl_cpp/` 與 `archive/` 不碰；`impls/aos-llm-kernel` 與 kernel 框架不動（「開工等假日，我自己也要思考」）。

使用者已點頭的兩件：修 `/goal`、`/compact` 失敗卡信（會改行為）；NORMS 附錄 4 evidence 的失效行號。明講不管：`/exit` 先看畫面再拿鎖的時間差。

## 整理前哪裡不乾淨（盤點結論）

1. **同一段「叫下層指令、轉下層的錯」抄了十幾份**：`lib/agent` 的 `self_ctl`、`self_history`、`self_hook`、`self_llm`、`self_state`、`self_system`、`self_tools`、`do_task`、`goal` 九支 `_entry` 各一份（約 35 行），`mailbox_call.py`、`agents_cmd.py` 又各一份；`kill_group` 兩份逐字相同。
2. **`py/aos_ws.py` 抄了 `lib/tool_io.py` 的時鐘函式**（六支），`os_reason` 也兩份。
3. **今晚拆檔留下的殼**：`cli_session.py` 的 `_Facade` 與整包相容匯出；`claude`／`codex` 的 `ModuleMissing` 名單沒列新分檔；aos-eca 的「bin 旁邊放一份就用那份」退路實際上走不到。
4. **放錯位置**：`lib/base/file_walk.py`（共用模組混在工具夾中間）、`lib/agent/fork_copy.py`（只有 fork 用卻放共用層）。
5. **兩份規則不同的 `read_env_file`**：同一份 env 檔，`aos-tools` 與 MCP server 檔讀出來不一樣（待裁，見下）。
6. **死碼**：`cli_screen.attach_main`（沒人叫，檔頭還在講 attach）、`aos_ws.stack_of`。
7. **命名不一**：`py/` 有的帶 `aos_` 前綴有的不帶；`agents_cmd.py` 沿用已拆掉的工具名；`aos_eca/common.py` 的 `warn` 其實是寫 `mailbox_warning.txt`；`templates/`、`kernel/`、`extras/` 夾名用連字號。
8. **範本內重複**：`templates/agent-fsm` 的 `idle.py`、`wait.py` 各一份 `write_atomic`。
9. **NORMS 附錄 4 evidence 寫死行號**（50 列），一改碼就失效。
10. **C++ 小重複**：`aos-exec` 自己的 `is_dir`（aos-util 已有）、`aos-json` 自己寫暫存檔改名。

刻意如此、不收的：每支 `_entry` 開頭「找 lib」的樣板（還沒找到 lib 就沒東西可共用）；各指令自己的一行 `die`／`warn` 包裝（綁程式名）；`write_atomic` 其餘幾份（失敗通道與暫存檔規則不同，硬合＝改行為）；測試檔不為長度拆。

## 批次表

| 批 | 領地 | 做了什麼 | 行為 | commit |
|---|---|---|---|---|
| A1 | `cmd/aos-eca/aos_eca/` | 修 bug：沒畫面交給 claude 的 `/goal`、`/compact` 失敗照一般一輪（收信、`brain_failed`、冷卻；成功冷卻歸零）；抽出 `handoff.py` 的 `Handoff`，一般一輪與 slash 共用 | **改**（使用者點頭） | `db2018b72` |
| B | `docs/NORMS/附錄4-持久檔.json`、`.md` | evidence 50 列改成「檔路徑（函式名）」、不寫行號 | 不變 | `4e07e6cd8` |
| A2 | `lib/agent/cli_*.py`、`agent_tool.py`、`claude`、`codex`、`cmd/aos-eca`、`cmd/aos-agent` | 清 `_Facade` 與整包相容匯出：`die`／`warn`／`PROG`／`ECHO` 只留在 `cli_base`，各處直接 import 分檔；`ModuleMissing` 名單換成分檔名；aos-eca 走不到的退路拿掉；`common.warn` 改名 `mailbox_warning`；`cli_session.py` 只剩說明與 hook／guard 入口 | 不變 | `d9c6ef32b`、`1e2202802` |
| C1 | `lib/agent` 九支 `_entry`、`mailbox_call.py`、`agents_cmd.py`、`fork/` | 新 `lib/agent/cmd_call.py`（`call`、`catch_signals`、`kill_group`、`ERR_RE`），九支工具＋mailbox 三支＋`clock_register` 共用；`fork_copy.py` 搬進 `fork/` | 不變（訊號行為手跑對照） | `e9e273c61`、`41a576f03`、`a4e9d51d7` |
| C2 | `py/aos_ws.py`、`py/aos_flags.py`、`lib/tool_io.py` | 時鐘函式只留 `tool_io` 一份、`os_reason` 一份；刪 `stack_of` | 不變 | `aa7d51295` |
| C3 | `lib/file_walk.py`、`glob`、`grep`；`templates/agent-fsm` | `file_walk.py` 搬到 `lib/` 頂層；`write_atomic` 收進夾內 `atomic_file.py` | 不變（`ModuleMissing` 句子裡 `lib/base/` → `lib/`） | `1e96c0b9c`、`6f944274a` |
| D1 | `impls/aos-exec`、`impls/aos-lock` | `is_dir`、`now_ms` 改用 aos-util 的 | 不變 | `42ed7b3eb` |
| E | `lib/directive_value.py` 與知道「那份檔」的呼叫處 | `$ref` 的 `#/`：Python 這邊補 `--file`（[ref-hash](../ref-hash.md) 未定項；頂層轉來） | 補齊已裁的 | `efde695fa` |
| F | `lib/base`、`lib/aos`、`lib/` 頂層 | 新 `lib/process_group.py`（`run_python`、`cmd_call.kill_group` 用）、`lib/file_summary.py`（ls、stat、view 用）；judge 兩份原子寫合一；沒用到的 import | 不變（訊號／逾時手跑對照） | `e7e15a61a`～`fcd4d2cfe` 七個 |
| G | `cmd/`（aos-eca 除外）、`py/` | 手寫的「交 aos-directive 解」五處改用 `directive_value.resolve`；刪死碼（`aos_ws` 三個沒人叫的包裝、沒作用的 `quiet` 參數、沒人讀的常數與 import）；aos-agent 只有 ctl 用的十個函式搬到 `ctl/shared.py` | 不變 | `30bad5fe5`、`bad20950e`、`8a36847a7`、`f39b702d9` |
| H | `templates/`、`kernel/`、`extras/`、knowledge | knowledge 補 `atomic_file.py`；範本過時註解、extras README 補列（盤點下來這三夾本身乾淨） | 不變 | `c20a898b9`、`3808f5b29` |
| 收尾 | 12 支 `_entry`、附錄 4、`daemon_ctl/entry.py`、生成冊 | `ModuleMissing` 名單補 `process_group`；evidence 一格跟上 `file_summary.py`；`resolve_here` 指向已不存在佈局的退路拿掉；code map 重生 | 不變 | 本檔同一個 commit |
| — | `impls/aos-llm-kernel`、kernel 框架 | 不動，等使用者假日開工 | — | — |

## 決定（fable 定，細節範圍）

- **附錄 4 evidence 的寫法**：只寫「檔路徑（函式名）」；沒函式可指的只寫路徑。行號註定會壞。
- **`cli_session` 的覆寫機制怎麼擺**：lib 這邊照 lib/docs/01 的通則（工具夾先找自己資料夾）不改，說明改成「要帶就帶 `cli_session.py` 與全部 `cli_*.py`」；不搬成套件資料夾——hook 指令路徑寫在開著的畫面裡，搬了會斷。aos-eca 那邊的退路（看 `cmd/aos-eca/bin` 有沒有同名 .py）實際走不到、沒人用，拿掉、直接 import `agent.X`。
- **`_metainfo` 六處讀法不收成一份**：[metainfo 04](../metainfo/04-題與代定.md) M23「不新增共用模組」，依據是使用者「我們目前是不做單一程式去處理的」「要不要支援，就看他們自己」——直接推得出答案，所以不排施工。剩一小題見待裁 1。
- **`cooldown.py`、`goal_state.py`、`aos_index.py` 不搬**：前兩支雖然沒有 lib 工具在用（cmd 與範本用），但跟 `hooks.py` 同屬 agent 的狀態檔，放一起；搬了要改一串找路徑的開場，收益小。

## 做到哪（11-12 晚收線）

上表各批都做完、各自 commit 進 main（沒 push）。本機另清掉只剩 `__pycache__`、沒進 git 的殘留夾：`lib/aos/knowledge_check`、`lib/agent/knowledge_export`／`read`／`sync`／`write`、`agents_children`、`thought`、`proto8/bin`、`cmd/aos-daemon-ctl/bin/__pycache__`。

看過、判斷不收的（差異保不住，硬合＝改行為）：`agents_cmd.run` 與 fork 的 `agent()`（位元組解碼、分段等、TERM 後 KILL、回錯不退出）；`mcp_client` 的收行程群（等整群）；各處原子寫檔（暫存檔名、fsync、權限、錯誤句子各不同）；讀 `/proc/<pid>/stat` 兩份；`aos-json` 的 `save_file`；「取下層最後一行錯誤」三份；觀察帳本兩份讀法；沙箱版 shell 自帶的 `stop`（沙箱只掛三個模組）。

下次可接的（行為不變、今晚沒排）：

- `templates/agent-fsm` 的 brain／act 兩段逐字相同（讀 history 約 16 行、決定用哪份登記檔約 7 行）與四格各一份的 `clock_tick`：收成夾內一支，連 `templates/docs/02` 的檔案清單與 knowledge 一起改。
- `lib/aos` 幾支審查工具「找 lib」的寫法有五種：對齊會改 lib 找不到時的錯誤輸出，見待裁 9。
- 文件裡還指著舊出處的兩處（當時 tidy 線有未提交改動、沒碰）：`cmd/aos-mcp/README.md` 的 `mcp_argv`（現在在 `lib/agent/cli_mcp.py`）、`cmd/docs/01` 講 `aos-eca-turn` 本體的段落。

要重建什麼：impls 只有 `aos-exec`、`aos-lock` 兩支執行檔變了（行為相同）；持久檔格式沒動；`install.sh` 不用重跑。抄出去的複本（試驗場）要整份重抄 `lib/`、`py/`、`cmd/`、`templates/agent-fsm`——新檔 `lib/process_group.py`、`lib/file_summary.py`、`lib/file_walk.py`（搬家）、`lib/agent/cmd_call.py`、`lib/agent/fork/fork_copy.py`（搬家）、`templates/agent-fsm/atomic_file.py`、`cmd/aos-eca/aos_eca/handoff.py`、`cmd/aos-agent/aos_agent/ctl/shared.py`，只抄部分會缺模組。

**收工全套一紅（11-12 晚追查）**：全套（在 `415cf6a2c`）只紅 `lib/agent/fork/tests` 的 `test_kernel_alone_is_not_a_daemon`（預期 `DaemonMissing`，實得 `StateMissing …/proto8/.stack/procs_state.json`）。**不是本輪整理的回歸，是測試沒隔離 cwd**：`fork` 叫 `aos-agent ctl who`，它找 daemon 照設計「`--daemon`＞`$AOS_DAEMON`＞猜 `./.stack`」（`py/daemon_ctl/table.py` 的 `find_daemon`，今晚沒動）；全套腳本在 `proto8/` 下跑，而 `proto8/.stack` 剛好有個空夾（11-02 21:18 建，裡面什麼都沒有、git 不追蹤，不是今晚留的），於是猜到它、往下讀表才報 `StateMissing`。在測試夾內或空的 cwd 跑就過（整理線報全過大概是這樣跑的）。修法：`test_fork.py` 的 `run()` 每次給子程序一個空的臨時 cwd（同 `subagent/tests/test_wait.py` 那支同類測試本來就給 `cwd=tmp`）。驗證：在 `proto8/` 下 `lib/agent` 全部子夾、`lib/agent/tests`、`cmd/aos-agent`、`cmd/aos-eca`、`cmd/aos-daemon-ctl`、`lib/tests` 全過；另把全套從空 cwd 再跑一遍（65 夾 1325 例），各夾例數與原來相同、全過——沒有「靠 `./.stack` 才綠」的假綠。`proto8/.stack` 空夾沒刪（不是今晚的東西），等使用者決定。

## 待使用者裁

1. **`lib/metainfo.read`（管 timeout、cost）遇到壞掉的 `_metainfo`**：現在報 `FileBad` 擋下；其他五處讀法都是略過。(a) 維持——壞檔擋下來，不會悄悄用預設 timeout 跑；(b) 改成略過——跟「`_metainfo` 壞掉不報錯」一致，但壞掉的 timeout／cost 會被安靜忽略。建議 (a)：使用者那句原話講的是 index_view，這支管的是上限。
   - **已裁（11-12 晚）＝(b) 略過**：使用者「當然，全都是觀點，全都是參考用，出事了自行負責。」、確認時「對，略過，出事自己負責」；已施工，各執行點略過後用什麼見 [metainfo-views § 使用者裁定](../metainfo-views.md#使用者裁定11-12-晚)。
2. **兩份 `read_env_file` 統一成哪種**：(a) 用 aos-tools 的完整 dotenv（`${X}` 展開、行內註解、嚴格引號）——MCP server 檔的 `env_file` 裡值含 `#`、`$`、`\` 的讀法會變；(b) 用 MCP 那份簡單規則——aos-tools 失去插值與嚴格檢查；(c) 維持兩份、文件寫明差異。例：`A=x # note` 現在 aos-tools 讀成 `x`、MCP 讀成 `x # note`。建議 (a)（跟 C++ 的 dotenv 同一套想法），外部 MCP 那條線穩了再做。
3. **`cli_screen.attach_main`（死碼）**：(a) 刪掉，`cli_session.py` 檔頭講 attach 的幾段一起改（aos-agent 自己有 attach）；(b) 接回 `cli_session.py attach`。建議 (a)。
4. **範本要不要「抄出去一行都不依賴」**：現在 `templates/agent-fsm` 本來就 import `py` 與 `lib`。若照舊，範本裡的小函式之後可以再往 lib 收；若要完全自帶，就維持各帶一份。這次只在夾內收，不受這題影響。
5. **改名**：(a) `py/` 前綴統一（`daemon_ctl` → `aos_daemon_ctl`，或全部去掉 `aos_`）；(b) `lib/agent/agents_cmd.py` 改掉舊工具名；(c) `templates/`、`kernel/`、`extras/` 的夾名照 C-54 改底線——牽動 `aos-agent ctl add` 的路徑、文件、已經抄出去的實例。建議做 (b)，(a) 聽他的，(c) 不做（在 C-54 補一句「範本／kernel 夾名照指令名用連字號」比較省，但那是動條文）。
6. ~~本機沒進 git 的殘留夾要不要清~~：已清（頂層轉來使用者「不存在的東西就刪掉」；確認只剩 `__pycache__`、沒有原始碼、沒有地方引用，清單在「做到哪」）。
7. **`extras/langs`（janet、lua，10-24 的嘗試）**：沒人引用、還跑得起來。(a) 留著；(b) 封存進 `archive/`。建議 (a)。`image-move-check` 同樣沒人引用、留著。
8. **`lib/aos/shell_report/report.py` import 了上層的 `agent.agent_files.declared_files`**（aos 層依賴 agent 層）：(a) 把 `declared_files` 往下搬到 `lib/` 頂層；(b) 留著、當明文例外。建議 (a)，但牽動 cmd、範本、`cli_cfg` 的 import，另排一批。同類：`promote/swap.py` 被隔壁的 `rollback` 伸手進來用——搬到 `lib/aos/` 或留著。
9. **`lib/aos` 審查工具「找 lib」寫法五種**（固定 `parents[2]`、`parents[1]`、`next(...)` 不帶 `ModuleMissing`、標準樣板）：對齊成標準樣板＝lib 找不到時從 traceback 變成一行 `ModuleMissing`。建議對齊。
   - **已裁（11-13）＝選 A：對齊成標準樣板**（照建議）。使用者回覆原文：「cl-9:A」（11-13 待裁頁 `wu-1113-top`；回覆整行見[回覆檔](../../13/decide_20261113_wu-top.reply.txt)，裁定後待施工見[裁定落地-1113](../../13/裁定落地-1113.md)）。還沒施工。
10. **兩種「收掉下層」的做法並存**：`self_*`／mailbox 工具送一次 TERM 就退（下層不理 TERM 會留著）；subagent／fork 會升到 KILL。要不要統一成後者。建議統一，但那是改行為。
11. **`py/daemon_ctl/__init__` 對外清單裡約 25 個外面沒人讀的名字**：要不要拿掉（算改模組對外的樣子）。建議拿掉。
12. **`lib/agent/hooks.py` 的 `_target` 還自己叫 `aos-directive`**（其他五處已改用 `directive_value`）：`hooks.py` 是範本可以單獨帶走的純標準庫模組，換了就多一個依賴——跟第 4 題同一題。
