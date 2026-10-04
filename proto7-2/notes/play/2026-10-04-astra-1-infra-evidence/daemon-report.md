# daemon／控制分項證據

命令：`PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/daemon-probes.py`。

獨立探針 11 項都完成；「完成」指情境建立與資料採集成功，**不等於承諾全部通過**。結果見 `daemon-probes.json`；既有 103 項基準結果由主代理收在 `regression.json`。最後一次探針 11.164 秒，暫存資料夾已刪除、依本次暫存路徑比對 `/proc/*/{environ,cmdline}` 的殘留 PID 為空。測試沒有呼叫 LLM；子程序只有本機 Python、shell、sleep、true 與原型工具。

## 實測判斷

| 承諾 | 判定 | 證據 |
|---|---|---|
| register／unregister、重開沿用 nodes.json | 成立 | `regression.json` 的 `TestRegister` 7 項通過；取消預設收任務、no-kill 留任務、清單保留及重開接續均有實際程序測試。 |
| node 刪除／搬走 → missing、保留登記、不建鬼目錄 | 成立 | 基準 `TestNodeGone.test_rm_rf_kills_and_stays_registered`、`test_move_kills_old_new_place_needs_register` 通過。 |
| node 換 symlink → missing | 不成立 | `symlink_same_inode`：先搬至 moved、a→moved symlink，回合 2→5、仍 running、原 PID 活著；`symlink_outside_root`：改指測試 root 外另一個受控空資料夾，daemon 隨後在目標建立 `.aos/round.json` 並繼續 running。兩目標都仍在證據暫存目錄內。 |
| EACCES／EIO 不當消失 | 成立，狀態呈現有侷限 | `actual_eacces` 用 uid 1000 真正 chmod 000；原任務存活、phase error、round_open null，恢復後同 PID 接續；`stat_io_fault_injection` 另在 `check_nodes` 精準注入 EACCES/EIO/ESTALE，均保留同一 timeline、不進 missing、不開 reaper。唯權限受阻時 status.live=[]，無法從此欄得知活任務仍在；last_error 有明確看不到訊息。 |
| early_tock 預設 false／true 節拍 | 成立 | `timing_modes`：1800ms 設定，fixed 回合 1.809s、early=false；early 回合 0.048s、early=true。 |
| wake 與 P2-01 | 部分 | `timing_modes`：early idle 的 wake 0.108s 開下回合，fixed 同時仍留在原回合，符合 P2-01；但 `wake_in_active_early_round`：2500ms、任務 sleep 0.7s，running 中 wake，0.768s 就進下一回合，因 kick 留到 idle 生效，文件「回合中照舊」未說會排入待用 wake。 |
| pause owner／resume wake | 部分 | `pause_owners`：A/B pause、A resume 後只剩 B；daemon 重開保留 B；B resume 馬上續跑。`rounds_owner_collision`：A resume rounds=1 尚被 B pause 擋住時，B resume rounds=3 直接覆寫 A 倒數，跑完 3 回合只 B 被加回，A 承諾遺失。 |
| 世代／action.lock／舊動作接管 | 核心保護成立，診斷部分 | `stale_generation`：gen9 下以 gen8 tick/tock 都回 stale，沒有 round 或 birth；基準 `test_new_daemon_reaps_old_holder`、`test_kill9_daemon_new_daemon_recovers_round_no_double` 通過。未知 holder 沒錯殺；基準唯一失敗另見下文。 |
| fd 寫入、搬移中途 | 成立 | `fd_mid_move`：在 tick-opened 精準搬 node，birth/exit code127 都落 moved、不建舊路徑；真正 runner sleep 途中搬 node，exit code0 落 moved2、不建舊路徑。基準 root 搬走亦能 stop/kill 並寫新位置 status。 |
| 控制洪水／壞檔／回條寫失敗 | 成立於既測邊界 | 基準 `TestCtlFiles`：3000 控制仍更新 status、FIFO／資料夾／非 json／破損 json／未知 op 有失敗回條；回條父路徑被一般檔堵住仍處理 stop。CLI 固定檔名，20 次 wake 只剩 register/wake 兩個回條。手寫無限新檔名仍會無限增加回條，是每名留一份的範圍限制。 |
| 子 daemon owner／daemon 分塊、allow_stop、stopped.json | 成立於既測邊界 | 基準 `TestOwnership` 全通過：owner false 拒 stop；父 kill 帶走 child 任務；allow_stop true 寫 stopped 並阻止 keep 重起；刪 stopped 恢復；手動重開保留 owner 但更新 daemon.pid。 |
| restart/reload／掛載及執行中加掛 | 基準通過，事故窗口另由主代理測 | 基準 `TestCtl`、`TestMounts` 通過：restart 同槽新 run/保留 state，reload 差異回條、無效定義不 kill，動態掛載回條、restart 攜帶 dyn 並清舊 mount-done。 |

## 建議納入 A2 的問題

1. **〔bug〕登記後未持續檢查 symlink 與空間邊界。** `aos7_daemon.py:394` 使用跟隨連結的 `os.stat`，只比目標 inode；相同 inode 的替換看不出來，不同 inode 在下一圈又直接建 Timeline（:425–429），且未重跑 register 的 realpath 邊界檢查。這不只是 missing 呈現，而是可能在新目標建設施檔。應持續維持登記時的路徑條件；依任務書要求，符號連結應保留登記但 missing。
2. **〔bug〕不同 owner 的有限回合要求互相覆寫。** `aos7_daemon.py:255–256` 每 node 只有一個 steps，而 spec §2.4 承諾「之後同一 owner 的 pause/resume 清掉倒數」。獨立探針證明 A=1 被 B=3 蓋掉；可為每 owner 保留計數，或至少明確拒絕衝突而不能默默成功。
3. **〔bug〕長路徑截掉錯誤類型／原因，造成基準測試可重現失敗。** `aos7_daemon_timeline.py:113` 對整段錯誤取末 300 字；holder 診斷的長 action.lock 路徑在後段，把 `stale-holder-unverified` 與缺 gen 原因擠掉。`unverified_holder_diagnostic` 五次取樣 holder 一直活著、last_event.ev/why 正確，但 last_error.err 只有路徑尾與提示、prefix_visible=false。因此 103 項中 `test_unverified_holder_not_killed` 的等待錯誤字串失敗；這是診斷輸出／測試對路徑長度敏感，**不能誤報為 holder 被錯殺或世代保護失效**。錯誤代碼與原因應另存固定欄位，僅截短路徑／stderr。
4. **〔bug，文件契約〕回合中 wake 被保留到 early idle。** `_kick` 不分 phase 設 kick，step4 不消費、step6 略過 idle；實際是「本回合不打斷，但完成後省略等滿 interval」。可直接把實際語意寫清楚，或只在 idle 接受 kick；它不同於已公開的 P2-01（fixed wake 無效果），不需新增大設計決策。

EACCES 恢復後 last_error 留舊訊息是「上一次錯誤」語意，不另列 bug；但 live=[] 容易被當成已無活任務，可列狀態可讀性的技術改進。
