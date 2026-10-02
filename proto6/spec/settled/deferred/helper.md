# 可選 root helper 與 aos-as

← [整理區](../README.md)｜[舊 daemon](daemon/README.md)｜[現行 daemon](../daemon/README.md)｜[通用 tick](../tick.md)｜其餘身分規則：[身分與資源](../../base/identity-resources.md)

> **這篇整篇在暫緩區**（2026-10-01）：可選 root helper 與 `aos-as`；helper 之後另做成模組。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

本篇只有 B-303，從[身分與資源](../../base/identity-resources.md)搬來，條號不變。身分額度的歸屬（B-301）、部署（B-302）與磁碟（B-304）仍在原篇。

## 分檔目錄

> 2026-10-02 整理：原檔約 9 KB 超過 8 KB 門檻，按標題逐字拆進 `helper/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-303-helper模式與固定動作.md](helper/01-B-303-helper模式與固定動作.md) | B-303：可選 root helper 與解析分界〔使用者方向 2026-09-29〕 |
| 2 | [02-B-303-aos-as.md](helper/02-B-303-aos-as.md) | `aos-as`：切換帳號的包裝 |
