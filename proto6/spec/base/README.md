# 基底規格入口

← [規格入口](../README.md)｜[共用契約](../contracts.md)

| 篇章 | 責任 |
|---|---|
| [工作材料與結果](work.md) | 固定一次工作的輸入、識別與結果 |
| [inst 第 1 版](inst.md) | 跑什麼、用誰、路徑、環境與指示詞 |
| [執行器](execution.md) | 啟動、後代收尾、取消、逾時與失敗 |
| [身分與資源](identity-resources.md) | 身分額度、資源限制的落地；可選 helper 與 `aos-as`（B-303）已搬到[整理區](../settled/helper.md) |
| [儲存](storage.md) | 收件區、追蹤區、完整發布與清理 |
| [通訊](transport.md) | 投件授權與簡單去重 |
| [daemon](../settled/daemon.md)（整理區） | 定期跑 `aos-tick` 的標準程式：登記、喚醒、程序生命週期、重啟與通道 |
| [通用 tick](../settled/tick.md)（整理區） | 核心（互斥鎖、照表跑、上下層、每項結束碼紀錄）與標準任務表範本（收件、投件、發摘要、清理；git 與 cgroup 下一步納入） |
| [kernel 樹](../scheduling/README.md) | node 成員關係、排程與資源 module |

<a id="b-000責任與驗收建議預設未拍板"></a>
## B-000：責任與驗收

（09-29 重寫：已刪；角色併入[名詞](../terms.md)，驗收各歸葉篇。）
