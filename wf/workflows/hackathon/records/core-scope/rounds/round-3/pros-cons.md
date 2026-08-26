# 第 3 輪紀錄 — 好處／壞處

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R2](../round-2/pros-cons.md)

書記對上面那批坑的正反兩面整理：這一輪補上了什麼、又長出什麼新負擔。

## 3. 好處／壞處

### 好處

上一輪留下的兩個窄缺口這輪都有實際輸出。Effect 這邊，response-ready 與 decision-ready 的第二次 resolve 都是 commit delta 0、provider ledger delta 0；response-ready 的 final hash 與 baseline 相同，decision-ready 則保留 `unknown_abandoned`。Deliver 這邊，合作 consumer 的四個死亡窗都能由一個高階 recover 收斂到 ack，重跑 recover 與 `aos exec` 沒再增加 effect ledger；`adopt-consumed`、人工搬檔與重造半批 instruction 沒再出現。

Thompson persona 的相同 manifest 對照把「沒有 target」保留成 Unknown，加入由 consumer claimed bytes 算出的 ack 後才成為 Already。Cantrill persona 把第一個數字拆成四欄，並直接量出私有 validator 與 C ABI object parser 的接受／拒絕差異。四份第三個數字仍是 0，producer、consumer、aggregate 被記為同一條 protocol 的階段，沒有新增 lane、join、scheduler 或 proc-table 現場。

### 壞處

Deliver completion 現在包含 payload、visibility receipt、claim、aggregate receipt、delivery deletion 與 ack；ack 若要讓 producer 在 aggregate 後仍可查，就會留下需要 retention／GC 的紀錄。ack 清太早會重新失憶，不合作 consumer 則直接停在 `unknown-consumer-history`。Armstrong persona 的 gate 目前還要求 ack commit 後才讓 `aos exec` 取 aggregate；若有另一個 executor 在 receipt／ack 前搶走 `inst.json`，本輪沒有涵蓋該並行窗口。

Effect 仍需 request、response、decision、done 四類 evidence，unknown 仍不能由本機檔案推成 success、failure 或 exactly-once。Publish 仍需唯一 temp、no-replace、內容比對與 receipt；canonical batch parser 沒有公開 C ABI，私有 validator 的差異已是實際輸出。四份 R2 `/tmp` 現場全部消失，R3 產物仍放在相同類型的暫存位置。
