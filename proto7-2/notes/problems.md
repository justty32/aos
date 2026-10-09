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
| A3-08 重播通知失敗被吞 | 已修 | 重播補 tock.json 失敗、alive 的槽判不出／判定例外都記進 round.json `notify_errors`（每筆帶 slot、run、round）與回傳；下一個 tick 開回合前補（同 run 還活著才補，補不上進 `tasks_error`），對已關回合再跑 tock 也補（`notify_retried`）。spec §7。**loop4 F47 改成只記不補**：跨回合補送已刪，只留記錄與同回合重播補寫 |
| A3-09 任務仍活、群組核對不了，kill 卻回成功 | 已修 | kill 最後確認 pid.json 記的任務程序（pid＋starttime）已不在，否則 `ok: false`（unknown）；群組有成員 environ 讀不到權限又沒成員核對得到＝不知道。spec §6 |
| 讀碼：`kill_node` 掃描不完整時沒打記著的群組 | 已修 | 照 spec 2.6 照樣打記著的群組，事件 ok:false；environ 讀不到權限又在記著群組裡＝不完整 |
| 矩陣盲點（healthy 12 案有 9 案注入命中 0 次） | 已修 | 測試鉤子加 `AOS7_TEST_FAULT_HITS` 命中紀錄（P2-15），每個注入案例斷言命中 ≥1。補了 EACCES 孤兒、restart 完成證據跨 run、FIFO 生命週期檔、id 碰撞等組合——見 [tests/core/test_matrix_a3.py](../tests/core/test_matrix_a3.py) |

- **until_round**（使用者 10-04，不是 astra 的題）：tasks.json 項目可選非負整數，回合數大於它就不再起新 run，跟 `from_round` 對稱；已在跑的不殺；once 已起過的照 launch 標記刪項，沒起成又過期的留著不起（commit 060dca8b）。用途：分配者掛了，使用權照樣到期。spec 4.1。

## astra 第三輪（A4）與 loop4 的處理

依 [astra 第三輪報告](play/2026-10-04-astra-3-infra.md)、[loop4 藍圖](blueprint-loop4.md)。核心 commit daf8d5cf、step 包 39681eec、control／audit 62e8c46b、契約卡見 play README 該列。核心 2791→2757 總行、2151→2123 實際程式。

| 編號 | 歸屬／類 | 處理 |
|---|---|---|
| A4-01 加掛讀不到當空值 | 核心 tick／B | 請求與 birth 改走 `fact`：U（birth 不是物件也算）＝請求留著、不寫回條、不改 birth，round.json `mounts` 記一筆 `unknown`；壞請求照舊回 `ok:false`。spec §0、§4.5 |
| A4-02 control 並行同 req_id 多起一次 | control 包／B | 表鎖內重讀 birth：已帶同 req_id 或 run 已換＝不改表、回 `once:"done"`；鎖內 birth 不能用＝拒寫。control README |
| A4-03 step 初始 wait 沒耐性起點 | step 包／B | 新框架（含 `restart_on_end` 重開）`since`＝當下回合；不知道就每圈開頭補。step spec §3 |
| A4-04 step checker 壞型別拋例外、漏查繼承限制 | step 包／B | 先驗欄位型別（不合只報型別、不拋例外）；`on_timeout: kill` 查套全域預設後的有效值（wait 步報錯）。step spec §2、§6 |
| A4-05 audit 不更新登記邊界 | audit 包／B | 判巢狀邊界時重讀 nodes.json；只記不擋不變。audit README |
| A4-06 control 去重期限 | control 包／G→文件 | 寫明完成證據＝表上 pending once 或**目前** birth 帶該 id；換 run 後再送同 id＝新意圖，跨 run 去重由呼叫者自己留證據；不加回 ctl-seen。control README 契約卡 |
| A4-07 step 選項覆蓋／停點名稱 | step 包／G→文件＋小改 | run 步接受 `wake`；spec §2 列明可逐步覆蓋的只有 `wake`／`on_timeout`／`on_unknown`；§5.5 寫明 kill 後 `halt.kind=timeout`、處理同 unknown |
| A4-08 契約卡過時 | 契約文件／G→文件 | 核心卡留 [component-contracts](component-contracts.md)，包的卡住進七個包 README「契約卡」節；卡只寫職責／前置／保證／明確不管，保證引 spec 節號 |
| F47 欠的 tock.json | 核心 tock／簡化 | 刪跨回合補送（`retry_notify`、tock 已關分支、tick 開回合前補）；寫不進去只記 `notify_errors`，同回合重播補寫保留。任務本來只看得到最新 tock（S-11）；要補由模組讀 round.json。spec §7、卡 2.4 |

