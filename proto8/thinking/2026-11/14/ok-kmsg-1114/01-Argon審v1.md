### (A) 審查意見（Review）

1. **`hooks.rejected(result)` 拿不到 `ctx.warn`，與「不動 `round.py`」矛盾**
   - **段落**：§一.2
   - **嚴重度**：**blocking**
   - **問題**：設計稿稱「只改 `hooks.rejected()`（`round.py` 那一行靠 `*` 展開，不必動）」，同時要求代號不在白名單或 `resets_at`／`window` 型別錯誤時呼叫 `ctx.warn`。但 `hooks.py:51` 的 `rejected(result)` 只有 `result` 一個參數，而 `hook_run.fire()` 回傳的 `result` 僅含 `data`、`changed`、`blocked`、`hook`、`text`（`hook_run.py:196`），沒有 `ctx` 或 `warn`。直接寫 `ctx.warn` 會 `NameError`。
   - **修法**：在 `hooks.fire()` 回傳前補 `result["warn"] = ctx.warn`（則 `round.py` 與 `after_verdict` 都不必改呼叫端），或改簽名為 `rejected(result, warn=None)` 並在 `round.py:104` 與 `hooks.py:79` 傳入 `ctx.warn`。

2. **`after_verdict` 的兩條拒絕路徑與設計稿敘述及測試預期不符**
   - **段落**：§一 現況、§一 測試
   - **嚴重度**：**important**
   - **問題**：
     1. `after_verdict` 退 0 回 `{"verdict":"refuse","error":{...}}` 時（`hooks.py:96-101`），不會自動補 `scope="hook"` 與 `hook=<名>`，也不會驗 `code` 白名單與 `resets_at`／`window` 型別；若測試預期這條路回信自帶 `scope="hook"`、`hook=名` 會失敗。
     2. `after_verdict` 的 hook 若退 10（`result["blocked"]`），`hooks.py:79` 也會呼叫 `rejected(result)`，設計稿漏列此路徑。
   - **修法**：明確區分 `before_verdict`／`after_verdict` 退 10（經 `rejected()`，自動補 `scope`、`hook`）與 `after_verdict` 退 0 改判（由 hook 自行給欄位，或統一抽共用 helper 驗欄位並補 `scope`、`hook`）。

3. **`brain_wait.json` 在「寄不出去」兩情形下沒有 `pending.txt`，會變永久殘留檔（Lifetime Bug）**
   - **段落**：§二.1
   - **嚴重度**：**blocking**
   - **問題**：設計稿規定「兩種寄不出去的情形也寫 `brain_wait.json`（`LlmKernelMissing`、`SendFailed`＋`KERNEL_GONE`）；刪 `pending.txt` 的每一處一併刪它」。但這兩種情形發生在 `if not name:` 分支（`wait.py:378-402`），**根本還沒寫 `pending.txt`**：
     1. `LlmKernelMissing` 退 1 後，使用者補好 `AOS_LLM_KERNEL` 重掛或重起 agent，在 agent 還在 `idle`／`think`（尚未進 `wait` 寄出新信）期間，`think/brain_wait.json` 仍留著舊的 `problem`；此時執行 `say` 或 `listen` 會誤報舊錯。
     2. `SendFailed` 冷卻期間若使用者改了 `llm.json`、改了 `history.jsonl` 或刪了 `request.json`，下一拍 `wait.py:356,366,375,377` 會直接 `sys.exit(REBUILD)`（退 11 回 `think`），不經任何刪 `pending.txt` 的路徑，`brain_wait.json` 永遠不會被刪。
     3. 下一拍若資料夾出現但 `aos-llm send` 因其他原因失敗（`gone` 為 `False`），舊的 `KERNEL_GONE` `brain_wait.json` 也不會被清掉。
   - **修法**：見 (B) 提案 1（不寫 `problem` 到 `brain_wait.json`）；若仍要寫，必須在 `wait.py` 進入 `if not name:` 開頭先刪舊的 `brain_wait.json`，且 `brain_hint(a)` 必須先核對 agent 當前狀態。

4. **`brain_wait.json` 未要求原子寫入，與 `listen`／`say` 存在讀寫競爭（Race Condition）**
   - **段落**：§二.1、§二.2
   - **嚴重度**：**important**
   - **問題**：`wait.py:390` 寫 `sent_path` 是直接 `open(..., "w")`（非原子），而 `pending` 用 `write_atomic`。若 `brain_wait.json` 直接 `open(..., "w")` 截斷寫入，`listen.py`（每拍輪詢）或 `say.py`（單次讀取）讀到半截 JSON 會靜默回 `None`，導致 `say` 或 `listen` 逾時漏印提示；反之若先刪 `pending.txt` 後刪 `brain_wait.json`，中間空窗或行程被殺也會留下孤兒檔。
   - **修法**：`brain_wait.json` 必須用同目錄暫存檔＋`os.replace` 原子寫入；在 `brain_hint(a)` 中比對 `brain_wait.json` 的 `"letter"` 與 `think/pending.txt` 內容一致才採信（不靠刪檔順序保證一致）。

