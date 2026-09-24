← [本提案](README.md)

# 兩支 CLI 在這台機器上查到的事（2026-09-24）

**只查了 `--help`，沒有真跑任務、沒花錢。** 標「未實測」的是照官方文件或慣例推的，做原型第一步就要驗。

| | Claude Code | Codex |
|---|---|---|
| 版本 | `claude --version` → `2.1.281 (Claude Code)`，在 `~/.local/bin/claude` | `codex --version` → `codex-cli 0.156.1`，在 `/usr/bin/codex` |
| 設定與登入 | `~/.claude/`（session 紀錄、settings.json、使用者自己的記憶與 CLAUDE.md） | `~/.codex/`（`auth.json`、`config.toml`、`AGENTS.md`、session）；`CODEX_HOME` 可換位置（help 提到 `$CODEX_HOME/config.toml`） |

## Claude Code：非互動會用到的旗標

| 旗標 | help 原意（摘） | 對 aos 的用處 |
|---|---|---|
| `-p` | 印完就退；**非互動時跳過「信任這個資料夾」的對話框**，help 叫你只在信得過的資料夾用 | 一張單子＝一次 `claude -p` |
| `--output-format json`／`stream-json` | 只在 `-p` 有效；json＝一個結果物件 | 讀回話與 session id。欄位名（`result`、`session_id`、`is_error`、`total_cost_usd`…）help 沒列，**未實測** |
| `-r`／`--resume <id>`、`--fork-session` | 接著某個 session；加 fork＝接著但換新 id | 上下文延續（[as-cpu §5](as-cpu.md#5-上下文怎麼延續)） |
| `--session-id <uuid>` | 指定新 session 的 id | 可以事先決定 id |
| `--no-session-persistence` | 不存 session（只在 `-p`） | 一次性的單子 |
| `--model`、`--effort`、`--fallback-model` | 模型別名、思考強度、過載時換模型 | 單子裡寫 |
| `--system-prompt`、`--append-system-prompt` | 換掉／追加系統提示 | 人格 |
| `--tools`、`--allowedTools`、`--disallowedTools` | 內建工具白名單；允許／拒絕規則，如 `Bash(git *)` | 工具範圍；**拒絕規則換個寫法（`sh -c`）就繞過**，真正的牆要靠牢 |
| `--permission-mode` | `acceptEdits`／`auto`／`bypassPermissions`／`manual`／`dontAsk`／`plan` | 沒人按「允許」，要選不會停下來問的 |
| `--permission-prompts none` | `-p` 時沒人回答權限提示＝一律拒絕 | 保證不會卡在等人 |
| `--restricted` | 拿掉 Bash 等會跑程式的工具與 WebFetch；檔案工具只能碰工作資料夾（含 `--add-dir`）；拒絕 bypassPermissions；不讀使用者／專案設定檔 | 「只讀寫、不跑程式」的安全版；但 `--tools` 明列仍能把執行工具加回，MCP 要另用 `--strict-mcp-config` 限 |
| `--add-dir` | 額外准碰的資料夾 | 對應 access.json 的映射 |
| `--safe-mode` | 關掉 CLAUDE.md、skills、plugins、hooks、MCP、自訂 agent；**登入、模型、內建工具照常** | 不讓使用者自己的 CLAUDE.md／記憶混進來；**也會關掉 skill 與 MCP**，要讓它用 aos 工具時就不能開 |
| `--bare` | 更精簡；Anthropic 登入只認 `ANTHROPIC_API_KEY` 或 `--settings` 給的 apiKeyHelper（**不讀 OAuth**）；第三方供應商用它們自己的憑證 | **要用訂閱額度就不能開** |
| `--mcp-config`、`--strict-mcp-config` | 只載入指定的 MCP 伺服器 | 把 aos 指令包給它（[others §4](others.md#4-反過來讓它們用-aos)） |
| `--max-budget-usd` | 只在 `-p`；「API 呼叫最多花多少美元」 | 用訂閱登入時算不算數，**未實測** |
| `--json-schema` | 最終輸出照 JSON Schema 驗 | 要它回固定形狀（抽取器、純模型） |
| `--bg`、`claude agents`／`attach`／`stop` | 背景 session | 另一條長駐路線，本提案不用 |
| stdin 當提示 | `claude -p < task.md` | help 沒寫，**未實測**；不行就把任務書路徑放在提示字串裡 |

## Codex：`codex exec`

| 旗標 | help 原意（摘） | 對 aos 的用處 |
|---|---|---|
| `codex exec [PROMPT]`、`-` | 沒給或給 `-`＝從 stdin 讀；同時給＝stdin 附在後面 | 任務書從 stdin 餵（調度者現在就這樣用） |
| `--json` | 事件一行一個 JSON 印到 stdout | 官方文件列了 `thread.started`（帶 `thread_id`）、`item.completed`（agent_message）、`turn.completed`（usage）、`turn.failed`；**官方契約、本機未實跑**。用成功事件判完成，別撿最後一行 |
| `-o FILE` | 最後一則訊息寫進檔 | 回話本文 |
| `-m`、`-C DIR`、`--add-dir` | 模型、工作根、額外可寫資料夾 | 單子裡寫 |
| `-s read-only｜workspace-write｜danger-full-access` | 它自己的沙盒（跑模型產生的 shell 指令時） | 自帶一道牆；審查員用 `read-only` |
| `--skip-git-repo-check` | 不在 git repo 也能跑 | 工作區不一定是 repo |
| `--ephemeral` | 不存 session 檔 | 一次性的單子 |
| `--ignore-user-config`、`--ignore-rules` | 不讀 `config.toml`（**登入仍用 `CODEX_HOME`**）、不讀 execpolicy | **只跳過 `config.toml`**，不擋 `AGENTS.md`、專案設定；要真的隔開得用專用的 `CODEX_HOME` |
| `--output-schema FILE` | 最終回覆照 schema | 同 claude 的 `--json-schema` |
| `codex exec resume <id> [-]`、`codex exec fork <id> [-]` | 接著／分岔一個 session | 上下文延續 |
| `-c key=value` | 單次蓋設定 | 模型、沙盒 |
| `--search`（頂層 `codex` 才有） | 開網路搜尋 | exec 可用 `-c 'web_search="live"'`（照官方設定參考，未實跑） |

**兩個坑（help 查到）**：
- `codex exec resume` 與 `fork` 的選項裡**沒有 `-s`、`-C`、`--add-dir`**；但放在子命令**前面**（`codex exec -s read-only -C DIR resume …`）可以解析（審查員用 `--help` 驗過），實際有沒有套用**未實測**。另一條路是 `-c` 蓋設定。
- `-s workspace-write` 預設關的是**它跑的指令**的網路，可被設定打開；模型本身連 API、網路搜尋另算。範本要明寫網路策略。
- 頂層有 `--no-daemon`（不用共用的背景 server）：exec 的工作是否真的在我們砍得到的 process group 裡，**要驗**。
- 頂層 `codex` 有 `-a never`，`codex exec` 沒有（非互動本來就不問人）；這版**沒有 `codex mcp-server`**（`codex mcp` 只管它要連的外部伺服器；另有 experimental 的 `app-server`）。

## 還沒驗、做原型第一天要驗的

1. `claude -p` 吃不吃 stdin；json 輸出的欄位名；`--resume` 不加 fork 時 id 變不變。
2. 用訂閱登入時 `--max-budget-usd` 有沒有作用；額度用完時退出碼與訊息長怎樣（aos 要靠它判「失敗」）。
3. 從一個 Claude Code session 裡開的 daemon，子行程會繼承 `CLAUDECODE` 之類的環境變數；巢狀開 `claude` 會不會被擋。
4. `codex exec --json` 的事件是否跟官方文件一致；子命令前的 `-s`／`-C` 對 resume／fork 有沒有生效；被逾時砍時背景 server 有沒有留下在跑的工作。
5. 兩支在 bwrap 牢裡（掛一份只含登入檔的設定資料夾、開網路）跑不跑得起來；codex 自己的沙盒在牢裡能不能再開一層。
