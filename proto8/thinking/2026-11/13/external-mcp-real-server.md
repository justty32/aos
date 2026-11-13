# 外部 MCP 接真的別人寫的 stdio server（11-13 公司 WSL，線丙）：官方 everything／time／filesystem 三台，eca（claude 經 aos＋CLI 自己接、codex CLI 自己接＋經 aos）與 agent-fsm（經 aos 匯入）都叫得到；codex 的 `disabled_tools` 有效；codex 沙盒管不到 stdio server；CLI 自己接的 server 壞了 aos 看不到（P3 仍在）

← [11-13 日索引](README.md)｜背景：[external-mcp](../12/external-mcp/README.md)、[06 施工結果](../12/external-mcp/06-施工結果.md)、[08 fsm 施工結果](../12/external-mcp/08-fsm施工結果.md)「沒做沒驗」

## 使用者原話

- 下載：「都可以下載」（11-13，經調度者轉述）。

## 場子

- 暫存夾 `~/code/mcp-try-1113/`（留著給使用者看）：`npm/`（npm 專用 prefix、`.npm-cache` 也在夾內）、`py-time/`（uv venv，`.uv-cache` 在夾內）、`tree/`（暫存小樹）、`fs-sandbox/`（filesystem server 唯一准的資料夾）、`scratch/`（直接 `aos-tools call` 的探針）、`baseline-procs.txt`／`after-procs.txt`。沒裝全域、沒 sudo。
- 三台 server（版本釘死）：`@modelcontextprotocol/server-everything@2.1.0`、`@modelcontextprotocol/server-filesystem@2.1.0`（npm，`--save-exact`，加相依共 103 包）；`mcp-server-time==2026.8.18`（PyPI，帶 `mcp` 1.30.0）。挑 2.1.0 而不挑最新 2.3.0（11-11 才出）。everything 的 `gzip-file-as-resource` 會對外抓網址，匯入時 `--except` 掉、沒叫過。
- 工具鏈：node 24.19.0、uv 0.12.2、codex-cli 0.167.2、claude 2.1.323；aos 指令是 `~/.local/bin` 連到 `~/repo/aos` 那份（沒重 build、沒重 install）。
- 小樹 `tree/`：照 [ops-notes-to-aos 十七步](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)起（根＋領班），根多一格 `llm`（llm kernel，加兩條假腦劇本 `fake-mcp-a`、`fake-mcp-p3`）。`env.sh` 先把繼承來的 `AOS_*`、`CLAUDE*` 全 unset，只設 `AOS_HOME`、`AOS_LLM_KERNEL`。agent：`fsm_a`、`fsm_p3`、`fsm_p3b`（agent-fsm＋假腦）、`eca_c`（eca-claude、haiku、上限 0.3 美金）、`eca_x`（eca 換 `kind: codex`、`gpt-6-luna`）。真腦一共 4 輪（haiku 2、luna 2），haiku 第一輪 0.008 美金。抄進樹的 `templates/agent-fsm` 是 HEAD `3cf4a9226` 那份（之後工作樹裡別線的改動沒進來）。

## 結論

**匯入（`aos-mcp-import`）**：三台都一次過——everything `imported 15 of 16`（`--except gzip-file-as-resource`）、time `2 of 2`、filesystem `14 of 14`；協商到的協定版本 `2025-06-18`（everything 也服務 2026-07-28 版，aos 走舊握手照樣通）。filesystem 的 annotations 正確翻成 `side_effect`（write／edit／move／create＝true，讀的＝false）。`sync` 對真 server：沒動＝`no changes`；手改說明、手刪一支＝印 `~ echo: description changed`＋`+ get-sum`，`--yes` 寫回 `synced 15 of 16`，再 sync＝`no changes`。

