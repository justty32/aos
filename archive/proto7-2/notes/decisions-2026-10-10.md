# 2026-10-10 頂層代定清單

← [前一天](decisions-2026-10-09.md)｜[catch-up](catch-up.md)

一行一條，格式比照 [decisions-2026-10-09](decisions-2026-10-09.md)：級別（A＝大、B＝中、C＝小）或結果／決定／出處。

## 結果

- 證明｜AP5：學徒自我改進 A／B 對照（luna 6×2、sol-low 5×2，4 題郵局慣例題、每題最多 5 輪；293 次真 AI、約 197 萬 token）→ 讀自己技能書的 B 組第 2～4 題平均輪數 luna 2.78→1.33、sol-low 2.33→1.40，大於題 1 雜訊（0.83、0.20）；一次過 A 0/33、B 21/33；兩模型 B 每一次都比 A 每一次好（排列檢定 p＝0.001／0.004）。限制：4 題的坑相同，證的是「同一種坑記得住」。分支 loop13/AP5 已 rebase、全套綠 → [apprentice-5](play/2026-10-09-real-ai/apprentice-5.md)

## loop14 FX1（修 astra-8 建議順序前四項）

- C｜A10-01：核心起任務的環境照舊只帶核心六個 `AOS7_*`，另**明列放行 `AOS7_LITELLM_KEY`** 一個（`lib/aos7_task.py` `TASK_ENV_ALLOW`）；不走「up.json 存金鑰」，因為秘密不能落地。金鑰只跟起 daemon 的環境走，要換金鑰得 stop 後從新環境重起 → `modules/up/ADVANCED.md`「要真 AI」段
- C｜A10-01 延伸：llmcall litellm 傳輸送出前驗金鑰字元，不合法就不送、當 rejected 退 1；其他傳輸例外的 why 只留例外型別名、不含原訊息（避免經例外 repr 進 out.log）→ `packs/llmcall/spec.md`
- C｜A10-02：`owe` 存不進 paused.json 就不開這一回合，等 POLL 回頂端重試（不確定寧可少跑）；`round_done`、`op_pause`／`op_resume`、`_save_paused_quiet`、`reap`／`sweep_leftovers` 的同型「存失敗照記憶體繼續」只盤點未修，留下一輪
- C｜A10-03＋B10-11：新增 `packs/llmcall/aos7_llmcall_exit.py` 當呼叫方共用的退出碼對照；退 4 只表示帳未清，答沒答成看回條 `outcome`。compact：答到（0／4＋answered）收摘要、確定失敗（1／2 或 4＋非 answered）退 1、3／未知退 3，pending 都留著
- C｜B10-11：author 收到 llmcall 1（模型拒答）或 2（作者自己組的請求被拒）都歸「確定沒做成」退 1，不再退 2；拒答不自動升級模型重送；本地用法錯仍退 2
- C｜brain／skills／author 一律用共用 `answered(rc, receipt)` 判斷「答到了」；brain 遇 llmcall 未知退出碼（不在 0～4）當不確定，保留同一筆請求等接續，不當失敗
- C｜A10-09：`aos7-ctl` 用法錯退 2 附例子、讀寫故障／Unknown／未預期例外退 3 一行（以前 1）；`notes/problems.md` G1 那列已加註；restart 失敗回條加 `outcome: unknown|refused` 欄位（只加不改），ctl 據此未知退 3、確定拒絕退 1
- C｜A10-11：照 10-09 L4 決定，前導零索引照收（4301 個 0＝索引 0），去前導零後仍超長才退 125
- C｜B10-01：error_path.json 補齊 12 支入口（共 29 支現役入口全登記）；凍結核心 tock／daemon／run／wait-tock 與退出碼透傳的包裝器用 exempt 寫理由；新增防漏列檢查
- C｜B10-02：error_path 檢查器把 HOME、XDG_*_HOME、TMPDIR 隔離到暫存區並納入不留檔快照，`--help` 也檢查不留檔；`__pycache__` 不例外（檢查器設 PYTHONDONTWRITEBYTECODE）

## loop14 FX2（daemon 存檔失敗不推進，接 FX1 A10-02 盤點）

