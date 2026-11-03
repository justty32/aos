← [入口](../proto8.md)｜涵蓋：`proto8/lib/`（base、aos、agent、endpoint）

工具契約、分層與完整索引以 [lib/README](../../../../../proto8/lib/README.md) 為準。路徑相對於該段標題的資料夾。

**工具**＝一個資料夾三個檔：`_entry`（第二行是 NAME）、`_tooldef.json`（給模型看）、`_metainfo`（給 kernel 與人）；agent 的 `tools/<名>` 用捷徑掛進來。**格**＝agent 自己一輪照順序叫的資料夾程式（不是給腦叫的工具），叫法 `aos-exec <格> <agent 資料夾絕對路徑> [子命令]`。

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

## `lib/aos/`（懂 aos 的工具）

| 檔 | 負責什麼 |
|---|---|
| `aos_ws.py` | 不是工具：寄信、等答案、讀 stack 的共用模組（只碰 stack） |
| `memory/` | 長期記憶庫 save／search／read／forget（`$AOS_HEAP`）；`heap.py` 是讀寫本體 |
| `send_message/`、`check_inbox/` | agent 之間寄信（照 `$AOS_ROSTER` 名冊、手數上限）；看自己信箱 |
| `ask_round/` | 同步問一隻格組起來的 agent 一題：queue push → 一格一格叫 → 印答案 |
| `spawn_agent/`、`ask_agent/`、`agent_status/` | 轉叫 `aos-ai`：起 agent、問、看狀態 |
| `make_json/`、`make_tool/`、`explain_aos/` | 轉叫 `aos-ai`：生成 JSON 與工具骨架、查概念 |

## `lib/agent/`（agent 的格與 agent 當工具）

| 檔 | 負責什麼 |
|---|---|
| `parts.py` | 格的共用找法 `find(agent, 槽)`：先查 `parts.json`，再看固定名字 |
| `round/roundlib.py` | 一輪的表＋五格共用：`main(格, 函數)`、找格、錯一行 `round/<格>: 代號 原因` |
| `round/fsm-stop.json`、`round/fsm-idle.json` | 一輪的兩張 fsm 表（沒題目時停下／停著等）；agent 的 `loop.json` 直接叫 `aos-fsm` |
| `round/idle/_entry` | 認領一題（`queue claim`；`cur/` 有沒接完的就補認領） |
| `round/think/_entry` | 問腦一次（`hook/pre_think` → endpoint → `post_think`），接進 history |
| `round/act/_entry` | 還有沒回的 tool_calls 就叫 act 格，tool 訊息接進 history |
| `round/more/_entry` | 插話後把新信接進 history |
| `round/finish/_entry` | 交卷：`queue finish`、叫 `hook/post_round` |
| `queue/_entry` | `$AOS_STACK/queue/`（有序信箱，底下叫 aos-post）的放、等、認領、看、中間輸出、收掉、撤回 |
| `history/_entry` | `$AOS_STACK/history.jsonl` 的 append／read／compact |
| `compact/_entry` | 掛在 `hook/pre_think`：history 超過 `--max-bytes` 才三步壓縮 |
| `compact/ask.py` | compact 問腦（經 endpoint 格）與讀回覆 |
| `compact/prompts/*` | 三步的提示詞：`note.txt`、`segment.txt`、`final.txt` |
| `act/_entry` | 跑工具格：每個 tool_call 經 `hook/pre_tool` → `aos-tools call` → `hook/post_tool`（`--max-parallel`） |
| `agent_tool.py` | 不是工具：把一隻 agent 包成工具的轉接（`fresh_cell`、`run_agent`） |
| `pyfix/_entry`、`pyfix/_tooldef.json`、`pyfix/_metainfo` | 把改 Python 的事交給子 agent pyfix-agent，印答案＋實際 diff |
| `pyfix/agent/*` | 子 agent pyfix-agent：`_entry`、`loop.json`、`fsm.json`、`idle/`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json`、`tools/`（捷徑到 `lib/base`） |
| `cli_session.py` | 不是工具：claude／codex CLI 接成工具（非互動續對話，或 tmux 貼字等 hook）；`call_main`、`attach_main`、`hook` |
| `claude/`、`codex/` | claude／codex CLI 當工具：`_entry`、`_tooldef.json`、`_metainfo`、`cli.json`（CLI 旗標） |

## `lib/endpoint/`（腦）

| 檔 | 負責什麼 |
|---|---|
| `fake/_entry` | 假腦：不連網，照最後一則 user 拼答案（tools 有 clock 就叫 clock） |
| `openai/_entry` | OpenAI 相容腦：`{AOS_BRAIN_URL}/chat/completions` → 一行 assistant；usage 追加 `$AOS_STACK/usage.jsonl` |
