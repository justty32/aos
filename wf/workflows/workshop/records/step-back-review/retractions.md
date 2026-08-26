# 四位收回了什麼

← [三場研討會的回頭審視](README.md)

> 本檔是本輪最有訊號的一塊：四位看過三場完整產出後，**各自收回了自己上一場剛收攏出來的東西**，以及砍掉之後那些問題暫時由誰承擔。

最有訊號的不是四位否定別人，而是他們看過三場完整產出後，**四位不約而同收回了自己上一場
剛收攏出的兩項前置功能**：公開 Publish 與通用 Effect。

| 收回／延後什麼 | 誰收回 | 為什麼收回 | 砍掉後，問題由誰負責 |
|---|---|---|---|
| **公開 Publish API** | **四位各自都明確收回** | 目前只證明 Deliver 內部需要 temp＋rename；通用檔／目錄發布、跨 filesystem、fsync 與斷電契約都沒有 workload 證據 | Deliver 內部保留私有 publish helper；其他腳本若要更新自己的 state／cursor，暫時自行 temp＋rename，等重複出錯再抽公開 API |
| **通用 Effect／Effect resolve 作為近期 core 前置** | **四位各自都明確收回** | 它誠實標 unknown，卻不能消除「遠端已做、本機未記」；provider 查詢與冪等仍各家不同，T5 也尚未實跑出重複痛點 | `.runi` 讓本地批次停住；provider wrapper／adapter 記簡單日誌，unknown 交給人 retry／放棄／採納，不先做通用 core ABI |
| **平行 `effect_join`／barrier** | 工程師收回自己的 `effect_join`；研究人員、開發者也把平行 join 列為尚不存在的問題 | 首版連串行「模型→一工具→模型」都沒跑過，先為平行工具造 barrier 沒有證據 | driver 先只跑串行；真的出現多工具並行後，再由腳本負責掃結果並暴露共同形狀 |
| **現在就定 events／calls／cursor 的耐久版面** | 架構師明確收回；其餘三位也都改成先用腳本落 prompt／response／result | 三場裡提出了多套資料夾名，沒有一套經真 CLI 或 crash 驗證 | T5 腳本先選最小檔名；它是實驗資料，不是 core ABI，重複後再升格 |
| **`slot@generation` 與永久身分** | 研究人員明確收回自己的 generation；工程師、架構師、開發者也都把活搬／舊 receipt 誤投列為預測問題 | 沒有第二個 world、沒有活搬，也沒有一次 stale receipt 事故 | 先用路徑定位且不承諾活搬；真的發生同名新世界誤收舊結果時，再加 generation |
| **lane／proc-table／capability／promotion 這組通用行程機制** | **四位獨立地都說整組走得太前面** | 從 Linux 行程隱喻推導出控制平面與磁碟 ABI，但目前只有一個人的新專案、單一 queue，agent loop 一次都沒跑 | agent 的續跑由 driver 腳本負責；`aos exec` 仍只推一個 folder。第二個 world、共享 writer 或真正的權限需求出現後再重開 |

四位沒有收回所有東西。**本地、單層的 `kernel.json` 仍被視為簡單的頭尾指令來源；`.runi` 仍
保留未完成回合；原子 Deliver 仍是四位都承認的現存缺口。**被收回的是在 workload 出現前，
把它們向上長成繼承政策、process manager、通用 WAL 與可搬身分。
