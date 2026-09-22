# aos-llm-cpu 程式規範（第 1 版）

← [proto5.1 README](../README.md)｜格式：[llm-cpu](llm-cpu.md)｜共用佇列：[cpu-queue](cpu-queue.md)

`aos-llm-cpu [dir]` 一次收屍、再同步問最多一份請求；省略 dir＝`.`。
`aos_llm_cpu.py` 是共用 `aos_cpu` 的薄包裝：指定 `llm_cpu` 身分，認領前驗 engine／body，
execute 用 `aos_llm_ask.call`，期限取 engine.timeout_ms（預設 120000）加共用 30 秒收屍寬限。

沒有背景 worker、pid、容量設定、重試、優先序或 usage；容量由同時啟動的進程數決定。
HTTP 期間不持佇列鎖。HTTP timeout 是 urllib 等待 timeout，慢速持續回資料可能超過總期限；
另一顆 CPU 收屍後，原進程遲到的回覆由共用層丟棄。

| 退出碼 | 意思 |
|---|---|
| 0 | 有處理請求或收屍；已寫 ok:false 也算完成 |
| 101 | 沒有可處理請求、也沒收屍 |
| 1 | 讀驗或 I/O 錯；stderr 一行 `aos-llm-cpu: <代號>: <白話>` |
| 2 | 用法錯，未知旗標或 dir 不是資料夾 |

stdout 不輸出，引擎錯誤只寫結果。`load(dir, env=None)` 只讀驗 info，回 dir／metainfo；
`tick(dir, env=None)` 回 0／101、失敗丟 AgentError；`main(argv=None)` 是 CLI。
`queue_lock` 保留為共用函式別名，交件者統一使用 `aos_cpu.submit`。

收屍、遲到檔案身分核對、原子發布與尚未提供的交易保證，一律見 [cpu-queue](cpu-queue.md)。
