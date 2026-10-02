← [3. 兄弟專案裡可以抄的](../19-3-兄弟專案裡可以抄的.md)（分檔 2/2）｜[上一份](01-freepy-agentloop.md)

**`freepy/base_tools/` 與 `freepy/exec_tools/` — 具名 registry 的兩種來源**

- **`freepy/base_tools/tools.json`**：一份完整的 OpenAI function schema 陣列（`read_file`／`write_file`／…），每個都帶 `_extra`（`_version: "0.1.0"`、`_type`、`module`／`attr`、以及 `source.size`／`mtime`／`sha256`）。要手寫 `tools.json` 的人可以直接照這份的形狀寫，**含 stale 偵測要的那三個欄位**。實作在 `freepy/base_tools/specs.py`、`files.py`、`edits.py`、`paths.py`、`shell.py`。
- **`freepy/exec_tools/README.md`**：從使用者明確指定的目錄讀 `.specs/*.json` 組成 `(schemas, dispatch)` 的薄 discovery 層——`tools(paths)`、`scan()`（回 `specs`／`missing`／`errors`）、`spec_path(executable)`。〈邊界〉那節寫明「**沒有 spec 的可執行檔不會暴露給模型**」「壞 spec 會丟 `DiscoveryError`，避免能力集合悄悄缺一塊」「不同目錄同名時先指定的優先，像 `PATH`」。〈它不保證什麼〉明寫 discovery 不是 permission 或 sandbox——正好對到 Pike 那個 `../../../../usr/bin/id` 的現場。實作在 `freepy/exec_tools/discover.py`。

**`freepy/adapters/pi/` — pi 這一側的既有介面**

- **`freepy/adapters/pi/pi_bridge.py`**：一支以 **JSONL over stdin/stdout** 當協定的 server，由 pi extension 起 child process 控制一個獨立的 agentloop Round。**`freepy/adapters/pi/check_pi_bridge.py`** 是完全離線的 subprocess protocol check（`uv run python adapters/pi/check_pi_bridge.py`），可以直接拿來當「一支子行程用 JSONL 對答」的最小可跑樣本。`pi-agentloop.ts` 是 extension 與 child lifecycle 那一側；`examples/minimal_factory.py` 是 deterministic factory。

**`agent-machine/` — 崩潰、unknown 與 recover 的設計文字與可跑原型**

- **`agent-machine/full/06-AOS-LIFECYCLE-AND-RECOVERY.md`〈recover 完，才可以 ready〉**：六步恢復次序，其中第 4 步一字不差就是這輪的坑——「**已有 dispatch intent 而結果證據不完整時，標為 unknown，不啟動舊工作、不重送外部作用，也不接回一個猜測中的 PID**」；第 5 步是 fail closed。〈新啟動世代要隔離舊工作〉那句「**取得中央 store 的鎖，也不等於舊 process tree 已停止**」正是 `.runi` 與孤兒的關係。〈drain 不等於 checkpoint〉區分停在安全續接點、等待受管理 process、與外部作用不明三種狀態。
- **`agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉**：同目錄 temp、write-all、file fsync、atomic rename、directory fsync 的完整文字基線。〈結果不明不是失敗，也不是重試許可〉：已有 intent、缺可信結果就停在 unknown，**不自動建立新 attempt**。
- **`agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉**：「可唯一推導就補回；仍有兩種可能就不猜」，以及〈小原型該回答什麼〉裡「effect 後殺 manager、重開不得重送」的驗收條件。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish(path, data, replace_staging=False)` 與 `fsync_directory(path)`**：可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync；遇到同內容既有 target 直接返回、不同內容則拒絕。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind(call, attempts)`**：「完整證據才 commit receipt、不完整證據維持 unknown」的三態判讀樣本，配 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()`。
- **`agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()`**：effect 落盤後殺掉 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`，**重跑 recover 不增加 effect**——這是 p3 那個「偵測到孤兒還活著、拒絕動作」實驗的既有測試樣本。範圍與限制寫在同目錄 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉與〈明確未驗，不可外推〉。
- **`agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`／`_terminal()`／`recover(invocation_id)`**：receipt JSON、receipt-ready、terminal 分三步；**receipt 完整時 recover 只補後續 marker，不再執行 effect**——p1 那支 `recover.sh` 可以直接照這個判斷順序寫。
- **`agent-machine/full/10-STEP-TOOL-ROUND.md`〈Tool 到 leaf process 的三種常見接法〉**：小型參數／結構資料／大型或二進位資料三種傳法——這是「transcript 長起來要不要走 stdin 或走檔案」那條 ARG_MAX 論證真正該查的地方。同檔〈錯誤分層〉與〈一個 Tool Call 可以展開多個 Functions〉。
- **`agent-machine/full/02-LEAF-PROCESS-CALL.md`〈已知結果不等於成功〉與〈證據與結果不明〉**：leaf process 呼叫的三態（成功／已知失敗／證據不明）文字基線。

---