**fsm 經 aos（`fsm_a`，假腦一題 9 支）**：`Echo: hello from fsm`、`The sum of 2 and 40 is 42.`、time 回 `"datetime": "2026-11-13T09:40:15+08:00"`、structured content 回 JSON、圖片存成 png、`fs_write_file`＝`Successfully wrote to …/fs-sandbox/from-fsm.txt`、讀回同一句；越界讀 `/etc/hostname`＝server 自己擋（`Access denied - path outside allowed directories`）、參數錯＝`Input validation error …`，兩個都接成 `mcp_tool: error: CallFailed the server reported an error`＋`[aos] tool: … exit code 1.` 回給腦、fsm 沒停。

**eca claude（`eca_c`，haiku 一輪）**：ev 經 aos（`tools.json` 疊 `mcp/ev.json`）、time CLI 自己接（`cli.json` 的 `mcp_servers`）。`live.jsonl` init：`mcp_servers` 兩台 `connected`、`mcp__aos__ev_*` 15 支、`mcp__time__*` 2 支；三支實叫：`Echo: hi from eca`、`The sum of 3 and 4 is 7.`、`2026-11-13T09:42:56+08:00`。

**eca codex（`eca_x`，luna 一輪）**：ev（帶 `except` 四支）與 fs CLI 自己接、time 經 aos。codex 命令列實際帶 `mcp_servers.ev.disabled_tools=["get-env", "gzip-file-as-resource", "toggle-simulated-logging", "toggle-subscriber-updates"]`；腦列出的 ev 工具 15 支、四支都不在，它答「ev does not have a `get-env` tool」。實叫 `mcp ev echo completed`（`Echo: hi from codex`）、`mcp aos time_get_current_time completed`、`mcp fs list_allowed_directories`、`mcp fs write_file completed`。

**`disabled_tools`（E5／X9）**：有效，代定 E5 可以拿掉「沒實測」。

**codex 沙盒對 stdio（03 步 4 開工先驗）**：管不到。同一輪 codex 的 shell 寫 `fs-sandbox/`（工作區外）＝`zsh:1: read-only file system`、exit 1；fs server 經 MCP 寫同一個資料夾＝成功、檔在。跟 X15「不為外部 server 另做沙箱」一致：server 能碰什麼由 server 自己（這台是 allowed dirs）與 Linux 權限決定。

**P3（server 壞了／中途死掉）**：

| 情況 | 經 aos（fsm 與 eca 的 `mcp__aos__*` 同一支 `mcp_tool`） | CLI 自己接 |
|---|---|---|
| `command` 不在 | `mcp_tool: error: CommandMissing cannot start MCP server`，腦拿得到 | claude：那台的工具整台不見，`live.jsonl` init 只有 `"status": "failed"`；codex：工具整台不見，`live.jsonl`、stack 的 `stderr.txt` 都沒字。aos 兩身都不報 |
| server 一起來就退（印錯到 stderr） | `ServerFailed MCP server closed its output`，server 的 stderr 附在後面 | 沒驗（同上，預期一樣看不到） |
| stdout 印垃圾、不回握手 | 30 秒後 `ServerFailed MCP server request timed out`，server 行程有收掉 | 沒驗 |
| 叫到一半 server 被 `kill -9` | 立刻 `ServerFailed MCP server closed its output`，fsm 照走下一步 | 沒驗 |

經 aos 那條 P3 已經看得到；**CLI 自己接那條 P3 仍在**（06 記的那條沒變）。

**兩條路看到的工具不一樣多**：codex 自己接看得到 everything 的三支 elicitation 工具（`trigger_elicitation_request` 等），aos 匯入看不到（16 支裡沒有）；推測是 server 只列給宣告了 elicitation 能力的 client，aos 的 client 沒宣告（沒去讀 server 原始碼證實）。不是 bug，換路時工具數會差。

## 問題（重現與判斷；沒動手修，proto8 寫入權在線乙）

