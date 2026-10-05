proto7-2 已有完整的正常流程與三態判定骨架，但本次唯讀審查確認了數項啟動、回收及中斷恢復缺陷，其中應優先修正的是「kill 過早回成功」與「舊任務尚未確認收乾淨就啟動新時間線」。

# proto7-2 程式品質與正確性審查

## 1. 範圍、方法與完成程度

依使用者要求立即收尾，以下是截至停止時的結果，**不是完整驗收報告**。

- 審查起點：`6daebe2ef8227021745def649f4e3d86a3a8038c`。
- 範圍：`proto7-2/lib/`、`bin/`、`modules/`、`packs/` 的 Python 程式，包含沒有 `.py` 副檔名的 Python 入口。
- 盤點共 **64 個 Python 檔、11,128 行**；排除測試與 examples 後為 **45 個執行／函式庫檔案**。
- 64 個檔案均完成 AST 語法解析，沒有語法錯誤。
- 六條平行審查線已通讀各自的主要實作，並針對候選缺陷進行靜態推導與純記憶體 mock。
- **沒有修改 repo、沒有 commit／push、沒有啟動實際 daemon 或排程任務，也沒有執行完整測試套件。**
- 重現程式只在記憶體中執行，沒有保存腳本檔。下文所稱「mock 確認」不代表已完成真實程序、檔案系統或 SIGKILL 整合重現。
- 收到停止指示後，未再讀取新檔或執行驗證程式。

重要程度：

| 等級 | 判準 |
|---|---|
| 高 | 可能重複執行、控制回報與實際狀態不符，或在回收未完成時繼續啟動 |
| 中 | 特定失敗或交接時序下錯判、卡住、遺失資訊或違反契約 |
| 低 | 診斷、測試可信度或維護性問題 |

既有文件明確接受的限制，例如漏取樣、手改核心生命週期檔、任務刻意脫離身分、斷電後的持久化順序，沒有直接列為新缺陷。

## 2. 已確認的發現

以下位置均相對於 `/home/guanyu/projs/aos/`。

### R8-01〔高〕runner 尚未完成啟動，kill 就可能回成功

**證據：** `proto7-2/lib/aos7_task.py:186`、`:193`、`:201`；`lib/aos7_proc.py:210`、`:230`；`lib/aos7_run.py:76`。對照 `proto7-2/spec.md:243`、`:247`。

`kill_run()` 對尚無 `pid.json` 的任務只等待一秒，之後仍呼叫排除 runner 的身分掃描。若此時只有 runner 存在、真正的任務尚未 `Popen`，掃描會回「沒有程序」，kill 因而成功，但 runner 稍後仍能啟動任務。

**觸發與驗證：** 純記憶體 mock 令槽為 LIVE、birth 已有活 runner，pid／exit 尚不存在；等待結束後得到 `(True, "no process")`，未對 runner 建立取消或禁止啟動的狀態。

**建議：** 沒有任務 pid 時，必須另外確認 runner 已結束或已確實取消啟動；無法確認就回 unknown。固定等待時間不能當作啟動交接完成的證據。

### R8-02〔高〕node 回收失敗，仍會啟動新時間線

**證據：** `proto7-2/lib/aos7_daemon.py:421`、`:434`、`:441`、`:446`；`lib/aos7_proc.py:235`。對照 `proto7-2/spec.md:94`、`:97` 及 `notes/component-contracts.md:50`。

背景 `reap()` 只把 `kill_node()` 的 `clean` 結果記入事件。`check_nodes()` 判斷能否重啟時，只看回收 thread 是否結束，沒有看是否成功。

**觸發與驗證：** 穩定運行中的 node 被搬走，同一路徑出現新資料夾；回收遭遇持續的 `/proc` 讀取失敗而回 `clean=False`。mock 確認背景工作結束後仍可建立新 Timeline。此情境不需要「起任務途中搬 node」這項已接受的誤用。

**後果：** 舊任務可能仍在，新時間線已開始執行。

**建議：** 分開記錄「回收工作已結束」與「確認收乾淨」。後者未成立時保留 missing／error 與已知程序資訊，下一圈重試。

