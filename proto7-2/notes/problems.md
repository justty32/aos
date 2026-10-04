# 照 proto7-2 spec 實作時碰到的問題

← [proto7-2](../README.md)｜[spec](../spec.md)｜[跟 proto7-1 的差別](changes-from-7-1.md)

照 [spec.md](../spec.md) 做 daemon／tick／tock／run／ctl（10-04）時，spec 說不清、做不出來、或有更簡單的做法的地方。spec 裡對應的地方標了「P2-」。W1～W12 照推薦做，沒有在這裡重列。astra 第一輪回歸（[報告](play/2026-10-04-astra-1-infra.md)）的 A2-01～A2-13 與讀碼疑點的處理在倒數第二節，spec 對應處標「A2-」；astra 第二輪（[報告](play/2026-10-04-astra-2-infra.md)）的 A3-01～A3-09 在最後一節，spec 對應處標「A3-」。

分級：**〔要使用者決定〕**＝語意題，先照最簡推薦做；〔技術選型，先這樣〕；〔默認正常〕。

## 要使用者決定（0 條）

原有的 P2-01、P2-02 兩條：10-04 使用者說「隨意，真的糾結就做選項」，頂層定案，astra-2 修補（commit 79e67233）已實作，語意如下。

### P2-01 固定 interval 時 `wake` 沒有作用 → 已定 (b)、已實作

- 原狀：`early_tock: false`（預設）時，時間線在第 4 步就等滿 interval 才 tock，第 6 步幾乎是 0，整段都在回合中，照「回合中照舊」`wake` 不起作用。
- **頂層定（10-04）：選 (b)，不做選項。** wake 是明確的請求，固定節拍是「沒人叫時」的預設；kernel 有信要叫醒閒置 node（第三波 tickless）靠它。沒選的：(c) `wake` 只縮短下一回合。
- **做法**：tick 開始之後收到 wake（或讓 node 從有人 pause 變成沒人 pause 的 resume）→ 提前結束這回合：馬上 tock（`AOS7_EARLY=1`）、跳過第 6 步、馬上開下一回合，記事件 `woke`。`early_tock: true` 照舊（回合中 wake 不起作用，A2-11）。resume 只在 node 因此變成沒人 pause 時才順便 wake（本來就沒人 pause 的 resume 不切掉正在跑的回合）。spec 2.1 第 4、6 步、2.3。

### P2-02 once 被殺在「寫了 birth、runner 還沒記到」之間：報成 lost，一次都沒跑 → 已做成選項 `retry_lost`

- 原狀：tick 被 kill -9 在 birth.json 寫完、runner 還沒補進去時，下一個 tick 分不出 runner 起了沒，等兩回合身分掃描找不到就判 lost，last-round.json 報 `{"run": "o#1", "code": null, "lost": true}`，不再跑（最多一次）。測試 `test_crash_after_birth` 鎖住這個預設行為。
- **頂層定（10-04）：做成選項。** 兩邊各有道理（付費工作怕重複 vs. 怕漏跑），照使用者「糾結就做選項」。
- **做法**：once 項可選 `retry_lost`（bool，預設 false＝最多一次，現狀）。true 時判 lost 若 birth 沒 runner、沒 pid.json、out.log 不存在或空 → 先把 once 項照 birth 定義加回 tasks.json（`slot` 釘同槽、`retry_lost: true`、`retry_of`＝原 run id；同槽同 `retry_of` 不重加；表鎖一秒拿不到就先不判 lost，下次再看），再寫 lost exit（帶 `retried: true`，`ended` 也帶）；可能跑兩次。out.log 讀不到大小＝不加回。spec 4.1、4.4。

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