5. **多種情境會誤報或重複印出「kernel 沒在跑」（False / Noisy Hints）**
   - **段落**：§二.2、§二.3、§二.4
   - **嚴重度**：**blocking**
   - **問題**：
     1. **Agent 自身已停、暫停或不在 `wait`**：當 agent 因 `LlmKernelMissing` 退 1 停在表上、被 `ctl stop`／`pause`／`sleep`，或剛重起還在 `idle` 時，`say.py:55-58` 與 `listen.py:86-98,110-116` 已經會印 `run_hint(a)`（含 daemon 記下的 `LlmKernelMissing` reason）或 `say_paused()`。若 `brain_hint(a)` 不看 agent 狀態就印，會重複印兩行甚至在 agent 根本沒在跑時怪罪 kernel。
     2. **`listen.py` 共用 `warned` 變數會每秒刷屏**：`listen.py:111` 在 `stages` 非空且 `on_table(a)` 為真時，每秒會把 `warned = False` 重置！若 `brain_hint` 共用 `warned` 旗標，信在 `queue/new/` 或 `cur/` 時每秒都會重印一次提示。
     3. **Python 檢查 `pid` 存活的兩個坑**：`send.cpp:15` 把 `::kill(pid, 0) == 0 || errno == EPERM` 視為活著，且 `is_number_integer()` 排除 `bool`。在 Python 中：
        - 若 kernel 屬於不同 Unix 使用者，`os.kill(pid, 0)` 會丟 `PermissionError`（`EPERM`，屬 `OSError` 子類）；若照設計稿「任何錯誤回 None 或當死掉」一併捕獲 `OSError`，跨使用者的活 kernel 會被誤判為 `pid gone`。
        - Python 的 `isinstance(True, int)` 為 `True`，且 `pid <= 0` 時 `os.kill(0, 0)` 會對自身 process group 發訊號。
     4. **用 `aos_flags.read_window` 讀 `<kernel>/state.json` 會違反「壞 JSON 安靜」**：`hints.py:16` 用的 `read_window` 遇到壞 JSON 會直接往 stderr 印 warning 並回 `None`（與檔案不存在無法區分，會誤報 `no state.json`）。
     5. **回信已到 `think/reply/new/<letter>` 但 `wait.py` 尚未收信**：若 kernel 答完最後一題後停機，而 agent 下一拍還沒跑完 `recv`，信其實已到，不應報 kernel 未啟動。
   - **修法**：
     - `brain_hint(a)` 僅在 `on_table(a)` 為真且 `label(a) == "running"`、無回信躺在 `think/reply/{new,cur}/<letter>` 時才檢查 kernel。
     - `listen.py` 獨立設 `brain_warned = False`；逾時只在信已進 agent（或確認該 agent 卡在等腦）時才附加提示。
     - Python 驗 PID：`isinstance(pid, int) and not isinstance(pid, bool) and pid > 0`，`os.kill(pid, 0)` 捕獲 `ProcessLookupError` 為死、`PermissionError` 為活。
     - 直接用 `open` + `json.load` 讀 `state.json`：只有 `FileNotFoundError` 報 `no state.json`，`ValueError`／其他 `OSError` 回 `None`。

6. **既有 hook 若退 10 且 stdout 恰為含 `error` 的 JSON，會破壞相容性並洩漏未驗證欄位**
   - **段落**：§一.2
   - **嚴重度**：**important**
   - **問題**：設計規定「`code` 不在白名單 → 仍回 `HookRejected`，`msg` 用 `error.msg`，其餘鍵照帶」。既有 hook 若直接把外部工具／API 的錯誤 JSON（如 `{"error":{"code":"bad_req","msg":"...","raw":...}}`）印到 stdout 並退 10，原本 `extra` 為空、全文進 `msg`；新設計卻會把 `error` 內未經驗證的任意鍵塞進回信頂層 `error`（且非 `BudgetMissing` 時連 `resets_at`／`window` 型別都不驗）。
   - **修法**：`code` 不在白名單時，只 `ctx.warn` 並回 `("HookRejected", error["msg"])`（或退回整段 stdout 原文），**不要帶入 `extra` 其餘鍵**。