### R8-03〔高〕unregister 寫檔失敗後，記憶體已取消登記，時間線卻繼續跑

**證據：** `proto7-2/lib/aos7_daemon.py` 的 `op_unregister()`；持久化入口 `:90`，控制例外處理 `:288`，node 檢查 `:390`。對照 `proto7-2/spec.md:62`、`:71`。

取消登記先修改記憶體 registry，再寫 `nodes.json`，後面的時間線退休動作只有寫檔成功才執行。寫入失敗使三者分裂：記憶體沒有登記、磁碟仍有登記、時間線仍運行。

**觸發與驗證：** mock 在寫 `nodes.json` 時注入 EIO；再次送 unregister 得到「沒有登記」的成功回應，但原時間線沒有 retire。

**建議：** 用候選 registry 寫檔，成功後才替換記憶體並退休時間線；或保存明確、可恢復的取消登記狀態。不能讓重送請求被記憶體中的半完成狀態短路。

### R8-04〔中〕LIVE 槽第二次讀 pid.json 失敗，会清掉已記住的 pgid

**證據：** `proto7-2/lib/aos7_daemon.py:471`、`:490`、`:492`、`:495`、`:498`。對照 `proto7-2/spec.md:18`、`:97`。

`live_of()` 已由 `judge()` 判定槽仍活著，卻重新寬鬆讀取 `pid.json`。第二次讀取失敗時，只有 `UNKNOWN` 狀態會保留旧 pgid；`LIVE`，包括带 unsure 的 LIVE，反而丟失旧記錄。

**觸發與驗證：** mock 令第一次判定為 LIVE、第二次 pid 讀取失敗，原 `_pgids[nid]` 被換成空集合。

**建議：** 優先使用判定時取得的 pid 證據；需要重讀時，必須保留三態，讀取未知就沿用舊 pgid。

### R8-05〔中〕回合已關但確認讀取暫時失敗，rounds 倒數會少扣

**證據：** `proto7-2/lib/aos7_daemon_timeline.py:184`、`:190`、`:204`、`:260`、`:266`。對照 `proto7-2/spec.md:80`。

`tock` 已成功關回合，但 daemon 隨後讀 `round.json` 得到未知，會設 `owe_done=True`。下圈若直接讀到 closed，程式跳過只在「恢復 open 回合」分支中的補扣邏輯，又開下一回合。

**觸發與驗證：** mock 中 tick／tock 都回 0；tock 後兩次 round 讀取為 U，下圈恢復 closed。`resume rounds=1` 實際完成兩回合才 pause。

**建議：** 對待結算的回合保存回合號；任何路徑確認該回合已關時，都只結算一次，再重新檢查 pause。

### R8-06〔中〕錯誤退避可能忙轉，長期失敗又會溢位

**證據：** `proto7-2/lib/aos7_daemon_timeline.py:133`、`:137`、`:139`、`:167`。對照 `proto7-2/spec.md:39`、`:47`。

有兩個同源的退避問題：

1. `backoff()` 等待 `wake` 後沒有清除事件；事件已設定時，每次 `wait()` 都立即返回，整段退避變成忙轉。
2. `min(0.5 * 2 ** n, 8)` 先計算巨大指數，再套上限；失敗計數累積後會出現 `OverflowError`。

**驗證：** 純記憶體 mock 確認 wake 保持 set；失敗計數達約 1024 次後，再計算退避可拋出浮點轉換溢位。

**建議：** 明確消費 wake；指數先限制到上限所需的範圍，再計算等待秒數。

### R8-07〔中〕fact() 在 fstat 失敗時漏關檔案描述元

**證據：** `proto7-2/lib/aos7_fs.py:94`、`:99`、`:103`、`:105`。

`os.open()` 成功後，`os.fstat()` 若失敗，fd 尚未交給 `fdopen()` 管理；例外分支直接回 U，沒有關閉 fd。

**觸發與驗證：** mock 連續四次令 open 成功、fstat 拋 EIO。結果四次均回 U，`opened=[100,101,102,103]`、`closed=[]`。

**後果：** 長期存活的 daemon 遇到反覆故障，可能累積至 EMFILE，讓更多原本正常的讀取失敗。

