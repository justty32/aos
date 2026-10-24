# proto8/ai_tools — 給 AI 用的 aos 工具集

**aos-ai - 讓 AI 用 aos：起 agent、丟題、跑、背景顧、看狀態與錯誤、停，生成 aos 的 JSON 與骨架，查概念；每次輸出一行 JSON。**

← [proto8](../README.md)｜設計與代定：[thinking 2026-10-24-ai-tools](../thinking/2026-10-24-ai-tools.md)｜用到的程式：[impls](../impls/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-directive）、範本 [demo/agent-dan](../demo/README.md)

嘗試性質（使用者 10-24「4.做一套方便AI使用我們這套aos工具的工具集」「我隨便說，你隨便做，反正只是嘗試」）。只管「aos 指令與資料夾」這一層；JSON 編輯只留接口（`edit`），agent 當工具、CLI 當工具、LLM kernel 是別的嘗試。

```
ai_tools/
  bin/aos-ai                 命令列（Python，只用標準庫）。PATH 自己放好 impls 各支（含 aos-json）、proto8/bin、自己
  bin/aos_ai_make.py         make：生成 JSON（驗形狀、欄位說明 notes）與骨架（工具、fsm 格、函數資料夾）
  bin/aos_ai_explain.py      explain：印概念一節；--here 照 N-58／N-59／N-61 模擬 aos-exec 會給的值
  （dan_tools/ 已刪）         給 agent 掛的六個工具 10-24 遷移進 proto8/lib/aos/（見下「給 agent 的工具」）
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
agents/<名>/runs.jsonl    aos-ai run 每次一行：at、code、signal、timed_out、elapsed_ms、errors、answers
daemon/daemon.json        背景用的 aos-daemon（一個 root 一個）；.stack/ctl.json、.stack/state.json、各 agent 的小格
```

| 命令 | 做什麼 |
|---|---|
| `templates` | 列 `proto8/demo/agent-*` 範本與 `proto8/lib/aos/` 的工具（`--tool` 能掛的） |
| `spawn 名 [--from 範本] [--tool 工具]...` | 範本（名字或路徑，預設 agent-dan）複製到 `agents/<名>/agent/`，加工具，建工作區 |
| `ask 名 文字…｜- [--id 題名]` | 題目寫進 `ws/new/<題名>.txt`（先寫暫存再改名，N-05）；題名沒給＝`q<UTC 時間>` |
| `run 名 [--timeout 秒] [--env K=V]...` | 前景 `aos-exec --ws ws agent`（`AOS_STACK` 明寫成 `ws/.stack/`），跑到 idle 退 10；回答案、錯誤、hint |
| `status [名]`、`answer 名 [題名]`、`trace 名 [-n N]`、`history 名 [-n N]` | 看 |
| `start 名 [--interval-ms N]`、`stop 名`、`wait 名 題名 [--timeout 秒]` | 背景：寫 daemon 的 ctl `loops_added`（N-54），等 `ctl_seq` 回音才回 |
| `daemon up｜down｜status` | 起／停（ctl `stopped`）／看背景的 aos-daemon |
| `exec [--ws WS] 目標 [參數...]` | 直接 `aos-exec` 跑一次，回 `code`、`stdout`、`errors`；WS 要在 root 裡 |
| `edit 名 檔 [參數...]` | JSON 編輯的接口：交給 `$AOS_AI_JSON_EDITOR`（argv＋檔的絕對路徑＋參數）；檔要在 `agents/<名>/` 裡 |
| `doctor` | 程式在不在、`AOS_BRAIN_URL` 連不連得到 |
| `make inst｜loop｜fsm｜daemon｜metainfo｜tool_json [旗標] [--out 檔] [--force] [--no-notes]` | 生成一份 JSON：先驗形狀（`SpecBad`），`--out` 原子寫入（root 裡、已有＝`FileExists`），有 aos-json 就跑 `aos-json check`；loop／fsm／daemon 自動帶 `_entry`（`--entry no` 不帶）；每種都收 `--spec '{整份}'`、`--set key=值` |
| `make tool 名 工具 --description … [--param 名:型別[:說明][:required]]... [--lang python｜sh]` | 在 `agents/<名>/agent/tools/` 起工具骨架（tool.json＋`_entry`，給了 `--summary` 等再加 `_metainfo`） |
| `make cell 名 格 (--exec …｜--dir) [--after 前一格] [--next 下一格]` | fsm 加一格（`--dir` 另起格資料夾）；先驗整張表，改 fsm.json 交給 `aos-json set`（沒有 aos-json 才自己寫） |
| `make func 資料夾 [--summary …] [--argv …｜--inst 單子]` | 函數資料夾：`_entry`（sh 骨架或單子）＋`_metainfo` |
| `explain [概念]`、`explain --here [目標] [--ws WS] [--dotenv-override]` | 概念速成一節；或算出「現在 aos-exec 目標」會讀哪些 `.env`、挑到哪個入口、六個變數的值（模擬，以 aos-exec 為準） |

- **輸出**：stdout 一行 JSON，`ok` 一定有。下層 stderr 的每一行拆成 `errors[{prog, code, reason}]`（認不出的放 `raw`），失敗時加一句 `hint`（下一步）。答案文字超過 4000 字截斷、給 `path`。
- **錯**：aos-ai 自己的錯 stderr 一行 `aos-ai: 代號 原因（下一步：…）`、退 1。代號：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`RootMissing`、`PathBad`、`NameBad`、`AgentMissing`、`AgentExists`、`AgentBusy`、`TemplateMissing`、`ToolMissing`、`ToolExists`、`SpecBad`、`FileExists`、`CellExists`、`CellMissing`、`CfgBad`、`EditFailed`、`ConceptUnknown`、`QuestionBad`、`QuestionExists`、`AnswerMissing`、`WaitFailed`、`EditorMissing`、`CommandMissing`、`DaemonFailed`、`Internal`。**agent 跑失敗不是 aos-ai 的錯**：退 0，看 JSON 的 `ok`／`code`。
- **安全**：只寫 root 底下（`--ws`、`edit` 的檔都檢查）；名字只收 `[a-z0-9][a-z0-9_-]*`（擋 `../`）；不刪任何東西（`stop` 只是從 ctl 拿掉）；不碰 git。
- **同一隻不能同時兩個人跑**：前景 `run` 拿 `agents/<名>/.run.lock`（flock）；背景表上 running 時 `run` 回 `AgentBusy`。寫 ctl 也拿 `daemon/.ctl.lock`。

## 給 agent 的工具（10-24 遷移前叫 dan_tools，現在在 proto8/lib/aos）

**10-24 遷移**：六個工具搬進 [proto8/lib/aos](../lib/README.md)（`aos-ai spawn --tool` 從那裡複製），錯改照 lib 契約：stderr 與 stdout 各一行「工具名: 代號 原因」、退 1（代號照 aos-ai 的，例 `NameBad`）——下面這段說的「印成 JSON、退 0」是遷移前的做法；aos-ai 生出來的 agent-dan 範本遇到工具退 1 會停（`ToolFailed`），要讓腦自己改就照 agent-pip 改 act。放題、等答案、讀 stack 的做法也跟 proto8/human 合成一份 `proto8/lib/aos/aos_ws.py`。`aos-ai spawn` 複製範本時，範本裡指出範本的相對捷徑（掛 lib 的工具）改成絕對捷徑。

`aos-ai spawn boss --tool ask_agent --tool agent_status` 就掛上（生成與查概念：`--tool make_json --tool make_tool --tool explain_aos`）。照 P-41：`arguments` 從 stdin 進、stdout 整段是結果。子 agent 放 `$AOS_AI_ROOT`（沒設＝老闆的 `$AOS_WS`）的 `agents/<名>/`。aos-ai 回的錯（名字不合…）印成 `{"ok": false, "error": "aos-ai: 代號 …"}`、**退 0**，腦看得到、能自己改；只有 aos-ai 起不來才退 1（act 報 `ToolFailed`）。`ask_agent` 前景跑子 agent，上限 `$AOS_AI_ASK_TIMEOUT` 秒（預設 50，要小於 agent-dan act 格的 60 秒）。PATH 上要有 `aos-ai`——經 `aos-ai run` 跑的 agent 已放好。

## Claude Code skill（claude_skill/aos）

`claude plugin validate` 過。裝法三選一（**repo 根的 `.claude/` 沒動**）：

```bash
claude --plugin-dir proto8/ai_tools/claude_skill/aos            # 只這次 session（plugin，skill 叫 aos:aos）
ln -s "$PWD/proto8/ai_tools/claude_skill/aos" ~/.claude/skills/aos   # 每個 session 自動載入（aos@skills-dir）
mkdir -p .claude/skills && ln -s ../../proto8/ai_tools/claude_skill/aos .claude/skills/aos   # 只在這個 repo
```

另外要讓 Claude 找得到 `aos-ai`（PATH 加 `proto8/ai_tools/bin`，或照 SKILL.md 用完整路徑），非互動（`claude -p`）要允許 `Bash(aos-ai *)` 與完整路徑那條。

## 測試

`python3 -m unittest discover -s proto8/tests -p test_ai_tools.py`（或整包 `discover -s proto8/tests`）：前景一題、stdin 題目與重複題名、邊界（名字、路徑、範本、旗標、edit）、腦壞了停住再接著做、背景 start／wait／stop／down、老闆掛 `ask_agent` 經假 server 叫 helper、工具錯印成 JSON；生成的 loop＋fsm、單子、函數、daemon 真的經 aos-exec 跑、生成的工具＋格掛進 agent-dan 經假 server 叫到、`explain --here` 跟真 aos-exec 給入口的值逐個比、三個生成／概念工具。不叫真模型、不叫 claude。
