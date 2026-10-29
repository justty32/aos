# proto8/extras/ai_tools — 給 AI 用的 aos 工具集

**aos-ai - 讓 AI 用 aos：起 agent、丟題、跑、背景顧、看狀態與錯誤、停，生成 aos 的 JSON 與骨架，查概念；每次輸出一行 JSON。**

← [proto8](../../README.md)｜設計與代定：[thinking 2026-10-24-ai-tools](../../thinking/2026-10-24-ai-tools.md)｜用到的程式：[impls](../../impls/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-directive）、範本 [demo/agent-dan](../../demo/README.md)

嘗試性質（使用者 10-24「4.做一套方便AI使用我們這套aos工具的工具集」「我隨便說，你隨便做，反正只是嘗試」）。只管「aos 指令與資料夾」這一層；JSON 編輯只留接口（`edit`），agent 當工具、CLI 當工具、LLM kernel 是別的嘗試。

```
ai_tools/
  bin/aos-ai                 命令列（Python，只用標準庫）。PATH 自己放好 impls 各支（含 aos-json）、proto8/bin、自己
  bin/aos_ai_make.py         make：生成 JSON（驗形狀、欄位說明 notes）與骨架（工具、fsm 格、函數資料夾）
  bin/aos_ai_explain.py      explain：印概念一節；--here 照 N-58／N-59／N-61 模擬 aos-exec 會給的值
  bin/aos-mcp                MCP server（stdio）：包在 aos-tools 上，agent 資料夾 tools.json 登記的工具＝MCP tools，見下「aos-mcp」
  （給 agent 掛的六個工具在 proto8/lib/aos/，見下「給 agent 的工具」）
    spawn_agent/             {"name", "template"?} → aos-ai spawn
    ask_agent/               {"name", "question", "template"?} → 沒有就 spawn，再 ask＋run，回答案
    agent_status/            {"name"?} → aos-ai status
    make_json/               {"kind", "spec", "out"?} → aos-ai make <kind> --spec …
    make_tool/               {"name", "tool", "description", "params"?, "lang"?} → aos-ai make tool
    explain_aos/             {"concept"?} → aos-ai explain
  claude_skill/aos/          Claude Code 的 skill（SKILL.md），同時是 plugin（.claude-plugin/plugin.json）
    concepts.md              aos 概念速成（每節：一句白話、最小範例、常見錯、條號）；aos-ai explain 讀的也是它
```

## aos-ai

只在一個工作資料夾（root）裡寫：`--root DIR`（放命令前面）＞ `$AOS_AI_ROOT` ＞ cwd。root 長這樣：

```
agents/<名>/agent/        agent 定義（範本的複本；定義資料夾不被寫，P-15）
agents/<名>/ws/           工作區 new/ cur/ out/ done/，stack 在 ws/.stack/（state.txt、trace.jsonl、history.jsonl…）
agents/<名>/runs.jsonl    aos-ai run 每次一行：finished_at（跑完的時間）、code、signal、timed_out、elapsed_ms、errors、answers
daemon/daemon.json        背景用的 aos-daemon（一個 root 一個）；.stack/ctl.json、.stack/state.json、各 agent 的小格
```

| 命令 | 做什麼 |
|---|---|
| `templates` | 列 `proto8/demo/agent-*` 範本與 `proto8/lib/aos/` 的工具（`--tool` 能掛的） |
| `spawn 名 [--from 範本] [--tool 工具]...` | 範本（名字或路徑，預設 agent-dan）原樣複製到 `agents/<名>/agent/`，加工具，建工作區；範本的 `parts.json`（格的通訊錄，例 `agent-nia`）與 `tools.json` 裡指出範本的相對路徑改成絕對（指在範本裡面的照舊相對；沒有 parts.json 的範本不受影響）；工具出錯停不停照範本自己的 act（agent-dan 回給腦） |
| `ask 名 文字…｜- [--id 題名]` | 題目寫進 `ws/new/<題名>.txt`（先寫暫存再改名，N-05）；題名沒給＝`q<UTC 時間>` |
| `run 名 [--timeout 秒] [--env K=V]...` | 前景 `aos-exec --ws ws agent`（`AOS_STACK` 明寫成 `ws/.stack/`），跑到 idle 退 10；回答案、錯誤、hint |
| `status [名]`、`answer 名 [題名]`、`trace 名 [-n N]`、`history 名 [-n N]` | 看 |
| `start 名 [--interval-ms N]`、`stop 名`、`wait 名 題名 [--timeout 秒]` | 背景：寫 daemon 的 `loops_ctl.json` 的 `loops_added`（N-54；10-29 拆窗前寫在 ctl），等 `loops_state.json` 的 `ctl_seq` 回音才回 |
| `daemon up｜down｜status` | 起／停（ctl `stopped`）／看背景的 aos-daemon |
| `exec [--ws WS] 目標 [參數...]` | 直接 `aos-exec` 跑一次，回 `code`、`stdout`、`errors`；WS 要在 root 裡 |
| `edit 名 檔 [參數...]` | JSON 編輯的接口：交給 `$AOS_AI_JSON_EDITOR`（argv＋檔的絕對路徑＋參數）；檔要在 `agents/<名>/` 裡 |
| `doctor` | 程式在不在、`AOS_BRAIN_URL` 連不連得到 |
| `make inst｜loop｜fsm｜daemon｜metainfo｜tool_json [旗標] [--out 檔] [--force] [--no-notes]` | 生成一份 JSON：先驗形狀（`SpecBad`），`--out` 原子寫入（root 裡、已有＝`FileExists`），有 aos-json 就跑 `aos-json check`；loop／fsm／daemon 自動帶 `_entry`（`--entry no` 不帶）；每種都收 `--spec '{整份}'`、`--set key=值` |
| `make tool 名 工具 --description … [--param 名:型別[:說明][:required]]... [--lang python｜sh]` | 在 `agents/<名>/agent/tools/` 起工具骨架（`_tooldef.json`＋`_entry`，給了 `--summary` 等再加 `_metainfo`），並登記進那隻 agent 的 `tools.json`（`aos-tools add`） |
| `make cell 名 格 (--exec …｜--dir) [--after 前一格] [--next 下一格]` | fsm 加一格（`--dir` 另起格資料夾）；先驗整張表，改 fsm.json 交給 `aos-json set`（沒有 aos-json 才自己寫） |
| `make func 資料夾 [--summary …] [--argv …｜--inst 單子]` | 函數資料夾：`_entry`（sh 骨架或單子）＋`_metainfo` |
| `explain [概念]`、`explain --here [目標] [--ws WS] [--dotenv-override]` | 概念速成一節；或算出「現在 aos-exec 目標」會讀哪些 `.env`、挑到哪個入口、六個變數的值（模擬，以 aos-exec 為準） |

- **輸出**：stdout 一行 JSON，`ok` 一定有。下層 stderr 的每一行拆成 `errors[{prog, code, reason}]`（認不出的放 `raw`），失敗時加一句 `hint`（下一步）。答案文字超過 4000 字截斷、給 `path`。
- **錯**：aos-ai 自己的錯 stderr 一行 `aos-ai: 代號 原因（下一步：…）`、退 1。代號：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`RootMissing`、`PathBad`、`NameBad`、`AgentMissing`、`AgentExists`、`AgentBusy`、`TemplateMissing`、`ToolMissing`、`ToolExists`、`SpecBad`、`FileExists`、`CellExists`、`CellMissing`、`CfgBad`、`EditFailed`、`ConceptUnknown`、`QuestionBad`、`QuestionExists`、`AnswerMissing`、`WaitFailed`、`EditorMissing`、`CommandMissing`、`DaemonFailed`、`Internal`。**agent 跑失敗不是 aos-ai 的錯**：退 0，看 JSON 的 `ok`／`code`。
- **安全**：只寫 root 底下（`--ws`、`edit` 的檔都檢查）；名字只收 `[a-z0-9][a-z0-9_-]*`（擋 `../`）；不刪任何東西（`stop` 只是從 ctl 拿掉）；不碰 git。
- **同一隻不能同時兩個人跑**：前景 `run` 拿 `agents/<名>/.run.lock`（flock）；背景表上 running 時 `run` 回 `AgentBusy`。寫 ctl 也拿 `daemon/.ctl.lock`。

## 給 agent 的工具（proto8/lib/aos）

六個工具（spawn_agent、ask_agent、agent_status、make_json、make_tool、explain_aos）在 [proto8/lib/aos](../../lib/README.md)，`aos-ai spawn --tool` 從那裡複製；照 lib 契約，錯是 stderr 與 stdout 各一行「工具名: 代號 原因」、退 1（代號照 aos-ai 的，例 `NameBad`），停下還是回給腦由叫它的 agent 決定（agent-dan 範本回給腦，[thinking](../../thinking/2026-10-23-tool-calls.md#10-24-定叫工具與小念頭的失敗回給腦)）。放題、等答案、讀 stack 的做法跟 proto8/extras/human 共用 `proto8/lib/aos/aos_ws.py`。`aos-ai spawn` 複製範本時，範本裡指出範本的相對捷徑（掛 lib 的工具）改成絕對捷徑。註冊檔也一樣：`parts.json`、`tools.json` 每一格的 `path` 是相對路徑、從範本資料夾算指到範本外面的（例 agent-nia 的 `../../lib/agent/round`），改成絕對路徑（不解開捷徑，同 `aos-parts add`／`aos-tools add`）；指示詞（`$ref`／`$env`）不碰。所以 `aos-ai spawn x --from agent-nia` 搬到 `agents/x/agent/` 後仍找得到 lib 的格（agent-round § 7 第 7 步，測試 `test_nia.py`）。

`aos-ai spawn boss --tool ask_agent --tool agent_status` 就掛上（生成與查概念：`--tool make_json --tool make_tool --tool explain_aos`）。照 P-41：`arguments` 從 stdin 進、stdout 整段是結果。子 agent 放 `$AOS_AI_ROOT`（沒設＝老闆的 `$AOS_WS`）的 `agents/<名>/`。`ask_agent` 前景跑子 agent，上限 `$AOS_AI_ASK_TIMEOUT` 秒（預設 50，要小於 agent-dan act 格的 60 秒）。PATH 上要有 `aos-ai`——經 `aos-ai run` 跑的 agent 已放好。

## aos-mcp（10-27；10-28 改成包在 aos-tools 上）

`bin/aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] AGENT_DIR...`：把 **agent 資料夾的 `tools.json`**（[aos-tools](../../bin/README.md) 的工具註冊檔）登記的工具當 MCP tools 給外部 agent（Claude Code、pi coding agent 等）叫，stdio JSON-RPC、只用標準庫。給不了外部 agent Bash 時用這條（能給 Bash 就繼續用 aos-ai＋skill）。決定 [thinking 10-28 aos-tools](../../thinking/2026-10-28-aos-tools.md)（使用者「aos-mcp 是一個小包裝，跑在 aos-tools 上」）。

> **10-28 介面改了**：以前給的是工具資料夾（掃 `tool.json`，或 `DIR/tools/*/tool.json`）；現在給的是 **agent 資料夾**，讀它的 `tools.json`，沒有就 `ToolMissing`。工具先用 `aos-tools add` 登記進去（資料夾、JSON 檔、可執行檔三種都行）。舊寫法 `aos-mcp lib/base/clock` 改成：建一個 agent 資料夾、`cd` 進去 `aos-tools add <路徑>/lib/base/clock`，再 `aos-mcp 那個資料夾`。

- **清單**：每個 AGENT_DIR 跑 `aos-tools --file AGENT_DIR/tools.json ls --json`；名字＝登記名、`description`／`inputSchema`＝工具定義的 `description`／`parameters`（沒寫 parameters 給空物件 schema）。`_metainfo`（資料夾的檔、JSON 檔的 key；可執行檔沒有）搬成 annotations：`side_effect`→`readOnlyHint`（反）、`idempotent`→`idempotentHint`、`resource` 含 llm／net→`openWorldHint`。好幾個 AGENT_DIR 的工具合在一起，撞名＝`ToolsBad`。**每次 `tools/list`、`tools/call` 都重讀**：tools.json 改了，下次列就看得到（不主動送 listChanged 通知；代定）。
- **叫一次**：`AOS_WS=WS AOS_STACK=<stack>/<名>/ aos-tools --file AGENT_DIR/tools.json call 名`（aos-tools、aos-exec、有指示詞時 aos-json 都從 PATH 找），arguments 進 stdin、stdout 整段回 text、退非 0＝`isError`（stdout 空就回一行 `aos-mcp: CommandFailed …`）；逾時＝`_metainfo` 的 `time_ms.max`，沒寫用 `--timeout-s`（預設 60），整群 TERM、2 秒後 KILL。每次叫完在 `<stack>/calls.jsonl` 記一行（`name`、`arguments`、`code`、`elapsed_ms`、`called_at`）。
- 工作區＝`--ws` ＞ `$AOS_WS`；stack＝`--stack` ＞ `$AOS_STACK` ＞ `$WS/.stack/`。自己的錯 stderr 一行 `aos-mcp: 代號 原因` 退 1（`ArgumentsBad`、`WsMissing`、`ToolMissing`〔AGENT_DIR 沒有 tools.json〕、`ToolsBad`〔啟動時 aos-tools ls 失敗，aos-tools 自己那行在前面〕）；跑起來之後 tools.json 壞了＝那一則回 JSON-RPC 錯誤（-32603）、不退。
- 只做 `initialize`、`ping`、`tools/list`、`tools/call`；沒有 progress、resources、prompts、HTTP。
- 掛法（Claude Code，WSL 裡）：`--mcp-config` 一份 `{"mcpServers": {"aos": {"command": ".../proto8/extras/ai_tools/bin/aos-mcp", "args": ["--ws", WS, AGENT_DIR], "env": {"PATH": "proto8/bin、impls 的 aos-exec／aos-json 的 bin:…"}}}}`，`--allowedTools mcp__aos__<名>`；例子在試驗場 `~/code/try/aos-tools/mcp.json`（不在 git）。**問一隻格組起來的 agent**（agent-round § 6 round 當外部接口）：登記 [`lib/aos/ask_round`](../../lib/README.md)（或一個工具小資料夾：`.env` 寫 `ASK_AGENT=<agent 資料夾絕對路徑>`、`_entry`／`_tooldef.json`／`_metainfo` 捷徑指 ask_round 的），Claude Code 叫它＝放題、叫 round 跑到答完、回答案，agent 不必常駐；被問的 agent 的工作區預設在 `<stack>/<工具名>/<agent 名>/`。測試 `proto8/tests/test_aos_mcp.py`。

## Claude Code skill（claude_skill/aos）

`claude plugin validate` 過。裝法三選一（**repo 根的 `.claude/` 沒動**）：

```bash
claude --plugin-dir proto8/extras/ai_tools/claude_skill/aos            # 只這次 session（plugin，skill 叫 aos:aos）
ln -s "$PWD/proto8/extras/ai_tools/claude_skill/aos" ~/.claude/skills/aos   # 每個 session 自動載入（aos@skills-dir）
mkdir -p .claude/skills && ln -s ../../proto8/extras/ai_tools/claude_skill/aos .claude/skills/aos   # 只在這個 repo
```

另外要讓 Claude 找得到 `aos-ai`（PATH 加 `proto8/extras/ai_tools/bin`，或照 SKILL.md 用完整路徑），非互動（`claude -p`）要允許 `Bash(aos-ai *)` 與完整路徑那條。

## 測試

`python3 -m unittest discover -s proto8/tests -p test_ai_tools.py`（或整包 `discover -s proto8/tests`）：前景一題、stdin 題目與重複題名、邊界（名字、路徑、範本、旗標、edit）、腦壞了停住再接著做、背景 start／wait／stop／down、老闆掛 `ask_agent` 經假 server 叫 helper、工具錯一行退 1；生成的 loop＋fsm、單子、函數、daemon 真的經 aos-exec 跑、生成的工具＋格掛進 agent-dan 經假 server 叫到、`explain --here` 跟真 aos-exec 給入口的值逐個比、三個生成／概念工具。不叫真模型、不叫 claude。
