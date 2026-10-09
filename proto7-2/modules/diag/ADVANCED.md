# diag 進階

← [README（第一次用看這裡）](README.md)

## 出錯與退出碼

出錯時 stderr 印一行 `aos7-diag: <發生什麼>。<怎麼辦>`；stdout 空。退出碼意義全 aos 共用，見 [blueprint-errors §2](../../notes/blueprint-errors.md#2-統一退出碼表全-aos-共用只有五個)。

- **0** 診斷完成，stdout 印 JSON；`--help` 印用法。
- **2** 參數不對、`--llm` 的 node 或 `<root>` 不是資料夾、`--llm` 給的資料夾底下沒有 `.aos`／`llmcall`／`budget`／`jobs`／`author` 任何一個（看起來不是 node；舊 llmdiag 這時印三張空表）；什麼都沒讀，訊息會說哪個參數錯並附例子。（`<root>` 是資料夾但還沒有 `.aosd/` 時照舊退 0、`nodes` 為空。）
- **3** 不確定：讀取故障（權限、I/O、符號連結迴圈；`.aosd/nodes.json`／`status.json` 讀不到或壞了也算），什麼都沒寫；修好存取後照原樣再跑一次。

舊入口 `modules/llmdiag/aos7-llmdiag` 是轉址 stub（r5 移除）：不管給什麼都只印一行「改用 aos7-diag --llm」並退 **1**（做不到：這個指令已不再做事）；`--help` 退 0。舊程式在 [archive/llmdiag](../../archive/llmdiag/README.md)。

## --llm 檔案與輸出協定

入口：`aos7-diag --llm <node>`。成功時 stdout 恰一行 JSON。

- `llmcall/<budget>/<call>/request.json` 是合法 JSON 物件，且同目錄沒有 `receipt.json`：列入 `llmcall_pending`。同目錄有 `raw.json` 時 `stage` 為 `raw`，否則為 `request`；兩檔均只看存在，不解析。
- `jobs/<job>/frame.json` 是 JSON 物件、`phase` 為 `halted`、job 名稱以 `_` 加恰好八位十六進位字元結尾，且 `author/req/<rid>/` 是資料夾：列入 `author_halted`。`rid` 是去掉該後綴的 job 名稱，`kind`、`why` 取自 `halt` 物件；缺少欄位時輸出 JSON null。
- `budget/<budget>/ledger.json` 是 JSON 物件，且 `inflight` 為大於零的整數（不含布林值）：列入 `budget_inflight`。

輸出物件包含 `v: 1`、`llmcall_pending`、`author_halted`、`budget_inflight`。各列欄位依序為 `(budget, call_id, stage)`、`(job, rid, kind, why)`、`(budget, inflight)`；三表分別依 `(budget, call_id, stage)`、`job`、`budget` 排序。不存在（含 ENOTDIR／EISDIR）、壞 JSON、非物件、UnicodeError 或 NaN 常數的 request、frame、ledger 均略過。讀寫故障（不是不存在）退 3，不再略過。

## 給維護者

程式：`aos7-diag`（入口與核心槽診斷）、`aos7_diag_llm.py`（唯讀 LLM 三表掃描）。
