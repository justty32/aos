# daemon 協議：訊息 socket 與 aos-mq

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-645](../../daemon/mq.md)｜[慣例](../../conventions.md)

本篇只有 P-125，只寫格式。信箱、急件叫醒的規則以 [B-645](../../daemon/mq.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[第十四批：aos-mq 取信](../../../../notes/verdicts/11-tick-as-unit/16-1001-第十四十五批.md#2026-10-01-第十四批aos-mq-取信)、[第二十一批：跨 daemon 用 socket 路徑當前綴](../../../../notes/verdicts/11-tick-as-unit/23-1001-第二十一批.md#2026-10-01-第二十一批跨-daemon-用-socket-路徑當前綴)、[第二十二批：廣播與頻道](../../../../notes/verdicts/11-tick-as-unit/24-1001-1002-第二十二二十三批.md#2026-10-01-第二十二批廣播與頻道)、[plan m3m 模組四](../../../../plan/m3m-daemon-modules/05-模組四-訊息.md#模組四訊息modulesmq)；現行程式 [訊息與 aos-mq](../../../../src/py/README.md#訊息與-aos-mqm3m-模組四)（有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 13 KB 超過 8 KB 門檻，按標題逐字拆進 `mq/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-125-設定與請求.md](mq/01-P-125-設定與請求.md) | P-125．訊息 socket、環境變數與 aos-mq〔使用者 2026-10-01 第十二批；欄位名照現行程式〕 |
| 2 | [02-P-125-回應與環境變數.md](mq/02-P-125-回應與環境變數.md) | 回應；環境變數 |
| 3 | [03-P-125-aos-mq.md](mq/03-P-125-aos-mq.md) | aos-mq |
