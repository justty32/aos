結論：文件的主要問題是把「有條件的保證」寫成絕對保證，以及跨套件沿用同名術語卻沒有交代語義差異；最優先應修正診斷手冊的回合恢復判準、pause 操作說明，以及 budget 接 step 的未知狀態處理說明。

# proto7-2 文件可讀性與一致性審查

## 審查範圍與完成程度

本報告依使用者要求立即收尾，只整理截至停止指示前取得的證據。

已讀完主要審查範圍：

- `proto7-2/spec.md`
- `proto7-2/modules/README.md`
- 六個 `modules/*/README.md`
- 三個 `packs/*/README.md`

另外讀取各包規格、部分實作與既有測試原始碼作交叉核對。共開五條平行審查線；本報告已整合收到的具體發現，但未完成所有子線的最終報告與第二輪互審。

審查基準 HEAD：`6daebe2ef8227021745def649f4e3d86a3a8038c`。開始時已有未追蹤的 `proto7-2/notes/reviews/`，不屬於本次產出。

**沒有修改專案檔案、沒有 commit 或 push，也沒有執行測試、daemon、tick、套件 CLI 或匯入專案模組。** 下列「已確認」指文件與原始碼可直接確認的落差，不表示已動態重現故障。曾有純讀取分析指令使用 heredoc，被唯讀 shell 擋下；未成功建立檔案，之後改用不需暫存檔的方式。

以下路徑均相對於 `/home/guanyu/projs/aos`。

## 一、優先修正：可能讓人操作錯誤或誤判保證

### F01．診斷手冊把「總結已提交」誤當成「回合已收完」

**證據**

- `proto7-2/modules/diag/README.md:47`：「N＝last-round 的 round → 第 N 回合已收，寫 `{"round": N, "open": false}`」。
- `proto7-2/spec.md:257`～`:262`：先提交總結，之後才通知、補 `seen_round`、刪槽、關回合；中斷後可以重播收尾。
- `proto7-2/lib/aos7_tock.py:96`～`:110`：實作順序相同，`last-round.json` 落地時，`round.json` 尚可能保持開啟。

**影響**

總結存在只證明總結已提交，不能證明通知與收尾完成。照手冊直接寫 `open:false`，可能跳過本來應執行的重播收尾。

**建議改寫**

> `last-round.json` 的回合號只證明該回合總結已提交，不能單獨證明回合已關閉。核實回合號後，若無法確認收尾完成，應保留或恢復 `open:true`，讓 tock 依已提交總結重播收尾；只有另有可靠證據確認回合已關閉，才寫 `open:false`。

### F02．pause 被描述成能停止所有寫檔競爭

**證據**

- `proto7-2/modules/diag/README.md:46`：要求 pause「讓會寫檔的動作停止競爭」，並說「pause 時不 tick／tock」。
- `proto7-2/spec.md:63`、`:81`：pause 不停止既有任務，本回合照常收完。
- `proto7-2/spec.md:52`：未關回合先 tock，之後才重新看 pause。
- `proto7-2/lib/aos7_daemon_timeline.py:183`～`:214`：恢復未關回合的分支確實排在 pause 判斷之前。

**影響**

人可能在仍有 tock 或任務寫檔時進行修復。收到 pause 回條也不等於已取得修復所需的排他性。

**建議改寫**

> pause 只阻止新回合，不會中止既有任務；進行中的回合及未關回合的恢復 tock 仍可能寫檔。修復前先保存證據、送出 pause，並確認相關寫者與動作已停止；不能只憑 pause 回條認定檔案已無競爭。

### F03．budget 的 `unknown` 不會直接觸發 step 的 `on_unknown`

**證據**

- `proto7-2/packs/budget/README.md:14`、`:55`：介紹 `on_unknown: resend`，並說後端讀寫不到會回 3「等人／等 step 重送」。
- `proto7-2/packs/step/aos7_step_result.py:64`～`:77`：命令正常退出 3，仍會發布有效結果，內容為 `code:3`、`ok:false`。
- `proto7-2/packs/step/aos7_step.py:636`～`:646`：有結果先採結果，不走證據不足的 `on_unknown`。
- 同檔 `:447`～`:457`：`ok:false` 走 `fail`，沒有 `fail` 才停在 `failed`。
- `proto7-2/packs/budget/examples/fakeapi/steps.json:7`～`:9`：示範把失敗導向結束。
- `proto7-2/packs/step/aos7_step.py:738`～`:740`：`resume` 只接受 `halted`，不接受已 `ended` 的工作。

**影響**

設定了 `on_unknown: resend`，仍不代表 budget 回 3 會自動重試。示範工作甚至會結束，而預留可能仍在途；此時也不能直接用 `resume --resend` 恢復。

**建議改寫**

