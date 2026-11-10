← [回入口 README.md](../README.md)｜段落：外部 coding agent 範本（eca-claude）｜上一份：—｜下一份：[02-agent-fsm](02-agent-fsm.md)

## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../../cmd/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。CLI 對話共用 [lib/agent/cli_session.py](../../lib/agent/cli_session.py)，介面宣告共用 [lib/agent/agent_files.py](../../lib/agent/agent_files.py)（11-06 晚 K-5）；兩者都在 `lib`，不 import 上層 `py`。設計：[thinking 2026-10-30 eca](../../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 照 lib/agent/codex 改。）

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；三扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標（--model 不寫在這，見 llm.json）；
              tools_flags ["--memory", "memory_read"]＝aos-mcp 在 MCP initialize 的 instructions 給知識庫根（Claude Code 放進它的 system prompt；11-05 晚）
  llm.json    腦設定：{"model": "sonnet"}（11-04 晚；cli_session 每題依 interfaces.json 的 llm 宣告讀定義並疊 stack 下同一相對路徑的覆蓋層，補成 --model）；只認 model（claude CLI 沒有 temperature 等取樣旗標，與快取無關的調整鍵這邊沒有對應，11-10 晚）
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔11-04 起，相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
  tools.json  aos-tools 的登記檔：`"$override"` 一串 [lib/packs](../../lib/packs/README.md) 十一包（通用四包 look、change、delete、shell，加 gadgets、events、self、children、def、mailbox、memory，共 34 支；11-10 深夜使用者「1.算了，把各種東西也一起掛回eca。」，翻掉稍早「對於eca，其實那些基礎工具就不用了」），自己只寫 memory_read、memory_write 兩格的 `env.AOS_MEMORY`（指 `knowledge/`）；
              cli.json 沒寫 tools＝照 interfaces.json 的 tools 宣告用它，cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__peek_now_time…；帶 `--own <stack>/tools.json`，self_tools 加減工具後 aos-mcp 送 list_changed，同一輪就叫得到，11-10 深夜「3.同一輪就生效」）；不要工具就刪掉它
  children.json 工具 agents_children 的配額設定：{"max_children": 4}（這隻最多同時生幾隻；這隻的 stack 裡放一份 children.json 只寫改過的鍵＝覆蓋；誰是我生的另記在 stack 的 tools/agents_children/children.json）
  interfaces.json  {"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json", "llm_keys": ["model"], "history": "history.jsonl", "hooks": "hooks.json"}}（11-04；hooks 鍵 11-10 晚加；history 鍵 11-10 加，給 aos-agent history 找檔；llm_keys 11-10 晚加，aos-agent llm set 不在上面的鍵照存＋warning；aos-agent ctl add 只看這個宣告）
  hooks.json  hook 清單（11-10 晚，空的 {"hooks": {}}；stack 那份同名蓋過、null 關掉；`aos-agent hook` 管，見下「eca 的 hook」）
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

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [cmd/docs/01](../../cmd/docs/01-逐支說明.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就放一份檔、aos-eca-turn 加 `--prompt 那個檔`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。

**history 被改過＝開新對話**（11-10 [self-family](../../thinking/2026-11/10/self-family/README.md) ⑩，解 10-30 eca 09「停著時改 history 再繼續」縮水版）：每輪 assistant 接進 history 後，把整份 history 的 sha256 寫進小格的 `.history_sum`；下一輪交出去前算出來不一樣（人用 `aos-agent history` 或直接改了）＝`drop_session`、開新的 claude 對話，題目前面照換台那套帶改過的 user／assistant 紀錄（上限 `reseed_bytes`），stderr 一行 `warning: history.jsonl was changed since the last turn; starting a new claude conversation that carries the changed record`。這一輪中間被改（claude 叫 `self_history`）＝`.history_sum` 寫 `edited`、下一輪照樣開新的。畫面開著時不換、只 warning。用法：`aos-agent history -t 名字 ls`、`rm 3-4`、`summarize 1-6 "…"`；原文搬到 stack 裡 `history_removed.jsonl`。


**eca 的 hook：有哪些、沒有哪些**（11-10 晚 [hook 圖紙 § 6](../../thinking/2026-11/10/self-family/hook/01-圖紙.md#6-eca-縮水版)，使用者「7.接受」縮水版）：腦在外面的 CLI，aos 只攔得到經過自己手的東西。

| 事件 | eca 有沒有 | 在哪 |
|---|---|---|
| `before_queue`（可改 content、可丟信）／`after_queue` | 有 | aos-eca-turn：讀出好信、交給 CLI 之前／信接進 history 之後 |
| `before_tool`（可改 arguments、可攔）／`after_tool`（可改結果） | 只有經 aos-mcp 叫的 aos 工具 | aos-mcp 的 tools/call（cli_session 起它時帶 `--hooks <定義>`） |
| `brain_failed` | 有（`name`＝`CliFailed`／`ReplyMissing`，交出去之後才算） | aos-eca-turn |
| `tool_added` | 有（看這隻生效的 aos 登記檔，交出去之前比一次） | aos-eca-turn |
| CLI 自帶工具（Read、Bash…）、人在畫面上自己打的話 | 沒有 | 沒經過 aos |

hook 停下＝`aos-eca-turn: error: HookFailed …` 退 1：交出去之前停的，信留在 `queue/cur/`、history 不動，修好照問；aos-mcp 裡停的＝那次工具呼叫回錯（isError）給 CLI，不整支死。

**長跑怎麼調**：`cli.json` 的 `print_flags` 預設 `--max-budget-usd 0.5`，是每次非互動 CLI 呼叫的美元上限；任務常因額度不足停下時再提高，想限制單次成本就降低。`cli.json.timeout_ms` 預設 600000（10 分鐘），限制 CLI 呼叫；`loop.json.exec.timeout_ms` 預設 900000（15 分鐘），限制整次 aos-eca-turn，要留得比 CLI 那層長，讓它有時間收尾。長任務要同時檢查這兩層，增加額度不會延長逾時。`loop.json.interval_ms` 預設 300，是每輪結束後等多久再看 queue；調大可減少空轉、但收信會較慢，調小則較快回應，不會增加同時跑的輪數。

**知識寫入**：範本預設登記 `memory_read` 與 `memory_write`（11-10 深夜 tool-packs），兩格 `env.AOS_MEMORY` 都指 `{"$env": "AOS_HOME", "$path": "/knowledge"}`＝repo 的 `knowledge/`（使用者「指knowledge/」）：claude 經 aos-mcp 寫了就改到它。要寫自己的庫就改兩格的值，或 `aos-agent tools add --replace --envs AOS_MEMORY=…`，寫法見範本 README。兩支透過 aos-mcp 提供給 Claude，`cli.json` 的內建 `--tools Read,Glob,Grep` 不必改；工具沒被指定庫（`MemoryMissing`）時 aos-mcp 安靜不給 instructions。agent 寫前先讀 `aos/memory.json`。
