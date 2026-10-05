364 項測試已有扎實的正常路徑與故障恢復覆蓋，但目前綠燈仍會漏掉「沒有真的崩潰、故障打錯階段、中斷當下不變條件不成立」等問題；應先補強測試判定與同步，再以獨立程序平行化。

# proto7-2 測試套件唯讀審查報告

## 範圍與證據界線

審查日期：2026-10-05。全程未建立或修改檔案、未 commit／push，也未執行會寫檔的測試或產品程式。

採六條平行審查線，並對關鍵發現交叉反證。除讀檔、搜尋外，只執行標準庫 AST 分析及不碰檔案、不送真訊號的記憶體替身驗證。

以下路徑均相對 `/home/guanyu/projs/aos/proto7-2/`。

| 範圍 | 測試檔 | 靜態案例數 |
|---|---:|---:|
| `tests/core/` | 14 | 220 |
| `modules/*/tests/`、`modules/tests/` | 8 | 52 |
| `packs/step/tests/` | 1 | 26 |
| `packs/budget/tests/` | 2 | 37 |
| `packs/adapt/tests/` | 2 | 29 |
| **合計** | **27** | **364** |

計數為 273 個明寫方法＋91 個 `gen()` 產生的方法，與 `README.md:48` 相符；**這不是本輪執行結果**。

「缺覆蓋」指 `tests/run_all.py:24`、`:51` 收錄的固定套件。`notes/play/` 中部分歷史探針已驗過相關情境，但不會隨目前套件執行。

本報告區分：

- **已確認的測試缺口**：由斷言及控制流即可證明。
- **靜態 flaky 風險**：存在合法排程反例，未量測發生率。
- **靜態契約差異**：實作路徑與文字不一致，未在本輪動態重現。

下文的「錯誤仍可過」指能滿足所述案例的現有斷言；未實際修改程式執行突變測試，也不擴大宣稱整套一定通過。

## 一、會漏掉錯誤的斷言與故障測試

### T8-01｜高｜runner-before-exit 沒有證明 runner 真的被殺

**證據：**`tests/core/test_matrix_once.py:33`、`:46`、`:62`、`:74`；`lib/aos7_run.py:91`。

runner crash 分支只檢查 **tick 退出碼為 0**。once 最後要求執行一次、結束紀錄一筆；正常完成的 `code:0` 也符合。keep 最後要求 LIVE，也未要求確實換成新 run。

只移除 `runner-before-exit` 的 SIGKILL，保留正常執行，就可能滿足這些斷言。

**補法：**恢復前確認指定 runner 的 PID／starttime 已死亡，並確認任務完成、`pid.json` 存在、`exit.json` 尚不存在；恢復後精確驗該 run 的 lost 紀錄及新 run。`runner-before-pid` 在其他矩陣另有前置驗證，不宜一併說成全無覆蓋。

### T8-02｜高｜step 三個 crash 點只驗 marker 消失

**證據：**`packs/step/tests/test_step.py:389`、`:402`；`packs/step/aos7_step.py:380`。

鉤子先 unlink `.step-crash`，再 SIGKILL。測試只驗最終完成、每步一次、visits／tries，以及 marker 不在。

**明確反例：**刪除 `aos7_step.py:382` 的 `os.kill()`，保留 unlink；正常流程仍滿足全部末態斷言。

**補法：**每個點先驗舊 interpreter run 的退出訊號，再恢復；同時驗中斷形狀：

- after-intent：意圖已持久化、尚未加項。
- after-add：表上已有相符 attempt。
- before-accept：結果已存在，尚未更新 accepted／pc。

### T8-03｜高｜subd 用「至少死一個」驗「全部收完」

**證據：**`modules/subd/tests/test_subd_recover.py:150`、`:156`、`:160`、`:169`。

```python
assertEqual(all(pid_alive(x) for x in old), False)
```

三個舊程序的存活狀態為 `[False, True, True]` 時也會通過。第三代啟動後又會補收，因此後面的「全部 old 消失」仍可能成立。

**漏掉的是中斷當下的保證：**第二代已走到 `subd-reaped`／`subd-before-argv`，卻仍有前代活著；第三代的正常補收掩蓋了它。

**補法：**False 分支直接要求 `alive_old == []`，並以 PID＋starttime 判身分。保留第三代恢復後的全空斷言。

### T8-04｜高｜budget 帳本 crash 核帳不在崩潰快照上

**證據：**`packs/budget/tests/test_budget_ledger.py:96`、`:174`、`:180`；`packs/budget/spec.md:50`。

`restart_ledger()` 確認舊帳被殺後，立即啟動新帳；接著才 `audit()`。所以「被殺的那一刻帳也守恆」的註解，比實際證據強。核帳可能讀到恢復前、恢復中或恢復後。

四個持久點也沒有精確區分提交前後。把 after-commit 鉤子搬到提交前，仍可能被殺、重啟成功，末態相同。

**補法：**先等死、讀取固定快照，再重啟。以現有額度 3、amount 1 的 fixture，應驗：

| 中斷點 | seq | available／inflight／used | K |
|---|---:|---|---|
| reserve-before-commit | 0 | 3／0／0 | 不存在 |
| reserve-after-commit | 1 | 2／1／0 | reserved |
| settle-before-commit | 1 | 2／1／0 | reserved；gateway 已 done |
| settle-after-commit | 2 | 2／0／1 | settled |