- 線頭 1：spec §4.4 寫明核心給上層的兩個原語 (a) 移項時 birth 已寫好、(b) 槽最早在報結束的下一個 tock 才刪；step「第三個 tock」寫在 step spec §5 引這兩句；加 birth 與移項之間 SIGKILL 的測試。
- 線頭 3（G3）：本輪不改程式；subd README 界線補兩句；重現了再做 `kill_grace_s` 選項。

## astra 第四輪（A5）與 loop5 的處理

依 [astra 第四輪報告](play/2026-10-04-astra-4-infra.md)、[loop5 藍圖](blueprint-loop5.md)。核心零改動（仍 2757／2800）。

| 編號 | 歸屬／類 | 處理 |
|---|---|---|
| A5-01（＝G3）父 kill 後子空間原任務不被收 | subd 包／B | subd 起 argv 前寫包自有紀錄 `subd-life.json`；重開時（紀錄非 `stopped`、含缺）持 `daemon.lock`，以子根路徑前綴＋環境身分收前代 launcher／runner／任務並重掃，乾淨才放行，掃不完不起新代。核心 §5.4 不保證重開必收前代，原 README 說法撤回。8c2145c4；同壓力探針 10／10（[evidence](play/2026-10-04-loop5-subd-evidence/stress/results.json)） |
| account 草稿 5 條意見 | budget 包（原名 account）／設計 | 收進 budget v1 契約卡與 spec：失敗不等於未支用、三種操作鍵、帳活過 step close、不可再分、半開效期與 completed_tock。025d2bfe。另記 5 個契約缺口在 budget spec（取消需可查詢後端、時鐘重建只靠規則、儲存只增不清、holder 合作式綁定、step 自動重送只一次） |

## astra 第五輪（A6）與 loop6 的處理

依 [astra 第五輪報告](play/2026-10-04-astra-5-infra.md)、[loop6 藍圖](blueprint-loop6.md)。核心零改動（仍 2757／2800）。

| 編號 | 歸屬／類 | 處理 |
|---|---|---|
| A6-01 合法 stop 記錄提交中斷後重開錯收 | subd 包／B | 「允許的 stop 已完成」改以核心停止事實判定：status `stopped` ＋ `ctl-done/` 成功 stop 回條且時間 ≥ 本代 since（父 kill 不留回條）；重開時成立就補完提交、不回收。95426b17；[驗收](play/2026-10-04-loop6-subd-evidence/summary.md) |
| A6-02 budget 後端讀取故障回 1 | budget 包／B | 入口回非終局 unknown；call／cancel／settle 共同故障邊界 rc 3、一行 JSON。bd9dcc10；[驗收](play/2026-10-04-loop6-budget-evidence/summary.md) |
| budget 五缺口 | budget 包／G | spec §9 已知界線五條、§10 保存與退役；`clock_hw` 每次推高；孤兒回條掃（3 回合寬限）；退役拒收新 K；step run 步 `max_resends`（預設 1）。bd9dcc10 |
| A7-01 adapt scale 平手取偶數 | adapt 包／B（低） | `round_half_up`（Decimal ROUND_HALF_UP，平手遠離零）；spec §2 寫明；單元測試 0.5／1.5／2.5／4.5／-2.5。藍圖 §3.3 門檻例子勘誤（801 true、800 null、799 false）；subd README 補牆鐘不倒退前置（astra-6） |
| adapt 第一版 | 新任務包 | 最新值轉接（d3738e04）；自報缺口：換鏈只能偵測不能切換、任務端無法注入測試故障、時鐘函式跟 budget 重複（待搬進工具包） |

## astra 第七輪（A8）adapt 數值回歸的處理（10-05）

依 [play7 報告](reviews/2026-10-05/play7.md) §3、§4（A8-01～04；[code-quality R8-23](reviews/2026-10-05/code-quality.md) 同件）。核心零改動；只動 adapt 包（`aos7_adapt.py`、spec §2／§4.2／§4.3、README 契約卡）。原則：spec 沒寫到或互相衝突的地方，一律照「不發布錯的 `ok`」。

