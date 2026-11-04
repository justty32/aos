**proto7-2 已能組出實用的小程式，但目前 README 還不足以讓新使用者順利完成部署與故障恢復；主要障礙是設定範本缺失、非同步操作的完成條件，以及不同包的重試語意，綜合評分為 5.4／10。**

## 1. 範圍與交付狀態

本次採主線加五條平行試玩線，只閱讀入口 `AGENTS.md`、`proto7-2/README.md`、`modules/README.md` 與各包 README。沒有閱讀 spec、notes、既有程式或測試原始碼；缺少的資訊透過 CLI help、公開 checker 與自己產生的執行結果摸索。

未修改 `/home/guanyu/projs/aos`，未 commit、未 push。自製程式與證據均放在：

```text
/tmp/claude-1000/-home-guanyu-projs-aos/8aa61430-d017-4079-b09f-02620d555dd9/scratchpad/burn/ws/packs-use/evidence/
```

以下路徑均相對於上述工作目錄的上一層 `packs-use/`。收到「立刻收尾」後，沒有再執行命令或讀取新檔。尚在進行的驗證，依最後已知狀態列在後文，沒有推定完成。

## 2. 已完成的小程式

完成了八種使用情境，另加一組跨包整合；不把 hello 算進數量。

| 小程式 | 已確認成果 | 重跑入口與證據 |
|---|---|---|
| 定時抓 HTTP CSV、轉換營收報表 | 首次產生台北 150／台中 80；經 HTTP 503、金額格式錯誤後，恢復產生台南 260／台北 10 | `python3 evidence/periodic_trial.py`；`evidence/periodic/result.json:5`、`:18`、`:24`、`:30` |
| 有稽核的發票匯出 | 匯出總額 230；寫進 sibling node 被標 `ok:false`，但不阻擋；root 外寫入不記錄，符合 README | `python3 evidence/audit_trial.py`；`evidence/audit/result.json:2` |
| 營運歷史取樣 | each 工作搭配 keep history；六回合後保留最近四回合，另取得 daemon 事件 | `python3 evidence/history_trial.py`；`evidence/history/result.json:1`、`evidence/history/transcript.jsonl` |
| CSV→換匯→發票報表的 step 流程 | 產生 `2 orders, TWD 1632.00`；完成失敗恢復、漏產物、重啟、unknown 重送及上限；另有最多重試一次的 fail 路由 | `python3 evidence/step/reproduce.py`；`evidence/step/normal-fixed.stdout.txt:18`、`explicit-fail-retry.stdout.txt:30` |
| 三 node 電子報預算 | research／editorial／quality 分配 3／2／1；最後已用 5、可用 1、在途 0；八次同鍵並行只扣一次 | `python3 evidence/budget/replay.py`；`evidence/budget/second-run.stdout:35`、`:75`、`:78` |
| 感測 node→風扇控制 node | 真 daemon 管理感測器、adapt 與消費者；完成正常更新、壞資料、停鐘、誤差帶、pause、restart、來源鐘倒退與修復 | `bash evidence/adapt/replay.sh`；`evidence/adapt/replay-final.log:156`；另見 `age-final.log`、`default-final.log` |
| 子 daemon 管三組訂單 worker | packing／billing／shipping 完成十五筆訂單、總額 900；stop、接回、回收、所有權拒絕、壞 life 恢復；最終 34／34 自製斷言通過 | `evidence/subd/rerun.sh`；`evidence/subd/final-run/result.json:1` |
| 訂單標籤服務＋一次性出貨 | restart 保留業務狀態；reload 套用新處理方式；舊 run 的 kill 不傷現役服務；20／20 自製檢查通過 | `python3 evidence/operations/trial.py`；`evidence/operations/runs/main-3/summary.json:1` |
| step→budget 跨包恢復 | 第一次已扣款但輸出失敗；修復後以同 request、新 attempt 完成，總共仍只扣一次 | `python3 evidence/budget/run_step_integration.py`；`evidence/budget/step-first.stdout:20`、`:21`、`:23` |

兩個重要界線：

