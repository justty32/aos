# 2026-10-24 把 agent 當工具給 agent 叫（agent-eve 叫 pyfix）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[2026-10-23 腦的工具呼叫](2026-10-23-tool-calls.md)（文末「agent 當腦的工具時題目怎麼交」）

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。這份是**嘗試性質**（使用者「反正只是嘗試」），結論全是頂層代定、可翻案。範本與現行佈局在 [demo/agent-eve](../demo/README.md#agent-eveagent-當工具10-24)。相關條文：[P-25、P-26、P-41](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32、P-33](../docs/CONVENTION/06-巢狀.md)、[C-52、C-54、C-56](../docs/CONCEPTS/01-設計理念.md)、[N-59](../docs/NORMS/10-基礎設施-定義與工作區.md)、[NORMS 待定 方向問題甲](../docs/NORMS/08-待定.md)。

## 使用者原文（整理版，10-24）

> 然後我這邊有不少想法，都麻煩你試着去思考去實作。我隨便說，你隨便做，反正只是嘗試：1.  把agent當做工具拿去給agent呼叫，比如一個專精於修改python程式的agent，他的context中已經包含了不少相關prompts，並且也有一整套工具。

## 代定（頂層，可翻案）

一次呼叫：eve 的腦回 `tool_calls: pyfix {"task", "dir"}` → eve 的 act 照 P-41 `AOS_STACK=$AOS_STACK/pyfix/ aos-exec tools/pyfix`、arguments 從 stdin 進 → `_entry` 開小格、`aos-exec --dotenv-override --ws runs/NNN/ws agent` 跑子 agent → 把子 agent 的答案＋實際 diff 印到 stdout，成為 eve history 裡一則 `tool` 訊息。

1. **轉接寫在工具自己的 `_entry`**：eve 的 act 不知道 pyfix 是 agent（C-52）；轉接用 python3 寫，不用 `sh -c`（使用者 10-15「少用 sh」）。這就是 WAIT_USER「agent 當腦的工具時題目怎麼交」的一個實例：介面照 P-41 stdin 進 stdout 出，`new/`／`out/` 那一套留在被叫的 agent 那邊、轉接層翻譯；`tool.json` 不加 `input` key。NORMS 待定方向問題甲（bob 叫 cathy 那種**非腦**的呼叫）不在這裡。
2. **每次呼叫都是新的、不帶記憶**：一次呼叫一個小格 `runs/NNN/`（mkdir 搶號），子 agent 的 history 從空的開始；舊的小格留著當現場。外層的腦要在 task 裡把事情寫清楚（它看不到子 agent 的對話）。
3. **子 agent 的工作區＝它自己的小格（`runs/NNN/ws/`），要改的程式碼用 `PYFIX_DIR` 指**（外層工作區不能直接給它，`new/`、`out/` 會撞）。`PYFIX_DIR`＝外層工作區底下的 `dir`，跑出工作區的擋掉（`DirBad`）。
4. **子工具只碰 `PYFIX_DIR`**（`realpath` 後必須在裡面）。路徑跑出去、檔不在、edit 的原文不是剛好一次，算模型的錯、照實回給它，不當工具失敗；只有環境沒設好（沒 `PYFIX_DIR`＝`DirMissing`）才算失敗。
5. **跑程式的子工具不是沙盒**：跑的程式能碰的跟這台機器的使用者一樣多（路徑限制只管讀寫工具）；逾時到了整個行程群 SIGKILL、回「逾時」給模型。
6. **出口保證：`_entry` 附真正的 diff**，不只信子 agent 自己說改了什麼。改之前把 `PYFIX_DIR` 裡 256 KB 以下的 UTF-8 檔備份到 `runs/NNN/before/`（不收 `.` 開頭、`__pycache__`），跑完逐檔比對；diff 超過 8000 字截斷。**不自動還原**，改壞了由外層的腦或人看 diff 決定。
7. **子 agent 失敗＝pyfix 失敗**：子 agent 退非 0 → `pyfix: AgentFailed …（現場在 runs/NNN）`、退 1；跑完沒答案 → `AnswerMissing`。eve 的 act 把那行回給腦、不停（[tool-calls 文末](2026-10-23-tool-calls/02-結論.md#10-24-定叫工具與小念頭的失敗回給腦)）；腦再叫 pyfix 就**開新的小格**從頭做。
8. **模型**：子 agent 用自己 `.env` 的模型（`_entry` 用 `aos-exec --dotenv-override` 叫；不加的話外層的 `AOS_BRAIN_MODEL` 一路傳下來、子 agent 的 `.env` 不蓋，N-59 第 4 件）。子 agent 要換模型就改它 `.env` 那一行。腦的位置（`AOS_BRAIN_URL`、`AOS_BRAIN_KEY`）兩層共用外層給的；要分開就在子 agent 的 `.env` 也寫 URL。
9. **逾時**：eve 的 act 放寬到 30 分鐘；子 agent 的 `loop.json` `max` 60。
10. **名字**：主 agent `agent-eve`（demo 慣例取人名）；工具 `pyfix`（白話：修 Python 的）；錯誤代號 `AgentFailed`、`AnswerMissing`、`DirBad`、`DirMissing`。eve、子 agent 的 `brain.py`／`act.py` 照抄 agent-dan，只改錯誤訊息開頭（P-25 每隻一份、不跨 agent 互指）。子工具現行名字見 [demo/agent-eve](../demo/README.md#agent-eveagent-當工具10-24)。

## 已知限制（用的時候注意）

- **逾時是層層套的**：外層 act 的 `timeout_ms` 一定要大於子 agent 可能跑的總時間，不然外層到時 SIGTERM 整群、子 agent 停在半路。直接拿 agent-dan（act 預設 60 秒）當主 agent 叫子 agent 幾乎一定逾時；沒有誰幫你算「裡面最多跑多久」。
- **巢狀深度＝資料夾深度**（P-25 工具放在叫它那格的資料夾裡、地址零個 `..`），自己叫自己做不到，不需要深度上限；但每多一層，逾時、token、現場位置都疊上去。
- 外層的腦看得到的只有 pyfix 那一行（子 agent 的 stderr 不給腦）；子 agent 的 stdout 由 `_entry` 轉到 stderr，不混進工具結果。
- 寫檔先寫暫存再改名，被殺不會留半個檔；「改錯」擋不了，靠備份＋diff。256 KB 以上或非 UTF-8 的檔不在 diff 裡。子工具沒有刪檔，模型只能寫空檔。
- **同時被叫兩次**：同一隻 eve 一個一個跑 tool_calls，第二個會看到第一個改過的檔。兩隻不同的 agent 同時叫：小格號碼不撞，但兩個子 agent 會同時改同一份程式碼——沒有鎖。
- **token**：子 agent 的整串對話不回外層（省）；但每次從空的開始，同一份檔每次呼叫都要再讀。brain.py 不記 `usage`，看不到兩層各花多少 token（10-19 重寫順序裡「kernel 看不到 token 用量」是同一個缺口）。
- 子 agent 只看得到 task；外層 system.txt 叮嚀寫清楚、子 agent 的 system.txt 叫它「題目不清楚就照實說」。

## 未決（留給使用者，都不擋）

1. 記憶：**每次新的**（現在）、**固定一個小格一直接著聊**（`_entry` 改成固定用 `$AOS_STACK/agent/`，子 agent 的 brain 會把新題目接在舊對話後面）、或**加 `session` 參數讓腦選**。
2. 子 agent 要不要用比外層強的模型（現在兩層同一個 `chatgpt-gpt-6-luna-low`；LiteLLM 開著時可以看 `/v1/models` 挑）。
