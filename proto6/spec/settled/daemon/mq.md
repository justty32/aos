# daemon 訊息模組與 `aos-mq`：多扇門、每項一個信箱

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜[收屍／cgroup B-644](cgroup.md)｜格式：[P-125](../protocol/daemon/mq.md)｜舊設計：[暫緩區 B-614](../deferred/daemon/messaging.md)

本篇只有 B-645，寫訊息模組**做什麼**（2026-10-02 第二十五批改成多扇門：每項訂門、從門寄進來的信原樣放進訂了的項的信箱並叫醒它們；socket 一律 666、權限靠資料夾）。socket 上的請求與回應、`aos-mq` 的用法與錯誤代碼，寫在格式篇 [P-125](../protocol/daemon/mq.md)。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[第十四批：aos-mq 取信](../../../notes/verdicts/11-tick-as-unit/16-1001-第十四十五批.md#2026-10-01-第十四批aos-mq-取信)、[第二十二批：廣播與頻道](../../../notes/verdicts/11-tick-as-unit/24-1001-1002-第二十二二十三批.md#2026-10-01-第二十二批廣播與頻道)、[第二十五批：訊息多扇門（取代前面幾批的訊息做法）](../../../notes/verdicts/11-tick-as-unit/26-1002-第二十五批.md#2026-10-02-第二十五批訊息多扇門)、[plan m3m 模組四](../../../plan/m3m-daemon-modules/05-模組四-訊息.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（`lib/aos_daemon_mq.py`、`lib/aos_mq.py`，有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 13 KB 超過 8 KB 門檻，按標題逐字拆進 `mq/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-645-信箱與socket.md](mq/01-B-645-信箱與socket.md) | B-645：訊息模組與 `aos-mq`（門、訂閱、寄與叫醒、信箱、跨 daemon、socket 權限、環境變數） |
| 2 | [02-B-645-aos-mq與先不做.md](mq/02-B-645-aos-mq與先不做.md) | `aos-mq`；跟其他模組；先不做；驗收 |
