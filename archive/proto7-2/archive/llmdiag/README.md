已併入 [diag](../../modules/diag/README.md)（`aos7-diag --llm`）；本資料夾只留歷史，入口 `modules/llmdiag/aos7-llmdiag` 是轉址 stub。

# llmdiag

**職責**

`aos7-llmdiag <node>` 唯讀列出尚無回條的 llmcall、已 halted 且有對應請求目錄的 author job，以及正數的 budget inflight。正常執行時，stdout 僅有一行 JSON。

**前置條件**

提供既有 node 資料夾；輸入檔案遵循 [檔案與輸出協定](spec.md)。node 不是資料夾時退出碼為 2。

**保證**

不寫入 node；依指定欄位排序三張表。壞掉或非物件的 request、frame、ledger JSON 不列入。raw.json 與 receipt.json 只檢查是否存在，不解析內容。入口在匯入模組前停用 bytecode 寫入。

**明確不管**

不修復帳差、不補回條、不改動 job、request 或 ledger，也不判定 inflight 的成因。
