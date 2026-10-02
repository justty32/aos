# hooks：外掛掛點

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜格式：[tick 協議](../protocol/tick.md) P-202、P-213｜plan：[m1h-hooks-module](../../../plan/m1h-hooks-module.md)

**狀態：已實作**（`aos-tick` 內建，`lib/aos_tick_table.py` 讀、`lib/aos_tick_hooks.py` 跑，[src/py](../../../src/py/README.md#hooks外掛掛點m1h)）。

## 分檔目錄

> 2026-10-02 整理：原檔約 14 KB 超過 8 KB 門檻，按標題逐字拆進 `hooks/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-635-掛點寫法與檢查.md](hooks/01-B-635-掛點寫法與檢查.md) | B-635：hooks：一格裡各個時機跑的一串 |
| 2 | [02-B-635-何時跑與紀錄.md](hooks/02-B-635-何時跑與紀錄.md) | 什麼時候跑、不跑；紀錄 |
| 3 | [03-B-635-範例hook加git.md](hooks/03-B-635-範例hook加git.md)<a id="範例用-hook-加普通-git-指令管版本"></a> | 範例：用 hook 加普通 git 指令管版本 |