**建議：** 在 fd 成功交給檔案物件前，以 `finally` 保證關閉。

### R8-08〔中〕動態掛載在 symlink 建好、birth 更新前中斷，重播會拒收原請求

**證據：** `proto7-2/lib/aos7_mount.py:61`、`:122`、`:154`、`:167`。對照 `proto7-2/spec.md:14`、`:186`。

執行中加掛先建立連結，再把掛載資訊寫進 birth。若中間中斷，連結已存在，但 birth 尚無紀錄。重播再次建立連結得到 EEXIST，轉成失敗回條並刪除請求。

**觸發與驗證：** 純記憶體 mock 重現「連結存在、birth 沒有 dyn、請求被失敗回條結案」。

**建議：** 重播遇到現有連結時，核對它是否指向這次要求的目標；一致才補交 birth 與回條。不能把所有 EEXIST 都當成功，也不能一律當失敗。

### R8-09〔中〕靜態掛載失敗的紀錄，會被誤認成已成功掛載

**證據：** `proto7-2/lib/aos7_mount.py:154`、`:156`；同檔 `make()` 所產生的 `{to, error}` 紀錄。對照 `proto7-2/spec.md:185`、`:186`。

靜態掛載失敗時，birth 仍會保存目標與 error。後來送同名、同目標的合法動態請求，程式只看目標相同，就回「已經掛了」，沒有確認先前是否成功。

**觸發與驗證：** mock 中沒有實際連結，仍得到 `ok:true`，請求被刪，birth 的失敗紀錄沒有修復。

**建議：** 區分成功紀錄與失敗紀錄；失敗紀錄應允許重新嘗試，未知則保留請求。

### R8-10〔中〕runner 讀 birth 失敗時，把 exit 寫成 run:null

**證據：** `proto7-2/lib/aos7_run.py:14`、`:30`、`:61`、`:64`；`lib/aos7_task.py:61`。對照 `proto7-2/spec.md:201`、`:204`、`:218`。

`RUN[0]` 在成功讀 birth 後才設定。birth 暫時讀不到時，`fail()` 先寫出 `{run:null, code:127}`；後續核心因 run 不符而忽略這份 exit，最後把它當 lost。

**觸發與驗證：** mock 已設定合法 `AOS7_RUN=1`，只對 birth 讀取注入 EIO，仍得到 run:null；後續判定把原先的啟動失敗覆成 run 1 的 lost。

**建議：** 啟動失敗的結果也必須帶可確認的本次 run。可使用既有交接環境的 run，或在身分未能確認時保持未知；不要提交必定被核心忽略的結果。

### R8-11〔中〕is_runner() 會把一般任務的普通參數當成 runner 身分

**證據：** `proto7-2/lib/aos7_proc.py:110`、`:113`、`:141`。對照 `proto7-2/spec.md:233`、`:246`。

判定只要 cmdline 任一參數以 `aos7-run` 結尾就成立。普通任務若有這個檔名或字串參數，也會被排除於一般任務掃描之外。

**觸發與驗證：** mock 的普通 Python 任務帶參數 `"aos7-run"`，`is_runner()` 回 true。原 runner 若在 pid 交接前死亡，該任務可能被誤當成仍存活的 runner，阻止 lost 收尾。

**建議：** 核對已知 runner 的 pid／starttime，或至少確認實際執行入口與參數位置；不要搜尋任意參數的尾綴。

### R8-12〔中〕非 UTF-8 的 /proc stat 內容會漏出例外，堵住程序掃描

**證據：** `proto7-2/lib/aos7_proc.py:16`、`:21`、`:23`、`:74`、`:86`、`:235`。

stat 以文字模式、嚴格解碼讀取，但 `_read_proc()` 只接住 `OSError`。解碼失敗會漏出 `UnicodeDecodeError`，沒有轉成共用的 Unknown。

**觸發與驗證：** 以記憶體 byte stream 注入包含非 UTF-8 名稱的 stat 資料，`stat_of()`、`proc()` 與 `kill_node()` 均可漏出例外。沒有實際改動任何程序名稱。

