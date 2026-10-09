# skills 意圖卡

← [intents](README.md)｜[包 README](../../modules/skills/README.md)

**①解決什麼**：node 的 `skills/` 抽屜一本一個資料夾；做索引、讓 AI 挑一本、把那本掛給某任務。

**②必要的副作用**：`index` 寫 `skills/index.json`（有 must.json 才有 `MUST.md`）；`pick` 經 llmcall 問一次 AI（真模型＝花錢）、llmcall 自己留證據；`mount` 改該任務在 `.aos/tasks.json` 的 `mounts`（這就是掛載）。

**③不做**：不複製外部 skill 進 repo；不自己開帳、不自己起帳任務；沒開帳時只用本機關鍵字比對挑（不問 AI、不花錢、不假裝是 AI 挑的；紀錄標 `via`），要 AI 挑就開帳（2026-10-09 頂層定，取代原「不用 AI 就不挑」）。

**④多出來的（現狀）**
- `pick` 用 `open(…,"a")` 碰 budget 的 `ledger.lock`（在別包的夾裡建檔）→ **移除**：只檢查存在／有人持有，沒有就退 1「帳任務沒在跑」。
- `pick` 要 AI 挑就要開帳 → **保留**；帳沒在跑時退 1、stderr 直接附可複製的起帳指令（10-09 ER-skills 上線的做法；第一次跑新手走 `aos7-up` 就不會碰到）。
- `pick` 每次追加 `skills/.pick/log.jsonl`、不封頂 → **改成可選**：只留最近 50 行或拿掉（llmcall 證據已夠）。
- `bank.py` 建 `/tmp/aos7-skills-bank.*` 不清 → **移除**（結束清）。
