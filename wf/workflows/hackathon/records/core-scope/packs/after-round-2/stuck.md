# 第 2 輪之後的資料包 — 這輪卡住的清單

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1 後](../after-round-1/stuck.md)

第 2 輪之後，四位各自卡在哪裡，每條都附現場檔案的路徑。

## 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在 Effect response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit 的兩個窗口尚未測重複 resolve；本輪未測範圍寫在 `/tmp/aos-core-scope-p1-r2/round2/report-r2.md`。
- **p2（Armstrong persona）**卡在 target commit 後被 aggregate 取走，receipt 卻尚未 commit，只能人工 `adopt-consumed`；完整現場在 `/tmp/aos-p2-round2.kTrhIV/p2-agent-loop/round2/evidence/delivery-consumed-no-receipt.log`。
- **p3（Cantrill persona）**卡在第一個數仍把 runtime transaction 當成手寫實作份數，且私有 validator 尚未與 canonical parser 做逐案差異對照；來源 inventory、validator 行為與未測項都整理在 `/tmp/p3-core-scope-round2/ROUND2.md`。
- **p4（Thompson persona）**卡在 publish 成功但 receipt 未回傳、以及 consumer 刪除 target 後重試的兩個窗口，沒有 ledger 時尚不能唯一回答 `Already`、`Unknown` 或 `Conflict`；原型與未測項在 `/tmp/p4-round2/ROUND2.md`。
