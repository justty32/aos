# 意圖卡（intents）

← [proto7-2](../../README.md)｜[代定清單](../decisions-2026-10-09.md)｜錯誤路徑 [blueprint-errors](../blueprint-errors.md)｜修改隊 [blueprint-simplify-teams.json](../blueprint-simplify-teams.json)

使用者 10-09 16:10：新模組或功能**先擬意圖再開隊**；副作用與外部影響只留必要的；錯誤路徑統合。包文件慣例（頂層 10-09 定）：README 只給第一次用的人（三行頭＋第一次跑），契約卡、退出碼與進階放 ADVANCED.md。每張卡 ≤1.5 KiB、白話，四段：①一句話要解決什麼 ②必要的副作用（寫哪些檔、起哪些程序、碰不碰別人的檔、花不花錢）③明確不做 ④對照現狀多出來的副作用，每條標「保留／改成可選／移除」。開新隊前先寫卡；改包前先對卡。

| 卡 | 多出來的 | 處置 |
|---|---|---|
| [routines](routines.md) | 3 | 移除 2、保留 1 |
| [skills](skills.md) | 4 | 移除 2、可選 1、保留 1 |
| [events](events.md) | 3 | 移除 1、可選 1、保留 1 |
| [wfnode](wfnode.md) | 2 | 保留 2 |
| [metrics](metrics.md) | 0 | — |
| [compact](compact.md) | 3 | 移除 1、可選 1、保留 1 |
| [mail](mail.md) | 4 | 移除 1、可選 1、保留 2 |
| [llmcall](llmcall.md) | 3 | 改 1、保留 2 |
| [prompt](prompt.md) | 0 | — |
| [author](author.md) | 4 | 可選 2、保留 2 |
| [budget](budget.md) | 0 | — |
| [up](up.md) | 設計中 | 統一負責跨包副作用 |
