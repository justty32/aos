# 照 proto7-2 spec 實作時碰到的問題

← [proto7-2](../README.md)｜[spec](../spec.md)｜[跟 proto7-1 的差別](changes-from-7-1.md)

照 [spec.md](../spec.md) 做 daemon／tick／tock／run／ctl（10-04）時，spec 說不清、做不出來、或有更簡單的做法的地方。spec 裡對應的地方標了「P2-」。W1～W12 照推薦做，沒有在這裡重列。astra 第一輪回歸（[報告](play/2026-10-04-astra-1-infra.md)）的 A2-01～A2-13 與讀碼疑點的處理在最後一節，spec 對應處標「A2-」。

分級：**〔要使用者決定〕**＝語意題，先照最簡推薦做；〔技術選型，先這樣〕；〔默認正常〕。

## 要使用者決定（2 條）

### P2-01 固定 interval 時 `wake` 沒有作用

- `early_tock: false`（預設）時，時間線在第 4 步就等滿 interval 才 tock，第 6 步「等到滿 interval」幾乎是 0。所以固定 interval 的 node **整段都在回合中**，照 2.3「回合中照舊」，`wake` 不起作用；`resume` 順便 wake 也只在 node 停在 pause 時有用（那時本來就不在回合中，照樣馬上開）。
- 現在：照 spec 字面做，測試的 wake 用 `early_tock: true`。
- 其他選項：（b）固定 interval 時 `wake` 打斷第 4 步，馬上 tock、馬上開下一回合（等於「這回合提前結束」）；（c）`wake` 只縮短下一回合（下一回合的 interval 從 wake 那一刻重算）。

### P2-02 once 被殺在「寫了 birth、runner 還沒記到」之間：報成 lost，一次都沒跑

- 4.4 的 launch 標記保證不重起。但 tick 被 kill -9 在 birth.json 寫完、Popen 之前或剛 Popen 之後（runner 還沒補進 birth.json）時，下一個 tick 分不出 runner 起了沒，只能照 5.4 等兩回合、身分掃描找不到就判 lost。
- 結果：這項**沒跑過，但 last-round.json 會報 `{"run": "o#1", "code": null, "lost": true}`**，不會無痕消失，但也不會再跑。測試 `test_crash_after_birth` 鎖住這個行為。
- 這是「最多一次」（at-most-once）。要「至少一次」可以：判 lost 時若 birth.json 沒有 runner、也沒有 pid.json、out.log 是空的，就把 once 項加回 tasks.json 重起（有極小機率真的跑了兩次）。要不要改由你定。

## 技術選型，先這樣

### P2-03 上一個 run 在 tock 之後才結束、下一個 tick 就重用槽：結束會漏報 → tick 先記進 round.json

- spec 5.1／5.3：重用槽時清掉上一個 run 的基礎設施檔。但 keep／each 的任務在 tock 之後才結束時，下一個 tick 看到「已結束」就重用槽，exit.json 被清掉，這次結束永遠不會出現在任何 last-round.json。
- 做法：tick 在清槽之前，把「已結束、exit.json 還沒有 seen_round」的 run 寫進 round.json 的 `reaped`，tock 併進 `ended`（依 run id 去重）。tick 在寫 round.json 之後才清槽，被殺時 tock 照樣讀得到。
- 同理，tick 要在疑似 lost 的槽起新 run 時，自己先做身分掃描、寫 lost 的 exit.json（spec 原本只說 tock 寫），再走上面這條報出去。spec 5.4 改了一句。

### P2-04 `ctl.json`／`ctl-done.json` 不在換 run 時清

- spec 5.1 的表把它們列成基礎設施檔。但 restart 的流程是：tock 執行 ctl、寫 ctl-done.json → 下一個 tick 在同一個槽起新 run。如果換 run 時清掉 ctl-done.json，restart 的回條活不到請求者讀它。
- 做法：兩個都不清（各只有一份，下一次控制就蓋掉，不會長）。回條的 `result.run` 記它作用在哪個 run，tock 的 `by_ctl` 也比這個 run，不會把上一次的回條算到這次。ctl.json 若在 tick 執行完控制之後才寫進來，照樣留給新 run（不寫 `run` 的人本來就是指「現在這次」）。

### P2-05 node 的 `.aos/` 不在時 tick 自己建

