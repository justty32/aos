# daemon、不同約定與人工停點審查

證據：`daemon-review.py`、`daemon-review.json`。本檔供主報告整合；所有案在 `daemon-work/` 下執行，`_cleanup` 證明目錄已刪、記錄的特殊 PID 均不再存活。

## 原重現回歸

| 舊編號 | 結論 | 原案適配與結果 |
|---|---|---|
| A2-04 | 已修 | 重放 daemon-probes.py 的 same-inode 與 outside-root 換 symlink：均 `phase=missing`、原任務 PID 已死，外部 target 無 `.aos`。外部 target 仍在本副本 evidence 內。舊探針原先等待錯誤寫出的 round 檔，現改等 missing 後確認未寫出。 |
| A2-06 | 已修 | 相同初始 A/B pause、A resume rounds=1、B resume rounds=3；r1 A 已再 pause、B 還有 2；再 resume A，r3 B pause。舊腳本只等 r3 會因正確的 A pause 而逾時，故加上中間觀察與 resume A。 |
| A2-11 | 已修 | 原 sleep 0.7s／early／interval 2500ms 案，running 中 wake 到 r2 為 2.439s，已不再約 0.7s 提早開始。 |
| A2-13 | 原 A/B 案已修；整體判定由主報告的其他 owner 組合合併 | 原 docs-and-crashes.py 的 pending owner collision 同 by A/B 請求：路徑不同，daemon 接受兩份，初始 `paused_by=[A,B]`。同 owner 的固定檔名最後寫入者勝仍是文件接受的界線。 |

## 真實 environ EACCES：漏收、假成功與雙開

`real-environ-eacces` 起正常 Python 任務，用 libc `prctl(PR_SET_DUMPABLE,0)` 關閉可追蹤性；沒有更動 uid，也沒有清環境。以 uid 1000 實際讀該任務 `/proc/PID/environ` 得 errno 13，非 monkeypatch。SIGKILL runner 後，環境掃描得到空清單；槽 `kill` 的回條卻是 `ok:true`，訊息同時寫「no process；pid.json 的 pgid … 不是這個任務的群組，沒動它」。任務仍活，tock 的 `alive` 仍是 `k#1`，status 未列 uncertain。

`real-environ-eacces-before-pid` 使用既有 `AOS7_TEST_RUNNER_CRASH=runner-before-pid` 精準讓 runner 在已 Popen 任務、未寫 pid.json 處 SIGKILL；等任務自己留下 ready PID，確認其 environ 真 EACCES 後才 tock。結果 `k#1` 被報 lost，下一 tick 起 `k#2`，兩個任務 PID 同時存活。此處 SIGKILL 邊界是真實生命週期，EACCES 也是核心回傳；鉤子沒有假造生命狀態。

分類建議：

- 〔技術選型，高影響〕以 EACCES 視作不是任務會把不可 ptrace 程序排除在生命週期保證外。spec §11 現在確實明寫接受，不能假裝仍滿足原本任何讀不到都 UNKNOWN 的承諾。無需 setuid 就可重現；setuid／不同 uid 未在本輪實跑，不作已驗證聲稱。若 kernel 後續要跑會自行降低 dumpable 或變更 credentials 的工具，必須明確限制支援範圍，或改用不依赖 environ 的程序所有權機制。
- 〔bug，中〕有 pid/starttime 證據仍活的目標，因群組無法再驗證而未殺，卻回 `ok:true`，是可独立修復的診斷假成功（`aos7_proc.kill_identity` 中群組驗證 false 後空 groups 仍 `return True`）。即使接受不保證收這類程序，回條也應清楚表示未執行／無法确认。