> `on_unknown: resend` 處理的是 step 無法確認嘗試結果的情況，例如結果檔未發布；budget 正常退出 3 時，step-result 仍會發布 `ok:false`，因此走步驟的 `fail` 分支。恢復未完成的預算操作時，須保留原業務鍵 K，以同 K 重跑 `call` 或依入口證據結算；工作走到 `ended` 後不能直接 `resume`。

### F04．「永久拿掉子空間」的步驟少了清除任務的條件

**證據**

- `proto7-2/modules/subd/README.md:77`：允許的 stop → 等 `stopped.json` → 拿掉父任務。
- 同檔 `:66`：不帶 `--kill` 的 stop 會保留任務。
- 同檔 `:75`：父不再起包裝程式，就不會執行下一次重開前回收。
- `proto7-2/spec.md:66`：stop 只有帶 `kill:true` 才要求收任務。

**影響**

照「永久拿掉」流程操作，可能留下持續執行、卻不再收到 tock 的子空間任務。

**建議改寫**

> 要停用子空間並收掉其任務，先對允許外部 stop 的子 daemon 送出 `stop --kill`，等待停止標記，並確認管理範圍內的任務已收完，再拿掉父 tasks.json 的包裝任務。不帶 `--kill` 的 stop 會保留任務，不能當成子空間已清空。

### F05．subd 宣稱「控制檔 stop 一定留回條」，與核心故障契約矛盾

**證據**

- `proto7-2/modules/subd/README.md:48`：「控制檔 stop 一定留回條」。
- `proto7-2/spec.md:71`：效果可能已生效，但回條寫入失敗；核心刪請求、記錯、不重做。
- `proto7-2/lib/aos7_daemon.py:285`：先執行 stop。
- 同檔 `:357`～`:365`：之後才準備回條。
- `proto7-2/modules/subd/aos7-subd:141`～`:176`：`allowed_stop` 確實需要成功 stop 回條作證據。

**影響**

「stop 已執行」與「subd 能辨認為被允許的 stop」不是同一件事。現有文字隱藏了回條遺失時的辨認限制。

**建議改寫**

> 正常完成的控制檔 stop 會留下成功回條；若停止效果已生效但回條寫入失敗，核心只記錄控制錯誤，subd 可能無法將這次停止辨認為 `allowed_stop`。本包的不回收保證以可讀的停止狀態及本代成功 stop 回條為前提。

這是需要補明契約界線的地方；本次未裁定是否也應修改實作。

### F06．step 宣稱不依賴槽保留時間，但補派判斷實際依賴它

**證據**

- `proto7-2/packs/step/README.md:45`：「本包不依賴槽留多久，只依賴自己的結果檔」。
- `proto7-2/packs/step/spec.md:80`～`:81`：用「第三個 tock 才刪」推導是否可以補加 once。
- `proto7-2/packs/step/aos7_step.py:493`～`:499`：補加前檢查槽證據及 `intent_round + 1` 窗口。

「第三個 tock」的推導本身也缺少前提：

- `proto7-2/lib/aos7_tick.py:287`～`:288`：先寫新回合。
- 同檔 `:313`～`:319`：之後才拿任務表鎖。
- `proto7-2/packs/step/aos7_step.py:482`～`:501`：step 加項只拿任務表鎖。
- `proto7-2/lib/aos7_tock.py:126`～`:136`：已在前一回合報過、且不在表上的結束槽可刪。

因此合法順序可以是：tick R 開回合後、讀表前加項 → 同一 tick R 啟動 → tock R 報結束 → tock R+1 刪槽。這是加項後第二個 tock。

**建議改寫**

> 已發布的工作結果存於槽外，不受槽刪除影響；派工中斷後能否補加，仍依賴任務表、birth 證據及其保留窗口。核心只保證槽最早在報結束的下一個 tock 刪除，不能無條件推成「加項後第三個 tock」。

**查證界線：**已確認文件矛盾與推導缺前提；尚未完成「是否真的造成同 attempt 重複派工」的完整時序驗證，不將它報成已重現的執行缺陷。

### F07．subd 範例直接使用不在預設 PATH 的程式

**證據**

- `proto7-2/modules/subd/README.md:31`：argv 使用裸名 `aos7-subd`。
- 同檔 `:35`：明說它不在任務 PATH。
- `proto7-2/spec.md:237`：任務 cwd 是 node。
- `proto7-2/README.md:36`：自動加入 PATH 的是 `proto7-2/bin`。

**影響**

乾淨的預設環境下，直接複製範例會找不到程式。把裸名換成文件列出的 repo 相對路徑，也未必能從 node 的 cwd 找到。

**建議改寫**

> 本例中的 `<proto7-2>` 必須替換成原型目錄的絕對路徑；任務 cwd 是 node，因此使用 `["python3", "<proto7-2>/modules/subd/aos7-subd", "team/sub", "--", ...]`，不要直接使用裸名或 repo 相對路徑。

### F08．`wait_tock` 的文件簽名把第三個參數寫錯

**證據**

