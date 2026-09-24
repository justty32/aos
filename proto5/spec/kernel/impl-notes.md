← [kernel](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 與 [LM Studio 真跑](../../notes/2026-09-23-rearch/lmstudio-run.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.1：cpu 家「缺的補齊、不覆蓋」（審查 C-1）。
- §1.3：ack 名加 digest（A-3、B-5）；boot-kill 兩顆時加 cpu 名（B-6）。
- §2：省略 name 從 0 起（B-7）。
- §3 第 10 步：空格不寫 log（真跑 ⑤-4）；log 不保證涵蓋崩潰中途（B-11）。
- §6：init `--cpu`、`ack`、`ls` 摘要／`--json`、`-h`（真跑 ⑤-2、3、5）；boot 第 2 步交接兩顆 kcpu（A-4、B-6）與硬砍例外（B-12）；
  第 3 步只丟未出貨的 stops（B-10）；第 4 步補齊家（C-1）。
