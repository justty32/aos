# once／三態／回合／控制冪等回歸子報告

執行：`PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/once-regression.py`。

26 個隔離案例。腳本前半直接沿用上一輪 `once-probes.py` 的 worker、8 個 SIGKILL 邊界、PID 清理及 identity 測試；birth 損壞及 /proc 案只把「等第二份出現」改成觀察沒有第二份，不再用預期舊 bug 的 wait 當斷言。回合案例呼叫真正 tick／tock，不呼叫上一輪已失配的 `timeline.read_json3` monkeypatch；現版改用共同 `read_round`，完整 daemon 狀態另見 daemon 證據。restart append 邊界沿用 `docs-and-crashes.py` 的真 subprocess SIGKILL。

本腳本跑了三次以逐步加測；最後一輪結果共 26 案，JSON 是最後一輪，不把重跑算更多獨立覆蓋。每輪 finally 清理皆完成。`once-cleanup.json` 最後 26 案存活 PID 皆空、remaining_test_pids 空、temp_root_exists false；僅在 evidence 下建立 once-work-*，沒有另外建立 /tmp 資料夾。

## A2 判定

| 編號 | 判定 | 實證（once-regression.json） |
|---|---|---|
| A2-01 | 原問題已修；EACCES 規格例外另審 | `three_state.proc_stat_eio`、`proc_all_eio`、`birth_bad_proc_environ_eio`：started 空、原 PID 仍活、pid.json 不改；前兩案 LIVE+unsure，第三案 UNKNOWN，tock errors 均有原因。`identity.runner_before_pid` 舊真 sleep orphan 先收掉，才起 run2。 |
| A2-02 | 已修 | `rounds.round_eio/round_bad/round_open_missing`：tick/tock 均 Unknown，round bytes 完全不改、last-round 保持 1，不覆寫尚未提交的 2。`direct_tick_open` 的 tick 拒絕後 tock 正常提交 2。 |
| A2-03 | 已修 | `once_corrupt_birth`：真 SIGKILL 在刪 once 前，run1 副作用已發生，birth 破壞為 `{`；tock 正確報 o#1/code0，下個 tick started 空、once 刪除，副作用只 [1]。 |
| A2-05 | 部分：原單次崩潰窗口已修，複合故障仍重做 | `restart.original_append_sigkill` rc=-9，恢復前後 tasks 只有一項，總執行 [1,2]。新增 `ctl_unlink_denied_birth_reused` 卻能以同一份請求重起兩次。 |
| A2-08 | 本分支已修，長路徑由主報告交叉驗 | `three_state.proc_starttime_none.summary.errors` 有 phase=unsure 及可讀原因，不再只藏在內部 View。 |

`once_boundaries` 八案 rc 全 -9；before/after-launch、before-birth、before/after-runner、before/after-delete 均恰一次。after-birth 為 0 次且報 lost，仍是明揭 at-most-once 取捨，不算回歸失敗。`identity.old_run_residue` 仍不把 RUN1 活程序當 RUN100。

## 矩陣審查

`test_matrix_once.py` 的 18 個 launch/runner crash 組合與 6 個 restart crash 組合，位置確實是 Popen/檔案 commit 交接邊界；test_point 真 SIGKILL subprocess，不是回傳一個假失敗，與真程序崩潰同一控制流。before/after-launch 的 keep 加一個 companion once 才經過鉤子，這點有明說。after-popen runner 活著當活是合理修正；它避免在交接沒寫 pid 時殺掉正常 runner。

但 restart 六案只在一次 crash 後恢復，ctl 刪除隨即成功；缺少「ctl 長期消費失敗 + restart run 已完成 + keep 自動換 run」組合。這個組合使最新 birth 的 ctl_id 消失，是綠燈下仍重做的盲點。明確 id 長度、mtime 保留、跨槽相同雜湊亦未覆蓋。

`test_matrix_faults.py` 的 healthy proc-list/environ/cmdline 部分會被 pid/runner 已確知活著的快路徑短路；通過不代表鉤子真的被觸發。不過 orphan/deadboth/brokenbirth 有補主動掃描路徑，故不能把整份矩陣說成假測試。其第 16–18 與 192–196 行刻意排除 orphan/brokenbirth × environ EACCES，正是需用真不可 ptrace 任務另驗的規格例外。

