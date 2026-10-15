# proto8/demo/fsm — 一個 agent 定義資料夾（aos-loop 拍 `aos agent fsm`，同步版小 agent）

← [proto8/demo](../README.md)｜程式：[lib fsm.md](../../lib/fsm.md)、[lib agent.md](../../lib/agent.md)｜規範：[NORMS 組合子 § fsm](../../NORMS/07-基礎設施-組合子.md#fsm)｜概念：[C-46、C-50](../../CONCEPTS/05-agent.md)

```
python3 proto8/demo/run.py fsm                          （或 python3 proto8/demo/fsm/run.py）
python3 proto8/demo/fsm/run.py brain/lmstudio.json      （換腦：在 frame 放一份 brain.json，蓋過定義的）
```

從哪裡跑都行，約 5 秒。只用 Python 標準庫，預設不連網：腦是假的（睡 0.4 秒、回寫死的話）。

## 裡面有什麼

這個資料夾本身就是一個 **agent 定義資料夾**（C-50：表、怎麼拍、每格一張 inst、預設的腦、系統提示、工具；呼叫時一個字都不寫）。所有葉子都寫指令名：`aos …`（PATH 上的 `proto8/bin/aos`）、`aos-demo …`（`demo/bin/aos-demo`：跑 demo 資料夾裡的腳本）。

- `fsm.json`：外層表。`start: idle`；`idle → cells/idle.json`、`thinking → cells/thinking.json`（內層 fsm）、`tool → cells/tool.json`（表上靜態 `next: thinking`）、`done → cells/done.json`；`end: ["done", "halted"]`（halted 只在 end：think 連錯自己寫好 ret.json）；state 窗 `fsm/state.json`（從 frame 算）。
- `loop.json`：怎麼拍。`aos agent fsm`（照 frame 的 `frame.json` 找到這裡的 fsm.json，不必寫自己在哪）每 100 ms 一次、最多 20 次，每拍那行附加到 frame 的 `steps.jsonl`；`stop_on_end: true`（fsm 走到 end 就停，N-44）。
- `brain.json`（假腦 `aos-demo fsm/brain/fake.py`）、`system.md`（繁體中文、簡短、需要時用工具）、`tools/clerk.json`（外層只有報時員這一個工具，要時間就得問它）。
- `cells/`：
  - `idle.json`＝`cells/idle.py`：frame 的 `inbox/` 有信就拿最早一封、開新對話（`history.json`＝`[user 訊息]`），回 `next: thinking`；沒信回 `next: done`。
  - `thinking.json`＝`aos agent fsm think/fsm.json`：內層 fsm（`think/fsm.json`：`ask → review`、`end: ["tool", "idle", "halted"]`、state 窗 `fsm/think_state.json`）。`think/ask.json`＝`aos agent think`（**同步**，N-41）；`think/review.py`：最後一則 assistant 有 `tool_calls`＝`next: tool`，否則寫 frame 的 `outbox.txt`、`next: idle`（都在內層的 `end`＝交給外層）。ask 連錯 3 次自己把錯寫成 frame 的 `ret.json`、回 `next: halted`，同樣交給外層（外層的 halted 也只在 end＝結束）。
  - `tool.json`＝`aos agent tool`：跑第一個 tool_call，每次在 frame 的 `work/<n>/` 開新資料夾、引數寫成 `args.json`、在那裡跑。
  - `done.json`＝`aos agent done`：寫 frame 的 `ret.json`；done 在 `end` 裡，fsm 結束那行帶 `"end": true`，loop 的 `stop_on_end` 看到就停（N-44）；halted 不用它（ret.json 的錯由 think 自己寫，done 不讀別格的私檔，10-15「都同意。」）。
  - `common.py`：idle、review 共用的 history 讀寫（cwd＝frame）。
- `brain/`：換用的腦。`fake.py`（假腦：問「幾點」有 `clerk` 就叫 clerk、否則叫 `clock`；「兩個」一次叫兩個；「亂」叫不存在的工具；拿到工具結果就照著回）、`openai.json`（`aos brain openai`，預設 LiteLLM）、`litellm.json`（本機 LiteLLM、`chatgpt-gpt-6-luna-nothink`，[實跑](../../thinking/2026-10-15-litellm-live.md)）、`lmstudio.json`（本機 LM Studio、`qwen/qwen3-1.7b`）、`ollama146.json`／`qwen146.json`（146 的 ollama——**146 已不准用**（10-15 使用者），只留當範例）。
- `clerk/`（報時員）：**另一個 agent 定義資料夾**，單層表 `intake → thinking → route → (tool → thinking → route)* → done`（halted 只在 end），`loop.json` 跟外層同一種寫法（`times` 20），腦 `brain.json`＝同一顆假腦，工具 `tools/clock.json`（`clock.py`：stdout `{"time": "HH:MM:SS"}`），`system.md`「你是報時員…」。
- `tools/clerk.json`：**agent 當工具**（[agent.md](../../lib/agent.md#agent-當函數當工具)）＝`sh -c` 三步：在工具的資料夾（tool 格開的 `work/<n>/`＝clerk 這次的 frame）寫 `frame.json` 指回 `clerk/` → `aos loop clerk/loop.json` → `cat ret.json`。`clerk/` 一個字都不寫——同一個函數重複用（測試 `test_clerk_reused_definition_untouched` 問兩次、比 `clerk/` 前後的雜湊）。外層只拿到 clerk 的 `ret.json`（`{"reply"}`）。
- `run.py`：mktemp 建一個 frame（`frame.json` 指回這裡、`inbox/` 兩封信「你好」「現在幾點？」；給了 `brain/xxx.json` 就複製成 frame 的 `brain.json`），在 frame 裡起 `aos loop demo/fsm/loop.json`（PATH 接上 `proto8/bin`、`demo/bin`），每 20 ms 看一次兩層 state 窗、變了就印一行；最後印 `steps.jsonl`、history、報時員的 frame（`work/1/`）、`outbox.txt`、`ret.json`，刪掉 frame。

## 換成真的 LLM

不改定義：`python3 proto8/demo/fsm/run.py brain/lmstudio.json`（或 `brain/openai.json`）——run.py 把那份複製成 frame 的 `brain.json`（綁定，C-46：frame 裡的同名檔蓋過定義的）。

- LM Studio 要先開 server、載好 Qwen3-1.7B，用完 unload、關 server（[dev-env](../../../wf/workflows/dev-env/01-跨機與外部工具.md#跨機--離線差異)）。10-15 試過整圈跑通，ask 那拍約 4～8 秒（[thinking 10-15 §9](../../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#9-試-lm-studioqwen3-17b)）。
- LiteLLM 端點預設 `http://localhost:4000/v1`（[dev-env](../../../wf/workflows/dev-env/02-模型端點.md#模型端點2026-09-25-定10-10-核對)），不用金鑰；先 `curl localhost:4000/v1/models` 看有哪些名字，把 `brain/openai.json` 的 `--model` 改成挑到的。換端點加旗標：`--base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key-env DEEPSEEK_API_KEY`，金鑰只放環境變數。
- 報時員的腦另外換：改 `clerk/brain.json`，或像 [demo/kernels/llm](../kernels/llm/run.py) 那樣讓工具在 clerk 的 frame 放一份 `brain.json`。它整趟都在外層 tool 那一拍裡跑完；小模型有時不查 clock 直接編時間（[clerk-live](../../thinking/2026-10-15-clerk-live.md)）。
- 真腦會慢：ask 那拍等多久就阻塞多久（`think/ask.json` 的 `timeout_ms` 200 秒）。
- 10-15 試過 146 ollama：gemma3:1b、deepseek-r1:8b 都不支援 tools（ollama 回 400），ask 格 `CellFailed`；現在 think 連錯 3 次自己寫 `ret.json`（那個錯）、回 `halted`＝外層也結束，loop 停掉（不再每拍叫腦）。qwen2.5:14b 整圈跑通（[thinking 10-15 §8](../../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#8-試-146-ollamaqwen2514b)）。

要非同步就把 ask 換成「丟請求、回 `{"next": "waiting"}`」再加一格 waiting。

## 會看到什麼

```
[ 0.1s] 外層 phase=thinking │ 內層 phase=-
[ 0.7s] 外層 phase=thinking │ 內層 phase=review
[ 0.9s] 外層 phase=idle     │ 內層 phase=ask
…
[ 1.9s] 外層 phase=tool     │ 內層 phase=ask
[ 3.8s] 外層 phase=thinking │ 內層 phase=ask
…
[ 4.7s] 外層 phase=done     │ 內層 phase=ask
[ 5.0s] aos-loop 結束，退出碼 0（done）
…
[ 5.0s] == work/1/（叫 clerk 那次的 frame：args.json＝引數；clerk/ 本身沒動，history 累積在這裡）
[ 5.0s]    args.taken.json：{"question": "現在幾點？"}
[ 5.0s]    {"role": "user", "content": "現在幾點？"}
[ 5.0s]    {"role": "assistant", "content": null, "tool_calls": [{… "name": "clock", "arguments": "{}"}}]}
[ 5.0s]    {"role": "tool", "tool_call_id": "call_2_0", "content": "{\"id\": \"…/clerk/tools/clock.json\", \"code\": 0, …, \"result\": {\"time\": \"18:50:50\"}}"}
[ 5.0s]    {"role": "assistant", "content": "現在是 18:50:50。"}
[ 5.0s]    ret.json：{"reply": "現在是 18:50:50。"}
[ 5.0s] == ret.json（done 格寫的）：{"reply": "報時員說：現在是 18:50:50。"}
```

- 外層在 thinking 時每拍只推內層一步：內層 ask → review 那拍沒到終點，外層的 `to` 還是 thinking。
- 內層 review 回 `next: idle`／`tool`（在 `end` 裡）：內層 phase 歸位 `ask`，外層換狀態。
- tool 那拍約 1.7 秒＝報時員整趟跑完（它自己的 loop 敲 7 拍：intake → thinking → route → tool → thinking → route → done）；外層看不到這幾拍，只拿到它的 ret.json。
- inbox 空了 idle 回 `done`：done 那拍寫 `ret.json`、stop，fsm 結束（phase 歸位 idle），loop 正常結束（`done`）。
