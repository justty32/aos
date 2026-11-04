← [cpu](README.md)｜[spec 總導航](../README.md)

# 實作補記（2026-09-24）

依 [實作審查報告](../../notes/2026-09-23-rearch/impl-review-report.md) 回寫；修正輪紀錄見 [impl-fix-round1.md](../../notes/2026-09-23-rearch/impl-fix-round1.md)。不改上面的節號，只把句子補進原節：

- §4.1：`run_target()` 改稱 `run_target_full()`（審查 A-5、B-1），舊入口保留相容。
- §4.3：`ack-`／`stop-` 帶 id 回 `-32600`（B-4）。
- §5.1：控制 pipe 驗信封（A-2）；`go` 帶合法 id 放行是隊長裁決。
- 主人被 KILL 後另一 session 的子程式仍可能活著（§5.3 已列保證外），kernel 那邊的後果見 [kernel §6 boot](../kernel/boot.md) 第 3 步的補句（B-12；2026-09-24 one-boot 後 tick 不在 cpu 上跑，只剩舊版升級收 kernel cpu 時適用）。
