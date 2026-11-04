# 學徒三連題 意圖卡（r4，S3 隊）

← [intents](README.md)｜[author 卡](author.md)｜計畫 plan-2026-10-09-r4（已封存）

**①解決什麼**：目標 3「自我改進」現在沒有真證據（A5 兩題失敗原因都是 proxy）。要拿證據就得讓學徒**連做三題同類**（同一張 aos-tool 工具卡、同一種「讀 node 檔→彙總→一行」形狀），每題做完寫踩坑，比較第 1 題與第 3 題的重問次數、token、時間；另跑一組不帶踩坑的對照。

**②必要的副作用**：學徒 node（`../aos-wt/apprentice-node`）的 `author/`、`wf/workflows/common/gotchas.md`；真 AI 呼叫（gate ≤200 次）；三關沙盒；發布只建 `apprentice/<rid>_<sha8>` 分支；量測用 `aos7-metrics` 讀證據檔，不寫別處。

**③不做**：不合進 main（這三題是量測用，合不合另議）；不給答案檢查器；不改 author 程式（要改→回報頂層另開）；不在 MC 修好前跑（否則失敗又是 proxy）。

**④對照現狀多出來的**：
- 三題題庫與隱藏答案檢查器（`packs/author/examples/aos-tool-{gap,runs,audit}/`）→ **保留**（之後 R 隊回歸也用）。
- 驅動腳本 `drive3.py` 跑 2×3 題 → **保留**在 evidence，不進包。
- 學徒的 gotchas 會越寫越長 → **改成可選**：每題後跑一次 `aos7-compact now` 把 gotchas 壓在 2 KiB 內（量「壓過的筆記還有沒有用」也是證據）。
