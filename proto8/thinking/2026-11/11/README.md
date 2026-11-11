# proto8 討論紀錄：2026-11-11

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [clock-hook](clock-hook/README.md) | 已施工：aos-loop 加 `on_start`／`on_stop`，hook 加 `after_start`／`after_stop`／`on_clock`（hook 格裡寫每 N 格或每 N 毫秒，格開頭判、到了才跑，handler 不進 history）；範本預設 `timer` 每 5 分鐘什麼都不做。先定的「時鐘登記＋專用信箱＋mail_arrived」被使用者改向取代、記錄不做；時鐘寄信那組原樣留著。第二輪使用者裁：事件名 `on_clock`（先代定 `clock_due`）、起來就先觸發一次、範本預設掛著、純每拍事件先不做 |
| [subagent-rename](subagent-rename.md) | 已施工：工具 `agents_children` 改名 `subagent`（夾、登記名、knowledge 節點、記帳檔位置跟著），舊名不留；包名 `children`、`children.json`、`max_children`、`Child*` 代號、`agents_ctl`／`agent_def` 沒動，待使用者裁（稍後使用者裁「一起改吧」：周邊全改成 subagent 系，`agents_ctl`／`agent_def` 不動，同檔下一節） |
| [playground](playground/README.md) | 公司試驗場 `~/code/playground` 照今天的 main 刷新（備份 `.bak-1111-1024`）：fsm_ann 假腦、eca_bob claude haiku、新加 eca_cody codex gpt-6-luna（沒畫面），三隻各驗一輪、停著乾淨；怎麼玩一頁、公司版刷新腳本與驗收在 [01](playground/01-公司刷新與驗收.md) |
| [self-system](self-system/README.md) | 已施工：agent 改自己的 system 文字——人用 `aos-agent system get／set／reset`、腦用 `self_system`（self 包，兩範本 35 支）；定義宣告 `system`、stack 那份在就整份用它；fsm 取代（下一格生效）、eca 附加（claude 下一輪、codex 下一段新對話）；codex 底下 aos-mcp 明寫帶 `AOS_*`、只對 aos 這個 server 免核准（使用者裁「修」「aos 工具免核准」），codex 改了 system 只提醒、不自動開新對話 |
| [knowledge-fix](knowledge-fix/README.md) | 已施工（線 C）：knowledge_write 不給預設庫、收呼叫參數 `root`（都沒有＝KnowledgeMissing），knowledge_read 照舊指出廠庫；thought 進 gadgets（36 支）；每支工具（`aos/tools/`）、每支 `aos-*` 指令（`aos/cli/`、`cli/parts/`）都有節點；必修 7 項與雜訊修完、長檔拆開；新檢查 `knowledge_check` 出廠庫 0 錯誤；大小改推薦值（一檔約 8 KB、一段約 1 KB）。六題 11-11 線 I 已裁並施工，見 [03](knowledge-fix/03-六題裁定與施工.md) |
| [do-task-rename](do-task-rename.md) | （同日稍後被 [fork-and-do-task](fork-and-do-task/README.md) 取代：do_task 改 save／load、開小幫手改由 fork）已施工（線 I）：工具 thought 改名 `do_task`（夾、登記名、`AOS_DO_TASK_FROM`／`AOS_DO_TASK_DEPTH`、知識節點、沙箱例子，舊名不留）；沒給 `from`、登記格也沒設＝用呼叫者自己的定義（daemon 表那列的 `def`），hooks 與工具一起帶、深度上限照擋；另帶回什麼「不加」 |
| [fork-and-do-task](fork-and-do-task/README.md) | 已施工（線 K）：使用者「把fork單獨拉出來做為工具。do_task改成save/load模式。」——新工具 `fork`（連對話整份複製自己去做一個 goal、只拿回結論，subagent 包）；`do_task` 改成 start／end（end 必附總結，紀錄點之後的訊息換成一則總結、原文留檔；稍後裁「可選。預設清掉。」＝信與 goal 提醒預設一起摺、`keep_others` 才留）；舊的「用別的定義開小幫手」拿掉；「eca 不給 do_task」「eca不給fork。」；fork 待裁 3、do_task 待裁 5（[01](fork-and-do-task/01-fork.md)、[02](fork-and-do-task/02-do_task.md)） |
| [i18n](i18n.md) | 只記想法（遠期構想，不設計、不排施工）：整個 aos 支援多語，偏好 `AOS_I18N` 這類「能支援的工具自己支援」；重點是給模型看的文字跟使用者同語言 |
| [mail-notify](mail-notify.md) | 已施工（線 I）：出廠 hook `mail_notify`（on_clock 每 10 秒，範本預設開）看自己的信箱，有沒通知過的新信才往 queue 寄一則 `[aos] new_mail: N new letters from A, B. …`（多封合成一句、不帶內文）；`self_hook rm` 免打擾、同名 `replace` 改間隔；驗證同一隻掛多個 on_clock 各自間隔 |
| [backlog-rulings](backlog-rulings.md) | 使用者用選項框一次裁積壓代定（線 K 施工）：mail_notify 預設「每 1 分鐘」、起來那次「只提醒新到的」；`llm set system=…`「報錯並指路」（ArgumentsBad 指到 `aos-agent system`／`self_system`）；do_task「帶過去」做了又撤（改由 fork＋save／load 重新設計取代）；另七題維持現狀；睡著時到的信稍後裁「睡著時新到的要提」（醒來提醒一次、睡前提醒過的不重複） |
| [tool-cells-lazy](tool-cells-lazy.md) | 已施工：工具小格改成真的寫東西才建（使用者「我確實想改成工具真的寫東西時才建資料夾」）——aos-exec 加 `--stack-lazy`（不建）、aos-tools call 傳它，act.py／observed.call 不再先建，aos-sandbox 綁 `$AOS_STACK` 前先建；直接當工具登記的 aos-loop／aos-fsm 入口會寫不進去——11-11 裁「loop／fsm 自己建」＋「stack只能在aos-exec建<-這個規則刪除」：兩支起來時 `$AOS_STACK` 有設但不在就 `mkdir -p`，N-59 等處那條規則刪掉（線 F） |
| [new-tools](new-tools/README.md) | grep／glob 已施工（線 K，使用者改口「啊，grep/glob得做」：兩支純 Python、問 git 跳過 .gitignore 擋的、進 look 包，[04](new-tools/04-施工結果.md)）；todo 也施工（改口「todo/goal也一起做吧」：一支四 op 存小格、新包，T1 裁「不帶，腦自己查」＝不動 brain.py）；兩範本 40 支；MCP client 匯入成包（M1～M8 已裁）停在設計稿（「先到這邊就好」） |
| [goal](goal/README.md) | 已施工（線 K，使用者「todo/goal也一起做吧」）：一支 `goal` 分動作（get／set／done／pause／resume）、外面 `aos-agent goal`、狀態 `<stack>/goal.json`；agent 自己停下來（信箱與 queue 空、腦不再叫工具）時 fsm 的 idle 格與 aos-eca-turn 丟 `[aos] goal: …`；四題新裁「一支 goal 分動作」「連續沒進展才算」「不自動，agent 自己 resume」「fsm 和 eca 都做」；代定 15 條、待裁 3 題見 [02](goal/02-裁定與施工結果.md) |
| [carry-over](carry-over.md) | 盤點（線 J）：11-10 傍晚兩行「明天順序」列的（B01 後半、templates-cp、cli-sweep 甲6／Q1／Q3／Q6、lv6 連帶、two-machines 其餘）11-10 晚～深夜都已做完，這次沒施工、只改記錄；two-machines 17 的三題使用者同日裁了並施工（kernel 範本拿掉示範預算、procs `$ref` 陣列缺一份跳過、`$ref` 檔內相對路徑維持現狀）；剩四題同日也裁了並施工（旗標位置推到全部指令、gitignore-check 改口徑；B14、defs 分群維持現狀），next_todo 剩 B06 兩種程式算出的路徑與大修題 |
| [kernel](kernel/README.md) | 只釐清概念、沒排施工、沒改條文：kernel 回歸「資源管理＋排程」、是從寄件人看進去的身分（請求寄到哪，那裡就是 kernel）；一般 proc 一律寄 `AOS_KERNEL`（沒設走 `AOS_DAEMON`、都沒設報錯），問腦維持 `AOS_LLM_KERNEL`；鏈上共通的只有 aos-post 信封、回信靠 `reply_to` 二選一；保底是 Linux 權限；狀態位址寄信問、不靠 symlink；aos-daemon-ctl 改定位成「指名 daemon」；判官以後收進通用 kernel 框架（選項框裁的下一站、數量另指、三個 hook 時機、daemon 壞信也回＝框架要有的能力）；會過時的條文與日後清單在 [03](kernel/03-過時清單與日後清單.md) |
