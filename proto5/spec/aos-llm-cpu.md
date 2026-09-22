# aos-llm-cpu 程式規範

← [proto5 README](../README.md)｜格式：[llm-cpu](llm-cpu.md)｜共用佇列：[cpu-queue](cpu-queue.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

`aos-llm-cpu [dir]` 一次收屍、再問最多一份請求；省略 dir＝`.`。
先讀驗 info 身分與 models 表、解 CPU 的指示詞，再透過 `aos_cpu` 收屍與認領。
認領後在 execute 驗請求 model／body，壞 payload 回 BadPayload；合法代號若不在表裡，
回 UnknownModel，msg 為「不認識的模型代號」。
查得到就把表裡真名填入 body.model，再用 `aos_llm_ask.call(engine, body)` 問一次。

## 1. HTTP 與期限

endpoint 去掉結尾 `/` 再接 `/chat/completions`，POST JSON body。
api_key 有非空值才送 `Authorization: Bearer <api_key>`。不串流、不重試，成功取
`choices[0].message` 物件，不在 CPU 驗訊息 role／content；逾時寫 Timeout，連線失敗、HTTP 非 2xx、非法 JSON 或缺 message 寫 EngineFailed；都是 ok:false。

HTTP 的 timeout 取 models 表的 timeout_ms，預設 120000，是 socket 阻塞期限；慢慢滴回資料
可能超過總期限。收屍使用同一模型預算再加共用 30 秒寬限；model 是已知代號便用該模型預算，即使 body 壞掉也一樣；
未知代號或 model 形狀不合才用 120000 ms。
HTTP 期間不持佇列鎖；另一顆 CPU 已收屍時，原程序遲到回覆由共用層丟棄。

沒有背景 worker、pid、容量設定、優先序或 usage；容量由同時啟動的進程數決定。

## 2. 退出碼與 API

| 退出碼 | 意思 |
|---|---|
| 0 | 有處理請求或收屍；已寫 ok:false 也算完成 |
| 101 | 沒有可處理請求、也沒收屍 |
| 1 | 讀驗／I/O 錯、隔離壞單或結果發布失敗；共用佇列診斷用 aos-cpu 前綴，其餘 `aos-llm-cpu: <代號>: <白話>` |
| 2 | 用法錯，未知旗標或 dir 不是資料夾 |

stdout 不輸出，引擎錯誤只寫結果。`load(dir, env=None)` 回 dir／metainfo／已解好的 models；
`tick(dir, env=None)` 回 0／1／101，無法繼續的讀驗／I/O 錯丟 AgentError；`main(argv=None)` 是 CLI。
交件者統一使用 `aos_cpu.submit`；共用 API 見 [aos-cpu](aos-cpu.md)。

收屍、遲到檔案身分核對、原子發布與故障界線見 [cpu-queue](cpu-queue.md)。