另驗 inbox／回條所處階段。`clock_hw` 可獨立提交，不應要求整份帳逐位元不變。wrapper crash 案 `:198` 確實先 audit 再重跑，不受此批評。

### T8-05｜高｜last-round 故障打在寫前，沒有測到寫後讀回

**證據：**`tests/core/test_matrix_faults.py:269`；`tests/core/test_matrix_misc.py:80`；`lib/aos7_tock.py:54`、`:98`；`spec.md:257`。

常駐的 `open:*/.aos/last-round.json:*` 故障在 tock 第一次讀舊總結時就觸發，永遠到不了提交後的整份讀回驗證。另一排序測試只觀察 `write_json()` 先後。

刪掉寫後讀回，或弱化成只比 round，這兩類測試仍無法辨識。

**補法：**第一次讀正常，只在提交後讀回注入 EIO／BAD／同 round 但 ended 不同。驗退出 3、round 保持 open、未通知、未標 seen_round、未刪槽；解除後再驗重播收尾。

### T8-06｜高｜tock 重播沒有 ENDED once 的收尾案例

**證據：**`tests/core/test_matrix_docs.py:121`；`tests/core/test_matrix_a3.py:295`；`tests/core/test_daemon.py:370`；`lib/aos7_tock.py:172`；`spec.md:205`、`:262`。

現有重播案例主要是空 node 或 LIVE keep，沒有已結束 once 進入重播的 seen_round／刪槽分支。`tock-after-finish` hook 亦未被正式測試使用。

移除 `_replayed()` 的 `_finish()` 呼叫，空／活槽重播仍可成立，卻漏掉已結束槽的收尾。

**補法：**完成 once 後，在 summary、seen_round 提交途中、finish 後分別中斷；驗總結不變、結束不重報、當回合槽仍在、下一個 tock 才刪。

### T8-07｜中｜Fault.check 只證明 op 命中，未證明每條規則命中

**證據：**`tests/_matrix.py:48`、`:93`、`:99`；`modules/diag/tests/test_diag.py:67`。

規則先被壓成 op 集合。兩條 `proc-stat` 分別指向 task 與 runner，只要任一條命中，就滿足 helper。

本輪以抽出的真實 `Fault` AST、跳過會建檔的 constructor，作純記憶體驗證：

```text
規則：open:/root-a/birth.json:EIO;open:/root-a/pid.json:ESTALE
紀錄：只有 birth.json 的 EIO
Fault.check：PASS
```

helper 的 docstring 本來就只承諾 op 級檢查；問題是不能把這個結果擴大解讀為路徑、errno、程序、階段全有覆蓋。

**補法：**以規則 ID，或 `(op, path, errno, phase)` 驗命中。多次命令共用 hit 檔時，每次檢查自己的增量。

### T8-08｜高｜once_retry 的「非 true 忽略」沒有候選資料

**證據：**`modules/once_retry/tests/test_once_retry.py:64`、`:72`；`modules/once_retry/retry_lost.py:21`、`:29`；README `:26`。

案例只 tick，尚未產生 lost 的 `last-round.json`，便要求 `candidates()==[]`。根本沒有走到 `x.retry_lost is True` 的判斷。

把精確 `is True` 改成一般 truthy，`"yes"` 仍未有機會成為候選。

**補法：**建立相同的有效 lost＋never_started＋同 run once birth，僅替換 `True／False／"yes"／1／None`，精確驗候選與 tasks 是否改變。

### T8-09｜高｜控制洪水測試可以在預算完全失效時通過

**證據：**`tests/core/test_daemon.py:293`、`:299`、`:302`；`spec.md:72`。

若 daemon 一次清完 3000 件，再第一次寫 status，只要在 10 秒內完成，測試便會接著在**空 queue** 上觀察 status 前進，然後通過。

它沒有證明「洪水仍存在時」status 能前進，也沒有驗 200 件／0.05 秒上限。

**補法：**以可控時鐘及處理 spy，直接驗單次 `handle_ctl()` 的件數、時間上限與排序；整合案例則確認 backlog 尚非空時，status／node 已前進。

### T8-10｜高｜budget 競爭程序失敗可被事後補跑掩蓋

**證據：**`packs/budget/tests/test_budget_ledger.py:245`、`:263`、`:265`。

20 個 call／cancel 程序只 `wait()`，沒有驗退出碼、JSON 或 stderr；接著逐 K 重跑 call，再驗最後結果。

cancel 在競爭時 traceback，或原始命令失敗但後續重跑修好，都可能留下合格末態。連續 Popen 也不能證明同 K 曾在關鍵區段重疊。

**補法：**先保存並驗每個競爭命令的合法 rc／JSON／無 traceback，再單獨驗恢復。用障礙分別安排 run 先持鎖、cancel 先持鎖；隨機壓力案保留作補充。

### T8-11｜高｜獨立核帳缺少完整身分與證據的獨立驗算

**證據：**`packs/budget/tests/budgetcase.py:108`、`:135`、`:143`；`packs/budget/spec.md:39`、`:41`。

目前有效驗到 log 重放、餘額守恆及部分後端關係，但：

- ops→reserve log 是單向檢查，沒有普遍驗集合相等。
- 未完整核對 key、digest、amount、reserve／settle seq。
- evidence 沒有獨立重算入口回條 SHA256。