7. **讓 hook 任意帶 `extra` 與 `"window": "all"` 的濫用與副作用**
   - **段落**：§一.2、§一.3
   - **嚴重度**：**important**
   - **問題**：
     1. 設計寫「`scope`（hook 沒給才補 `"hook"`）」，代表 hook 可偽造 `"scope": "account"`、`"limit"` 等欄位混淆除錯。
     2. 設計 §一.3 教 hook 用 `"window": "all"` 讓 agent 停下，但 `wait.py:459-460` 對 `BudgetMissing` + `window == "all"` **不記冷卻**就直接 `die("BudgetMissing", "... (window all: it never resets; raise the budget...)")` 退 1。這不僅印出誤導人的「raise the budget」，還會害開了 `auto_restart` 的 agent 因沒有冷卻保護（見 `wait.py:32` 註解）在 3 秒內連續重試 3 次被打成 crashed 停死；而原本的 `HookRejected`（退 10 純文字）本來就會記 `BrainFailed` 冷卻並退 1 停下！
     3. `wait.py:285` 的 `kernel_dir()` 沒對 `AOS_LLM_KERNEL` 做 `.strip()`，若環境變數頭尾有空白會與 `wait.py:378` 不一致。
   - **修法**：`scope` 與 `hook` 一律強制覆寫為 `"hook"` 與攔截的 hook 名；`BudgetMissing` 的 `extra` 只白名單放行 `resets_at`、`window`；移除教 hook 用 `"window": "all"` 的設計，要 agent 停下直接回 `HookRejected`。

8. **`listen.py`／`hints.py`／`say.py` 存檔即活樹生效的部署順序風險**
   - **段落**：§二.7、§三
   - **嚴重度**：**important**
   - **問題**：`proto8/cmd/aos-agent/aos_agent/` 在活樹直接被執行。若先改 `listen.py` 或 `say.py`（加入 `from .hints import brain_hint`），在 `hints.py` 尚未寫入完成的瞬間，活樹上任何呼叫 `aos-agent` 的行程都會 `ImportError`；若直接覆寫檔案而非 `os.replace`，並發 import 會讀到半截檔案 `SyntaxError`。
   - **修法**：三個檔案皆須在同一目錄寫暫存檔再 `os.replace`，且嚴格依 **先 `hints.py` → 測試 import → 再 `listen.py`、`say.py`** 的順序上線。

9. **測試缺口（Test Gaps）**
   - **段落**：§一 測試、§二 測試
   - **嚴重度**：**minor**
   - **問題**：缺 (1) `after_verdict` 退 10 回 `BudgetMissing` JSON；(2) hook 試圖偽造 `hook`／`scope` 鍵時被強制覆蓋；(3) `<kernel>/state.json` 為 `phase: "waiting"`／`"stopping"` 或跨使用者 `EPERM` 時不誤報；(4) `pid` 為 `bool` 或 `<= 0` 的防呆；(5) agent 本身 paused／stopped 或 `wait.py` 退 11（`REBUILD`）時不誤報。

---

### (B) 更簡單或更安全的替代方案（Proposals）

1. **簡化 `brain_wait.json`：只綁定 `pending.txt`，不存 `problem`、不靠多處同步刪檔**
   - **作法**：
     1. 取消「寄不出去也寫 `brain_wait.json`（`problem`）」：
        - `LlmKernelMissing` 本來就退 1 停下，daemon 表上的 `reason` 已有完整原因，`listen`／`say` 現有的 `run_hint(a)` 就會直接印出，無須重複機制。
        - `SendFailed`＋`KERNEL_GONE` 本來就會寫入 `$AOS_STACK/cooldown.json`（含 `KERNEL_GONE` 字串），若想提示，在 `brain_hint(a)` 直接讀既有的 `cooldown.json` 即可，完全不必多管一個檔案的生命週期。
     2. `wait.py` 只在 `write_atomic(pending, name + "\n", die)` 前後，原子寫入 `think/brain_wait.json`：`{"letter": name, "kernel": os.path.abspath(kernel_dir())}`。
     3. `hints.py` 的 `brain_hint(a)` 先檢查：`on_table(a)` 且 `label(a) == "running"`，再讀 `think/pending.txt` 取得 `name`，讀 `think/brain_wait.json` 確認 `bw.get("letter") == name`，且 `think/reply/new/<name>` 不存在，才檢查 `<kernel>/state.json`。
   - **好處**：就算 agent 被強殺、`reset` 或 `wait.py` 退 11 回 `think` 沒刪到 `brain_wait.json`，只要 `pending.txt` 不在或信名換了，`brain_hint(a)` 自然安靜，徹底消除所有殘留檔與刪檔漏網之魚。

2. **收緊 `hooks.rejected()` 的 JSON 規格與白名單**
   - **作法**：
     1. 在 `hooks.fire()` 結尾加一行 `result["warn"] = ctx.warn`，不動 `round.py`。
     2. `hooks.rejected(result)` 只認 `error.code == "BudgetMissing"`（要回 `HookRejected` 用既有純文字即可，不必繞 JSON）；若 `error.code` 是其他值，只 `warn` 一行並回 `("HookRejected", error["msg"])`，**不帶任何 `extra`**。
     3. 當 `error.code == "BudgetMissing"` 時，`extra` 只從 `error` 取白名單鍵 `("resets_at", "window")`（且若 `window == "all"` 則拒絕並轉為 `HookRejected` + `warn`），最後強制覆寫 `extra["scope"] = "hook"`、`extra["hook"] = result["hook"]`。
   - **好處**：避免污染 `HookRejected` 回信結構、防止 hook 偽造 `scope` 或用 `window: "all"` 破壞 `auto_restart` 冷卻機制，且實作不到 20 行。
