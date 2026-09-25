# proto5/lib — agent（44 支）

← [proto5/lib README](../README.md)｜上一份：[kernel](kernel.md)｜下一份：[team](team.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_agent.py`](../aos_agent.py) | agent 的 tick 三格流程、批次派工與 kernel 排程登記；`main` 轉給 aos_agent_cli |
| [`aos_agent_cli.py`](../aos_agent_cli.py) | `aos-agent` 各子命令的 argparse 與分派。這支留 `main`（先驗用法、再照子命令分派） |
| [`aos_agent_cli_parser.py`](../aos_agent_cli_parser.py) | `aos-agent` 的 argparse：子命令一句話、秒數上限、tools／access／listen 的用法說明與選項表、建 parser |
| [`aos_agent_cli_args.py`](../aos_agent_cli_args.py) | `aos-agent` 解析後的參數再驗（用法錯退 2）：`--wait` 秒數、listen 看法、tools 各動作參數與分派、memory 類參數 |
| [`aos_agent_home.py`](../aos_agent_home.py) | agent 家的內容讀驗（人格／記憶／工具、message）與 `aos-llm call` 的六格 loader |
| [`aos_agent_info.py`](../aos_agent_info.py) | agent 的 info 設定、state 進度與恢復紀錄讀驗，原子寫回 state |
| [`aos_agent_batch.py`](../aos_agent_batch.py) | 批次建立、inst 產生（含 aos-jail 包裝）、kernel 交件、收回音、結清 |
| [`aos_agent_inputs.py`](../aos_agent_inputs.py) | waits 門、輸入讀驗與 intake／consuming 的恢復流程 |
| [`aos_agent_results.py`](../aos_agent_results.py) | 模型與工具結果判定、失敗分類與輸出轉換 |
| [`aos_agent_runtime.py`](../aos_agent_runtime.py) | 持久化操作、恢復清理、tick 鎖、交件與測試掛鉤 |
| [`aos_agent_init.py`](../aos_agent_init.py) | `aos-agent init`：寫死的單一預設家 |
| [`aos_agent_say.py`](../aos_agent_say.py) | `aos-agent say`：原子投一則訊息，可等回話 |
| [`aos_agent_wake.py`](../aos_agent_wake.py) | （09-24 停車）投完輸入後往 K 放 `wake` 單，叫醒停車（退 102）的 agent；say／talk／drop_new 共用 |
| [`aos_agent_listen.py`](../aos_agent_listen.py) | `aos-agent listen --last／--wait／--follow` |
| [`aos_agent_listen_render.py`](../aos_agent_listen_render.py) | listen 的印法：挑最後 N 則、輪次標頭、工具呼叫行 |
| [`aos_agent_talk.py`](../aos_agent_talk.py) | `aos-agent talk`：讀一行、投遞、等這一輪回話、印，slash 指令 |
| [`aos_agent_status.py`](../aos_agent_status.py) | `aos-agent status`：收集診斷並印文字／`-v`／`--json` |
| [`aos_agent_pause.py`](../aos_agent_pause.py) | `aos-agent pause`／`continue` |
| [`aos_agent_check.py`](../aos_agent_check.py) | `aos-agent check`：找 K、跑 kernel 檢查、再查 agent 家、工具與權限牆 |
| [`aos_agent_tools.py`](../aos_agent_tools.py) | `aos-agent tools add`：裝工具包或原地引用工具檔／資料夾 |
| [`aos_agent_tools_edit.py`](../aos_agent_tools_edit.py) | `aos-agent tools ls／rm／alias／unalias` 與共用的 info 編輯（管理鎖、試算後整份重寫） |
| [`aos_agent_tools_dev.py`](../aos_agent_tools_dev.py) | （第二波 A 隊，spec/aos-agent/tools-dev.md）造工具：`tools new`（骨架）、`tools test`（照工具檔描述自動跑正例／型別錯／缺參數＋`cases.json`，預設用 aos-jail 關牢）、`tools wrap-py`（`ast` 靜態讀 Python 檔、有註解的函式包成工具包、拒收表）；不需要 agent 家、不叫模型（wrap-py 的 `--describe-with-llm` 例外：第三波 W3-2，只寫提案檔、人看過用 `--describe` 才產包）。入口＋匯出層：只留 `wrap_py`、`test` 兩個主流程 |
| [`aos_agent_tools_dev_pack.py`](../aos_agent_tools_dev_pack.py) | 造工具共用：整包寫暫存資料夾再 rename 就位（`--force` 備份、殘渣回收）與 `tools new` 骨架 |
| [`aos_agent_tools_dev_pyread.py`](../aos_agent_tools_dev_pyread.py) | `wrap-py` 的讀：ast 靜態讀 Python 檔，型別註解→型別記號／JSON Schema、docstring 參數說明、拒收表 |
| [`aos_agent_tools_dev_wrappy.py`](../aos_agent_tools_dev_wrappy.py) | `wrap-py` 的產包零件：run 樣板、README、印表、讀原檔與包名檢查 |
| [`aos_agent_tools_dev_describe.py`](../aos_agent_tools_dev_describe.py) | `wrap-py --describe-with-llm／--describe`：模型補描述只寫提案、提案的機械檢查、照提案補描述 |
| [`aos_agent_tools_dev_run.py`](../aos_agent_tools_dev_run.py) | `tools test` 跑一次：關牢探測、起工具行程、收輸出（封頂、逾時、殺整組） |
| [`aos_agent_tools_dev_test.py`](../aos_agent_tools_dev_test.py) | `tools test` 的案例與判定：自動案例、`cases.json`、判過不過、整套跑與印表 |
| [`aos_agent_tools_wrapcli.py`](../aos_agent_tools_wrapcli.py) | （第三波 W3-2，spec/aos-agent/tools-wrapcli.md）`tools wrap-cli CMD`：argparse 靜態讀／`--help` 文字規則解 → 工具包；`--describe-with-llm` 只寫提案、`--spec` 照人看過的表產包。入口：拿 help 文字、主流程 `wrap_cli`、對照用 `score` |
| [`aos_agent_tools_wrapcli_const.py`](../aos_agent_tools_wrapcli_const.py) | `wrap-cli` 共用常數：參數表的種類、型別、名字與旗標規則、各種上限 |
| [`aos_agent_tools_wrapcli_argparse.py`](../aos_agent_tools_wrapcli_argparse.py) | `wrap-cli` 機械版之一：ast 靜態讀 argparse 的 `add_argument` → 參數表 |
| [`aos_agent_tools_wrapcli_helptext.py`](../aos_agent_tools_wrapcli_helptext.py) | `wrap-cli` 機械版之二：規則解 help 文字的 usage 行與選項行 → 參數表 |
| [`aos_agent_tools_wrapcli_check.py`](../aos_agent_tools_wrapcli_check.py) | `wrap-cli` 參數表的機械檢查（模型回的、人改過的都走這條）與 `--describe-with-llm` 叫模型 |
| [`aos_agent_tools_wrapcli_pack.py`](../aos_agent_tools_wrapcli_pack.py) | `wrap-cli` 產包：run 樣板、工具描述、README、包內檔案與參數表印表 |
| [`aos_agent_access.py`](../aos_agent_access.py) | 權限牆（access.json）讀驗、信任資料、重疊檢查、快照 |
| [`aos_agent_access_cli.py`](../aos_agent_access_cli.py) | `aos-agent access ls／set／rm／cwd／net` |
| [`aos_agent_events.py`](../aos_agent_events.py) | 事件紀錄（tool-era T4，spec/agent/events.md）：agent 家 `log/events.jsonl` 一行一事件（收件、每批起訖、壓縮），`aos-llm call` 的 `log/usage.jsonl` token 用量；只有持 `.tick.lock` 的一方寫，至少一次＋去重，滿了自動輪換 |
| [`aos_agent_context.py`](../aos_agent_context.py) | `aos-agent context`（tool-era T4，cli-memory.md）：送給模型的東西多大，人格＋記憶＋工具的字數／token 粗估；跟 `talk` 的 `/context` 共用同一份算法 |
| [`aos_agent_compact.py`](../aos_agent_compact.py) | `aos-agent compact`（tool-era T4，spec/agent/compact.md）：機械壓縮記憶（封存＝8 KB 機械摘要），tick idle 時的自動壓縮、`compact` 申請、`history --archive`；不叫模型，每步可重跑。`--summarize`（第三波 W3-2，spec/agent/compact-summarize.md）：人用的旗標，模型濃縮封存摘要、機械檢查不過退回。這支留 `apply` 與三個入口（`compact`、`auto`、`on_request`）和測試掛鉤 `_hook` |
| [`aos_agent_compact_plan.py`](../aos_agent_compact_plan.py) | 壓縮記憶的算法：常數與設定、沒做完的任務、成對檢查、每級每輪留多少、機械摘要、算新記憶 `plan` |
| [`aos_agent_compact_archive.py`](../aos_agent_compact_archive.py) | 壓縮記憶的封存檔：sha、原子寫檔、封存資料夾、`history --archive` |
| [`aos_agent_compact_summarize.py`](../aos_agent_compact_summarize.py) | `compact --summarize`：封存摘要叫模型濃縮，機械檢查不過退回機械摘要 |
| [`aos_agent_notes.py`](../aos_agent_notes.py) | `aos-agent notes ls／show`（tool-era T4）：讀 `tools/notes/` 那支 `note` 工具寫的 `wf-table/1` 長期筆記檔，不叫模型 |
| [`aos_agent_persona.py`](../aos_agent_persona.py) | `aos-agent persona show／set／append`（第二波 C 隊，spec/agent/persona.md）：人格是信任資料，模型只能用 `persona_propose` 提案，人批了才用這支寫進 `prompts/system.json`；不叫模型、不進牢 |

## aos_agent_home — agent 家共用內容讀驗

`load_llm_view(agent_dir, env=None)` 回人格、記憶、原始／送模型的工具表、model／params 與絕對路徑；只解模型輸入六格，不讀 state、不寫檔。
`resolve_field(doc, ctx, position)` 帶原文件位置解欄位；`check_message(m, *, from_model=False)` 驗訊息，錯誤為 `AgentError(code, msg)`。

## aos_agent_info — 設定與進度讀驗

`load(agent_dir, env=None)` 共用 aos_agent_home 的內容讀驗，再補 llm.pool／timeout_ms、tool_pool 與 tick 排程設定。
`load_state(agent_dir, env=None)` 讀驗三格狀態、waits／input、batch／intake／consuming／sweep，缺檔給初始狀態。
`write_state(agent_dir, st)` 原子寫回 state，保留原始 input、排除內部解析欄位。

## aos_agent — 走格與 kernel 排程

`tick(agent_dir, env=None)` 先拿 `.tick.lock`（被佔退 101、不動檔）、看手動暫停（有就退 0），再讀驗、恢復消費與清理，看門、收批次或走 idle／think／act；模型與工具都透過 kernel once 工作執行。
`start(agent_dir, env=None)` 建立／核對 tick.json，向 `AOS_KERNEL_HOME` 的 kernel 登記反覆工作；`stop(agent_dir, env=None)` 撤銷登記，兩者等回音並 ack。
`main(argv=None)`（在 aos_agent_cli）提供九個子命令、家一律 `--target`；回傳 0（完成）、101（tick 等待或鎖被佔、say／listen --wait 逾時、沒登記或暫停）、1（執行／讀驗錯）、2（用法錯）。tick／start 的 `AOS_KERNEL_HOME` 必須是 kernel 家的絕對路徑；stop 沒設就用 tick.json 記的。

日常 CLI（09-24 試玩 r2 補；fix-r4 改）：`aos_agent_init.init(dir)` 寫單一內建預設家；`aos_agent_say.say(dir, text, *, wait, timeout_ms)` 原子投遞並可等回話；`aos_agent_status.collect(dir, env)` 回診斷 dict、`status()` 印文字或 JSON；`aos_agent_pause.pause(dir)`／`resume(dir)` 是 `pause`／`continue`；`aos_agent_listen.listen(dir, mode, *, count, calls)` 是 listen（calls＝None／'short'／'full'，印法在 `aos_agent_listen_render`），`wait_reply()`／`print_message()` 給 listen 與 say 共用；（09-24 talk）`aos_agent_talk.talk(dir, *, timeout_ms, show_calls)` 是 talk（stdin 讀行，tty 才載 readline、印提示符）。

拆分模組：`aos_agent_batch` 建批、送件與收尾；`aos_agent_inputs` 處理門與輸入消費；
`aos_agent_results` 判定模型／工具結果；`aos_agent_runtime` 集中持久化、恢復清理與測試掛鉤。
