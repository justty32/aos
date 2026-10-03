# proto7-1 試玩紀錄

← [proto7-1](../../README.md)｜[problems.md](../problems.md)

試玩者只從 README 進入、照文件操作，再回報分數與新問題。一輪一列。

| 日期 | 試玩者 | 報告 | 證據 | 結果與後續 |
|---|---|---|---|---|
| 2026-10-03 | astra | [2026-10-03-astra.md](2026-10-03-astra.md) | [2026-10-03-astra-evidence/](2026-10-03-astra-evidence/)（全收，沒有超過 200 KB 的檔） | 分數 4／4／3／3／3。新 bug 一個（二-1：任務 ctl.json 是 `[]` 這類非物件時 tick 丟例外、時間線反覆卡住、status 停在舊回合）**已修**：非物件寫失敗回條；daemon 回合數以 round.json 為準，tick／tock 失敗時 status 帶 `last_error`（測試 `test_ctl_not_object_gets_failed_receipt`、`TestTickFailure`）。二-2、二-3 補進 [P-04、P-08、P-10、P-11](../problems-core.md) 當新證據。 |

注意：這一輪是在 D-1 改成掛載**之前**玩的。報告與重現腳本裡的 `dirs` 現在已換成 `mounts`（見 [spec.md](../../spec.md) 第 4 節），跨 node 的寫入要經過掛載點。