**建議：** 以 bytes 解析 stat，只將數值欄轉成整數；至少也應把解碼失敗轉成 Unknown。無關程序的名稱不應破壞整個掃描流程。

### R8-13〔中〕step 過期 intent 直接 halt，繞過 on_unknown 策略

**證據：** `proto7-2/packs/step/aos7_step.py:493`、`:497`、`:565`、`:569`、`:677`。對照 `packs/step/spec.md:80`、`:84`。

`evidence()` 對 intent 一律回 readd，真正的期限檢查在 `add_item()`。期限已過時直接拋 `Halt("unknown")`，沒有走 `on_unknown()`，所以 receipt 或合法的自動重送策略不會執行。

**觸發與驗證：** after-intent 中斷後，超過補加窗口才恢復；即使有 receipt 或 `on_unknown: resend`，仍直接 halt。

**建議：** 補加安全性不足時，轉入統一的 unknown 決策路徑。不要讓相同的「說不清是否派過」因入口不同而套用不同策略。

### R8-14〔中〕step 表寫入暫時失敗，会重設自動重送計數

**證據：** `proto7-2/packs/step/aos7_step.py:461`、`:469`、`:513`、`:515`、`:573`。對照 `packs/step/spec.md:84`。

自動重送的次數放在 pending 裡；派送遇到 Unknown 時清掉 pending，下一圈 `new_pending()` 又把 `resends` 設成 0。

**觸發與驗證：** 設 `max_resends=1`：a1 unknown → a2 加表被拒 → a3 下一圈成功、計數為 0 → a3 再 unknown → 又自動送 a4。

**建議：** 把自動重送額度保存在 request 層，或撤銷 pending 時保留額度。表鎖／讀取故障不應重新給一份重送預算。

### R8-15〔中〕budget payload 讀取故障回退出碼 2，不符合共同 unknown 邊界

**證據：** `proto7-2/packs/budget/aos7_budget_gate.py:153`、`:166`、`:168`、`:172`。對照 `packs/budget/spec.md:80`。

payload 讀取經 `fact()` 得到 U 後，被 `_call()` 直接轉成 stderr 與退出碼 2；沒有丟例外，因此外層共同故障邊界接不到。

**觸發與驗證：** mock 對 payload 注入 EIO，得到 rc 2、stdout 空白；不是約定的 unknown JSON 與 rc 3。

**建議：** 分開處理壞輸入與讀取未知；U 應走 `pending()` 或拋 Unknown，套用同一故障邊界。

### R8-16〔中〕budget 已結算重播時，入口回條讀取故障被吞成成功

**證據：** `proto7-2/packs/budget/aos7_budget_gate.py:138`、`:185`、`:187`。對照 `packs/budget/spec.md:74`、`:77`、`:80`。

帳回 settled 後，程式讀入口終局回條；讀不到時以帳上的 outcome／used 補出結果，忽略讀取失敗，response 變成 null，仍可能退出 0。

**觸發與驗證：** mock 令帳已 settled、gateway 讀取 EIO，結果為 accepted、rc 0、`response:null`。

**建議：** 帳的結算證據與完整入口結果要分開。契約既然要求讀入口回條並回傳 response，讀取未知就應回 rc 3，不能用缺欄結果冒充完整成功。

### R8-17〔中〕history 的檔名編碼會碰撞

**證據：** `proto7-2/modules/history.py:65`、`:72`、`:76`、`:85`；合法 node 名判定 `lib/aos7_daemon.py:26`。

`nid.replace("/", "+")` 不是一對一編碼：合法 node `a/b` 與 `a+b` 都寫入 `a+b.jsonl`。另有合法 node `daemon-events`，會與 `--status` 的固定事件檔同名。

**觸發與驗證：** 同時觀測上述 node，即會寫到相同路徑；這是名稱推導本身的確定結果，不需要競爭。

**後果：** 不同來源混在同一份歷史，輪替也互相影響。

**建議：** 使用可逆且不碰撞的編碼，並分開 node 歷史與 daemon 事件的命名空間。

### R8-18〔中〕subd 恢復紀錄會逐次巢狀包入舊紀錄，最後無法序列化

**證據：** `proto7-2/modules/subd/aos7-subd:266`、`:267`。