其他個案有 `len(ops)` 補強，也有重播整份 settle 相等；缺的是跨快照通用的一致性與正確性 oracle。固定寫錯 hash，仍可能滿足「兩次相等」。

**補法：**獨立重建每個 K 的連接關係與雜湊；另用故意缺 ops、錯 seq、錯 evidence 的小型資料 fixture，確認 audit 自己會拒絕。

### T8-12｜高｜budget sampler 丟掉非法快照，空樣本也不失敗

**證據：**`packs/budget/tests/test_budget_ledger.py:250`、`:253`、`:279`；`lib/aos7_fs.py:113`；`packs/budget/spec.md:50`。

sampler 用寬鬆 `read_json()`，只保存 dict。半份 JSON、缺檔或讀取錯誤被丟棄；最後也未要求有樣本或看過 reserved 中間態。

因此非原子發布產生的壞讀，可能恰好被測試忽略。

**補法：**保留錯誤分類、將採樣執行緒錯誤傳回主測試，驗 sampler 已 ready，並以提交障礙確保觀察指定中間態。即使修正，5ms 輪詢仍只能證明抽樣結果，不能宣稱所有轉移都已觀察。

### T8-13｜高｜diag 唯讀測試避開了最危險的 SUSPECT 分支

**證據：**`modules/diag/tests/test_diag.py:76`、`:84`、`:89`；`modules/diag/aos7-diag:56`；`lib/aos7_task.py:118`、`:135`、`:144`；diag README `:19`。

fixture 只有 LIVE 與 UNKNOWN。若把 `judge` 誤換成 `judge_resolved`，這些案例仍可原樣返回；真正 SUSPECT 卻會進入掃描、kill、寫 exit。

檔案快照亦無法驗出發訊號或空目錄變動。

**補法：**加入 SUSPECT fixture，禁止 resolve／env_procs／kill／write 的呼叫，並保留完整前後快照。

### T8-14｜中｜history 可過度刪除；gap 只靠偶然漏取樣

**證據：**`modules/tests/test_modules_history.py:38`、`:41`、`:61`、`:65`；`modules/history.py:53`、`:73`；`modules/README.md:28`、`:30`。

保留上限案例只驗筆數 ≤2、最後事件 e5；只留一筆也過，node 歷史全空也符合其上限斷言。

gap 案只在「若有 gap」時展開，未刻意跳號。正常排程沒漏取樣時，完全刪掉 gap 產生邏輯仍可能通過。

**補法：**精確驗事件 `[e4,e5]`、node rounds `[4,5]`；直接送 round 1→4，要求 gap `[2,3]`，再測重複與倒退不追加。

### T8-15｜中｜kill 重播拒絕斷言有 `all([])` 空集合漏洞

**證據：**`tests/core/test_matrix_a3.py:113`、`:117`。

後續紀錄先篩掉 `k#1`，再對剩下的紀錄做 `all(not ok)`，沒有要求至少一筆。只留下初次成功紀錄，後續漏回條／漏 ctl 紀錄，也能通過這個斷言。

**補法：**要求至少一筆針對目前 `k#2` 的拒絕紀錄，並檢查最終 ctl-done。現有副作用與 PID 斷言仍有效保護「新 run 沒被殺」。

### T8-16｜中｜adapt 長跑的觀察範圍比「逐回合、檔數不長」窄

**證據：**`packs/adapt/tests/test_adapt_flow.py:63`、`:70`、`:403`、`:407`、`:410`、`:412`。

collector 只留下嚴格增號版本，同回合改寫、倒退版本及未取到的短暫錯誤不會進入斷言。檔數則只列一層且排除所有 dotfile；每圈新增 `.leak-<round>` 也看不到。

**補法：**

- daemon 長跑明確定位為跨 300 回合範圍的抽樣。
- 精確轉移以受控回合＋每圈 acknowledgement 驗證。
- 寫者穩定後，遞迴比較包含隱藏檔的集合。

最新值協定允許漏取樣，**不應把整合案改成強制收到 300 份連續通知**。

### T8-17｜高｜共用 reap 可能先移除追蹤，卻留下同群組程序

**證據：**`tests/_proc.py:20`、`:30`、`:33`、`:37`；`tests/base.py:55`、`:81`、`:98`、`:206`。

漏收窗口是：leader 在入口仍活著，TERM 後於 grace 內退出，但同群組 child 忽略 TERM。`wait()` 成功後直接關 pipe，不再確認整群；該項已從 `_live` 移除。

本輪抽出真實函式，用 FakeP／FakeOS 驗到：

```text
事件：[killpg(PGID, SIGTERM), wait(3.0)]
剩餘追蹤：0
沒有後續群組 KILL／存活檢查
```

入口就已退出的 leader 反而會走 `:37` 的 KILL，兩種情況須區分。

後續 root 掃描也非完整保底：正常 daemon／tick／tock 未必帶 `AOS7_ROOT`；leader 被回收後 `_leads_group()` 又可能回 False。

**補法：**加入 leader 快退、child 忽略 TERM 的 helper 自測；確認自有群組清空才移除追蹤。一般 tick 起出的 runner 亦未進 `_live`，Ctrl-C 保底應另有 root／程序登記，不能只依正常 unittest cleanup。

