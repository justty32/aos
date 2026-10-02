# tick spec 與程式一致性 審查（astra，2026-10-02）

## 一段話結論

核心正常流程大致一致，未找到確定的執行 bug。必修集中在兩處格式驗證落差，以及幾處仍描述舊行為的文件。建議沿用現行程式修正 schema、驗證器與文字，不增加 POC 邊緣處理。本次只讀，沒有跑測試。

## 必修

1. **schema 會拒絕程式支援的 `id`／`kind` 指示詞。**  
   [tick-tasks.schema.json:483](../../../../proto6/spec/protocol/schemas/tick-tasks.schema.json) 兩欄只收字串，但 [aos_tick_table.py:183](../../../../proto6/src/py/lib/aos_tick_table.py) 會展開它們。[test_tick_kind.py:70](../../../../proto6/src/py/tests/test_tick_kind.py) 更明確使用 `kind:{"$env":"AOSTEST_KIND"}`。  
   **改法：** schema 接受原有字串格式或 `ValueDirective`，補同款正例。

2. **驗證器會把正常執行中的紀錄判錯。**  
   [validate.py:73](../../../../proto6/spec/protocol/examples/messages/validate.py) 要求 hook 的 `task_index < ran＋skipped筆數`。但 [aos_tick.py:177](../../../../proto6/src/py/lib/aos_tick.py) 先跑 `before_kind`，任務完成才增加 `ran`。第一個 hook 回非零時，合法紀錄就是 `task_index=0、ran=0`。另外，[aos_tick_record.py:144](../../../../proto6/src/py/lib/aos_tick_record.py) 的跳過紀錄只在收尾落盤，也會讓後續任務的位置超過當下界限。  
   **改法：** 上限關係只驗 `ended:true`；進行中只驗型別與排序。同步 [協議:170](../../../../proto6/spec/protocol/tick.md) 與 [_tick_util.py:81](../../../../proto6/src/py/tests/_tick_util.py)。

3. **指示詞的展開規則有三處寫錯。**  
   [tick.md:22](../../../../proto6/spec/tick.md) 寫「先合併再展開」，實際是開格先展開，執行各項時才合併。[conventions.md:65](../../../../proto6/spec/conventions.md) 漏了每項陌生鍵也不展開；[協議:56](../../../../proto6/spec/protocol/tick.md) 說未知模組忽略，但它們的內容仍會展開。程式證據分別在 [aos_tick_table.py:106](../../../../proto6/src/py/lib/aos_tick_table.py)、[183](../../../../proto6/src/py/lib/aos_tick_table.py)、[240](../../../../proto6/src/py/lib/aos_tick_table.py)。  
   **改法：** 改成「開格展開已知內容，跑各項時再合併」；說清楚陌生欄位不解、未知模組仍展開但不執行。刪掉 [schema:5](../../../../proto6/spec/protocol/schemas/tick-tasks.schema.json) 同樣過時的逐項展開說法。

4. **hooks 文件漏掉 `before_kind` 的任務環境變數。**  
   [hooks.md:16](../../../../proto6/spec/tick/hooks.md) 說只有三個 after 掛點拿到 `AOS_TASK_*`。實際 [aos_tick_hooks.py:55](../../../../proto6/src/py/lib/aos_tick_hooks.py) 也給 `before_kind` 任務 ID、INDEX；[test_tick_kind.py:55](../../../../proto6/src/py/tests/test_tick_kind.py) 明確驗證。  
   **改法：** 補上 `before_kind` 有 ID、INDEX，沒有 EXIT；或直接指向已寫對的 [協議:91](../../../../proto6/spec/protocol/tick.md)。

5. **版本慣例誤稱任務表頂層會驗版本。**  
   [conventions.md:17](../../../../proto6/spec/conventions.md) 說 inst 與 tasks 只認 `posix/1`，不合就拒絕。但 [test_tick_table.py:235](../../../../proto6/src/py/tests/test_tick_table.py) 明確要求頂層 `_type:"nope", _version:9` 仍能跑。  
   **改法：** 分清楚「inst／任務項照 inst 驗版本」與「任務表頂層 `_metainfo` 不看」。

6. **`aos-exec` 找目標表把普通執行檔也說成 JSON。**  
   [inst.md:19](../../../../proto6/spec/inst.md) 說檔案一律當 inst JSON 讀。但 [aos_exec.py:164](../../../../proto6/src/py/lib/aos_exec.py) 只把 `.json` 當 inst，其他普通檔案直接執行；[test_exec_targets.py:20](../../../../proto6/src/py/tests/test_exec_targets.py) 有對應案例。  
   **改法：** 表格拆成 `.json` 與其他普通檔案，或刪表改指程式。

7. **`busy` 是否印 stderr，通則與程式相反。**  
   [conventions.md:26](../../../../proto6/spec/conventions.md) 把 busy 列為正常中斷，並說正常結束不印 stderr。[aos_tick.py:136](../../../../proto6/src/py/lib/aos_tick.py) 實際印 `busy:`；[鎖測試:142](../../../../proto6/src/py/tests/test_tick_target.py) 也明定此行為。  
   **改法：** 文件列出 busy 例外，保留程式。

8. **schema 說明仍保留舊版 hooks 規則。**  
   [tick-tasks.schema.json:5](../../../../proto6/spec/protocol/schemas/tick-tasks.schema.json) 還說只開 `after_all`；[tick-record.schema.json:265](../../../../proto6/spec/protocol/schemas/tick-record.schema.json) 還說 hooks 只在 `ended:true` 出現。實際已有六個掛點，且 [aos_tick_record.py:105](../../../../proto6/src/py/lib/aos_tick_record.py) 開格就寫 hooks，此時 `ended:false`。  
   **改法：** 刪除舊行為敘述，description 只留欄位用途。

## 建議

- **範例與實際輸出共用跨欄位驗證。** [_tick_util.py:67](../../../../proto6/src/py/tests/_tick_util.py) 與 [validate.py:45](../../../../proto6/spec/protocol/examples/messages/validate.py) 各寫一份規則，前者沒有後者的 hook 位置檢查。共用後，再補「任務還在跑」的紀錄案例，能避免兩邊各自通過卻互不一致。

## 疑問

無需新增方向題。以上都有程式或測試依據，可沿用現行行為修正。

## 看過的範圍

- `AGENTS.md`、使用者偏好。
- 指定的 `README`、`conventions`、`terms`、`inst`、`tick`、`tick/` 與 tick 協議。
- `tick-tasks`、`tick-record`、`inst`、`common` schema，tick 正反例與驗證器。
- `bin/aos-tick`、`aos_tick*.py`、`aos_inst.py`、`aos_directives*.py`、`aos_exec*.py` 及相關測試。

全程未改檔、未 commit、未執行測試。