- **P2-15 測試鉤子留在程式裡（只給測試用）**：環境變數 `AOS7_TEST_CRASH=<點>`（在那個點自己 SIGKILL；tick：`before-launch`、`after-launch`、`after-birth`、`after-popen`、`after-runner`、`before-once-delete`、`after-once-delete`；任務控制：`restart-after-append`、`restart-after-kill`、`ctl-after-done`；tock：`tock-summary`、`tock-after-finish`；任務控制另有 `ctl-after-seen`（記完 ctl-seen.json、寫回條之前，A3-01）；原子寫：`tmp:<檔名>`）、`AOS7_TEST_HANG=<點>`（`tick-opened`、`tock-summary` 卡住）、`AOS7_TEST_RUNNER_CRASH=<點>`（aos7-run 的 `runner-before-pid`、`runner-before-exit`；aos7-run 一開始就從環境拿掉）、`AOS7_TEST_FAULT=<op:glob:ERRNO;…>` 或 `@<規則檔>`（在 /proc 讀取、三態讀檔、列槽、daemon 看 node、tick 開 node 注入 errno；規則檔每次重讀，給跑著的 daemon 中途開關）、`AOS7_TEST_FAULT_HITS=<檔>`（注入真的命中時追加一行 `op<TAB>errno<TAB>路徑`，子程序命中也記得到；矩陣用來斷言故障確實打中，A3）。用來做 A2 回歸矩陣（`tests/test_matrix*.py`）。tick 起任務時把 CRASH／HANG／FAULT／FAULT_HITS 從任務環境拿掉；正常環境沒有這些變數，程式只多一次環境查詢。
- **P2-16 kernel／agent 沒做**：照這次的範圍只做基礎設施。第 8 節（kernel 用量累計）沒有程式；第 9 節的歷史 module 有參考實作（`modules/history.py`），另有最小示範任務 `modules/counter.py`（讀同槽上一次的 state、收 tock.json）。
- **P2-17 寫入紀錄（`AOS7_AUDIT`）照搬沒測**：`lib/audit_site/`、`aos7_audit.py` 原樣複製自 proto7-1，`writes.jsonl` 換 run 時清（5.1）。這次沒有對它寫測試。
- **P2-18 max_live 要是正整數**：0 不合（整項跳過）；要停用用 `enabled: false`。

## astra 第一輪（A2）的處理

依 [astra 第一輪報告](play/2026-10-04-astra-1-infra.md) 與 astra 加註解時讀出的 14 處疑點（commit b749d5eb）。三件核心工作（未知一路保留、回合與槽的身分證據、控制意圖重播只生效一次）做成固定回歸矩陣：`tests/test_matrix*.py`（維度與判定見各檔檔頭）。P2-01、P2-02 當時仍待使用者決定，語意沒動（後來的處理見上面 P2-01、P2-02）。

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

## astra 第二輪（A3）的處理

依 [astra 第二輪報告](play/2026-10-04-astra-2-infra.md)。修補在 commit 537ef674（A3-02、03、09、命中紀錄）與 79e67233（其餘、P2-01、P2-02、until_round）。報告第四節的人工停點表改寫成 spec 第 12 節（給操作者的停止範圍、證據、恢復步驟），並補上報告指出的缺口（N 從哪裡核實、刪 birth＝重新授權執行、uncertain 非空不等於要人工、恢復前先保存證據並 pause）。