## 二、時間與機器負載造成的 flaky 風險

以下均有具體排程反例；本輪未實跑，沒有宣稱已觀察到失敗率。

| 編號 | 證據與風險 | 改法 |
|---|---|---|
| **T8-18** | **metadata 不等於任務 ready。** `tests/core/test_tick_tock.py:30` 只等 pid，第一個 tock 尚未被 waiter 消費便送第二個；任務合法只看到 round 2，測試卻等它收到兩次。`modules/control/tests/test_control.py:38`、`:268` 也只等 pid 就 kill，shell 的第一筆 echo 未必完成。`tests/base.py:196` 只驗 pid.json。 | 發下一次通知前等 `seen.jsonl` acknowledgement；kill 前等任務副作用 ready；最後等新 run 寫出副作用再比較。另測合法漏通知。 |
| **T8-19** | **sleep 猜生命週期，以及 PID 數誤當 run 數。** `tests/core/test_tick_tock.py:300` 用 sleep 0.3 假設第一次 tock 時仍活；負載高時可能早已正常報結束。`tests/_matrix.py:144` 的短首輪 shell 會起 touch／sleep 子程序，`:208` 卻把多個 PID 判成雙開。 | 用 ready／release 閘門控制「第一次 tock 後才結束」；先验 alive、未報 ended。短首輪改單一程序 workload；雙開按任務實例／run 重疊判定。 |
| **T8-20** | **subd 的進度推測。** ownership `:126` 只等 wrapper pid 就要求 children 非空；`:93` 等子 daemon 死便人工重啟，可能搶在 wrapper 提交 stopped.json 前覆寫 status。recover `:78`、`:97` 又要求父 kill 後三個任務全活，測試程序被延遲時，daemon 可能已合法收掉一個。 | 等 owner／child ready；人工重啟前等 stop 提交及 wrapper terminal。父 kill 後記錄實際殘留集合，驗前提與後續回收分開；需要精確窗口時用障礙。 |
| **T8-21** | **adapt 的輸入與排程假設不成立。** flow `:119`、`:132`、`:146` 未固定 feed，sensor `examples/temp/sensor.py:22` 在來源 round≡100 mod200 產生 800，依法應 within_error_band／unknown，但 flow `:113` 要求全 ok。`:124` 的每對來源回合差 >1 也不是 interval 設定能保證。`bad_phase:243` 則要求輪詢器完整看到 held 1、2、unknown，合法漏讀會假紅。 | 流速案固定 feed=790／801；skipped、held 邊界以手動回合驗。daemon 案驗實際觀察到的版本關係與最終進展。 |
| **T8-22** | **budget 推鐘前未確認消費者進度。** ledger `:458` 每輪 sleep 0.3，假設帳首次於 c=6 看見孤兒；若首次看到的是7，最後固定9便永遠不到三回合。`:349` 等 error.json 後推鐘，也不保證 caller 已記住起始鐘5。另 `:153` 在帳活著時先刪目錄、kill 後未 wait 即重建。 | 每次推鐘前取得掃描／caller 起始鐘 acknowledgement；邊界算術直接驅動函式。清理改 kill→wait→刪→重建。 |
| **T8-23** | **故障啟停本身有競態。** daemon `test_daemon.py:383` chmod 的 round inode 可被正常 rename 換掉。`test_matrix_faults.py:407` 刪規則後立刻取 hits，但 `_hooks.py:31` 已讀入的規則仍可於 `:41` 追加最後一筆。adapt flow `:289` 在活寫者上 unlink→mkdir，也可能撞上重新發布。 | 用明確注入階段與停用 acknowledgement；修改 fixture 前先讓寫者停在可證明的位置。unlink 規則檔不等於所有舊注入已離開。 |
| **T8-24** | **權限與硬時間上限的環境相依。** `test_once_threestate.py:93` 的 chmod 000 案沒有 root skip，下面 `:109` 卻整類 skip，連純邏輯案也一起跳過。early_tock `test_daemon.py:165` 把3秒當完成上限；wake／resume 的短上限也會隨新增 workers 變脆弱。 | 邏輯 U 分支採可驗命中的注入，真權限案單獨標記。時間語意用可控時鐘驗；少量真時間 smoke 保留寬裕卡死上限，另報延遲，不以放大所有 timeout 掩蓋競態。 |

pause 還有共同問題：daemon 已 `phase=paused`，不代表任務已處理完最後一次 tock。step `test_step.py:316`、adapt `test_adapt_flow.py:306`、budget `test_budget_step.py:142` 的 0.3 秒都應換成該任務的最後回合 acknowledgement，再開始比較凍結狀態。

## 三、規格保證尚缺的固定回歸

這裡的「缺」針對指定條文／分支；同一功能可能已有其他有效測試。

### T8-25｜核心啟動與世代隔離缺直接回歸

**條文：**`spec.md:85`、`:86`。  
**現況：**`tests/core/test_daemon.py:68`、`:396`、`:415` 有正常重開、gen 遞增、舊 holder 接管，沒有涵蓋下列契約。