- 登記不要求 timeline.json（W12），所以 node 資料夾可能連 `.aos/` 都沒有。tick 抓住 node fd 後經 fd 建 `.aos/`（node 被刪就建不出來 → gone，不建鬼目錄）。

### P2-06 round.json 不存在時

- spec 第 3 節只寫了讀不到與內容壞掉。不存在：tick 用 last-round.json 的 round 接著數（也沒有就從 1），tock 印 `skipped`（沒有回合可關）。A2-02 後：last-round.json 讀不到或壞掉時是「不知道」（退出碼 3），不從 1 重數。

### P2-07 restart 先加 once 項、再 kill

- spec 原寫「kill，然後在 tasks.json 加 once」。kill 完、加項之前被殺會「殺了沒重起」。改成先拿鎖加項（1 秒拿不到鎖就整個 ctl 不執行、不 kill），再 kill；中途被殺時 once 項等槽空了才起（busy 會記進 skipped）。

### P2-08 「starttime 讀不到」記成「活，但 unsure」

- 5.4 的「不知道 → 當活」在程式裡是 `state: live` 加 `unsure` 欄（說明原因），不另開一個狀態：tock 照樣對它寫 tock.json、列進 `alive`，tick 不起、不判 lost。真正的「不知道」（birth.json／exit.json／pid.json 讀不到）是 `unknown`：不起、不判 lost、不刪槽、不寫 tock.json，記進 `errors`。
- daemon 的 status `live` 把 `unknown` 也列進去（保守）。

### P2-09 推定不了時 tick／tock 退出碼 3

- round.json 讀不到、兩份回合數都不能用、`.aos/tasks/` 列不出來、last-round.json 讀不到（tock）：什麼都不寫，stdout 印 `{"unknown": "..."}`、退出碼 3。daemon 把 3 當「不知道」走 2.1 第 1 步的退避。A2 後多了：round.json 內容不完整（A2-02）、tick 時上一回合還開著、gen.json 不能用、看不到 node（開 node 不是 ENOENT 的錯誤）、重播時列不出槽。
- tasks.json.lock 一秒拿不到、或列不出槽時，這回合照常開（回合數往前），只是不從 tasks.json 起任何東西，記 `tasks_error`。

### P2-10 unregister 立刻從 nodes.json 拿掉

- spec：「本回合照常 tock 收完，然後時間線結束、從 nodes.json 拿掉」。做法是處理控制檔時就從 nodes.json 拿掉、時間線標 retire（不等 interval，帶 kill 時先收活任務，tock 收回合後結束），收完後 daemon 再掃一次環境變數相符的殘留。差別只在 daemon 在這中間死掉時：重開不會再跑它（回合可能留著 open，下次登記時照 2.2 先收）。

### P2-11 壞控制檔的原物名

- 不是 `.json` 結尾、不是一般檔的：原物搬成 `ctl-done/<原檔名>.bad`，回條是 `ctl-done/<原檔名>.json`（原檔名已是 `.json` 就同名）。同名的舊的都蓋掉（資料夾也蓋）。

### P2-12 status 多一個 phase `unregistering`

- unregister 之後到時間線收完回合前，status 還列著這個 node，phase 是 `unregistering`；不然看 status 的人以為已經收完。

### P2-13 回條路徑被佔成資料夾時直接蓋掉

- proto7-1 的「回條寫不進去」毒丸（`ctl-done/<名>.json` 被建成資料夾）在「同名蓋掉」下不再是毒丸：先刪掉再寫。ctl-failed 只剩其他寫不進去的情形（例如整個 `ctl-done` 被換成一般檔），測試用這個情形驗證「一件出事不擋同圈的 stop」。

### P2-14 收程序時不打自己與祖先所在的程序群組

- kill 範圍照 Q1；另外排除 tick／tock／daemon 自己與祖先所在的群組（子 daemon 本身是父 node 的任務，它的 tick 跟它同群組）。

## 默認正常

