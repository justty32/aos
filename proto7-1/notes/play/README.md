# proto7-1 試玩紀錄

← [proto7-1](../../README.md)｜[problems.md](../problems.md)

試玩者只從 README 進入、照文件操作，再回報分數與新問題。一輪一列。

| 日期 | 試玩者 | 報告 | 證據 | 結果與後續 |
|---|---|---|---|---|
| 2026-10-03 | astra | [2026-10-03-astra.md](2026-10-03-astra.md) | [2026-10-03-astra-evidence/](2026-10-03-astra-evidence/)（全收，沒有超過 200 KB 的檔） | 分數 4／4／3／3／3。新 bug 一個（二-1：任務 ctl.json 是 `[]` 這類非物件時 tick 丟例外、時間線反覆卡住、status 停在舊回合）**已修**：非物件寫失敗回條；daemon 回合數以 round.json 為準，tick／tock 失敗時 status 帶 `last_error`（測試 `test_ctl_not_object_gets_failed_receipt`、`TestTickFailure`）。二-2、二-3 補進 [P-04、P-08、P-10、P-11](../problems-core.md) 當新證據。 |
| 2026-10-03 | astra（第二輪） | [2026-10-03-astra-2.md](2026-10-03-astra-2.md) | [2026-10-03-astra-2-evidence/](2026-10-03-astra-2-evidence/) | 試掛載、加掛、outbox。分數 4／3／3／3／3（容易理解 4→3：故障時 `ok:true` 不一定代表真的寄到）。新 bug 五個（二-1～二-5）**已修**：壞加掛請求一律寫失敗回條、不拖垮 tick；自動掛載名稱不撞（只有英數、`-`、`/` 的路徑照舊，其他加短雜湊）；mount_allow 與掛載目標先 realpath、必須在空間根內；audit 用宣告的目標與 dir_fd 判實際落點；收件夾不在時 send 當一般失敗（信進 outbox/failed 記原因）（測試 `TestMountRequestEdges`、`test_audit_uses_dir_fd_and_declared_target`、`test_send_to_deleted_inbox_fails_softly`、`test_tool_exception_does_not_kill_agent`）。二-6、二-8 技術選型；二-7 kernel 移除已被自己 pause 的成員後不再 resume——屬「管轄範圍之後再說」，頂層先定最簡單：kernel 自己 pause 的自己負責 resume，不管還在不在 members，**已做**（`test_removed_member_still_resumed`）。修補帶出的新條目：[M-12～M-14](../problems.md)。 |
| 2026-10-03 | astra（第三輪） | [2026-10-03-astra-3.md](2026-10-03-astra-3.md) | [2026-10-03-astra-3-evidence/](2026-10-03-astra-3-evidence/) | 回歸驗前兩輪 bug；分數 4／3／3／3／3。新 bug 兩個待修：三-1 移出成員到期 resume 後沒清用量、加回又被同一筆用量 pause；三-2 成員搬走讓名冊掛載斷掉、寫名冊直接殺掉 kernel。三-3 memory 全讀歷史（技術選型）。長跑：6 agent 跑 362 回合、5,070 次 tick／tock 全 exit 0，耗時中位約 19 ms 不隨回合變慢，daemon RSS 約 20 MB 不漲，每回合（七 node 合計）約 9 個檔。**後續**：三-1 **已修**（移出成員到期 resume 也把累計歸零，`test_removed_member_resume_clears_acc`）；三-2 **已修**（寫名冊、寫成員／daemon 控制檔丟 OSError 只在 decisions.jsonl 記 `skipped`、跳過那個成員，kernel 不死；cap resume 的理由改寫實際用量與上限，`test_broken_member_mount_does_not_kill_kernel`；帶出 [M-16](../problems.md)）；三-3 **已改**（memory 只讀尾端 max(N, 200) 封，sent.jsonl 從檔尾往回讀，`test_memory_reads_only_tail`，見 [R-13](../problems-real.md)）；長跑檔數：回合總結 `rounds/<N>.json` 改成一個 `.aos/rounds.jsonl` 一回合一行（[P-12](../problems-core.md)、R-10、spec 第 3 節）。 |

注意：這一輪是在 D-1 改成掛載**之前**玩的。報告與重現腳本裡的 `dirs` 現在已換成 `mounts`（見 [spec.md](../../spec.md) 第 4 節），跨 node 的寫入要經過掛載點。