| 缺的情境 | 最小測試設計 |
|---|---|
| nodes／paused／gen 啟動時 U／BAD | 逐檔注入 EIO、非一般檔、壞 JSON；驗 rc3、既有三檔未覆寫、gen 未增加、node 未前進。 |
| action 等鎖期間世代改變 | 先持 action.lock，啟動 GEN=5 的 tick／tock 等鎖，改成6再釋放；驗 stale，round／birth／summary／owner 不變。 |
| gen 不可讀及同世代序列化 | 不可讀應 rc3；同世代兩 action 必須序列化，鎖 inode 不被換掉。 |

對应實作：`lib/aos7_fs.py:274`。移除拿鎖後的 stale 比對，現有「正常重開」案例無法直接攔住。

### T8-26｜兩個契約差異已被弱邊界案例放過

| 條文、證據 | 靜態結果與補測 |
|---|---|
| **壞控制檔保留原物**：`spec.md:70`；測試 `test_daemon.py:314`、`:321`；實作 `aos7_daemon.py:334`、`:359`、`:374`。 | BAD JSON 沒進 `.bad` 分支，原文最後被刪；測試只檢查 FIFO 的 `.bad`。補驗 malformed JSON 的原 bytes 保留，以及其他非一般檔的原物型別。 |
| **名稱只含允許字元**：`spec.md:135`；測試 `test_tick_tock.py:81`；實作 `aos7_task.py:16`、`aos7_tick.py:69`。 | `$` 結尾 regex 搭 `.match()` 接受 `"job\n"`。本輪以 AST 取 regex、標準庫 re 在記憶體確認。補 LF／CRLF／NUL／非 ASCII 與正常項混合表，驗不起、不建槽、其他項照起。 |

以上是靜態可達的實作／契約差異，未動態執行產品。

### T8-27｜核心其餘明文保證缺少辨識力案例

| 條文 | 最近的既有測試與缺口 | 缺的測試設計 |
|---|---|---|
| timeline 預設、數值不合需記錄，`spec.md:29` | `test_errors.py:88` 只驗 FIFO 的部分回傳值。 | 缺檔、0、負數、bool、NaN／Infinity、字串；驗 interval、early、timeout、診斷及修復後生效。 |
| 退避0.5起、封頂8秒，`:39` | 未見退避序列／飽和直接測試；`aos7_daemon_timeline.py:137` 先算指數再 min。 | 假時鐘驗0.5→1→2→4→8及很大 recover_fails；標準庫純運算已確認大指數轉浮點可 OverflowError，無須實等數小時。 |
| tick／tock 失敗不扣 rounds，`:46` | `test_errors.py:103` 主要是尚未開回合就失敗。 | tick 已開 round 後失敗、tock 失敗再恢復；完整關一回合只扣一次。 |
| 表鎖及 once 按 launch 刪，`:157`、`:160`、`:165` | G1 工具拒寫已有測試，並非 tick 的鎖競爭測試。 | 真正持鎖逾時；合作 writer 插入／重排後，tick 不丟更新、不刪錯 once。 |
| tasks_rev 是原文 SHA1前12碼，`:161` | `test_tick_tock.py:22`、`:28` 只驗非空及兩處相同。 | 對 fixture 原始 bytes 獨立算 hash；固定回 `"x"` 必須失敗。 |
| mount_allow／realpath／回條失敗，`:185`、`:186` | `test_ctl.py:182`、`test_matrix_faults.py:315` 有成功及讀 U。 | 前綴邊界、相鄰名稱不誤中、realpath 越界；receipt 寫失敗留請求、重試不破坏 birth。 |
| 起不來 exit127、無效 fd 不回退，`:218` | `test_tick_tock.py:314` 是 inst 成功路徑。 | executable 不存在、Popen失敗、out.log不可開；無效 fd 驗 rc2且原字串路徑未被寫入。 |
| never_started 的限制，`:233` | `test_exits.py:34` 有正例及曾啟動反例。 | 無 runner／pid 但 out 非空；out stat EIO；均不得帶 never_started。 |
| 六個環境欄、cwd、PATH、argv 展開，`:237` | `test_tick_tock.py:30` 名稱有 env，實際主要驗通知。 | 真任務回報完整環境、cwd、PATH前綴及展開後 argv。 |
| 控制例外不重做、U等待，`:70`、`:71`、`:243` | `test_daemon.py:324` 驗回條失敗但請求刪得掉。 | 效果已生效、回條失敗、刪請求也失敗時，每圈不得重做；U 修復後同請求只執行一次。 |

### T8-28｜tools：三個重要 API 分支未被核心間接測試補到

**證據：**`modules/tools/README.md:21`、`:37`、`:44`、`:47`；`modules/tools/tests/test_tools_ctl.py:61`。

| 保證 | 缺的測試 |
|---|---|
| kill 未給 run 時讀當前 birth，失敗不寫 | 現有案明寫 `--run 1`。用 birth run7、不給參數，驗 ctl.run7；缺檔／BAD／FIFO／EIO 時驗未產生或覆蓋 ctl。實作 `aos7_ctl.py:103`。 |
| wait_tock 忽略其他 run、CLI timeout空輸出 | 核心 waiter 只驗正常通知；stale-infra 案放的是錯 run **exit**。以讀取序列驗舊 run 的大 round 不喚醒；CLI驗成功、timeout rc1且stdout空。實作 `aos7_taskside.py:45`、`bin/aos7-wait-tock:29`。 |
| JSONL 壞行隔離 | 正式案例未故意混半個UTF-8、壞JSON、合法尾行。獨立驗好行保留、bad計數正確，不能用整檔decode。實作 `aos7_taskside.py:102`。 |