| 編號 | 處理 |
|---|---|
| A8-01 Decimal 精度不足拋例外、任務退出留舊 ok | 鏈改用精確十進位（`EXACT` context：精度、指數開到上限；鏈裡只有乘、加、比較、取整，都精確）；1e16 取 12 位、1e28 取 0 位、30 位整數都照算。另加保險：`pass_` 判定拋沒料到的例外＝這圈 unknown（`internal_error`）、框架不動、不退出（spec §4.3）。 |
| A8-02 取整後強轉 float，整數失真突破誤差界 | 發布時才轉 JSON 數字（`publish`）：整數值且沒有小數位（或 float 放不下）＝ Python int 原樣（2^53+1 不變）；其餘 float，**float 與精確值的差加進 `err`**，誤差界往上取到 float。 |
| A8-03 浮點端點塌縮 | 門檻區間 `[x − err, x + err]` 用精確十進位比；x=10000、err=5e-13 對 10000 四種比較都落誤差帶。 |
| A8-04 有限輸入乘出 Infinity 仍 ok | 產出欄的值或誤差界超出 float 範圍＝unknown `out_of_range`（§4.2 第 7 列：讀取成功、答案不能用，不靠耐性撐舊值）；trace 裡超範圍的中間值記成十進位字串。中間值超範圍、最後縮回來的照常 ok。順帶：`is_num` 對大整數（10^309）不再拋 OverflowError。 |

**spec 自己的缺口與取捨（照最保守）**：
- 原 spec 只寫 `err ← |mul|×err + q`，沒算「發布成 float」的表示誤差——照字面會發布超出誤差界的 `ok`（A8-02）。改成表示誤差加進發布的 `err`；鏈內部（門檻）仍用不含表示誤差的精確值。
- 原 spec 沒有「超出範圍」這列；放第 7 列（unknown、不撐舊值）而不是第 3 列耐性分支，因為來源讀到了、是答案不能用。
- 數字語意定為「JSON 文字的十進位值」（float 取 repr）：`mul: 0.1` 就是 0.1。行為變化：沒 `round` 時不再有 float 雜訊（801×0.1 發布 80.1，不是 80.10000000000001）；`round: 0` 與整數相乘的產出是 JSON 整數（數值相等，型別從 float 變 int）。
- 檢查器的 `q` 夠不夠蓋取整改精確比（原本有 1e-9 相對寬容，會放行少一點點的 `q`）。
- 驗證：單元測試 +7（`TestNumeric`，修之前全紅）；play7 證據的 `numeric_matrix.py` 改斷言後對本版跑過（390 個平手案例取整正確且在誤差界內、52 個精度邊界 0 例外、6 個大整數原樣、4 個門檻都落誤差帶、2 個值域都 `out_of_range`）。

## 10-05 審查（A8／MC／R8）的處理

依 [next-steps 修補清單](next-steps-fixes.json) 第 2 組。核心零改動。

| 編號 | 歸屬／類 | 處理 |
|---|---|---|
| A8-09 合法 no-kill stop 的回條寫失敗，重開後誤收應保留任務 | subd 包／B | 判定補一條：status `stopped`、沒有合格 stop 回條、但本代有 `last_ctl_error`（at ≥ since，核心 §2.3 處理例外的紀錄）且這代 `--allow-stop`＝不知道是不是那件 stop，**不轉成可回收**：照被允許的 stop 提交（stopped.json 帶 `unconfirmed`），刪掉再起照核心接回。不解析錯誤文字。代價：同代別件控制檔出錯又被父 kill、子 daemon 寬限內收完時會多擋一次（任務已被收，不毀東西）。測試 `test_subd_keep.TestReceiptLost`（`ctl-done/` chmod 555 重現，修前紅） |
| MC-01 刪 stopped.json 重接、argv 前中斷，重開時舊回條不符新 since 而回收保留任務 | subd 包／B | **真程式重現**（`AOS7_TEST_CRASH=subd-before-argv`，修前紅）。從 `stopped` 跳過回收寫的 `running` 帶 `kept`；再起時本代還沒有 daemon 起來過（子根 gen.json 的 at 早於 since）仍照被允許的 stop 不回收、`kept` 沿用；daemon 起來過＝已照核心接回，之後照一般前代。測試 `test_subd_keep.TestReattachInterrupted` |
| R8-18 subd recovering.prev 遞迴成長 | subd 包／品質 | 回收一再被打斷時 `prev` 沿用最初那份前代記錄、加 `attempt` 計次，記錄大小固定。測試 `test_subd_keep.TestRecoveringRecord` |
| （順手）`test_reaped_before_new_daemon` 斷言 run＋1 | 測試 | 新 run＝起它的回合數（核心 `next_run`），父 kill 後隔一回合才重起時是 run＋2；改成比現役槽的 run、且大於被 kill 的 run。改前用 HEAD 的 aos7-subd 一樣紅，非本輪回歸 |

## loop7（10-09）的處理

依 [blueprint-loop7](blueprint-loop7.md) 第 3～6 組；頂層代定在 [decisions-2026-10-09](decisions-2026-10-09.md)。核心有改（D7：行數只印不擋）。A8-09 見上一節。

