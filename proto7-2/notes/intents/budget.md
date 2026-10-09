# budget 意圖卡

← [intents](README.md)｜[包 README](../../packs/budget/README.md)

**①解決什麼**：一份固定額度、一本單一寫者的帳；每次用資源都「先預留、再准入、後結算」記成精確帳，斷掉也不多扣。

**②必要的副作用**：全在 `<node>/budget/<id>/`：`ledger.json`＋鎖、`inbox/`（處理完刪）、`receipts/`（結算後 3 回合清孤兒）、`gateway/`、`error.json`；`ledger` 是長駐任務；讀核心 `.aos/round.json` 當時鐘。不連網、不花錢、不碰別包。

**③不做**：不分配、不估價、不接真 AI（那是 llmcall）、不自動凍結超支。

**④多出來的（現狀）**：零。只有錯誤路徑兩處（`status` 沒帳仍退 0；`call` 時鐘停會一直等）見 [blueprint-errors](../blueprint-errors.md)。
