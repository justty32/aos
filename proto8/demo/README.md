# proto8/demo — 兩個 agent 範本：eca-claude（外部 coding agent）與 agent-fsm（aos 自己的 loop／fsm agent）

← [proto8](../README.md)｜程式：[impls](../impls/README.md)（aos-exec、aos-loop…，C++）、[bin/README](../bin/README.md)（aos-eca-turn、aos-tools…）、[extras/eca](../extras/eca/README.md)（aos-eca）｜慣例：[CONVENTION](../docs/CONVENTION.md)

<a id="agent-danagent-dan-q11-02-晚刪了"></a>
<a id="agent-eveagent-當工具10-24"></a>
<a id="agent-meg記憶庫10-24"></a>
<a id="talkagent-之間寄信10-24"></a>
<a id="agent-gus小念頭10-24"></a>
使用者 11-04：「demo中的，用不到的全部刪掉，也不用封存了。」所以這裡只留 `eca-claude`（[aos-eca](../extras/eca/README.md) `add` 的預設範本）；同一天又加了 [`agent-fsm`](#agent-fsm)（使用者「接下來是弄aos loop/fsm agent了」）。兩個範本對外同形（`_entry`＝aos-loop、queue／history／ctl／state、同一份 `tools.json`、`--prompt` 開場白），對照表在 [thinking 11-04 loop-fsm-agent 02](../thinking/2026-11/04/loop-fsm-agent/02-跟-eca-對照.md)。其餘範例（agent-ann、agent-bob、agent-eve、agent-gus、agent-hal、agent-kai、agent-liv、agent-meg、agent-pip、daemon、daemon-2、daemon-3、tick、talk、eca-codex）與 `run.sh` 都刪了、沒封存；測試還要用的 agent-bob、agent-ann、agent-eve、tick 搬到 `proto8/tests/fixtures/` 當測試的固定資料（說明在 [code map 02-tests](../../wf/workflows/common/code-map/proto8/02-tests.md)）。

**PATH 由呼叫的人放**：aos 的程式都不動 PATH（ideas § 24，使用者「也套用，都不動path吧」），定義裡寫的 `aos-loop`、`aos-exec`、`aos-eca-turn` 要呼叫端事先放進 PATH：C++ 的 `proto8/impls/<名>/bin/`（要先建，見 [testing](../../wf/workflows/testing.md#proto8不在-ctest-裡)）與 Python 的 `proto8/bin/`；`proto8/tests/aos_bins.py` 就是這樣放的。

<a id="eca-templates"></a>
## 外部 coding agent 範本（eca-claude）

claude code／codex **整隻當成一隻平級的 agent**（不是腦、不是工具）：包成跟 aos agent 同形的定義資料夾，`loop.json` 直接叫 [`aos-eca-turn`](../bin/README.md)，aos 只碰它 stack 裡的 queue／history／ctl（P-42）。設計：[thinking 2026-10-30 eca](../thinking/2026-10/30/eca/README.md)；條文草稿 P-43。（codex 版 eca-codex 11-04 刪了：只差 `cli.json`，要就複製一份、`cli.json` 照 lib/agent/codex 改。）

```
eca-claude/
  _entry      ["aos-loop", "loop.json"]（JSON 入口）
  loop.json   {"exec": {"argv": ["aos-eca-turn", "--on-empty", "idle", "--on-busy", "yield", {"$env": "AOS_CD"}], "timeout_ms": 900000},
               "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（停著等版：沒有 max；queue 空就退 0、loop 隔 300 毫秒再來；兩扇窗落在 $AOS_STACK）
  cli.json    怎麼叫 CLI（kind、flags、print_flags、timeout_ms），抄 lib/agent/claude 的保守旗標
  （開場白：範本沒有；要就放一份檔、loop.json 的 aos-eca-turn 加 "--prompt", "prompt.txt"〔11-04 起，相對路徑從這個資料夾算〕，
              history 與 queue 都空時當第一則 user 投進 queue；沒給旗標就沒有，不自己找 prompt.txt）
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

`aos-eca-turn` 一次答一批（怎麼答、`--on-empty`／`--on-busy`、錯見 [bin/README](../bin/README.md)）。人在畫面上自己打的話不進 history，完整對話看小格的 `transcripts/`。**射後不理**：複製一份，`loop.json` 的 `--on-empty idle` 改 `stop`（或拿掉，沒給＝stop；要開場白就放一份檔、aos-eca-turn 加 `--prompt 那個檔`）——queue 空 aos-eca-turn 退 10、loop 以 0 收工。CLI 那層出錯＝aos-eca-turn 退 1、loop 停下等人（信留 `cur/`）。測試 `test_eca.py`（範本）、`test_eca_turn.py`（aos-eca-turn）。

<a id="agent-fsm"></a>
## loop／fsm agent 範本 agent-fsm（11-04）

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `.env`／`system.txt`／`tools.json` 就是另一隻（三支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`_entry` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；格是範本裡三支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../thinking/2026-11/04/loop-fsm-agent/README.md)；條文 P-11、P-19、P-35 的 11-04 註。

```
agent-fsm/
  _entry       ["aos-loop", "loop.json"]（JSON 入口，沒 +x）
  loop.json    {"exec": "fsm.json", "interval_ms": 300, "ctl": "ctl.json", "state": "state.json"}（沒有 max：常駐，靠 ctl 的 stop 收工）
  fsm.json     三格：idle {"0": "think", "10": "idle"}、think（brain.py --system system.txt）{"0": "act", "10": "idle"}、act → "think"
  idle.py      收信：$AOS_STACK/queue/ 全部收進 history.jsonl（接進去就 aos-post done）；有好信退 0、沒有退 10；[--prompt FILE] 開場白
  brain.py     問腦：history（＋system、tools）→ OpenAI 相容端點，回覆接一則 assistant；有 tool_calls 退 0、沒有（答完了）退 10
  act.py       跑工具：最後一則 assistant 的 tool_calls 逐個 aos-tools call，結果各接一則 tool；退 0
  system.txt   system 訊息（brain.py 的 --system 指到它；每次從檔讀、不存進 history）
  tools.json   aos-tools 登記檔，只登記 clock（"../../lib/base/clock"；跟 eca-claude 同一份寫法）
  .env         AOS_BRAIN_MODEL=chatgpt-gpt-6-luna-low（不蓋外面已設的）
```

**腦**：`AOS_BRAIN_URL` 沒設＝假腦（有工具就先叫第一個、再答一句「FAKE ANSWER to: …」，不碰網路）；設了＝問 `{AOS_BRAIN_URL}/chat/completions`，`AOS_BRAIN_KEY` 有才帶 Bearer（P-23）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp），工具小格 `$AOS_STACK/tools/<名>/`；工具退非 0、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-fsm／aos-post、proto8/bin 的 aos-tools（真腦再設 AOS_BRAIN_URL）
aos-exec --ws ~/proj proto8/demo/agent-fsm &              # 直接跑：stack＝~/proj/.stack/
aos-say --ws ~/proj 現在幾點 && aos-listen --ws ~/proj
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

aos-daemon-ctl add --ws ~/proj --name fsm1 proto8/demo/agent-fsm   # 掛 daemon（有 loop.json＝loop 型；daemon 的環境要有上面的 PATH）
S=$(aos-daemon-ctl where --stack fsm1)
aos-say --stack $S 現在幾點 && aos-listen --stack $S
aos-daemon-ctl pause fsm1    # 停在格與格之間；新信留 queue/new/
aos-daemon-ctl resume fsm1   # 也有 stop／start（同一個 stack 接著對話）、rm
```

- **停著等 vs 射後不理**寫在表上：範本 idle 的 `next` 接住 10＝queue 空就停著等（loop 隔 `interval_ms` 再看）。射後不理＝複製一份，idle 的 `next` 改成字串 `"think"`（10 到 loop＝收工）、`loop.json` 拿掉 `interval_ms`；要開場白就在 idle 的 argv 加 `"--prompt", "prompt.txt"`（相對這個資料夾；history 空、queue 沒好信時投一次）。
- **思考中來的信**留在 `queue/new/`，答完回 idle 才收、跟那批一起答（使用者 11-04「等答完回 idle 再收」）。
- **暫停時改 history**：`pause` 之後改 `history.jsonl`（例：刪掉最後一則答案），要它重答就把 `stage.txt` 寫成 `think` 再 `resume`；brain 每次從頭讀，改了就生效。最後一則已是答案時 brain 不問腦、退 10 回 idle。
- **錯**：stderr 一行 `agent-fsm: 代號 原因`、退 1、loop 停下等人（P-20）——`BrainFailed`、`ReplyBad`、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起（`aos-exec` 同一個工作區、或 daemon `start`）從停的那格接著做。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。
- 掛 daemon 卻沒給 `AOS_BRAIN_URL`＝假腦照跑（daemon 的環境或範本 `.env` 要給）。

## 測試

`python3 -m unittest discover -s proto8/tests`（先建 impls）：`test_agent_fsm.py`（agent-fsm：13 案，假腦與本機假端點、掛 daemon）、`test_eca.py`（這份範本；codex 版由它複製再換 `cli.json`）、`test_eca_turn.py`（aos-eca-turn）、`test_eca_cmd.py`（aos-eca）。
