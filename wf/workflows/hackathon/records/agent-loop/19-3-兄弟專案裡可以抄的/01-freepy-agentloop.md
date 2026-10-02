← [3. 兄弟專案裡可以抄的](../19-3-兄弟專案裡可以抄的.md)（分檔 1/2）｜[下一份](02-freepy-base-tools.md)

**`freepy/agentloop/` — 同一個作者用 Python 寫過同一件事**

- **`freepy/agentloop/loop.py` 的 `advance(bot, dispatch, prompt, handle, images)`**：一次呼叫只做「一個 Step **或**一整批 tools」，做完就返回，不 park——這正是 `aos exec` 單回合的形狀。同檔 `run()` 是「一直 `advance()` 到 Round 結束」的外殼，`_perform_all(calls, dispatch, seed)` 是**依序**跑完一批 tool call 並以 `call["id"]` 當 key 收結果。
- **`freepy/agentloop/calling.py` 的 `perform(dispatch, call)`**：整支的契約是「**永遠回一個字串**，它會直接變成送回模型的 tool message」，四種壞法各翻成一句模型讀得懂的話——`args_raw` 存在（JSON 壞掉）、沒有這個工具（**附上可用工具清單**）、參數對不上簽名、工具自己炸了。註解裡那句「模型讀到 `Error: ...` 會自己改一次再試，讀到 traceback 只會整條斷掉」就是 Evans 的自癒論證。同檔 `_mismatch(fn, args)` 特別註明**先問簽名再叫**，否則工具內部自己丟的 `TypeError` 會被誤報成參數錯，「模型就照著那句假話去改一個本來沒問題的參數」。`_text(value)` 與 `MAX_OUTPUT = 30000` 是回程截斷。
- **`freepy/agentloop/handle.py`**：`Handle.stop` 的具體原因（`done`／`length`／`budget`／`input_tokens`／`output_tokens`／`engine`／`error`）、`phase`、`done()`、`pause()`／`resume()`／`end()`、`_commit_step()`／`_commit_tools()` 兩個提交點、`_park_unlocked()`。**「做完了／沒事做／壞掉了／正在想」在這裡是四個不同的欄位值，不是同一個 exit 0。**
- **`freepy/agentloop/ROUNDS.md`〈固定術語〉**：Round 與 Step 的定義（「一次 `ask() → message` 是一個 Step；**工具執行發生在兩步之間，不另算一步**；一步要求十個工具仍只算一步」）——直接對到 Pike 那句「回合數 ≠ agent 步數」。同檔〈Round 狀態機〉是 `idle → ready → running_step → ready → running_tools → …` 加 `waiting`／`paused`／`completed`／`error`；〈自然靜止與 `auto_finish`〉把「模型沒有 tool calls」「`run()` 返回」「Round completed」**明講成三件可以分開的事**；〈固定的 operation 與 callback 邊界〉的 `CONTINUE`／`PAUSE`／`END`（優先序 `END > PAUSE > CONTINUE`）是「停止＝不投遞」的有名字版本。
- **`freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉**：Step 中斷分成「`Reply` 沒有留下任何 message → 回滾、不計 Step」與「已留下完整或部分 message → 保留、計一個 Step」；tool call 中斷「**當作工具失敗……已產生的外部副作用仍可能存在，錯誤結果不代表 rollback**」。〈整個實例被強制終止〉一句話劃界：「Ctrl-C、SIGTERM 或直接殺 process 屬於不可抗力。這種情況**不做收尾保證**」——這是拿來對照「aos 該承諾到哪一級」的能力邊界，不是 crash recovery 實作。
- **`freepy/agentloop/CONTROLLER.md`〈最小 API〉**：`.advance()`／`.run()`／`.state`／`.wait(*states)`／`.send(prompt, finish=False)`，以及「同一個 Controller 只能選一種 runner 樣式」。〈明確不負責〉明列它不做持久化、Task queue、worker lease、副作用 recovery——**照抄它的功能可以，照抄它的可靠性不行**。
- **`freepy/agentloop/LIMITS.md`〈內建 Limits 負責什麼〉**：Step 數、工具總呼叫次數、單一工具次數、工具白名單、模型白名單、經過時間、input／output token——一份現成的「停止條件」清單，全部透過公開的 `after_step` callback 實作。〈合作式限制〉明寫它不切斷進行中的請求、不回滾副作用。
- **`freepy/agentloop/threading/`** 與 **`freepy/agentloop/limits/`** 是兩個只用公開 API 的可選子專案，可作「核心不為政策保留分支」的分層樣本。

**`freepy/llmkit/` — tool call 的協定形狀**

- **`freepy/llmkit/llms/TOOLS.md`〈工具〉**：`reply.calls` 的形狀是 `[{"id": ..., "name": ..., "args": {...}}]`，結果以 `{c["id"]: ...}` 回填，並明寫「一步可能吐出**好幾個**呼叫……`tool_results` 的 **key 少一個下一步就對不起來**」——這就是 Evans 要的 tool_call_id 的最小形狀。同節也寫了「`args` 的 JSON 壞掉不會丟例外，會給空 dict 並附上 `args_raw`——**執行前記得看一眼**」。〈欠著的工具呼叫〉的 `bot.pending_calls` 是「這一輪還欠哪幾個結果」的現成查詢。〈tool_choice：逼它叫工具〉是 `auto`／`none`／`required`／指名四個值的對照表。
- **`freepy/llmkit/tooljson/`**：`FORMAT.md`、`EXEC.md`（〈exec〉〈argv〉〈stdin / stdout / stderr〉〈ok_exit〉〈cwd / timeout / limits / source〉）、`PYTHON.md` 是 `core/tooljson` 那份 C++ 格式的**Python 參考實作**；`invoke.py`、`args.py`、`exec_type.py`、`registry.py`、`text.py` 是實際執行的那一半——也就是 C++ S1 明講「尚未實作」的 `run`。
- **`freepy/llmkit/llms/USAGE.md`** 是 token／成本欄位的位置；`freepy/llmkit/live_smoke.py` 是打真端點的冒煙腳本（拿來對照 `aos llms` 要怎麼被冒煙）。
