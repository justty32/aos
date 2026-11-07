# bash — 執行指令並在自己的小格留下內層結果。

設定 `AOS_STACK` 時，執行前透過共用 `observed.prepare_strict` 開好帳檔並宣告 `aos-observed` 介面；不能寫就回 `LogFailed`，不執行指令。沒有 `AOS_STACK` 時照跑、不記帳。

每次完成追加 `cmd` 行：`command`（bash 指令）、`timeout_s`、`exit`（內層碼，訊號為 128＋訊號值）、`elapsed_ms`、`out_bytes`（截斷前 stdout 與 stderr 合計位元組）。逾時也記停止後的內層碼，再回 `CommandFailed`；外部 TERM／INT 同樣先停內層並記帳，再以工具自己的訊號碼退出。若執行後寫入失敗，回 `LogFailed`；已發生的指令副作用無法撤回。

原本輸出截斷、非零內層碼仍屬成功工具結果的規則維持。
