# aos-llm-cpu 程式規範

← [proto5.1 README](../README.md)｜格式：[llm-cpu](llm-cpu.md)｜共用佇列：[cpu-queue](cpu-queue.md)

`aos-llm-cpu [dir]` 一次收屍、再問最多一份請求；省略 dir＝`.`。
先讀驗 info 身分與 models 表、解 CPU 的指示詞，再透過 `aos_cpu` 收屍與認領。
認領前驗請求 model／body；合法代號若不在表裡，寫固定「不認識的模型代號」失敗結果。
查得到就把表裡真名填入 body.model，再用 `aos_llm_ask.call(engine, body)` 問一次。

## 1. HTTP 與期限

endpoint 去掉結尾 `/` 再接 `/chat/completions`，POST JSON body。
api_key 有非空值才送 `Authorization: Bearer <api_key>`。不串流、不重試，成功取
`choices[0].message` 物件，不在 CPU 驗訊息 role／content；連線失敗、HTTP 非 2xx、逾時、非法 JSON 或缺 message 都寫 ok:false。

HTTP 的 timeout 取 models 表的 timeout_ms，預設 120000，是 socket 阻塞期限；慢慢滴回資料
可能超過總期限。收屍使用同一模型預算再加共用 30 秒寬限；未知代號用 120000 ms 預算。
HTTP 期間不持佇列鎖；另一顆 CPU 已收屍時，原程序遲到回覆由共用層丟棄。

沒有背景 worker、pid、容量設定、優先序或 usage；容量由同時啟動的進程數決定。

## 2. 退出碼與 API

| 退出碼 | 意思 |
|---|---|
| 0 | 有處理請求或收屍；已寫 ok:false 也算完成 |
| 101 | 沒有可處理請求、也沒收屍 |
| 1 | 讀驗或 I/O 錯；stderr 一行 `aos-llm-cpu: <代號>: <白話>` |
| 2 | 用法錯，未知旗標或 dir 不是資料夾 |

stdout 不輸出，引擎錯誤只寫結果。`load(dir, env=None)` 回 dir／metainfo／已解好的 models；
`tick(dir, env=None)` 回 0／101，失敗丟 AgentError；`main(argv=None)` 是 CLI。
`queue_lock` 保留為共用函式別名，交件者統一使用 `aos_cpu.submit`。

收屍、遲到檔案身分核對、原子發布與故障界線見 [cpu-queue](cpu-queue.md)。
