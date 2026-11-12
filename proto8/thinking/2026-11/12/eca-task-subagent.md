# eca 的子 agent 與 skill、aos MCP 切兩台：調查與施工結果（11-12 晚，家機）

← [11-12 日索引](README.md) ・ 前情：[eca-file-tools](eca-file-tools.md)（claude 開內建工具、dontAsk＋白名單）、[external-mcp 06](external-mcp/06-施工結果.md)

## 使用者原文

- 11-12 晚：「對了，關於claude eca那塊，我有些想法，想請你派一個fable去研究並實作。就是說claude code cli自己本身有Task工具，可以的話幫我加入claude eca範本和定義中(Skill也加上)。然後我們的aos工具是透過mcp接入claude code cli的，這個mcp在claude跑Task工具叫出子agent的時候會被繼承，這一塊似乎可以用一些選項設定.claude/...，去設定說子agent只能用啥工具或mcp，這個要調查一下。要是真能，那我們就可以將aos mcp切成幾個，一個是給主agent用的，另一個是比較少功能的，給子agent用的」
- 11-12 晚（追加）：「去做吧」「codex eca那塊也去研究看看，應該也有類似功能」
- 11-12 晚（codex 身會連到全域 `~/.codex/config.toml` 的 MCP、每輪留幾行 `AuthRequired`）：「全域mcp這個我們管不着，只要確定不要干擾到我們的aos就好。」

## 決定

1. **claude eca 範本開 `Agent` 與 `Skill`**：`templates/eca-claude/cli.json` 的 `--tools` 改成 `Read,Write,Edit,Glob,Grep,Bash,Agent,Skill`；其餘旗標不動（dontAsk、`--allowedTools Write,Edit,Bash`、`--strict-mcp-config`），沒加任何全繞過權限的旗標。
2. **限制得了，所以切**：`cli.json` 新增選填鍵 `tools_sub`＝子 agent 那台的 aos 登記檔；範本帶一份 `tools_sub.json`。主 agent 那台（`aos`，25 支）不變；內建的 `general-purpose` 子 agent 只拿到 `aos_sub`（八支）；其他類型的子 agent 叫 `mcp__aos__*` 會被擋。沒寫 `tools_sub`＝不切，照 CLI 預設。
3. **codex 身**：見下「codex 身」一節。
4. **全域 MCP 不隔離**（使用者裁）：只確認不干擾 aos，見下「全域設定帶進來的東西」。

## 調查結論：claude（本機 2.1.322）

「文件」＝ code.claude.com/docs 的 sub-agents、permissions、cli-reference、skills 頁（11-12 抓）；「實測」＝本機 `claude -p`、haiku、兩台假 stdio MCP（alpha、beta，各兩支工具；另一台 gamma 只內嵌給子 agent）。

