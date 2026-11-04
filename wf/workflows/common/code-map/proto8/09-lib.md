← [入口](../proto8.md)｜涵蓋：`proto8/lib/`（base、aos、agent）

工具契約、分層與完整索引以 [lib/README](../../../../../proto8/lib/README.md) 為準。路徑相對於該段標題的資料夾。

**工具**＝一個資料夾三個檔：`_entry`（第二行是 NAME）、`_tooldef.json`（給模型看）、`_metainfo.json`（給 kernel 與人；11-04 前叫 `_metainfo`）；agent 的 `tools/<名>` 用捷徑掛進來。（11-03 round 那套「格」——一輪的表與五格、parts、queue、history、compact、act、`lib/endpoint/`——與 aos-ai 的六個工具、ask_round 連程式刪了，概念在 proto8/archive/agent-round-concepts/。）

## `lib/base/`（不懂 aos 的通用工具）

| 檔 | 負責什麼 |
|---|---|
| `read/`、`write/`、`edit/` | 讀檔（截斷提示）、整份寫、照字面替換（全有或全無） |
| `bash/` | 在工作區跑一行 bash（`timeout_s`、逾時整群收） |
| `ls/`、`stat/`、`view/` | 列資料夾（分頁、JSON）、單一個的屬性、漸進看檔 |
| `mkdir/`、`move/`、`copy/`、`trash/` | 建資料夾、搬／改名、複製、丟進 `.trash/<時間>/`（可救回） |
| `json_read/`、`json_edit/` | 照指標看 JSON；照指標改 JSON（經 PATH 上的 `aos-json`） |
| `math/`、`clock/` | 四則運算、印 UTC 時間 |
| `run_python/` | 跑一段 Python，回結束碼與輸出 |
| `llm_http/`、`llm_fake/` | endpoint 函數（11-04 晚）：stdin `{endpoint, request}` → POST OpenAI 相容端點、印 `{message, usage, model}`；假腦同契約不碰網路。aos-llm-kernel 的 `kernel.json` `exec`／`endpoints.*.exec` 指它們 |

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
| `pyfix/agent/*` | 子 agent pyfix-agent：`_entry`、`loop.json`、`fsm.json`、`idle/`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json`、`tools/`（捷徑到 `lib/base`） |
| `cli_session.py` | 不是工具：claude／codex CLI 接成工具（非互動續對話，或 tmux 貼字等 hook）；`call_main`、`attach_main`、`hook`；`stack_copies`＝`$AOS_STACK` 的 `tools.json`／`llm.json` 副本優先（11-04） |
| `claude/`、`codex/` | claude／codex CLI 當工具：`_entry`、`_tooldef.json`、`_metainfo.json`、`cli.json`（CLI 旗標） |
