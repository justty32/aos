# proto8/demo/fsm — aos-loop 拍 aos-fsm（同步版小 agent）

← [proto8/demo](../README.md)｜程式：[lib fsm.md](../../lib/fsm.md)、[lib agent.md](../../lib/agent.md)｜規範：[NORMS 組合子 § fsm](../../NORMS/07-基礎設施-組合子.md#fsm)

```
python3 proto8/demo/run.py fsm        （或 python3 proto8/demo/fsm/run.py）
```

從哪裡跑都行，約 3.6 秒。只用 Python 標準庫，預設不連網：腦是假的（睡 0.4 秒、回寫死的話）。

## 裡面有什麼

- `loop.json`：aos-loop 的設定，inst＝`aos_fsm.py agent.json`，跑 10 次、每次隔 100 ms；fsm 每拍吐的那行附加到 `steps.jsonl`。窗都用 `$env` 指到暫存資料夾。
- `agent.json`：外層 fsm＋agent 設定。`start: idle`，表 `idle → cells/idle.json`、`thinking → think/`（資料夾＝走 aos-inst 的找法，找到 `think/inst.json`）、`tool → cells/tool.json`（表上靜態 `next: thinking`）；state 窗、lock、`max_steps: 10`。fsm 不認得的四個 key 給現成格庫 `aos_agent_lib.py` 用（fsm 把整份設定當 stdin 的 `cfg` 給格，[agent.md](../../lib/agent.md)）：`brain`（腦的 TARGET）、`tools`（`{"clock": "tools/clock.json"}`）、`history`（`work/history.json`＝OpenAI messages）、`work`。
- `think/`：內層 fsm。`inst.json` 跑 `aos_fsm.py think/fsm.json`（cwd 跟外層一樣是 demo 資料夾）；表 `ask → review`（ask 帶表上靜態 `next: review`）、`end: ["tool", "idle"]`、自己的 state 窗、沒有 lock 與 ctl。內層給格的 `cfg` 是 `think/fsm.json` 自己，所以 `brain`、`tools`、`history`、`work` 四個 key 用 `$ref` 指到 `agent.json`（N-40）。
- 格（stdin 讀 fsm 給的 `{"state", "step", "prev", "cfg"}`、stdout 吐 `{"next"?, "data"}`）：
  - `cells/idle.py`：`inbox/` 有信就拿最早一封、開新對話（history＝`[user 訊息]`），回 `next: thinking`；沒信不回 next。
  - `think/ask.json`＝`aos_agent_lib.py think`（**同步**，N-41）：讀 history、組 `{"messages", "tools"}`、跑腦、接 assistant 訊息。
  - `think/review.py`：最後一則 assistant 有 `tool_calls`＝`next: tool`，否則寫 `outbox.txt`、`next: idle`（兩個都在 `end`＝交給外層）。
  - `cells/tool.json`＝`aos_agent_lib.py tool`：跑第一個 tool_call（引數寫成 `work/N-call.json` 當 stdin）、接 tool 訊息。
- `brain/fake.py`（`brain/fake.json`）：假腦，照思考介面。問「幾點」回 OpenAI `tool_calls` 叫 `clock`；「兩個」一次叫兩個；「亂」叫不存在的工具；拿到工具結果就照著回。`brain/openai.json`：真腦（`aos_brain_openai.py`）；`brain/ollama146.json`：ollama 原生真腦（`aos_brain_ollama.py`，146、gemma3:1b、num_ctx 4096、keep_alive 30s）。
- `tools/clock.json`＋`clock.py`：工具＝inst，說明在 `_tool`；stdout `{"time": "HH:MM:SS"}`。
- `run.py`：mktemp 建暫存資料夾（`inbox/` 兩封信「你好」「現在幾點？」、`work/`、窗），起 aos-loop，每 20 ms 看一次兩層 state 窗、每拍跑完印一行；最後印 `steps.jsonl`、history、`outbox.txt`，刪掉暫存資料夾。

## 換成真的 LLM

只改 `agent.json` 一行：`"brain": "brain/fake.json"` → `"brain": "brain/openai.json"`。其他格、表、loop 都不動。

- 端點預設 LiteLLM `http://localhost:4000/v1`（[dev-env](../../../wf/workflows/dev-env.md#模型端點2026-09-25-定10-10-核對)），不用金鑰；先 `curl localhost:4000/v1/models` 看有哪些名字，把 `brain/openai.json` 的 `--model` 改成挑到的（預設寫 `chatgpt-gpt-6-sol`）。
- 換端點加旗標：`--base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key-env DEEPSEEK_API_KEY`，金鑰只放環境變數（`export DEEPSEEK_API_KEY=…`），不寫進檔。
- 真腦會慢：ask 那拍等多久就阻塞多久（`think/ask.json` 的 `timeout_ms` 200 秒、`loop.json` 的 20 秒要跟著加大）。

### 換成 146 的 ollama

同樣只改一行：`"brain": "brain/ollama146.json"`。走 ollama 原生 `/api/chat`（`/v1` 設不了 num_ctx）。**用 146 之前先照 [dev-env](../../../wf/workflows/dev-env.md#跨機--離線差異) 的規矩**（看負載、只准小模型、num_ctx 4096、短 keep_alive、試完確認卸載）。

- 10-15 試過：gemma3:1b、deepseek-r1:8b 都不支援 tools（ollama 回 400），ask 格 `CellFailed`、外層停在 thinking。之後補了：內層 state 的 `last_error` 寫出真正原因（`CellFailed: BrainFailed: HttpError: …does not support tools`），連錯 3 次（`max_fails`）內層就停住（`halted: true`）、不再叫腦；要再試就把內層 state 的 `halted` 拿掉。

要非同步就把 ask 換成「丟請求、回 `{"next": "waiting"}`」再加一格 waiting。

## 會看到什麼

```
[ 0.1s] 外層 phase=thinking step=1 │ 內層 phase=-      │ data={"q": "你好"}
[ 0.8s] 外層 phase=thinking step=2 │ 內層 phase=review │ data=null
[ 1.0s] 外層 phase=idle     step=0 │ 內層 phase=ask    │ data={"reply": "收到「你好」。（我是假的腦）"}
[ 1.2s] 外層 phase=thinking step=1 │ 內層 phase=ask    │ data={"q": "現在幾點？"}
[ 1.9s] 外層 phase=thinking step=2 │ 內層 phase=review │ data=null
[ 2.2s] 外層 phase=tool     step=3 │ 內層 phase=ask    │ data={"tool_calls": ["clock"]}
[ 2.4s] 外層 phase=thinking step=4 │ 內層 phase=ask    │ data={"tool": "clock", "result": "{\"code\": 0, \"result\": {\"time\": \"10:15:30\"}}"}
[ 3.1s] 外層 phase=thinking step=5 │ 內層 phase=review │ data=null
[ 3.3s] 外層 phase=idle     step=0 │ 內層 phase=ask    │ data={"reply": "現在是 10:15:30。"}
…
[ 3.6s] == work/history.json（OpenAI messages，最後一段對話）
[ 3.6s]    {"role": "user", "content": "現在幾點？"}
[ 3.6s]    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1_0", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}
[ 3.6s]    {"role": "tool", "tool_call_id": "call_1_0", "content": "{\"code\": 0, \"result\": {\"time\": \"10:15:30\"}}"}
[ 3.6s]    {"role": "assistant", "content": "現在是 10:15:30。"}
```

- 外層在 thinking 時每拍只推內層一步：內層 ask → review 那拍沒到終點，外層的 `to` 還是 thinking（`data` 是 null）。
- 內層 review 回 `next: idle`／`tool`（在 `end` 裡）：內層 phase 歸位 `ask`，外層換狀態、拿到那份 data。
- 外層回到 `start`（idle）時 `step` 歸零；ask 那拍約 500 ms＝同步等腦。
