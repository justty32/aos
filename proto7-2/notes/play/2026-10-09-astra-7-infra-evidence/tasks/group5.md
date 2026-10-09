# 子線 group5：blueprint-loop7 §7 第 5 組（數值、遷移漏接與模組）＋第 6 組 T8 抽驗＋文件項

你的線名 `group5`，evidence 目錄 `proto7-2/notes/play/2026-10-09-astra-7-infra-evidence/group5/`。

1. 第 5 組每條一案，照 `proto7-2/notes/blueprint-loop7-items.json` group==5 各列 `test` 欄寫**獨立探針**（不只是跑作者測試）：A8-11＋R8-20（含 interval 10**309、負巨數、改回合法值下一回合生效；同 daemon 另一 node 不受影響）、R8-05、N-06、A8-07＋R8-09、N-66 subroot（三層 subd：D2 的 .aosd 落在正確位置、D1 daemon.lock 沒被搶、孫任務 env 無父層 SUBROOT）、N-66 audit＋subd（D9 `AOS7_AUDIT_ALLOW`）、N-86、R8-04、R8-06（100 圈 CPU 不忙轉、n 大不炸）、R8-07（fd 不長）、R8-10、R8-11、R8-12、R8-28、R8-17、R8-18（連續恢復 50 次 recovering.json 有界）、R8-24、R8-25、R8-26。不排的 R8-30 跳過。C8-03 由 pack4 線做，你跳過。
2. 確認 proto7-1 的 `test_interval_huge_int` 已搬回 proto7-2（找出在哪個檔、單跑一次）。
3. 第 6 組 T8-01～08：§7 要求「拿掉故障注入就轉紅」各手動驗一次。你**不能改 tracked 檔**，做法：把該測試檔複製到 /tmp 自己的副本（或在 /tmp 建一份 worktree 外的完整 proto7-2 複本 `cp -a`），在副本裡拿掉注入，跑該案，記錄確實轉紅（失敗訊息摘要）；再跑原版確認綠。8 條各一次。
4. 文件項（§7 文件）抽查，每項記「有／無＋檔:行」：spec §2.3／§2.6／§4.3／§5.5／§6 各一句（對應 loop7 改動）；契約卡 2.1（`proto7-2/notes/component-contracts.md`）；`proto7-2/notes/problems.md` 有 A8-05～A8-11、C8-01～03 列（I 隊可能還在補，若沒有就記「未見，HEAD=…」不要當 bug）。
5. 自由挖：K3／K4／M 改動（`git diff 510dd134..HEAD -- proto7-2/lib/aos7_daemon_timeline.py proto7-2/lib/aos7_mount.py proto7-2/lib/aos7_tick.py proto7-2/lib/aos7_fs.py proto7-2/lib/aos7_tock.py proto7-2/lib/aos_directives.py proto7-2/modules/`）的新邊角：interval 上限一年的邊界值、多個 timeline 欄位同時非法、`AOS7_AUDIT_ALLOW` 含空段／相對路徑／node 外路徑、history 新編碼與舊檔名共存（同 node 新舊兩個檔？）、mount 讀連結出錯留請求是否會永遠重試。