resolver 最長完整路徑前綴、request 的 refused 不重送亦缺專門 oracle；契約在 tools README `:45`、`:46`。

### T8-29｜control：掛載目標、reload 合併與不同 id 的換 run 競態

**證據：**`modules/control/README.md:20`、`:23`、`:29`、`:30`、`:32`；測試 `test_control.py:57`、`:107`、`:180`。

- restart 掛載只驗有 `at`，沒有驗 `to`／symlink realpath；目標錯改成 `"."` 仍可能過。
- reload 成功案只改 argv，缺宣告覆蓋同名 dyn、保留異名 dyn、x／inst／diff 與第二次 reload 邊界。
- 並行案 A/B 都用同 id；刪掉「run已換」保護，仍被同 id 條件遮住。應用不同 id 的 B 完成換 run，再恢復 A，要求不加 once、不送舊 kill。
- 缺表／birth U、鎖逾時時不 kill，以及正常換 run 後同 id 可成為新意圖的期限案例。

### T8-30｜once_retry：重派資格、pending 保留與去重

**條文：**`modules/once_retry/README.md:20`、`:21`、`:28`。  
**證據：**`test_once_retry.py:31`、`:37`、`:82`；`retry_lost.py:24`、`:28`、`:44`、`:53`、`:62`。

真正 lost fixture 都偏向 after-birth 的 never_started，沒有逐一否定：

- 曾啟動的 lost、正常 ended。
- birth 已換 run、keep birth、槽／birth 消失。
- 第一次表 I/O／鎖失敗後，pending 必須留下。
- summary 已被覆寫，仍能由 pending 補排。
- 同 summary 連掃且中間不 tick，只加一筆。

pending 等待期間 birth 換 run 的預期也應明定：目前保留的是舊 birth，重試時未重讀。這是需建立契約與回歸的交叉情境，不在本報告代替作者決策。

### T8-31｜audit：兩個 open/write 案例不足以保護全部事件規則

**條文：**`modules/audit/README.md:20`、`:28`。  
**證據：**`test_audit_wrapper.py:14`、`:35`；`audit_site/sitecustomize.py:97`、`:135`。

缺 rename、remove、mkdir、truncate、symlink、link；缺合法 mounted target、執行中加掛、透過 symlink 越入其他 node；缺 log 寫失敗仍不阻擋任務，以及換 run 清紀錄。

**設計：**每種事件同時驗真實副作用與對應紀錄；加入允許／不允許路徑對照。JSONL 壞行統計共用 T8-28 fixture，避免重複慢整合測試。

### T8-32｜subd：位置與完整回收範圍尚有空缺

**條文：**`modules/subd/README.md:20`、`:23`、`:40`、`:42`、`:47`、`:60`、`:63`、`:67`。

| 缺口與證據 | 建議設計 |
|---|---|
| 父 nodes schema：`aos7-subd:62` 把部分合法JSON但錯schema的值當空；直接 fixture `test_subd_recover.py:32` 常未建父 registry。 | EIO、null、list、nodes非物件逐案驗不起 argv。缺檔 N 的語意先與 README 對齊。 |
| 子根 alias：`:58` 用realpath，但 `:66` 對父registry用字面前綴；ownership `:107` 只有字面一致案例。 | 父登記 `a/reg/n`，另建 `a/alias→a/reg`，以alias認領必須拒絕且不收父任務。這是靜態反例，未實跑。 |
| 回收 oracle 主要只記 task PID：recover `:42`、`:132`。 | 分別保留可辨識舊 launcher、卡住 runner、nested 任務；新代可見時三類皆消失，sibling／ancestor仍活。 |
| daemon.lock 與掃描失敗邊界 | 持鎖人工daemon使wrapper拒起；recovery期間別的daemon不能起；proc-stat／environ／cmdline及receipt U不得錯收、錯起；五輪仍不乾淨拒起。 |
| SIGTERM 起前保證及 stopped 鎖內檢查：實作 `:227`、`:242`、`:293`、`:295` | 分別在取得鎖前後、檢查got_term與Popen間安排障礙；SIGKILL 的 before-argv案不能替代SIGTERM測試。 |
| stop內容與退出碼 | 比完整 `{by,why,at}`，人工重開前後比完整owner／guard；驗argv自訂退出碼及signal→128+N。 |

### T8-33｜step：安全補派、結果驗證、耐性與重送額度

| 條文 | 現況證據與缺的測試 |
|---|---|
| 舊 intent 不可補派，`packs/step/spec.md:80` | `test_step.py:389` 都立即恢復。補 intent age1／2 邊界；停直譯器跨GC再恢復，無證據應unknown，不能多派。 |
| 結果的missing、hash、不覆寫、識別，`:70`、`:71` | `test_step.py:272` 只驗run及artifacts有名稱。补 code0但缺expect、獨立SHA256、預存結果拒寫且子命令不執行、識別欄逐一不符不前進。實作 `aos7_step_result.py:28`、`:59`、`:69`，`aos7_step.py:530`。 |
| run timeout與late result，`:77`、`:83` | 現行耐性案主要是wait，kill主要是checker。以閘門run測unknown／fail／kill；驗kill精確帶run，halt後晚結果保留，resume採用原attempt。 |
| max_resends，`:84` | 0只有checker，預設案第一次重送便成功。持續unknown，驗0／省略／2對應總嘗試1／2／3；人手resend後額度重設。 |
| frame rev與鎖，`:54`、`:59`、`:79` | 舊rev寫回須拒絕且保留新frame；表鎖／真U時撤pending、不破壞表、下次attempt增加。 |
| receipt及close | unknown後receipt成立應先採用、不重送；running／halted close拒絕，清理失敗不可宣稱完成。參見 `aos7_step.py:569`、`:689`。 |