| 編號 | 處理 | 做法（spec 對應處標 A3-） |
|---|---|---|
| A3-01 restart 完成證據隨 keep 換 run 消失 | 已修 | node 層 `.aos/ctl-seen.json` 每槽記最近一件已處理的任務控制（不隨換 run 清，tock 刪槽時拿掉）；順序是先記 seen、再寫 ctl-done、再刪 ctl.json。同 ctl_id 再出現不執行，回條沒寫成就照 seen 補寫（`replayed`）；ctl.json 刪不掉在總結 ctl 帶 `err`；seen 讀不到／壞掉＝請求留著。birth 與 pending once 的查重保留，蓋「執行完、記 seen 之前被殺」。spec §6 |
| A3-02 environ EACCES 使不可 ptrace 任務雙開 | **誤用，不處理（原則 9）**；spec 框範圍 | 任務自己變得不可讀（關 dumpable、換 uid）＝故意脫離身分，是誤用，不歸核心管；spec §11 寫明管理範圍即是處理。本輪在原則 9 定下前已寫的保護先留著（之後核心精簡統一處理），不再擴張：environ EACCES 的程序在這個 run 的 runner session 或 pid.json 群組裡（殭屍除外）＝不知道，不判 lost；其他照舊當不是任務。cmdline 讀不到（含 EACCES）＝不知道。pid.json 多 `uid`。spec §11 明寫管理範圍（同 uid、environ 可讀；setuid／換 uid／關 dumpable 不在範圍），§5.4「不會雙開」加上只對管理範圍內成立 |
| A3-03 非一般檔當不存在，繞過 round／birth 保護 | **誤用，不處理（原則 9）** | 把生命週期檔換成 FIFO／資料夾是錯誤操作，不歸核心管。原則 9 定下前已寫的保護先留著（之後核心精簡統一處理），不再擴張：三態讀檔加嚴格模式給生命週期檔（round、last-round、birth、pid、exit，及 ctl-seen）：存在但不是一般檔＝不知道；其他檔照舊當不存在。tock 刪槽前讀 tasks.json 也用嚴格讀。spec §0 |
| A3-04 明確 id 靜默截 64 字 | 已修 | id 完整使用、不截斷；超過 200 字拒絕（回條 ok:false 說明）。spec §6 |
| A3-05 內容＋mtime 不是唯一意圖、作用域未定 | 已修＋改 spec | 沒帶 id 時雜湊加上 `<node-id>/<槽>`、st_dev、st_ino；id 作用域定為同 node 同槽，pending once 查重比同槽＋同 ctl_id。`aos7-ctl task` 自動產生 uuid，`--id` 重送沿用。spec §6、§10 |
| A3-06 owner 檔名有損編碼互蓋 | 已修（不是誤用：非 ASCII owner 如「甲」「乙」是正常用法） | by／node／owner 每段無損編碼（`/`→`+`，其他 `%XX`；太長取前 40＋`~`＋sha1 前 16）。spec 2.3、§10 |
| A3-07 mount 子目錄的暫存檔漏清 | 已修 | tock 清槽暫存檔時連 `mount-req/`、`mount-done/` 一起，不遞迴清任務自己的資料夾。spec §0 |
| A3-08 重播通知失敗被吞 | 已修 | 重播補 tock.json 失敗、alive 的槽判不出／判定例外都記進 round.json `notify_errors`（每筆帶 slot、run、round）與回傳；下一個 tick 開回合前補（同 run 還活著才補，補不上進 `tasks_error`），對已關回合再跑 tock 也補（`notify_retried`）。spec §7 |
| A3-09 任務仍活、群組核對不了，kill 卻回成功 | 已修 | kill 最後確認 pid.json 記的任務程序（pid＋starttime）已不在，否則 `ok: false`（unknown）；群組有成員 environ 讀不到權限又沒成員核對得到＝不知道。spec §6 |
| 讀碼：`kill_node` 掃描不完整時沒打記著的群組 | 已修 | 照 spec 2.6 照樣打記著的群組，事件 ok:false；environ 讀不到權限又在記著群組裡＝不完整 |
| 矩陣盲點（healthy 12 案有 9 案注入命中 0 次） | 已修 | 測試鉤子加 `AOS7_TEST_FAULT_HITS` 命中紀錄（P2-15），每個注入案例斷言命中 ≥1。補了 EACCES 孤兒、restart 完成證據跨 run、FIFO 生命週期檔、id 碰撞等組合——見 [tests/test_matrix_a3.py](../tests/test_matrix_a3.py) |

- **until_round**（使用者 10-04，不是 astra 的題）：tasks.json 項目可選非負整數，回合數大於它就不再起新 run，跟 `from_round` 對稱；已在跑的不殺；once 已起過的照 launch 標記刪項，沒起成又過期的留著不起（commit 060dca8b）。用途：分配者掛了，使用權照樣到期。spec 4.1。

## 核心精簡：刪掉的誤用保護（10-04）

照 [精簡方案](core-slimming.md)「頂層定案」第 2 條與[組件契約藍圖](component-contracts.md)：違反組件前置條件造成的問題（M 類）不歸組件管，保護刪掉，spec 只留界線一句（§11「其他誤用，不處理」）。順手偵測到的記一筆，不保證偵測到（定案第 4 條）。

