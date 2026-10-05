# 文件與程式對齊（2026-10-05）

← [本日審查](README.md)｜素材：[spec-readability](spec-readability.md) F01～F34、[packs-use](packs-use.md) §4、§5；界線：[loop7 藍圖](../../blueprint-loop7.md) D1～D10

只改「文件說錯、程式是對的」與「有條件的保證寫成絕對」；**沒改任何 .py**。每條改前對照程式（審查時的行號已部分移位，以下行號是本次核對的 HEAD 4fdf7f4b）。

## 改了（一行一條）

- F01 diag README：last-round 的 N 只證明總結已提交 → 寫 `open: true` 讓 tock 重播收尾（`lib/aos7_tock.py:60～61` 重播分支、`:96～110` 先總結後收尾）。
- F02 diag README：pause 不等於沒人寫檔（`lib/aos7_daemon_timeline.py:183～214` 恢復 tock 排在 pause 前）。
- F04 subd README：永久拿掉子空間要 `stop --kill`、確認任務收完（`modules/tools/aos7_ctl.py:140` `--kill`）。
- F05 subd README：「控制檔 stop 一定留回條」→ 正常完成才留，並接到已存在的 A8-09 段（`lib/aos7_daemon.py` 先執行後寫回條）。
- F06（只改 README 半條）step README：結果檔在槽外，但補加仍依賴 tasks 表、birth 與保留窗口（`packs/step/aos7_step.py` 補加判斷）；spec 的「第三個 tock」推導留給使用者（見下）。
- F07 subd README：範例 argv 改 `python3 <proto7-2>/modules/subd/aos7-subd`，註明要絕對路徑、cwd 是 node（`spec.md:237`）。
- F08 tools README：`wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None)`（`modules/tools/aos7_taskside.py:30`）。
- F09 核心 spec §4.4、once_retry README：分開「runner 還沒起」與「runner 已起、沒補記」（`lib/aos7_task.py:304～328`）。
- F10 once_retry、control README：「至少一次」「不會殺了沒重起」加上條件（取樣、槽證據；核心 once 契約）。
- F11 step README：普通 `resume` 在 failed 停點也會派新 attempt；`--resend` 不先採舊結果（`packs/step/aos7_step.py:447～457`、`:629～635`、`:738～747`）。
- F12 核心 spec §1、§2.1：interval 從起 tick 前的單調時間起算（`lib/aos7_daemon_timeline.py:217～221`）。
- F13 核心 spec §2.1：tock 以 round.json 是否確知關上為準，不只看退出碼（同檔 `:250～266`）。
- F14 核心 spec §2.3：只有檔名／檔案種類不合才留 `.bad`；內容壞只回拒絕回條（`lib/aos7_daemon.py:331～360`）。
- F15 核心 spec §4 表：`each` 有空槽就起（`lib/aos7_tick.py:184～194`）。
- F16 核心 spec §6：kill 重播是針對原 run、冪等，不是只執行一次（`lib/aos7_task.py`、diag 表「刪不掉」列）。
- F17 step README：耐性起點分 wait／run，resume／新嘗試會重設（`packs/step/aos7_step.py:626`、`:649`、`:741～746`）。
- F18 step README、spec §4：hard link 發布、`ok` 要求產物可讀可雜湊（`packs/step/aos7_step_result.py:28～45`、`:69～77`）。
- F20 budget README：判定補 `not_yet`（`packs/budget/aos7_budget.py:150`）。
- F21 budget README：取消成功才按 used＝0 結算（`packs/budget/spec.md:62`）。
- F22 adapt README：「每次重算」與「重起後不重算」統一為「可重算同一版、不當新版」（`packs/adapt/spec.md` §4.3）。
- F23 adapt README：耐性只撐讀取失敗、且上一份 ok、未作廢（`packs/adapt/spec.md` §4.2 表第 3 列）。
- F24 adapt README：max_age 用來源 node、patience 用自己 node 的回合。
- F25 audit README：寫入紀錄是盡力、已涵蓋事件（`modules/audit/audit_site/sitecustomize.py:91～96`、`:148～150`）。
- F26 step README：派工窗口改指 spec §5 第 4 步。
- F27 modules README：packs/ 已有 step、budget、adapt。
- F28 budget README：`caller` → holder。
- F29 tools README：`resolver` 回解析函式（`modules/tools/aos7_taskside.py:52～74`）。
- F30 tools README：截短段是雜湊、不是無損（`modules/tools/aos7_ctl.py:47～58`）。
- F31 audit、control README：依賴欄分「核心協定／程式依賴」，補 `aos7_taskside`（`modules/audit/aos7_audit.py:11～12`、`modules/control/aos7_control.py:12`）。
- F32 step README：新增「第一次跑」，寫明範例整份放進 `<node>/jobs/<job>`、人手指令在 node 目錄、用絕對路徑呼叫（`packs/step/spec.md:5` 路徑相對 node）。
- F33 step README：啟動時先推進一圈（`packs/step/aos7_step.py:699～707`）。
- F34 核心 spec §2.2：明確 open:true 另走收尾，缺欄／型別不合／讀不到才是不知道。

## 留給使用者（沒改）

- **F03**（budget rc 3 不會觸發 step `on_unknown`）：怎麼接是 **D4**（`unknown_codes` 開關）；現行 README 第 14、55 行的 `on_unknown: resend` 說法仍會誤導，等 D4 定了跟程式一起改。
- **F19、packs-use 4.3**（budget 退出碼表：payload 失敗目前退 2、code 3 可能已結算）：藍圖 B 線把它和 A8-08（gate `:168～172` U→rc 3，要改程式）、D4 綁成一件；先改文件會跟著要改的程式打架。
- **F06 spec 半條**（step spec §5「第三個 tock」推導缺前提）：屬 R8-22／**D5**（縮窗還是改記 completed_tock），要先寫時序驗證。
- **packs-use 4.5**（budget「次數」vs `--amount` 加權）：**D6**。
- spec-readability §四 術語表、§五／§六 未驗完項：不是對齊錯誤，是新增內容／待驗，沒動。
- packs-use §5 其他卡點（quickstart 等待、目錄樹、回條位置、status 退出碼表…）：屬「補新文件」，不是「文件說錯」，本次範圍外。

## 範例（packs-use 4.1）

三包 README 各加「第一次跑」一節（完整命令、預期輸出、停止方式），已照該節在 scratchpad 臨時空間根實跑成功（nice -n 5，跑完確認沒留程序）：

- step：新增 `packs/step/examples/minimal/steps.json`（一步 run），約兩回合到 `phase: ended`、`end: ok`、`out/hello.txt`＝hello。
- budget：沿用 `examples/fakeapi/grant.json`；init → call（accepted、used 1；同 K 重跑不再扣）→ status（available 2、used 1）。README 補「`grant.budget` 必須等於資料夾名」。
- adapt：沿用 `examples/temp/`；約第 2 回合暫存器 `state: ok`。README 補鏈宣告 `src`／`src_clock` 是空間路徑、要被 mounts 蓋到。

實跑時另見、未改的：三包 README 都沒交代人手指令 cwd 要是 node（已寫進各節）；人的 shell 裡 `aos7-ctl`／`aos7-daemon` 要寫 `python3 <proto7-2>/bin/…`（專案 README 已有，各節照寫）。
