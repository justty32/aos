← [kernel](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 與 [LM Studio 真跑](../../notes/2026-09-23-rearch/lmstudio-run.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.1：cpu 家「缺的補齊、不覆蓋」（審查 C-1）。
- §1.3：ack 名加 digest（A-3、B-5）；boot-kill 兩顆時加 cpu 名（B-6）。
- §2：省略 name 從 0 起（B-7）。
- §3 第 10 步：空格不寫 log（真跑 ⑤-4）；log 不保證涵蓋崩潰中途（B-11）。
- §6：init `--cpu`、`ack`、`ls` 摘要／`--json`、`-h`（真跑 ⑤-2、3、5）；boot 第 2 步交接兩顆 kcpu（A-4、B-6）與硬砍例外（B-12）；
  第 3 步只丟未出貨的 stops（B-10）；第 4 步補齊家（C-1）。
- §3 第 4／10 步（09-24 kernel-crash，C-7／C-8 真 KILL 實測，見[報告](../../notes/2026-09-24-kernel-crash/README.md)）：出貨「送出後、清帳前」崩潰，下一格照「EEXIST 當已放」重放，
  保守讀法是**接收者可能已經處理完**：ack 重放用新一格的 seq 取名，同一則回音可能收到兩份不同名的 ack（第二份無害）；
  stop 若接收的 cpu 已消化並退出，重放會在它家留下一份同名 `stop-<chain>.json`，下次 boot 的新 cpu 讀到就退 0、下一格第 7 步再拉起（同 B-10 跨代 stop，等使用者拍）。
