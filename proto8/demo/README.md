# proto8/demo — 外部 coding agent 範本 eca-claude

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[bin/README](../bin/README.md)（aos-eca-turn、aos-tools…）、[extras/eca](../extras/eca/README.md)（aos-eca）｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
使用者 11-04：「demo中的，用不到的全部刪掉，也不用封存了。」所以這裡只留 `eca-claude`（[aos-eca](../extras/eca/README.md) `add` 的預設範本）。其餘範例（agent-ann、agent-bob、agent-eve、agent-gus、agent-hal、agent-kai、agent-liv、agent-meg、agent-pip、daemon、daemon-2、daemon-3、tick、talk、eca-codex）與 `run.sh` 都刪了、沒封存；測試還要用的 agent-bob、agent-ann、agent-eve、tick 搬到 `proto8/tests/fixtures/` 當測試的固定資料（說明在 [code map 02-tests](../../wf/workflows/common/code-map/proto8/02-tests.md)）。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)）與 Python 的 `proto8/bin/`；`proto8/tests/aos_bins.py` 就是這樣放的。

<a id="eca-templates"></a>
## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../bin/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。設計：[thinking 2026-10-30 eca](../thinking/2026-10-30-eca.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 照 lib/agent/codex 改。）

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；兩扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標
  prompt.txt  （選填，範本沒有）開場白：history 與 queue 都空時當第一則 user 投進 queue
  tools.json  aos-tools 的登記檔，只登記 clock（"../../lib/base/clock"，相對路徑從這份檔的資料夾算）；cli.json 沒寫 tools＝用它，
              cli_session 起 CLI 前接上 aos-mcp（工具名 mcp__aos__clock）；不要工具就刪掉它
```

**實例＝定義 × 工作區**：工作區＝CLI 的 cwd（你的程式專案）；stack 預設 `<工作區>/.stack/`，裡面長 `queue/`、`history.jsonl`、`ctl.json`、`state.json`、`eca.json`（kind、ws、template）與 cli_session 的小格 `claude/`（`session.txt`、`transcripts/`…）。

```sh
aos-exec --ws ~/code/myproj proto8/demo/eca-claude &     # PATH 要有 impls 的 aos-exec／aos-loop／aos-post、proto8/bin 的 aos-eca-turn 與 aos-tools、extras/ai_tools/bin 的 aos-mcp、claude
aos-say --ws ~/code/myproj 看一下 README 在講什麼 && aos-listen --ws ~/code/myproj
echo '{"cmd": "pause"}' > ~/code/myproj/.stack/ctl.json      # 暫停：不餵下一則（新信留 queue/new/），粒度＝一則訊息
echo '{"cmd": "stop"}' > ~/code/myproj/.stack/ctl.json       # 收工
```

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [bin/README](../bin/README.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就在定義放 `prompt.txt`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。測試 `test_eca.py`（範本）、`test_eca_turn.py`（aos-eca-turn）。

## 測試

`python3 -m unittest discover -s proto8/tests`（先建 impls）：`test_eca.py`（這份範本；codex 版由它複製再換 `cli.json`）、`test_eca_turn.py`（aos-eca-turn）、`test_eca_cmd.py`（aos-eca）。
