← [3. 兄弟專案裡可以抄的](../19-3-兄弟專案裡可以抄的.md)（分檔 2/2）｜[上一份](01-freepy-agentloop.md)

**`freepy/base_tools/` 與 `freepy/exec_tools/` — 具名 registry**

- `freepy/base_tools/tools.json`：完整的 OpenAI function schema 陣列，每個帶 `_extra`（`_version`、`_type`、`module`／`attr`、`source.size`／`mtime`／`sha256` 供 stale 偵測）。實作在 `specs.py`、`files.py`、`edits.py`、`paths.py`、`shell.py`。
- `freepy/exec_tools/README.md`：從使用者明確指定的目錄讀 `.specs/*.json` 組成 `(schemas, dispatch)`——`tools(paths)`、`scan()`、`spec_path(executable)`。〈邊界〉：沒有 spec 的可執行檔不暴露給模型、壞 spec 丟 `DiscoveryError`、同名先指定者優先。〈它不保證什麼〉：discovery 不是 permission 或 sandbox。實作 `discover.py`。

**`freepy/adapters/pi/` — pi 這一側**

- `pi_bridge.py`：JSONL over stdin/stdout 的 server；`check_pi_bridge.py` 是離線的 subprocess protocol check（`uv run python adapters/pi/check_pi_bridge.py`）；`pi-agentloop.ts`、`examples/minimal_factory.py`。

**`agent-machine/` — 崩潰、unknown 與 recover**

- `full/06-AOS-LIFECYCLE-AND-RECOVERY.md`〈recover 完，才可以 ready〉：六步恢復次序，第 4 步——已有 dispatch intent 而結果證據不完整時標為 unknown，不啟動舊工作、不重送外部作用、不接回猜測中的 PID；第 5 步 fail closed。〈新啟動世代要隔離舊工作〉（拿到鎖不等於舊 process tree 已停）、〈drain 不等於 checkpoint〉。
- `full/05-DURABLE-STATE.md`〈持久屏障〉（temp、write-all、fsync、atomic rename、directory fsync）、〈結果不明不是失敗，也不是重試許可〉。
- `full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉、〈小原型該回答什麼〉。
- `workbench/2026-08-14/p1a2-process-python/`：`p1a2_store.py` 的 `atomic_publish(...)`、`fsync_directory(path)`；`p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind(call, attempts)`（配 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()`）；`test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()`（重跑 recover 不增加 effect，是「孤兒還活著就拒絕」的既有樣本）；範圍見 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉〈明確未驗，不可外推〉。
- `workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`／`_terminal()`／`recover(invocation_id)`：receipt 完整時 recover 只補 marker、不再執行 effect，`recover.sh` 可照這個判斷順序寫。
- `full/10-STEP-TOOL-ROUND.md`〈Tool 到 leaf process 的三種常見接法〉（ARG_MAX 問題該查這裡）、〈錯誤分層〉、〈一個 Tool Call 可以展開多個 Functions〉。
- `full/02-LEAF-PROCESS-CALL.md`〈已知結果不等於成功〉〈證據與結果不明〉。
