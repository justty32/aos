← [入口](../proto8.md)｜涵蓋：`proto8/lib/`（base、aos、agent）、`proto8/knowledge/`（記憶工具讀的知識庫）

工具契約、分層與完整索引以 [lib/README](../../../../../proto8/lib/README.md) 為準。路徑相對於該段標題的資料夾。

**工具**＝一個資料夾三個檔：`_entry`（第二行是 NAME）、`_tooldef.json`（給模型看）、`_metainfo.json`（給 kernel 與人；11-04 前叫 `_metainfo`）；agent 的 `tools/<名>` 用捷徑掛進來。（11-03 round 那套「格」——一輪的表與五格、parts、queue、history、compact、act、`lib/endpoint/`——與 aos-ai 的六個工具、ask_round 連程式刪了，概念在 proto8/archive/agent-round-concepts/。）

## `lib/`（共用模組）

| 檔 | 負責什麼 |
|---|---|
| `tool_io.py` | 不是工具：每支 lib 工具共用的開頭（11-05 晚）——`start`（`--help`、Ctrl-C 130）、`die`（錯誤行 stderr＋stdout、退 1；`echo=False` 只 stderr）、`warn`、`arguments`、`workspace`；工具先找自己資料夾、再找 lib/（lib/docs/01 規則 9），沙箱要綁它 |

## `lib/base/`（不懂 aos 的通用工具）

| 檔 | 負責什麼 |
|---|---|
| `read/`、`write/`、`edit/` | 讀檔（截斷提示）、整份寫、照字面替換（全有或全無） |
| `bash/` | 在工作區跑一行 bash（`timeout_s`、逾時整群收） |
| `ls/`、`stat/`、`view/` | 列資料夾（分頁、JSON）、單一個的屬性、漸進看檔 |
| `mkdir/`、`move/`、`copy/`、`trash/` | 建資料夾、搬／改名、複製、丟進 `.trash/<時間>/`（可救回） |
| `json_read/`、`json_edit/` | 照指標看 JSON；照指標改 JSON（經 PATH 上的 `aos-json`） |
| `math/`、`clock/` | 四則運算、印 UTC 時間 |
| `run_python/` | 跑一段 Python，回輸出、最後一行 `[exit code N]`（同 bash） |
| `judge/` | 只有 `_entry`（不是腦的工具，11-05）：判官，一輪＝收 `$AOS_STACK/requests/` 的 `procs_*` 信，照 `judge.json`（`allowed`、`max_running`〔數 `$AOS_DAEMON/procs_state.json` 的 running 列，經 aos-directive 解〕）判 `procs_added`（`procs_started`／`procs_woken` 也算進 `max_running`，11-05 edge-agent）；掛＝body 原樣 `aos-post send --reply-to` 進 daemon 的 ctl 信箱（無序信同名）、不掛＝stderr 一行＋`done --reply` 回 `applied: false`（`msg` 英文；aos-daemon-ctl `--reply-to` 帶的信才回得到，11-05 edge-agent 題 2）；不自己跑東西。模式 1 的身體、模式 2 的 0 號共用（[demo/docs/04](../../../../../proto8/demo/docs/04-kernel-modes.md)） |
| `llm_http/`、`llm_fake/` | endpoint 函數（11-04 晚）：stdin `{endpoint, request}` → POST OpenAI 相容端點、印 `{message, usage, model}`；body 組法 request 先、endpoint.fixed 蓋上、model 用包的（11-05）；假腦同契約不碰網路，認 endpoint.script 劇本、endpoint.tool（先叫哪個工具，11-05 E 線）。aos-llm-kernel 的 `kernel.json` `exec`／`endpoints.*.exec` 指它們 |

## `lib/aos/`（懂 aos 的工具）

| 檔 | 負責什麼 |
|---|---|
| `aos_ws.py` | 不是工具：寄信、等答案、讀 stack 的共用模組（只碰 stack）；`letter_key`＝信件名稱的處理順序（有序先、無序後，同 aos-post），queue 的格 new／cur／archive |
| `check_inbox/` | 看自己信箱 |

## `lib/agent/`（agent 當工具）

