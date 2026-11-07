mailbox 命名這題替使用者定下的 8 個設計決定（五欄一覽表）
← [入口](../04-設計規劃.md)｜上一份 [03-mailbox-naming](03-mailbox-naming.md)｜下一份 [04-效能標準](04-效能標準.md)

## 設計決策一覽

| 決定了什麼 | 出處檔:行 | 對照的使用者原話 | 判斷 | 要裁時的選項與推薦 |
|---|---|---|---|---|
| 名字帶 mailbox 的一個都不改成 queue | mailbox-naming/README.md:17 | 「如果那個mailbox是有序的話，是否應該都改名為_queue？」（README:6） | 該問使用者 | 補一句確認就好（推薦）；或列出硬改 1.5～2 小時讓他選 |
| queue 的定義：四條都成立才叫 queue | 03-R14.md:6,12 | 「請求的投遞倒是可以用信箱概念，但也可以用queue概念」（agent-bob/04:17） | 該問使用者 | A 加註保留嚴讀法（推薦）；B 放寬 |
| 「信箱」是機制名，錯誤代號、旗標、型別都不改 | 03-R14.md:4；05:14-19 | 「寫進 C-54 (Recommended)」（README:10） | OK | 不用裁 |
| `queue.json` 不算一詞兩義，檔頭寫明排法 | 03-R14.md:10 | 「不算、檔頭寫明 (Recommended)」（README:11） | OK | 不用裁 |
| llm kernel 收件箱改名 `requests/`，回信信箱是 `requests/reply/` | 05:6 | 「現在統一 requests/」（README:13） | OK | 不用裁 |
| 舊名不認、不寫遷移 | 05:22 | 「其實不用管舊版本遷移這件事……一律當成沒有舊版」（wf/workflows/common/user.md 表「舊版遷移」） | OK | 不用裁 |
| 知識庫把 agent 的 queue 從 inbox 改叫 queue，判官變數 `inbox` 改 `requests` | 05:9-10 | 沒找到原話（照 C-54 R4 一詞一義的推論） | OK | 不用裁（對內用語，行為不變） |
| P-11「有順序信箱」先不動 | 03-建議表.md:26 | 沒找到原話 | 該問使用者 | 加註、原句全留（推薦）；或不動，但會跟 R14 第 5 點矛盾 |
