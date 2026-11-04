# llmcall 意圖卡

← [intents](README.md)｜[包 README](../../packs/llmcall/README.md)｜[凍結介面](../blueprint-llm2.md)

**①解決什麼**：問 AI 一次，保證「同一題不重送、原始回覆與用量留著、花了多少記進帳」；斷掉再跑接得上。

**②必要的副作用**：寫 `<node>/llmcall/<帳>/<call>/{request,raw,receipt}.json`＋鎖；寫帳的 `gateway/<kid>.json`、投 `inbox/`、讀完刪 `receipts/`（帳只有這一條證據路徑，藍圖 ②）；litellm 傳輸連網、花錢；`--out` 另存一份。

**③不做**：不重送、不串流、不設 max_tokens、不自己 cancel、不輪詢遠端、不接假 AI 以外的本機後端。

**④多出來的（現狀）**
- 帳任務沒在跑時 `call` 等 patience 回合，時鐘停就**永遠卡住** → **改成**：進門先看 `ledger.lock` 有沒有人持有，沒有就退 1「帳任務沒在跑：…」；不改凍結的回條與 0～4。
- fake 傳輸寫 `fake-remote.json` → **保留**（只給測試數送出次數）。
- `.crash` 測試旗標留在正式碼 → **保留**（沒旗標不動作）。