矩陣的 `test_matrix_faults.py` 模組說明明確排除 orphan／deadboth／brokenbirth 的 environ/cmdline EACCES，只留 healthy 及「本來就已死」的 deadboth_skip。healthy 有 pid/runner 的其他證據而不會走缺 pid 的 lost 路徑，綠燈不能替代此組合。EIO／ESTALE 在 `_read_proc` 的同一 try 範圍注入，適合測錯誤傳遞；但不能當 EACCES 語意也有同樣保證的證據。

## tick 拒絕 open 與恢復

`manual-round`：先單獨 tick 開 r1，再 tick 退出 3，round 檔 bytes 不變。起 daemon 後能先收 r1，繼續 r2，沒有因明確 open 永久卡住。將 r2 的 round 半寫成 `{`，status 是 `phase:error`、`round_open:null`、`last_error.kind:round-unknown`，含 JSON 格式與人工寫回提示；寫回本案已保存的完整 round 後 resume，進 r3。

因此「open=true 就拒絕 tick」本身合理；需要人工的是證據壞掉或持續 I/O／持鎖失敗，不是每次 tick 拒絕都需人工。`last_error` 恢復後仍保留，是「最近錯誤」欄位的現有語意；使用者要合看目前 phase、round 與錯誤時間，不能只看到 last_error 就以為仍故障。

文件不足在如何選 N、如何確認「上一回合收完」、何時能安全標 `open:false`。README 無復原步驟；spec §2.2/§3 只有原則。可靠操作應先保留證據、停止會改檔的動作，檢查同回合 last-round 是否完整、是否仍有未收槽／未報結果，再還原可信完整 round；若只是原回合未關，應用 tock 收尾。不得盲寫 false 跳過尚未提交的回合，也不得把 N 猜成 0。證據全失時本來就無法保證不漏不重，須由操作者明確接受復原損失。

## 人工／外部修復停點全表

「停」分為整條時間線停開新回合、单槽不准重用、单項控制或任務准入暫停；UNKNOWN 不必然令整 node 停下。以下覆蓋 source 的讀取、身分、控制與准入分支；暫時 I/O 恢復後多會自動重試，只有原因永久存在才須人處理。

特別排除正常交接：birth 已寫而 runner／pid 尚未完成交接時的 `LIVE＋unsure=剛起`，以及 after-popen 能辨識 runner 仍活時的 unsure，都是等既有執行者完成交接。它們可能短暫出現在 status.uncertain，並不是要求人介入的故障。沒有 runner/pid 的 birth 會等兩回合再進 lost 身分掃描；「uncertain 非空」本身不能作為人工停機告警。

