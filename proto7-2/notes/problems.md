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
| A3-02 environ EACCES 使不可 ptrace 任務雙開 | 已修＋改 spec | environ EACCES 的程序在這個 run 的 runner session 或 pid.json 群組裡（殭屍除外）＝不知道，不判 lost；其他照舊當不是任務。cmdline 讀不到（含 EACCES）＝不知道。pid.json 多 `uid`。spec §11 明寫管理範圍（同 uid、environ 可讀；setuid／換 uid／關 dumpable 不在範圍），§5.4「不會雙開」加上只對管理範圍內成立 |
| A3-03 非一般檔當不存在，繞過 round／birth 保護 | 已修 | 三態讀檔加嚴格模式給生命週期檔（round、last-round、birth、pid、exit，及 ctl-seen）：存在但不是一般檔＝不知道；其他檔照舊當不存在。tock 刪槽前讀 tasks.json 也用嚴格讀。spec §0 |
| A3-04 明確 id 靜默截 64 字 | 已修 | id 完整使用、不截斷；超過 200 字拒絕（回條 ok:false 說明）。spec §6 |
| A3-05 內容＋mtime 不是唯一意圖、作用域未定 | 已修＋改 spec | 沒帶 id 時雜湊加上 `<node-id>/<槽>`、st_dev、st_ino；id 作用域定為同 node 同槽，pending once 查重比同槽＋同 ctl_id。`aos7-ctl task` 自動產生 uuid，`--id` 重送沿用。spec §6、§10 |
| A3-06 owner 檔名有損編碼互蓋 | 已修 | by／node／owner 每段無損編碼（`/`→`+`，其他 `%XX`；太長取前 40＋`~`＋sha1 前 16）。spec 2.3、§10 |
| A3-07 mount 子目錄的暫存檔漏清 | 已修 | tock 清槽暫存檔時連 `mount-req/`、`mount-done/` 一起，不遞迴清任務自己的資料夾。spec §0 |
| A3-08 重播通知失敗被吞 | 已修 | 重播補 tock.json 失敗、alive 的槽判不出／判定例外都記進 round.json `notify_errors`（每筆帶 slot、run、round）與回傳；下一個 tick 開回合前補（同 run 還活著才補，補不上進 `tasks_error`），對已關回合再跑 tock 也補（`notify_retried`）。spec §7 |
| A3-09 任務仍活、群組核對不了，kill 卻回成功 | 已修 | kill 最後確認 pid.json 記的任務程序（pid＋starttime）已不在，否則 `ok: false`（unknown）；群組有成員 environ 讀不到權限又沒成員核對得到＝不知道。spec §6 |
| 讀碼：`kill_node` 掃描不完整時沒打記著的群組 | 已修 | 照 spec 2.6 照樣打記著的群組，事件 ok:false；environ 讀不到權限又在記著群組裡＝不完整 |
| 矩陣盲點（healthy 12 案有 9 案注入命中 0 次） | 已修 | 測試鉤子加 `AOS7_TEST_FAULT_HITS` 命中紀錄（P2-15），每個注入案例斷言命中 ≥1。補了 EACCES 孤兒、restart 完成證據跨 run、FIFO 生命週期檔、id 碰撞等組合——見 [tests/test_matrix_a3.py](../tests/test_matrix_a3.py) |

- **until_round**（使用者 10-04，不是 astra 的題）：tasks.json 項目可選非負整數，回合數大於它就不再起新 run，跟 `from_round` 對稱；已在跑的不殺；once 已起過的照 launch 標記刪項，沒起成又過期的留著不起（commit 060dca8b）。用途：分配者掛了，使用權照樣到期。spec 4.1。
