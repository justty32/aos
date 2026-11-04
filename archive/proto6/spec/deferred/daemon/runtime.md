# daemon 核心：開格與 runner

← [舊 daemon 目錄（暫緩區）](README.md)｜[規格](../../README.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊 daemon 的開格核心：記憶體登記、runner、收屍。現行 daemon 只定期叫 aos-exec（[B-640](../../daemon/core.md)）。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## 分檔目錄

> 本檔只留前言與目錄，內容按標題拆在 `runtime/`。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-601-socket與IPC授權.md](runtime/01-B-601-socket與IPC授權.md) | B-601：記憶體登記與按需執行 |
| 2 | [02-B-601-執行身分與開格.md](runtime/02-B-601-執行身分與開格.md) | 執行身分與 helper；開格：runner 與回報 |
| 3 | [03-B-601程序管理與B-504啟動自檢.md](runtime/03-B-601程序管理與B-504啟動自檢.md) | B-504：通知只是提示；啟動自檢（B-605 的共通部分） |