- 三 node 預算是**部署者在外層固定分額**，不是 budget 內建跨 node 分帳。README 已明確排除跨 node、split 與動態配額。證據：`proto7-2/packs/budget/README.md:12`、`evidence/budget/run_trial.py:132`。
- HTTP 重試、風扇遇未知值時全速保護、worker 用 receipt 去重，都是自製應用政策，沒有冒稱框架自動提供這些保證。證據：`evidence/periodic_worker.py`、`evidence/adapt/fan.py:9`、`evidence/subd/worker.py:40`。

## 3. 五項評分

這是「只靠 README 的新使用者」評分，不是核心正確性或效能評分。

| 標準 | 分數 | 理由與例子 |
|---|---:|---|
| 容易上手 | **4／10** | 基本 daemon 能起來，但三個上層包缺完整設定範本。step 在第一份有效表前有 11 次失敗 checker 呼叫；adapt 到第 19 次猜測才成功。證據：`evidence/step/REPORT.md:41`、`evidence/adapt/discovery.log:446`。 |
| 容易理解 | **6／10** | 契約卡能說清職責與界線；但 failed／unknown、不同時鐘、不同層級的完成條件沒有串成操作模型。跨包 unknown 落差已實測。證據：`proto7-2/packs/budget/README.md:42`、`evidence/budget/step-first.stdout:9`、`:13`。 |
| 複雜的藏起來 | **7／10** | 同鍵並行、結果持久化、重啟接續與新代前回收，確實能由包處理；事故修復仍會把框架、槽、程序身分等細節交回操作者。證據：`evidence/budget/second-run.stdout:35`、`evidence/step/restart-first.stdout.txt:32`、`evidence/subd/corruption/transcript.jsonl:40`。 |
| 外層控制結構簡單但全面 | **6／10** | 任務、argv 包裝、工具三種接法一致，正常控制可組合；但單一成功回覆或 diag 輸出不足以判定整個工作已完成／健康。證據：`proto7-2/modules/README.md:7`、`evidence/subd/removal/transcript.jsonl:25`、`evidence/operations/runs/main-3/transcript.txt:140`。 |
| 要背的少 | **4／10** | 要記 root／node／slot、run／request／attempt、owner、回條位置、三種時間政策及恢復差異。目前缺可直接使用的操作卡。證據：`proto7-2/modules/tools/README.md:28`、`:30`、`proto7-2/packs/adapt/README.md:25`、`evidence/step/REPORT.md:49`。 |

## 4. 已確認、最值得先處理的發現

### 4.1 三個上層包都缺第一份可直接使用的設定

- **step**：README 給 keep 任務接法，卻沒有 `steps.json` 範本；必須從 checker 學到 steps 是物件、run 是 argv 陣列、成功邊叫 `ok`、有限命令需宣告 `finite` 等。
- **adapt**：README 列出 select／scale／threshold，卻沒有完整鏈宣告；`q`、`as` 等欄位是從錯誤訊息摸索出來。
- **budget**：README 列「預算、持有人、額度、時鐘」等概念，沒有完整 grant JSON，也沒有明講 `grant.budget` 必須等於資料夾名稱。

這不是「照 README 一次成功」。checker 有幫助，但不能取代入門範本。

**證據：**

- `proto7-2/packs/step/README.md:10`、`:11`、`:14`；`evidence/step/probes/minimal-valid.json:1`、`evidence/step/REPORT.md:41`。
- `proto7-2/packs/adapt/README.md:10`、`:14`、`:34`；`evidence/adapt/guess-19.json:1`。
- `proto7-2/packs/budget/README.md:26`、`:46`；`evidence/budget/discovery.jsonl:2`、`evidence/budget/first-run.stdout:2`。

**建議：** 每包先提供一份完整有效設定、完整啟動命令、預期輸出與停止方式，再接契約卡和進階規則。

### 4.2 step 的普通 `resume` 可能重做非冪等工作

獨立試驗明標 `idempotent:false`，worker 在失敗前追加一筆本機通知。失敗結果已被接受、`pending:null`、沒有 fail 分支時：

| 操作 | 實際結果 |
|---|---|
| 第一次執行 | 通知次數 1，code 17 |
| 普通 `resume`，**沒有 `--resend`** | 同 request、新 attempt，再執行一次 |
| 第二次成功 | 通知次數變成 2 |

相對地，結果仍 unknown、pending 保留時，普通 resume 只重新檢查；需要 `--resend` 才重派。

