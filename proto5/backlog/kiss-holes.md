# proto5.1 為了 KISS 先接受的洞

來自 [proto5.1 findings-brief §4](../../proto5.1/notes/findings-brief.md)，編號指 findings。

1. 沒有請求對帳與跨檔交易，中斷可能串單、重做或漏計錯誤（#11～13、23、26）→ [request-identity](request-identity.md)。
2. 排隊與等待沒期限，半批沒送完可能永遠等（#8、23）。
3. 收屍不等於殺掉原工作，HTTP 慢慢回資料也可能超過名義時限（#9、23）。
4. 另開入口同時跑同一 agent，agent 自己沒有並行鎖（第二段回報）。
5. daemon 不自動收養崩潰留下的 runner（#28～29）。
6. 排程只看最後結果，可能漏中間退出碼（#30）。
7. 「寫完請求、還沒加 waits」之間崩掉會重送（llm cpu 6）→ [request-identity](request-identity.md)。
