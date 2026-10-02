# daemon 協議：控制 socket 與 aos-ctl

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-641](../../daemon/control.md)｜[慣例](../../conventions.md)

本篇只有 P-121，只寫格式。各指令做什麼（補跑、暫停、恢復的規則）以 [B-641](../../daemon/control.md) 為正本。

依據：[第二十批篇末「`insts` 改成物件＋控制模組裁定」](../../../../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)、[plan m3n](../../../../plan/m3n-control-module.md)；現行程式 [控制模組與 aos-ctl](../../../../src/py/README.md#控制模組與-aos-ctlm3n)（有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 9 KB 超過 8 KB 門檻，按標題逐字拆進 `control/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-121-socket請求回應.md](control/01-P-121-socket請求回應.md) | P-121．控制 socket、環境變數與 aos-ctl〔使用者方向 2026-10-01；欄位名照現行程式〕 |
| 2 | [02-P-121-aos-ctl.md](control/02-P-121-aos-ctl.md) | aos-ctl |