**證據：** `proto7-2/packs/step/README.md:38`；`evidence/step/nonidempotent-proof.stdout.txt:2`、`:3`、`:4`、`:5`；對照 `evidence/step/unknown-first.stdout.txt:31`、`:38`、`:39`。

**重現：**

```sh
python3 evidence/step/reproduce.py nonidempotent-failure
```

**建議：** 在 resume 指令旁直接列出 failed／unknown 的不同動作，明寫「已接受的 failed 結果可能由普通 resume 重新執行，即使 idempotent:false」。這是已確認的公開行為與文件缺漏；未讀 spec，因此不直接判定為執行器違約。

另外已寫成有限次 fail 路由，不需人工恢復、最多呼叫兩次；但兩個不同 step 會產生不同 request，不能拿來當同鍵去重。證據：`evidence/step/explicit-fail-retry.stdout.txt:30`、`evidence/step/REPORT.md:33`。

### 4.3 budget 的退出碼 3，不代表「預留一定還留著」

故意讓 `--out` 指向目錄：

1. 後端已受理。
2. 帳已結算，`inflight=0`、`used` 已增加。
3. 輸出失敗，call 回傳 3、`stage:io`。
4. 修復後沿用同 K 重送，只補輸出，沒有再扣款。

README 的「3＝未知，預留留著」過於絕對。

**證據：** `proto7-2/packs/budget/README.md:42`；`evidence/budget/output-fault.stdout:7`、`:9`、`:10`、`:12`；重現腳本 `evidence/budget/run_faults.py:72`。

**建議改文：** 退出 3 表示本次呼叫未完整交付終局結果；交易可能未預留、仍在途，或已結算但輸出失敗。先查指定 K 的 status，修復後沿用同 K、同內容重送。

### 4.4 budget unknown 與 step unknown 是不同事情

跨包實測：

- budget 正常退出 3，會產生一份有效的 step 結果。
- step 因此判為 **failed**，不是「結果不明」的 unknown。
- 設了 `on_unknown:resend` 也不會自動重送這次失敗。
- 人工修復並 `resume --resend` 後，同 request 的 a2 成功，仍只扣一次。

**證據：** `proto7-2/packs/budget/README.md:14`、`:55`；`proto7-2/packs/step/README.md:22`；`evidence/budget/step-first.stdout:9`、`:13`、`:20`、`:23`。

**建議：** 在 budget 的 step 接法旁放一張對照表，分開「step 沒拿到結果」與「拿到 budget code 3 的失敗結果」。

### 4.5 budget 示範資源的「次數」與 `--amount` 不一致

README 說每個業務請求預留一次；實際 `--amount 2` 被接受並扣二，但後端只增加一次受理。

獨立重現最後得到：**兩個業務請求、`backend.accepted=2`、`ledger.used=3`**。帳仍平衡，但不能把 used 直接當 API 受理次數。

**證據：** `proto7-2/packs/budget/README.md:13`；`evidence/budget/units-repro.stdout:9`；`evidence/budget/run_faults.py:97`。

**建議：** 明確選擇「次數」或「加權成本」；前者限制 amount=1，後者改寫 README 的單位定義。

### 4.6 子空間「永久移除」流程可能留下仍在工作的 worker

精確照 README 操作：

1. 對允許 stop 的子 daemon 送普通 stop。
2. 等 `stopped.json`。
3. 移除父 tasks.json 的該項。
4. 再停止父 daemon，包含 `--kill`。

三個 worker 仍存活，心跳繼續更新。

這符合 README 另一段「普通 stop 保留任務」，但與「永久拿掉子空間」的直覺衝突。

**證據：** `proto7-2/modules/subd/README.md:66`、`:77`；`evidence/subd/removal/transcript.jsonl:20`、`:25`、`:26`。試驗最後已精準清理自身殘留，見同檔 `:30`。

**建議：** 永久停工的範例直接寫对子根 `stop --kill`，分開「只停排程器」與「連 worker 一起停止」。

此外，父 task kill 回成功也不代表子樹已空；來不及收完的 worker 可能要到下一次起包前才回收。證據：`proto7-2/modules/subd/README.md:75`、`evidence/subd/lifecycle-rerun/transcript.jsonl:23`、`:27`。

### 4.7 成功回覆、回合前進、diag 空提示，都不是完整健康判斷

已確認：

