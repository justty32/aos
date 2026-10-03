# Q4 與 orphan 證據摘要

重跑：`python proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/node/repro.py`。
完整結果在 `results.json`；`run.log` 是同一結果的 stdout。只用自己建立的 `/tmp/astra5-node-*`，每個案例 finally 都清自有程序與目錄；沒有呼叫 real.py 或真 LLM。Q4 使用真 sleeper、真 aos7-run、真 Daemon.scan/reaper；時間線保持 paused 以精準控制 scan 視窗。網路錯誤採系統呼叫邊界的 fault injection，沒有聲稱實際架設 NFS。

## 新問題 A：掃描失敗被當成 node 消失，I/O 故障變成 kill〔bug〕

- **核心／需求：** S-03、S-06、S-07；N-22、N-26、N-12。優先必要。
- **重現：** 建 n、start_task 真正啟動 sleeper，Daemon.live_of 已記住 pgid。單次 `os.scandir(n)` 注入 ESTALE（模擬網路掛載失效）；另一案對 n/.aos/timeline.json 的 `os.stat` 注入 EIO。執行原本的 `Daemon.guard(Daemon.scan)`，再恢復 I/O。
- **看到：** 兩案 n 與 timeline 實體都存在，sleep 卻死了，log 是 `node-`、`node-gone-kill(ok:true)`；`io_errors_delta=0`，完全沒有 I/O error。ESTALE 被 `os.walk` 預設忽略；EIO 被 `os.path.isfile` 吃掉變成 False；guard 根本接不到。
- **原因：** `aos7_daemon.py:23–36` 的 scan_nodes 只回「看見什麼」，沒有掃描完整性或 unknown；`scan()` 把集合差直接當刪除，再 `reap_gone`。
- **修正方向：** scan 回傳 found + 不可觀測範圍／錯誤；對 EIO、ESTALE、EACCES 等保留舊 node 與 pid 記錄，記錄 scan error/unknown，恢復後重掃；只有確認的不存在才依已答 Q4 kill。這不要求推翻 Q4，也不需再問使用者是否接受 cgroup。

## 新問題 B：原有 --rounds 測試失敗路徑會留下指向已刪空間的 agent〔bug〕

- **核心／需求：** S-06、S-10、S-11；N-09、N-26 只涵蓋 daemon 管得到的任務，測試直接 Popen 的生命週期沒有 owner。優先必要（測試／demo 清理契約）。
- **重現：** 原封執行 `tests/test_agent.py::RoundsFlag.test_rounds_n_exits`，只把 Popen 的實際 agent 啟動延後 0.5 秒，並把 mkdtemp 前綴導到本輪空間。原測試在 0、0.15 秒覆寫 tock 為 1、2；agent 啟動只看見 round=2，實際只處理一次，`--rounds 2` 還缺一次。5 秒後原 `communicate(timeout=5)` 拋 TimeoutExpired。
- **看到：** 原 unittest 的 addCleanup(rmtree) 已刪除 root，但 agent 0.7 秒後仍活，`/proc/PID/environ` 的 AOS7_ROOT 確實指向已刪 root。這完全重現使用者描述的現象。本輪最後另外收掉它；沒有觸碰使用者之前找到的兩個程序，因此無法證實那兩個的歷史一定來自此測試。
- **原因：** `tests/test_agent.py:355–366` 只有目錄 cleanup，沒有 process cleanup；`aos7_agent.run()` 收不到 tock 就每 0.5 秒重試，`--rounds` 是收到 N 次 tock，不是最終 round 達 N，也不是牆鐘期限。`wait_tock()` 將不存在當沒有新消息，因此刪檔不會使它結束。測試直接 Popen，沒有 daemon Q4 來收。
- **最簡對策：** Popen 成功後立即 addCleanup／try-finally 註冊「terminate → communicate/wait → 有界等候後 kill → wait」，保證它在 rmtree 之前執行；每次送 tock 後等 state/progress 確认該回合，取代固定 sleep(0.15)。不必改 `--rounds` 或 S-11 語意，不必讓任務自行猜「暫時讀不到檔＝該死」。

