← [daemon](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.2：`last_exit`／重拉只看孩子實際退出碼，exit 檔寫失敗另記（審查 B-3）。
- §2：缺檔一律 `SpawnFailed`（A-1、B-2），程式同步改了。
- §6：新增 `aos-daemon stop` 子命令與 `-h`（LM Studio 真跑報告 ⑤-1）；§7 同步一句。
- §6.1：不收孤兒的 PID 1 環境在保證外（B-9）。
- §2 對 §6.1（崩潰窗口測試 C-2／C-3，見 [daemon-crash 筆記](../../notes/2026-09-24-daemon-crash/README.md)）：§2「崩在寫表之後、回音之前……重送 spawn 回它的 pid（冪等）」只在同一任 daemon 還活著時成立；daemon 被 KILL 後照 §6.1，新任先把舊孩子弄死、原單對帳成 `Interrupted`、表從空開始，重送 spawn 拉新的一顆（程式本來就這樣，未改）。