- 原 quickstart 背景啟動後立即 cat，三次都遇到檔案尚未產生。
- `paused_by` 已有 owner，仍可能處於 `pause_pending:true`。
- pause 停 tick／tock，**已啟動 worker 仍可寫入**。
- 壞 tasks.json 可讓回合繼續前進；錯誤在 `last-round.tasks_error`，diag 的 `uncertain`／`hints` 仍為空。
- `ctl add` 接受合法 JSON、回 wrote，不代表項目 schema 已通過。

**證據：** `evidence/core/quickstart.jsonl:3`、`:11`、`:19`；`evidence/step/pause-diagnosis.stdout.txt:30`；`evidence/operations/runs/main-3/transcript.txt:64`、`:140`、`:174`；對照 `proto7-2/modules/tools/README.md:23`、`proto7-2/modules/diag/README.md:46`、`:68`。

已做一份有界等待「hello 真正成功」的改寫範例：

```sh
sh evidence/hello_readme_recipe.sh
```

成功輸出見 `evidence/hello-readme-recipe.log`。第一版草案只等回合完成，也曾錯把仍 alive 的 hello 當完成；原始失敗保留在 `evidence/hello-readme-recipe-first.log`，沒有算成產品 bug。

## 5. README 讀完仍卡住的完整清單與改法

以下合併不同試玩線遇到的重複卡點；重要行為已在上一節展開。

### 共通入口與工具

| 卡點 | 建議改法 | 證據 |
|---|---|---|
| quickstart 沒等待啟動／工作完成 | 加有逾時的等待與預期產物，不能只加固定 sleep | `proto7-2/README.md:31`；`evidence/core/quickstart.jsonl:3` |
| `<槽>`、cwd、node-id 與 node 路徑要自己猜 | 一張目錄樹，附可直接執行的 restart 範例及 AOS7_* 範例值 | `proto7-2/modules/tools/README.md:30`、`:43`；`evidence/periodic/transcript.jsonl:4` |
| 知道要「看回條」，不知道完整位置與等待條件 | 列 daemon／task 回條路徑，分清 wrote、回條與最終狀態 | `proto7-2/modules/tools/README.md:23`、`:33`；`evidence/operations/REPORT.md:34` |
| each／keep／once 的選擇與預設不集中 | 加模式、重跑時機、非零退出處理的三列對照表 | `proto7-2/README.md:20`、`:29`；`evidence/history/transcript.jsonl` |
| 想改定時週期，找不到設定位置與範本 | 補最小 node 設定、預設值、變更何時生效 | `evidence/core/readme-discoverability.txt:1`；`proto7-2/README.md:20` |
| task_env／wait_tock 缺回傳型別與完整 loop | 放最短 Python 發布／等待範例，列 timeout 回傳值 | `proto7-2/modules/tools/README.md:41`；`evidence/core/wait-tock-timeout.json:1` |
| history 有概念，缺完整任務項與旗標說明 | 提供 tasks.json、說清 out 是目錄及產生檔名 | `proto7-2/modules/README.md:24`；`evidence/history_trial.py` |
| 入口先導向 spec／設計歷史，使用流程太薄 | 把首個成果、觀察、停止放最前面；維護者資料後移 | `proto7-2/README.md:7`、`:24`、`:38` |

### step 與 budget