- `proto7-2/modules/tools/README.md:44`：`wait_tock(task_dir, last_round, timeout=None)`。
- `proto7-2/modules/tools/aos7_taskside.py:30`：實際為  
  `wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None)`。
- 同檔 `:40`～`:49`：timeout 控制截止時間，poll 控制睡眠間隔。

**影響**

照文件寫 `wait_tock(task, last, 5)`，實際是每五秒輪詢，並沒有五秒逾時。

**建議改寫**

> `wait_tock(task_dir, last_round, poll=0.02, timeout=None, run=None)`：回傳新的回合號，逾時回傳 `None`。設定等待上限請寫成 `wait_tock(task_dir, last_round, timeout=5)`；第三個位置參數是輪詢間隔。

### F09．once 中斷窗口被寫得過度籠統

**證據**

- `proto7-2/spec.md:176`、`proto7-2/modules/once_retry/README.md:5`：把「birth 已寫、runner 尚未記上」整段描述為一次都沒跑、之後 lost。
- `proto7-2/lib/aos7_task.py:304`～`:328`：該窗口同時涵蓋 runner 尚未啟動，以及 runner 已啟動但尚未補記的兩種情況。
- `proto7-2/tests/core/test_matrix_once.py:25`、`:58`～`:63`：既有測試明確區分 `after-birth` 與 `after-popen`；後者期待執行一次。

**影響**

容易誤把「birth 沒有 runner 欄位」當成「任務確定没跑過」。

**建議改寫**

> 若 tick 在 birth 落地後、runner 尚未啟動前中斷，可能留下沒有執行過的 once；符合第 5.4 節條件後才判 lost。若 runner 已啟動、只是尚未補記到 birth，則須依 runner、pid、exit 與身分掃描判定，不能只憑 birth 缺 runner 認定沒有執行。

### F10．重試與重起的首頁保證，比實際契約更強

**證據**

- `proto7-2/modules/once_retry/README.md:5`、`:17`：「讓 once 至少一次」。
- 同檔 `:22`、`:33`～`:34`：取樣漏掉、槽已刪除時，無法保證補回。
- `proto7-2/spec.md:176`：「要至少一次用 once 保證包」。
- `proto7-2/modules/control/README.md:21`：「不會殺了沒重起」。
- `proto7-2/spec.md:176`：核心 once 仍存在啟動零次的中斷窗口。

**影響**

讀者只讀入口或契約卡，會得到比後文限制更強的可靠性承諾。

**建議改寫**

once_retry：

> 本包在觀察到符合條件的 lost 紀錄、且槽證據仍在時補登 once；它降低未啟動就遺失的機會，但因為採樣與證據保存有限，不提供無條件的至少一次保證。

control：

> kill 送出前，重起用的 once 項目已先落地，因此不會因請求端兩步之間中斷而只留下 kill；後續能否成功啟動，仍受核心 once 契約及故障條件限制。

### F11．step 的普通 `resume` 也可能重派，並非只有 `--resend` 才會

**證據**

- `proto7-2/packs/step/README.md:38`：「結果已到就照結果走；`--resend` …重派」。
- `proto7-2/packs/step/aos7_step.py:447`～`:457`：採到失敗結果且沒有 `fail` 目標時，清掉 pending，再停為 `failed`。
- 同檔 `:629`～`:635`：pending 為空時直接派工。
- 同檔 `:738`～`:747`：普通 resume 清停點；`--resend` 則主動丟掉仍在的 pending。

**影響**

人可能以為不加 `--resend` 就不會重新執行；反過來，加了 `--resend`，即使舊結果已到，也不會先採用它。

**建議改寫**

> `resume` 只接受 `halted`。pending 仍在時，不加 `--resend` 會保留該嘗試並重新查證；但 `failed` 停點可能已清除 pending，普通 resume 也會派新 attempt。加 `--resend` 會丟棄舊 pending，以同 request 建立新 attempt，不先採用舊嘗試遲到的結果。

## 二、其他已確認的一致性落差

### F12．固定 interval 的起算點寫成了 tick 結束後

**證據：**`proto7-2/spec.md:30`、`:42` 寫「tick 之後等滿 interval」；但 `proto7-2/lib/aos7_daemon_timeline.py:217`～`:221` 在啟動 tick **之前**設定截止時間，`:241` 只等到該時間。

**建議改寫**

> interval 從本回合啟動 tick 前的單調時間起算，包含 tick 執行時間；tick 結束後只等剩餘時間。wake 與 early_tock 依第 2.1 節提前結束等待。

### F13．tick 與 tock 的非零退出碼被錯誤概括成同一條規則

**證據：**`proto7-2/spec.md:46` 說後兩類退出碼都退避、不算回合；實作 `proto7-2/lib/aos7_daemon_timeline.py:229`～`:233` 對 tick 如此處理，但 `:257`～`:266` 對 tock 以回合是否確知關閉為準，`:204`～`:206` 也會在恢復完成後扣倒數。

**建議改寫**

