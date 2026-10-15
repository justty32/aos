# proto8/demo/fsm — aos-loop 拍 aos-fsm（同步版小 agent）

← [proto8/demo](../README.md)｜程式：[lib fsm.md](../../lib/fsm.md)｜規範：[NORMS 組合子 § fsm](../../NORMS/07-基礎設施-組合子.md#fsm)

```
python3 proto8/demo/run.py fsm        （或 python3 proto8/demo/fsm/run.py）
```

從哪裡跑都行，約 3.5 秒。只用 Python 標準庫。沒有真的 LLM：ask 格是假的（睡 0.4 秒、回寫死的話）。

## 裡面有什麼

- `loop.json`：aos-loop 的設定，inst＝`aos_fsm.py agent.json`，跑 10 次、每次隔 100 ms；fsm 每拍吐的那行附加到 `steps.jsonl`。窗都用 `$env` 指到暫存資料夾。
- `agent.json`：外層 fsm。`start: idle`，表 `idle → cells/idle.json`、`thinking → think/`（資料夾＝走 aos-inst 的找法，找到 `think/inst.json`）、`tool → cells/tool.json`；state 窗、lock、`max_steps: 10`。
- `think/`：內層 fsm（一格＝一個資料夾＝子物件）。`inst.json` 在 `think/` 裡跑 `aos_fsm.py fsm.json`；`fsm.json` 表 `ask → review`、`end: ["tool", "idle"]`、自己的 state 窗、沒有 lock 與 ctl（沿用外層）。
- 格（方法程式，stdin 讀 fsm 給的 `{"state", "step", "prev"}`、stdout 吐 `{"next", "data"}`）：
  - `cells/idle.py`：`inbox/` 有信就拿最早一封、開新對話（`work/convo.json`），回 `next: thinking`；沒信不回 next（留在 idle）。
  - `think/fake_llm.py`（ask 格，**同步**，N-41）：讀對話、睡 0.4 秒假裝等回覆、把回覆寫進 `work/answer.json`，回 `next: review`。問「幾點」就回要用工具 `clock`。
  - `think/review.py`：要用工具＝回 `next: tool`，否則把回覆寫進 `outbox.txt`、回 `next: idle`——兩個都不在內層表裡、在 `end` 裡＝交給外層。
  - `cells/tool.py`：跑工具（只有 `clock`＝現在時間），結果接進對話，回 `next: thinking`。
- `run.py`：mktemp 建暫存資料夾（`inbox/` 放兩封信「你好」「現在幾點？」、`work/`、窗、`steps.jsonl`、`outbox.txt`），起 aos-loop，每 20 ms 看一次兩層 state 窗、每拍跑完印一行；最後印 `steps.jsonl` 與 `outbox.txt`，刪掉暫存資料夾。

**換成真的 LLM**：只換 `think/ask.json` 那一格——改成一張跑 aos-llm（`core/llm`）的 inst，stdin 給從 `work/convo.json` 組好的請求、stdout 接到 `work/answer.json`，最後吐 `{"next": "review"}`（或包一支小程式做這三件事）。其他格、表、loop 都不動。要非同步就把 ask 換成「丟請求、回 `{"next": "waiting"}`」再加一格 waiting。

## 會看到什麼

```
[ 0.1s] 外層 phase=thinking step=1 │ 內層 phase=-      │ data={"q": "你好"}
[ 0.8s] 外層 phase=thinking step=2 │ 內層 phase=review │ data=null
[ 1.0s] 外層 phase=idle     step=0 │ 內層 phase=ask    │ data={"reply": "收到「你好」。（我是假的 LLM）"}
[ 1.2s] 外層 phase=thinking step=1 │ 內層 phase=ask    │ data={"q": "現在幾點？"}
[ 2.0s] 外層 phase=tool     step=3 │ 內層 phase=ask    │ data={"tool": "clock"}
[ 2.3s] 外層 phase=thinking step=4 │ 內層 phase=ask    │ data={"tool": "clock", "result": "09:44:53"}
[ 3.1s] 外層 phase=idle     step=0 │ 內層 phase=ask    │ data={"reply": "現在是 09:44:53。"}
[ 3.3s]    {"step": 3, "from": "thinking", "to": "tool", "code": 0, "ms": 68}
[ 3.3s]    現在是 09:44:53。
```

- 外層在 thinking 時每拍只推內層一步：內層 ask → review 那拍沒到終點，外層的 `to` 還是 thinking（`data` 是 null，因為內層那拍的 stdout 最後一份沒帶 data）。
- 內層 review 回 `next: idle`／`tool`（在 `end` 裡）：內層 phase 歸位 `ask`，外層換狀態、拿到那份 data。
- 外層回到 `start`（idle）時 `step` 歸零；ask 那拍約 470 ms＝同步等「LLM」。