| 卡點 | 建議改法 | 證據 |
|---|---|---|
| steps／grant 缺完整格式；名稱限制需試錯 | 放已驗證的最小 JSON，列欄位、預設、識別字限制及 budget 資料夾對應 | `evidence/step/REPORT.md:41`；`evidence/budget/discovery.jsonl:2`、`first-run.stdout:2` |
| 普通 resume 是否重做不清楚 | failed／unknown／restart 分別列出 request、attempt 與副作用 | `evidence/step/nonidempotent-proof.stdout.txt:2` |
| code 0、ok false，status 沒列缺什麼產物 | status 帶 missing 與結果檔位置；README 區分 code 與產物檢查 | `evidence/step/artifact-first.stdout.txt:22` |
| pause 的完成邊界不明 | 寫明 phase=paused、pause_pending=false；已起工作不凍結 | `evidence/step/REPORT.md:79` |
| status／close 的退出碼、歷史 error 未說明 | 加退出碼表；error 是最近錯誤，需合看 phase／halt | `evidence/step/REPORT.md:85`、`:87` |
| fail 路由與 resend 的 request 範圍不同 | 範例明寫不同 step 是不同 request，不保證同鍵去重 | `evidence/step/REPORT.md:33` |
| budget 的次數／amount 單位不清 | 限制 amount=1，或改成加權成本契約 | `evidence/budget/units-repro.stdout:9` |
| budget code 3 可能已結算 | 增加查指定 K、同 K 恢復的完整步驟 | `evidence/budget/output-fault.stdout:7`、`:9` |
| 兩包 unknown 意義不同 | 在跨包範例直接放失敗路由與恢復對照 | `evidence/budget/step-first.stdout:9`、`:13` |
| budget status 有 error 卻退出 0 | 列錯誤 JSON，不能以 shell 成功碼當健康 | `evidence/budget/replays/20261005T014229.179402Z/fault-recovery.stdout:33` |
| 同 request 重送還必須維持同內容 | 在 call／恢復範例提醒 amount、resource、payload 不可暗改 | `evidence/budget/faults-second.stdout:7`、`:9` |

### adapt

| 卡點 | 建議改法 | 證據 |
|---|---|---|
| 沒有鏈宣告 JSON | 放 select／scale／threshold 的完整範例與欄位表 | `evidence/adapt/guess-19.json:1` |
| 空間根／node／槽內掛載三種路徑混用；mount_allow 沒設定例 | 用兩 node 目錄樹標清基準、預設與最小放行方式 | `proto7-2/packs/adapt/README.md:10`、`:20`；`evidence/adapt/pilot.log:238` |
| patience／stall／max_age 缺逐回合邊界例 | 展示哪一回合 held、哪一回合 unknown，以及各自使用的時鐘 | `evidence/adapt/run-1.log:16`、`:57`；`age-final.log` |
| reset 等結果只有概念，缺輸出字典 | 列 ok／held／unknown／absent／reset，含 why、src_state、last.void | `evidence/adapt/reset-fixed.log:17` |
| 「那一欄 null」容易理解成部分 value 可用 | 明寫 trace 判定為 null 時，對外整個 value 也為 null | `proto7-2/packs/adapt/README.md:26`、`:36`；`evidence/adapt/run-1/events.jsonl:64` |
| 缺欄只有 select_missing，沒有欄位名稱 | detail 附 select 路徑與步號 | `evidence/adapt/run-1/events.jsonl:28` |
| status 的「宣告讀不到」無解析後路徑 | 印實際路徑與 cwd 提示，給完整 cd＋status 範例 | `evidence/adapt/checker-trials.log:172` |
| 消費者需要等 my_round，不能與 adapt 同等 tock 後直接讀 | 保留現有提醒，再加可貼上的最小消費 loop | `proto7-2/packs/adapt/README.md:35`；`evidence/adapt/fan.py:9` |

### subd 與日常操作

| 卡點 | 建議改法 | 證據 |
|---|---|---|
| subd 範例用 bare executable，下一段才說不在 PATH | 範例直接使用正確絕對路徑 | `proto7-2/modules/subd/README.md:31`、`:35` |
| 缺完整父、子、worker 建表範例 | 補包含登記、執行與清理的兩 worker 範例 | `evidence/subd/FIRST_LOOK.md:6`、`evidence/subd/run.py:150` |
| 首句「kill 帶走整棵」比後文實際保證強 | 第一段就寫明可能延到下次起包前回收 | `proto7-2/modules/subd/README.md:5`、`:75`；`evidence/subd/lifecycle-rerun/transcript.jsonl:23` |
| 永久移除沒有明寫 --kill | 分開停止排程器與整群停工 | `proto7-2/modules/subd/README.md:77`；`evidence/subd/removal/transcript.jsonl:25` |
| 正常 stopped marker 會表現為 keep code 1，log 又會換 run | 說明這是預期拒絕重起；提供先暫停、保存證據流程 | `proto7-2/modules/subd/README.md:73`；`evidence/subd/lifecycle-rerun/transcript.jsonl:56` |
| 壞 life 修復要求「確認前代程序」，但沒有現成工具 | 提供唯讀列出子根程序的工具／命令，及精確恢復步驟 | `proto7-2/modules/subd/README.md:61`；`evidence/subd/corruption/transcript.jsonl:36`、`:40` |
| 正常操作與兩把鎖、life、since 等細節交錯 | 前面放 stop／stop --kill／重起三列操作卡，內部恢復後移 | `proto7-2/modules/subd/README.md:48`、`:55`、`:59` |
| pause 容易被理解成所有任務都停寫 | 明寫只停排程與控制，已起任務仍運行 | `proto7-2/modules/diag/README.md:46`；`evidence/operations/runs/main-3/transcript.txt:64` |
| once_retry 名稱易被當成一般失敗重試 | 第一段直接寫「不重試 runtime 非零退出」，並附完整兩項任務表 | `proto7-2/modules/once_retry/README.md:5`、`:20`；`evidence/operations/runs/main-3/transcript.txt:17` |
| add 成功不是 schema 驗證成功 | 用法旁說明下一回合看 tasks_error | `evidence/operations/runs/main-3/transcript.txt:174`、`:178` |
| diag 空提示容易被當健康 | 同時提示／彙整 tasks_error、skipped 與任務 out.log | `proto7-2/modules/diag/README.md:68`、`:69`；`evidence/operations/runs/main-3/transcript.txt:140` |
| CLI help 不一致 | daemon/subd 補完整 help；diag 不要把 --help 當 root 回空 nodes | `evidence/operations/help/09.txt:1`；`evidence/subd/FIRST_LOOK.md:8` |