| 題 | 文件寫的 | 實測到的 |
|---|---|---|
| 子 agent 工具叫什麼 | 正式名 `Agent`；2.1.63 前叫 `Task`，舊名當別名還認 | `--tools` 寫 `Agent` 或 `Task` 都開得起來；`-p` 的 init 事件列成 `Task`，模型實際叫的 tool_use 名字是 `Agent` |
| dontAsk 下卡不卡 | 子 agent 沒設 permissionMode 就繼承主對話的模式與規則 | `Agent`、`Skill` 不必列進 `--allowedTools`，`permission_denials` 是空的；子 agent 用 Read、Bash、MCP 工具都照主對話的白名單過 |
| 子 agent 繼承哪些 MCP | 繼承主對話所有內建與 MCP 工具（去掉少數幾支內建） | `general-purpose` 與 `Explore` 都拿到 alpha、beta 兩台全部工具、叫得到 |
| 定義裡 `tools`（白名單） | 可寫 MCP 工具名或整台 | `["Read","mcp__beta__beta_secret",…]` 與 `["Read","mcp__beta"]` 都只拿到列的；alpha 不在清單裡 |
| 定義裡 `disallowedTools` | 從繼承的清單拿掉；可寫整台 | `["mcp__alpha"]`＝內建工具與 beta 照繼承、alpha 整台不見 |
| 定義裡 `mcpServers` 內嵌 | 內嵌的 server 只給那個子 agent，主對話沒有；`--strict-mcp-config` 會濾掉 `.claude/agents/*.md` 裡內嵌的，但**不濾** `--agents` 帶進來的 | 主對話只接 alpha、`--agents` 內嵌 gamma：子 agent 拿到 alpha＋gamma，主對話的 init 只有 alpha；再加 `tools` 白名單＝只剩 gamma（都在 `--strict-mcp-config` 下） |
| 定義放哪 | `.claude/agents/*.md`（工作區或帳號）、`--agents` JSON | 兩種都生效（工作區 `.claude/agents/filehelper.md` 的 `tools: Read, mcp__beta` 有效） |
| 蓋掉內建類型 | 同名定義蓋掉內建（文件只舉 Explore） | `--agents` 定義 `general-purpose`＝蓋掉內建的，限制有效 |
| 關掉內建類型 | `--disallowedTools "Agent(Explore)"`、`permissions.deny`；`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` 在非互動模式關掉全部內建 | 兩個都有效：環境變數＝只剩外掛帶的與 `--agents` 定義的；`--disallowedTools "Agent(Explore),Agent(Plan)"`＝叫 Explore 回 `Agent type 'Explore' has been denied by permission rule`（類型還列在清單裡，叫的時候才拒） |
| 只限某幾類型 | `--tools` 的說明沒寫 `Agent(類型)` | `--tools "…,Agent(general-purpose)"`＝整支 Agent 工具不見（不能這樣寫） |
| hook 分得出子 agent 嗎 | — | PreToolUse 的輸入在子 agent 叫工具時多 `agent_id`、`agent_type`；主對話叫的沒有。hook 回 deny 擋得住 |
| Skill | 子 agent 預設也能用 Skill；skill 從工作區 `.claude/skills/`、`~/.claude/skills/`、外掛載入 | 工作區放一個 skill：主對話與 general-purpose 子 agent 都用 `Skill` 叫到、拿到內容；dontAsk 下沒被拒 |

**所以限制有兩層，缺一不可**：
- 「這個類型看得到什麼」靠定義（`tools`／`disallowedTools`／`mcpServers`），但只管得到**有定義的那個類型**；沒有「所有子 agent 一律…」的設定。主對話隨時可以改叫 Explore、Plan、外掛帶的或使用者帳號裡自己定義的類型，那些照樣繼承全部。
- 所以再加一層「叫的時候擋」：PreToolUse hook 看 `agent_id`，不分類型。

`settings.json` 的 `permissions.deny` 寫 `mcp__server` 是全域的，連主對話一起擋，不能拿來只擋子 agent。

## 做了什麼（claude 身）

- `lib/agent/cli_session.py`：`cli.json` 選填 `tools_sub`（寫法同 `tools`）。有寫時起 claude 多帶：
  1. `--agents`：蓋掉 `general-purpose`——`disallowedTools: ["mcp__aos"]`、`mcpServers` 內嵌 `aos_sub`（另一隻 `aos-mcp`，同一個工作區與 stack，帶 `--hooks` 與 `tools_flags`，不帶 `--own`）；
  2. `--allowedTools` 多 `mcp__aos_sub`；
  3. `--settings` 的 PreToolUse hook（matcher `mcp__aos__.*` → `cli_session.py guard`）：輸入有 `agent_id`＝deny＋一句說明；讀不懂輸入也 deny。畫面那條路併進原本那份 hook 設定。
