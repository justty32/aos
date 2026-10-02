# daemon 維運：佈建與 helper 動作

← [舊 daemon 目錄（暫緩區）](README.md)｜[整理區](../../README.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊 daemon 的佈建與 helper 動作。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## 分檔目錄

> 2026-10-02 整理：原檔約 11 KB 超過 8 KB 門檻，按標題逐字拆進 `helper-actions/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-609-通則與動作.md](helper-actions/01-B-609-通則與動作.md) | B-609：佈建固定動作與 helper 動作 |
| 2 | [02-B-609-spawn_as與分工.md](helper-actions/02-B-609-spawn_as與分工.md) | 以指定帳號開程序（`spawn_as`）；daemon 自己做的與 helper 做的 |