- C｜`round_done` 改交易式：用複本算新 owe／steps／paused，paused.json 寫成功才換進記憶體；失敗記憶體全不動、回 False（磁碟留舊 owe，重開照 N-06 結算一次，不會雙扣）
- C｜時間線：結算失敗記 `settle_pending`（記住該扣或不扣），回頂端先重試、落盤前不走 `mark_owe`／tick（否則新回合號蓋掉舊 owe＝少扣多跑）；tick 失敗的半回合恢復時沿用 pending 的「不扣」
- C｜`mark_owe` 寫失敗改還原原值（以前一律 pop，會丟掉未結算的舊 owe）
- C｜`op_pause`／`op_resume` 交易式：寫不進回條 ok:false「沒有改；請重送」、記憶體不動、resume 不 wake（以前丟例外→無回條、效果卻已在記憶體生效）；上一回合結算還沒落盤時也先拒（免得重試扣到新額度）
- C｜`_save_paused_quiet`（unregister、node 消失拿掉倒數）失敗設 `_paused_dirty`，`check_nodes` 每圈補寫、停機前再補一次
- C｜`reap`：回收意圖沒寫進 nodes.json（或還有待補寫）就不起收任務的 thread、記 `reap-deferred`，已知 pgid 保留；補寫成功後回收迴圈照起，舊時間線還沒結束也照起（舊線結束後照舊再掃一次）。停機帶 kill 仍照身分掃全部 node
- C｜`sweep_leftovers`：held 意圖寫不進時每 0.1 秒重試、最多約 2 秒，仍失敗印一行 stderr＋事件後照常退出（不卡、不改退出碼）
- 留著｜起動時 `save_paused`／`save_nodes`／`gen.json` 寫失敗仍是未捕捉例外（traceback、退 1）：要改就得定新退出碼，屬退出碼契約，不在本輪範圍
- 留著｜停機時回收意圖重試 2 秒仍寫不進＝重開後不會續收（只剩 stderr 一行）；沒有別的落盤處可放，要不要「寫不進就不退出」是方向問題
- B｜頂層（使用者說「隨意」）：FX2 遺留兩題照頂層建議——① 啟動時存檔失敗不另立退出碼，維持退 1；② 關機前回收意圖重試約 2 秒仍寫不進就印一行照常退出（寧可下次漏收，不卡住）；pause 存不進回 ok:false 請重送（同 register）照收

## loop14 MN1（選單核心＋玩具選單，blueprint-scaffold1 §7 第一線）