## 6. 故意弄壞後，錯誤訊息好不好懂？

| 故障 | 評價 | 證據 |
|---|---|---|
| reload 的 argv 是字串 | **很好**：指出欄位、錯值，並說「沒做（沒 kill）」 | `evidence/operations/runs/main-3/transcript.txt:192` |
| 舊式頂層 retry_lost | **很好**：給替代寫法、需要另跑 retry 任務，以及 README 路徑 | `evidence/operations/runs/main-3/rounds.jsonl:15` |
| budget 額度不足 | **很好**：直接列可用 0 小於需要 1、拒絕階段 | `evidence/budget/second-run.stdout:59`、`:60` |
| subd 位置錯誤／重複認領 | **好**：短、指出衝突位置，且沒有啟動下游 argv | `evidence/subd/ownership/duplicate-out.log:1`、`outside-owner-out.log:1` |
| step 設定型別錯、非冪等自動重送 | **好**：有 step／rule／why，無 traceback；能逐步修正 | `evidence/step/probes/check-run-wrong-type.stdout.txt:1`、`check-unsafe-auto-resend.stdout.txt:6` |
| birth.json 半寫 | **很好**：diag 指出不確定原因，提醒先核對活程序與 once 副作用 | `evidence/operations/runs/main-3/transcript.txt:223`、`:233` |
| step 漏交產物 | **偏弱**：只看到 code 0、ok false，沒列 missing | `evidence/step/artifact-first.stdout.txt:22` |
| adapt 缺來源欄位 | **偏弱**：select_missing 可分類，但不知道缺哪個欄位 | `evidence/adapt/run-1/events.jsonl:28` |
| budget 輸出寫失敗 | **偏弱**：有 stage:io／IsADirectoryError，缺路徑及可能已結算的提示 | `evidence/budget/output-fault.stdout:7` |
| 對不存在槽 kill | **偏弱**：`birth.json None…用 --run 指定`，不如直接說槽不存在 | `evidence/operations/runs/main-3/transcript.txt:110` |

## 7. 完整測試與獨立重跑

執行了指定入口：

```sh
python3 proto7-2/tests/run_all.py
```

**初跑結果：364 項，9 項失敗，耗時 1299.739 秒。** 證據：`evidence/baseline-tests.log:124`、`:126`。

共用機器當時負載很高：一次紀錄的 load average 為 135.66；後續獨立重跑時仍約 71～87，回報 CPU 數為 8。證據：`evidence/host-load.txt:1`、`evidence/isolated-core-tests/results.jsonl`、`evidence/adapt/isolated-tests/results.jsonl`。**獨立重跑不等於整台機器沒有其他負載。**

截至收尾前，九項初跑失敗的重跑結果如下：

