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
