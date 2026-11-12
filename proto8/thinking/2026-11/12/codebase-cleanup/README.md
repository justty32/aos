# 程式碼庫整理（11-12 晚，fable 領隊）：方案、批次表、做到哪、待裁

← [11-12 日索引](../README.md) ・ 前情：今晚的兩次拆檔（`aos-eca-turn` → `cmd/aos-eca/aos_eca/`、`lib/agent/cli_session.py` → 同層 `cli_*.py`）

## 使用者原文

11-12 晚：

> 「重構拆檔和tidy結束後，派fable領隊，去做整個程式碼庫的整理，架構弄乾淨些。」

施工中（頂層轉來）：

> 「盡量做」

頂層向他說過的做法（他沒有反對）：行為不變、只整理結構（模組邊界、重複的程式、放錯位置的東西、命名不一致），不加功能、不改工具對外的樣子；先出方案再動手、每批跑測試各自 commit；要動概念／規範條文或刪整塊的列給他裁；範圍 `proto8/`，`impl_cpp/` 與 `archive/` 不碰；`impls/aos-llm-kernel` 與 kernel 框架不動（「開工等假日，我自己也要思考」）。

使用者已點頭的兩件：修 `/goal`、`/compact` 失敗卡信（會改行為）；NORMS 附錄 4 evidence 的失效行號。明講不管：`/exit` 先看畫面再拿鎖的時間差。

## 現在哪裡不乾淨（盤點結論）

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

| 批 | 領地 | 做什麼 | 行為 | 測試罩得住 | 狀態 |
|---|---|---|---|---|---|
| A1 | `cmd/aos-eca/aos_eca/` | 修 bug：沒畫面交給 claude 的 `/goal`、`/compact` 失敗照一般一輪（收信、`brain_failed`、冷卻）；抽出 `handoff.py` 的 `Handoff`，一般一輪與 slash 共用 | **改**（使用者點頭） | 是（補 3 支，修前紅） | 做完 |
| B | `docs/NORMS/附錄4-持久檔.json`、`.md` | evidence 改成「檔路徑（函式名）」、不寫行號 | 不變 | 檢查腳本：路徑在、名字 grep 得到 | 做完 |
| A2 | `lib/agent/cli_*.py`、`agent_tool.py`、`claude`、`codex`、之後 `cmd/aos-eca` | 清 `_Facade`：會被換掉的東西（`die`、`PROG`、`ECHO`）只留在 `cli_base`、各處直接用分檔；補 `ModuleMissing` 名單；aos-eca 的退路拿掉；`common.warn` 改名 | 不變 | 是（lib/agent、aos-eca、aos-agent） | 見「做到哪」 |
| C1 | `lib/agent` 九支 `_entry`、`mailbox_call.py`、`agents_cmd.py`、`fork/` | 收成一份共用呼叫器；`kill_group` 一份；`fork_copy.py` 搬進 `fork/` | 不變 | 是（各工具夾 tests）；訊號行為手跑對照 | 見「做到哪」 |
| C2 | `py/aos_ws.py`、`py/aos_flags.py`、`lib/tool_io.py` | 時鐘函式與 `os_reason` 收成一份；刪 `stack_of` | 不變 | 是；缺時鐘檔提醒手跑對照 | 見「做到哪」 |
| C3 | `lib/base/file_walk.py`、`glob`、`grep`；`templates/agent-fsm` | `file_walk.py` 搬到 `lib/` 頂層；`write_atomic` 夾內收成一份 | 不變 | 是 | 見「做到哪」 |
| D1 | `impls/aos-exec`、`impls/aos-json` | `is_dir` 改用 aos-util；看 aos-json 的寫檔能不能用 aos-util 那組 | 不變 | 要 build；aos-json 今晚是別條線的領地 | 沒做（之後） |
| D2 | `py/`、`lib/agent/agents_cmd.py` | 改名（見待裁 5） | 不變但牽動廣 | 是 | 等裁 |
| — | `impls/aos-llm-kernel`、kernel 框架 | 不動，等使用者假日開工 | — | — | 不做 |

