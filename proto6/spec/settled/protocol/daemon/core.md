# daemon 協議：aos-daemon 的 argv、設定檔與輸出

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-640](../../daemon/core.md)｜[慣例](../../conventions.md)

本篇只有 P-120，只寫格式。daemon 做什麼（週期、起點、停不停、停機）以 [B-640](../../daemon/core.md) 為正本。

依據：[第二十批篇末「2026-10-01：最核心 daemon」](../../../../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)、[plan m3](../../../../plan/m3-daemon-core.md)；現行程式 [aos-daemon](../../../../src/py/README.md#aos-daemon第三段最核心-daemon)（有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 12 KB 超過 8 KB 門檻，按標題逐字拆進 `core/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-120-argv與設定檔.md](core/01-P-120-argv與設定檔.md) | P-120．aos-daemon 的 argv、設定檔、輸出與結束碼〔使用者方向 2026-10-01；欄位名照現行程式〕 |
| 2 | [02-P-120-輸出與結束碼.md](core/02-P-120-輸出與結束碼.md) | stdout；aos-exec 的 stdout 與 stderr；daemon 自己的 stderr；結束碼 |