重試恢復時，新的 recovering 紀錄再次把上一份放進 `prev`。持續失敗會形成無界巢狀結構，而不是固定大小的前代身分紀錄。

**觸發與驗證：** 按相同包裝方式在記憶體重複約 1000 次，使用同樣的 `json.dump(..., indent=1)` 寫入 `StringIO`，得到 `RecursionError`。因新的 recovering 寫入在回收前，資料長成這樣後，即使原故障解除也可能跨不過寫入步驟。

**建議：** 保存固定格式的前代身分；若上一份已是 recovering，沿用其原始前代資料，不再把整份恢復紀錄包進去。

### R8-19〔低〕step 壞型別 CLI 測試沒有真的測到檢查器

**證據：** `proto7-2/packs/step/tests/test_step.py:219`～`:224`；`packs/step/aos7_step.py:719`～`:723`；`lib/aos7_fs.py:94`～`:102`。

測試把 JSON 透過 subprocess stdin 傳入，再執行 `check /dev/stdin`。但 `fact()` 拒讀非一般檔，pipe 在進入 `check(t)` 之前就失敗。只斷言 rc 1，無法證明壞型別真的被檢查器正確處理。

**驗證：** 唯讀確認該入口回的是「不是一般檔」錯誤。另直接對 `check()` 做 444 個型別變異，沒有發現例外；因此這項是測試盲點，**不是宣稱現行 checker 已壞**。

**建議：** 單元測試直接呼叫 `check()`；CLI 整合測試使用一般檔，並斷言具體 rule／why，確保命中預期分支。

### R8-20〔低〕timeline 的部分非法設定被靜默換成預設

**證據：** `proto7-2/lib/aos7_daemon_timeline.py:59`～`:73`。對照 `proto7-2/spec.md:29`。

`interval_ms` 不合法時會設定錯誤訊息，但 `action_timeout_s` 不合法時直接換成預設；`early_tock` 非 true 的值也直接視為 false。

**觸發：** 例如把 `action_timeout_s` 寫成 0 或字串。結果使用預設值，但沒有相應設定錯誤紀錄。

**建議：** 三個設定欄位使用一致的驗證與回報方式；若刻意允許寬鬆轉換，應在 spec 明講。

### R8-21〔低〕history 留有確定未使用的 import

**證據：** `proto7-2/modules/history.py:19`。

`json` 沒有被該檔使用；AST 名稱引用檢查與檔案閱讀一致。

**建議：** 移除這個 import。其餘「看似沒用到」的公開 API 不宜一併刪除，見後面的未完成項目。

## 3. 做到一半、尚未完成核驗的發現

以下**不算定案缺陷**。部分已有局部 mock 結果，但尚未完成跨層時序、契約歸屬或精確行號核對。

### R8-22〔可能高〕step 的 intent_round＋1 補加窗口可能造成同 attempt 再執行

**位置：** `proto7-2/packs/step/aos7_step.py:493`～`:500`；`packs/step/spec.md:80`～`:81`；核心開回合入口 `lib/aos7_tick.py:278`，刪槽判定 `lib/aos7_tock.py:134`～`:136`。

候選時序：

1. 既存 step 任務被上一個 tock 喚醒。
2. 下一個 tick 已寫 round=r，但尚未讀任務表。
3. step 讀到 r、保存 intent、加 once；該 once 被同一個 r 的 tick 起動。
4. r 的 tock 報結束，r+1 的 tock 刪槽。
5. step 曾在 after-add 中斷，恢復時仍在 r+1；表、槽、結果都沒有，卻仍符合補加條件。

這意味著「第三個 tock 才可能刪」的推論可能差一回合。**完整跨核心的記憶體時序驗證尚未收齊。**

建議後續優先驗證這項；安全窗口必須從真正的登記／挑選順序推導，不能只依已讀到的 round 數字。

### R8-23〔可能中〕adapt 的合法數值可導致 Infinity、量化例外與門檻誤判

**位置：** `proto7-2/packs/adapt/aos7_adapt.py` 的數值鏈區段（`:150` 起）與框架判定區段（`:242` 起）。