## 新缺口：同一 restart 的完成證據會隨 birth 換代消失〔bug，高〕

來源：`aos7_task.py:416` 只查當前 birth 的 ctl_id；`:448` 只查 pending tasks；`:469–474` 寫回條後，unlink 失敗全吞。程式不從 ctl-done 判定完成。

實測 `restart.ctl_unlink_denied_birth_reused`：

1. keep run1 完成，寫唯一一份 `{"op":"restart","id":"one-request"}`。
2. 在每次 ctl-done 真落盤後暫把槽 chmod 0555，隨後呼叫真 `os.remove`，作業系統回 errno 13（JSON 記實際 errno 及 mode），finally 還原 0755。沒有以 mock 直接偽造 EACCES；猴補只用來在明確 commit 窗口控制權限。
3. run2 birth 帶 id:one-request、restart_of=o#1，第一次 restart 已生效。run2 自行完成。
4. tick3 先看到 run2 的 id，認為重播；接著 keep 自動起 run3，新 birth 沒 ctl_id。這個 run3 設定為真 sleep60。
5. tock3 再看仍在的相同 ctl，已忘記它完成過，真 kill run3，回條 `killed 1 group(s); once 項已加進 tasks.json（slot o）`；tick4 起 run4，birth 再次帶 id:one-request、restart_of=o#3。

正常 keep 的 run3 會持續活，現在被舊請求中止，故不是用「keep 本來一直重起」混淆的執行次數觀察。建議完成身分保留在不隨普通 run 換代清除的槽級紀錄，消費失敗必須可觀察；至少補上述複合矩陣，並驗新 run 活著時不再殺。

## 新缺口：請求識別的碰撞與命名域〔bug／技術選型，中〕

`restart.new_mtime` 是控制組：相同內容普通原子重寫，兩個 cid 不同，總執行 [1,2,3]，兩次 restart 都有生效。因此不能泛稱「相同內容一定只做一次」。

`restart.same_mtime`：兩個不同 inode 的新 ctl，內容相同並用 os.utime 保留 mtime；cid 相同，第二次回條宣稱已重起，總執行只有 [1,2]。這是用內容+mtime 當請求身分的技術選型限制；保留時間的複製／恢復、低時間解析度檔案系統都不能靠「有人重寫時間一定不同」證明。當前規格沒有禁止保留 mtime。可要求每件新請求帶完整唯一 id，CLI 也產生 id，或明列 fallback 的限制。

`restart.long_ids`：id 分別是 64 個 x 加 0/1，規格允許不同字串，但 `ctl_id_of` 的 `[:64]` 直接把它們變成同一件；第二件被靜默忽略。這是明確實作 bug，不是 SHA1 機率碰撞。應保留完整 id、雜湊完整 id，或明確拒絕超長，不應靜默截斷。

`cross_slot_ids`：兩槽 o/p 都有獨立 ctl；explicit_same_id 與 same_raw_mtime 兩案均只 o 重起，p 回條 ok:true 且稱「上次已加過」，p 副作用只有 [1]。根因 pending tasks 查 cid 不比 slot。explicit id 應不應 node 全域唯一尚未定義，不宜獨立放大；但 fallback 沒含槽路徑，複製同份 ctl 並保留 mtime 到兩槽確实互相吃掉。建議把識別作用域寫清楚，再以 slot+id 查重。

## 回合人工停點評估

round open=true 的正常情況不是永久停住：直接 tick 的 Unknown 明確寫「先 tock」，隨後 tock 可收尾。BAD/缺open 的兩入口都拒絕屬合理保守；錯誤有 {round:N,open:false} 模板，但「確認上一回合收完」如何核對 started/reaped 與 last-round 並無實際步驟，本分支證據只證明提示存在，不能證明操作者一定能安全恢復。已完成 last-round 的同回合若只是 round.open 缺失，仍要求人工，是可用性選擇，可討論用已提交總結做有條件恢復；不能無条件把 BAD 當關閉。
