# daemon 核心：定期叫 aos-exec

← [daemon 目錄](README.md)｜[整理區](../README.md)｜[慣例](../conventions.md)｜[名詞](../terms.md)｜格式：[P-120](../protocol/daemon/core.md)｜控制模組：[B-641](control.md)

本篇只有 B-640，寫 `aos-daemon` 核心**做什麼**。argv、設定檔每個欄位的型別、輸出行的確切樣子、結束碼，寫在格式篇 [P-120](../protocol/daemon/core.md)。

依據：[第二十批篇末「2026-10-01：最核心 daemon」整節](../../../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)、[daemon 核心草稿](../../../notes/2026-10-01-daemon-core-sketch.md)、[plan 第三段 m3](../../../plan/m3-daemon-core.md)；現行程式 [aos-daemon](../../../src/py/README.md#aos-daemon第三段最核心-daemon)（`lib/aos_daemon.py`，有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 13 KB 超過 8 KB 門檻，按標題逐字拆進 `core/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-640-清單起點週期.md](core/01-B-640-清單起點週期.md) | B-640：最核心 daemon：定期叫 aos-exec〔使用者方向 2026-10-01〕 |
| 2 | [02-B-640-輸出停機鎖檔模組.md](core/02-B-640-輸出停機鎖檔模組.md) | 輸出；停機：Ctrl-C 直接退出；同一份設定只能開一個：鎖檔；模組：`modules`；第一版默認一切正常 |
