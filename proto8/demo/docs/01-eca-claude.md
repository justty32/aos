← [回入口 README.md](../README.md)｜段落：外部 coding agent 範本（eca-claude）｜上一份：—｜下一份：[02-agent-fsm](02-agent-fsm.md)

## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../../bin/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。設計：[thinking 2026-10-30 eca](../../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 照 lib/agent/codex 改。）

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；兩扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標（--model 不寫在這，見 llm.json）
  llm.json    腦設定：{"model": "sonnet"}（11-04 晚；cli_session 每題讀它疊 $AOS_STACK/llm.json 副本，補成 --model）
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔11-04 起，相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
  tools.json  aos-tools 的登記檔，只登記 clock（"../../lib/base/clock"，相對路徑從這份檔的資料夾算）；cli.json 沒寫 tools＝用它，
              cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__clock）；不要工具就刪掉它
  interfaces.json  {"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json"}}（11-04；aos-agent add 只看這個宣告）
  screen/     子介面：_entry＝["aos-eca-screen", ".."]（aos-agent open／close／watch 叫它）
```

**實例＝定義 × 工作區**：工作區＝CLI 的 cwd（你的程式專案）；stack 預設 `<工作區>/.stack/`（掛 daemon 的在 daemon 給的小格），裡面長 `queue/`、`history.jsonl`、`ctl.json`、`state.json` 與 cli_session 的小格 `claude/`（`session.txt`、`transcripts/`…）；`eca.json` 11-04 起不寫（沒人讀）。改過副本的還有 `tools.json`、`llm.json`（`aos-agent tools`／`llm`；`aos-agent llm --target myproj set model=haiku`＝下一題起 `--model haiku`，`reset` 回定義的 sonnet）。換定義的模型＝`aos-json set --str proto8/demo/eca-claude/llm.json#/model opus`。eca 的腦是 CLI 自己，不經 llm kernel（think-as-function 03 § 2）。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-post／aos-daemon、proto8/bin 的 aos-eca-turn、aos-eca-screen、aos-tools 與 aos-daemon-ctl、
# extras/ai_tools/bin 的 aos-mcp、extras/agent/bin 的 aos-agent、claude；AOS_DAEMON＝跑著的 daemon 的 $AOS_STACK
aos-agent add --ws ~/code/myproj --name myproj proto8/demo/eca-claude
aos-agent say --target myproj 看一下 README 在講什麼 && aos-agent listen --target myproj
aos-agent pause --target myproj      # 暫停：不餵下一則（新信留 queue/new/），粒度＝一則訊息
aos-agent open --target myproj       # 接上畫面（Ctrl-] 跳出）
aos-agent rm myproj                  # 拔掉並刪它的 stack
```

不掛 daemon、直接 `aos-exec --ws ~/code/myproj proto8/demo/eca-claude &` 跑的，aos-agent 不管：`aos-post send --ordered ~/code/myproj/.stack/queue` 寫信（stdin＝`{"role": "user", "content": 話}`）、看 `.stack/history.jsonl`、寫 `.stack/ctl.json` 停（`{"cmd": "pause"}`／`{"cmd": "stop"}`）。

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [bin/README](../../bin/README.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就放一份檔、aos-eca-turn 加 `--prompt 那個檔`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。