**刪掉的保護**（F 號照 [盤點表](core-slimming-inventory.json)）：

| F | 類別／卡 | 原編號 | 刪了什麼 | 界線一句 |
|---|---|---|---|---|
| F31 | M／卡 2.3（tick 前置：生命週期檔只有核心寫） | A2-03 | `aos7_task._judge_broken`：birth.json 壞掉時身分掃描（NODE＋TID）判活、看 exit.json／pid.json 推回 run；View 的 `broken` 欄 | birth.json 被手改或寫壞＝不知道，單槽保留；確認沒在跑後人刪 birth.json |
| F33 | M／卡 2.8、2.5（任務前置：同 uid、environ 可讀） | A3-02 | `aos7_proc.DENIED`、`related_of`、`_denied_related`、`env_procs` 的 `related`、`kill_identity` 的 `runner`、`group_is_task` 的 denied 分支、`stat_of` 的 sid、pid.json 的 `uid` | environ 讀不到權限的程序一律當成不是任務；脫離管理範圍的任務不保證不雙開、kill 收得到 |
| F28 | M／卡 2.5（runner 前置：由 tick 照約定起）、K-06 | K-06、astra-7 H-05 | `aos7_task.same_dir` 與 start_in_slot 兩處比對、`aos7_run.env_mismatch` | 起任務途中搬 node＝誤用；鬼目錄已接受 |
| F03 | M／卡 2.1（daemon 前置：node 路徑沒有符號連結） | A2-04 | daemon `check_nodes` 每圈 realpath 比對與 S_ISLNK 分支（併進「不是資料夾」）；tick／tock `held_node` 的 readlink＋canonical_node 比對 | 運行中把 node 路徑**中間段**換成符號連結＝誤用。留：登記時檢查、`O_NOFOLLOW` 開 node、lstat 不是資料夾或 inode 變了＝missing |
| F36（簡化） | 卡 2.6（kill 範圍 Q1） | — | `group_is_task` 看成員父程序環境的那段 | 只留「群組沒有活成員，或有成員是這個 run」才打，防 pgid 被重用（外部故障）；任務改自己的 pgid＝誤用 |

**保留**（不是誤用）：A3-09「kill 最後確認 pid.json 記的任務程序已不在才回 ok:true」（B，回條不能說謊）；A3-03 生命週期檔「存在但不是一般檔＝不知道」（定案第 3 條併成統一規則，之後收進單一讀檔入口）。

**刪掉的測試**（17 項；252 → 235）：

| 測試 | 對應 | 理由 |
|---|---|---|
| `test_matrix_docs.TestBrokenBirth.test_birth_live_{half,list,run_str}` | F31 | 壞 birth＋活程序判 LIVE 是證據鏈；現在一律 UNKNOWN（`test_birth_none_*` 仍斷言不起、不判 lost、刪 birth 後照常起） |
| `test_matrix_docs.TestBrokenBirth.test_birth_exit_{half,list,run_str}` | F31 | 壞 birth＋exit.json 推回 run 是證據鏈 |
| `test_matrix_docs.TestBrokenBirth.test_birth_pid_{half,list,run_str}` | F31 | 壞 birth＋pid.json 推回 run 判 lost 是證據鏈 |
| `test_ctl.TestIdentityScan.test_broken_birth_uses_node_tid_scan` | F31 | 同上（壞 birth 靠 NODE＋TID 掃描判活） |
| `test_matrix_faults.TestProcUnknown.test_brokenbirth_environ_{EIO,ESTALE}` | F31 | 壞 birth 不再做身分掃描，environ 注入打不中（矩陣要求命中 ≥1）；壞 birth＝UNKNOWN 已由 `test_birth_none_*` 測 |
| `test_matrix_a3.TestHiddenEnviron.test_runner_dead_before_pid_not_lost` | F33 | 不可 dumpable 任務在已知 session 裡＝不知道，是誤用保護 |
| `test_matrix_a3.TestHiddenEnviron.test_kill_live_hidden_task_not_ok` | F33 | 同上；A3-09 的「kill 不說謊」由 `test_matrix_faults` healthy 系列的 kill 控制（ok:false／unknown）繼續測 |
| `test_matrix_faults.TestProcUnknown.test_orphan_proc_environ_EACCES` | F33 | 孤兒任務自己 environ 讀不到＝任務違反「environ 可讀」；現在當成不是任務 |
| `test_matrix_daemon.TestDaemonMatrix.test_symlink_parent_outside_root` | F03 | node 的上層換成符號連結＝路徑中間段，誤用 |
| `test_matrix_misc.TestSymlinkInProcess.test_symlink_node_parent` | F03 | 同上（同程序 tick／tock 版） |

