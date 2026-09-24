← [daemon](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §1.2：`last_exit`／重拉只看孩子實際退出碼，exit 檔寫失敗另記（審查 B-3）。
- §2：缺檔一律 `SpawnFailed`（A-1、B-2），程式同步改了。
- §6：新增 `aos-daemon stop` 子命令與 `-h`（LM Studio 真跑報告 ⑤-1）；§7 同步一句。
- §6.1：不收孤兒的 PID 1 環境在保證外（B-9）。
- §2 對 §6.1（崩潰窗口測試 C-2／C-3，見 [daemon-crash 筆記](../../notes/2026-09-24-daemon-crash/README.md)）：§2「崩在寫表之後、回音之前……重送 spawn 回它的 pid（冪等）」只在同一任 daemon 還活著時成立；daemon 被 KILL 後照 §6.1，新任先把舊孩子弄死、原單對帳成 `Interrupted`、表從空開始，重送 spawn 拉新的一顆（程式本來就這樣，未改）。

## 池式納入（2026-09-24 proto5-2）

上面講的 `spawn`、孩子表，池式納入後已不存在。實作時跟 proto5-2 草稿字面不同、已寫進本資料夾的決定（proto5-2 實作隊的 D-n）：
§1.1 第 1 版 info 缺 `restart_max_ms` 的預設（D-51）；§1.2 壞 `pool.json` 不開（D-55）、kids 檔寫不進去不送 `go`（D-64）、活滿 `stable_ms` 不寫檔（D-57）、
摘要與刪池失敗每圈重試（D-67）、`pool_summary_state` 只有 gone 算消失（D-66）、沒 `pool.json` 的池資料夾（D-63）；
§3 `TooMany` 上限取小（D-52）、沒 `decl` 不擋（D-53）、池不在 count>0 沒 target＝-32602（D-54）、kill 到 dead／failed（D-59）；
§4 fd 1 接 /dev/null 的做法（D-50）、`restarting` 怎麼算（D-60）、`waitpid(-1)` 與 Popen 共處（D-65）、每圈只看有事的池（D-68）；
§5 halt 時的 kids 檔（D-58）；§6.1 開機只殺 running／killing 的 pid（D-56）；§6.3 CLI 的細節（D-61、D-62、D-126）；刪池後忘掉 decl（D-69，保證外）。