| 編號 | 歸屬／類 | 處理 |
|---|---|---|
| A8-05（＝R8-03）登記持久化失敗後重送仍回成功、磁碟沒修好 | daemon／B | register／unregister 先寫候選 nodes.json，成功才換記憶體；失敗回條 `ok: false`、登記不變、可重送（spec §2.3）。K2 7ac33100；測試 `test_daemon.TestDaemonDurableRecovery` |
| A8-06（＝R8-01）runner 已起、任務還沒 Popen 時 kill 回成功 | task／G→定 D1 | runner 還在、沒有同 run 的 pid.json／exit.json＝回 `ok: false`／`unknown`、請求留著下次再做；已掃到相符任務照殺（spec §6）。K1 915f53e6、235172da；daemon 逐槽收回 unknown 算未確認乾淨（K2 35f21912）。測試 `test_ctl` k1 系列 |
| A8-07（＝R8-08）動態加掛連結已建、birth 未提交，中斷後不能冪等恢復 | mount／B | 建連結撞 EEXIST 且指向同處＝已建；讀不到連結＝不知道、請求留著；birth 失敗紀錄不算已掛（R8-09）。K4 f6aa2a8d；測試 `test_mount_dyn` |
| A8-08（＝R8-15／R8-16）budget 共同 unknown 邊界漏兩條路徑 | budget／B | payload 讀不到、已結算重播時入口回條讀不到都退 3（不補欄、不寫 `--out`）；退出碼表 0／1／2／3 三處統一。B d8b5f267 |
| A8-10 budget 的 rc 3 被 step 當一般失敗 | step＋budget／G | step run 步選項 `unknown_codes`（預設空）：列出的退出碼走 `on_unknown` 同 request 重送；重送額度記 request 層 `resends`（R8-14），過期 intent 也走 `on_unknown`（R8-13）；fakeapi 示範表開 `[3]`；文件分清兩種 unknown。(c) 不做（見代定清單）。S 135314e2、B 937001bf |
| A8-11（＋R8-20）巨大整數 interval 讓設定驗證拋例外、node 不開回合 | timeline／B | `read_config` 先型別、再範圍（≤ 一年）、最後 isfinite，整段不丟例外；壞值用預設並記錯。K3 9c9cfa5f；測試 `test_errors.TestTimelineConfig`（proto7-1 案例搬回） |
| C8-01（＝R8-03 同族）取消登記後 daemon 被殺，回收義務遺失 | daemon／B | 回收意圖先寫 nodes.json `reaping`（`{id: {since, why}}`），確認乾淨且清除寫成功才拿掉；重開續收（spec §2.6）。K2 7ac33100；測試 `test_unregister_crash_before_kill_resumes` 等 |
| C8-02（＝R8-02）node 替換後中斷回收，新舊任務同活 | daemon／B | 在 `reaping` 的 node 不開時間線；收不乾淨保留 missing、約每秒重試；舊時間線結束後再掃一次才算乾淨（K2 0b68b3a0）。磁碟不記 pgid，重開只靠身分掃描 |
| C8-03 任務包槽外暫存檔沒人回收 | 核心＋各包／G | 原則寫進 spec §5.5：核心只清自己的資料夾，槽外由寫的人跑 `sweep_tmp`；step 直譯器啟動清工作資料夾與 results、budget 帳任務起時清 `gateway/`；adapt 份已做（`9d8767da`，`Adapter.init()` 啟動時清 `in/`）；三包都處理完 |

已知限制（不修，記在代定清單）：N-06 回合已關、`steps` 還沒存之間當機，重開多跑一回合；daemon 停機時 node 被換掉偵測不到；once_retry R8-26 重讀 birth 到提交之間仍可能多補一次（契約是至少一次）；node id 很長（約 250 bytes）時 history 檔名太長。

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

## 核心精簡：控制包與 once 保證包（10-04）

照[精簡方案](core-slimming.md)頂層定案第 1、5 條（第 6 節、6.1 第 1、3 點）。

**核心的任務控制只剩 kill，`run` 必填**：槽 ctl.json＝`{"op": "kill", "run": 整數, "by", "why"}`。op 不是 kill、run 缺或不是整數＝輸入不合（B）：回條 ok:false、刪請求；run 已換人＝ok:false；run 已結束＝ok:true 順便收殘留；A3-09「最後確認任務程序不在才 ok:true」保留。帶 run 讓重播天然冪等，所以拿掉了：restart／reload 整段、`ctl_id_of`（id 與檔案 inode＋mtime 雜湊）、`ctl-seen.json`（read_seen／write_seen／_seen_again、tock 刪槽時拿掉那筆）、`reload_item`、`def_diff`、`dyn_mounts`、`RESTART_KEYS`／`DIFF_KEYS`／`SCHED_KEYS`、`_append_items`、birth.json 的 `ctl_id`／`restart_of`、tasks.json 的 `restart_of`／`mounts_dyn`／`ctl_id` 欄、起任務時照 `mounts_dyn` 標 dyn。`slot`（once 釘槽）留在核心。

