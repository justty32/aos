← [回入口 README.md](../README.md)｜段落：索引：agent、agent 自己的格（11-03 刪了）、外部 agent 的一輪（eca）、範例（demo/agent-liv 11-04 刪了）｜上一份：[02-索引-base與索引-aos](02-索引-base與索引-aos.md)｜下一份：—

## 索引：agent

| 工具 | 一句話 | 參數 | 回什麼 |
|---|---|---|---|
| [pyfix](../agent/pyfix/) | 把改 Python 的事交給子 agent pyfix-agent（`agent/`，它的工具是 base 的 ls、read、write、edit、bash） | `task`、`dir` | 子 agent 的報告＋實際 diff |
| [claude](../agent/claude/) | 交給 Claude Code CLI 做、同一段對話續著講（人可以 attach 進去） | `prompt` | CLI 的回答 |
| [codex](../agent/codex/) | 交給 Codex CLI 做、同上 | `prompt` | CLI 的回答 |
| [self_tools](../agent/self_tools/) | 改叫我的 agent 自己的工具箱（11-05 [feat-proto 件 1](../../thinking/2026-11/05/feat-proto/01-self-tools.md)，使用者「讓agent給自己改tool」）：`aos-agent ctl who` 查 daemon 表認出是哪隻，再 `aos-agent tools --target 那隻 add [--override]／rm／ls --json`——只改那隻的覆蓋層 `<stack>/tools.json`、定義不動，下一格 brain 重讀就看到。`path` 相對＝從 `$AOS_WS` 算、不能出工作區，絕對＝要在 `lib/` 底下，其他＝`PathBad`；aos-agent／aos-tools 的錯取最後一行代號回給腦（`PathMissing`、`ToolExists`、`ToolMissing`…，尾巴 `(from aos-tools)`）。只在 daemon 下跑的 agent 能用（沒表＝`DaemonMissing`／`InstanceMissing`）；不擋加什麼（10-15「先信任」）。PATH 要有 aos-agent | `op`（add／rm／ls）、`name`、`path`、`override` | add／rm 一句 `added X (…) to your tools; available from your next turn`；ls 一行 JSON（aos-tools ls --json） |