> tick 回 3 或其他失敗時退避，不因該次 tick 扣 rounds；動作逾時另依中斷回合流程處理。tock 執行後重新判定 round.json：尚未確知關閉就補收或進恢復流程，確知關閉後才扣一次 rounds，不能只用 tock 的退出碼判斷。

### F14．壞 JSON 控制檔不一定保存成 `.bad`

**證據：**`proto7-2/spec.md:70` 把「讀不懂、不是 `.json`、不是一般檔」都寫成保留 `.bad`。`proto7-2/lib/aos7_daemon.py:331`～`:356` 只有檔名或檔案種類不合進 `.bad` 分支；`:357`～`:360` 對不可解析／非物件內容改寫成拒絕回條。

**建議改寫**

> 檔名不是 `.json` 或不是一般檔時，嘗試將原物保留為 `.bad`，另寫拒絕回條。一般檔的 JSON 讀不懂或不是物件時，回 `ok:false`，不保證保留原始內容。

### F15．`each` 的描述漏掉 `max_live > 1` 的情況

**證據：**`proto7-2/spec.md:137` 說「上一次還在跑就跳過」；`proto7-2/lib/aos7_tick.py:184`～`:194` 是有空槽就挑一個，沒有可用槽才跳過。

**建議改寫**

> `each` 每回合最多在一個可用槽啟動一次；只要還有可用槽，即使其他同名 run 仍在執行也可啟動。沒有可用槽時才跳過；`max_live:1` 時才等同於上一個還在跑就跳過。

### F16．kill 的冪等性被寫成「只生效一次」

**證據：**`proto7-2/spec.md:245`：「帶 run 讓重播只生效一次」；`proto7-2/modules/diag/README.md:65` 明寫刪不掉會每回合再執行；`proto7-2/lib/aos7_task.py:245`～`:249` 也保留此行為。

**建議改寫**

> 帶 run 讓重播始終只針對原 run，不會誤殺槽內的新 run；同一請求可能重複執行，但重複收掉已結束的同一 run 是冪等的，並非只執行一次。

### F17．step 的耐性起點不全是「走進該步」

**證據：**`proto7-2/packs/step/README.md:22` 一概如此描述；`proto7-2/packs/step/aos7_step.py:469` 為新嘗試設定 pending 的起點，`:626` 的 wait 用 frame 起點，`:649` 的 run 用 pending 起點，`:741`～`:746` 的 resume 又會重設。

**建議改寫**

> 耐性以本 node 的回合計算：wait 從進入該步的 frame.since 起算，run 從當次 pending.since 起算；建立新嘗試或人工 resume 時會重設相應起點，因此不是整個步驟不可重設的總期限。

### F18．step 結果的發布方式寫錯，且「產物都在」不足以代表通過

**證據**

- `proto7-2/packs/step/README.md:28`、`proto7-2/packs/step/spec.md:70` 寫 rename。
- `proto7-2/packs/step/aos7_step_result.py:28`～`:45` 實際使用 `os.link`，目的檔存在就拒絕覆寫。
- `proto7-2/packs/step/spec.md:70` 把成功條件寫成「expect 的產物都在」。
- `proto7-2/packs/step/aos7_step_result.py:20`～`:25`、`:69`～`:77` 要能完整讀取並計算 SHA-256；資料夾或不可讀檔案也算 missing。

**建議改寫**

> 結果先完整寫入暫存檔，再以 hard link 原子發布；目的檔已存在就拒絕覆寫。`ok` 要求命令退出碼為 0，且 expect 所列都是可完整讀取並計算 SHA-256 的檔案；不支援目錄，讀取失敗也列入 missing。

### F19．budget 的退出碼契約自相矛盾，並漏列 payload 失敗的 2

**證據**

- `proto7-2/packs/budget/README.md:42`：「拿到終局結算回條才退出」，同句卻列未知退出 3。
- `proto7-2/packs/budget/spec.md:74`～`:77`：預留被拒等情況也能在沒有結算回條時退出 1。
- `proto7-2/packs/budget/README.md:42` 承諾「任何讀寫不到都歸 3、印一行 JSON」。
- `proto7-2/packs/budget/aos7_budget_gate.py:168`～`:172`：payload 讀取不成功時印 stderr，退出 2。

**建議改寫**

> call 成功完成預留、准入與結算後退出 0；拒絕、衝突或終局失敗退出 1；尚未取得可完成下一步的證據時退出 3，不自動退款。目前 payload 讀取失敗另走 stderr 並退出 2。只有成功完成結算的分支，才保證已有終局結算回條。

若原意是「所有 I/O 故障一律 3」，則應調整實作而非採用最後一句；本次只指出落差。

### F20．grant 的三分法漏掉 `not_yet`

**證據：**`proto7-2/packs/budget/README.md:27` 說只有准許／拒絕／未知；`proto7-2/packs/budget/spec.md:32` 及 `proto7-2/packs/budget/aos7_budget.py:129`、`:150` 另有尚未生效的 `not_yet`，而且是非終局。

