# 四位收回了什麼

← [三場研討會的回頭審視](README.md)

前三場收攏出的公開 Publish 與通用 Effect，四位都收回作為近期前置。收回的項目與砍掉後的承擔者：

| 收回／延後什麼 | 為什麼收回 | 砍掉後，問題由誰負責 |
|---|---|---|
| **公開 Publish API**（四位都收回） | 只證明 Deliver 內部需要 temp＋rename；通用檔／目錄發布、跨 filesystem、fsync 與斷電契約沒有 workload 證據 | Deliver 內部保留私有 publish helper；其他腳本更新自己的 state／cursor 時自行 temp＋rename，重複出錯再抽公開 API |
| **通用 Effect／Effect resolve 作為近期 core 前置**（四位都收回） | 它誠實標 unknown，卻不能消除「遠端已做、本機未記」；provider 查詢與冪等各家不同，T5 也沒實跑出重複痛點 | `.runi` 讓本地批次停住；provider wrapper／adapter 記簡單日誌，unknown 交給人 retry／放棄／採納 |
| **平行 `effect_join`／barrier** | 串行「模型→一工具→模型」都沒跑過，先為平行工具造 barrier 沒有證據 | driver 先只跑串行；真的出現多工具並行，再由腳本掃結果並暴露共同形狀 |
| **現在就定 events／calls／cursor 的耐久版面** | 提出過多套資料夾名，沒有一套經真 CLI 或 crash 驗證 | T5 腳本先選最小檔名；它是實驗資料，不是 core ABI，重複後再升格 |
| **`slot@generation` 與永久身分** | 沒有第二個 world、沒有活搬，也沒有一次 stale receipt 事故 | 先用路徑定位且不承諾活搬；真的發生同名新世界誤收舊結果，再加 generation |
| **lane／proc-table／capability／promotion 這組通用行程機制**（四位都說走得太前面） | 從 Linux 行程隱喻推導出控制平面與磁碟 ABI，但目前只有一個人的新專案、單一 queue，agent loop 一次都沒跑 | agent 的續跑由 driver 腳本負責；`aos exec` 仍只推一個 folder。第二個 world、共享 writer 或真正的權限需求出現後再重開 |

**沒收回的**：本地、單層的 `kernel.json` 是頭尾指令來源；`.runi` 保留未完成回合；原子 Deliver 是
現存缺口。收回的是在 workload 出現前把它們向上長成繼承政策、process manager、通用 WAL 與可搬身分。
