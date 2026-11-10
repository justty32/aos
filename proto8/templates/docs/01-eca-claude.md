← [回入口 README.md](../README.md)｜段落：外部 coding agent 範本（eca-claude）｜上一份：—｜下一份：[02-agent-fsm](02-agent-fsm.md)

## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../../cmd/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。CLI 對話共用 [lib/agent/cli_session.py](../../lib/agent/cli_session.py)，介面宣告共用 [lib/agent/agent_files.py](../../lib/agent/agent_files.py)（11-06 晚 K-5）；兩者都在 `lib`，不 import 上層 `py`。設計：[thinking 2026-10-30 eca](../../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 照 lib/agent/codex 改。）

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；三扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標（--model 不寫在這，見 llm.json）；
              tools_flags ["--memory", "memory"]＝aos-mcp 在 MCP initialize 的 instructions 給知識庫根（Claude Code 放進它的 system prompt；11-05 晚）
  llm.json    腦設定：{"model": "sonnet"}（11-04 晚；cli_session 每題依 interfaces.json 的 llm 宣告讀定義並疊 stack 下同一相對路徑的覆蓋層，補成 --model）
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔11-04 起，相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
  tools.json  aos-tools 的登記檔：wall_clock、self_tools、self_llm、agents、memory（跟 agent-fsm 同一份：都寫 `{"$env": "AOS_HOME", …}`，memory 直接登記 lib/agent/memory、`env.AOS_MEMORY` 指知識庫；後兩個 11-05 使用者裁「內建」）；
              cli.json 沒寫 tools＝照 interfaces.json 的 tools 宣告用它，cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__wall_clock…）；不要工具就刪掉它
  agents.json 工具 agents 的設定：{"max_children": 4}（這隻最多同時生幾隻；這隻的 stack 裡放一份 agents.json 只寫改過的鍵＝覆蓋）
  interfaces.json  {"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json"}}（11-04；aos-agent ctl add 只看這個宣告）
  screen/     子介面：_entry＝["aos-eca-screen", "--eca", ".."]（aos-agent open／close／watch 叫它；動作接在最後）
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


**長跑怎麼調**：`cli.json` 的 `print_flags` 預設 `--max-budget-usd 0.5`，是每次非互動 CLI 呼叫的美元上限；任務常因額度不足停下時再提高，想限制單次成本就降低。`cli.json.timeout_ms` 預設 600000（10 分鐘），限制 CLI 呼叫；`loop.json.exec.timeout_ms` 預設 900000（15 分鐘），限制整次 aos-eca-turn，要留得比 CLI 那層長，讓它有時間收尾。長任務要同時檢查這兩層，增加額度不會延長逾時。`loop.json.interval_ms` 預設 300，是每輪結束後等多久再看 queue；調大可減少空轉、但收信會較慢，調小則較快回應，不會增加同時跑的輪數。

**知識寫入**：範本不預先登記 `memory_write`；先把 `memory` 那格的 `env.AOS_MEMORY` 指到有權寫的庫（相對、絕對或 `{"$env": "MY_KNOWLEDGE"}`），再在定義的 `tools.json` 照同樣寫法加 `memory_write` 一格（`env` 給同一個 `AOS_MEMORY`，寫法見 [02-agent-fsm](02-agent-fsm.md)「長跑與知識寫入」）。它與 `memory` 看同一個庫，透過 aos-mcp 提供給 Claude，`cli.json` 的內建 `--tools Read,Glob,Grep` 不必改。出廠庫由人維護；agent 寫前先讀出廠庫的 `memory.json`。