歷史 `notes/play/2026-10-04-astra-6-infra-evidence/regression/step/probe_step.py:41`、`:61` 已有部分延遲意圖與timeout情境，適合轉成固定回歸。

### T8-34｜adapt：提交窗口、獨立值驗證及狀態交叉

**條文：**`packs/adapt/spec.md:42`、`:64`、`:75`、`:88`、`:103`。

- **state→register 窗口未測。** `test_adapt_flow.py:316` 等完整發布後才殺；交換 `aos7_adapt.py:460` 的寫入順序仍可能過。補順序spy、第一寫失敗第二檔不動、第二寫失敗後重播不重加skipped，以及兩寫之間的真SIGKILL。
- **basis沒有獨立SHA256 oracle。** flow `:115` 用產品trace算值，`:163` 等處只比hash相等關係。應保存fixture來源，獨立canonicalize／hash；所有非ok共同驗 `value is None`、`err is None`。
- **threshold端點矩陣不足。** unit `:91`、`:101` 沒完整涵蓋gt／ge／lt／le與端點。用可精確二進位表示的0.5誤差、獨立真值表測4×5點。
- **宣告U後的耐性交叉未測。** `aos7_adapt.py:442` 發布decl_bad unknown卻不更新frame.prev_state；下一圈原宣告恢復但source仍U，`:332` 可能依舊ok框架重新撐成ok。spec `:75` 要求上一份暫存器為ok。補 `ok→宣告讀取U→宣告恢復但source U→健康`，不必藉工作中改鏈這種誤用製造。
- **數值域不足。** rounding unit `:110` 只用小值、round0；補round0～12、不同量級、有限輸入乘法溢位與大整數，要求有限結果或可恢復診斷。
- **本包 completed_tock 邊界。** spec `:48`、實作 `:231`：同round10，closed→10、open→9，缺檔／BAD／U→未知；unit直接傳ct不能覆蓋讀鐘函式。

### T8-35｜budget：可信證據、非單位金額及共同I/O邊界

| 條文 | 缺的測試設計與證據 |
|---|---|
| 帳自己讀入口、不信請求人報量，`packs/budget/spec.md:49`、README `:32` | 現有CLI settle只送key。直接送偽造used／outcome／evidence，與真gateway相反，帳仍按入口證據結算。 |
| amount運算，spec `:48`、`:72` | `test_budget_ledger.py:143` 的amount2只是同K衝突，不經正常算術。額度5依序預留／使用2與3，另驗拒絕退回、正好不足、0／負數。 |
| call／cancel／settle讀寫U→JSON＋rc3，`:80` | 現有fault集中backend。補payload、gateway、inbox、receipt、輸出寫入及settle命令，各自驗命中增量。 |
| payload U的現行差異 | `aos7_budget_gate.py:169` 對fact非OK直接rc2且無JSON；明確EIO也走此路。依目前§6應補測rc3；缺檔／壞輸入B另列。 |
| settled重播讀入口，`:74`、`:77` | `aos7_budget_gate.py:185` 入口U時用ledger fallback，可能成功但response為None。需明列這是否為共同故障邊界例外，並固定測試。 |
| 首次准入unknown／not_yet不落終局，`:58` | 先reserve成功，再使入口看到grant／clock U；驗不生成終局，修復後同K可成功。 |
| cancel查回原效果，`:62`、`:68` | 現有after-effect cancel偏accepted。補failed／rejected，必須查回原終局，不改成cancelled。 |
| 合法JSON但schema錯誤 | 帳與gateway缺必要欄位、錯型別、非終局證據；不得當空帳或提前結算。 |

## 四、測試入口與執行成本

### T8-36｜中｜空選集會被報成成功；逐案计時仍不完整

**證據：**`tests/run_all.py:49`、`:52`、`:53`。

不匹配任何案例的 `-k`，或存在但沒有測試的資料夾，可形成空 suite；沒有測試數下限，`wasSuccessful()` 仍為真。本輪純標準庫記憶體驗證得到：

```text
testsRun = 0
wasSuccessful = True
```

不存在的資料夾會由 discovery 拋錯，不屬於此情形。

**補法：**

- 預設要求 selected、testsRun 都大於0；刻意允許空shard才用明確選項。
- 平行時核對「分派ID集合＝回收ID集合」，驗無遺漏、無重複。
- 用 `TestResult.startTest/stopTest` 計完整逐案耗時，另分 setup、body、cleanup；subTest內的大矩陣加階段計時。

既有計時器只識別沒有額外docstring行的輸出，故只記到145案。證據：`notes/play/2026-10-04-astra-6-infra-evidence/regression/run_suites.py:19`、`summary.md:56`。

### T8-37｜加速方案與估算

**歷史基線，不是本輪量測：**

