# proto8/demo/fsm — aos-loop 拍 aos-fsm（同步版小 agent）

← [proto8/demo](../README.md)｜程式：[lib fsm.md](../../lib/fsm.md)、[lib agent.md](../../lib/agent.md)｜規範：[NORMS 組合子 § fsm](../../NORMS/07-基礎設施-組合子.md#fsm)

```
python3 proto8/demo/run.py fsm        （或 python3 proto8/demo/fsm/run.py）
```

從哪裡跑都行，約 5 秒。只用 Python 標準庫，預設不連網：腦是假的（睡 0.4 秒、回寫死的話）。

## 裡面有什麼

- **不靠指示詞**（10-15 依 C-48）：repo 裡的 `agent.json`、`think/fsm.json` 只寫定義；`run.py` 的 `bind()` 把執行期的 key（`state`、`lock`、`history`、`work`）填進暫存資料夾裡的副本 `agent.json`（`lock` 已不歸 fsm，不再填），格都攤成內嵌 inst、`stdin` 指副本，thinking 格換成 `aos_fsm.py <暫存>/think.json`（內層表的副本，state 窗指進暫存）；aos-loop 的設定也寫成暫存資料夾裡的完整檔（inst＝`aos_fsm.py <副本>`，跑 10 次、每次隔 100 ms；fsm 每拍吐的那行附加到 `steps.jsonl`）。cwd 照舊是 demo 資料夾，所以格的相對路徑不變。
- `agent.json`：外層 fsm＋agent 設定（定義）。`start: idle`，表 `idle → cells/idle.json`、`thinking → think/`（資料夾＝走 aos-inst 的找法，找到 `think/inst.json`）、`tool → cells/tool.json`（表上靜態 `next: thinking`）；`max_steps: 10`（fsm 已不認得，忽略；state 窗由 `bind()` 填）。fsm 不認得的 key 給現成格庫 `aos_agent_lib.py` 用（10-15 收工後 fsm 不再餵格 stdin：`bind()` 把格攤成內嵌 inst、`stdin` 指暫存副本 `agent.json`，[agent.md](../../lib/agent.md)；第二批改成定義資料夾）：`brain`（腦的 TARGET）、`tools`（`{"clerk": "tools/clerk.json"}`：外層只有報時員這一個工具，要時間就得問它）、`history`（`work/history.json`＝OpenAI messages）、`work`（這兩個由 `bind()` 填），另有選填 `system`（`system.md`＝系統提示：繁體中文、簡短、需要時用工具；think 每次叫腦時插在最前面，不進 history）。
- `think/`：內層 fsm。`inst.json` 跑 `aos_fsm.py think/fsm.json`（cwd 跟外層一樣是 demo 資料夾）；表 `ask → review`（ask 帶表上靜態 `next: review`）、`end: ["tool", "idle"]`、自己的 state 窗（`--state` 旗標給）、沒有 lock 與 ctl。`think/fsm.json` 只寫表（格名字從 `think/` 算）；`bind()` 把它攤成暫存的 `think.json`，內層的格 `stdin` 同樣指外層副本。
- 格（stdin＝`bind()` 寫的副本 agent.json、stdout 吐 `{"next"?, "data"}`；`cells/common.py` 從 stdin 的 `history` 讀寫對話）：
  - `cells/idle.py`：`inbox/` 有信就拿最早一封、開新對話（history＝`[user 訊息]`），回 `next: thinking`；沒信不回 next。
  - `think/ask.json`＝`aos_agent_lib.py think`（**同步**，N-41）：讀 history、組 `{"messages", "tools"}`、跑腦、接 assistant 訊息。
  - `think/review.py`：最後一則 assistant 有 `tool_calls`＝`next: tool`，否則寫 `outbox.txt`、`next: idle`（兩個都在 `end`＝交給外層）。
  - `cells/tool.json`＝`aos_agent_lib.py tool`：跑第一個 tool_call（引數寫成 `work/N-call.json` 當 stdin）、接 tool 訊息。
- `brain/fake.py`（`brain/fake.json`）：假腦，照思考介面。問「幾點」：工具裡有 `clerk` 就叫 clerk（引數 `{"question": 原問題}`、拿到就回「報時員說：…」），否則叫 `clock`；「兩個」一次叫兩個；「亂」叫不存在的工具；拿到工具結果就照著回。`brain/openai.json`：真腦（`aos_brain_openai.py`）；`brain/ollama146.json`：ollama 原生真腦（`aos_brain_ollama.py`，146、gemma3:1b、num_ctx 4096、keep_alive 30s）；`brain/qwen146.json`：同上換 qwen2.5:14b（10-15 跑通過一圈）——**146 已不准用**（10-15 使用者），兩份只留當範例；`brain/lmstudio.json`：本機 LM Studio（`aos_brain_openai.py --base-url http://localhost:1234/v1`、`qwen/qwen3-1.7b`）。
- `tools/clock.json`＋`clock.py`：工具＝inst，說明在 `_tool`；stdout `{"time": "HH:MM:SS"}`。
- `clerk/`（報時員）＋`tools/clerk.json`：**tools 裡包含其他 agent 的呼叫**（[agent.md「agent 當函數／當工具」](../../lib/agent.md#agent-當函數當工具)）。`clerk/` 是一份綁好的定義（bob/ 那樣）：`agent.json`（單層表 `thinking → route → tool → thinking`、`start: thinking`、`end: ["idle"]`、`max_steps: 10`；腦 `brain.json`＝同一顆假腦、工具 `clock.json`、`system.md`「你是報時員…」，路徑都從 `clerk/` 算）。`tools/clerk.json`＝`aos_agent_lib.py ask clerk/agent.json`（`timeout_ms` 120000，`cells/tool.json` 跟著加到 150000）：每問一次就在外層的 `work/ask-<n>/` 開一個新 frame，history、state 累積在那裡，`clerk/` 一個字都不寫——同一個函數重複用（測試 `test_clerk_reused_definition_untouched` 問兩次、比 `clerk/` 前後的雜湊）。外層只拿到 `{"reply", "ticks"}`。
- `run.py`：mktemp 建暫存資料夾（`inbox/` 兩封信「你好」「現在幾點？」、`work/`、窗、`bind()` 寫的副本與 loop 設定），起 aos-loop，每 20 ms 看一次兩層 state 窗、每拍跑完印一行；最後印 `steps.jsonl`、history、報時員 frame 的 history（`work/ask-1/`）、`outbox.txt`，刪掉暫存資料夾。

## 換成真的 LLM

只改 `agent.json` 一行：`"brain": "brain/fake.json"` → `"brain": "brain/openai.json"`。其他格、表、loop 都不動。

- 端點預設 LiteLLM `http://localhost:4000/v1`（[dev-env](../../../wf/workflows/dev-env/02-模型端點.md#模型端點2026-09-25-定10-10-核對)），不用金鑰；先 `curl localhost:4000/v1/models` 看有哪些名字，把 `brain/openai.json` 的 `--model` 改成挑到的（預設寫 `chatgpt-gpt-6-sol`）。
- 換端點加旗標：`--base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key-env DEEPSEEK_API_KEY`，金鑰只放環境變數（`export DEEPSEEK_API_KEY=…`），不寫進檔。
- 真腦會慢：ask 那拍等多久就阻塞多久（`think/ask.json` 的 `timeout_ms` 200 秒、`run.py` 寫的 loop 設定 20 秒要跟著加大）。
- 報時員的腦另外換：`clerk/brain.json`（路徑從 `clerk/` 算，例 `["python3", "../../../lib/aos_brain_openai.py", …]`）。它整趟都在外層 tool 那一拍裡跑完，真腦時 loop 設定（`run.py`）的 `timeout_ms` 要蓋得住好幾次叫腦。

### 換成本機 LM Studio

只改一行：`"brain": "brain/lmstudio.json"`。LM Studio 要先開 server、載好 Qwen3-1.7B，用完 unload、關 server（[dev-env](../../../wf/workflows/dev-env/01-跨機與外部工具.md#跨機--離線差異)）。10-15 試過整圈跑通，ask 那拍約 4～8 秒（[thinking 10-15 §9](../../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#9-試-lm-studioqwen3-17b)）。

報時員（外層→clerk→clock）整圈 10-15 實跑過兩趟，一趟 16～20 秒；要實跑得把 loop 設定（`run.py`）的 `timeout_ms` 加到幾百秒，clerk 的腦也要換成 LM Studio；小模型有時不查 clock 直接編時間（[clerk-live](../../thinking/2026-10-15-clerk-live.md)）。

### 換成 146 的 ollama（146 已不准用，只留當範例）

同樣只改一行：`"brain": "brain/ollama146.json"`。走 ollama 原生 `/api/chat`（`/v1` 設不了 num_ctx）。**用 146 之前先照 [dev-env](../../../wf/workflows/dev-env/01-跨機與外部工具.md#跨機--離線差異) 的規矩**（看負載、只准小模型、num_ctx 4096、短 keep_alive、試完確認卸載）。

- 10-15 試過：gemma3:1b、deepseek-r1:8b 都不支援 tools（ollama 回 400），ask 格 `CellFailed`、外層停在 thinking。之後補了：內層 state 的 `last_error` 寫出真正原因（`CellFailed: BrainFailed: HttpError: …does not support tools`），連錯 3 次（`max_fails`）內層就停住（`halted: true`）、不再叫腦。〔10-15 收工後：fsm 不再管連錯，改由 think 格自己數、回 `halted`（[agent.md](../../lib/agent.md)），demo 的表還沒有 halted 狀態，第二批補。〕
- 10-15 試 qwen2.5:14b（`"brain": "brain/qwen146.json"`）：整圈跑通，會叫 `clock`；第一次叫腦含載入約 15 秒，用 loop 拍要把 loop 設定（`run.py`）的 `timeout_ms` 加大（[thinking 10-15 §8](../../thinking/2026-10-15-topics/03-試146-qwen與LM-Studio.md#8-試-146-ollamaqwen2514b)）。

要非同步就把 ask 換成「丟請求、回 `{"next": "waiting"}`」再加一格 waiting。

## 會看到什麼

```
[ 1.3s] 外層 phase=thinking step=1 │ 內層 phase=ask    │ data={"q": "現在幾點？"}
[ 2.2s] 外層 phase=tool     step=3 │ 內層 phase=ask    │ data={"tool_calls": ["clerk"]}
[ 3.7s] 外層 phase=thinking step=4 │ 內層 phase=ask    │ data={"tool": "clerk", "result": "{\"id\": \"…/tools/clerk.json\", \"code\": 0, \"signal\": null, …, \"result\": {\"reply\": \"現在是 11:20:08。\", \"ticks\": 5}}"}
[ 4.6s] 外層 phase=idle     step=0 │ 內層 phase=ask    │ data={"reply": "報時員說：現在是 11:20:08。"}
…
[ 4.8s] == work/ask-1/history.json（報時員 clerk 的 frame：clerk/ 本身沒動，history 累積在這裡）
[ 4.8s]    {"role": "user", "content": "現在幾點？"}
[ 4.8s]    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_2_0", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]}
[ 4.8s]    {"role": "tool", "tool_call_id": "call_2_0", "content": "{\"id\": null, \"code\": 0, \"signal\": null, …, \"result\": {\"time\": \"11:20:08\"}}"}
[ 4.8s]    {"role": "assistant", "content": "現在是 11:20:08。"}
```

- 外層在 thinking 時每拍只推內層一步：內層 ask → review 那拍沒到終點，外層的 `to` 還是 thinking（`data` 是 null）。
- 內層 review 回 `next: idle`／`tool`（在 `end` 裡）：內層 phase 歸位 `ask`，外層換狀態、拿到那份 data。
- tool 那拍約 1.3 秒＝報時員整趟跑完（它自己 5 拍：thinking → route → tool → thinking → route）；外層看不到這 5 拍，只拿到最後一句。
- 外層回到 `start`（idle）時 `step` 歸零；ask 那拍約 500 ms＝同步等腦。