**建議改寫**

> 判定回傳 `ok`（准許）、`denied`（拒絕）、`unknown`（未知）或 `not_yet`（尚未到效期，非終局）；不得把 `not_yet` 保存成永久拒絕。

### F21．budget 取消後「結算 0」少了取消成功的前提

**證據：**`proto7-2/packs/budget/README.md:48` 先說取消可能不成功，隨後仍寫「之後 settle 或重跑 call 結算 0」。`proto7-2/packs/budget/spec.md:62` 明定 accepted／failed 的 used 是 amount，只有 cancelled／denied／rejected 為 0。

**建議改寫**

> 取消成功、入口終局為 `cancelled` 時，後續 settle 或同 K 的 call 才會按 used=0 結算；若已支用而取消不成，應依原終局的 used 結算，不能假定退款。

### F22．adapt 同時寫「每次重算」與「重起後不重算」

**證據**

- `proto7-2/packs/adapt/README.md:19`：每次從固定版本依據重算。
- 同檔 `:27`：被殺重起「不重算」。
- `proto7-2/packs/adapt/spec.md:88`：下一圈從框架重算同一版，skipped 不重加。
- `proto7-2/packs/adapt/aos7_adapt.py:306`：每圈對有效來源執行鏈。

「不吃上一跳」也容易被誤讀為不使用鏈內前一步的輸出；但 `proto7-2/packs/adapt/spec.md:40`～`:42` 明確是逐步轉換。

**建議改寫**

> 每次都從本次固定的來源檔版本重跑整條鏈，不把前一輪產出的暫存器當成新來源。中斷後可以重算同一版本，但不把它當成新版本，也不重複增加 skipped。

### F23．adapt 的耐性不是所有未知情況都能撐住舊值

**證據：**`proto7-2/packs/adapt/README.md:24` 容易讀成讀取或轉換失敗都先撐到耐性到期。`proto7-2/packs/adapt/spec.md:73`～`:83` 區分讀取失敗、依據作廢、過期、停太久與誤差帶；`proto7-2/packs/adapt/aos7_adapt.py:332` 的保留條件也要求先前為 ok、沒有 reset 等條件。

**建議改寫**

> 可恢復的讀取或型別錯誤，只有在上一份輸出為 ok、耐性尚未到期，且舊依據未因 reset、過期或來源停滯而失效時，才維持舊值；宣告錯誤、依據失效及誤差帶不確定等情況依規則直接輸出 unknown。

### F24．adapt 的「pause 時都不走」沒有指明是哪一個 node

**證據：**`proto7-2/packs/adapt/README.md:25` 把效期與耐性合寫成「pause 時都不走」；`proto7-2/packs/adapt/spec.md:48`～`:56` 分別使用來源回合與消費端回合。

**建議改寫**

> max_age 用來源 node 的回合計算，來源 pause 時年齡不增加；patience 用消費端 node 的回合計算，消費端 pause 時耐性不增加。兩個 node 的 pause 互不代替。

### F25．audit 的「每筆寫入都有紀錄」超過實作涵蓋範圍

**證據**

- `proto7-2/modules/audit/README.md:5`、`:20`：每個寫動作、每筆寫入都有紀錄。
- `proto7-2/modules/audit/audit_site/sitecustomize.py:92`～`:96`：略過非文字路徑與部分目標。
- 同檔 `:130`～`:147`：只處理列出的 audit 事件。
- 同檔 `:148`～`:150`：紀錄失敗會吞掉例外，維持只記不擋。

**影響**

即使任務是 Python、也確實使用包裝程式，沒有紀錄仍不能證明沒有寫入。

**建議改寫**

> 本包盡力記錄已涵蓋的 Python audit 寫入事件，並判斷路徑是否越界；整數 fd、未涵蓋的事件及紀錄本身失敗時可能沒有紀錄。因此 writes.jsonl 可作觀察資料，不能作為完整寫入清單或「未曾寫入」的證明。

## 三、引用、命名與入口可讀性

以下也已確認，但優先度低於前述操作與契約問題。