沒有加回的：`deadboth` 矩陣裡排除的 environ × EACCES——`_deadboth` 斷言「掃描讀不到＝UNKNOWN、不寫 lost」，現在 environ EACCES 當成不是任務會直接判 lost，正好就是已有的 `test_deadboth_skip_proc_environ_EACCES`，不重複加。`test_symlink_same_inode`（node 本身換成連回原處的連結）照新程式仍過（lstat 看到連結＝不是資料夾），改標〔core〕保留。F28 沒有專門測試。

## 核心精簡：錯誤四分支（10-04）

照[精簡方案](core-slimming.md)第 4 節與頂層定案第 3、4 條。判定入口：讀檔 `aos7_fs.fact`（N／OK／BAD／U）、程序 `aos7_proc.proc`（N／OK starttime／U）、例外 `aos7_fs.Unknown(why, kind)`（併掉 `ProcUnknown`、`ReadBack`、tick 的 `_Skip`；`LockTimeout` 改成 Unknown 的子類）、紀錄 `aos7_fs.hold(where, kind, why, **extra)`（`{"kind","where","why","at"}`；`clip` 搬進 fs）。`read_json3`（含 strict 參數）、`is_regular`、`pid_state` 拿掉；`read_json` 只剩寬鬆包裝（顯示、任務端用）。

**行為變化**（都照四分支的規則，不是另加的檢查）：

| 變化 | 以前 | 現在 | 類 |
|---|---|---|---|
| G1：寫 tasks.json 的人讀舊內容 | `edit_json` 用寬鬆讀，壞掉／讀不到／FIFO 一律當空表，寫回只剩新項（實驗重現過） | 讀不到、不是一般檔、壞掉＝不知道，丟 Unknown、不寫；`aos7-ctl add` 退出碼 1、restart 回條 ok:false 不 kill、tick 記 tasks_error、retry_lost 當不知道 | 真 bug（B） |
| tick 在表鎖內重讀 tasks.json（寫 launch 標記） | 讀不到時以空表為基底寫回 | 丟 Unknown：這回合一個都不起（once 不能沒標記就起）、記 tasks_error | 同 G1 |
| G2：tick 非 3 的失敗（例外、退出碼 1） | 照常往下 tock（印 skipped），被當成一回合，扣 `resume --rounds` 倒數 | 退出碼只看 0／3／其他：其他＝失敗退避、回頂端，不算回合、不扣倒數；tick 被逾時收掉照舊標 `incomplete: tick` | 真 bug（B） |
| 存在但不是一般檔（頂層定案 3） | 生命週期檔＝不知道，其他檔（tasks.json、timeline.json…）＝不存在 | 一律＝不知道（U）。tasks.json：這回合不起、tock 不刪槽；timeline.json：用預設並記一筆；daemon 控制檔不是一般檔照舊回條 ok:false（B：請求本身不合） | U |
| pid.json／exit.json 內容壞掉 | 當不存在 | 不知道（核心自己寫的檔壞了只能是被手改或磁碟壞） | U |
| daemon 起來時 nodes.json／paused.json／gen.json 讀不到或壞掉 | 當空的照跑（gen 從 1 重數，之後一寫就把原內容蓋掉） | daemon 不起來，退出碼 3、stderr 說明 | U |
| daemon 控制檔讀不到（I/O） | 回條 `not a JSON object` 並搬走 | 留著，下一圈再看 | U |
| tasks.json 讀不到時的加掛審核 | `mount_allow` 當沒寫（全給） | 這回合不審，請求留著 | U |
| tock 總結讀回確認不了 | 退出碼 1 | 退出碼 3（不知道；時間線本來就看 round.json 有沒有關上，結果一樣） | U |
| 錯誤紀錄格式 | `last_error` 是 `{"prog","rc","round","at","kind","err"}`；總結 `errors` 與 `notify_errors` 是 `{"slot","phase","err"}` | 一律 `{"kind","where","why","at"}`＋身分欄（`slot`／`run`／`round`／`rc`）；`phase: judge` → `where: judge`、`kind: unknown`；`phase: unsure` → `kind: unsure` | — |

