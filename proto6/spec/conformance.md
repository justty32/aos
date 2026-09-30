# 完整性與驗收入口

← [規格入口](README.md)

## V-01．何時算拆到可實作

〔主編補〕有效規則須能找到責任、輸入輸出、失敗處理及驗收；共用定義用連結，未裁選擇保持標記。以下**不是已執行的產品測試**。

### 正本規則

〔使用者方向 2026-09-30，第十八批〕**主規格是正本**（方案 A）：

- 行為規則只寫在主規格；協議篇只留欄位、JSON、schema、範例、method／argv 形狀、結束碼與錯誤碼，寫到行為時只留一句加主規格條號（[P-001](protocol/README.md)）。各協議檔對應的主規格見 [P-009](protocol/README.md)。
- 同一主題分散兩處的，照下面的正本表：正本那邊寫全，其他地方改成一句加條號。只寫在協議篇的行為，改到時搬到正本，原處留一句加條號。
- 條號不重編；內容搬走的條留一句殘根加連結。新條號接在該篇現有號碼後面（見文末「新條號」）。
- 被推翻的舊說法直接改掉，不留刪除線；需要交代來源的在條文後標〔使用者方向 2026-09-30，第十八批〕、〔使用者方向 2026-09-30，第十九批〕或〔使用者方向 2026-09-30，第二十批〕。使用者未答、照計畫預設寫的標〔暫定〕，不寫進使用者方向的段落。
- 〔使用者方向 2026-09-30，第二十批〕保證跟著「掛了什麼」走（[T-01](terms.md)）：tick 核心四件事（[T-07](settled/terms.md)）要確認不靠任何系統級任務；其餘保證由各條寫明「掛了哪一項系統級任務、包了哪個普通程式時成立」。第十九批的全掛前提與兩級保證已撤。〔使用者方向 2026-09-30，納入 cgroup 與 git〕git 與 cgroup 已納入，是「有就用」：現行規則在兩者都沒有時也要成立，有的時候多出的保證寫在各條（[B-630、B-622、B-634](settled/tick.md)、[B-605](settled/daemon/cgroup.md)）。延後項只寫一句並連到 [P-008](protocol/README.md#p-008)。

### 概念與正本

| 概念 | 規格正本 |
|---|---|
| 定位、多層多 kernel、各 kernel 自訂、上下層不必對齊 | [T-06](terms.md) |
| tick 核心四件事、tick 是衡量基準、唯一逃生口；投件權就是執行權 | [T-07、T-08](terms.md) |
| 核心、系統級任務、普通程式、其他任務；管轄區；保證跟著掛了什麼走 | [T-10、T-01](terms.md)；[B-626、B-629、B-632、B-633](settled/tick.md)；普通程式 [B-303](settled/helper.md)、[B-621](settled/tick.md)、[B-634](settled/tick.md)（`aos-cg`）；git [B-630、B-622](settled/tick.md)；node 框 [B-605](settled/daemon/cgroup.md) |
| node 與兼任角色、兩張註冊表 | [T-02](terms.md) |
| 上下層判定（預設看資料夾、登記覆蓋） | [B-628](settled/tick.md)、[B-606](settled/daemon/registration.md) |
| node 登記、喚醒、重啟、逐層重建與核心收尾 | [B-601](settled/daemon/runtime.md)、[B-603、B-604、B-611](settled/daemon/lifecycle.md)、[B-606、B-607](settled/daemon/registration.md) |
| daemon 部件與核心開關、同機多實例界線 | [B-615](settled/daemon/components.md)、[B-611](settled/daemon/lifecycle.md)；熱重載 [B-608](settled/daemon/reload.md)、helper 動作 [B-609](settled/daemon/helper-actions.md) |
| cgroup 框、上限與清框、子樹鎖 | [B-605 與核心條文的 cgroup 部分](settled/daemon/cgroup.md) |
| 核心通道、憑證、掛行程與診斷；可掛訊息與急件 | [B-612、B-613、B-610](settled/daemon/channel.md)；[B-614](settled/daemon/messaging.md) |
| 任務順序、停格檔與擋板檔、結束碼紀錄、`aos-needs`、互斥、Q1／Q2、git 開格／存檔點／收尾 | [tick](settled/tick.md) |
| 身分額度、可選 helper；inst 欄位與解析 | [身分](base/identity-resources.md)、[inst](base/inst.md) |
| 工作材料、可信結果、後代收尾、取消 | [work](base/work.md)、[execution](base/execution.md) |
| 追蹤／ignored 區、完整發布、去重與清理 | [storage](base/storage.md)、[transport](base/transport.md) |
| kernel 樹、資源 module 與 LLM 池 | [scheduling](scheduling/README.md) |
| 可選 run、unknown 與待辦彙整 | [runs](scheduling/runs.md)、[operations](scheduling/operations.md) |
| agent 任務、設定、context、工具、完成證據、清理遍歷 | [agent](agent/README.md)（清理遍歷 [A-304](agent/memory.md)） |
| 中間層 kernel 卡住、給 kernel 的一般回話 | [S-206](scheduling/admission.md)、[S-406](scheduling/operations.md) |
| 跨篇 ID、時間（格數與毫秒）、結果與錯誤；版本演進與禁止鍵 | [contracts](contracts.md)（C-01、C-07） |
| 錯誤碼與結束碼在哪定 | [集中碼表](protocol/README.md#集中碼表) |
| 延後項 | [P-008](protocol/README.md#p-008) |

### 正本表

〔主編補，第十八批；第十九、二十批改〕審稿找出 24 個寫在兩處以上的主題，第十九批再加 25～27，第二十批加 28。號碼見文末預留表；搬家由正本那篇的主責隊落筆，別隊把要改的句子交給主責隊。〔使用者方向 2026-09-30，第二十批〕第十九批寫成「標準配備」的主詞（01～03、05、09～12、16、20、22），照 [T-10](settled/terms.md) 改成各自的系統級任務、普通程式或 daemon；規則除第二十批改的以外不變。

| # | 主題 | 行為正本（主規格） | 協議篇只留 | 改成一句加條號 | 落筆 |
|---|---|---|---|---|---|
| 01 | cgroup 子樹、框命名、`task-*` 層（node 框歸 daemon；`task-*` 歸普通程式 `aos-cg`） | B-605（子樹、偵測、命名、交框、逃生口、中途失效；首推 systemd 使用者委派）＋B-634（`aos-cg`）；沒有 cgroup 時照 B-601 由 runner 管 | P-101 `cgroup_root` 等欄位；P-107 `cgroup_limits` 參數；P-211 `aos-cg` argv | P-107、P-101 欄位說明、P-503、P-203 的框規則、H-036 | T2、T3（B-634、P-203）、T5（P-503）、T6（H-036） |
| 02 | 重啟：全殺、收尾、boot id、逐層重建 | B-603 | P-116 `state.json` 格式；P-115 `boot_id` 欄位 | P-116、P-115 的行為句；P-814、P-812、H-004、V-03、B-605 驗收句 | T2、T5（P-812、P-814）、T6（H-004）、T1（V-03） |
| 03 | 停機：短寬限與排空 | B-604 | P-114 只留訊號、結束碼與設定欄位 | P-114 行為段、H-004、V-03 | T2、T6、T1 |
| 04 | 登記、解除、別每格重登、換父 | B-601（總則）＋B-606（登記規則、解除即收尾、前綴／範圍額度；〔第十九批〕登記可覆蓋預設上層、新舊兩上層都同意；換父兩條路：搬資料夾或改登記）＋B-628（預設上層） | P-103～106 只留 method、params、result、錯誤碼；P-104 `parent_id` 改可省 | P-104／105 的行為句、P-115、P-802（daemon 那側改引用；kernel 何時登記成員歸 S-202）、H-004 | T2、T5（P-802、S-202）、T6 |
| 05 | 寬限與強殺（daemon 端） | B-604（「收尾」：對 runner 送 SIGTERM→`shutdown_grace_ms`→第二次 SIGTERM 由 runner 清空名下→確認全空，有 cgroup 時最後對框 `cgroup.kill` 兜底；重啟、停機、解除、helper 停程序、砍掉掛載行程（B-613）都用它；〔納入 cgroup 與 git 疑-7〕逃生口准，`kill_escape_cgroups` 恢復、預設不殺）＋B-202（執行器：attempt 逾時照 inst 的寬限）＋B-634（`aos-cg` 對 `task-*` 殘留 `cgroup.kill`） | P-101 `shutdown_grace_ms`；P-108 helper 停程序帶設定值，不寫死 2 秒 | P-108、B-603 的寬限句；inst 的 2 秒只指 inst 自己的逾時 | T2、T3 |
| 06 | pause 批次存檔 | B-603 | P-116 存檔格式；P-101 `pause_save_interval_ms` | P-116 行為句、H-004（刪「每秒」） | T2、T6 |
| 07 | 停格檔、擋板檔、故障停格與 node 事項 | 〔第二十批〕停格檔：B-620（任務建 `.aos/tick/stop`，核心不開本格後面的項、整格回 1；只管本格，daemon 不因它暫停）；擋板檔：B-620（核心取鎖後看到 `.aos/tick-blocked` 就一項不跑）＋B-607（有擋板時 daemon 不開格；daemon 不看結束碼；daemon 自己的開格故障仍停格）；事項：S-405 | P-213 停格檔與擋板檔；P-601 事項檔位置與 `daemon.attention.*` 表；P-203 結束碼表 | P-105、P-205、P-609、P-601 行為句、B-601 的事項句 | T2、T5（S-405）、T3（P-203、P-213、P-601、P-609） |
| 08 | tick 任務表 | B-620（tick.md「任務註冊表」節：順序、類別與自訂種類、`methods` 欄的意思、一個 module 一項任務；〔第十九批〕核心只照陣列順序跑、只驗 inst 合法與 `id` 不重複；-32601 搬到 B-623；〔第二十批〕核心每項後查停格檔、開格先看擋板檔，任務的 `user` 跟 tick 不同時那一項回 125，給任務 `AOS_TASK_ID`、`AOS_TASK_INDEX`；`kind:"system"` 只是系統級任務的標記；〔暫定〕`group`、`needs` 欄撤，needs 改用 `aos-needs`（B-621）；`methods` 由收件任務讀（B-623）） | P-202 欄位表、JSON、schema；P-203 任務環境 | tick.md 欄位表刪、H-004 | T3、T6 |
| 09 | Q1／Q2 | B-623（Q1）、B-624（Q2）（tick.md 兩節；〔第二十批〕屬收件、投件、發摘要這幾項系統級任務。astra 審整理區定案後只剩系統訊息佇列 `aos-mq get`／`aos-mq post` 與發摘要，檔案收件與投件 aos 不管；有 git 時 `mq-post` 與發摘要排在 `aos-git close` 之後；P-206 的交接行為搬上） | P-206 只留待送檔與鬧鐘檔格式 | P-003、P-206、P-305、B-402、B-503、A-201、agent/README、P-704、P-800 | T3、T1（P-003）、T6、T5（P-800） |
| 10 | 投件失敗、鬧鐘 | B-624 | P-206 鬧鐘與待送檔欄位 | S-301、P-303、P-701、P-706、V-03、H-004 | T3、T4（S-301）、T6、T1（V-03） |
| 11 | method 開放、-32601 | B-501（method 就是指令；-32601 只表示沒任務宣告或 argv 不符，未授權走 -32000 業務碼；投件權即執行權）＋B-620（`methods` 欄）；〔第二十批〕沒人宣告的由收件任務回（B-623） | P-202 `methods` 格式；P-306 method 目錄 | P-004、P-306（兩處）、H-030 | T3、T1（P-004）、T6（H-030） |
| 12 | 去重、同 ID 衝突、重送 | B-503（P-304 的重送與補投回應規則搬上） | P-304 只留檔名與比對格式 | P-003、P-304、C-03 | T3、T1（P-003、C-03） |
| 13 | 工作材料、attempt、結果 | T-03（識別）＋B-101（固定材料與預設值）＋B-103（結果） | P-401～403 只留 payload、工作目錄命名、結果 JSON | C-03、B-201、P-400～403 行為句、S-104 | T3、T4（P-400～403）、T5（S-104） |
| 14 | 取消 | B-203（核權的兩種主人、排隊中拿掉、在跑的下一格經通道送 `node.kill`；判界只有一套；只適用 once，其他任務的取消延後） | P-411 只留 `work.cancel` 請求、回應、錯誤碼 | P-411 行為句、P-306 表、P-806、S-102、S-304 | T3（B-203）、T4（P-411、S-304）、T5（P-806、S-102） |
| 15 | unknown 放著不重做 | S-401（原則＋證據判斷，從 P-807 搬上） | P-807 只留啟動標記等檔案位置 | P-404、C-03、S-104、P-807、B-404、P-606、P-814、A-304、A-503 | T5、T4（P-404）、T1（C-03）、T3（B-404、P-606）、T6（A-304、A-503） |
| 16 | once、從未啟動證據 | 〔第十九批〕B-613（once 經通道把行程掛到 daemon、砍掉、資源與核權歸掛的那個 tick、`.err` 何時寫；從 B-606 once 段與 P-104、P-110 的行為搬上）＋B-610（掛載行程的診斷）＋S-401（從未啟動證據的判讀）；`.err` 何時寫、寫什麼的行為正本是 B-613 | P-118 掛行程的 method；P-110 只留 `.err` 格式 | B-606 once 段、P-104、P-402、P-709、P-807、P-008 | T2、T5、T4（P-402）、T6（P-709）、T1（P-008） |
| 17 | 資源 module、配額 | S-203（框架：六類是預設範本的資源，kernel 可自訂資源名；cgroup 與身分額度維持巢狀）＋S-205（套用、調整與故障，從 P-504、P-507 搬上）＋S-206（中間層 kernel 卡住）＋S-207（用量收集與去重，從 P-810、P-502 搬上） | P-500～507 只留配額、用量檔格式與 cgroup 檔對照；P-810 只留 argv 與檔案 | B-301、B-304、B-605、P-107、P-804、V-03 | T5、T2、T3、T1（V-03） |
| 18 | LLM：三檔、兩條路線、份額、key、重試 | S-301～307（兩條路線表只留 S-301，從 P-813 搬上；S-302 加「份額扣在誰身上」「池的共享窗口」，從 P-809、P-811 搬上；S-307 池 node 的任務與收件；〔第十九批〕S-307 另收 P-808 的路由成環、未授權、在途不改投，以及 P-406 的轉交、P-407 的重試派出） | P-405～407 池設定、請求、結果；P-505 份額格式；P-808 只留路由表格式；P-809、P-811 只留 argv 與狀態檔格式；P-813 只留範本權限 | H-004、A-101、P-400、P-701、P-809、V-03 | T4、T5（P-505、P-811、P-813）、T6、T1（V-03） |
| 19 | agent 設定原則、`in_reply_to` | A-102（原則；〔第十九批〕接住 P-207 的鎖與提交、P-210 的建立與恢復流程）＋A-201（`in_reply_to` 配對，從 P-705 搬上） | P-705 欄位；P-207、P-210 只留 argv 與檔名 | P-203、P-207、P-210、P-701、P-805 的原則句；H-036；其餘 `in_reply_to` 各處 | T6、T3（P-203）、T5（P-805） |
| 20 | 清理、保留期、待辦 | B-404（清理資格、保留期；〔第二十批〕`aos-clean` 是系統級任務，保留期與清理間隔以格計）＋S-405（`aos attend` 三個動作）＋A-304（agent 的清理遍歷，〔第十九批〕從 P-716 搬上） | P-605／606 清理設定與報告；P-603 argv 與輸出；P-716 只留殘根 | P-601、P-716、P-814、H-004、P-603 行為句 | T3、T5、T6 |
| 21 | 錯誤碼與結束碼 | C-04（原則）；碼值屬格式，正本 P-005／P-006 與各篇碼表 | 各篇自己的碼表；集中碼表在 P-006 | H-002 連集中碼表；設定檢查 kernel 2、agent 1 的不一致延後 | T1、各隊 |
| 22 | helper 與切換帳號（〔第二十批〕普通程式 `aos-as`） | B-303（角色與界線；〔第二十批〕`aos-as` 怎麼請 helper 開程序、交鎖）＋B-609（新：固定動作清單與各動作做什麼，含新加的動作，從 P-107 搬上；〔第十九批〕`spawn_as` 以指定帳號開程序、任務繼承鎖；〔第二十批〕呼叫者是帶本格憑證的程序，實際就是 `aos-as`）＋B-620（任務的 `user` 跟 tick 不同時回 125）＋B-601（helper 開格何時回，從 P-108 搬上） | P-107 參數；P-108 私有通道；P-212 `aos-as` argv | B-601、P-102、H-004、B-605 | T3（B-303）、T2、T6 |
| 23 | inst | [inst](base/inst.md)（新增「inst 目標：檔案或資料夾」節，從 P-010 搬上） | node-inst schema | P-010（inst 篇寫好後由 T1 縮成殘根）、P-200、P-201、P-109 | T3、T1、T2（P-109） |
| 24 | 結構問題 | — | — | B-504：transport 的標題改成非標題的一行殘根；P-100～119 條號表只留 daemon/README，protocol/daemon.md 縮成一句連結；P-001 改寫 | T3、T2、T1 |
| 25 | 〔第二十批改〕tick 核心、系統級任務、普通程式、結束碼紀錄 | T-07（核心四件事、衡量基準、停格檔）、T-10（四類與管轄區）、T-01（保證跟著掛了什麼走；git 與 cgroup 有就用）；B-626（核心與系統級任務的界線）、B-602（互斥）、B-620（照表跑、停格檔、擋板檔、`user` 不同回 125、任務環境變數）、B-633（每項結束碼紀錄與格數）、B-629（標準任務表範本）、B-632（結束碼紀錄取代日誌：沒有 git 時怎麼做）、B-631（殘根）；普通程式 B-621（`aos-needs`）、B-303（`aos-as`）、B-634（`aos-cg`）；git B-630、B-622 | P-203 結束碼與任務環境；P-202 任務表；P-204 `aos-needs`、P-212 `aos-as`；P-213 結束碼紀錄、停格檔與擋板檔；P-205 `aos-git`、P-211 `aos-cg` | README 定位與依賴段、T-06、B-605 啟動輸出、B-302、P-101、P-203、H-004、H-036、V-03 | T1、T3、T2（B-605、P-101）、T6（H-004、H-036） |
| 26 | 上下層 | B-628（預設看資料夾包含、有效上層、身分繼承有效上層、巢狀 git）＋B-606（登記覆蓋、兩上層同意、管轄權跟資料夾、換父兩條路） | P-104 `parent_id`（可省） | T-02、C-02、P-103、P-402、P-801～806、P-813、S 篇首、S-202、S-405、P-601、inst 的「繼承上層」、H-004 | T3、T2、T1、T4（P-402）、T5、T6 |
| 27 | tick–daemon 通道 | B-612（誰有通道、環境變數、憑證發放／核對／作廢、事務表）＋B-613（掛行程與砍掉）＋B-614（暫存訊息、急件叫醒、誰能送、收件任務自己取） | P-117～119（[channel.md](settled/protocol/daemon/channel.md)）變數、method、params、錯誤碼；P-108 `daemon.helper.start` 帶 `token`（runner 環境的行為在 B-601） | P-001、P-004、P-006、B-504、B-601、B-303、inst、P-101、P-408、P-701、P-801 的 `daemon_socket`、A-201、A-401 | T2、T1、T3（B-303、inst）、T4（P-408）、T5（P-801）、T6（P-701、A-201、A-401） |
| 28 | 〔第二十批〕時間：格數與毫秒 | C-01（內部時長改格數、外部留毫秒、算安排者的格、起算點換成第幾格） | P-002 欄位命名；common `Ticks`、`TickSeq`、`TimeMs` | 各篇時間欄位的說明句：S 篇首、S-201～206、S-303、B-404、B-624 鬧鐘、A 篇鬧鐘、各 schema | T1、T2～T6 各改自己的欄位 |

### 新條號

〔主編補，第十八批；第十九、二十批加列〕第十八～二十批新開的條號如下（先預留；`check_ids --strict` 會核對每一列都有正文）。B-6xx 由 daemon/ 與 tick.md 共用；原 daemon.md 從 606 起、tick.md 從 620 起，tick.md 現有沒編號的各節照下表補號（補號不算重編）。〔主編補，第二十批整理區〕這兩篇連同 node 與 daemon 協議已搬進 `settled/`（[整理區](settled/README.md)），條號不變；T-07、T-09、T-10 搬到 settled/terms.md，B-303 搬到 settled/helper.md。第十九、二十批沿用的舊號只換主題、不重編。

<!-- check_ids:reserved -->
| 條號 | 檔 | 主題 | 落筆 |
|---|---|---|---|
| B-506 | base/transport.md | 〔第十九批〕收件區權限與建立時的路線核對（P-208 搬上） | 修正輪 A |
| B-606 | settled/daemon/registration.md | 登記、解除（收尾）、覆蓋上層、換父兩條路、前綴／範圍額度（〔第十九批〕once 登記搬到 B-613） | T2 |
| B-607 | settled/daemon/registration.md | 叫醒、暫停、故障停格與格次序號（〔第二十批〕停格靠擋板檔、不看結束碼） | T2 |
| B-608 | settled/daemon/reload.md | 熱重載與「免重開／要重開」 | T2 |
| B-609 | settled/daemon/helper-actions.md | 佈建固定動作與 helper 動作 | T2 |
| B-610 | settled/daemon/channel.md | 〔第十九批改名〕掛載行程的診斷：留存、淘汰與清除 | T2 |
| B-611 | settled/daemon/lifecycle.md | 一棵資源樹只准一個 daemon | T2 |
| B-612 | settled/daemon/channel.md | 〔第十九批〕tick–daemon 通道 | T2 |
| B-613 | settled/daemon/channel.md | 〔第十九批〕掛行程與砍掉（原 once 的 daemon 端） | T2 |
| B-614 | settled/daemon/messaging.md | 暫存訊息與急件；09-30 晚拆為可掛訊息部件 | T2 |
| B-615 | settled/daemon/components.md | 09-30 晚：部件形式、核心功能開關與未拍板預設 | 本輪 |
| B-602 | settled/tick.md | 〔第十九批換標題〕同一資料夾一次一格：互斥鎖（原「同一 node 一次一格」） | T3 |
| B-620 | settled/tick.md | 任務註冊表：照表依序跑（〔第十九批〕換標題） | T3 |
| B-621 | settled/tick.md | 〔第二十批換主題〕aos-needs：前置沒成功就不跑（原節補號） | T3 |
| B-622 | settled/tick.md | git 的共同規則（原節補號） | T3 |
| B-623 | settled/tick.md | 系統訊息佇列：取件（mq-get）；檔案收件 aos 不管（〔第二十批〕原「收件：分派、-32601，下一格刪原件（Q1）」，astra 審整理區定案改寫） | T3 |
| B-624 | settled/tick.md | 派出：系統訊息佇列送出（mq-post）與發摘要（Q2）（原節補號；〔第二十批〕原「投件、鬧鐘與發摘要」，astra 審整理區定案改寫：檔案投件與鬧鐘撤出 aos） | T3 |
| B-625 | settled/tick.md | 當機恢復、設定與清理（原節補號） | T3 |
| B-626 | settled/tick.md | 〔第二十批換主題〕核心與系統級任務的界線 | T3 |
| B-627 | settled/tick.md | 〔第十九批換主題〕人手或 cron 直接跑一格：風險自負 | T3 |
| B-628 | settled/tick.md | 〔第十九批〕上下層判定：預設看資料夾包含、可登記覆蓋 | T3 |
| B-629 | settled/tick.md | 〔第二十批換主題〕標準任務表範本 | T3 |
| B-630 | settled/tick.md | 〔第二十批換主題〕git：開格、存檔點、收尾 | T3 |
| B-634 | settled/tick.md | 〔納入 cgroup 與 git〕aos-cg：每項一框（從 B-202 的草稿搬進整理區） | T3 |
| B-631 | settled/tick.md | 〔第二十批撤，留殘根〕cgroup 框的備援 | T3 |
| B-632 | settled/tick.md | 〔第二十批換主題〕結束碼紀錄取代日誌：沒有 git 時怎麼做 | T3 |
| B-633 | settled/tick.md | 〔第二十批〕每項結束碼紀錄與格數 | T3 |
| S-205 | scheduling/admission.md | 套用、調整與故障 | T5 |
| S-206 | scheduling/admission.md | 中間層 kernel 卡住 | T5 |
| S-207 | scheduling/admission.md | 用量收集與去重 | T5 |
| S-307 | scheduling/llm.md | 池 node 的任務與收件 | T4 |
| S-406 | scheduling/operations.md | 給 kernel 的一般回話 | T5 |
| H-037 | cli/debugging.md | 除錯指南 | T6 |
| A-304 | agent/memory.md | 〔第十九批〕清理遍歷（P-716 搬上） | T6 |
| T-10 | settled/terms.md | 〔第二十批換主題〕tick 核心、系統級任務、普通程式與其他任務 | T1 |
| P-117 | settled/protocol/daemon/channel.md | 〔第十九批〕通道變數與憑證 | T2 |
| P-118 | settled/protocol/daemon/channel.md | 〔第十九批〕掛行程與砍掉 | T2 |
| P-119 | settled/protocol/daemon/channel.md | 〔第十九批〕送訊息、取訊息與通道錯誤碼 | T2 |
| P-211 | settled/protocol/node.md | 〔第二十批〕`aos-cg`：每項一框 | T3 |
| P-212 | settled/protocol/node.md | 〔第二十批〕`aos-as`：切換帳號 | T3 |
| P-213 | settled/protocol/node.md | 〔第二十批〕每項結束碼紀錄、停格檔與擋板檔 | T3 |

之後要開新條，就接各篇下一號：

| 篇 | 下一號 |
|---|---|
| settled/daemon/ | B 616 起（到 619 為止） |
| settled/tick.md | B 635 起 |
| base/work.md、execution.md、identity-resources.md、storage.md、transport.md | B 104、205、306、405、507 起（305 是已刪的舊號，不要再用） |
| scheduling/runs.md、admission.md、llm.md、operations.md | S 105、208、308、407 起 |
| agent/configuration.md、input.md、memory.md、tools.md、README.md | A 104、204、305、405、507 起 |
| cli/ | H 038 起 |
| terms.md、contracts.md、conformance.md | T 11、C 08、V 06 起 |
| 協議篇 | 接各檔現有最後一號（daemon 協議 P 120 起、node 協議 P 214 起；這兩份在 settled/protocol/） |

B-605 的共通自檢在 [runtime](settled/daemon/runtime.md#啟動自檢b-605-的共通部分)，框規則在 [cgroup](settled/daemon/cgroup.md)；B-601、B-603、B-604、B-609、B-611、B-613 的 cgroup 部分也集中在該檔，沿用原條號。

## V-02．先測行為，再測規模

〔建議預設，未拍板〕先用假工具／mock LLM 驗檔案交接、授權及結果。再在可丟棄的 Linux／WSL 環境，驗無 helper 通用 user、有 helper 兩個真 UID、已裝 module 與程序群組的後代清理；最後測萬級冷 node。〔使用者方向 2026-09-30，納入 cgroup 與 git〕git 與 cgroup 有就用：現行規則要在兩者都沒有的機器上也驗過。〔使用者方向 2026-09-30，第二十批〕保證跟著掛了什麼走（[T-01](terms.md)），所以系統級任務與普通程式分開驗：有沒有掛 `aos-mq get`／`aos-mq post`、發摘要、清理、`aos-git` 三項，任務有沒有包 `aos-needs`、`aos-as`、`aos-cg`，daemon 有沒有 cgroup（[B-629](settled/tick.md)、[B-621](settled/tick.md)、[B-303](settled/helper.md)）。

cgroup 子樹依 [B-605](settled/daemon/cgroup.md) 至少驗三種：首推的 systemd 使用者委派、不用 sudo（〔使用者方向 2026-09-30，第十九批〕）；root 事先準備好的子樹；開 `--create-cgroup` 由 daemon 自己建（〔使用者方向 2026-09-29 晚〕）。WSL 另驗三個坑：shell 在 `/init.scope`、scope 名每次不同、檔案歸自己不等於有委派（B-605）。git 依 [B-630、B-622](settled/tick.md) 驗三種：有 git、沒有 git、git 不能用（只印 `no_git` 警告、照 [B-632](settled/tick.md)）。

保存版本、配置、環境與結果；mock 不代表 OS 隔離已驗證，磁碟記帳不算硬限制。範圍依[平台邊界](README.md)，須涵蓋同機 node 樹。

## V-03．跨篇故障場景

〔建議預設，未拍板〕以下測試交叉覆蓋已裁規則與各篇工程預設；具體預設仍依正本來源。〔納入 cgroup 與 git〕git 與 cgroup 有就用：各小節的句子在兩者都沒有時也要成立；要靠兩者的驗收句集中在文末「git（有就用）」「cgroup（有就用）」兩小節。

### daemon 部件開關與同機多實例

正本：[B-615](settled/daemon/components.md) 與表中各條。〔使用者方向 2026-09-30 晚〕分工與多 daemon 界線已裁；以下開關細節皆為〔建議預設，未拍板〕，是未來驗收清單，本輪未執行。單獨關閉一鍵的案例，其餘鍵保持 true；全部關閉另有一列。

| 組合／操作 | 預期 |
|---|---|
| 五鍵省略 | 保留既有行為；環境不可用時仍照原有 no-helper／cgroup=off 路線 |
| 五鍵全部 false；同一支程式、同一張任務表 | 通用 user 的登記、開格、wake／pause、runner 清名下程序、重啟與憑證核對仍成立；mount／kill 不靠 cgroup |
| `enable_messaging:false`；有合法待送件 | `node.send` 回 `not_available`；mq-post 回 1、移至 failed 並記 code、不自動重試；tick 後續項照跑，daemon 不停格 |
| 同上，get／無待送件／急件 | 合法 take 回空且 more=false、mq-get 回 0；post 沒件回 0；不產生急件 wake；不需改任務表 |
| 訊息部件關閉，壞憑證或掛載行程取件 | 原核權／kind_mismatch 仍成立，不能用開關略過 |
| `enable_cgroup:false`；環境本來有委派子樹 | cgroup=off、show.cgroup=null；不建框、不取 cgroup 鎖、不碰新舊框；limits 或 spawn_as 帶 frame 回 unsupported，runner 收尾照常 |
| `enable_reload:false`；修改設定再送 SIGHUP | 只警告、不讀取、不套用、不退出 |
| `enable_drain:false` 且 stop_mode=drain | SIGINT／SIGTERM 採立即停，正常收尾／存檔仍做 |
| `enable_helper_actions:false`；helper 存在 | 非 cgroup 的 provision 與 spawn_as 回 not_available、無動作副作用；aos-as 回 125；核心 helper 開格／收尾保留，cgroup 動作仍看自己的開關 |
| 熱重載開著時修改任一開關 | restart_required；其他可熱重載欄位照套，開關只在重開後生效 |

〔使用者方向 2026-09-30 晚〕另驗既有界線：各實例各管自己的 node 樹；B-611 的 state／socket 鎖（有 cgroup 時另含子樹鎖）衝突仍回 125，不待命；兩 daemon 誤管同 node 只沿用 B-602／B-607 的鎖與 75 普通結束。訊息部件開著時，收件方只在另一 daemon 登記，送件回既有 not_registered、不轉送。巢狀內層經 mount 掛上，外層重啟依既有收尾界線處理，不另接回內層；沒有 cgroup 時仍不保證重啟清空。不開 daemon 的 node 間溝通不列基底驗收。

### node、登記與身分

驗兼任 kernel／agent、只有收信任務及空成員表，角色須依任務判定。正常重開讀回登記、pause 與 wake，意外重開最多丟最後一個存檔間隔的 pause；無快照也自動 tick 頂層，boot id 變更後逐層補登記，壞成員留待辦、不擋其餘成員；漏叫醒可補查，重複叫醒不並行同 node 的兩格。

啟動自檢依 [B-605](settled/daemon/cgroup.md)：〔使用者方向 2026-09-30，第二十批〕沒有 cgroup v2 時 daemon 照常啟動、照常開格，stdout 沒有 `standard:` 行；cgroup 部件關掉時不查 cgroup，daemon 一律不查 git；只有 Python 版本不足才報錯退出。quota 偵測到但設定強制關時不用。

測 socket 冒名、超額授予／宣告 user、不懂 user 語意、無 helper 繼承與切 UID 後開檔。超額須 125、不啟動、不寫 `exit` 並留待辦；整份 `$ref` 可用但不能偷換身分，搬資料夾也不能取得新身分。

### 收件與派出

〔astra 審整理區定案〕檔案收件區 `requests/`、`responses/` 的收與寫是普通程式，aos 不管（B-623）；以下只驗系統訊息佇列。`mq-get` 取出請求與回應，同一件再取不到（B-623、B-614）。`mq-post` 途中被殺，下一格再送同一份，接收方靠 ID 去重；執行不明仍 unknown、不自動重做（B-624）。沒有 git 時：失敗任務寫出的待送訊息也會送，前面有項建了停格檔時這格不送（B-624）。送不出去的（`forbidden`、`not_registered` 等）不重試，搬到 `.aos/mq/failed/`，下一格 `mq-post` 開始前被清（B-624）。

### 程序與結果

正常 Ctrl-C 時在途 tick 也先收到信號；主程序已退、同一程序群組的孫程序仍活時不能報清空（B-604）。無可信結果的在途工作不能自動再跑。取消與完成競爭只發布一次結果，晚到舊結果不覆寫新嘗試，同一結果與用量不重複採計；沒有 OOM 證據不能只憑 SIGKILL 猜原因。

### 分層資源與 LLM

父層分給子層的 cgroup 上限與身分額度不能被子層加大；kernel 自訂、Linux 管不到的資源與隔離可以跟上層不同，上層不認得的不代管、不報錯（[T-06](terms.md)）。子層未裝某 module 不另記或另限，但父層限制仍有效。兩個 kernel 可各有 endpoint 池；同一 provider 限制怎麼分、要不要共用一池，照各 kernel 自己的資源政策（[T-06](terms.md)），不靠同名 scope 跨 node 同步。測 429 退避、送出後斷線及部分內容；部分回覆不能冒充完成，unknown 不因一般 retryable 標記而重試。

LLM 三檔（[S-301](scheduling/llm.md)）：預設 `schedule:aos` 的池做窗口與冷卻，`schedule:endpoint` 的池只轉發、不讀窗口設定，遇 429 也不重試；投給不是 node 的路徑、或沒有寫入權限，當場報一次錯、丟掉待送檔、不寫待辦、不重試；投給有 tick 但沒任務宣告的 node、或沒被 tick 的 node，分兩種情況驗，見下面「第十八批新增場景」的 LLM 段。指定 stream_path 時呼叫途中檔案持續變長，中途斷線任務非 0 結束、結果不算成功。

分開驗證 key 部署：無 helper 且代發／agent 同帳號時，或 agent 自己打 endpoint 的直連檔，文件須明說 key 不受保護；採獨立服務帳號保護時，整條投件鏈以外的 node 與工具不可讀 key；能投件給持 key node 的帳號等於能用它的身分，不在保護範圍內（[T-08](terms.md)）。上層查詢只取下層摘要，未授權者不能因猜 ID 讀內容。

### 第十八批新增場景

〔第十八批〕以下由各主責隊交來的驗收句依主題合併；正本仍在各條，句末標條號。版本演進的通則驗收見 [C-07](contracts.md)。

**daemon 啟動、熱重載與停機**

- 兩份設定用不同 socket、指向同一 `state_dir`：後啟動的回 125 拒絕，先啟動的不受影響（B-611）。
- SIGHUP 後改 `interval_ms`、加一棵只用通用 user 的 root，免重開、立即生效；同時改 `socket_path` 或其他帳號的額度時，其餘照套、這些欄位回報要重開；壞設定整份不套、舊設定照跑（B-608）。
- `stop_mode:"drain"` 收 SIGTERM：新的掛行程與新成員登記回 `stopping`、已登記 node 照常開格、在途做完回 0；超過 `drain_timeout_ms` 或再按一次 Ctrl-C 改立即停（B-604）。

**登記、換父、額度與格次**

- 換父：子樹沒停、或新父在被搬的子樹裡，被拒；只有一方父的 owner 同意，被拒；搬好後框在新父下，`registration_id` 換新（B-606）。已覆蓋成 B 再換 C，要 B 與 C 同意，資料夾推得的上層不必（B-606、B-628）。
- 前綴規則比不中 UID 小於 1000 的帳號；子額度寫了父沒有的前綴或更大的範圍，被拒（B-606）。上層收小身分額度後，重登被拒的成員只隔離那一項並記事項，其他成員照常（B-607、S-205）。
- 成員跑完一格、摘要沒變且牆鐘倒退，kernel 仍靠 `tick_seq` 認出新格；daemon 重啟後 `registration_id` 換了，kernel 重新核對、不空等（B-607、B-627）。
- 〔第十九批〕掛載行程不存檔；daemon 重啟或停機時被收尾的，由掛它的 tick 照 unknown 規則核對，重啟後不接回（B-603、B-613）。
- 已結束的掛載行程紀錄超過 `mount_diag_max` 或 `mount_diag_ttl_ticks` 就消失；`mount.clear`（CLI `aos mount clear`）帶上層 node 只清整棵子樹下已結束、呼叫者有權清的紀錄，在跑的與別人的不動（B-610、H-004）。

**框、收尾與佈建**

- 砍掉在跑的掛載行程（取消在跑的 once 也走這條）：寬限後被殺、程序群組清空（B-203、B-613、B-604）。
- 〔納入 cgroup 與 git 疑-7〕設定帶 `kill_escape_cgroups` 照收：省略或 false 時 node 自開的子框（逃生口）重啟與解除都不殺，true 時一併收尾；沒有 cgroup 時沒有作用（B-605）。
- 多帳號部署下兩個 node 帳號靠 `group_create`、`group_add_member`、`chgrp` 交接檔案（B-609）。頂層額度改到小於已分出的合計：不自動收回，記 `over_allocated`、寫事項、停新派工，在跑的照跑（S-205）。

**任務表、method 與人手跑一格**

- 任務表沒有任何 system 類也能正常跑；`kind:"agent.review"` 照收，`system.x` 核心照跑、不擋（只有恢復前驗證擋，B-620、B-625、B-626）。〔第二十批〕任務項帶 `user` 照收，跟 tick 帳號不同時那一項回 125（B-620、C-07）。
- 〔第十九批〕不經 daemon 直接跑 `aos-tick` 照常跑完一格，只是沒有通道（B-627）。`aos node tick` 經 daemon：送 wake 後看到 `tick_seq` 變大才回 0，逾時回 101，paused 回 1 不等（B-607、H-004）。
- 沒人宣告的 method 由收件任務回 -32601；有宣告但來源未授權回 -32000 加業務碼（B-501、B-623）。

**收件、投件與取消**

- 同一個壞收件連跑多格只有一件事項；過保留期由 `aos-clean` 刪，期內留著（B-623、B-404）。
- 同 ID 重送時，照 [B-503](base/transport.md) 處理（檔案投件的補投由處理它的普通程式定，aos 不管）；本地動作回應的 `stdout.path` 指向存在的 `.stdout` 檔（B-503、B-624、B-632）。
- 取消：node 根目錄擁有者與 inst 執行帳號不同時，兩者送的取消都收；其他人回 `cancel_not_authorized`，原工作照跑；once 自己 inst 的 user 被拒（B-203）。記了 canceling 的那格不送 `node.kill`；`not_registered` 又沒有可信證據時記 unknown；進 canceling 前已經有完整結果的照原結果（B-203、P-411）。
- `aos work trace` 用請求 ID 或 attempt ID 都查得到同一件工作；讀不到的站標「看不到」、不回錯；全找不到回 1（H-037）。

**資源、kernel 與 agent**

- 工作在途時弄壞父配額或讓資源任務失敗：仍收結果、接受取消，不開新工作（S-205）。父配額公開檔在期望配額提交後的下一格才發布（S-203）。
- 中間層 kernel 停格：父 kernel 過了 `member_stale_ms` 寫一件事項、不重複寫、不碰孫輩（S-206）。
- 兩個 kernel 各登記自訂資源名，上層不認得不報錯；配額檔帶自訂資源照收（T-06、S-203）。
- 投給 kernel 的 `agent.say` 記進 kernel 的 history、序號遞增、`listen` 讀得到；kernel 不回話；清理後序號不倒退（S-406）。帶 `in_reply_to` 的 agent 回話過了保留期被清，仍有引用就保留，agent 序號不倒退（A-201、B-404）。

**LLM**

- 純池 node 宣告 `llm.chat` 時直投收得到；沒有任務宣告時回 -32601、原件被清、鬧鐘不響；投給沒被 tick 的 node 就堆著，鬧鐘到期報錯（S-307、B-624）。
- 下層自建的池不扣上層份額（S-301）。
- 送出後斷線：本機連線名額立刻還，unknown 份額到 `timeout_ms` 才還；池狀態裡兩個數分開，工作仍是 unknown、不重送（S-304）。
- 池限流重試的第二次嘗試，目錄前綴是池的雜湊，`request.json` 的 `node_id` 仍是發起者（P-402、T-03）。改 `llm-pools.json` 後，已派出的嘗試仍用自己的 `W/llm-config.json`（S-307）。

**版本與禁止鍵**

- LLM 池設定帶 `api_key` 整份拒收；〔第十九批〕agent／kernel 範本的任務表項目帶 `user` 照收；agent 設定、kernel 持久檔、LLM 池設定多一個不認得的欄位照樣讀進（C-07）。`work-result` 的 signal 65 拒收（P-403）。

### 第十九批新增場景

〔第十九批〕總綱的主幹加上各隊交來的驗收句，依主題合併、去掉重複；正本仍在各條，句末標條號。〔第二十批〕第十九批的三層、全掛與保證兩級已撤，相關句子改寫或移到文末「git（有就用）」「cgroup（有就用）」。

**tick 核心**

- 沒有 daemon、git、cgroup、helper 的機器上直接跑 `aos-tick`：同資料夾同時跑兩格，一格回 75、什麼都不做；照任務表陣列順序跑；預設上層照資料夾算得出（T-07、B-602、B-620、B-628）。
- 鎖檔是 `.aos/tick.lock`、不在 git 管理目錄；任務留下的程序還握著鎖時，下一格拿不到鎖（B-602）。daemon 開的格回 75 當普通結束，不停格、pending 照留（B-607）。
- 人手或 cron 不經 daemon 直接跑 `aos-tick`：照常做完一格，沒有通道，stderr 沒有 `standard:` 行（B-627）。
- 沒 cgroup：daemon 照常啟動、印 `cgroup=off`、開格，`cgroup_limits` 回 `unsupported`、`node.show` 的 `cgroup` 為 null（B-605、B-609）；kernel 的資源任務不報套用失敗，新派工照額度放行（S-205）。
- 沒 git：兩版範本任務表都照常跑完、每格都有結束碼紀錄；掛了 `aos-git` 的只印 `no_git` 警告、回 0（B-632、B-622）。發布摘要從目前的 `summary.json` 發布（B-624）；unknown 的保留期從 `aos-clean` 記下的格數起算，不會提早清（B-404）。

**任務帶 `user` 與 `aos-as`**

- 任務表項目（含 agent、kernel 範本）帶 `user` 照收、schema 通過；〔第二十批〕帶了跟 tick 不同帳號的那一項不跑、回 125、stderr 印 `user_mismatch`、紀錄記 `exit:125`，其餘照表處理（B-620、C-07、P-814、P-717）。
- 〔第二十批〕argv 包 `aos-as <帳號> --`、有 helper 也有通道時，經 `node.provision` 的 `spawn_as` 用那個帳號跑：任務（含 kernel、agent 的工具）用 `AOS_TICK_LOCK_FD` 核對得到同一把獨占鎖；它在跑時同資料夾另一格回 75、下一項不開；`aos-as` 照原指令的結果結束（B-303、B-609、B-602）。直接跑的格沒有通道，`aos-as` 回 125、印 `no_channel`（B-303、B-627）。
- `spawn_as` 的帳號在身分額度外回 `user_not_granted`；不帶憑證、由掛載行程叫、或交來的鎖 fd 不是本 node 的 `.aos/tick.lock`，都被拒；交來的 fd 不是 5 個或帶 `frame` 被拒；沒 helper 回 `helper_unavailable`（B-609、P-107）。

**上下層與登記覆蓋**

- 成員在 kernel 資料夾內登記不帶 `parent_id`，上層由資料夾推得；在外面的帶 `parent_id` 覆蓋（B-628、B-606、S-202）。
- 資料夾上層在同一個 daemon 登記時，覆蓋只有一方上層同意，回 `forbidden`；資料夾上層不同意時只隔離那一項成員、其他照常（B-606、S-202）。覆蓋後資料夾上層仍保有檔案上的管轄權（B-628）。
- 〔使用者方向，第十九批疑點裁定 11〕資料夾上層由 cron 或人手跑、沒在 daemon 登記時，只要新上層同意，覆蓋照收（B-606、B-628、C-02）。
- 設定只列 `/a/b` 為頂層、`/a` 由 cron 跑：`/a/b` 照常載入成頂層，直接跑的核心仍算出 `/a`；`/a` 已是這個 daemon 另一棵 root 底下的 node 時，整份設定不收（B-606、B-628）。
- 換父兩條路：搬資料夾後新位置最近的包含 tick 成為上層、舊回址失效；改登記覆蓋時子樹沒停被拒（B-606、B-628）。

**tick–daemon 通道**

- daemon 開的 tick 有 `AOS_DAEMON_SOCKET`、`AOS_TICK_TOKEN` 兩個變數；直接跑的沒有，要走通道的客戶端自己報 `no_channel`、不連 socket（B-612、P-119）。
- 上一格的憑證拿到下一格用回 `token_invalid`；daemon 重啟後舊憑證全部失效（B-612）。
- 寄件 tick 的帳號對收件 tick 的 `.aos/mq/get/` 沒寫權，`node.send` 回 `forbidden`；對 `requests/` 有沒有寫權不影響（B-614）。回應物件跟請求一樣送得進、取得到（B-614、B-623）。
- 急件送到就叫醒收件 tick；一般件不叫醒，收件 tick 下一格用 `node.take` 取得到；daemon 重啟後暫存訊息丟失（B-614）。agent 每格收件（檔案加通道）不超過 64 件（A-201）。
- 第一格掛一個常駐行程、第四格用 `node.kill` 砍得掉而且收尾完成；別隊的 tick 砍不掉；對登記的 node 送 `node.kill`（或 `aos mount kill`）回 `kind_mismatch`（B-613、H-004 第 60 列）。
- `aos mount run` 不帶 `--parent` 被拒：人手沒有憑證（H-004 第 59 列、P-118）；`node.mount` 既沒帶 `token` 也沒帶 `parent_id`，schema 就擋下（P-118）。
- 通道客戶端只對收憑證的 method 附 `token`；對 `daemon.info`、`node.show` 附了回 `invalid_params`（B-612、P-117）。

**掛載行程與派工**

- kernel 替成員派工具時，`node.mount` 的 `parent_id` 填成員、不帶 `identity_grant`，工作歸成員；池的 `aos-llm` 掛 `aos-llm-call` 時省略 `parent_id`，歸池 node（B-613、P-402、S-307）。缺通道變數時 `aos-llm` 報 `no_channel`、結束碼 125（P-408）。
- 啟動標記已建、掛載紀錄還在跑時不重掛；daemon 重開後查不到掛載紀錄、也沒有結果和 `.err` 的，記 unknown（S-401、B-613）。
- 取消：送 TERM 後程序自己 exit 0 並完整發布，回原結果，不是 canceled（B-203）。
- 沒被叫醒過的成員不寫失聯事項（S-206）。

### 第二十批新增場景

〔第二十批〕T1、T2、T3 交來的驗收句，依主題合併；正本仍在各條，句末標條號。這些句子在沒有 cgroup、沒有 git 的機器上都要成立。

**tick 核心、停格檔與擋板檔**

- 拿掉 daemon、git、cgroup、helper 與所有系統級任務，任務表只放一項 `true`：互斥、照表跑、預設上下層與每項結束碼紀錄都成立；佇列沒人取也沒人送、不發摘要（T-07、B-626）。
- 某項建了 `.aos/tick/stop`：本格後面的項不跑，紀錄 `ended:true` 並有 `stopped_after`，整格回 1；daemon 不暫停 node，下一格照常開、核心開頭刪掉停格檔（B-620、B-633、B-607）。
- 任務回 3、100、125 或任何碼都只是一般的失敗，後面的項照跑；tick 回任何結束碼 daemon 都不暫停 node（B-620、B-607）。
- 有 `.aos/tick-blocked`：直接跑 `aos-tick` 回 1、stderr 有 `blocked`、一項都不跑、兩份紀錄與 `seq` 都不變；在 daemon 底下到期與叫醒都不開格、`paused` 不變、只寫一件事項；人手刪掉擋板後下一格照常（B-620、B-633、B-607）。
- 任務環境有 `AOS_TASK_ID`（該項 `id` 字串原樣）與 `AOS_TASK_INDEX`（陣列位置，從 0 起），另有 `AOS_NODE_DIR`、`AOS_TICK_LOCK_FD`、`AOS_TICK_RECORD`（B-620、P-203）。

**結束碼紀錄與格數**

- 任務第二項讀得到第一項的結束碼；第三項被 SIGKILL 時紀錄是 `signal:9`；tick 在某項中途被殺，下一格的 `last.json` 是 `ended:false`（B-633）。
- 同一資料夾連跑十格，`seq` 從 1 到 10，daemon 與 cron 交替跑仍連續；斷電後 `seq` 不倒退只在帶 `--firstdo-fsync`（或 daemon 帶了旗標）時要求，沒帶時不要求（B-633）；鎖被占回 75 時兩份紀錄都不變；資料夾唯讀時仍照表跑完、stderr 有 `record_unwritable`（B-633、B-627）。
- 牆鐘倒退時，以格數計的保留期不提早也不延後到期（C-01、B-404）。

**系統級任務與普通程式**

- 沒有 git 版範本任務表在沒有 git、沒有 cgroup 的機器上照常跑完；拿掉 `mq-post` 後佇列訊息不送、其餘照常；拿掉 `mq-get` 後佇列訊息留在 daemon、其餘照常（B-629、B-623）。
- `aos-needs a -- …`：`a` 失敗或還沒跑時回 125、原指令沒跑；`a` 成功時照跑、結束碼是原指令的；`b` 被擋下後 `aos-needs b -- …` 也回 125（B-621）。

**daemon（沒有 cgroup 時）**

- 任務在背景留下同一程序群組的 `sleep`，那格結束後被 runner 清掉；沒有 cgroup 也成立。runner 當收屍人是定案：runner 自己被 SIGKILL 時，掛回 daemon 的程序一律被殺、那格記 `unknown`（B-601、B-604）。
- 往收件區放新檔不會開格；daemon 只照登記週期或叫醒開格（B-504、B-607）。
- 沒有 cgroup v2 時 daemon 照常啟動、印 `cgroup=off`，沒有 `standard:` 行；設定明寫 `cgroup_root` 卻準備不好時報錯退出（125），不默默改成沒有（B-605）。
- daemon 被 SIGKILL 後重開，舊格還握著鎖時同資料夾的新格回 75、不重疊（B-603）。

### 設定、清理與待辦

驗重要設定暫停手改、確認提交再恢復；把 tasks 寫壞或寫壞 kernel 路由，resume 都不開閘、不抹手改，修好後先提交再恢復（A-102，〔第十九批〕從 P-210 搬來）；普通設定由任意可讀路徑經持同一把鎖的工具匯入，下格可讀；tick 內改設定不檢查或阻擋。滿碟不得假成功或刪原件。

清理依 [B-404](base/storage.md) 驗間隔、保留與去重證據；到期 unknown 可清，不認得的資料不碰也不回報。node 事項存 ignored `.aos/attention/`，daemon 自己事項才走 IPC；沿樹彙整清單。寫不進 node 只警告到 stdout，daemon 自己錯誤才到 stderr；啟停核對兩份 pid 檔，舊檔不拿來殺程序。show 只顯示建議，done 只將事項標完成。牆鐘大跳時到期工作仍依本 kernel 序號及額度分批放行，不重做 unknown。

### git（有就用）

〔納入 cgroup 與 git〕以下都是掛了 `aos-git` 三項、git 能用時的驗收；正本 [B-630、B-622](settled/tick.md)，句末標條號。

- 有 git 版範本：使用者任務那組有一項失敗，它寫進 `.aos/mq/post/` 的訊息在 `mark-user` 被還原、不送；它改的 `state/` 檔留著、不被提交；清理成功，那格一個 commit `aos-tick <seq>`，含清理的變動（B-630、B-629）。
- 某項建停格檔：`aos-git close` 沒跑、沒有 commit；下一格 `aos-git open` 把 `.aos/` 還原到 HEAD，這格作廢；`mq-get` 那格取出的訊息一起被還原（B-620、B-630、B-623）。
- 當機窗口：使用者任務中、close 提交前當機，下一格 `.aos/` 回 HEAD、使用者任務自己的檔不動；提交後、`mq-post` 途中當機，已提交的都在，已送的下一格重送、對方靠 ID 去重（B-625、B-624）。
- 格間手改 aos 範圍：上一格正常收尾時被下一次 close 提交；上一格沒正常收尾時被 open 還原；不留救援 ref（B-602）。
- `.gitignore` 拿掉 `/.aos/tick/` 後 `seq` 仍連續、紀錄不進 commit（B-622）。
- git 沒裝、低於 2.36、不是 repo、HEAD 讀不到：`aos-git` 三項都印 `no_git` 警告、回 0、不寫擋板，這格照 B-632（B-622）。
- 格中用 `aos node new` 建的子 node 不進上層的 commit（B-622）。
- 格結束後沒有 git 程序握著鎖 fd，下一格不回 75（B-622）。
- node 根擁有者跟 tick 帳號不同、使用者全域開了 commit 簽章時照常提交（B-622）。
- `aos-as` 開的別帳號程序寫進 aos 範圍的 0600 檔：git 讀不到，當故障，擋板＋停格檔（B-630、B-303）。
- 滿碟或 commit、還原失敗：擋板＋停格檔，不假成功；close 失敗時 `mq-post` 與發摘要不跑（B-622、B-624）。
- 任務 id 以 `.lock` 結尾的存檔點：`mark_id_invalid`，擋板＋停格檔（B-622）。
- `aos-config-add` 寫入 `config/` 不產生 commit（B-625）。
- 還原不撤銷外部效果；跨 repo／submodule 沒有共同交易（B-622）。把任務表寫壞時 resume 不開閘、不抹手改（B-625、A-102）。

### cgroup（有就用）

〔納入 cgroup 與 git〕正本 [B-605](settled/daemon/cgroup.md)、[B-634](settled/tick.md)，句末標條號。

- WSL 的 shell 直接跑（在 `/init.scope`）與用沒加 `Delegate=yes` 的 scope 開：印 `cgroup=off`；用 `systemd-run --user --scope -p Delegate=yes` 開：印 `cgroup=on`；cgroup v1、混合模式自動偵測一律 `off`（B-605）。
- 任務用 `setsid` 加 double fork 留下的殘留，格後被 `cgroup.kill`（B-601）。
- daemon 被 SIGKILL 後以新的 scope 重開：舊 scope 裡仍有程序的受管框先收到 SIGTERM、寬限後被清空，才開新格（B-603）。
- 某個 node 建框失敗：只有它照沒有 cgroup 跑、有一件事項，別的 node 照常（B-605）。
- node 自己開的子框（逃生口）：格後與重啟都不收；`kill_escape_cgroups:true` 時重啟與解除會收（B-605）。
- 某個 tick 用 `node.mount` 掛了另一個 daemon（沒寫 `cgroup_root`）：內層印 `cgroup=off` 照跑，仍受外層框的上限（B-611）。
- 兩份設定明寫同一個（或重疊的）`cgroup_root`：後啟動的回 125（B-611）。
- `aos-cg`：沒 cgroup 時退回 subreaper 加程序群組、stderr 有 `cgroup_unavailable`；`aos-cg -- aos-as <帳號> --` 時別帳號的程序在同一框；框清不空時 `frame_not_empty`、建停格檔（B-634）。
- 有程序在跑時調低記憶體上限，直接寫入、立即生效、不等全空，kernel 的資源狀態檔留 `over_limit`；OOM 證據只從框裡讀，沒框的一律不標 OOM（B-609、S-205、B-204）。
- 任務吃滿 node 記憶體、tick 被 OOM 殺掉後，daemon 仍能清空 `tick` 與 `task-*`（B-204、B-604）。
- 砍掉在跑的掛載行程後 `mount-*` 框被刪；重啟逐層重建完仍沒人登記的空框被刪，重建途中不先刪（B-603、B-613）。
- 換父搬好後框在新上層的框下；解除在跑的 node 時框被刪（B-606）。

## V-04．萬級穩態與冷啟動分開

〔建議預設，未拍板〕負載目標依 [T-05](terms.md)。同一台有配置紀錄的測試機，以 1,000→10,000 筆冷 node、相同少量活動量比較 daemon／kernel CPU、RSS、程序數、檔案與 history 讀取量、佇列等待、喚醒到啟動時間。

穩態不應每格掃全樹、讀全部 history 或替冷 node 開程序。冷啟動重建登記可以走完整棵樹，但成本另列；再分開量多層 kernel 的端到端喚醒延遲，含轉交鏈（agent→kernel→上層→池→回來）的來回延遲，每一跳至少一格（〔使用者方向 2026-09-30，第二十批〕反應速度就是一格），要能看出急件叫醒或上層 wake 縮短了多少。萬級與多層時另量補查延遲與空轉負載，確認成員多時的配置指引（[S-202](scheduling/admission.md)）夠用：單層一萬成員照預設 64 個／60 秒，補查一輪約 2.6 小時；要分別量「單層加大批量或縮短間隔」與「分層（每個子 kernel 管幾百個）」兩種配置下，補查一輪的實際時間與每格讀摘要的負載。中間層 kernel 的失聯判斷（[S-206](scheduling/admission.md)）也不能變成每格掃全部成員。無排隊時 p95 約 0.5 秒僅作起始參考，不當已裁門檻，也不混入雲端等待。

## V-05．規格自身查核

〔主編補〕檢查路徑／錨點、正本、來源及故障場景；舊條款只留殘根，protocol 舊材料不當新主規格。

從 repo 根目錄跑 `bash wf/tools/wf-lint.sh proto6`，其中 spec 的 broken 須為 0；`python3 proto6/spec/check_ids.py --strict` 須為 0（條號有定義、沒有重號、沒有只剩索引列，V-01 預留的新條號都已寫出正文）。文件通過與產品運行時驗收分開回報。