| 編號 | 發現與證據 | 建議改寫 |
|---|---|---|
| F26 | **派工窗口指錯章節。** `proto7-2/packs/step/README.md:43` 引 spec §4，但 §4 是結果檔；派工順序在 `packs/step/spec.md:79`～`:81`。 | 「框架與 tasks.json 不是同一筆交易，派工與中斷恢復順序見本包 spec §5 第 4 步。」 |
| F27 | **模組總覽仍寫 kernel 任務包尚未做。** `proto7-2/modules/README.md:22` 與 `proto7-2/README.md:108`～`:111` 列出的 step、budget、adapt 不一致。 | 「安裝工具 aos7-pack 尚未實作；上層任務包另置於 packs/，目前已有 step、budget、adapt，入口見專案 README 的結構表。」 |
| F28 | **`caller` 是欄位名殘留。** `proto7-2/packs/budget/README.md:40` 說 caller 欄位，實際公開欄位是 holder，見同檔 `:38`、`:56` 及 `packs/budget/spec.md:25`。 | 「明確不管：呼叫者自報的 holder 是否真為本人。」 |
| F29 | **resolver 回傳的是函式，文件像在說直接回路徑。** `proto7-2/modules/tools/README.md:45`；實作 `modules/tools/aos7_taskside.py:52`～`:74`。 | 「`resolve = resolver(taskdir)` 建立解析函式；再呼叫 `resolve(空間路徑)` 取得經掛載的路徑，沒有對應掛載時回 None。」 |
| F30 | **檔名編碼不是全程無損。** `proto7-2/modules/tools/README.md:20`、`:29` 宣稱無損、不會撞名，同一段卻明寫長字串截斷加 64-bit 雜湊。 | 「短字串使用可逆編碼；編碼後超過 64 字元時改用前綴加雜湊，屬實務上的低碰撞命名，不是無損編碼或數學上的零碰撞保證。」 |
| F31 | **「依賴」欄混用契約依賴與 Python 匯入依賴。** audit README `:11` 寫無，但 `modules/audit/aos7_audit.py:11`～`:12` 使用 tools；control README `:11` 也未列其 `aos7_control.py:12` 的 tools 匯入。 | 「依賴分為核心協定與程式依賴；本包的程式依賴包含工具包 aos7_taskside。」各包依實際內容補列。 |
| F32 | **step 範例與執行入口缺少接續步驟。** `proto7-2/packs/step/README.md:10`、`:14`、`:35`～`:39` 列工作路徑與裸命令，卻沒交代範例整份放到 node 的工作目錄；`packs/step/spec.md:5` 才說路徑相對 node。 | 「使用範例前，將 examples/<範例> 整份放入 <node>/jobs/<job>；人手指令在 node 目錄執行，並以 `python3 <proto7-2絕對路徑>/packs/step/bin/aos7-step …` 呼叫。」 |
| F33 | **step 啟動時也會推進，並非必須等第一個 tock。** `packs/step/README.md:20` 只寫每次 tock；`packs/step/spec.md:73` 與 `packs/step/aos7_step.py:699`～`:707` 有啟動時的一圈。 | 「直譯器啟動時先推進一圈，之後每觀察到新的 tock 再推進一圈。」 |
| F34 | **回合三態的「其餘」範圍寫太大。** `proto7-2/spec.md:51` 把非 closed／不存在都寫成不知道，`:52` 卻另處理已知 open。 | 「明確 open:false 或確定不存在時可開新回合；明確 open:true 時先收尾；缺欄、型別不合或讀不到才是不知道。」 |

### 引用檢查中沒有發現問題的部分

已完成的靜態檢查涵蓋主要 11 份文件中的 **71 個 Markdown 相對連結**，目標均存在；其中實際使用的兩個片段錨點也核對到對應標題。

以下沒有列成缺陷：

- account → budget 已在 `packs/budget/README.md:3` 明示為改名背景。
- 各模組的「方案 6.1 第 1／2／3／9 點」仍能對應精簡方案。
- 「三個小出口」實際按三類分組：x、事實／事件、守門檔；不能只因出現四個識別字就判錯。
- step 的 CSV 與 backup 範例，在已读過的腳本與步驟表之間，未找到可直接證明的內部路徑錯誤；缺的是部署與入口說明。

## 四、術語表草稿

建議固定使用以下名稱。程式識別字可以保留，但首次出現時應加限定詞；尤其不要把不同層的同名欄位當成同一概念。

### 核心與控制