**移到控制包**（`modules/control/aos7_control.py`）：`restart(node, slot, why, reload, req_id, by)`——讀 birth → 拿表鎖加釘同槽的 once（`x.restart_of`、`x.req_id`，同槽同 req_id 不重加；birth 已帶同 req_id＝已經重起過，什麼都不做；表壞掉照 G1 拒寫）→ 寫 kill 帶 run。`aos7-ctl task … restart` 改呼叫它；`aos7-ctl task … kill` 沒給 `--run` 就讀 birth 帶現在的 run。

**動態掛載的 `dyn` 標記**：留在核心——它是加掛審核寫進 birth 的事實（「這個掛載是執行中加的」），控制包 reload 靠它分出要另外帶過去的掛載；拿掉的只有「起任務時照 `mounts_dyn` 再標 dyn」那段（只為 restart 存在）。代價：restart 後新 birth 把帶過去的掛載當宣告、不再標 dyn，之後再 reload 不會帶它們。

**移到 once 保證包**（`modules/once_retry/retry_lost.py`，普通 keep 任務）：核心拿掉 tasks.json 的 `retry_lost`／`retry_of` 欄、`retry_wanted`、`requeue_lost_once`、lost exit 的 `retried`。核心只留事實欄 `never_started`。舊的頂層 `retry_lost` 欄＝那項不合、tasks_error 指到這個包（不靜默忽略：忽略會讓人以為還有至少一次）。要保證的 once 改帶 `x.retry_lost: true`。

**行為變化**：

| 情況 | 以前 | 現在 |
|---|---|---|
| ctl.json 不帶 run 的 kill | 收現在這次 | 輸入不合：回條 ok:false、刪請求、沒執行（`aos7-ctl task … kill` 會自動帶） |
| ctl.json 的 restart | tick／tock 原子做（加 once＋kill，ctl-seen 防重播） | 回條 ok:false「op 只有 kill」；restart 由請求端（控制包）做 |
| 請求端在加 once 之後、寫 kill 之前死掉 | （核心做，不存在） | once 等槽空才起（busy）；重試責任在請求端（同 req_id 再呼叫一次） |
| retry_lost | 核心判 lost 時同步加回（精確） | 模組收到 tock 才加回（取樣：慢了、被 pause 錯過那筆就退回最多一次） |
| lost 紀錄 | 加回時帶 `retried: true` | 不帶（核心不知道）；看 tasks.json 的 `x.retry_of` |

**搬走、改寫的測試**（250 → 250）：

| 原測試 | 去向 |
|---|---|
| `test_ctl.TestCtl` 的 restart 四項（same_slot_new_run_keeps_state、reload_takes_new_definition、reload_refused_without_kill、restart_receipt_survives_new_run） | 搬到 `modules/control/tests/test_control.py`，改用 `aos7_control.restart`（reload 拒絕改成「回 ok:false、沒寫 kill」） |
| `test_ctl.TestMounts.test_mount_request_served_and_restart_carries_dyn` | 拆兩項：核心留 `test_mount_request_served`（加掛審核、dyn 標記；換 run 改用 kill，加掛的不帶過去）；控制包 `test_restart_carries_dynamic_mounts`（新增一項） |
| `test_errors.TestTasksWriteG1.test_restart_with_bad_table_does_not_kill` | 搬到控制包（壞表＝restart 回 ok:false、不寫 kill） |
| `test_matrix_once.TestRestartCrash`（once／keep × 3 點，6 項） | 搬到控制包改寫：3 點改成「請求端加完 once、寫 kill 前被殺（同 req_id 重試）」「tock 寫完 kill 回條、刪請求前被殺」「tick 同上」；斷言照舊（只重起一次、不雙開、表上不留殘項），新 birth 帶 `x.restart_of`（以前是 `ctl_id`＋`restart_of`） |
| `test_matrix_a3.TestCtlSeen`（3 項） | 改寫留在核心成 `TestKillReplay`：ctl.json 刪不掉＝每次再執行也只對同一個 run（新 run 不被打到）；run 不對＝ok:false、run 缺＝輸入不合、改對重送照樣執行；`ctl-after-done` 被殺後再執行同一份 kill＝already ended、只重起一次 |
| `test_matrix_a3.TestCtlId.test_same_prefix_ids_distinct` | 改寫到控制包 `test_same_prefix_req_ids_distinct`（前 199 字相同的兩個 req_id 各自生效） |
| `test_matrix_a3.TestCtlId.test_two_slots_same_content_mtime` | 改寫到控制包 `test_two_slots_same_req_id`（同 req_id 不同槽各自生效） |
| `test_matrix_a3.TestCtlId.test_cli_task_auto_id` | 改寫到控制包 `test_cli_restart_auto_id_and_resend`（自動 req_id 兩次都生效；`--id` 重送＝once 不重加）；「--id 超過 200 字被拒」那段拿掉（req_id 不截斷、不雜湊，沒有長度限制的理由） |
| `test_options_a3.TestRetryLost`（3 項） | 搬到 `modules/once_retry/tests/test_once_retry.py`：true_runs_once（同程序呼叫模組的 scan；ended 不再帶 `retried`）、default_at_most_once（照舊）、bad_type_skipped 改成「舊的頂層欄被拒、`x.retry_lost` 不是 true 模組不理」；另新增 `test_module_as_keep_task`（模組真的當 keep 任務跑） |

