← [回入口 README.md](../README.md)｜段落：外部 coding agent 範本（eca-claude）｜上一份：—｜下一份：[02-agent-fsm](02-agent-fsm.md)

## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../../cmd/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。CLI 對話共用 [lib/agent/cli_session.py](../../lib/agent/cli_session.py)，介面宣告共用 [lib/agent/agent_files.py](../../lib/agent/agent_files.py)（11-06 晚 K-5）；兩者都在 `lib`，不 import 上層 `py`。設計：[thinking 2026-10-30 eca](../../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 換成下面這份；**沙盒是 `workspace-write`**，codex 用自己的指令在工作區讀寫（11-12 使用者「codex拿掉唯讀沙盒」；不是 `danger-full-access`，隊長代定、使用者「可以先定這樣」，[thinking 11-12 eca-file-tools](../../thinking/2026-11/12/eca-file-tools.md)）。不要照抄 lib/agent/codex 那支工具的 `cli.json`：那是給腦叫的 codex 工具，沙盒照舊唯讀。）

```json
{"kind": "codex",
 "flags": ["-c", "sandbox_mode=\"workspace-write\"", "-c", "approval_policy=\"never\""],
 "print_flags": [],
 "timeout_ms": 600000}
```

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；三扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、tools_sub、timeout_ms）：--tools Read,Write,Edit,Glob,Grep,Bash,Agent,Skill、--permission-mode dontAsk、--allowedTools Write,Edit,Bash、--strict-mcp-config；
              tools_sub＝子 agent 那台的登記檔（11-12 晚，見下「子 agent 與 skill」）
              （11-12 起 claude 內建的寫檔、改檔、指令都開，aos 不再給檔案與 shell 工具；--model 不寫在這，見 llm.json；不加全繞過權限的旗標）
  llm.json    腦設定：{"model": "sonnet"}（11-04 晚；cli_session 每題依 interfaces.json 的 llm 宣告讀定義並疊 stack 下同一相對路徑的覆蓋層，補成 --model）；只認 model（claude CLI 沒有 temperature 等取樣旗標，與快取無關的調整鍵這邊沒有對應，11-10 晚）
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔11-04 起，相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
  tools.json  aos-tools 的登記檔：`"$override"` 一串 [lib/packs](../../lib/packs/README.md) 七包（gadgets、events、self、def、mailbox、json〔json_get、json_ls、json_search、json_set、json_add、json_del、json_multi_get、json_multi_set，11-12 json-tools〕、index〔index_view，11-12 index-tools〕），共 25 支；不掛通用四包 look、change、delete（含 trash）、shell（11-11 晚使用者「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」、11-12「可以先定這樣，然後trash也拿掉。」）與 subagent、goal、todo（11-11 晚，原話與代定見範本 README）；do_task 只給 agent-fsm，寫 `"do_task": null`；
              cli.json 沒寫 tools＝照 interfaces.json 的 tools 宣告用它，cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__peek_now_time…；帶 `--own <stack>/tools.json`，self_tools 加減工具後 aos-mcp 送 list_changed，同一輪就叫得到，11-10 深夜「3.同一輪就生效」）；不要工具就刪掉它
  tools_sub.json  子 agent 那台的登記檔（11-12 晚）：gadgets、json、index 三包裡不改東西的八支（peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_multi_get、index_view）
  interfaces.json  {"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json", "llm_keys": ["model"], "history": "history.jsonl", "hooks": "hooks.json"}}（11-04；hooks 鍵 11-10 晚加；history 鍵 11-10 加，給 aos-agent history 找檔；llm_keys 11-10 晚加，aos-agent llm set 不在上面的鍵照存＋warning；aos-agent ctl add 只看這個宣告）
  hooks.json  hook 清單（11-10 晚；11-11 起預設一格 timer：on_clock 每 300000 ms、handler lib/agent/hook_noop 什麼都不做；另一格 mail_notify：on_clock 每 60000 ms（11-11 翻案「每 1 分鐘」）、handler lib/agent/mail_notify，有新信才往 queue 寄一則 `[aos] new_mail: …`；stack 那份同名蓋過、null 關掉；`aos-agent hook` 管，見下「eca 的 hook」）
  screen/     子介面：_entry＝["aos-eca-screen", "--eca", ".."]（aos-agent open／close／watch 叫它；動作接在最後）
  README.md、_metainfo.json  首行一句話與 summary 一致；估時 cost.time_ms 60000、resource ["llm"]，沒有頂層 timeout_ms（11-10 晚補，讓 agent_def check 過）
