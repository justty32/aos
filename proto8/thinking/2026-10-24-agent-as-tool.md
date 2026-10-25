# 2026-10-24 把 agent 當工具給 agent 叫（agent-eve 叫 pyfix）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)（文末「agent 當腦的工具時題目怎麼交」）

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。這份是**嘗試性質**（使用者「反正只是嘗試」），結論全是頂層代定、可翻案。相關條文：[P-25、P-26、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32、P-33](../docs/CONVENTION/06-巢狀.md)、[C-52、C-54、C-56](../docs/CONCEPTS/01-設計理念.md)、[N-59](../docs/NORMS/10-基礎設施-定義與工作區.md)、[NORMS 待定 方向問題甲](../docs/NORMS/08-待定.md)。

## 使用者原文（整理版，10-24）

> 然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試：1.  把agent當做工具拿去給agent呼叫，比如一個專精於修改python程式的agent，他的context中已經包含了不少相關prompts，並且也有一整套工具。

## 做了什麼（範本 [demo/agent-eve](../demo/README.md#agent-eveagent-當工具10-24)）

```
agent-eve/                  主 agent：照抄 agent-dan（三態、brain.py、act.py），只有一個工具 pyfix
  system.txt                「改 Python 的事交給 pyfix；task 要寫清楚；回答前看 diff」
  fsm.json                  act 的 timeout_ms 從 60 秒放寬到 30 分鐘（act 裡要跑一整隻子 agent）
  tools/pyfix/
    tool.json               給 eve 的腦看：{task（必填）, dir（相對於工作區，預設 .）}
    _entry                  轉接（python3）：stdin → 子 agent 的 new/task.txt、aos-exec 它、out/task.txt＋diff → stdout
    agent/                  子 agent：也是照抄 agent-dan 的一整隻，自己的 system.txt（修 Python 的做事順序與規矩）、自己的 .env
      tools/list_files、read_file、write_file、edit_file、run_python     只碰 $PYFIX_DIR
```

一次呼叫的路：eve 的腦回 `tool_calls: pyfix {"task": "...", "dir": "proj"}` → eve 的 act 照 P-41 `AOS_STACK=$AOS_STACK/pyfix/ aos-exec tools/pyfix`、arguments 從 stdin 進 → `_entry` 開小格 `$AOS_STACK/runs/001/`（`ws/new/task.txt`、`stack/`、改之前的備份 `before/`），設 `PYFIX_DIR=$AOS_WS/proj`，`aos-exec --dotenv-override --ws runs/001/ws agent` → 子 agent 自己 `idle think act …` 跑到答完 → `_entry` 讀 `runs/001/ws/out/task.txt`，後面接上**實際的 diff**（改前備份對改後），印到 stdout → 那段就是 eve 的 history 裡一則 `tool` 訊息 → eve 的腦再想、回答。

測試 [tests/test_eve.py](../tests/test_eve.py) 5 個（假 server 同一個 URL 扮兩個腦，看 request 的 tools 有沒有 pyfix 分劇本）：委派修好、每次呼叫是新的、子 agent 失敗外層停住再跑、`dir` 出不去、子工具出不去／edit 要剛好一次／run_python 逾時。

## 跑一次（10-24，`~/code/try/agent-as-tool/`）

- **LiteLLM 沒開**（localhost:4000 連線被拒、機器上也沒有 litellm 可起），所以**用假 server 劇本跑通**（`fake_brains.py`，劇本照一個合理的模型會做的寫；不是真模型的表現）。要真跑：`python3 setup_ws.py` 重建工作區、`AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ws <repo>/proto8/demo/agent-eve`（指令在試驗場的 `README.txt`）。
- 題目：「我的 proj/ 裡 test_stats.py 一直沒過，幫我把 stats.py 修好（測試本身是對的，不要改測試），最後告訴我錯在哪。」`stats.py` 有兩個 bug：`mean` 除以 `len(xs)-1`、`median` 偶數個沒取平均。
- eve：think → 叫 pyfix（task 寫明「修 stats.py、不要改測試、回報原因與改法」、`dir: proj`）→ act 跑子 agent。
- 子 agent（pyfix）：`list_files` → 同時 `read_file` 兩個檔 → `run_python -m unittest -v`（結束碼 1、兩個 FAIL）→ 同時兩個 `edit_file` → 再跑測試（結束碼 0、3 個過）→ 純文字回報。trace 19 筆（6 輪 think/act）。
- pyfix 回給 eve 的：子 agent 的報告＋真正的 diff（`mean` 一行、`median` 改成分奇偶）。eve 答：「修好了。stats.py 有兩個 bug：mean 除以 len(xs)-1…；median 遇到偶數個時只取了中間偏右那個…三個測試現在都通過，test_stats.py 沒動。」整個結束碼 0，`proj/` 的測試實際跑過全綠。
- 現場留在 `~/code/try/agent-as-tool/ws-fake/`（含兩層 history、trace、`before/` 備份）、腦收到與回的每一筆在 `ws-fake-brains.jsonl`。