**共用模組**（不是工具、沒有 `_entry`；工具用 realpath 找到 `lib/agent/` 再 import）：
- [agent_tool.py](../agent/agent_tool.py)：「把一隻 agent 包成工具」的轉接，共用一支——每次呼叫開新小格 `$AOS_STACK/runs/NNN/`、題目寫進子 agent 的 `ws/new/`、`aos-exec --dotenv-override --ws` 跑、拿 `ws/out/` 的答案（錯 `AgentFailed`、`AnswerMissing`）。要把另一隻 agent 包成工具：資料夾裡放 `agent/`、`_entry` 叫 `agent_tool.run_agent`（pyfix 是範例）。
- [cli_session.py](../agent/cli_session.py)：claude／codex CLI 接成工具的做法（非互動續對話、或 tmux 畫面開著時從畫面送字）；工具資料夾由 `_entry` 傳進來（`cli.json` 在那裡）、agent 資料夾由 `attach` 傳進來。工具被整個複製進某隻 agent 的 `tools/`（覆寫）時，`_entry` 改找那隻 agent 根的 `cli_session.py`。拿到 session id 就在小格建 `transcripts/<kind>-<id>.jsonl`＝指到 CLI 自己存的對話檔（claude `~/.claude/projects/*/<id>.jsonl`、codex `~/.codex/sessions/**/*<id>.jsonl`）的 symlink，工具形（agent 叫的）也建；一直是 symlink，要留的人自己複製。問 CLI 那段（note_cell → lock → 畫面開著貼字／沒開非互動 → symlink）是 `ask(cfg, cell, tool_dir, ws, stack, prompt)`（`stack` 給 aos-mcp），工具形 `call_main` 與 eca 的 [`aos-eca-turn`](../../bin/aos-eca-turn) 共用。`live`、`ask`、`call_main` 有參數 `on_busy`（預設 `"yield"`＝有人佔著就 `SessionBad`，lib/agent/claude、codex 照用預設；`"answer"`＝lock 等、有人接著照樣貼、`busy.txt` 等它消失，給 `aos-eca-turn --on-busy answer`）。格裡記 `tool.txt`／`ws.txt`／`stack.txt`（`note_cell`，叫回畫面用）。**接 aos 工具**（[thinking eca-tools](../../thinking/2026-11/03/eca-tools/README.md)）：`cli.json` 選填 `tools`（aos-tools 登記檔，相對路徑從 cli.json 的資料夾算；沒寫＝同層 `tools.json` 有就用）與 `tools_flags`（原樣給 aos-mcp）；有登記檔時 `mcp_argv` 每次起 CLI 前接上 `aos-mcp --ws <工作區> --stack <stack> [tools_flags] [--overlay $AOS_STACK/tools.json] <登記檔>`（11-05：cli.json 沒明寫 tools 時，stack 裡那份是這隻的覆蓋層、疊在定義的登記檔上，定義那份不在也行；[aos-agent docs/03](../../extras/agent/docs/03-tools覆蓋層.md#tools-覆蓋層)）——claude 寫小格 `mcp.json`＋`--mcp-config`／`--allowedTools mcp__aos`，codex 兩個 `-c mcp_servers.aos.*`；stack 平級形＝那隻 eca 的 `$AOS_STACK`、工具形＝這格本身。錯 `ToolsMissing`（tools 指的不在）、`CfgBad`、`CliMissing`（aos-mcp 不在 PATH）、`WriteFailed`、`CellBad`（叫回畫面時沒 `stack.txt`）。lib/agent 的 `claude`、`codex` 兩個工具不附登記檔（要接自己加）。**開場白不歸這裡**（11-04 翻案，[eca 21](../../thinking/2026-10/30/eca/21-11-04-開場白檔可指定.md)）：是 [`aos-eca-turn`](../../bin/aos-eca-turn) 的 `--prompt FILE`，`cli.json` 寫了 `prompt` 跟其他沒認的鍵一樣不看。

pyfix 的子 agent 要改的程式在 `$AOS_WS/<dir>`——pyfix 開子 agent 前把它的絕對路徑寫進子 agent 的 stack 的 `pyfix_dir.txt`（一行），自己的 `$AOS_WS` 是收題交答案的小格，所以它的 act 讀 `$AOS_STACK/pyfix_dir.txt`、把庫的工具的工作區換成那裡（`AOS_WS=<那個資料夾> aos-tools call <名>`）（規則 4：換根是呼叫者的事）；庫的工具錯一律退 1，子 agent 的 act 把那行回給腦。
沒收進來的：agent-gus（11-04 隨 demo 刪了）的「小念頭」（`thought.json`／`thought.py`）——它是 agent-gus 自己的入口、遞迴起 agent-gus 本身（`shared.launch`），要收就得把整隻 agent-gus 搬進庫；也沒有給模型的 `_tooldef.json`。aos-json 自帶的 `tools/json`、`tools/json_edit`（小念頭式兩步改）留在 `impls/aos-json/`，跟它的測試在一起。

## agent 自己的格（11-03 刪了）

round 那套用格組起來的 agent（一輪的 fsm 表與五格、parts、queue、history、compact、act，與 lib/endpoint 的 fake、openai 兩個腦）11-03 連程式刪了（使用者「該刪的都刪光刪乾淨」），概念收在 proto8/archive/agent-round-concepts/。

<a id="外部-agent-的格eca不是工具"></a>
## 外部 agent 的一輪（eca）

claude code、codex 這類外部 coding agent 的一輪是 bin 指令 [`aos-eca-turn`](../../bin/README.md)（使用者「aos eca turn」；定義資料夾範本在 [demo eca-claude](../../demo/README.md#eca-templates)），問 CLI 那段是這層的 [cli_session](../agent/cli_session.py) `ask`。

## 範例（demo/agent-liv 11-04 刪了）

原本的 demo/agent-liv（`tools/` 七條捷徑掛 lib/base）隨 demo 刪了。捷徑掛庫的工具的例子現在是 agent-eve（11-04 隨 proto8/tests 刪了）：`tools/pyfix` 捷徑指到 lib/agent/pyfix，pyfix 的子 agent 的 `tools/` 再捷徑掛 lib/base 五個（read、write、edit、bash、ls）。