| 情況 | 範圍、status／文件 | 合理性與恢復 |
|---|---|---|
| round 半寫、缺 round/open、型別錯、I/O | 全時間線 `error`、`round_open:null`，kind round-unknown；spec §2.2/3。實測。 | 合理。修權限／檔案或還原可信 round；不可直接猜 false。文件欠完整 runbook。 |
| round 不存在，last-round 也讀不到／不能用 | tick 3、error，stderr 請人寫回 round；`round_open` 可能 false，因「無 round」。 | 合理保住回合編號，但 status 必須合看 last_error，不能把 false 理解為已知正常已關。兩檔都不存在則當新空間，不停。 |
| round 明確 open，但 last-round I/O、列槽 I/O、總結寫入／讀回／收尾失敗 | 回合持續 open，recovery_pending、last_error，退避 0.5～8 秒；spec §2.2/7。 | 合理，不可先關回合；修權限、空間或 I/O 後重試 tock。單純 last-round JSON 損壞會重建，不必人工。 |
| gen.json 讀不到／格式壞 | daemon 發起的 tick/tock 3，error、訊息 gen.json 不能用；spec §2.5。 | 合理。修 I/O 或確認現役世代／重啟 daemon，禁止隨便猜 gen 讓舊動作復活。無專門復原章節。 |
| node/root EIO、EACCES、ESTALE，或開 fd/辨識位置讀不到 | node last_error errno kind；root 頂層 last_error；tick/tock 3。 | 合理，修存取後自動恢復，不能當成刪除。不是強制整個 daemon 停機。 |
| action.lock 有人持有，owner 缺／壞，pid/starttime 不符／讀不到，gen 未知或非舊 | `stale-holder-unverified`，有人類可讀的 fuser/lsof、核對舊程序再 kill 或修 owner 提示；spec §2.5。 | 合理，不能殺不明程序；目前人工提示最完整的一類。不可 unlink 鎖檔。 |
| birth/exit/pid I/O，或槽列表 I/O | 單槽 UNKNOWN、`uncertain`，last-round errors；列表全失會擋 tick/tock。 | 合理；修 I/O 後自動重試。unknown 槽 ctl 請求保留。 |
| birth 壞、掃不到活程序且沒有可辨識 run 的 exit/pid | 單槽不重用，status live `k#?`＋uncertain，含「確認沒在跑後刪 birth」；spec §5.4。實測其他回合繼續，刪 birth 後可再起。 | 合理避免一次性任務重做，但刪 birth 相當於授權重新起；文件應提醒已做外部副作用無法由此還原，不能只確認「現在沒在跑」。 |
| 保存的 starttime 缺失、活 pid 的 stat/starttime 暫不可讀 | LIVE＋unsure，阻止槽重用，uncertain（若另一 runner/task 可證實活，可能直接 LIVE）；spec §5.4。 | 暫時讀錯會恢復；若紀錄本來就是 null，單純恢復 /proc 讀取也不會補身分，需可信證據修正或等程序結束。提示目前統稱 /proc 讀不到，未區分歷史缺值。 |
| 疑似 lost 的身分掃描不完整、相符程序 SIGKILL 後還活、收尾 exit 重讀失敗 | 單槽 UNKNOWN，uncertain 與 errors，ctl 留著；spec §5.4/6。 | 合理；待 I/O/權限恢復或處理阻塞程序後重試。Linux D state／無權送訊號可长期卡住，不能保證自動恢復。 |
| ctl.json 讀不到或槽 UNKNOWN | 單份控制留著，不產生最終失敗回條；last-round ctl 有錯誤。 | 合理；修權限／槽證據後重試。status 无 pending_ctl 詳細欄位，需讀 ctl 與 last-round。 |
| daemon 控制處理丟例外，移到 ctl-failed；搬不走留在 ctl_stuck | 非整條停，該請求不再執行；status last_ctl_error，spec §2.3。 | 效果可能已完成，須核實再重送；文件解釋原因但沒有逐 op 復原指引。重開 daemon 才會重試留在 ctl 的檔，可能再施效，不能當通用復原法。 |
| tasks 表壞／I/O、tasks.json.lock 拿不到、項目不合法或 subroot 檢查被擋 | 回合可繼續、該項不起；last-round tasks_error/skipped；status 不直接列任務表錯誤。 | 大部分合理隔離。修表或持鎖原因；status 只能看 round 在跑不足以知道工作未跑。 |
| subroot stopped.json／既有子 daemon lock／當回合已被其他項認領 | 單項准入不啟動；tasks_error，spec §2.7。 | 停止標記要人刪或明確重開子 daemon；有現役 lock 是合理避免雙開。 |
| 人工 pause／rounds 歸零、node missing／變 symlink、unregistered、正常 stopped | paused_by/steps_left、missing 原因、stopped 等；spec §2.3/2.4/2.6/2.7。 | 是明確控制／實體變更，不是未知故障。resume 相應 owner、恢復真目錄或 register 新位置、重啟 daemon。 |

可用性評估：原先把未知誤當沒有的問題修正後，多數新增停點是必要的安全退讓，且單槽未知不拖停其他槽。剩餘可改善處是恢復 runbook、保存 starttime=null 的診斷、status 看不到 tasks_error／pending ctl、以及使用「最近錯誤」時需分清歷史與現況。沒有證據支持為可用性把證據不足一律改成可重跑。