### demo 同類異常路徑也存在〔bug〕

`demo/play.py:46–87` 正常路徑有 stop(kill) 與殘留程序清除；但整段沒有 finally。`demo_stop_write_error` 用真 daemon＋fake agent，在寫 zz-play-stop.json 注入 EIO，`play.run()` 直接拋錯，daemon／任務尚活。呼叫端刪 root 後，Q4 收掉節點任務，但 daemon 繼續活，status/log 又把 root/.aosd 建回。最簡對策同上：demo owner 的 finally 在刪 root 前無條件停、等、強殺並回收自己起的 daemon／任務；不要只把正常路徑的末尾當 cleanup。

## Q4 邊界對照〔技術選型；已答決定的代價〕

| 案例 | 看到什麼 | 判斷 |
|---|---|---|
| 短暫 rename：n→.hidden；掃一次；立刻搬回 | 原 task 被 kill，即使 kill 完時 n 又存在 | 符合已答「搬家算消失」；操作上有破壞性，不能用 rename 當無害設定更新。不另列為違反 Q4 的 bug。 |
| timeline.json 正規原子更新 | 1000 次 write_json/os.replace，另一 thread 同時 500 次 scan；task 存活、無 node- | 本地 POSIX 同檔替換沒有不存在空窗。本轮沒有重現「原子替換瞬間誤殺」。先 unlink 再 rename 並不屬於此保證。 |
| 清掉 AOS7_NODE/AOS7_TID，但 pgid 已被 daemon 採樣 | 刪 node 後成功 kill | 單改環境未必逃得掉，程序群組記錄有效。 |
| 清掉上述環境；先讀空 live cache，再起 task，採樣前刪 node | `_pids={}`；node- 後 task 仍活，無 node-gone-kill | 0.25 秒 cache 採樣窗口；runner 被 `_escaped` 排除，記憶體根本沒捕獲 group。任務刻意清除識別環境已落在 Q1(a) 責任邊界，應明確揭露，不能寫成絕對可收。若想加強可讓 spawn 成功時註冊 pgid，屬技術改善。 |
| 同樣採樣前刪 node，但保持 AOS7 環境 | 成功 kill | 正常任務由環境 fallback 接住，不能把 env-scrub 案推論成一般任務必漏。 |

## infra-needs.md 建議

1. **N-26 已做→部分，優先應該→必要。** 已有確定刪除的回收，但「看不到」與「確定不存在」混同會造成無故 kill；應列觀測錯誤與恢復後重掃驗收。短暫實際 rename 本來就屬已答 Q4，不再追加未經授權的「搬回免死」政策。
2. **N-22 部分保留並補強文字。** OSError guard 只能處理冒出的例外，walk/isfile 吞掉的 I/O 故障不記數且可觸發破壞性動作；不是只有「還缺降級策略」。
3. **N-12 的 unknown 從附帶缺項升為近期必要驗收。** unknown 應至少能阻止掃描不完整時的 delete/kill 判斷；不能只有對外狀態顯示。
4. **N-25 保留已答 Q1(a)。** 補 0.25 秒採樣＋環境 fallback 的保證前提，不以此重新推銷跨 cgroup 的無條件回收。N-26 所稱「daemon 記各 node 活任務 pgid」應寫「週期採樣，未採到的靠環境 fallback」。
5. **新增必要：測試／demo／探針建立的程序先回收才刪空間。** 支援 assertion、TimeoutExpired、OSError、KeyboardInterrupt 的 finally；保存 PID／Popen handle，回收有期限、有剩餘清單；不能依賴 --rounds 一定能退出。這是基礎設施的驗證工具生命週期需求，不是 agent 產品新功能。