| 建議名稱 | 識別字 | 定義與容易混淆的地方 | 來源 |
|---|---|---|---|
| 空間根 | root | 一個 daemon 管理的根目錄，自己的狀態放在 `.aosd/`。 | `proto7-2/spec.md:25` |
| 節點 | node | 登記在 nodes.json 的資料夾；登記不等於資料夾已存在。 | `proto7-2/spec.md:26`～`:27` |
| 節點識別 | node id | 相對空間根的路徑；根節點用 `.`。 | `proto7-2/spec.md:26` |
| 空間路徑 | mounts 的 path | 相對空間根的路徑；不要與相對 node 的工作檔案路徑混用。 | `proto7-2/spec.md:185` |
| 時間線 | timeline | daemon 為每個 node 維持的 tick、等待、tock 排程。 | `proto7-2/spec.md:37`～`:44` |
| 回合 | round | node 內的一次 tick／tock 週期及其編號；不是任務執行次數。 | `proto7-2/spec.md:121` |
| 開回合動作 | tick | 判控制與任務表、啟動符合條件的任務，不等任務結束。 | `proto7-2/spec.md:152`～`:161` |
| 收回合動作 | tock | 提交總結、通知活任務、收尾並關閉回合；不等於所有任務結束。 | `proto7-2/spec.md:254`～`:260` |
| 任務項目 | tasks[] item | tasks.json 裡的一筆宣告；與槽、一次執行不是同一物件。 | `proto7-2/spec.md:131`～`:144` |
| 槽 | slot／tid | 可重用的任務資料夾；`AOS7_TID` 是槽名。 | `proto7-2/spec.md:194`、`:209` |
| 執行號 | run | 槽內這次執行的整數識別；同槽遞增。 | `proto7-2/spec.md:209` |
| 執行識別 | run id | `<槽名>#<run>` 字串，與整數 run 分開稱呼。 | `proto7-2/spec.md:209` |
| 執行包裝程序 | runner | `aos7-run`，負責起任務、等待並寫 pid／exit；不是任務本體。 | `proto7-2/spec.md:216`～`:218` |
| daemon 世代 | gen | daemon 啟動世代，用於排除舊 tick／tock；不是任務 run。 | `proto7-2/spec.md:85`～`:86` |
| 暫停擁有者標籤 | pause owner | 一個暫停理由／來源的標籤；全部標籤清空才開新回合。不是身分認證。 | `proto7-2/spec.md:78`～`:80` |
| 控制回條 | ctl-done | 控制請求的處理結果；不能一概當成任務工作已完成。 | `proto7-2/spec.md:68`、`:243` |
| 遺失結束紀錄 | lost | 依程序與檔案證據確認無法取得正常結束結果後的判定；不代表沒有外部副作用。 | `proto7-2/spec.md:233` |
| 疑似未啟動 | never_started | 根據 runner、pid、out.log 得出的事實標記，不是外部副作用不存在的證明。 | `proto7-2/spec.md:233`；`modules/once_retry/README.md:5` |
| 未知 | unknown／U | 證據不足，不能據此推定不存在、已結束或准許破壞性動作。具體停多大由該層契約決定。 | `proto7-2/spec.md:11`、`:18` |
| 指令檔路徑 | 核心 inst | 任務表中交给 aos-exec 的 inst JSON 路徑；與 step 工作實例無關。 | `proto7-2/spec.md:136` |

### step

| 建議名稱 | 識別字 | 定義與容易混淆的地方 | 來源 |
|---|---|---|---|
| 工作名稱 | job | 步驟表上的工作名稱；不是一次執行實例。 | `packs/step/spec.md:56` |
| 工作實例 | step inst | 一次工作的隨機識別；與核心 inst 指令檔完全不同。 | `packs/step/spec.md:56` |
| 目前步驟 | pc | 框架指向的下一個／目前處理步驟名稱。首次出現宜直接寫「目前步驟 pc」。 | `packs/step/spec.md:45`；`packs/step/aos7_step.py:436`～`:441` |
| 邏輯請求 | request | 某工作實例第幾次走到某一步；跨重送保持不變。 | `packs/step/spec.md:56` |
| 派工嘗試 | attempt | 同一 request 的一次派工；重送會增加 attempt。 | `packs/step/spec.md:56` |
| 派工步 | step run | 步驟表中啟動子工作的種類鍵，不是核心的整數執行號。 | `packs/step/spec.md:33` |
| 接續框架 | frame | 保存 pc、pending、已採結果與計數的接續狀態。 | `packs/step/spec.md:42`～`:59` |
| 工作結果檔 | result | step 採用結果的主要證據，存於槽外；不是核心 exit.json。 | `packs/step/README.md:31` |
| 冪等 | idempotent | 同一邏輯請求重做，不產生第二份應避免的效果；不等於程式只執行一次。 | `packs/step/spec.md:84`、`:94`；`packs/budget/README.md:42` |
| 有限工作 | finite | 作者宣告子工作會結束；檢查器要求宣告或耐性，不代表它能證明任務一定結束。 | `packs/step/spec.md:93` |
| 耐性 | patience | 以指定回合鐘計算的等待額度；必須同時說明起點、到期比較及是否重設。 | `packs/step/spec.md:83` |
| 重送 | resend | 同 request 建立新 attempt；不要與核心重播收尾、control restart 混稱重試。 | `packs/step/spec.md:84` |

### budget

