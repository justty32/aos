← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 6. 兩個逾時各管什麼

| 逾時 | 設在哪 | 管什麼 | 撞到時 agent 看到 |
|---|---|---|---|
| 內圈：HTTP | llm.json 那筆的 `timeout_ms`（預設 120000） | aos-llm call 等模型回話多久 | 回音 `kind=child`、`code=1`；原因在 `log/llm.err` 的 `Timeout` 行 |
| 外圈：工作 | agent 的 `info.llm.timeout_ms`（預設 125000），就是 kernel `add` 的 `timeout_ms` | 這件工作在 cpu 上整個跑多久（含讀檔、組 body、HTTP），到了 cpu 砍整組 | 回音 `timed_out=true` |

外圈設得比內圈大一點，正常是內圈先到、aos-llm call 自己乾淨地退 1；外圈只是保險（例如 DNS 卡住）。兩者都不含在 kernel 排隊的時間。
agent 看不到 llm.json（它在 llm cpu 那邊、金鑰也只在那邊），所以外圈只能由 agent 自己的 `info.llm.timeout_ms` 給，兩邊要人自己配好。
兩種逾時對 agent 都是「問模型失敗一次」（[aos-agent.md §6.1](../aos-agent/collect.md)）。
