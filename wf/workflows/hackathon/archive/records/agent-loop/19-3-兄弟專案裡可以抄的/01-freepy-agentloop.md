← [3. 兄弟專案裡可以抄的](../19-3-兄弟專案裡可以抄的.md)（分檔 1/2）｜[下一份](02-freepy-base-tools.md)

**`freepy/agentloop/` — 同一件事的 Python 版**

- `loop.py` 的 `advance(bot, dispatch, prompt, handle, images)`：一次只做一個 Step 或一整批 tools 就返回，是 `aos exec` 單回合的形狀；`run()` 是外殼；`_perform_all(calls, dispatch, seed)` 依序跑一批 tool call，以 `call["id"]` 當 key 收結果。
- `calling.py` 的 `perform(dispatch, call)`：永遠回一個字串當 tool message；四種壞法（`args_raw`、沒有這個工具＋附可用清單、參數對不上簽名、工具自己炸）各翻成模型讀得懂的話。`_mismatch(fn, args)` 先問簽名再叫，避免把工具內部的 `TypeError` 誤報成參數錯。`_text(value)`、`MAX_OUTPUT = 30000` 是回程截斷。
- `handle.py`：`Handle.stop` 的原因（`done`／`length`／`budget`／`input_tokens`／`output_tokens`／`engine`／`error`）、`phase`、`pause()`／`resume()`／`end()`、`_commit_step()`／`_commit_tools()`。做完了／沒事做／壞掉了／正在想是不同欄位值。
- `ROUNDS.md`〈固定術語〉（Step 定義：工具執行在兩步之間、不另算一步）、〈Round 狀態機〉、〈自然靜止與 `auto_finish`〉、〈固定的 operation 與 callback 邊界〉（`CONTINUE`／`PAUSE`／`END`，`END > PAUSE > CONTINUE`）。
- `RUNNER.md`〈operation 在中途被強行中止〉（Step 中斷的回滾規則；tool 中斷當工具失敗，副作用可能仍在）、〈整個實例被強制終止〉（不做收尾保證）。
- `CONTROLLER.md`〈最小 API〉、〈明確不負責〉（不做持久化、queue、lease、副作用 recovery：功能可抄，可靠性不能抄）。
- `LIMITS.md`〈內建 Limits 負責什麼〉：現成的停止條件清單（步數、工具次數、白名單、時間、token），透過 `after_step` callback；〈合作式限制〉。
- `threading/`、`limits/`：只用公開 API 的可選子專案，分層樣本。

**`freepy/llmkit/` — tool call 的協定形狀**

- `llms/TOOLS.md`〈工具〉：`reply.calls` 是 `[{"id": ..., "name": ..., "args": {...}}]`，結果以 `{c["id"]: ...}` 回填，一步可能多個呼叫——tool_call_id 的最小形狀。`args` 壞掉給空 dict 加 `args_raw`。〈欠著的工具呼叫〉`bot.pending_calls`；〈tool_choice：逼它叫工具〉。
- `tooljson/`：`FORMAT.md`、`EXEC.md`、`PYTHON.md` 是 `core/tooljson` 的 Python 參考實作；`invoke.py`、`args.py`、`exec_type.py`、`registry.py`、`text.py` 是 C++ S1 尚未實作的 `run` 那一半。
- `llms/USAGE.md`（token／成本欄位）、`live_smoke.py`（打真端點的冒煙腳本）。