優先序：使用者點頭的（A1、B）→ 拆檔留下的殼（A2）→ 最大的重複（C1、C2）→ 放錯位置（C3）→ C++（D1）→ 改名（D2）。A2、C1、C2、C3 領地互不重疊、同時開工。

## 決定（fable 定，細節範圍）

- **附錄 4 evidence 的寫法**：只寫「檔路徑（函式名）」；沒函式可指的只寫路徑。行號註定會壞。
- **`cli_session` 的覆寫機制怎麼擺**：lib 這邊照 lib/docs/01 的通則（工具夾先找自己資料夾）不改，說明改成「要帶就帶 `cli_session.py` 與全部 `cli_*.py`」；不搬成套件資料夾——hook 指令路徑寫在開著的畫面裡，搬了會斷。aos-eca 那邊的退路（看 `cmd/aos-eca/bin` 有沒有同名 .py）實際走不到、沒人用，拿掉、直接 import `agent.X`。
- **`_metainfo` 六處讀法不收成一份**：[metainfo 04](../metainfo/04-題與代定.md) M23「不新增共用模組」，依據是使用者「我們目前是不做單一程式去處理的」「要不要支援，就看他們自己」——直接推得出答案，所以不排施工。剩一小題見待裁 1。
- **`cooldown.py`、`goal_state.py`、`aos_index.py` 不搬**：前兩支雖然沒有 lib 工具在用（cmd 與範本用），但跟 `hooks.py` 同屬 agent 的狀態檔，放一起；搬了要改一串找路徑的開場，收益小。

## 做到哪

（收線時填：各批 commit、測試數字、剩下的續行點。）

## 待使用者裁

1. **`lib/metainfo.read`（管 timeout、cost）遇到壞掉的 `_metainfo`**：現在報 `FileBad` 擋下；其他五處讀法都是略過。(a) 維持——壞檔擋下來，不會悄悄用預設 timeout 跑；(b) 改成略過——跟「`_metainfo` 壞掉不報錯」一致，但壞掉的 timeout／cost 會被安靜忽略。建議 (a)：使用者那句原話講的是 index_view，這支管的是上限。
2. **兩份 `read_env_file` 統一成哪種**：(a) 用 aos-tools 的完整 dotenv（`${X}` 展開、行內註解、嚴格引號）——MCP server 檔的 `env_file` 裡值含 `#`、`$`、`\` 的讀法會變；(b) 用 MCP 那份簡單規則——aos-tools 失去插值與嚴格檢查；(c) 維持兩份、文件寫明差異。例：`A=x # note` 現在 aos-tools 讀成 `x`、MCP 讀成 `x # note`。建議 (a)（跟 C++ 的 dotenv 同一套想法），外部 MCP 那條線穩了再做。
3. **`cli_screen.attach_main`（死碼）**：(a) 刪掉，`cli_session.py` 檔頭講 attach 的幾段一起改（aos-agent 自己有 attach）；(b) 接回 `cli_session.py attach`。建議 (a)。
4. **範本要不要「抄出去一行都不依賴」**：現在 `templates/agent-fsm` 本來就 import `py` 與 `lib`。若照舊，範本裡的小函式之後可以再往 lib 收；若要完全自帶，就維持各帶一份。這次只在夾內收，不受這題影響。
5. **改名**：(a) `py/` 前綴統一（`daemon_ctl` → `aos_daemon_ctl`，或全部去掉 `aos_`）；(b) `lib/agent/agents_cmd.py` 改掉舊工具名；(c) `templates/`、`kernel/`、`extras/` 的夾名照 C-54 改底線——牽動 `aos-agent ctl add` 的路徑、文件、已經抄出去的實例。建議做 (b)，(a) 聽他的，(c) 不做（在 C-54 補一句「範本／kernel 夾名照指令名用連字號」比較省，但那是動條文）。
6. **本機沒進 git 的殘留夾**（`lib/agent/knowledge_*`、`agents_children`、`lib/aos/knowledge_check`、`proto8/bin`，裡面只剩 `__pycache__`）：要不要 `rm -r`。不影響 repo。