| 檔 | 負責什麼 |
|---|---|
| `agent_tool.py` | 不是工具：把一隻 agent 包成工具的轉接（`fresh_cell`、`run_agent`） |
| `pyfix/_entry`、`pyfix/_tooldef.json`、`pyfix/_metainfo.json` | 把改 Python 的事交給子 agent pyfix-agent，印答案＋實際 diff |
| `pyfix/agent/*` | 子 agent pyfix-agent：`_entry`、`loop.json`、`fsm.json`、`idle/`、`brain.py`（`aos-llm ask` 問 kernel，11-04 晚）、`act.py`、`system.txt`、`tools.json`、`tools/`（捷徑到 `lib/base`） |
| `cli_session.py` | 不是工具：claude／codex CLI 接成工具（非互動續對話，或 tmux 貼字等 hook）；`call_main`、`attach_main`、`hook`；`stack_copies`＝`$AOS_STACK` 的 `tools.json` 是這隻的覆蓋層、給 aos-mcp `--overlay`（11-05）、`--model` 取 cli.json 同層 `llm.json` 疊 `$AOS_STACK/llm.json` 的 `model`（11-04 晚） |
| `self_tools/_entry`、`self_tools/_tooldef.json`、`self_tools/_metainfo.json` | 改叫我的 agent 自己的工具覆蓋層（11-05 feat-proto 件 1）：`aos-agent ctl who` 認出是哪隻 → `aos-agent tools --target 它 add／rm／ls --json`；`tool_path`（相對從 `$AOS_WS`、絕對限 `lib/`）、`agent`（轉 aos-agent，stderr 原樣透出；退非 0＝取它最後一行錯誤行的代號與原因當自己的錯，沒有才 CommandFailed，11-05 E 線） |
| `agents/_entry`、`agents/_tooldef.json`、`agents/_metainfo.json` | 生、叫、收另一隻 agent（11-05 feat-proto 件 4；E 線補兩種生法與配額）：op new（`build_def`：範本複製到暫存資料夾、`absolutize_tools`、寫 files、併 llm、改 tools 檔，改名後掛上，掛不上刪掉）／add（`mount`＝`ctl add`，`llm set`、`tools rm`、`tools add --override` 走子的覆蓋層，失敗 `ctl rm` 收回）／say／ask／rm／ls；`read_path`（相對從 `$AOS_WS`、絕對照用）、`write_path`（限工作區）；配額 `reconcile`（`children.json`〔`[{name, stack}]`〕對 `ctl ls --json`）、`max_children`（父定義的 `agents.json` 疊父 stack 的，預設 4）、`quota`（滿＝ChildSlotMissing、不寄信）；`agent`（叫 aos-agent、逾時與被 TERM 收整群、錯取最後一行 `aos-…: error: 代號`） |
| `memory/_entry`、`memory/_tooldef.json`、`memory/_metainfo.json` | 層級式記憶工具的查詢半邊（11-05 下午 agent-knowledge）：`AOS_MEMORY` 指知識庫根（`base`：相對從 `$AOS_DAEMON`）、`parse_path`（段名 `[a-z0-9_-]`、尾巴 `/` 可有）、`resolve`（資料夾 → `.md` → `.json`）、`read`／`ls`／`find`（`find` 真的叫 `grep -ril`，TERM 時先收掉它）、`title_summary`（md 第一行與其後第一個非空行／json 的 `title`／`summary`）、`NodeMissing` 附祖先的子節點名 |
| `memory_export/_entry`、`memory_export/_tooldef.json`、`memory_export/_metainfo.json` | 把知識庫（或子樹）整棵印成一份 Markdown 給人看（11-05 晚 agent-knowledge K6）：`memory_root`（同 memory 的找法，規則 9 抄一份）、`children`、`export`（深度優先、`<!-- node: 路徑 -->`、json 包 code block）、`max_bytes` 截斷 |
| `thought/_entry`、`thought/_tooldef.json`、`thought/_metainfo.json` | 小念頭（11-05 晚 small-thought）：派一件事給用完即走的子 agent（範本 demo/agent-fsm）只拿回結論；`agent`（叫 aos-agent、逾時與 TERM 收整群、錯取最後一行代號）、`reconcile`（工具小格 `children/<名>/state` 對 `ctl ls`，failed 超過 3 隻 rm 最舊）、深度讀寫子 stack 的 `thought.json`、`undo`（設定失敗收回）、子答不出 `ctl stop` 留 stack |

## `proto8/knowledge/`（知識庫：記憶工具讀的資料夾樹，不是程式）

| 檔 | 負責什麼 |
|---|---|
| `README.md` | 知識庫是什麼、節點怎麼寫（繁中，給人） |
| `aos/README.md`、`aos/*.md`、`aos/me/*.md`、`aos/agents/README.md` | 第一個知識庫：aos 體系知識（英文、給小模型）：根＝八個詞＋五條規則；節 `world`、`me`、`me/self_tools`、`agents`、`brain`、`status`、`errors`、`rules`、`cli`（各節教什麼見 [thinking 02](../../../../../proto8/thinking/2026-11/05/agent-knowledge/02-aos知識庫.md)） |
| `claude/`、`codex/` | claude／codex CLI 當工具：`_entry`、`_tooldef.json`、`_metainfo.json`、`cli.json`（CLI 旗標） |