## 代定（頂層，可翻案）

1. **轉接寫在工具自己的 `_entry`**（照 10-23 的推薦；範本 agent-dan 的 act 一行沒改）：eve 的 act 不知道 pyfix 是 agent（C-52）。轉接用 python3 寫（不用 `sh -c`，使用者 10-15「少用 sh」）。所以 **WAIT_USER 那題「agent 當腦的工具時題目怎麼交」這次的做法就是答案的一個實例**：介面照 P-41 stdin 進 stdout 出，`new/`／`out/` 那一套留在被叫的 agent 那邊、轉接層翻譯；`tool.json` 不加 `input` key。NORMS 待定方向問題甲（bob 叫 cathy 那種**非腦**的呼叫）沒動。
2. **每次呼叫都是新的、不帶記憶**：一次呼叫一個小格 `runs/NNN/`（mkdir 搶號），子 agent 的 history 從空的開始；舊的小格留著當現場。理由：外層的腦本來就要在 task 裡寫清楚（它看不到子 agent 的對話），帶記憶反而讓第二次呼叫背著上一次的整串 history（token 浪費、上一題的錯會帶過來）。**選項**：要記憶＝`_entry` 改成固定用一個小格（例 `$AOS_STACK/agent/`），子 agent 的 brain 會自然把新題目接在舊對話後面（agent-dan 的 brain 本來就這樣接）；或加一個 `session` 參數讓腦自己選要不要接著上次。
3. **子 agent 的工作區＝它自己的小格（`runs/NNN/ws/`），要改的程式碼另外用 `PYFIX_DIR` 指**：agent-dan 範本把 `AOS_WS` 當收題目、交答案的地方，所以不能直接拿外層的工作區給它（`new/`、`out/` 會跟外層的撞）。`PYFIX_DIR`＝外層工作區底下的 `dir`，`_entry` 擋掉跑出工作區的（`DirBad`）。名字照 C-54 環境變數全大寫，主詞是 pyfix。
4. **子工具只碰 `PYFIX_DIR`**（`realpath` 後必須在裡面）。**路徑跑出去、檔不在、edit 的原文不是剛好一次，算模型的錯、照實回給它（stdout「錯誤：…」、退 0）**，不當工具失敗——讓子 agent 自己改，不然模型一抄錯就整串停下。只有環境沒設好（沒 `PYFIX_DIR`＝`DirMissing`）才退 1。
5. **`run_python` 不是沙盒**：跑的程式能碰的跟這台機器的使用者一樣多（路徑限制只管讀寫工具）。逾時預設 30 秒、上限 120 秒，到時整個行程群 SIGKILL、回「逾時」給模型。
6. **出口保證：`_entry` 附真正的 diff**，不只信子 agent 自己說改了什麼。改之前把 `PYFIX_DIR` 裡 256 KB 以下的 UTF-8 檔備份到 `runs/NNN/before/`（不收 `.` 開頭、`__pycache__`），跑完逐檔比對；diff 超過 8000 字截斷。**不自動還原**——改壞了由外層的腦或人看 diff 決定，備份在小格裡。
7. **子 agent 失敗＝pyfix 失敗**：子 agent 退非 0 → `pyfix: AgentFailed …（現場在 runs/NNN）`、退 1；跑完沒答案 → `AnswerMissing`。eve 的 act 把那行回給腦、不停（10-24 晚改，[tool-calls 文末](2026-10-23-tool-calls.md#10-24-定叫工具與小念頭的失敗回給腦)）；腦再叫 pyfix 就**開新的小格**從頭做（不接著失敗的那格做）。
8. **模型**：子 agent 用自己 `.env` 的模型——`_entry` 用 `aos-exec --dotenv-override` 叫它。不加的話外層 `.env` 設的 `AOS_BRAIN_MODEL` 會一路傳下來，子 agent 自己的 `.env` 不蓋（N-59 第 4 件），兩層永遠同一個模型。兩隻現在都是 `chatgpt-gpt-6-luna-low`；子 agent 要換強的就改它 `.env` 那一行。腦的位置（`AOS_BRAIN_URL`、`AOS_BRAIN_KEY`）兩層共用外層給的。
9. **逾時**：eve 的 act 放寬到 30 分鐘（子 agent 最多 60 次 × 每次 think 3 分鐘／act 5 分鐘，理論上還是可能超過）。子 agent 的 `loop.json` `max` 60。
10. **名字**：主 agent 照 demo 慣例取人名 `agent-eve`（接 bob、ann、cathy、dan）；工具 `pyfix`（白話：修 Python 的）；子工具 `list_files`、`read_file`、`write_file`、`edit_file`、`run_python`（動詞在前，跟 OpenAI 慣用的工具名一樣）；錯誤代號 `AgentFailed`、`AnswerMissing`、`DirBad`、`DirMissing`（主詞＋四種結尾）。eve、子 agent 的 `brain.py`／`act.py` 照抄 agent-dan，只改錯誤訊息開頭（P-25 每隻一份、不跨 agent 互指）。

## 挖出的邊緣狀況

- **子 agent 失敗**：腦壞了、工具真的起不來、`max` 用完沒答案——全部變成 pyfix 退 1、那行回給外層的腦（代定 7，10-24 晚起），腦自己決定重試、換說法、放棄。外層的腦看得到的只有 pyfix 那一行（現場在 runs/NNN，子 agent 的 stderr 不給腦）。
- **逾時是層層套的**：外層 act 的 `timeout_ms` 一定要大於子 agent 可能跑的總時間，不然外層到時 SIGTERM 整群，子 agent 停在半路（它的 state 停在某一格、可能剛改完一個檔還沒跑測試）。範本預設 act 60 秒，直接拿 agent-dan 當主 agent 叫子 agent 幾乎一定逾時。沒有誰幫你算「裡面最多跑多久」。
- **巢狀深度**：P-25 工具放在叫它的那一格的資料夾裡、地址零個 `..`，所以**巢狀深度就是資料夾的深度，自己叫自己做不到**（除非用捷徑繞回去）——不需要深度上限。但每多一層，逾時、token、現場位置（`runs/NNN/stack/<工具>/runs/NNN/…`）都疊上去。
- **子 agent 寫壞檔**：寫檔是先寫暫存再改名，被殺不會留半個檔；但「改錯」擋不了。備份＋diff 讓外層看得到、拿得回（代定 6），不自動還原。改到 256 KB 以上或非 UTF-8 的檔不在 diff 裡（外層看不到）。
- **同時被叫兩次**：eve 的 act 是一個一個跑 tool_calls，同一隻 eve 不會同時叫。腦一次回兩個 pyfix 時，第二個會看到第一個改過的檔（diff 也只算自己那次的）。兩隻不同的 agent 用同一個 stack 同時叫：小格號碼用 mkdir 搶、不會撞，但兩個子 agent 會同時改同一份程式碼——沒有鎖。
- **token 浪費**：子 agent 的整串對話（讀檔全文、測試輸出）不回外層，外層只拿報告＋diff，這是省的；但子 agent 每次都從空的開始（代定 2），同一份檔每次呼叫都要再讀一次。brain.py 不記回覆裡的 `usage`，現在**看不到兩層各花了多少 token**；10-19 重寫順序裡「kernel 看不到 token 用量」是同一個缺口。
- **兩個腦共用一個 URL**：`AOS_BRAIN_URL` 往下傳，子 agent 跟外層打同一個端點。要分開（例如子 agent 走另一台）得在子 agent 的 `.env` 也寫 URL（因為 `--dotenv-override`，它會蓋過外層的）。
- **子 agent 的 stdout**：子 agent 的 loop／fsm 印的東西會混進工具結果，所以 `_entry` 把它轉到 stderr；子 agent 的錯誤訊息照樣一路往上印（使用者看得到 `pyfix-agent: BrainFailed …`、`pyfix: AgentFailed …`、`agent-eve: ToolFailed …` 三行）。
- **外層腦給的 task 不清楚**：子 agent 看不到外層的對話，只看到 task。外層的 system.txt 有叮嚀，但擋不了；子 agent 的 system.txt 叫它「題目不清楚就照實說」。
- **刪檔**：子工具沒有刪檔；模型只能寫空檔。diff 會顯示整份變空。

## 留給使用者的選項（都不擋）

1. 子 agent 失敗時：**停下等人**（現在）還是**把失敗當結果回給外層的腦**。
2. 記憶：**每次新的**（現在）、**固定一個小格一直接著聊**、或**讓腦用參數選**。
3. 子 agent 要不要用比外層強的模型（現在兩層同一個 `chatgpt-gpt-6-luna-low`；LiteLLM 開著時可以看 `/v1/models` 挑）。
4. 「把 agent 包成工具」這個轉接要不要做成**共用的一支**（給一個 agent 資料夾就包成 stdin 進 stdout 出的工具），而不是每個工具自己寫一份 `_entry`。現在照 P-25 每隻一份。
5. 真模型還沒跑過這一套——等 LiteLLM 開著時照試驗場 `README.txt` 跑一次。