- 結果｜新包 `packs/menu/`：`aos7-menu run <node> <menu.json> [--llm M|--reply F]`＋`status`；純函式 `step`／`after`、選單驗證、五種格子檢查、先存 state 再呼叫、工具目錄 `tools.json`（argv 不經 shell）；玩具 `examples/hello/` 由 astra 寫。真 AI：luna／luna-low 各 5 次走 hello 10/10 退 0、0 次重問、每次 2 呼叫約 3.5k token → `packs/menu/spec.md`
- 結果｜hello 第一版（第一層只問「回給誰」、沒附來信）真 AI 10/10 都選出口；改成把兩封短信寫進該層 ask、第二層用 `set` 帶對方那句後 10/10 過。教訓：每次呼叫是單獨一問，選單作者要把「做這層決定所需的資訊」放進這層，不然笨模型照實選出口
- C｜使用者「每層 2～5 個編號選項」解讀為**含出口**的顯示編號；沒有 `when` 的層靜態檢查，有 `when`／`from` 的層顯示時檢查。藍圖 §3 範例 `which` 層（5 檔＋出口＝6）會被擋，MN2 要改形（例：已交的檔用 `when: new:` 藏起、交齊再顯示「都交齊了」）
- C｜只有格子、沒有 options 的層＝隱含選項「交出這一格」＋出口，仍走 `選：N`／`格：` 回法（藍圖 write 層沒寫出口，改為每個問的層都必有 exit）
- C｜llmcall `--call` 名不能有 `/`：一律 `menu-`＋sha256(nonce + "\n" + call_id) 前 32 碼；log／state 仍記藍圖的 `menu/<run>/<層>/<第幾次>`
- C｜`step` 不做 I/O：寫檔與工具由驅動做，結果經 `after()` 餵回；工具與寫檔先存 pending 再做，被殺重跑會再做一次（登記的工具要能重跑）
- C｜練習用的 AI＝選單旁 `practice.json` 第 k 句（k＝本 run 第幾次呼叫，被殺重跑拿同一句）；grant gateway 是 llm.fake 時也送這句，測試可數真送次數
- C｜為 MN2 先備的功能（MN2 不能改 aos7_menu.py）：`--var`／`--brief`／`--run`、選項 `when`（required_done／required_missing／`new:<模板>`）、`options: {"from":"done","only":[…]}`、層 `show`（改檔時附那檔）、做事層 `ok`／`fail`／`max_rounds`、工具退 0／1 都把一行 JSON 合進變數（只清 var_owner 仍歸該工具的鍵，set 覆寫移除歸屬、字串截 600 字）、`required`／slot prefix／sections 可用模板
- C｜帳任務沒在跑＝退 1 但不記停下（起好照原樣再跑接續）；llmcall 退 1／2 記停下退 1（同 FX1 B10-11）；llmcall 退 4 記 journal、命令結束最多一行提醒
- C｜寫檔安全：out/ 或任一段是符號連結拒寫退 2；暫存檔同資料夾隨機名 `O_EXCL|O_NOFOLLOW` 再 rename；run 鎖不等待，忙退 3
- C｜state 多 `journal`（log.jsonl 每次照它重寫，被殺在 rename 後也不漏行）、`initial_vars`、`var_owner`（每鍵目前歸屬）、`nonce`（新 run 隨機 16 hex）、`fence`、`code`；journal 隨步數長，hello／aos-tool 量級（≤百步）不處理
- C｜工具目錄範例登記 `gates-check`、`skills-pick`、`ctl-help`（aos7-ctl 沒有唯讀子命令，只登記 `daemon --help`）；格式是「名字→argv 模板＋參數＋輸出」，之後加抽屜／寄信這類標準工具只是多幾列，不擋
- 待｜MN2 可開（AP5 已進 main，MN1 進 main 後）；MN3 等 MN2；MN4（README／ADVANCED／新手）MN1 進 main 後可與 MN2 並行

## loop14 MN4（menu 包文件＋新手試用，blueprint-scaffold1 §7）

- 結果｜`packs/menu/README.md`（新手：4 詞、2 指令跑 hello、沒跑成／停下／重走）與 `ADVANCED.md`（寫選單的人：契約卡、menu.json 三種層、2～5 編號含出口、「這層決定要的資訊放這層」、格子五種、回法、practice.json、`--reply`／`status --prompt`、tools.json 登記、status、中斷重跑、`--llm` 經 aos7-up 起真 AI node、退出碼）；INDEX 那列改連兩份、code map 補一句 → [play 總表](play/2026-10-10-menu/README.md)
- 結果｜新手三輪：luna 8.6／8.6／8.8、Haiku 5.4／5.6／6.4，五題兩人每輪全對、2 指令、README 列 4 概念；第 3 輪過「五題全對＋較差者 ≥6 且 luna ≥7」
- C｜真 AI 的 README 外路徑寫成「`aos7-up <node> --model M -d` 起 node（帳一起裝好）→ `aos7-menu run <node> … --llm M` → `aos7-up stop`」；隊長實跑 luna 一次 2 呼叫約 3.5k token 退 0
- C｜README 統一稱「出口」（字由選單作者定）；「node」只在 README 註明＝工作資料夾，不改訊息
- 待｜程式面 5 條只記不修（JSON 壞的訊息說「不在或」且無行號、缺出口訊息範例字與 hello 不同、`run --help` 無說明、停下的 status 退 0、選項數／next 錯沒說實際值），交頂層排；MN2 合進 main 後若 menu.json／tools.json 格式有變，ADVANCED 要對齊

## loop14 MN2（學徒 aos-tool 選單，blueprint-scaffold1 §7 第三線）

