**必修**

以下共 7 項。全程未改檔、未跑模型、未開 daemon／kernel，也未連 localhost。兩組單元測試都因唯讀環境無法建立暫存目錄而停在 `setUp`；下述數字來自不寫檔的 `plan()` 重現。

- **M1｜清 archive 沒拿鎖，可能刪掉壓縮正在引用的原文。**  
  [aos_agent_compact.py:340](../../lib/aos_agent_compact.py)：`prune()` 與 `apply()` 沒有互斥。例如 compact 已寫 archive、尚未換 history，此時執行 `--prune-archive 0`，prune 讀到舊 history，判定新 archive 沒被引用而刪掉；compact 接著寫入指向不存在 archive 的說明行。  
  **改法：** prune 也持 `.tick.lock`，拿鎖後才讀 history、列 archive、刪檔。

- **M2｜`plan()` 不是不動點，破壞換完 history 後的恢復保證。**  
  [aos_agent_compact.py:180](../../lib/aos_agent_compact.py)：是否壓縮取決於說明行長度，但說明行包含會隨壓縮改變的訊息索引。  
  **已重現：** 30 輪，每輪 `user → assistant(read) → tool → assistant`，前 28 輪工具結果各 1000 字、後兩輪各 105 字，`keep_rounds=1`、無上限。第一次第 29 輪因 `small` 保留；第二次索引位數縮短，又壓縮該輪，**7144 → 875 → 874 token**。所以在 `compact.history` 後崩潰，重跑可能再改記憶、再建 archive。  
  **改法：** 用與當前索引無關的固定成本決定是否值得替換，並補這個邊界測試；需一起驗證封存與無最後回話的輪。

- **M3｜封存沒有「不能越縮越大」檢查。**  
  [aos_agent_compact.py:192](../../lib/aos_agent_compact.py)：普通壓縮有比較 token，`seal` 卻直接換。  
  **已重現：** 舊輪只有 `q／a`，最近一輪回答是 1000 個 ASCII 字元；`keep_rounds=1, max_tokens=100`，記憶由 **253 增為 281 token**，還刪掉了原本很短的問答。  
  **改法：** 封存候選區段也比較替換前後成本；相連輪可合併評估，不值得換就保留並回報仍超限。

- **M4｜compact 申請的去重有並行窗口。**  
  [aos_agent_compact.py:494](../../lib/aos_agent_compact.py)：先查 `done/`，再 `drop_new()`，中間 tick 可以把原申請搬走。郵差重試若恰好先查到「尚未 done」，tick 隨後完成搬移，郵差便能重新投進同 id，讓已處理申請再執行。現有測試只涵蓋循序重投。  
  **改法：** 用投遞與消費共用的短鎖，或永久、原子建立的投遞憑據；補交錯執行測試。

- **M5｜任務完成後，自動壓縮可能永遠沿用「不能縮」的舊判斷。**  
  [aos_agent_compact.py:391](../../lib/aos_agent_compact.py)：skip key 只有記憶 sha、keep、limit，但能不能縮也取決於任務狀態。任務從 `working` 變 `done`，或原本讀不到的任務檔恢復，記憶沒變就仍被直接跳過。  
  **改法：** key 納入相關任務狀態快照，或在命中 skip 時重新檢查那些受保護任務。

- **M6｜notes 的相對設定路徑，關牢後工具與人會看不同檔案。**  
  [tools/notes/_common.py:126](../../tools/notes/_common.py) 與 [aos_agent_notes.py:55](../../lib/aos_agent_notes.py)：例如 `config.file="notes/notes.json"`，工具相對牢裡 cwd（例如 `/work/ws`），CLI 卻相對 agent 家。工具寫成功，人可能看到空表。另以「有 access.json」推定 note 一定關牢，也漏掉 `_jail:false`。  
  **改法：** 統一路徑契約；關牢時至少要求明確的 `/work/<mount>/…`，或由 CLI 正確映射工具 cwd。補實際路徑往返測試。

- **M7｜全部工具都不存在的 act 批，崩潰重播無法去重。**  
  [aos_agent_events.py:48](../../lib/aos_agent_events.py)：這種批所有 `name=None`，`batch_id()` 回 `None`，而 `dedupe()` 刻意不去重 null。事件寫完、state 提交前崩潰，就會把同一批重算成多批，起訖也沒有可靠配對鍵。  
  **改法：** 建批時把已有的 `identity` 存進 batch，事件使用該固定 id，不從工作名反推。

