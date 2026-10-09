# 子線 core3：blueprint-loop7 §7 第 3 組（kill／回收時序）驗收＋deep-play C8-01／C8-02／K-04 壓力重現

你的線名 `core3`，evidence 目錄 `proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/core3/`。

驗收逐條（§7 第 3 組原文）——每條寫獨立探針：
1. R8-01：runner 停在 Popen 前（`AOS7_TEST_HANG=runner-before-pid` 或等效）時 kill 回 `ok:false`、msg 以 unknown 開頭、請求留著；放行後下一次 kill 成功、任務真的死（PID＋starttime 核）。各 3 次。
2. R8-03 前半：nodes.json 寫失敗（D3 `inject("write")`，或 chmod）時 register／unregister 回 ok:false、不變更；重送後記憶體（status）＝磁碟 nodes.json。
3. C8-01：unregister 成功回條後、寬限內 SIGKILL daemon（任務忽略 SIGTERM，keep 單任務）→ 同 root 重起 daemon → 舊 PID 已被收（PID＋starttime＋非殭屍核）。**3／3 中斷＋3 正常對照**。檢查 nodes.json 的 `reaping` 鍵前後狀態。
4. C8-02：node 目錄替換（任務 ready、時間線 running 後 mv 舊目錄、放新目錄同 id）→ 回收中 SIGKILL daemon → 重起：新舊任務不得同時存活（連續快照 ≥30 次，記觀測跨度）；新任務只有在舊任務確認收乾淨後才起。**3／3 中斷＋3 對照**。另做一組「回收未確認乾淨」（`AOS7_TEST_FAULT` 規則檔讓 /proc stat EIO）：node 保持 missing、不開新回合、舊任務仍活；撤規則後才開線且舊任務已收。
5. K-04：keep＋inst 長睡眠、stdin FIFO 讓 aos-exec 停在 Popen 前、殺 runner、tock 走到 resolve、TERM 前放行 FIFO：下一代起來後該 node/tid 的程序只剩一代。**壓力：至少 10 次**（照 blueprint-loop7-items.json K-04 test 欄）。
6. R8-29：node 級回收打記著的 pgid 前做身分重驗——用真程序做「pgid 被不相干程序佔用」情境（例如記錄 pgid 後讓原群組死光、再起一個 setsid 程序且盡可能讓它拿到同號；拿不到同號就改用 mock 層級，照 items json 的做法，並明說是 mock）：不得 killpg 外人。
7. 順手：kill／回收相關作者測試 `tests/core/test_ctl.py`、`test_daemon.py` 各單跑一次當對照（不算驗收）。

另外自由挖：K1／K2 改動（`git diff 510dd134..HEAD -- proto7-2/lib/aos7_task.py proto7-2/lib/aos7_proc.py proto7-2/lib/aos7_run.py proto7-2/lib/aos7_daemon.py`）可能新引入的邊角，例如 reaping 鍵在 nodes.json 半寫／壞型別時、重複 unregister／re-register 同 id 撞 reaping、daemon 連續被殺兩次、stop --kill 時有 reaping 項。每個邊角至少一案，分類照共同規則。
