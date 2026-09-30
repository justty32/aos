# 基底規格入口

← [規格入口](../README.md)｜[共用契約](../contracts.md)

| 篇章 | 責任 |
|---|---|
| [工作材料與結果](work.md) | 固定一次工作的輸入、識別與結果 |
| [inst 第 1 版](inst.md) | 跑什麼、用誰、路徑、環境與指示詞 |
| [執行器](execution.md) | 啟動、後代收尾、取消、逾時與失敗 |
| [身分與資源](identity-resources.md) | 身分額度、可選 helper、資源限制的落地 |
| [儲存](storage.md) | 收件區、追蹤區、完整發布與清理 |
| [通訊](transport.md) | 投件授權與簡單去重 |
| [daemon](../daemon.md) | 定期跑 `aos-tick` 的標準程式：登記、喚醒、程序生命週期、重啟與通道 |
| [通用 tick](../tick.md) | 核心（互斥鎖、任務表、上下層）與標準配備（git、收件、投件、備援等） |
| [kernel 樹](../scheduling/README.md) | node 成員關係、排程與資源 module |

<a id="b-000責任與驗收建議預設未拍板"></a>
## B-000：責任與驗收

（09-29 重寫：已刪；角色併入[名詞](../terms.md)，驗收各歸葉篇。）