| 測試 | 獨立重跑結果 |
|---|---|
| `test_old_run_leftover_not_taken_as_new_run` | **仍失敗**：預期一個 PID，觀察到兩個 |
| `test_keep_runner_before_exit` | 通過 |
| `test_reaped_before_new_daemon` | **仍失敗**：預期 owner run 2，重跑觀察到 4 |
| `test_fast_source` | **仍失敗**：來源回合增量未滿足每次都大於 1 |
| `test_same_rate` | 通過 |
| `test_slow_source` | **仍失敗**：重跑已收滿資料，但同 seq 最長連續 2 次，斷言要求至少 3 |
| `test_pause_stall_3` | 通過 |
| `test_pause_stall_null` | 通過 |
| `test_source_rebuilt` | 通過 |

重跑入口與紀錄：

```sh
python3 evidence/rerun_baseline_failures.py
python3 proto7-2/tests/run_all.py -v -k <測試名稱>
```

- 核心／subd：`evidence/isolated-core-tests-run.log:1`、`:2`、`:3`，各列包含完整輸出檔位置。
- adapt：`evidence/adapt/isolated-tests/results.jsonl` 及同名 `.log`。
- 初跑各失敗定位：`evidence/baseline-tests.log:3`、`:19`、`:33`、`:44`、`:53`、`:68`、`:83`、`:95`、`:110`。

**不能宣稱全綠，也不能把剩下四項全部歸為負載問題。** 已確認它們在單項重跑仍會失敗；原因未以源碼或安靜環境進一步釐清。adapt 的兩個速率斷言目前沒有提供數值轉換錯誤證據。

## 8. 做到一半、尚未驗完

1. **adapt 的 `test_long_run_file_count` 獨立重跑。**  
   最後已知仍在執行。它是額外 adapt 單包初測的失敗項，不在主線九項失敗內。未取得完成結果，不算通過。證據入口：`evidence/adapt/package-tests.log`、`evidence/adapt/isolated-tests/`。

2. **once_retry 的真實 never_started 正向補跑。**  
   已用真 SIGKILL 命中 birth→runner 間隙；直接 tick／tock 曾持續顯示「剛起」。後來 daemon 接管能報 `lost:true, never_started:true`，因此沒有把先前觀察當作產品 bug。加上已運行 retry keep 的完整正向恢复，最後仍在補驗。證據：`evidence/operations/runs/daemon-recovery-1/transcript.txt:10`、`evidence/operations/once_lost_trial.py`。

3. **最終全部檔案與行程查核。**  
   budget、step、subd 及 operations 主情境各有自身清理紀錄；但收到立刻收尾指示後，沒有再做整體行程掃描或前後 manifest 比對。因此不宣稱最後時刻整條線完全沒有仍在執行的測試行程。

4. **整合版一鍵入口的最後整串重跑。**  
   budget 原四種情境已串跑，後加的 step 整合已獨立成功，但沒有再次把五項完整串跑。adapt 的主情境、age、default 分別成功，曾修正 replay shell 的編輯問題；不把分段成功冒稱最終 shell 整串重新跑過。證據：`evidence/budget/REPORT.md:13`、`evidence/adapt/replay-final.log:156`、`age-final.log`、`default-final.log`。

## 9. 沒有完成、也沒有宣稱驗證的範圍

- 未在安靜主機條件下重驗仍失敗的四項測試。
- 未做真實外部 API、任意外部副作用的 exactly-once 驗證；budget 使用的是其假後端。
- 未驗證 budget 的所有到期、取消、退役、時鐘倒退與每個持久化 crash 點。
- 未驗證第二層巢狀 subd、所有 `/proc` I/O 故障及牆鐘倒退。
- 未做 Python 3.11 或其他作業系統矩陣；本次實際 Python 為 3.12.3。
- 未修改產品程式或產品 README。改善草案只在 `evidence/README-improvement-proposal.md`，已跑通的 quickstart 改稿在 `evidence/hello_readme_recipe.sh`。

完整分線報告已保存於：

```text
evidence/core/REPORT.md
evidence/step/REPORT.md
evidence/budget/REPORT.md
evidence/adapt/REPORT.md
evidence/subd/REPORT.md
evidence/operations/REPORT.md
```

若依本次證據安排改善順序，應先補三包可執行範本，再補 step resume、budget code 3／跨包 unknown、subd 永久停工的精確說明，最後統一等待完成與診斷入口。這幾項能直接減少已實際發生的試錯與操作誤解。