審查線已回報以下純記憶體結果：

- `x=1e308`、乘數 2，可產生 `state:ok`、value 為 Infinity。
- `x=1e28, round=0`，或 `x=1e16, round=12`，可拋 `Decimal.InvalidOperation`。
- 大整數 `9007199254740993` 經 `x ± 0.0` 轉成浮點後，等值門檻可能誤判。
- `x=1e16`、誤差 0.5 的門檻判定，也有誤差被浮點精度吃掉的候選。

**未完成：** 各案例的精確運算行號、輸入契約與輸出誤差保證尚未逐條複核。

建議核定數值域、每一步檢查有限性，並避免精確整數／誤差界被隱式浮點轉換破壞。

### R8-24〔可能中〕subd 的別名路徑可漏過「包住父 node」檢查

**位置：** `proto7-2/modules/subd/aos7-subd:66`。

mock 中 `a/alias → a/sub`，父 daemon 已登記 `a/sub/n1`。用實際路徑 `a/sub` 會拒絕，用 alias 卻通過；後续回收使用實際路徑，可能把父管理的任務納入。

**未完成：** 尚未最後確認 README 對 subroot 符號連結與非法配置的前置條件，不能直接定成契約內 bug。

建議所有位置與從屬關係檢查統一使用 canonical path。

### R8-25〔可能中〕audit 全域 busy 旗標會漏掉其他 thread 的寫入

**位置：** `proto7-2/modules/audit/audit_site/sitecustomize.py`；精確行號尚未完成核對。

兩個 thread 的記憶體模擬顯示：第一個 thread 正在記錄稽核 I/O 時，第二個 thread 的真正寫入被全域 busy 當成稽核遞迴而略過。

**未完成：** 尚未完成 README 保證範圍，以及 `dir_fd` 寫入定位問題的複核。

建議若要支援多執行緒 Python 任務，遞迴防護應使用 thread-local；log 寫入的同步另行處理。

### R8-26〔可能中低〕once_retry 使用舊 birth 加回已經重試過的工作

**位置：** `proto7-2/modules/once_retry/retry_lost.py:34`～`:47`；契約 `modules/once_retry/README.md:20`、`:27`。

局部 interleaving mock 顯示：讀取舊 lost birth 後，另一輪 tick 已消耗 retry once 並寫新 birth；取得表鎖時，因 pending 項已不在表上，又能追加同一個 retry_of。

**未完成：** 此包明確接受至少一次的有限重複，尚未完成「這個競爭是否超出既定代價」的契約判定。

建議參照 control，在表鎖內重讀目前 birth，核對原 run 與 retry 證據。

### R8-27〔契約交接待核〕budget 的 rc 3 不會自然觸發 step 的 on_unknown

**位置：** `proto7-2/packs/budget/spec.md:80`～`:81`；`packs/step/spec.md:70`；`packs/step/aos7_step.py:447`～`:457`。

budget 用 rc 3 表示 unknown，但 step 結果包裝程式的一般規則是非零退出碼寫成 `ok:false`；step 採用後走 fail，而不是 on_unknown。這與 budget 文件推薦的 `on_unknown: resend` 接法有落差。

**未完成：** 尚未收齊包裝程式精確行號與完整兩包串接證據。

建議明定 budget unknown 如何透過結果協定傳給 step，或修正接法文件。

### R8-28〔可能低至中〕inst 指示詞解析有漏判與例外外洩

**位置：** `proto7-2/lib/aos_directives*.py`、`lib/aos_inst.py`。

局部驗證回報：

- `$at:null` 被當成省略，而不是型別不符。
- 陣列 pointer `/²` 通過 `isdigit()`，卻在 `int()` 拋 `ValueError`，可能漏成 traceback 與非約定退出碼。

**未完成：** 精確行號與 inst 規範逐條對照尚未整理完畢。

### R8-29〔設計風險待核〕daemon 保存的裸 pgid 缺少身分重驗

**位置：** `proto7-2/lib/aos7_proc.py:235`～`:246`；`lib/aos7_daemon.py:448`。

槽級 kill 有防 pgid 重用的檢查，但 node 級回收會直接加入保存的 pgid。若程序群號已被重用，存在打到其他群組的風險。