1. **CLI 自己接的 server 起不來，aos 不報（P3，中）**。重現：eca 的 `cli.json` `mcp_servers` 指一份 server 檔，把 `command` 改成不存在的路徑，`aos-agent say` 一句。claude：`live.jsonl` init 的 `mcp_servers` 有 `{"name": "time", "status": "failed"}`，stack `stderr.txt` 0 位元組；codex：連 `live.jsonl` 都沒有。直接跑 `aos-mcp-launch <那份檔>` 會印 `aos-mcp-launch: error: CommandMissing cannot start …: No such file or directory`，但這行被 CLI 吞了。判斷修法：(a) claude 身，cli_session 讀 init 事件，外部 server 不是 `connected` 就在 stderr 印 `cli_session: warning: external MCP server <名> failed to connect (status …)`；(b) 兩身都可以在起 CLI 前先預檢（server 檔讀得過、`command` 找得到又能執行），不過就照 X8 warning 跳過那台。中途死掉只有 CLI 自己知道，aos 補不到。
2. **媒體存檔的提示路徑會指錯地方（低）**。重現：叫 `ev_get_tiny_image`，結果是 `[image saved: $AOS_STACK/image-_eycn2jk.png …]`，檔其實在 agent stack 的 `tools/ev_get_tiny_image/image-_eycn2jk.png`。`mcp_tool` 跑的時候 `$AOS_STACK` 是 aos-tools 給那支工具的小格，`tool_io.place` 照小格算；腦讀到的 `$AOS_STACK` 是自己的 stack，照字面找不到。判斷修法：`saved_media` 印工作區相對或絕對路徑，或 aos-tools 另給工具一個「agent stack」變數讓 `place` 照它算（後者會動到所有用 `place` 的工具，要先看別支有沒有同樣的問題）。
3. **匯入過的 server 檔換名或抄成別的名字，會靜靜用回舊檔（低，跟 G4 同類）**。重現：`aos-mcp-import ev-probe.json` 之後 `cp ev-probe.json ev-crash.json`，改 ev-crash.json 的 `command`、疊進 tools.json，`call ev_echo` 照樣起原本那台、回 `Echo: x`。原因：`tools` 的指標與 `_entry` 的 `--pack` 寫死匯入當時的檔名。放進別的資料夾、檔名不變就對（樹裡各 agent 的 `mcp/ev.json` 都是這樣抄的、沒事）。判斷修法：`mcp_tool` 發現 `--pack` 不是登記它的那份檔就報 `PackBad`；不然至少在 aos-mcp-import README 寫「改名＝重新匯入」。
4. **codex 0.167 的 shell 不出現在 `live.jsonl`（資訊）**：這版 codex 的 shell 走 `exec` 這個 custom tool（code mode），`exec --json` 沒有 `command_execution` 事件；rollout 裡才看得到（`exit_code: 1, read-only file system`）。aos 之後要從 `live.jsonl` 看 codex 跑了什麼指令會撲空。

## 代定（可翻案）

- 挑 2.1.0 不挑最新的 2.3.0（才出兩天）；三台都只碰本機。
- everything 的 `gzip-file-as-resource` 匯入時排掉、codex 那份 `except` 也排掉（它會對外抓網址）。
- 同一台 server 在 eca_c 只走一條路（ev 經 aos、time 自己接），照 templates/docs/01「一台選一條」。
- 沒驗：claude 的 `except`→`--disallowedTools`；CLI 自己接那條的「一起來就退」「中途死掉」（成本高、預期跟起不來一樣看不到）；經 aos 的 server 卡住不回（凍結的 `timeout_ms` 是 60000，沒實測）。

## 收尾

- 小樹 `aos-daemon-ctl -d ~/code/mcp-try-1113/tree/.stack shutdown`＝`4 procs asleep`；之後掃 `/proc`，cmdline 或 environ 帶 `mcp-try-1113` 的行程只剩查的那支 shell 自己。`~/aos-home` 沒碰。
- 殘留：`~/.codex/sessions/2026/11/13/` 多了一份 rollout（兩輪同一個 session）、`~/.claude/projects/` 多了 `tree/ws` 那份 transcript（都是這次的真腦輪）。
