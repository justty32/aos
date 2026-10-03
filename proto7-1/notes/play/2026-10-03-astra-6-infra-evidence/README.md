# astra-6 證據與重跑

從這份副本的根目錄執行，Python 標準函式庫即可。不啟動 LLM、不連網、不需要編譯。每支腳本都只寫本證據目錄與自己建立的 `/tmp/astra6-*`；舊腳本建立的空間包在當次 astra6 暫存根裡。請**依序執行**，尤其容量測試不要和其他測試重疊。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/regression.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/legacy.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/boundaries.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/ownership.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/fd_sweep.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/fairness.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/recovery_edges.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/extra_faults.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/owner_matrix.py
PYTHONDONTWRITEBYTECODE=1 python3 proto7-1/notes/play/2026-10-03-astra-6-infra-evidence/verify.py
```

- `regression.py`：原版 `test_astra5` 28 項＋`test_owner_reload` 9 項，逐項結果在 `regression.json`。沒有跑 `test_agent` 全套或任何 real／LLM 探針。
- `legacy.py`：直接載入第五輪 `tasks/stop_only.py`、`tasks/archive_probe.py`、`node/repro.py` 的重現函式。crash 掛鉤沿用第五輪 `crash/sitecustomize.py`，suffix 可匹配 `/proc/self/fd/N`。舊持鎖者現在可能已被產品收掉，因此放行時容許 PID 已不存在；舊 harness 等「倒寫成功」的條件已換成觀察恢復與世代。demo EIO 改用 sleeper，保留故障點而不跑 LLM。agent 僅驗 bob 無信、無 goal 的 idle 通知計數。
- `boundaries.py`：reload／動態掛載／不合法排程欄位、控制檔回條故障、低負載預算、PID 身分檢查、300 組 tick/tock 的 fd 數。
- `ownership.py`、`owner_matrix.py`：Q5 實際子 daemon、任務改 owner／刪 stopped、父 node 搬移、三層所有權、欄位型別、四種起動入口的 stopped 阻擋。
- `fd_sweep.py`：fd 持有期間 rename／symlink、掛載與 runner 路徑、EXDEV 模擬、stop-sweep 的程序範圍與巢狀收尾。
- `fairness.py`：一萬 wake、20／200 條空時間線各 15 秒；容量組單獨執行。20／200 的間隔皆 100 ms，沒有任務。JSON 的 tick 次數包含停機排空階段，**不能當成恰好 15 秒吞吐**；`nodes_round_positive_during_window` 才是窗內觀察。
- `recovery_edges.py`：舊 action owner 缺 starttime、測試 helper 的 atexit 群組回收、兩個 node 爭同一 subroot。
- `extra_faults.py`：巨大 interval 的真 daemon 恢復、總結 append 只留下前 24 字元時的 kill／重播。

`common.py` 的控制器設 subreaper，只為回收自己的孤兒；**產品沒有被改成 subreaper**。每個案例先終止已追蹤的程序，再用 PID 收、wait 掉控制器的剩餘後代，確認沒有後代才 rmtree。JSON 中的 `cleanup` 是測試器收尾結果；產品是否漏收要看各案例在 harness 介入**之前**記下的 alive／survivors，不能把 harness 清掉誤算成產品成功。`regression.json` 的 `pre_harness_cleanup_children` 是測試套件剛結束的瞬間快照，包含 zombie 與尚在退場的 runner，最後都由控制器回收。

`recorded` 只表示成功記錄觀察，**不表示產品通過**；請看報告判定。`harness_error` 表示案例本身未跑完；本次 48 份結果 JSON（含 regression）沒有這個欄位。PID 重用採 starttime 不相符模擬，沒有強迫作業系統重用 PID；EXDEV 是注入，沒有在副本外建立第二個檔案系統。半行總結是明示的短寫故障注入，沒有宣稱自然發生率或測過斷電。

最後一次收尾期間，副本外另有使用者環境的測試程序啟動。`verify.py` 保留完整 pgrep 輸出，分列本副本匹配、外部匹配，並掃描本輪 AOS7_ROOT 環境；`clean` 指本輪空間與程序清乾淨，`global_pgrep_clear` 才表示全域沒有匹配。外部匹配不會被本輪清除。