| 建議名稱 | 識別字 | 定義與容易混淆的地方 | 來源 |
|---|---|---|---|
| 使用權 | grant | 固定內容的資格、額度與效期宣告，不是即時餘額。 | `packs/budget/README.md:24`～`:28` |
| 持有人 | holder | 使用權的持有人識別，由呼叫者自報；不是 pause owner 或 OS 帳號。 | `packs/budget/README.md:38`；`packs/budget/spec.md:96` |
| 業務鍵 | K | `(budget, holder, request)`，用來辨認同一筆業務操作；attempt、slot#run 不屬於它。 | `packs/budget/spec.md:39`；`packs/budget/README.md:42` |
| 業務鍵檔名識別 | kid | K 的雜湊縮寫，用於檔名；檔內另存完整 key。 | `packs/budget/spec.md:20` |
| 預算帳 | ledger | 保存餘額、預留、結算與去重證據的單一寫者帳。 | `packs/budget/README.md:30`～`:34` |
| 預留 | reserve | 從可用額移到在途額，尚不代表資源已支用。 | `packs/budget/spec.md:48` |
| 在途額 | inflight | 已預留、尚未依終局證據完成結算的額度。 | `packs/budget/spec.md:48`～`:49` |
| 資源入口 | gateway | 核對准入條件、呼叫後端並保存支用證據的組件。 | `packs/budget/README.md:36`～`:40` |
| 准入意圖 | intent | 呼叫後端前持久保存的准入紀錄；不是已支用或已結算的證明。 | `packs/budget/spec.md:59`～`:60` |
| 終局回條 | terminal receipt | 該層已確定且固定的結果；入口終局與帳的結算回條仍是不同階段。 | `packs/budget/README.md:39`；`packs/budget/spec.md:49` |
| 結算 | settle | 依入口終局證據，把在途額分成已用與退回可用。 | `packs/budget/spec.md:49` |
| 已完成回合鐘 | completed_tock | round 關閉取 round，仍開啟取 round−1；不是單純讀 round 整數。 | `packs/budget/spec.md:30` |

### adapt

| 建議名稱 | 識別字 | 定義與容易混淆的地方 | 來源 |
|---|---|---|---|
| 最新值轉接 | adapt | 抽樣來源最新值，經確定性鏈產生消費端輸出；不是完整事件傳遞。 | `packs/adapt/README.md:5`、`:33` |
| 依據版本 | basis | 本次轉換使用的來源物件版本及其雜湊、來源回合；不是上一輪輸出。 | `packs/adapt/spec.md:64`、`:96` |
| 轉換鏈 | chain | select、scale、threshold 組成的固定宣告與版本。 | `packs/adapt/spec.md:40`～`:44` |
| 最新值暫存器 | register／in 檔 | 覆寫保存最新輸出的 JSON 檔，不是硬體暫存器，也不是歷史佇列。 | `packs/adapt/spec.md:92`～`:104` |
| 輸出三態 | ok／unknown／absent | 值可用／目前無法提供可用值／來源確定不存在；不能直接套成核心或 budget 的狀態列舉。 | `packs/adapt/spec.md:73`～`:80` |
| 來源年齡 | age_src_rounds | 來源已完成回合鐘減去依據的來源回合，下限為 0；不是牆鐘秒數。 | `packs/adapt/spec.md:48`～`:50` |
| 漏取樣版數 | skipped | 依 seq 的向前跳號估算漏掉的來源版本數；沒有 seq 時不能推得。 | `packs/adapt/spec.md:84` |

建議在入口加一段共用提醒：

> 同一個識別字在不同層可能代表不同概念：本文以「核心 run／step run 步」、「核心 inst 指令檔／step 工作實例」、「pause owner／subd 擁有者／budget holder」區分。unknown 也必須連同所屬層閱讀，不能直接跨層傳遞語義。

## 五、做到一半、尚未驗完的部分

1. **step 補派窗口的完整後果。**  
   已確認「第三個 tock」缺前提，但尚未完整排除直譯器重起、結果檔先到、任務排序等條件，因此沒有確認重複派工或重複副作用。相關位置：`packs/step/spec.md:80`～`:81`、`packs/step/aos7_step.py:482`～`:519`。

2. **subd 成功 stop 但回條遺失的完整恢復路徑。**  
   已確認文件的「一定留回條」不成立，也確認 allowed_stop 依賴回條；尚未把所有停止時機、舊回條及生命週期紀錄組合逐一推演。相關位置：`modules/subd/aos7-subd:141`～`:204`。

3. **核心「不知道」總則的全部例外。**  
   已看到 `spec.md:11` 的保留現狀總則，與 `spec.md:262` 允許重建壞總結等特例需要更清楚交代；尚未完成全表分類，不將每個特例都判成實作錯誤。

4. **所有改寫句子的第二輪互審。**  
   已完成主要證據核對，但使用者要求立即停止時，五條子線尚未全部提交終局報告，交叉互審未完成。以上建議是文案草稿，尚未套回全文檢查重複或銜接。

## 六、沒來得及做，以及本次刻意不做的部分

- 未完成所有散文中的 S／P2／A2／A3／W／Q／K／N 編號逐一追溯；不能把 Markdown 連結全數有效，延伸宣稱所有歷史條號都正確。
- 未完成每一個範例從部署、環境、輸入檔到收尾的完整靜態操作清單。
- 未做全部 JSON 欄位型別、必要性、預設值的文件對照矩陣。
- 未完成所有候選發現與既有 problems／歷次審查報告的逐條去重，因此本報告不宣稱每條都是首次發現。
- **依唯讀限制，沒有也不應在本線執行範例、故障注入或測試。** 文中引用測試只表示已讀取其斷言，不表示本次跑過或通過。
- 沒有修改文件；所有修正文案與術語表均只存在於這份報告。