**刪掉的測試**（類別：移出核心＝控制包，頂層定案 1）：

| 測試 | 理由 |
|---|---|
| `test_matrix_a3.TestCtlId.test_too_long_id_refused` | 防的是 ctl_id 被截斷後兩件請求撞成同一件（A3-04）；ctl_id 拿掉了，控制包的 req_id 原樣比對、不截斷，沒有這個問題 |
| `test_matrix_a3.TestCtlId.test_copy_with_same_mtime_new_inode_is_new` | 防的是「沒帶 id 時用檔案 inode＋mtime＋內容雜湊當識別」誤判重播（A3-05）；kill 帶 run 後重播天然冪等，不再需要識別請求檔 |

## 核心精簡：程式減肥、診斷包、防再胖（10-04）

照[精簡方案](core-slimming.md)第 3.3、9 節。核心 `lib/aos7_*.py` 從 3544 總行／2444 實際程式降到預算內（數字見 `tests/core/test_budget.py` 的訊息，README「防再胖」）。

**做了的**：

- **診斷包** `modules/diag/aos7-diag`（F53）：status 拿掉 `uncertain`（以前 daemon 每 0.25 秒判一次所有槽、把判不出的放進 status），改由唯讀工具按需重算並對到恢復步驟；核心 spec §12 的恢復表搬到 [modules/diag/README.md](../modules/diag/README.md) 當操作手冊。`steps_left` 是 daemon 記憶體裡的倒數，工具算不出來，留在 status。
- **F13 控制檔通道**：拿掉 `.aosd/ctl-failed/`。處理丟例外（例如回條寫不進去）的請求：效果可能已生效、不重做——直接刪掉並記 `last_ctl_error`；刪不掉就記著、不再執行、每圈再試著刪（以前是搬到 ctl-failed，搬不走才留著）。壞的請求一律回條 ok:false（原本就是）。
- **F16 舊動作接管**：`reap_stale_owner` 與 `holder_unverified` 併成一個函式，回 (殺了的 pid, 認不出的原因)；last_error 只記一句原因（kind `stale-holder-unverified`），人工步驟（fuser／lsof、補正 action.owner.json、不要 unlink 鎖檔）寫在診斷包 README。順帶：以前會先試著殺「舊世代、同 starttime」的持有者再看鎖有沒有人拿，現在先看鎖——沒人拿就什麼都不做。
- **F21 任務表驗證改表驅動**：`aos7_tick.FIELDS`（欄位、預設、合格判斷、說明）＋ `MOVED`（移到模組包的舊欄位）。錯誤訊息格式統一成「<欄位> <說明>，拿到 <值>」。
- **收掉的程式**（grep 確認沒人用或只剩一處用）：`aos7_fs` 的 `node_id_of`、`join_id`、`aos_dir`、`real_path`、`clip`（併進 `hold`）、`is_regular`；`read_jsonl` 搬到工具包（只有測試、歷史、稽核用）；`append_jsonl` 不再回半行的位元組數；`aos7_mount.decl_of` 搬到工具包（只有控制包、once 保證包用）；`aos7_proc` 的 `want_env`（併進 `group_is_task`）、`sweep_nodes`（`kill_node` 收多個 node 就是它）；`aos7_task` 的 `tasks_dir`、`_wait_pid_json`（併進 `kill_run`）、`Ctx` 改 namedtuple；`aos7_tick` 的 `Plan`（改 SimpleNamespace）、`_Skip`、`_raw_items`、`GONE`；keep／each 挑槽併成一段；時間線的 `done()`（併進 `leaving()`）；aos7-run 的 `read_birth`（直接用 fact），起程序失敗與起之前失敗共用 `fail()`（runner 退出碼 0→1，exit.json 的 error 改成「起不來：…」）。
- **docstring／註解**：只留「做什麼、保證什麼、丟什麼」與「為什麼」；參數逐一唸過的套話縮成一句；由來編號（A2-／A3-／P2-／astra-N／K-／N-、「以前…」、「註解疑點 檔:行」）拿掉，仍有價值的記在下面。
- **防再胖**：`tests/core/test_budget.py`（總行 ≤ 2800、實際程式 ≤ 2200）；README「防再胖：新功能預設進模組」寫進核心的三問。

