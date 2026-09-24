整體合併保留了合併前 proto5 的 agent CLI、工具、權限功能，以及 `kernel_checks／finish`、舊 `check --agent` 用法錯訊息、`stderr_hint` fallback、health broken 退 1；proto5-2 的逐池 daemon 檢查、envs.json、三池 count 0 警告、agent 專屬 llm 池檢查與 `ls --pool` 的 NotFound 也在。拆檔核心經 AST 對照，未發現非預期邏輯變更；未找到刪除名稱的殘留呼叫、失效 patch 或 import 循環。仍有下列 **3 項必修、1 項建議**。本次以 `ef29b7c`（合併前共同祖先）至 `46f28d8` 為主，避免把 main 後續新增功能誤判為被覆蓋；工作樹另有教程與模板修改。全程未修改檔案，僅做靜態比對、`python -B` 匯入與記憶體測例，未重跑會建立檔案的完整測試。

1. **P1｜必修：多 daemon 時，LLM 檢查使用錯誤 daemon 的環境**

   **位置：** `proto5/lib/aos_kernel_check.py:335`、`:351`、`:251`。

   **問題：** `kernel_checks()` 只取得 kernel 池 daemon（或 `--daemon-target`）的一份環境，再拿它檢查所有 LLM 池；`aos-agent check` 也將同一份環境傳給 `agent_model()`。但每池可以指定不同 daemon，池 envs 的 `$env` 應在實際啟動該池的 daemon 環境中解析。

   **重現／推理：** kernel 池指定 `/Dkernel`，llm 池指定 `/Dllm`，後者設定：
   ```json
   {"AOS_LLM_CONFIG": {"$env": "LLM_PATH"}}
   ```
   兩個 daemon 的 `LLM_PATH` 不同。記憶體測例確認 llm 池收到的是 `/Dkernel/llm.json`，不是 `/Dllm/llm.json`。因此可能錯報設定缺失、檢查錯模型，甚至讓 `--probe` 打到錯誤 endpoint。這是沿用 proto5-2 的既有缺口，並非拆檔造成。

   **建議改法：** 按 daemon 家快取環境，LLM 檢查依該池的 daemon 選取；agent 模式也使用其 `llm.pool` 對應環境。補兩個 daemon 同名環境變數值不同的測例。

2. **P2｜必修：`ls --json` 第 2 版的未宣告池數值與規範表不一致**

   **位置：** `proto5/lib/aos_kernel_rows.py:65`；`proto5/spec/kernel/cli-ls.md:75`。

   **問題：** 規範把未宣告或不適用的計數描述為 `null`，實作卻在 `entry is None` 時輸出 `busy: 0`，包括尚未宣告的 kernel 池。

   **重現／推理：** 對有 info、尚未 boot 的快照呼叫 `ls_data()`，已確認輸出：
   ```json
   {"want": 1, "sent": null, "busy": 0, "idle": null, "draining": null}
   ```
   宣告後 kernel 池的 `busy` 又變成 `null`。消費者若按規範區分「已知為零」與「不適用」，會得到不同判斷。

   **建議改法：** 明確定義每個計數的缺省語意並同步實作與規範。若維持 proto5-2 行為，規範應逐欄寫明 `want` 仍取設定、未宣告池 `busy=0`，避免把五個欄位概括成同一條 null 規則；補未 boot 與新增尚未宣告池的 JSON 契約測例。

3. **P3｜必修：`aos-agent check` 規範仍承諾已移除的 daemon 選取規則**

   **位置：** `proto5/spec/aos-agent/cli-check.md:23`、`:30`；`proto5/lib/aos_kernel_check.py:291`、`:335`。

   **問題：** 規範仍寫 daemon 依 `AOS_DAEMON_HOME → info.daemon → cwd` 選取；實作已改成逐池查 daemon，沒有這套 fallback。規範也把 `llm/<池>` 排在完整 kernel 檢查段，實際是在 agent 讀驗與三個池項之後才查。

   **重現／推理：** 設 `AOS_DAEMON_HOME=/Dother`，K 的池均指向 `/Dactual`；實作只查池表中的 `/Dactual`，環境變數不會改變選取。若池解不出 daemon，則報 bad，不會退回 cwd。

   **建議改法：** 依這次池式納入方向修正文檔：daemon 逐池查、PATH 預設取 kernel 池 daemon；LLM 只查 agent 的 llm 池，並把列印順序寫成實際順序。不要為遷就舊文字恢復單一 daemon 模型。

4. **P4｜建議：`aos-agent init` 成功提示被換回 proto5-2 的舊入口**

   **位置：** `proto5/lib/aos_agent_init.py:35`。

   **問題：** 此次合併把原本指向 proto5 文件的提示改成 `proto5-2/README.md`「十分鐘上手」第 2 段。功能仍能執行，但使用 proto5 的人會被導到已納入的另一份原型文件。

   **重現／推理：** 成功執行 `aos-agent init` 即固定印出該路徑；diff 確認這是此次帶入的文字變更。

   **建議改法：** 改指向 proto5 現行模型設定教程的明確檔名，例如 `proto5/tutorials/03-first-agent.md`。