`notes/play/2026-10-04-astra-6-infra-evidence/regression/summary.md:7` 記載舊版363案三輪為 **184.170、186.646、196.273秒**。145個可辨識案例的耗時合計約 **74.48、77.21、77.21秒**，不能把其餘案例算成0。

歷史可見熱點包括：

| 案例／範圍 | 歷史觀察 |
|---|---:|
| subd recover已計到的7案合計 | 31.03～33.80秒 |
| `test_killed_before_argv` | 5.66～8.45秒 |
| `test_killed_while_reaping` | 5.69～8.42秒 |
| `test_sibling_and_current_gen_untouched` | 6.85～6.90秒 |
| `test_resume_wakes_immediately` | 4.18～4.21秒 |

來源為同目錄 `suite-1-cases.json`、`suite-2-cases.json`、`suite-3-cases.json`；計時方式見 `run_suites.py:19`。這些包含setup／cleanup，不宜直接視為產品執行時間。

#### 可平行的範圍

目前未找到固定埠、跨root固定寫檔或全機pkill導致必然衝突。每案獨立TemporaryDirectory，fault hit使用mkstemp；證據：`tests/base.py:90`、`tests/_matrix.py:67`。

適合用**全新Python interpreter的程序worker**分片：

| 工作 | 建議粒度 |
|---|---|
| core不同測試檔、各modules測試檔 | 先檔級分片 |
| adapt unit、checker／schema／純資料oracle | 獨立快速分片 |
| step／budget／adapt flow | 各自程序，依實測耗時動態派工 |
| subd recover | 先獨立重工作分片；再考慮方法級 |
| budget 20程序競爭、subd多代回收 | 限制同時跑的重工作數，避免 `/proc` 掃描與程序啟動互相放大 |

**不適合同程序thread平行。** `os.environ`、mock patch、`sys.path/sys.modules`、`_proc._live` 是共用狀態，見 `tests/base.py:23`、`:28`，`tests/_matrix.py:122`、`:132`，`tests/_proc.py:13`。也不宜從已有活程序登記的測試程序直接fork worker。

先修T8-17清理，再處理T8-18～24的同步。增加worker後仍須限制程序負載，並留意裸PID／PGID重用；`_matrix.dead_pid():150` 只保證wait當下不存在。

#### sleep與長跑的具體處理

| 位置 | 建議 | 單輪節省估計 |
|---|---|---:|
| budget孤兒回條 `test_budget_ledger.py:458`、`:464` | 用受控掃描／ack代替3×0.3＋0.2秒 | 約0.8～1.1秒 |
| step／adapt／budget pause前各0.3秒 | 等最後一圈ack | 合計約0.3～0.8秒 |
| `test_daemon.py:199` 的4秒resume案 | 從已paused的受控初始狀態開始，保留長interval驗wake，免先等完整首輪 | 約3～4秒 |
| history8筆、counter每代2通知 | gap改精確單元案；smoke保留必要通知與3代接續 | 名目約0.9秒 |
| control一般案例的19次tick／tock CLI | 保留CLI smoke，其餘可用itick／itock | 約15次interpreter啟動成本，需量測 |
| adapt300回合 | 受控tick／tock＋真task＋每圈ack | 工程估計約省3～10秒，需新版本實測 |

adapt已有可參考歷史證據：`notes/play/2026-10-04-astra-6-infra-evidence/adapt/summary.md:59` 記錄受控320回合、真task、每圈ack，耗時 **3.304秒**；腳本 `adapt/probe.py:196`。它可以作方案依據，不能當成目前測試改寫後的實測速度。

**不宜直接刪掉的等待：**

- `SLEEP=["sleep","60"]` 是活任務占位，由cleanup收掉，不是每案真等60秒。
- pause後的1～1.5秒觀察窗有驗「牆鐘走、回合耐性不走」的用途；應減少重複、搭配可控時鐘，不能只刪sleep。
- 真SIGTERM寬限與SIGKILL恢復案例應保留代表性整合測試，不以縮短產品寬限換速度。

#### 整套時間預算

以下為以約200秒基線做的工程估算，**未經平行實跑驗證**：

| 方案 | 預估總時間 | 預估節省 |
|---|---:|---:|
| 維持單程序，修固定等待及改受控長跑 | 約180～192秒 | 約8～20秒 |
| 2個程序worker，按耗時分片 | 約120～150秒 | 約50～80秒 |
| 4個程序worker，修同步並限制重工作 | 約80～120秒 | 約80～120秒 |

估算不能相加；平行收益會與等待優化重疊。200÷4＝50秒只是無競爭、完美分片的理想下界，目前沒有足夠完整計時支持這個目標。

## 五、建議落地順序

1. **先修會假綠的關鍵判定：**T8-01～08，尤其真SIGKILL、提交前後快照、tock讀回與重播收尾。
2. **修共用可信度：**T8-10～13、T8-17、T8-36；讓競爭失敗、非法快照、程序殘留、空選集能確實轉紅。
3. **換成明確握手：**T8-18～24；先讓測試在負載变化下測的是同一個情境。
4. **補契約矩陣：**優先T8-25的世代隔離、T8-28的run fencing、T8-30的重派資格，以及三個pack的持久化／結果邊界。
5. **取得完整逐案計時後開2個worker，再評估4個。**驗收同時看案例ID完整性、失敗率、清場結果與總耗時，不能只看最後退出碼。