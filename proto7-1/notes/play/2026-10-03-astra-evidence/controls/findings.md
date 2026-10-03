# 控制檔、崩潰、不理 tock 實驗

入口順序：先讀 README.md，再讀連結的 spec.md。按其格式自建隔離空間；跑完第一組才讀 core.md / problems.md / problems-core.md 去重。**沒有讀 lib/ 或 tests/ 實作**；例外原因直接從 daemon log.jsonl 看得到。全部自啟 daemon / task 已清理，/proc 查核沒有存活的自啟程序（不把已死 zombie 算活）。

重現：從 repo 根依序執行 `python3 proto7-1/notes/play/2026-10-03-astra-evidence/controls/reproduce.py`、`additional.py`、`pause.py`（後兩支用同一目錄完整路徑）。每支在 `/tmp/astra-controls-*` 自建空間，結束前複製檔案快照到此目錄。三份 `*-events.json` / `events.json` 保存故障當下，node 快照則含最後正常清理造成的修改。

## 新 bug：合法 JSON 但非 object 的任務控制檔毒化整條時間線

- S-01、S-06、S-08、S-17，分類〔bug〕。
- `additional.py` 的 task-array-recovery：n 有一個 keep sleeper，另設 healthy 空時間線。等 sleeper 起來後原子寫 `n/.aos/tasks/sleeper-r1/ctl.json` 為 `[]`。
- 0.7 秒後：ctl.json 留著，沒有 ctl-done；n 的 round.json 到 6、open=true，卻沒有任何 rounds 摘要 / tock 通知。status.json 同時寫 n.round=1、phase=idle；healthy 正常到 6。
- `.aosd/log.jsonl` 持續 tick/tock rc=1，含 `AttributeError: 'list' object has no attribute 'get'` 與 `aos7_task.py:187 op = ctl.get("op")`。
- 把同檔改成合法 `{"op":"kill"}` 後立刻恢復，舊 sleeper exit.code=-15，keep 產生 sleeper-r7；摘要從 7.json 開始，1–6 沒補。這不是只拒絕一筆錯誤指令，會阻斷同 node 的任務啟動與 tock；另一條線持續。
- 對照：daemon ctl 的 `[]`、null、破損 JSON、錯誤 op、op=[]、pause node={} / ['n'] 均正常拒絕且回 ok:false。task ctl 破損 JSON/null/未知 op 也正常拒絕，唯 [] 重現毒化。
- 檔案協議足以定位 rc=1，但正常 status 把故障呈現 idle、回合又不一致；要理解根因只能讀 traceback 所露出的 Python 型別假設，spec 沒有告知這種失敗模式。

## 已知問題的新證據

- D-4（兼 D-3）：pause.py 的 busy 任務完全不讀 tock，每 40ms 寫一次 heartbeat。pause 生效後 round 和 tock 都固定在 1；500ms 內 heartbeat 從 4 增至 16。這期間寫 task kill 留 pending、沒有回條/exit；resume 後第 2 回合才執行，exit=-15，且同個 tick 立刻生出 busy-r2。證明 pause 不會凍結 Linux 動作；把「pause＝凍結一切」理解成停止副作用會錯，寫 kill 也不能在 pause 期間止住它。
- D-2：ignore-r1 在自訂 120ms 時間線跨 12 回合而不讀 tock；最新通知停在 11（第12回合仍開著），未被判失敗或殺死。只能看到通知寫過，不能從通知推論任務已處理。
- D-3 延伸後果：crash 的 keep 定義 `raise RuntimeError(...)`，前 11 實例全 exit.code=1 / ended 同回合，連續開到 crash-r12；無退避。此為 keep 語意的新事故證據，不另外重報一條問題。
- typo node：`{"op":"pause","node":"ghost"}` 回 ok:true，`.aosd/paused.json` 保存 ghost；不驗 node 是否存在。可能是預先控制未出生 node 的技術選型，但打錯字的人拿到成功回條、目標線不會暫停。spec 未說明。沒有自行列 bug。

## S-01 可讀性

- 不用讀程式就能搭空間、寫控檔、看任務 crash traceback / exit、看 pending kill，daemon log 也含錯誤摘要；JSON 檔案協議有用。
- README 自己只給 demo/test 指令，建立空間必須跳至 spec；spec 對上述基本操作已足夠。
- 作業系統 daemon 啟停本來就還要執行命令；「只用 cat 和寫檔」能操作的是已啟動 daemon 之上的協議。這裡沒有為此去讀程式。