**未完成：** 未做真實重用重現；目前 spec 的 node 回收規則本身也採已知 pgid，應先釐清是契約缺口還是實作缺陷。

### R8-30〔維護性待核〕部分搬入的公開 API 在本版本沒有呼叫者

**位置：**

- `proto7-2/lib/aos_exec.py:78`：`run_target_full`
- `proto7-2/lib/aos_exec.py:173`：`run_inst`
- `proto7-2/lib/aos_exec_spawn.py:44`：`spawn_target`
- `proto7-2/lib/aos_inst.py:91`：`load_obj`

目前搜尋未見 proto7-2 生產／測試呼叫，但其中有明確公開 API、`__all__` 或相容 re-export，**不能直接等同死碼**。

建議先區分「本原型需要的介面」與「搬入時保留的相容介面」，再決定保留、隔離或刪除；不要只靠 unused-import 掃描清掉 facade。

## 4. spec 條文對應實作：已完成的初步表

這是核心 `spec.md` 的初步映射，尚未完成每一句規則的驗收。

| 條文 | 實作位置 | 目前判定 |
|---|---|---|
| §0 檔案三態、錯誤入口 | `lib/aos7_fs.py:84`、`:205`、`:223` | 有實作；R8-07 的資源收尾有缺陷 |
| §0 程序三態 | `lib/aos7_proc.py:29`、`:54` | 有實作；R8-12 有未轉成 Unknown 的例外 |
| §0 原子寫、鎖、暫存清理 | `lib/aos7_fs.py:119`、`:136`、`:185` | 有實作；未完成所有呼叫端順序驗證 |
| §1 node 登記與路徑檢查 | `lib/aos7_daemon.py:145`、`:174` | 有實作；取消登記見 R8-03 |
| §1 timeline 設定 | `lib/aos7_daemon_timeline.py:59` | 部分設定錯誤未回報，R8-20 |
| §2.1 時間線六步 | `lib/aos7_daemon_timeline.py:176` | 有實作；退避及回合結算有 R8-05、06 |
| §2.2 舊回合先收尾 | `lib/aos7_daemon_timeline.py:151`、`:184` | 有實作；closed 恢復後的倒數交接不完整 |
| §2.3 daemon 控制檔 | `lib/aos7_daemon.py:156`、`:288`、`:325` | 有實作；R8-03 |
| §2.4 owner 與 rounds | `lib/aos7_daemon.py:124`、`:128` | 有實作；R8-05 違反指定回合數 |
| §2.5 世代、動作鎖 | `lib/aos7_fs.py:259`；`lib/aos7_daemon.py:558` | 有實作 |
| §2.5 動作逾時、舊持有者回收 | `lib/aos7_daemon_timeline.py:28`、`:299`；`lib/aos7_fs.py:286` | 有實作；未做真程序驗證 |
| §2.5 抓住 root／node fd | `lib/aos7_daemon.py:46`；`lib/aos7_tick.py:221` | 有實作 |
| §2.6 node 消失、回收後重開 | `lib/aos7_daemon.py:390`、`:446` | 成功門檻不足，R8-02 |
| §2.6 未知時保留 live／pgid | `lib/aos7_daemon.py:471` | 部分路徑違反，R8-04 |
| §2.7 stop 與守門檔 | `lib/aos7_daemon.py:280`、`:379`、`:501` | 有實作；kill 啟動窗口受 R8-01 影響 |
| §2.8 status 與事件 | `lib/aos7_daemon.py:79`、`:510` | 有實作 |
| §3 回合判定與接號 | `lib/aos7_fs.py:223`；`lib/aos7_tick.py:246` | 有實作 |
| §4.1 任務表驗證 | `lib/aos7_tick.py:26`、`:50` | 有實作；未完成全部欄位邊界核验 |
| §4.2 tick 順序 | `lib/aos7_tick.py:278` | 有實作 |
| §4.3 表鎖與讀改寫 | `lib/aos7_fs.py:205`；tick 的挑選與 once 處理 | 有實作 |
| §4.4 once launch 證據 | `lib/aos7_tick.py:170`、`:180`；`lib/aos7_task.py:304` | 有實作；上層對保存窗口的推論待 R8-22 核驗 |
| §4.5 掛載與動態加掛 | `lib/aos7_mount.py`；`lib/aos7_tick.py:199` | 有實作；R8-08、09 |
| §5.1 槽重用、清理、結果保存 | `lib/aos7_task.py:275`；`lib/aos7_tock.py:114` | 有實作；尚未全面驗證所有中斷點 |
| §5.2 run 與身分掃描 | `lib/aos7_proc.py:122` | 有實作；runner 分類有 R8-11 |
| §5.3 啟動交接與失敗結果 | `lib/aos7_task.py:285`；`lib/aos7_run.py:38` | R8-01、10 |
| §5.4 槽三態與 lost | `lib/aos7_task.py` 的 `judge`／`resolve`；`lib/aos7_proc.py` | 已通讀；完整條文映射尚未整理 |
| §5.5 任務環境與 tock | `lib/aos7_task.py:306`；`modules/tools/aos7_taskside.py:21`、`:30` | 有實作 |
| §6 帶 run 的 kill | `lib/aos7_task.py:186`、`:209`；`lib/aos7_proc.py:210` | 有實作；成功條件有 R8-01 |
| §7 總結提交、通知、重播 | `lib/aos7_tock.py:42`、`:96`、`:139` | 有實作 |
| §8 任務 state 保留 | `lib/aos7_task.py:275` | 有實作；上層累計仍由各包負責 |
| §9 模組擴充出口 | `lib/aos7_task.py:301`；daemon 的 log／stop-guard | 有實作 |
| §10 工具 | `modules/tools/aos7_ctl.py`、`aos7_taskside.py` | 已通讀；逐命令映射未整理完 |
| §11 界線 | 契約與範圍宣告 | 不應視為待實作功能清單 |
| §12 診斷 | `modules/diag/aos7-diag`、`modules/diag/README.md` | 已通讀；逐停點對照未整理完 |

