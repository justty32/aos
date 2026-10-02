# daemon 控制模組：叫醒、暫停、恢復、查詢

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[慣例](../conventions.md)｜格式：[P-121](../protocol/daemon/control.md)

本篇只有 B-641，寫控制模組與 `aos-ctl` **做什麼**。socket 上一行 JSON 的確切欄位、錯誤代碼、`aos-ctl` 的 argv 與結束碼，寫在格式篇 [P-121](../protocol/daemon/control.md)。

依據：[第二十批篇末「`insts` 改成物件＋控制模組裁定」與「m3n 待問 1 先照建議做」](../../../notes/verdicts/11-tick-as-unit/07-1001-最核心daemon.md#2026-10-01最核心-daemon待統一更新-spec)、[第二十五批（環境變數改名 `AOS_DAEMON_CTL_SOCKET`、socket 一律 666）](../../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)、[plan m3n](../../../plan/m3n-control-module.md)；現行程式 [控制模組與 aos-ctl](../../../src/py/README.md#控制模組與-aos-ctlm3n)（`lib/aos_daemon_ctl.py`、`lib/aos_ctl.py`，有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 10 KB 超過 8 KB 門檻，按標題逐字拆進 `control/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-641-指令與細節.md](control/01-B-641-指令與細節.md) | B-641：控制模組與 aos-ctl〔使用者方向 2026-10-01〕 |
| 2 | [02-B-641-aos-ctl與連線出錯.md](control/02-B-641-aos-ctl與連線出錯.md) | `aos-ctl`：送一個指令的小工具；一條連線出錯只影響那一條 |
