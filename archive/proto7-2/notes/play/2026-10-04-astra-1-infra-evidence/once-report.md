# once／三態／不變條件子報告

本子測試以真實子程序、副作用紀錄與 PID 核對執行 20 個隔離案例。所有暫存位於本證據目錄；程序逐 PID SIGKILL／waitpid，結束後資料夾刪除。`once-cleanup.json`：20 案 survivor 均空、`remaining_test_pids=[]`、`temp_root_exists=false`。沒有改程式碼。

重現命令（副本根目錄）：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-1-infra-evidence/once-probes.py
```

證據 `once-results.json` 的頂層 key 是案例群。`once_boundaries` 由獨立 tick Python 程序在實際 write／edit 邊界以 `os.kill(os.getpid(), SIGKILL)` 中斷（8 案退出碼全 -9），不是把函式回傳改成成功／失敗。`three_state` 的 EIO 透過 runtime monkeypatch 注入實際檔案 open／listdir 層；任務與 runner 是真正 sleep 程序。`timeline` 執行真正 `Timeline._loop`，控制器採最小測試 stub，prog 呼叫實際 tick／tock 函式；這部分屬狀態機整合測試，**不是完整 daemon 程序測試**。

## 承諾判定

| 承諾 | 判定 | 實測／JSON 定位 |
|---|---|---|
| once launch 前／後 SIGKILL 不重起、不遺失 | 成立 | `once_boundaries[before-launch,after-launch]`：各執行一次，run2，最終項目刪除、ended code0。 |
| once birth 前／後 SIGKILL | 部分，符合已揭露 P2-02 | before-birth 一次；after-birth 零次，兩回合後 `o#1 lost:true`，沒有無痕消失。這是 at-most-once，不能稱至少一次。 |
| once runner 記錄前／後 SIGKILL | 成立，限這次排程 | before-runner、after-runner 都一次，ended code0；before-runner 是已 Popen、補 birth.runner 前的真窗口。 |
| once 刪項目前／後 SIGKILL | 成立 | before-delete、after-delete 都一次，無殘留項目。 |
| starttime helper 回 None | 部分 | `three_state.starttime_none`：judge live＋unsure、tick started=[]、原 PID 活、恢复後 view 正常；但公開 last-round.errors=[]、skipped=[]、alive=[o#1]，未呈現 unsure 原因。 |
| birth.json EIO | 成立 | `three_state.birth.json_eio`：原 PID 活、run1 不改、tick 不起、tock errors 有 EIO；恢復後繼續。 |
| birth 壞／半寫但 /proc 正常 | 部分 | `birth_bad_{`、`birth_bad_[]`：活任務被辨成 `o#?`，不雙開；還原 birth 後 `birth_restored` 回 run1。可是無活程序時直接 EMPTY，once 既有成功會重複起，見新問題 B。 |
| round.json EIO | 成立 | `round.json_eio`：tick／tock 都 Unknown，原任務不改；`timeline.round_eio`：回合2停留 open、round_open=null、只 backoff、不 tick，恢復先 tock2。 |
| last-round.json EIO／壞 | 部分 | EIO tock 拒絕關回合；恢復後原回合完成。只有 last-round 壞、round 健康時，下一次 tock 會覆寫回正常但無警告；兩者皆壞則 Unknown，要求人工補 round，不能自動回正。 |
| /proc 看不到不破壞 | 不成立 | `proc_stat_eio`：健康任務被 SIGTERM 並重起；`proc_all_eio`：lost 後兩份 sleep 同活。恢復讀取後舊 run 仍活。 |
| 不變條件一：確知關閉才下一回合 | 部分 | 正常 open/EIO 恢復與 pause 倒數成立；半寫 round、缺 open 被當 False，直接 tick；缺 open 的 last-round 從1跳3。 |
| 不變條件二：lost 前身分掃描／keep 不雙開 | 部分 | `identity.runner_before_pid`：runner 生出 sleep 後、pid.json 前自殺，舊 sleep PID 真活；tock 找出並收掉它、報 lost，再 tick 才起新 run。/proc EIO 仍雙開。 |
| 舊 run 殘留不当新 run | 成立，限身分與讀檔篩選 | `identity.old_run_residue`：birth run100、pid/exit run1，judge suspect100，NODE/TID/RUN100 找不到舊程序；RUN1 能找到。這是受控 metadata 測試。 |

## K-01～K-05 對照

| 舊題 | 結論 | 證據與範圍 |
|---|---|---|
| K-01 round 讀不到卻跳回合 | **換了形式** | EIO 原案已修；BAD/缺 open 仍當關閉，`timeline.round_open_missing` 直接3、跳過2總結。 |
| K-02 恢復後漏 pause／倒數多跑 | **已修** | `timeline.recovery_pause_count`：注入第一次 tock 失敗，calls=[tock,backoff,tock]，done 只1次、paused=true、無 tick；實作 line202 continue 回迴圈頂部。完整 daemon 行為由主報告其他子測試交叉驗證。 |
| K-03 tick＋runner 死可永久 born | **已修，改成有界 lost** | after-birth 無 runner 的相同持久化狀態，兩回合後 lost；once 零次屬明揭 P2-02 取捨。不是舊式永遠 alive。 |
| K-04 runner 死於 pid 前 keep 雙開 | **換了形式** | 原出生窗口已修，`identity.runner_before_pid` 舊 PID 先收掉再新起；觀測失敗仍經空清單推定乾淨，/proc EIO 可重現雙開。 |
| K-05 starttime 讀不到當 PID 重用 | **換了形式** | helper None 原案修為 live＋unsure；更低層 `/proc/pid/stat` EIO 被 pid_alive 當 dead，誤殺健康任務；與 all_pids EIO 合併則雙開。 |

## 新問題（編號交主報告統一）

### A〔bug，高〕三態沒有傳到底層 /proc：EIO 可誤殺健康任務或 keep 雙開

`aos7_proc.py:17 pid_alive` 將 stat OSError 回 False；`:52 all_pids` 讀不到回空；`:59 stat_of` 回 None；`:122 env_procs` 不傳「掃描不完整」。這使 `aos7_task.resolve` 把未知誤當確定無程序。單獨 stat EIO 仍能讀 environ，最後按舊 pgid SIGTERM 真正健康的 run1，然後起 run2（`proc_stat_eio`，old_alive=false，reaped code -15）。stat＋/proc listdir EIO 時 run1 被報 lost，run2 已起，兩 PID 同活（`proc_all_eio`）；解除注入後再 tick/tock 舊 PID 仍活，不會自動修復。半寫 birth＋environ EIO 則直接 EMPTY，完全不進 lost 身分收尾，也雙開（`birth_bad_proc_environ_eio`）。

這不是巧合 timing：每案注入期間兩個實際程序存活與結束均以原始 `/proc/PID/stat` 查驗。應讓掃描回「完整且無匹配／找到／未知」，未知沿途禁止 kill、lost、clear_slot、重起；pid_alive 應保留 OSError 種類。

### B〔bug，高〕birth 半寫使 launch 失去否重複依據，once 可跑兩次並漏第一次 ended

`once_corrupt_birth`：tick 真 SIGKILL 在刪 once 前；已執行副作用 `[1]`，launch 指 run1，exit.json 有 run1/code0；等待 runner 完全退出後把 birth 寫成 `{`。tock 的 summary ended=[]、errors=[]；下一個 tick 把 bad birth 當 EMPTY，改 launch 並起 run2，最終副作用 `[1,2]`、只報 run2。

這是「SIGKILL＋birth 損壞」複合故障，不能說單純 SIGKILL 的 8 點保證失敗；但使用者要求的半寫矩陣不成立，且 spec §0 把半寫列未知，§5.4 又允許空槽，設計自相矛盾。若要維持 at-most-once，已有 launch 而 birth 無法確知時應保留待恢復，不能只凭活程序數為0認定沒執行。

### C〔bug，高〕round.json 缺 open／半寫仍當已關，未關回合可被覆蓋

`timeline.round_open_missing`：先完成r1並開r2，保留r2其餘內容但移除open；`Timeline.check_round` 回False，calls=[tick,tock]，last-round 從1直接成3且last_error=null。`timeline.round_bad`：把r2寫成半寫 `{`，直接再次 tick，以last-round1接成r2，覆蓋原r2 tick狀態。這違反「確知關閉才開下一回合」；只能由 open:false（及有明確全新狀態規則的真正不存在）確認關閉。壞內容必須走未知或明確恢復，而不能當 false。`tick` 自己也不檢查 open（`direct_tick_open`），但這個直接 API 限制需跟 daemon 不變條件分開，不把 API 連 tick 算主要缺陷。

### D〔bug，低〕starttime 的保守原因只留在內部 View，公開總結失去診斷

`three_state.starttime_none.view.unsure` 有中文原因，但同案 tick.skipped=[]、summary.errors=[]／alive=[o#1]。birth 半寫但程序仍活只顯示 o#?，也没有errors。spec §0 的「記原因／可看懂」落實不完整。這可併 A 的可觀測性，不必獨立高優先級。

總評：launch＋槽＋run 已有效縮短正常 crash 恢復狀態，K03／K04 的原始出生交接不再卡死或雙開；但真正欠缺仍是**觀測完整性**，read_json3 的三態沒有涵蓋 /proc 掃描與 schema 判定，而且「壞 birth＝空槽」從設計上把已執行與未執行混成一種狀態。這些是縮小後仍存在的結構性缺口，尚不是只剩邊角。