**保留的例外**：last-round.json 內容壞掉（BAD）照舊**重新產生**總結、不當不知道停住——tock 是它唯一的寫者，總結本來就由各槽重算，重寫不丟任何東西（`test_matrix_docs.TestLastRoundJson` 鎖住這個行為）；讀不到（U）照規則退出碼 3。

**改了斷言的既有測試**（行為沒變，只是格式或名字跟著改）：

| 測試 | 改了什麼 |
|---|---|
| `test_once_threestate.TestThreeState.test_read_json3_states` → `test_fact_states` | `read_json3` 拿掉，改測 `fact`；FIFO 從「不存在」改成 U（定案 3），多測資料夾＝U |
| `test_matrix_faults.TestProcUnknown` 的 healthy／orphan／deadboth 系列 | 總結 errors 的判斷從 `phase in (unsure, judge)＋err` 改成 `where == judge＋why` |
| `test_matrix_faults.TestProcUnknown.test_kill_identity_incomplete_scan` | `aos7_proc.ProcUnknown` → `aos7_fs.Unknown` |
| `test_matrix_faults.TestDaemonStatUnknown` | `last_error.err` → `why` |
| `test_matrix_misc.TestDiagnostics`（兩項） | `err` → `why`；`phase: unsure` → `kind: unsure` |
| `test_matrix_docs.TestBrokenBirth.test_birth_none_*` | errors 的 `err` → `why` |
| `test_daemon.TestStuckActions.test_stuck_tick_cut_and_round_marked` | `last_error.prog` → `where` |
| `test_daemon.TestDaemonDeath.test_unverified_holder_not_killed` | `last_error.err` → `why` |
| `test_matrix_a3.TestReplayNotify`（兩處） | notify_errors 的 `err` → `why`、`phase` → `where` |

**新增測試**（`tests/core/test_errors.py`，8 項）：G1 的 `aos7-ctl add` 遇半寫／FIFO／EIO 注入拒寫且檔案原封不動（3）、不存在照常加（1）、restart 遇壞表回 ok:false 不 kill（1）；定案 3 的 tasks.json FIFO 不起不刪、timeline.json FIFO 用預設並記錯（2）；G2 的 `.aos/` 唯讀時 `resume --rounds 3` 不被吃掉、修好後剛好跑 3 回合再 pause（1；改回舊判斷會失敗，已驗證）。

## 核心精簡：擴充點、子 daemon 包、稽核包（10-04）

照[精簡方案](core-slimming.md)第 5.2、6 節。核心給模組三個小出口（核心不知道它們的語意）：

- **`x` 透傳**：tasks.json 項目可帶 `x`（物件），tick 不看內容、照抄進 birth.json；restart 照 birth 重起時也帶著（`RESTART_KEYS`）。不是物件＝那項不合、跳過、記 tasks_error。
- **事實欄位 `never_started`**：lost 時 birth 沒有 runner、沒有 pid.json、out.log 不存在或空 → exit.json 與總結 `ended` 那筆帶 `never_started: true`（out.log 讀不到大小＝不帶）。retry_lost 的判斷改成建立在這個事實上（retry_lost 本身下一步才移出）。
- **通用守門檔** `.aosd/stop-guard.json`：存在而 `allow` 不是 true（讀不到、壞掉也算）→ 控制檔 stop 回 ok:false（帶 `note`）；SIGTERM 照停。

