# 照 proto7-2 spec 實作時碰到的問題

← [proto7-2](../README.md)｜[spec](../spec.md)｜[跟 proto7-1 的差別](changes-from-7-1.md)

照 [spec.md](../spec.md) 做 daemon／tick／tock／run／ctl（10-04）時，spec 說不清、做不出來、或有更簡單的做法的地方。spec 裡對應的地方標了「P2-」。W1～W12 照推薦做，沒有在這裡重列。

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

- spec 第 3 節只寫了讀不到與內容壞掉。不存在：tick 用 last-round.json 的 round 接著數（也沒有就從 1），tock 印 `skipped`（沒有回合可關）。

### P2-07 restart 先加 once 項、再 kill

- spec 原寫「kill，然後在 tasks.json 加 once」。kill 完、加項之前被殺會「殺了沒重起」。改成先拿鎖加項（1 秒拿不到鎖就整個 ctl 不執行、不 kill），再 kill；中途被殺時 once 項等槽空了才起（busy 會記進 skipped）。

### P2-08 「starttime 讀不到」記成「活，但 unsure」

- 5.4 的「不知道 → 當活」在程式裡是 `state: live` 加 `unsure` 欄（說明原因），不另開一個狀態：tock 照樣對它寫 tock.json、列進 `alive`，tick 不起、不判 lost。真正的「不知道」（birth.json／exit.json／pid.json 讀不到）是 `unknown`：不起、不判 lost、不刪槽、不寫 tock.json，記進 `errors`。
- daemon 的 status `live` 把 `unknown` 也列進去（保守）。

### P2-09 推定不了時 tick／tock 退出碼 3

- round.json 讀不到、兩份回合數都不能用、`.aos/tasks/` 列不出來、last-round.json 讀不到（tock）：什麼都不寫，stdout 印 `{"unknown": "..."}`、退出碼 3。daemon 把 3 當「不知道」走 2.1 第 1 步的退避。
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

- **P2-15 測試鉤子留在程式裡**：環境變數 `AOS7_TEST_CRASH=<點>`（在 tick 的 `after-launch`、`after-birth`、`after-popen`、`before-once-delete` 自己 SIGKILL）與 `AOS7_TEST_HANG=<點>`（`tick-opened`、`tock-summary` 卡住），用來測「各點 kill -9」與「卡住的 tick／tock」。tick 起任務時把它們從任務環境拿掉。
- **P2-16 kernel／agent 沒做**：照這次的範圍只做基礎設施。第 8 節（kernel 用量累計）沒有程式；第 9 節的歷史 module 有參考實作（`modules/history.py`），另有最小示範任務 `modules/counter.py`（讀同槽上一次的 state、收 tock.json）。
- **P2-17 寫入紀錄（`AOS7_AUDIT`）照搬沒測**：`lib/audit_site/`、`aos7_audit.py` 原樣複製自 proto7-1，`writes.jsonl` 換 run 時清（5.1）。這次沒有對它寫測試。
- **P2-18 max_live 要是正整數**：0 不合（整項跳過）；要停用用 `enabled: false`。