- 結果｜`packs/menu/examples/aos-tool/`：`menu.json`（astra 寫問句）逐檔交件→索引列→REPORT→葉子工具三關→沒過按問題改檔（三關最多 5 輪）；`build.py`＋`summary.py` 登記成 `tools.json` 的 `aos-tool-gates`：把 out/ 組成 AP5 `=== 路徑 ===` 文字候選、跑 `aos7-gates check`（`--var review=rules`）或 `aos7-author propose --candidate … --review-llm M`，輸出 `{ok,gate,issues}` 一行；`build.py brief` 產生 ≤1500 字需求摘要；`practice.json` 離線走 mailcount（含一次重問、一次第 2 關失敗→改主程式→過）
- 結果｜真 AI 冒煙（luna 學徒、astra-high 審查、mailcount）三輪 0/3→1/3→3/3；第 3 輪每次 2 輪三關、13～14 呼叫、約 4.2 萬 token，0 次死在格式；三輪合計 140 次呼叫、408,967 token → [play 總表](play/2026-10-10-menu-aos/README.md)
- 結果｜每步提示平均約 1,650 字（練習整圈 1,599），AP4 gap 第一輪單次提示 9,558 字（重問 15,791）、AP5 mailcount 5,767 字，都用目前程式 `propose --prompt-out` 重建、不呼叫 AI；達「≤AP4 單輪 1/2」
- C｜`which` 層 2～5 含出口：已交的檔用 `when: new:` 藏起，四檔交齊才顯示「都交齊了」（開頭 4 檔＋出口＝5，交齊時 1＋出口＝2）；寫檔分 readme／bin／code／test 四層（各自格子限制），fix 用分組：fix（主程式／測試／README 或入口／索引列或 REPORT）→ fixdoc、fixtail 再選（各帶「回上一層重選」）→ fixcode（主程式、測試）／fixdocw（README、入口）／fixrow／fixreport，只附那一檔的目前內容
- C｜葉子工具退出碼：三關沒過＝1（menu 走 fix）；子程序退 2＝2；子程序退 3、逾時、輸出讀不懂、審查模型沒交回（rules 已過但 review 沒成）＝3（停在 gates，照原樣再跑重驗）。逾時收掉自己起的子程序群組
- C｜issues 摘要 ≤580 字、按 issue 分配：答案檢查器每條保留「變體名（慣例說明）：答案不合」、只給第一條的得到／應為；traceback 按 FAIL／ERROR 分段留最後的例外行；審查退件理由先於「建議：」
- C｜真 AI 要審查時 grant holder 一定是 `author`（menu 照 grant holder 送、author 寫死 holder author，共用一本帳），amount ≥100 萬（author 審查預設預留 100 萬）；寫進 aos-tool README
- C｜核心小修（頂層授權順手修）：render 回法改三行（第二行講「格：」後到結尾放全文、不加圍欄、後面不寫字；第三行「這格的限制（只是說明，不要抄進格子）」用人話列）；圍欄剝除多收「尾行 ``` 後接誤抄的『這格…』說明」，其他照原樣；MN4 五條（JSON 壞報行字、出口字可自訂、`--help` 說明、status 退出碼寫進 spec、選項數報目前幾個、next 報名字、停下的 `status --prompt` 一行說明）；README／ADVANCED／spec 對齊
- 待｜MN3（A／B）前要使用者定：AP4 三題（gap／runs／audit）需求摘要 2,900～3,600 字，超過 brief 1500 上限——放寬上限、把 work 拆進各寫檔層，或 A／B 改用 AP5 mail 四題
- 待｜astra 二審輕微一條沒做：fixcode 仍同時附主程式與測試兩類規則（未拆四層）；MN3 若看到修錯檔再拆
- 待｜MN4 寫的真 AI 路徑（`aos7-up … --model M -d` 裝帳）要確認 grant holder 能讓 aos-tool 選單的審查（holder author）用同一本帳

## loop14 MN3（需求切段＋選單 A／B，blueprint-scaffold1 §4）

- 結果｜使用者定「維持每步 1500 字、把長題目切小」：menu 核心加分段需求摘要（`--brief` 用 `=== 段名 ===` 分段、問層 `brief` 選段、每步實際附量 ≤1500、選項與層 `when: brief:<段>`）；aos-tool `build.py brief` 通用切段（head／accept／tools／work1～4／toc，原文保真）、選單加 code2～4 逐段補主程式與 fixpart 選段改檔。gap／runs／audit 切 2／3／3 段，每步最多 1,490 字 → `packs/menu/spec.md`、`ADVANCED.md`
- 結果｜A／B（luna、各 5 次）：A 12/15、B 2/15，B token 1.81 倍，格式型被擋 A 0、B 4；三條全紅＝「機制收下、不往 brain 推」；約 235 萬 token → [menu-ab](play/2026-10-10-menu-ab/README.md)
- C｜A 組不給 `--context`（AP4 有），兩組都只看需求；A 最多 6 輪、B 三關 5 輪照藍圖（A 的通過都在 5 輪內，不影響結論）
- C｜格式型被擋 A 只算格式類 rule（text／json／schema／size），B 算第 1 關擋下＋選單重問（對 B 較嚴）
- C｜冒煙發現 luna 會把「這步沒看到的需求」當「需求缺」選出口：code／test 問句講明後段下一層才給、code2～4 講明以目前程式為準；全部出口字改成不吸引的說法（「跟需求完全對不上，需要人來看」「摘要空的或看不懂」「這段需求是空的或亂碼」），改檔層加「答案不合只列你的輸出、不給正確答案」。正式開跑後 B1 在 code2 出口，停掉 B、改字、B1 重跑（A 不受影響照用）
- C｜正式跑到一半 LiteLLM 約 10 分鐘瞬間失敗、帳上留 516 萬未結預留；該段 15 次在新帳本整批重跑，舊的不算
- C｜沒加 sol-low：結論清楚、預算留著
- 待｜選單在「笨模型＋長需求」這組上輸給「一次交整包＋文字格式」；要不要換方向（例如只把選單用在改檔導航、或只在格式型失敗多的題上用）由使用者定

## loop15 TD2（proto7-2 文件整理，頭腦風暴前）

- C｜新增 [notes 索引](README.md)：notes/ 頂層平放 53 個檔（整理後 43 個），按「現行設計依據／藍圖／計畫報告決策／子資料夾」分組，每份標現行／已落地／歷史；thinking-catalog 原本沒人連，現在從索引進得去。proto7-2 README 與 INDEX 的 notes 列改指這份
- C｜[intents 索引](intents/README.md) 補 6 張漏列的卡：mail-plain、apprentice-4、apprentice-5、scaffold、drawers-and-mail、drawers-and-mail-ideas
- C｜封存到 [notes/archive/](archive/README.md)：10-09 的四份派隊計畫（上午、下午、第三段、r4）與各自的 teams.json、r5 分線表、r4 的 worktree 清單（共 11 檔，`git mv`）。活文件裡指向它們的 16 處連結改成純文字（多數加註「已封存」，標題裡的三處只留檔名）。plan-2026-10-09-next 仍被 wfnode 與藍圖當「三目標與門檻」的出處引用，沒封存
- C｜拆 decisions-2026-10-09（303 行、62 KB）：照 `##` 拆成 [四份](decisions-2026-10-09.md)（上午／下午到 14:40／續推／r4 與 19:00），內容逐字搬、只重算相對連結；原檔留前言＋分檔目錄，並列原行號對照，別處引用的「decisions-2026-10-09.md:行號」照表找得到
- C｜過時說法加日期註、不改原文：README（kernel 任務包已做、10-10 一段、catch-up／next-steps 標 10-05 快照）、core-slimming、catch-up 與名詞表、next-steps 兩份、layer-interfaces、drawers-and-mail 種子卡；status/ 兩張 HTML 快照頂端加一行註（1061→1308 項、M1 已進 main、usage／llmdiag 只剩轉址說明），新增 [status 索引](status/README.md)
- C｜沒做：>1 KB 條列轉 json（命中的多半是規格條文與給人讀的決策紀錄，轉了反而難讀）；problems.md 標題「kernel 還沒做」的那段（kernel 用量以 run 為單位）有沒有被 packs/kernel 做到拿不準，留原樣；packs/menu、packs/author 與 32 份思想文件沒動
- 結果｜壞連結：主 repo 的 proto7-2 前後都是 0（worktree 裡顯示 2 條，都是指向沒進版控的 `proto7/user-advice.md`）；`wf-lint wf .claude/commands` 前後 broken=0