**移出核心**（F50 → 子 daemon 包 `modules/subd/aos7-subd`；F55 → 稽核包 `modules/audit/aos7-audit`）：tasks.json 的 `subroot`／`allow_stop` 欄、tick 的子根檢查與同 tick 認領、起任務時的 `AOS7_SUBROOT` 與三個 owner 環境變數、aos7_task 的 `registered_nodes`／`under`／`subroot_of`／`stopped_note`／`subroot_running`／`check_subroot`、daemon 的 `owner()`／`claim_owner()`／stop 時寫 stopped.json／起來時刪 stopped.json；aos7-run 裡 `AOS7_AUDIT` 那段（包裝程式自己設 `AOS7_AUDIT` 與 `PYTHONPATH`）。

**舊項目帶 `subroot`／`allow_stop`**：選「那項不合、跳過、記 tasks_error 指到子 daemon 包」，不選「當未知欄位忽略」——忽略的話那項照起，argv 裡常見的 `"$AOS7_SUBROOT"` 會是空的，子 daemon 會起在錯的地方。

**行為變化**：

| 情況 | 以前（核心 tick 做） | 現在（包裝程式做） |
|---|---|---|
| 子根有 stopped.json、已被認領、位置不合 | tick 不起，記 tasks_error，總結 `skipped` | 包裝程式起了、印原因到 out.log、退出碼 1；總結 `ended` 該 run code 1 |
| 同一個 tick 兩項認領同一個子根 | tick 在同一回合擋下第二項 | 兩項都起，先拿到 `<子根>/.aosd/subd.lock` 的那個跑，另一個退出碼 1 |
| 人手直接起子 daemon | daemon 起來時更新 owner.json 的 daemon 塊、刪掉 stopped.json | daemon 不碰 owner.json、stop-guard.json、stopped.json；刪 stopped.json 由人決定 |
| 子 daemon 被允許的 stop | daemon 自己寫 stopped.json 再停 | daemon 照常停；包裝程式看到子程序結束、自己沒收到 SIGTERM、status `stopped: true` → 寫 stopped.json（by／why 取 ctl-done 最近一份 stop 回條） |
| 任務的 `AOS7_OWNER_*` 環境變數 | tick 給 | 沒有了（擁有者寫在 owner.json，給人看） |
| 稽核 | 任務環境有 `AOS7_AUDIT` 時 aos7-run 加 PYTHONPATH | argv 前面加 `aos7-audit --` |

**改了斷言的既有測試**：

| 測試 | 改了什麼 |
|---|---|
| `modules/subd/tests/test_subd_ownership.py`（5 項，案例一個不少） | 全部改用包裝程式起子 daemon。`test_allow_stop_writes_stopped_and_parent_does_not_restart`：「父 tick 擋下、tasks_error 有 stop」改成「包裝程式退出碼 1（總結 ended code 1）、out.log 有原因、子 daemon 沒起」。`test_manual_restart_keeps_owner_block`：「owner.json 的 daemon 塊更新成新 pid、stopped.json 被刪」改成「owner 塊與守門檔留著、stopped.json 也留著」。`test_subroot_rules`：「tick 只起 s1、tasks_error 列三種原因、任務環境有 AOS7_OWNER_TID」改成「五項都起、不合的三項退出碼 1 且 out.log 有原因、同子根兩項一項退出碼 1（已被認領）、留下那項的子程序環境有 AOS7_SUBROOT」 |
| `test_matrix_once.TestLaunchCrash.test_once_after_birth`、`test_once_threestate.TestOnceCrash.test_crash_after_birth`、`test_options_a3.TestRetryLost`（兩項） | lost 紀錄多了事實欄 `never_started: true`（tick 在 after-birth 被殺，birth 沒有 runner） |

**新增測試**：`tests/core/test_exits.py` 6 項（`x` 照抄、壞 `x` 與舊 subroot 欄跳過、never_started 有／無、守門檔擋／壞掉擋／放、SIGTERM 不看守門檔）；`modules/audit/tests/test_audit_wrapper.py` 1 項。
