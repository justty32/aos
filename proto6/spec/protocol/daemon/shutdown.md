# daemon 協議：停機與存檔重開

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-114．前景 Ctrl-C 停機〔使用者方向 2026-09-29，裁定「軟性標準」／CLI H-036 第 1、7 步〕

`aos daemon --config F` 收到 SIGINT（Ctrl-C）或 SIGTERM，依 [B-604](../../daemon.md) 停止新登記／叫醒／開格，對在途 tick 送 SIGTERM 讓它們優雅結束；shutdown_grace_ms 到期以 `cgroup.kill` 依執行器清空，再次收訊號也不略過驗證。清空後存 P-116 狀態、讓 helper 退出，清 socket 與 PID 檔，回 0。失敗回 125：node 問題寫 node 事項／stdout 警告，自身錯誤寫 daemon 事項／stderr。只 kill helper 不是停止 daemon。

首版沒有跨終端 `aos daemon stop` 或 shutdown IPC。非正常死亡後仍由下次啟動的 B-603 檢查舊程序，不因 socket 不見就推論已全空。

**驗收：**有執行中 node 時 Ctrl-C／SIGTERM 都不開新格，等全部受管後代與 helper 全空才回 0；清不空不得回 0。

## P-116．存檔與重開〔使用者方向 2026-09-29〕

`state_dir/state.json` 用 [daemon-state schema](../schemas/daemon-state.schema.json)：`{version:1,clean_shutdown,registrations:[...]}`。每項存 node_id、parent_id（根為 null）、identity_grant、once、paused、pending，以及有設定的 interval_ms／provision。不保存 PID、程序或業務結果。

正常 Ctrl-C／SIGTERM 收尾後寫完整登記表、pause 與未處理 wake，clean_shutdown 為 true。pause 有變動時最多每 pause_save_interval_ms 原子寫一次，標 false；意外退出最多遺失最後這段時間的 pause 變動。寫入採 P-003 的完整暫檔與原子替換，失敗寫 daemon 自身事項並報 stderr。

啟動先讀回，依目前 roots、inst 與父鏈重新核對登記、身分和授權；缺檔／壞檔便從 roots 重建，壞檔留診斷。讀回後先將 clean_shutdown 原子改 false，再接受工作；依 [B-603](../../daemon.md) 清空舊程序（仍有程序的 node cgroup 先 SIGTERM、寬限後 `cgroup.kill`）後自動對每個 root 留一個 wake，paused 者保持關閘，resume 才跑。

乾淨停機可接回尚未啟動的 once；意外退出的舊 once 不恢復為可啟動登記，不能把舊 pending 或空 last_tick 當作從未啟動；交原發起者按工作結果／unknown 核對。其他未處理 wake 照常接回。boot_id 每次重生；頂層發現改變後逐層核對、補回成員，不必每格全量重登。daemon 自身 attention 依 P-601 接回、透過 IPC 查；node 事項留在各自目錄。