## loop15 TD1（程式拆檔與 tidy，頭腦風暴前；行為不變）

- 結果｜拆檔：核心 `aos7_daemon.py` 842→571＋`aos7_daemon_control.py` 287（控制請求、回條、停止要求成 `DaemonControl` mixin）；step 796→587＋`aos7_step_check.py` 220；adapt 565→325＋`_common` 78／`_check` 100／`_chain` 90；budget 568→164（請求端與 CLI）＋`_common` 177／`_ledger` 251。八個大測試檔（test_daemon、test_matrix_faults、test_step、test_budget_ledger、test_kernel_core、test_llmcall、test_events_store、test_events_read）按 TestCase 分檔、共用 fixture 放 `_*.py`；全庫「類別.方法」1444 項前後逐一相同
- 結果｜收斂：核心 `aos7_fs.py` 加 `json_sha256`、`completed_round`、`say_line`，budget／adapt／events／kernel 的雜湊、budget／adapt／kernel 的 `completed_tock`、budget／llmcall／events／routines／skills 的 stderr 一行訊息改成轉呼叫（原函式名留著）；刪 51 個沒用到的 import（含拆檔後剩下的）。核心總行 3089→3128、實際程式 2434→2457（預算仍只印不擋）；proto7-2 範圍內 .py 總行約 36.8k→37.1k
- C｜拆出去的名字一律由原模組照舊匯出（`aos7_step.check`、`bg.ledger_running`…照用）。代價：測試若替換**舊模組**的屬性（如 `aos7_budget.fact`、`aos7_step._type_issues`），搬到新檔的函式看不到——現有測試沒有這種用法；以後要替換請對新檔。核心 daemon 例外：mixin 裡的 aos7_fs 函式（fact、write_json、now…）經 `aos7_daemon.<名字>` 取用，替換 `aos7_daemon.X` 照樣生效（astra 審查指出後補）
- C｜不收的重複（astra 唯讀盤點逐處比過）：原子寫、flock、tmp 清理、JSON／JSONL 讀取、名稱編碼、時間字串——各處 tmp 命名（`.compact-tmp`、`.brain-tmp`、隨機 mkstemp）、權限、fsync、錯誤語意都不同，換成核心版會改檔名或錯誤行為；metrics 的 `is_int` 寫法也不換（metrics 沒 import 核心，不為一行加依賴）；kernel 的 flat／error 帶 flush 不收
- C｜沒拆：compact（727，直接載檔＋測試 monkeypatch 邊界）、up brain（525，同理）、tick（414，單一開回合流程）、test_compact（1042，單一 TestCase 共用整圈 fixture）
- C｜轉址 stub 全留：`modules/llmdiag/aos7-llmdiag` 寫「r5 移除」已到期，但 `packs/author/examples/aos-module-diag` 的答案檢查器與 diag 測試、error_path.json 都還指著它，author 是 MN3 的範圍；`packs/usage/bin/aos7-usage` 決策沒寫期限；events `read --ack`（10-09「下一輪移除」）要連 mail 測試輔助 `_mailcase.acked()` 一起改、還會改 CLI——三者都留給頂層排一條線
- C｜沒改名：`wfnode_fill.py`／`wfnode_judge.py`／`wfnode_state.py`、`skills/bank.py`、`once_retry/retry_lost.py`、`tools/aos7_ctl.py`／`aos7_taskside.py` 不照 `aos7_<包>_<部分>.py`，但改名會動到 README 裡的 argv、任務設定與跨包 import；包內同義 helper（atomic／atomic_write／atomic_text／_write）實作本來就不同，不統一名字
- 待｜盤點附帶發現：既有跨包 import 不少（compact／skills／up → llmcall，llmcall → budget，kernel → mail，tools → control，十多個包 → tools 的 taskside），與「包之間只經檔案協定」的原則不合，沒動；`modules/mail/INTERNALS.md:24` 說「本包不 import events store」但 `aos7_mail_ack.py` 已 import `load_state`；`notes/play/2026-10-09-astra-7-infra-evidence/group5/probe_t8.py` 指名的舊測試檔名已拆走（歷史證據不改）