**建議**

- **S1｜縮小「至少一次」的承諾範圍。** `append_line()` 失敗會直接丟事件，這符合「量測不能拖垮 tick」，卻不能同時宣稱永遠不會做了沒記。此外未檢查 `os.write()` 短寫；殘行接上下一筆可能連下一筆一起被跳過。應明列 I/O 失敗例外，處理短寫／殘行。
- **S2｜任務狀態應先讀成固定快照。** 現在 `plan()` 呼叫的 `status()` 會即時讀檔，郵差不受 tick 鎖限制；archive 後崩潰、重跑前任務狀態改變，就不保證算出相同結果。另「讀不到算未完成」、`failed` 保留都偏保守，可能長期縮不下去；宜在輸出列出阻擋單號。`TASK_RE` 也會漏掉緊貼中文字的 `請處理t-0001`。
- **S3｜補足設定與原因的可觀察性。** `auto()` 註解說壞設定由 `check` 查，但目前 check/info 沒接 compact 設定驗證；壞設定可能靜默停用。另外 `_request_opts()` 沒把申請的 `reason` 帶進事件，與新規範不符。
- **S4｜notes 讀驗沒有真正驗完整 `wf-table/1`。** 目前只查 `rows`、`key`、`text`，錯誤 contract、columns、非字串 tags 仍能進來。建議拒絕錯誤格式，避免讀取時才出 `InternalError`。
- **S5｜補異常記憶與 dry-run 的一致性測試。** `check_pairs()` 能拒絕留下來的孤立 tool、user 插在未收齊結果中間等問題；但 `apply()` 在 dry-run 或無變更時先返回，沒有跑這個檢查。預覽可能成功，正式壓縮卻失敗。說明行用 `user` 符合目前規範，但會併入下一段連續 user，輪數不再等於原始輪數，應明確測試。

**確認沒問題的**

- 正式 compact 與 tick 自動路徑有持 tick 鎖；自動路徑沒有重拿鎖，且有檢查 idle、batch、intake。有待收輸入時先不縮。
- archive 與 history 都透過暫存檔再 rename；就 **SIGKILL 行程崩潰**而言，history 保持完整舊版或新版。重跑結果相同的承諾仍受 M2 影響。
- start、end、intake 都在對應 state 提交前記事件，state 留有重播依據；compact 在換 history 前記事件。一般寫事件失敗不會拖垮 tick。
- usage 的 `finally` 符合新規範：收到 2xx JSON 物件，即使 message 驗證失敗仍記；HTTP 失敗、非 JSON 不誤記。`AOS_LLM_BATCH` 是環境疊加，不會清掉 llm cpu 原本的金鑰與設定。
- 申請的 human 跨成員權限、數值範圍、額外欄位拒絕，以及正常循序去重都有實作。note 的 add/rm 有完整 flock 讀改寫；預設 `/work/notes/notes.json` 與 CLI 掛載換算一致。

驗收八條的**測試證據審查**如下；不是本次測試通過紀錄：

| 條目 | 判斷 |
|---|---|
| ① context 一致 | 有整段輸出比較，兩邊共用函式。 |
| ② events／usage | 有一般批次與假 HTTP 測試；漏 M7。真跑用量只有交付報告記載，本次未重驗。 |
| ③ dry-run 不改檔 | 有整棵目錄內容與 mtime 比較。 |
| ④ 合法、成對、archive、上限 | 有標準案例；不能證明所有情況，漏 M2、M3。受保護內容過大時本來就無法保證低於上限。 |
| ⑤ 未完成任務保留 | 有 working、done、查無任務案例；漏任務完成後解除 skip。 |
| ⑥ KILL 窗口 | **確實使用 SIGKILL**，掛鉤位於 archive 寫完、history 替換之前，並與未崩潰副本比較；不是只丟例外。 |
| ⑦ 鎖與自動壓縮 | 有持鎖拒絕、非 idle 拒絕、子行程 timeout 防死鎖測試。 |
| ⑧ 真模型壓縮後問答 | 單元測試不能證明；交付報告記載 deepseek 真跑 10 次，本次依限制未重驗。 |