**尚不能宣告「所有 spec 條文都已實作」。** 截止目前沒有確認某一整節完全缺席；已確認的是上述局部保證未兌現。

文件明列延後的 keep restart 政策、pause 中任務控制、事件式喚醒、成組全有全無與 out.log 上限，位於 `proto7-2/spec.md:294`，不算本次新發現的漏實作。

## 5. 已做的補充驗證與限制

審查線另外回報：

- budget 純記憶體隨機狀態轉移 **20 組 seed × 500 次**：守恆、非負、每 K 最多一筆 reserve／settle 與後端計數未發現違反。
- A6 類後端 EIO 的主要路徑，能保留 intent／inflight 並在恢復後完成。
- adapt 的 **14 個純函式既有單元測試**通過。
- step checker 的 **444 個型別變異**沒有發現未捕捉例外。

這些结果支持已測到的局部行為，**不能代替完整測試套件或真實並行／中斷驗收**；原始測試輸出與 mock 腳本未保存成檔。

## 6. 沒來得及做的

1. 完成 R8-22 的跨核心重複派工時序驗證，以及所有未定案項目的最後否證。
2. 收齊各審查線完整終稿，逐一獨立重跑高重要程度 mock。
3. 補齊 modules 各 README、step／budget／adapt 各 spec 的逐條實作映射與缺漏表。
4. 完成全部測試檔的斷言有效性審查；目前只確認 step 的 `/dev/stdin` 盲點。
5. 系統性整理可合併的重複邏輯。目前最值得檢查的是檔案三態的重讀、程序 stat 的重複解析、unknown 策略入口與各包的去重檢查，但尚未形成可保證行為不變的重構方案。
6. 執行真實檔案故障、程序退出、PID／PGID 重用、SIGKILL 與長跑測試；這些本來就超出本次「只讀檔、不跑會寫檔的東西」的授權。
7. 收尾時重新計算來源雜湊與 Git 狀態；依立即停止要求沒有再做。

修補順序建議先處理 **R8-01～03**，並優先完成 **R8-22** 的核驗；其次修正三態資訊遺失、掛載重播與 step 重送計數，再處理診斷、測試及清理項目。