**沒做的**：F47（欠的 tock.json 只記不補）——組件契約卡 2.4 的保證寫「通知寫失敗不吞，記 notify_errors，下一個 tick 補」，跟方案衝突；其他手段已經壓到預算內，照隊長指示不做。→ loop4 做了（見下面「astra 第三輪（A4）」，卡 2.4 一併改）。

**改了的既有測試**：`test_daemon.TestCtlFiles.test_receipt_failure_goes_to_ctl_failed_and_stop_still_works` → `test_receipt_failure_drops_request_and_stop_still_works`（斷言請求刪掉、沒有 ctl-failed、有 last_ctl_error；stop 照樣生效）。`test_matrix_misc.TestDiagnostics` 兩項搬到 `modules/diag/tests/test_diag.py` 改成斷言 aos7-diag 的輸出（核心的部分——hold 保留頭尾、tock 總結 errors 有 unsure——照樣斷言），另加一項「diag 唯讀」。新增 `tests/core/test_budget.py` 一項。

### 從程式搬來的由來（一條一行）

| 檔／函式 | 由來 |
|---|---|
| aos7_fs.write_json | 暫存檔用 `.` 開頭，列資料夾的人不會讀到半份 JSON（probes/polyglot N11） |
| aos7_fs.sweep_tmp | SIGKILL 在 rename 前留下的暫存檔沒人收會一直累積（A2-07）；tock 連槽的 mount-req／mount-done 一起清（A3-07） |
| aos7_fs.append_jsonl | append 被殺留下沒換行的半行，新的一行會黏成一條壞行（astra-6 G-08） |
| aos7_taskside.read_jsonl | 逐行各自解碼：半個 UTF-8 字元只壞那一行，不會整檔丟例外（astra-7 H-04） |
| aos7_fs.fact | 生命週期檔換成 FIFO 曾被當不存在而雙開、重開同號回合（A3-03）；頂層定案 3 併成「不是一般檔一律不知道」 |
| aos7_fs.read_round | 半寫、缺 open 的 round.json 以前當已關，會跳過或覆蓋未提交的回合（A2-02） |
| aos7_fs.summary_ok | 重播只拿完整的同回合總結（A2-02 疑點：原本只比 round） |
| aos7_fs.action_lock | 拿鎖後才比世代，排在新 daemon 後面的舊動作看得到世代換了（astra-4 I-01） |
| aos7_fs.reap_stale_owner | 舊世代持鎖者要 pid＋starttime 都對得上才殺（astra-5 F-04）；認不出就不殺、記提示（astra-6 G-10） |
| aos7_fs.edit_json | 寬鬆讀把壞表當空表、寫回只剩新項（G1，layer-interfaces 05-gaps） |
| aos7_daemon.save_paused | daemon 是 paused.json 唯一寫者，仍拿 flock 是為了外部工具的約定（註解疑點 daemon:106） |
| aos7_daemon.ctl_one | 壞控制檔原物留成 .bad（P2-11）；回條路徑被佔成資料夾直接蓋掉（P2-13） |
| aos7_daemon.handle_ctl | 處理失敗的不再執行（註解疑點 daemon:346／416：以前會排到最後再執行一次） |
| aos7_daemon.op_unregister | 先寫回 nodes.json 再收尾（P2-10） |
| aos7_daemon.op_resume | rounds 按 owner 各記一份（A2-06）；沒人 pause 的 resume 不 wake（P2-01 之後 wake 會切掉固定 interval 的回合） |
| aos7_daemon.live_of | 列不出槽沿用上次的 live 與 pgid，不能清空（註解疑點 daemon:522） |
| aos7_daemon.check_root | 看不到 root 不是消失，記在 status 頂層（註解疑點 daemon:595） |
| aos7_daemon_timeline.read_config | interval 不另設上限、不截小數（註解疑點 timeline:76／83） |
| aos7_daemon_timeline._loop | wake 提前結束固定 interval 的回合（P2-01 選 (b)）；early_tock 的回合中 wake 不起作用、也不留到回合後（A2-11）；tick 非 3 的失敗不算回合（G2） |
| aos7_daemon_timeline.run_done | birth 缺 run 以前當已換人、准許提前 tock（註解疑點 timeline:311） |
| aos7_daemon_timeline.err | 診斷截尾把錯誤類型與根因截掉，改成保留頭尾、kind 分欄（A2-08） |
| aos7_tick.held_node | `.aos/` 經 fd 建，不復活已搬走的舊路徑（P2-05）；O_NOFOLLOW 是 A2-04 刪剩的最小保險 |
| aos7_tick.next_round | round.json 不存在照 last-round.json 接號（P2-06）；判不出不再用 last-round 接（A2-02） |
| aos7_tick._tick | tock 之後才結束的 run 先記進 reaped（P2-03）；欠的 tock.json 開回合前補（A3-08，loop4 F47 刪） |
| aos7_tick.check_item | max_live 要大於零（P2-18） |
| aos7_tock._tock | 總結提交後才寫 tock.json，歷史 module 才不會讀到上一回合（A2-12）；總結整份讀回比對（註解疑點 aos7_tock.py:130） |
| aos7_tock._replayed | 列不出槽不能照樣關回合（註解疑點 aos7_tock.py:185）；重播補 tock.json 失敗不吞（A3-08） |
| aos7_task.judge | /proc 讀不到當活＋unsure（K-05、A2-01、P2-08）；沒 runner 沒 pid.json 等兩回合才掃描（P2-02） |
| aos7_task._recheck | 判疑似 lost 前再看一次 exit.json（proto7-1 P-07） |
| aos7_task.resolve | 這個 run 的 aos7-run 還在就當活（矩陣 after-popen）；掃描不完整不判 lost（A2-01） |
| aos7_task.INFRA_FILES | ctl.json／ctl-done.json 換 run 不清，回條要活過新 run（P2-04） |
| aos7_task.kill_run | kill 最後確認任務程序不在才回成功（A3-09） |
| aos7_proc（檔頭） | /proc 讀不到一路往上傳，不再悄悄當沒有（A2-01）；cmdline 的 EACCES 以前當 b""，會把讀不到的 aos7-run 當任務去打 |
| aos7_proc.groups_with_descendants | aos-exec 把 inst 的子程式開在另一個 session（proto7-1 P-05） |
| aos7_proc.kill_groups | 不打自己與祖先所在的群組（P2-14） |
| aos7_proc.kill_node | 掃描不完整時以前連記著的群組都沒收（astra-2 讀碼） |
| aos7_mount.req_name | `a/b` 與 `a_b` 曾推出同一個名字（astra-2 二-2） |
| aos7_mount.in_root／allowed | 只看字面會被符號連結繞出空間根（astra-2 二-3） |
| aos7_mount.serve | 先寫回條、成功才刪請求（astra-5 F-07）；壞請求也要有回條（astra-2 二-1）；`.` 開頭的是暫存檔（註解疑點 aos7_mount.py:202）；請求／birth 讀不到留著、不寫回條（A4-01） |
| aos7_mount.make | 目標不存在先建資料夾（problems M-2）；經 fd 寫、目標在 node 底下經抓著的 fnode 建（astra-5 F-09、astra-6 G-02） |
| aos7_run（檔頭） | 第二參數是內部交接用的 fd 不是身分約束（astra-7 H-09）；fd 無效不回退字串路徑、cwd 是抓著的 node（astra-6 G-02） |
| aos7_run.main | out.log 被建成資料夾照樣寫 exit 127（astra-7 H-06）；argv 有非字串、NUL 照樣寫 exit（probes/chaos B4） |
| aos7_run.round_at | 非阻塞、只讀一般檔，round.json 換成 FIFO 不會卡住 runner（註解疑點 aos7_run.py:165） |

### 從核心 spec 搬出的設計：kernel 用量以 run 為單位（A2-09；kernel 還沒做）

核心會刪的只有換 run 的基礎設施檔與名字不在表上的槽，所以上層的累計要靠自己的 state（核心 spec 第 8 節）。用量的設計：任務的 `usage.json` 只記**這一次 run** 的用量（`{"run": <AOS7_RUN>, "usage": N}`，run 內只增不減，新 run 從 0 起）；kernel 在自己的 kernel-state 對每個 run id（`<槽>#<run>`）記「已見最大值」，**總用量＝所有見過的 run 的最大值相加**，只增不減。換 run、槽被刪又重建都只是多一個 run id（同名槽重建後的 run 取起它的回合數，回合只增，不會撞），不靠「usage 變小」去猜重建。代價：kernel 是取樣的，run 最後一次被看到之後又用掉、還沒被看到就結束並被清掉的那段算不到——總數是已觀測用量的下界；要精確的 cap，任務在超用前自己停。run 紀錄何時合併成「已退役總和」由 kernel 自己決定。
