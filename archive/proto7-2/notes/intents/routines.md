# routines 意圖卡

← [intents](README.md)｜[包 README](../../modules/routines/README.md)

**①解決什麼**：node 裡一張「到時候跑這個」的清單（每隔多久一次／某時刻一次），時間到就跑，最多一次。

**②必要的副作用**：寫 `wf/routines.json`、`wf/schedule.json`（含各一個 `.lock`）；到期時起一個子程序跑你給的程式；不連網、不花錢。

**③不做**：不補跑錯過的；不自己起心跳；不碰別包的檔。

**④多出來的（現狀）**
- `add` 順手改核心的 `.aos/tasks.json`（沒有就新建、連 `.aos/` 一起建）→ **移除**：裝 keep 任務交 `aos7-up`（它本來就裝四個）；進階者用 `aos7-ctl add`。`add` 只印一句「要讓心跳自動跑：…」。
- `rm` 表不存在也會建 `wf/` 與兩個 `.lock` → **移除**：沒表就印「清單是空的」。
- `add` 先改 tasks.json 再撞名丟錯 → 隨上一條消失。
- `wf/` 留兩個固定 `.lock` → **保留**（頂層已核可）。