- **P2-15 測試鉤子留在程式裡（只給測試用）**：環境變數 `AOS7_TEST_CRASH=<點>`（在那個點自己 SIGKILL；tick：`before-launch`、`after-launch`、`after-birth`、`after-popen`、`after-runner`、`before-once-delete`、`after-once-delete`；任務控制：`restart-after-append`、`restart-after-kill`、`ctl-after-done`；tock：`tock-summary`、`tock-after-finish`；原子寫：`tmp:<檔名>`）、`AOS7_TEST_HANG=<點>`（`tick-opened`、`tock-summary` 卡住）、`AOS7_TEST_RUNNER_CRASH=<點>`（aos7-run 的 `runner-before-pid`、`runner-before-exit`；aos7-run 一開始就從環境拿掉）、`AOS7_TEST_FAULT=<op:glob:ERRNO;…>` 或 `@<規則檔>`（在 /proc 讀取、三態讀檔、列槽、daemon 看 node、tick 開 node 注入 errno；規則檔每次重讀，給跑著的 daemon 中途開關）。用來做 A2 回歸矩陣（`tests/test_matrix*.py`）。tick 起任務時把 CRASH／HANG／FAULT 從任務環境拿掉；正常環境沒有這些變數，程式只多一次環境查詢。
- **P2-16 kernel／agent 沒做**：照這次的範圍只做基礎設施。第 8 節（kernel 用量累計）沒有程式；第 9 節的歷史 module 有參考實作（`modules/history.py`），另有最小示範任務 `modules/counter.py`（讀同槽上一次的 state、收 tock.json）。
- **P2-17 寫入紀錄（`AOS7_AUDIT`）照搬沒測**：`lib/audit_site/`、`aos7_audit.py` 原樣複製自 proto7-1，`writes.jsonl` 換 run 時清（5.1）。這次沒有對它寫測試。
- **P2-18 max_live 要是正整數**：0 不合（整項跳過）；要停用用 `enabled: false`。

## astra 第一輪（A2）的處理

依 [astra 第一輪報告](play/2026-10-04-astra-1-infra.md) 與 astra 加註解時讀出的 14 處疑點（commit b749d5eb）。三件核心工作（未知一路保留、回合與槽的身分證據、控制意圖重播只生效一次）做成固定回歸矩陣：`tests/test_matrix*.py`（維度與判定見各檔檔頭）。P2-01、P2-02 仍待使用者決定，語意沒動。

| 編號 | 處理 | 做法（spec 對應處標 A2-） |
|---|---|---|
| A2-01 /proc 讀不到當沒有 | 已修 | `aos7_proc` 的 /proc 讀取只剩一個入口：讀到／程序已不在／讀不到（丟 `ProcUnknown`）。`pid_state` 三態、掃描不完整整個丟出；judge 當活＋unsure、resolve 判 UNKNOWN 不寫 lost、kill_identity 回「不知道收乾淨沒」；疑似 lost 時這個 run 的 aos7-run 還活著（tick 被殺在 after-popen、回合跑得比 runner 起來快）也當活，不判 lost（矩陣抓到的雙開）。environ 是 EACCES 的程序（別的 uid、同 uid 但不可 ptrace，例如 systemd --user）當成不是任務，否則每次掃描都不完整（spec §11） |
| A2-02 round.json 半寫／缺 open 當已關 | 已修 | `aos7_fs.read_round` 一個判定給 daemon、tick、tock：只有明確 `open: false` 是已關；壞掉＝不知道（daemon 退避、tick／tock 退出碼 3）。tick 不再用 last-round.json 接壞掉的 round.json，也拒絕在 `open: true` 時開下一回合；tock 不再替壞掉的 round 補號 |
| A2-03 birth 半寫使 once 重跑 | 已修 | birth 壞掉＋掃不到活程序時看同槽 exit.json／pid.json 的 run（換 run 時先清舊的才寫新 birth，所以一定是這個 run 的）：exit → 結束（run R，once 的 launch 對得上就刪項）；只有 pid → 疑似 lost；都沒有 → UNKNOWN（不起，等人刪 birth.json）。§0 與 §5.4 不再衝突 |
| A2-04 node 換符號連結 | 已修 | 登記要求路徑沒有符號連結（realpath＝`realpath(root)/<id>`）；daemon 每圈用 lstat＋realpath 比對，變成連結或路徑經過連結＝missing；tick／tock 開 node 用 O_NOFOLLOW，開到後再比 realpath，不合印 gone——不會沿連結寫出 root。沒有另存 dev+inode 到 nodes.json：Q4「刪掉又出現就重開」要保留，inode 仍照時間線開始時記的比 |
| A2-05 restart 重播兩次 | 已修 | restart 的 once 項與新 run 的 birth 帶 `ctl_id`（請求的 `id`，或原始內容＋mtime 的雜湊）；append 前查表、執行前查現在的 birth，同 id 就不再加、不再 kill，只補回條 |
| A2-06 rounds 倒數每 node 一份 | 已修 | `steps` 改成 `{node: {owner: left}}`，每關一回合各扣一，誰到零誰再 pause；status `steps_left` 是 `{owner: 剩幾回合}` |
| A2-07 SIGKILL 留下的暫存檔 | 已修 | `aos7_fs.sweep_tmp`：寫者 pid 確定不在才刪 `.<名>.tmp.<pid>`。tick 清 `.aos/`，tock 清 `.aos/` 與每個槽，daemon 每秒清 `.aosd/`、`ctl/`、`ctl-done/` |
| A2-08 保守判定的原因看不到、截尾丟類型 | 已修 | `last_error` 多 `kind` 欄（錯誤類型），`err` 太長時保留頭尾；tock 對 unsure／birth 壞掉的活任務在總結 `errors` 記 `phase: "unsure"`；status 每 node 多 `uncertain` 列判不出的槽 |
| A2-09 §8 憑 usage 下降辨認重建 | 改 spec（kernel 未實作） | §8 改成用量以 run 為單位：usage.json 只記這次 run，kernel 對每個 `<slot>#<run>` 記已見最大值、跨 run 相加，不靠「變小」猜重建；明寫總數是已觀測用量的下界 |
| A2-10 history max-lines 沒套事件歷史 | 已修 | `--max-lines` 也截 `daemon-events.jsonl` |
| A2-11 early 回合中的 wake 被保留 | 已修 | kick 記時刻，第 6 步只認回合關上之後的 wake／resume |
| A2-12 history 通知早於總結提交 | 已修 | tock 先提交 last-round.json（整份讀回確認）才寫 tock.json；中途被殺時重播照總結的 alive 補寫。§9 另補「最後一回合、起來之前的回合記不到」的限制 |
| A2-13 CLI 固定檔名沒含 owner | 已修 | `aos7-ctl` 帶 `--owner` 時檔名 `<by>.<op>.<node>@<owner>.json` |