- `templates/eca-claude/`：`cli.json`（`--tools` 加 `Agent,Skill`、`"tools_sub": "tools_sub.json"`）、新檔 `tools_sub.json`。
- 測試 `lib/agent/tests/test_cli_tools_sub.py`（14 支）；說明在 [templates/docs/01 § 子 agent 與 skill](../../templates/docs/01-eca-claude.md#子-agent-與-skill11-12-晚-eca-task-subagent)。

**真腦實測（haiku，暫存定義＝範本原樣、不掛 daemon 直接跑 `aos-eca-turn`）**：一封信要它做四件事——
1. 主 agent 自己叫 `mcp__aos__peek_now_time` → `2026-11-12T11:06:38Z`（guard 沒擋主對話）。
2. `general-purpose` 子 agent 列工具 → `Agent, Bash, Edit, Glob, Grep, Read, Skill, Write` 加 `mcp__aos_sub__` 八支，沒有任何 `mcp__aos__*`；叫 `mcp__aos_sub__math`（6*7）與 `mcp__aos_sub__json_get` 都回 `42`。
3. `Explore` 子 agent：清單裡有 `mcp__aos__peek_now_time`、沒有 `mcp__aos_sub__*`；一叫回 `PreToolUse:mcp__aos__peek_now_time hook error: aos tools on the server aos belong to the main agent and are not available to subagents. …`。
4. 主 agent 自己的清單沒有 `mcp__aos_sub__*`；init 的 MCP 只有 `aos`。

`permission_denials` 空；跑完沒有殘留的 aos-mcp 行程。`-p` 下子 agent 常被放到背景跑、同一次 `claude -p` 會吐好幾個 `result` 事件，cli_session 取最後一個，拿到的是等子 agent 回來之後的完整回答。

## 代定清單（可翻案）

- **T1 子 agent 那台放八支**：peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_multi_get、index_view。判準：`_metainfo.side_effect` 是 false，而且講的不是「這隻 agent 自己」。不放 json_set／add／del／multi_set、self 一族（含唯讀的 self_state）、events、def、mailbox 三支（含唯讀的 mailbox_peek：信箱是主 agent 的）。翻案＝改 `templates/eca-claude/tools_sub.json`。
- **T2 切的是 `general-purpose`**（Agent 工具沒指定類型時用的那個）；因為要蓋掉內建的，定義裡的說明與 prompt 是 aos 寫的短版（英文），不是 claude 內建那份。
- **T3 其他類型不給 aos**：Explore、Plan、外掛或使用者自己定義的類型，看得到 `mcp__aos__*` 但叫了被擋，也沒有 `aos_sub`。沒去關掉這些類型（關掉＝少功能；eca「以 CLI 為主」）。
- **T4 鍵名 `tools_sub`、server 名 `aos_sub`**（主題放前面）；工具名是 `mcp__aos_sub__<名>`。
- **T5 沒寫 `tools_sub`＝不切、不擋**（寫什麼就做什麼）；範本預設有寫。
- **T6 `self_tools`／`aos-agent tools` 的加減只進主 agent 那台**，子 agent 那台只看定義的 `tools_sub.json`。
- **T7 `Agent`、`Skill` 不列進 `--allowedTools`**：實測 dontAsk 下不需要。
- **T8 guard 讀不懂輸入＝擋**：擋錯只少一次工具呼叫；放錯是子 agent 用到主 agent 那台。
- **T9 codex 身寫 `tools_sub`＝`CfgBad`**（不靜靜吞掉）。

## 全域設定帶進來的東西

- **claude**：`--strict-mcp-config` 讓使用者帳號設定與外掛的 MCP server 都不接（實測 init 的 MCP 只有我們給的）。但帳號層的 **skill、外掛、外掛帶的子 agent 類型**照樣載入（實測 init 列得出 feature-dev、code-simplifier 等類型與三十幾個 skill）：這是使用者自己帳號的東西，跟 aos 的工具不撞名（aos 的都是 `mcp__aos…`）；外掛帶的子 agent 類型叫 `mcp__aos__*` 一樣被 guard 擋。
- **codex**：見下節。

## codex 身

調查另派一位在做，結果隨下一個 commit 補在這一節。

## 未定題（要使用者裁）

claude 身的見回報；codex 的調查回來後一併補在這一節。

## 沒驗的

- 畫面那條路（`aos-agent open` 的 tmux 互動版）帶 `--agents` 與併進去的 PreToolUse hook：沒實跑，只有單元測試看旗標。
- 掛在 daemon 底下的整棵樹：沒起，只直接跑 `aos-eca-turn`。
- 子 agent 再叫子 agent（巢狀）、fork 模式、agent teams：沒測；guard 看的是 `agent_id`，推測一樣擋，未證實。
- sonnet／opus 沒測（只測 haiku）。

## 要重建什麼

持久格式沒改。已經抄出去的 eca 定義（試驗場、`~/aos-home` 這類）要用到新功能：`cli.json` 的 `--tools` 加 `Agent,Skill`、加 `"tools_sub": "tools_sub.json"`，並把範本的 `tools_sub.json` 抄過去（或整份定義照範本重抄）。