```

**實例＝定義 × 工作區**：工作區＝CLI 的 cwd（你的程式專案）；stack 預設 `<工作區>/.stack/`（掛 daemon 的在 daemon 給的 proc 的 stack），裡面長 `queue/`、`history.jsonl`、`ctl.json`、`state.json` 與 cli_session 的小格 `claude/`（`session.txt`、`transcripts/`…）；`eca.json` 11-04 起不寫（沒人讀）。這隻自己改過的還有 tools 與 llm 覆蓋層（只存差異；路徑依 `interfaces.json` 的同名欄位，此範本是 `tools.json`、`llm.json`，11-06 K-6）（`aos-agent tools`／`llm`；`aos-agent llm --target myproj set model=haiku`＝下一題起 `--model haiku`，`reset` 回定義的 sonnet）。換定義的模型＝`aos-json set --str proto8/templates/eca-claude/llm.json#/model opus`。eca 的腦是 CLI 自己，不經 llm kernel（think-as-function 03 § 2）。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-post／aos-daemon、proto8/cmd/*/bin 的 aos-eca-turn、aos-eca-screen、aos-tools、aos-daemon-ctl、
# aos-mcp、aos-agent（跑過 proto8/install.sh 就都在），還有 claude；AOS_DAEMON＝跑著的 daemon 的 $AOS_STACK
aos-agent ctl add --ws ~/code/myproj --name myproj proto8/templates/eca-claude
aos-agent say --target myproj 看一下 README 在講什麼 && aos-agent listen --target myproj
aos-agent ctl pause --target myproj  # 暫停：不餵下一則（新信留 queue/new/），粒度＝一則訊息
aos-agent open --target myproj       # 接上畫面（Ctrl-] 跳出）
aos-agent ctl rm myproj              # 拔掉、stack 留著（加 --purge 才連 stack 刪）
```

不掛 daemon、直接 `aos-exec --ws ~/code/myproj proto8/templates/eca-claude &` 跑的，aos-agent 不管：`aos-post send --ordered ~/code/myproj/.stack/queue` 寫信（stdin＝`{"role": "user", "content": 話}`）、看 `.stack/history.jsonl`、寫 `.stack/ctl.json` 停（`{"cmd": "pause"}`／`{"cmd": "stop"}`）。

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [cmd/docs/01](../../cmd/docs/01-逐支說明.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就放一份檔、aos-eca-turn 加 `--prompt 那個檔`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。**goal**（11-11 [thinking goal](../../thinking/2026-11/11/goal/README.md)）：queue 空、上一輪 CLI 答完了、`$AOS_STACK/goal.json` 是 active＝這輪的題目換成一則 `[aos] goal: …`（射後不理版也一樣：有 active 的 goal 就不收工）；這輪 CLI 自己的對話檔（`transcripts/`）裡叫了 `goal` 以外的工具＝計數歸零，連續 LIMIT 次（預設 10）沒進展＝goal 改 paused；codex 照同一套。

**history 被改過＝開新對話**（11-10 [self-family](../../thinking/2026-11/10/self-family/README.md) ⑩，解 10-30 eca 09「停著時改 history 再繼續」縮水版）：每輪 assistant 接進 history 後，把整份 history 的 sha256 寫進小格的 `.history_sum`；下一輪交出去前算出來不一樣（人用 `aos-agent history` 或直接改了）＝`drop_session`、開新的 claude 對話，題目前面照換台那套帶改過的 user／assistant 紀錄（上限 `reseed_bytes`），stderr 一行 `warning: history.jsonl was changed since the last turn; starting a new claude conversation that carries the changed record`。這一輪中間被改（claude 叫 `self_history`）＝`.history_sum` 寫 `edited`、下一輪照樣開新的。畫面開著時不換、只 warning。用法：`aos-agent history -t 名字 ls`、`rm 3-4`、`summarize 1-6 "…"`；原文搬到 stack 裡 `history_removed.jsonl`。

**slash 指令**（11-12 [eca-slash](../../thinking/2026-11/12/eca-slash.md)，使用者「eca就是會變成以他為主，aos體系要盡量跟上」）：畫面上打的照 CLI 自己的做，aos 跟上——對話 id 換了（`/clear`、`/resume`、codex 的 `/new`）畫面 hook 就改記 `session.txt`，`/clear` 連 history 一起清（claude 看 SessionStart source clear；codex 看換到的 thread 是不是剛開的——rollout 只有這一輪＝清、剛交出去的 user 留著，有舊輪數＝`/resume` 到別段、只跟 id）；claude 的 `/compact` 同一個 id、history 換成它的摘要一則（`[aos] summary: …`；原文都搬到 `history_removed.jsonl`）；codex 的 `/compact` 不給摘要文字，改成從它壓縮後留下的 `replacement_history` 撈出 user／assistant 的話（工具定義、developer 訊息、工具呼叫、它自己塞的 `<environment_context>` 這類都略過）當新 history，前面一則 `[aos] summary: … codex compacted …`；畫面上打的在下一輪看到 rollout 多一個 `compacted` 時補做（`.compact_seen` 記已跟上幾次），撈不到就不動；`/exit` 畫面關掉，下一句照常（非互動）答。`aos-agent say`／`chat` 送一封剛好是 `/clear`、`/compact`、`/status`、`/usage`、`/exit` 的信＝aos-eca-turn ⑭ 做出同樣的效果、回一則 `[aos] slash: …`；畫面開著時 `/clear`、`/compact` 直接打進畫面（正在答題就等下一輪）。`/goal …`（以 `/goal` 開頭就算，含 `/goal clear`、只打 `/goal` 查看）是 CLI 自己的 goal，跟 aos 的 `goal.json` 各管各的：畫面開著打進去；沒開＝claude 原樣交給它（`claude -p` 認得，但目標只活在那一次 `claude -p` 裡），codex exec 沒有 `/goal`、回一句請開畫面；`/status` 多一行 CLI 最後記下的 goal；經 aos 打進 codex 畫面的 `/goal 新目標` 若跳「Replace goal?」選單（已有 goal），aos 自動選「1. Replace current goal」，選單認不得就不按、回一句請人處理（人自己在畫面上打的不代按）。codex 身也有畫面（同一個 `screen/`，11-12 實測 `aos-agent open` 開得起來、answer 照進 turns／history）。


**eca 的 hook：有哪些、沒有哪些**（11-10 晚 [hook 圖紙 § 6](../../thinking/2026-11/10/self-family/hook/01-圖紙.md#6-eca-縮水版)，使用者「7.接受」縮水版）：腦在外面的 CLI，aos 只攔得到經過自己手的東西。

| 事件 | eca 有沒有 | 在哪 |
|---|---|---|
| `before_queue`（可改 content、可丟信）／`after_queue` | 有 | aos-eca-turn：讀出好信、交給 CLI 之前／信接進 history 之後 |
| `before_tool`（可改 arguments、可攔）／`after_tool`（可改結果） | 只有經 aos-mcp 叫的 aos 工具 | aos-mcp 的 tools/call（cli_session 起它時帶 `--hooks <定義>`） |
| `brain_failed` | 有（`name`＝`CliFailed`／`ReplyMissing`，交出去之後才算） | aos-eca-turn |
| `tool_added` | 有（看這隻生效的 aos 登記檔，交出去之前比一次） | aos-eca-turn |
| `after_start`／`after_stop`（11-11） | 有 | loop.json 的 `on_start`／`on_stop` → `lib/agent/hook_fire` |
| `on_clock`（11-11，[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)） | 有（每輪最開頭判，冷卻中、退讓的那輪也判；到了才起 handler） | aos-eca-turn |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos |

hook 停下＝`aos-eca-turn: error: HookFailed …` 退 1：交出去之前停的，信留在 `queue/cur/`、history 不動，修好照問；aos-mcp 裡停的＝那次工具呼叫回錯（isError）給 CLI，不整支死。

**長跑怎麼調**：`cli.json` 的 `print_flags` 預設 `--max-budget-usd 0.5`，是每次非互動 CLI 呼叫的美元上限；任務常因額度不足停下時再提高，想限制單次成本就降低。`cli.json.timeout_ms` 預設 600000（10 分鐘），限制 CLI 呼叫；`loop.json.exec.timeout_ms` 預設 900000（15 分鐘），限制整次 aos-eca-turn，要留得比 CLI 那層長，讓它有時間收尾。長任務要同時檢查這兩層，增加額度不會延長逾時。`loop.json.interval_ms` 預設 300，是每輪結束後等多久再看 queue；調大可減少空轉、但收信會較慢，調小則較快回應，不會增加同時跑的輪數。

## 子 agent 與 skill（11-12 晚 eca-task-subagent）

使用者 11-12 晚：「claude code cli自己本身有Task工具，可以的話幫我加入claude eca範本和定義中(Skill也加上)」「將aos mcp切成幾個，一個是給主agent用的，另一個是比較少功能的，給子agent用的」。調查、實測與代定在 [thinking 11-12 eca-task-subagent](../../thinking/2026-11/12/eca-task-subagent.md)。

- **開法**：`cli.json` 的 `--tools` 列 `Agent`（子 agent 工具；2.1.63 前叫 `Task`，舊名還認）與 `Skill`。dontAsk 下這兩支不必進 `--allowedTools`；子 agent 的權限照主對話的（Write、Edit、Bash、`mcp__aos…` 照白名單，其他照拒）。
- **不切的話**：claude 的子 agent 繼承主對話全部 MCP 工具，`mcp__aos__*` 整台都叫得到（含 self_ctl、mailbox_send 這類）。
- **切（`tools_sub`）**：`cli.json` 寫 `"tools_sub": "<登記檔>"`（寫法同 `tools`：相對從 `cli.json` 的資料夾算，也可寫指示詞；不是檔＝`ToolsMissing`）。cli_session 起 claude 時多帶三樣：
  1. `--agents`：蓋掉內建的 `general-purpose`——`disallowedTools: ["mcp__aos"]`（看不到主 agent 那台）、`mcpServers` 內嵌 `aos_sub`（`aos-mcp --ws <工作區> --stack <stack> [--hooks <定義>] [tools_flags…] <tools_sub 那份>`；只有這個子 agent 連得到，主對話的清單沒有它）。內建工具照繼承。
  2. `--allowedTools` 多 `mcp__aos_sub`（整台免問）。
  3. `--settings` 的 PreToolUse hook（matcher `mcp__aos__.*`，`cli_session.py guard`）：別的類型的子 agent（Explore、Plan、外掛帶的、使用者自己定義的）還看得到 `mcp__aos__*`，但 hook 輸入帶 `agent_id`＝子 agent 叫的＝擋下、回一句說明；主對話叫的不受影響。
- **子 agent 那台放什麼**（代定、可翻案）：只放 `_metainfo.side_effect` 是 false 而且講的不是「這隻 agent 自己」的——peek_clock、peek_now_time、math、json_get、json_ls、json_search、json_multi_get、index_view 八支。不放：會改東西的 json_set／add／del／multi_set、self 一族、events、def、mailbox 三支（信箱是主 agent 的）。要加減＝改定義的 `tools_sub.json`。
- **不跟著變的**：這隻自己用 `self_tools` 加減的工具只進主 agent 那台（`aos_sub` 不帶 `--own`）；`aos-agent tools` 也只管主 agent 那份。外部 MCP server（`mcp_servers`）照 CLI 預設，子 agent 一樣繼承。
- **限制**：只有 claude 身（codex 寫了＝`CfgBad`）；`flags` 裡自己寫了 `--agents` 又寫 `tools_sub`＝`CfgBad`。子 agent 是 CLI 的黑盒子：它叫 `mcp__aos_sub__*` 照樣過 aos-mcp 的 `before_tool`／`after_tool` hook，其餘 aos 看不到。
- **skill**：claude 自己從工作區 `.claude/skills/`、帳號的 `~/.claude/skills/` 與外掛找；主對話與子 agent 都能用 `Skill` 叫（haiku 實測）。aos 不管 skill 放哪。

## 接外部 MCP server（11-12 external-mcp）

定義資料夾放一份 **server 檔**（一台一份，例 `mcp/teamsite.json`），`cli.json` 加 `"mcp_servers": ["mcp/teamsite.json"]`（相對從 `cli.json` 的資料夾算，也可寫指示詞；可列好幾份）。claude、codex 兩身都吃；CLI 自己連、自己列工具（不凍結說明），列了的那台整台免核准，`only`／`except` 挑工具。某一份壞了＝`cli_session: warning: external MCP server … skipped: …`，其他照接。設計：[external-mcp 02](../../thinking/2026-11/12/external-mcp/02-設計.md)；程式：`lib/mcp_server_file.py`、`cmd/aos-mcp-launch`。

**http（Bearer＋自簽 CA）**：

```json
{"description": "<一句話：這台是什麼>",
 "mcp_server": {"name": "<名字，小寫英數底線>", "transport": "http", "url": "https://<主機>:<埠>/mcp",
                "bearer_token_env": "<放 token 的變數名，例 TEAMSITE_TOKEN>",
                "env_file": "<token 檔的絕對路徑，例 /home/<你>/.config/<agent>/teamsite.env>",
                "ca_file": "<CA bundle 的絕對路徑（選填）>"}}
```

token 檔一行 `TEAMSITE_TOKEN=<值>`、權限 600，放定義與工作區以外。起 CLI 那一刻才讀：codex＝值只放進 codex 行程的環境、自動補 `shell_environment_policy.exclude`（腦的 shell 看不到）；claude＝走 `headersHelper`（值不進 claude 的環境）。`ca_file`＝codex 的 `SSL_CERT_FILE`／`CODEX_CA_CERTIFICATE`、claude 的 `NODE_EXTRA_CA_CERTS`。

**stdio**（經 `aos-mcp-launch` 起，`env_file` 整份只進 server 行程）：

```json
{"description": "<一句話>",
 "mcp_server": {"name": "<名字>", "transport": "stdio", "command": "<指令>", "args": ["<參數>"],
                "env": {"<明文變數>": "<值>"}, "env_file": "<金鑰檔的絕對路徑（選填）>", "only": ["<工具名>"]}}
```

腦看到的工具名＝`mcp__<名字>__<工具名>`。**秘密不要用 `aos-agent ctl add --envs` 給**（值明文寫進 `procs/<名>/exec.json`）。`aos-mcp-launch` 要在 PATH（`proto8/install.sh` 重跑一次）。