讀碼疑點（b749d5eb 的 14 處）：

| 位置（加註解時的行號） | 處理 |
|---|---|
| aos7_proc.py:35、65、162、202（/proc 讀失敗當死或略過；掃不到成員還准許 pgid） | 已修，同 A2-01（`group_is_task` 掃描不完整丟出，不准許） |
| aos7_task.py:183（最後重讀 exit 遇 I/O 錯仍寫 lost） | 已修：讀不到＝UNKNOWN |
| aos7_fs.py:200、207（比 gen 前先寫 owner；gen 檔不是物件也放行） | 已修：先比世代、現役才寫 owner；gen.json 不能用＝不知道（退出碼 3） |
| aos7_tick.py:258（開 node 的任何 OSError 當 gone） | 已修：只有 ENOENT／ENOTDIR／符號連結是 gone，其他退出碼 3 |
| aos7_tock.py:185、130、77（重播忽略列槽錯誤；總結檢查不完整） | 已修：重播列不出槽不關回合；讀回整份比對；只拿完整的同回合總結重播（`summary_ok`） |
| aos7_run.py:165（讀 round 阻塞開檔） | 已修：非阻塞開、只讀一般檔 |
| aos7_daemon_timeline.py:181、311（open 值不合法當已關；缺 run 的 birth 准許提前 tock） | 已修：同 A2-02；birth 的 run 要是另一個整數才算換人 |
| aos7_daemon_timeline.py:76、83（interval 365 天上限、截小數） | 已修：照 spec 只要求有限非負，不截小數 |
| aos7_daemon.py:522（列槽失敗清空 live／pgid） | 已修：沿用上次的，status `uncertain` 記原因 |
| aos7_daemon.py:106（寫 paused 沒拿 flock） | 已修：照 §0 拿 `paused.json.lock`（daemon 仍是唯一寫者） |
| aos7_daemon.py:595（root 讀取錯誤沒記） | 已修：status 頂層 `last_error` |
| aos7_daemon.py:346、416（控制檔失敗又搬不走會再執行） | 已修：卡住的不再執行，只每圈再試著搬到 ctl-failed（daemon 重開後才會再當新請求，已接受） |
| sitecustomize.py:63（靠 timeline.json 認巢狀 node） | 已修：改讀 nodes.json（P2-17 仍沒有專門測試） |
| aos7_mount.py:202（列掛載請求沒排除 `.` 開頭） | 已修 |
