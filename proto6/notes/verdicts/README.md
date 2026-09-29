# 2026-09-29 使用者裁定：索引

← [筆記索引](../README.md)

09-29 使用者一整天分十四批裁定，另有一段軟性標準、一段「下班前的方向」與 B1／B2，依時段分成五份。

讀法：

- **以裁定紀錄為準，後批優先**：後面的批次常推翻或細化前面的（例如第五批拿掉帳本、第十四批改成初版不用 systemd），同一件事以最後一次裁定為準。
- 被取代的舊說法多半留在原處，用刪除線或括號註明「已作廢」「已被第幾批取代」。
- 落進 spec 的條文，各條後面有連結指到 spec 條號。第十三、十四批與 B1／B2 已整批落進 spec。
- 舊連結指到 [2026-09-29-verdicts.md](../2026-09-29-verdicts.md) 的，那裡留了批次對照表。

| 份 | 批次 | 一句話 |
|---|---|---|
| [01](01-notes-review-1-10.md) | 第一批、第二批 | notes 審查待裁定 1～10（極小 root helper、額度只記帳、重啟全殺、中央代發 LLM 等）；設定下一次 tick 生效、待處理資料夾、結果隨 tick 清理 |
| [02](02-kernel-tree-and-tick.md) | 第三～五批 | tick 改註冊式；改回 kernel 樹；拿掉帳本改用 git，資源做成可插拔 module |
| [03](03-node-and-protocol.md) | 第六～十二批、軟性標準 | root helper 與 sudo 啟動、kernel 與 agent 合併成 node、協議篇的 method／收件／attention／清理等細節、一步一步走完整套 agent 循環 |
| [04](04-late-day-directions.md) | 下班前的方向、第十三批 | systemd 方向（後被第十四批取代）、LiteLLM 只當可選 endpoint；LLM 排程三檔、預設自己排、串流、池就是一個 node |
| [05](05-dependencies.md) | 第十四批、追加、B1／B2 | 只用標準庫（jsonschema 例外）、quota 可選、cgroup v2 必要、初版不用 systemd；cgroup 子樹來源、daemon 當掉後清程序 |
