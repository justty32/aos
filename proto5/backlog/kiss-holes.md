# proto5.1 為了 KISS 先接受的洞

來自 [proto5.1 findings-brief §4](../../proto5.1/notes/findings-brief.md)，編號指 findings。
2026-09-23 重架構後，原第 3、5、6 條已被新規範解掉、刪了（見 [backlog-cleanup](../notes/2026-09-23-rearch/backlog-cleanup.md)）；剩下的：

1. 沒有請求對帳與跨檔交易，中斷可能串單、重做或漏計錯誤（#11～13、23、26）。cpu／kernel 這層已有開機對帳、ack、帳本（[cpu §6.2](../spec/cpu.md)、[kernel §3](../spec/kernel.md)）；剩 agent 那層 → [request-identity](request-identity.md)。
2. 排隊與等待沒期限（#8、23）。kernel 的 `queue` 沒有期限、只有 `timeout_ms` 管跑的時間（[kernel §3 第 8 步](../spec/kernel.md)）；「半批沒送完永遠等」是 agent 那層，等 agent 規範重寫後再判。
4. 另開入口同時跑同一 agent，agent 自己沒有並行鎖（第二段回報）。kernel 保證同一行程不會同時派兩顆，但人手動跑同一份 inst 在保證外（[kernel §7](../spec/kernel.md)）；agent 那層等 agent 規範重寫後再判。
7. 「送出請求、還沒加 waits」之間崩掉會重送（llm cpu 6）→ [request-identity](request-identity.md)。
