← [回入口 README.md](../README.md)｜段落：loop／fsm agent 範本 agent-fsm（11-04）｜上一份：[01-eca-claude](01-eca-claude.md)｜下一份：—

## loop／fsm agent 範本 agent-fsm（11-04）

aos 體系自己的 agent：**一隻＝一個範本資料夾**，複製一份、改 `.env`／`system.txt`／`tools.json` 就是另一隻（三支格的程式也放在範本裡，每隻複製；使用者 11-04「放範本裡，每隻複製」）。`_entry` 讓 aos-loop 跑 `loop.json`，loop 每次跑 `fsm.json` 的一格；格是範本裡三支純標準庫的 Python。設計與代定：[thinking 11-04 loop-fsm-agent](../../thinking/2026-11/04/loop-fsm-agent/README.md)；條文 P-11、P-19、P-35 的 11-04 註。

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
  interfaces.json  {"aos-agent": {"tools": "tools.json", "llm": "llm"}}（11-04；沒有 screen）
  llm/         子介面：_entry＝["python3", "llm.py"]，看／改 .env 的腦設定或 stack 的副本 llm.json（brain.py 每格先讀副本）
```

**腦**：`AOS_BRAIN_URL` 沒設＝假腦（有工具就先叫第一個、再答一句「FAKE ANSWER to: …」，不碰網路）；設了＝問 `{AOS_BRAIN_URL}/chat/completions`，`AOS_BRAIN_KEY` 有才帶 Bearer（P-23）。**工具**：腦看到的名字＝登記名，act 直接 `aos-tools call`（不經 aos-mcp），工具小格 `$AOS_STACK/tools/<名>/`；工具退非 0、沒登記、arguments 壞都接成 tool 訊息回給腦、不停（P-41）。**history 就是全貌**：user、assistant（含 tool_calls）、tool 都在 `$AOS_STACK/history.jsonl`；回答＝最新那則沒有 `tool_calls` 的 assistant。

```sh
# PATH 要有 impls 的 aos-exec／aos-loop／aos-fsm／aos-post、proto8/bin 的 aos-tools（真腦再設 AOS_BRAIN_URL）
aos-exec --ws ~/proj proto8/demo/agent-fsm &              # 直接跑：stack＝~/proj/.stack/；說話用 aos-post send --ordered ~/proj/.stack/queue
echo '{"cmd": "stop", "seq": 1}' > ~/proj/.stack/ctl.json  # 收工（這格跑完 loop 退 0）

# 掛 daemon（AOS_DAEMON＝daemon 的 $AOS_STACK；daemon 的環境要有上面的 PATH；PATH 再加 extras/agent/bin 的 aos-agent）
aos-agent add --ws ~/proj --name fsm1 proto8/demo/agent-fsm
export AOS_AGENT=fsm1        # 之後不用每次 --target
aos-agent say 現在幾點 && aos-agent listen
aos-agent pause              # 停在格與格之間；新信留 queue/new/
aos-agent resume             # 也有 stop／start（同一個 stack 接著對話）、rm fsm1、chat、tools、llm
```

- **停著等 vs 射後不理**寫在表上：範本 idle 的 `next` 接住 10＝queue 空就停著等（loop 隔 `interval_ms` 再看）。射後不理＝複製一份，idle 的 `next` 改成字串 `"think"`（10 到 loop＝收工）、`loop.json` 拿掉 `interval_ms`；要開場白就在 idle 的 argv 加 `"--prompt", "prompt.txt"`（相對這個資料夾；history 空、queue 沒好信時投一次）。
- **思考中來的信**留在 `queue/new/`，答完回 idle 才收、跟那批一起答（使用者 11-04「等答完回 idle 再收」）。
- **暫停時改 history**：`pause` 之後改 `history.jsonl`（例：刪掉最後一則答案），要它重答就把 `stage.txt` 寫成 `think` 再 `resume`；brain 每次從頭讀，改了就生效。最後一則已是答案時 brain 不問腦、退 10 回 idle。
- **錯**：stderr 一行 `agent-fsm: 代號 原因`、退 1、loop 停下等人（P-20）——`BrainFailed`、`ReplyBad`、`HistoryBad`、`ToolsBad`、`ToolFailed`、`PostFailed`、`StackMissing`、`WriteFailed`、`ArgumentsBad`，旗標指的檔不在＝`PromptMissing`／`SystemMissing`／`ToolsMissing`。修好再起（`aos-exec` 同一個工作區、或 daemon `start`）從停的那格接著做。壞信（body 不是 `{"role": "user", "content": 非空字串}`）丟掉、`$AOS_STACK/mailbox_warning.txt` 一行。
- 掛 daemon 卻沒給 `AOS_BRAIN_URL`＝假腦照跑（daemon 的環境或範本 `.env` 要給）。

