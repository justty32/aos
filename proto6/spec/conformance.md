# 完整性與驗收入口

← [規格入口](README.md)

## V-01．何時算拆到可實作

〔主編補〕有效規則須能找到責任、輸入輸出、失敗處理及驗收；共用定義用連結，未裁選擇保持標記。以下**不是已執行的產品測試**。

### 正本規則

〔使用者方向 2026-09-30，第十八批〕**主規格是正本**（方案 A）：

- 行為規則只寫在主規格；協議篇只留欄位、JSON、schema、範例、method／argv 形狀、結束碼與錯誤碼，寫到行為時只留一句加主規格條號（[P-001](protocol/README.md)）。各協議檔對應的主規格見 [P-009](protocol/README.md)。
- 同一主題分散兩處的，照下面的正本表：正本那邊寫全，其他地方改成一句加條號。只寫在協議篇的行為，改到時搬到正本，原處留一句加條號。
- 條號不重編；內容搬走的條留一句殘根加連結。新條號接在該篇現有號碼後面（見文末「新條號」）。
- 被推翻的舊說法直接改掉，不留刪除線；需要交代來源的在條文後標〔使用者方向 2026-09-30，第十八批〕。延後項只寫一句並連到 [P-008](protocol/README.md#p-008)。

### 概念與正本

| 概念 | 規格正本 |
|---|---|
| 定位、多層多 kernel、各 kernel 自訂、上下層不必對齊 | [T-06](terms.md) |
| tick 是基底；投件權就是執行權 | [T-07、T-08](terms.md) |
| node 與兼任角色、兩張註冊表 | [T-02](terms.md) |
| node 登記、喚醒、全殺重啟、逐層重建、停機、熱重載 | [daemon](daemon.md) |
| 任務順序、group／needs、互斥、git、Q1／Q2 | [tick](tick.md) |
| 身分額度、可選 helper；inst 欄位與解析 | [身分](base/identity-resources.md)、[inst](base/inst.md) |
| 工作材料、可信結果、後代收尾、取消 | [work](base/work.md)、[execution](base/execution.md) |
| 追蹤／ignored 區、完整發布、去重與清理 | [storage](base/storage.md)、[transport](base/transport.md) |
| kernel 樹、資源 module 與 LLM 池 | [scheduling](scheduling/README.md) |
| 可選 run、unknown 與待辦彙整 | [runs](scheduling/runs.md)、[operations](scheduling/operations.md) |
| agent 任務、設定、context、工具、完成證據 | [agent](agent/README.md) |
| 中間層 kernel 卡住、給 kernel 的一般回話 | [S-206](scheduling/admission.md)、[S-406](scheduling/operations.md) |
| 跨篇 ID、時間、結果與錯誤；版本演進與禁止鍵 | [contracts](contracts.md)（C-07） |
| 錯誤碼與結束碼在哪定 | [集中碼表](protocol/README.md#集中碼表) |
| 延後項 | [P-008](protocol/README.md#p-008) |

### 正本表

〔主編補，第十八批〕審稿找出 24 個寫在兩處以上的主題。「新」表示這輪要新開的條，號碼見文末預留表；搬家由正本那篇的主責隊落筆，別隊把要改的句子交給主責隊。

| # | 主題 | 行為正本（主規格） | 協議篇只留 | 改成一句加條號 | 落筆 |
|---|---|---|---|---|---|
| 01 | cgroup 子樹、框命名、`task-*` 層 | B-605（子樹、命名、委派；內部重述併掉）＋B-202（`task-*` 的開、殺、刪與格首清上一格殘留，從 P-203 搬上） | P-101 `cgroup_root` 欄位；P-107 上限參數 | P-107、P-101 欄位說明、P-503、P-203 的框規則、H-036 | T2、T3（B-202、P-203）、T5（P-503）、T6（H-036） |
| 02 | 重啟：全殺、收尾、boot id、逐層重建 | B-603 | P-116 `state.json` 格式；P-115 `boot_id` 欄位 | P-116、P-115 的行為句；P-814、P-812、H-004、V-03、B-605 驗收句 | T2、T5（P-812、P-814）、T6（H-004）、T1（V-03） |
| 03 | 停機：短寬限與排空 | B-604 | P-114 只留訊號、結束碼與設定欄位 | P-114 行為段、H-004、V-03 | T2、T6、T1 |
| 04 | 登記、解除、別每格重登、換父 | B-601（總則）＋B-606（新：登記規則、解除即收尾、換父、前綴／範圍額度，從 P-104／105 搬上） | P-103～106 只留 method、params、result、錯誤碼 | P-104／105 的行為句、P-115、P-802（daemon 那側改引用；kernel 何時登記成員歸 S-202）、H-004 | T2、T5（P-802、S-202）、T6 |
| 05 | 寬限與強殺 | B-604（「收尾」：TERM→`shutdown_grace_ms`→`cgroup.kill`→確認全空；重啟、停機、解除、helper 停程序、取消在跑的 once 都用它；範圍是 `tick`、`task-*`、`once-*` 與子 node 框，逃生口照 `kill_escape_cgroups`）＋B-202（執行器：attempt 逾時照 inst 的寬限；`task-*` 殘留直接 `cgroup.kill`） | P-101 `shutdown_grace_ms`；P-108 helper 停程序帶設定值，不寫死 2 秒 | P-108、B-603 的寬限句；inst 的 2 秒只指 inst 自己的逾時 | T2、T3 |
| 06 | pause 批次存檔 | B-603 | P-116 存檔格式；P-101 `pause_save_interval_ms` | P-116 行為句、H-004（刪「每秒」） | T2、T6 |
| 07 | 故障停格與 node 事項 | 停格：B-607（新，從 P-105 搬上）；事項：S-405 | P-601 事項檔位置與 `daemon.attention.*` 表；P-203 結束碼表 | P-105、P-205、P-609、P-601 行為句、B-601 的事項句 | T2、T5（S-405）、T3（P-203、P-205、P-601、P-609） |
| 08 | tick 任務表 | B-620（新編號，tick.md「任務註冊表」節：順序、類別與自訂種類、`methods` 欄的意思、一個 module 一項任務） | P-202 欄位表、JSON、schema | tick.md 欄位表刪、H-004 | T3、T6 |
| 09 | Q1／Q2 | B-623（Q1）、B-624（Q2）（新編號，tick.md 兩節；P-206 的交接行為搬上） | P-206 只留待送檔與鬧鐘檔格式 | P-003、P-206、P-305、B-402、B-503、A-201、agent/README、P-704、P-800 | T3、T1（P-003）、T6、T5（P-800） |
| 10 | 投件失敗、鬧鐘 | B-624 | P-206 鬧鐘與待送檔欄位 | S-301、P-303、P-701、P-706、V-03、H-004 | T3、T4（S-301）、T6、T1（V-03） |
| 11 | method 開放、-32601 | B-501（method 就是指令；-32601 只表示沒任務宣告或 argv 不符，未授權走 -32000 業務碼；投件權即執行權）＋B-620（`methods` 欄） | P-202 `methods` 格式；P-306 method 目錄 | P-004、P-306（兩處）、H-030 | T3、T1（P-004）、T6（H-030） |
| 12 | 去重、同 ID 衝突、重送 | B-503（P-304 的重送與補投回應規則搬上） | P-304 只留檔名與比對格式 | P-003、P-304、C-03 | T3、T1（P-003、C-03） |
| 13 | 工作材料、attempt、結果 | T-03（識別）＋B-101（固定材料與預設值）＋B-103（結果） | P-401～403 只留 payload、工作目錄命名、結果 JSON | C-03、B-201、P-400～403 行為句、S-104 | T3、T4（P-400～403）、T5（S-104） |
| 14 | 取消 | B-203（核權的兩種主人、排隊中拿掉、在跑的請 daemon 收尾；只適用 once，其他任務的取消延後） | P-411 只留 `work.cancel` 請求、回應、錯誤碼 | P-411 行為句、P-306 表、P-806、S-102、S-304 | T3（B-203）、T4（P-411、S-304）、T5（P-806、S-102） |
| 15 | unknown 放著不重做 | S-401（原則＋證據判斷，從 P-807 搬上） | P-807 只留啟動標記等檔案位置 | P-404、C-03、S-104、P-807、B-404、P-606、P-814、P-716、A-503 | T5、T4（P-404）、T1（C-03）、T3（B-404、P-606）、T6（P-716、A-503） |
| 16 | once、從未啟動證據 | B-606（once 登記、跑一格自動解除、資源歸 parent）＋S-401（從未啟動證據的判讀） | P-104 once 欄位；P-110 `.err` 格式 | P-402、P-709、P-807、P-008 | T2、T5、T4（P-402）、T6（P-709）、T1（P-008） |
| 17 | 資源 module、配額 | S-203（框架：六類是預設範本的資源，kernel 可自訂資源名；cgroup 與身分額度維持巢狀）＋S-205（套用、調整與故障，從 P-504、P-507 搬上）＋S-206（中間層 kernel 卡住）＋S-207（用量收集與去重，從 P-810、P-502 搬上） | P-500～507 只留配額、用量檔格式與 cgroup 檔對照；P-810 只留 argv 與檔案 | B-301、B-304、B-605、P-107、P-804、V-03 | T5、T2、T3、T1（V-03） |
| 18 | LLM：三檔、兩條路線、份額、key、重試 | S-301～307（兩條路線表只留 S-301，從 P-813 搬上；S-302 加「份額扣在誰身上」「池的共享窗口」，從 P-809、P-811 搬上；S-307 池 node 的任務與收件） | P-405～407 池設定、請求、結果；P-505 份額格式；P-809、P-811 只留 argv 與狀態檔格式；P-813 只留範本權限 | H-004、A-101、P-400、P-701、P-809、V-03 | T4、T5（P-505、P-811、P-813）、T6、T1（V-03） |
| 19 | agent 設定原則、`in_reply_to` | A-102（原則）＋A-201（`in_reply_to` 配對，從 P-705 搬上） | P-705 欄位 | P-203、P-701、P-805 的原則句；其餘 `in_reply_to` 各處 | T6、T3（P-203）、T5（P-805） |
| 20 | 清理、保留期、待辦 | B-404（清理資格、保留期）＋S-405（`aos attend` 三個動作） | P-605／606 清理設定與報告；P-603 argv 與輸出 | P-601、P-716、P-814、H-004、P-603 行為句 | T3、T5、T6 |
| 21 | 錯誤碼與結束碼 | C-04（原則）；碼值屬格式，正本 P-005／P-006 與各篇碼表 | 各篇自己的碼表；集中碼表在 P-006 | H-002 連集中碼表；設定檢查 kernel 2、agent 1 的不一致延後 | T1、各隊 |
| 22 | helper | B-303（角色與界線）＋B-609（新：固定動作清單與各動作做什麼，含新加的動作，從 P-107 搬上） | P-107 參數；P-108 私有通道 | B-601、P-102、H-004、B-605 | T3（B-303）、T2、T6 |
| 23 | inst | [inst](base/inst.md)（新增「inst 目標：檔案或資料夾」節，從 P-010 搬上） | node-inst schema | P-010（inst 篇寫好後由 T1 縮成殘根）、P-200、P-201、P-109 | T3、T1、T2（P-109） |
| 24 | 結構問題 | — | — | B-504：transport 的標題改成非標題的一行殘根；P-100～116 條號表只留 daemon/README，protocol/daemon.md 縮成一句連結；P-001 改寫 | T3、T2、T1 |

### 新條號

〔主編補，第十八批〕第十八批新開的條號如下（先預留、各隊已寫出正文；`check_ids --strict` 會核對每一列都有正文）。B-6xx 由 daemon.md 與 tick.md 共用，所以 daemon.md 從 606 起、tick.md 從 620 起，tick.md 現有沒編號的各節照下表補號（補號不算重編）。

<!-- check_ids:reserved -->
| 條號 | 檔 | 主題 | 落筆 |
|---|---|---|---|
| B-606 | daemon.md | 登記、解除（收尾）、換父、前綴／範圍額度、once 登記 | T2 |
| B-607 | daemon.md | 叫醒、暫停與故障停格 | T2 |
| B-608 | daemon.md | 熱重載與「即時改／要重開」表 | T2 |
| B-609 | daemon.md | 佈建固定動作與 helper 動作 | T2 |
| B-610 | daemon.md | once 診斷的留存、淘汰與清除 | T2 |
| B-611 | daemon.md | 一棵資源樹只准一個 daemon | T2 |
| B-620 | tick.md | 任務註冊表（原「任務註冊表」節補號） | T3 |
| B-621 | tick.md | group 與 needs（原節補號） | T3 |
| B-622 | tick.md | git 提交與還原（原節補號） | T3 |
| B-623 | tick.md | 收件：commit 後才刪原件（Q1）（原節補號） | T3 |
| B-624 | tick.md | 派出：先 commit 請求，再送出（Q2）（原節補號） | T3 |
| B-625 | tick.md | 當機恢復、設定與清理（原節補號） | T3 |
| B-626 | tick.md | tick 是基底：系統性任務的範圍 | T3 |
| B-627 | tick.md | 人手跑一格：不在正確的框就拒跑 | T3 |
| S-205 | scheduling/admission.md | 套用、調整與故障 | T5 |
| S-206 | scheduling/admission.md | 中間層 kernel 卡住 | T5 |
| S-207 | scheduling/admission.md | 用量收集與去重 | T5 |
| S-307 | scheduling/llm.md | 池 node 的任務與收件 | T4 |
| S-406 | scheduling/operations.md | 給 kernel 的一般回話 | T5 |
| H-037 | cli/debugging.md | 除錯指南 | T6 |

之後要開新條，就接各篇下一號：

| 篇 | 下一號 |
|---|---|
| daemon.md | B 612 起（到 619 為止） |
| tick.md | B 628 起 |
| base/work.md、execution.md、identity-resources.md、storage.md、transport.md | B 104、205、306、405、506 起（305 是已刪的舊號，不要再用） |
| scheduling/runs.md、admission.md、llm.md、operations.md | S 105、208、308、407 起 |
| agent/configuration.md、input.md、memory.md、tools.md、README.md | A 104、204、304、405、507 起 |
| cli/ | H 038 起 |
| terms.md、contracts.md、conformance.md | T 10、C 08、V 06 起 |
| 協議篇 | 接各檔現有最後一號 |

## V-02．先測行為，再測規模

〔建議預設，未拍板〕先用假工具／mock LLM 驗檔案交接、git、授權及結果。再在可丟棄的 Linux／WSL 環境，驗無 helper 通用 user、有 helper 兩個真 UID、已裝 module 與後代清理；最後測萬級冷 node。〔使用者方向 2026-09-29 晚〕cgroup 子樹依 [B-605](daemon.md) 至少驗兩種：事先準備好的子樹，以及開 `--create-cgroup` 由 daemon 自己建。

保存版本、配置、環境與結果；mock 不代表 OS 隔離已驗證，磁碟記帳不算硬限制。範圍依[平台邊界](README.md)，須涵蓋同機 node 樹。

## V-03．跨篇故障場景

〔建議預設，未拍板〕以下測試交叉覆蓋已裁規則與各篇工程預設；具體預設仍依正本來源。

### node、登記與身分

驗兼任 kernel／agent、只有收信任務及空成員表，角色須依任務判定。正常重開讀回登記、pause 與 wake，意外重開最多丟最後一個存檔間隔的 pause；無快照也自動 tick 頂層，boot id 變更後逐層補登記，壞成員留待辦、不擋其餘成員；漏通知可補查，重複叫醒不並行同 node 的兩格。

啟動自檢依 [B-605](daemon.md)：kernel／Python／git 版本不足、沒有 cgroup v2、沒有準備好的子樹又沒開 `--create-cgroup` 都報錯退出；quota 偵測到但設定強制關時不用。

測 socket 冒名、超額授予／宣告 user、不懂 user 語意、無 helper 繼承與切 UID 後開檔。超額須 125、不啟動、不寫 `exit` 並留待辦；整份 `$ref` 可用但不能偷換身分，搬資料夾也不能取得新身分。

### group、收件與派出

前組成功、後組失敗：前組保留，後組修改／新增檔還原，ignored 收件不丟；改 `.gitignore` 不能躲還原。失敗組不能滿足跨組 needs，獨立組可繼續；壞表整格不跑，無變動不 commit。

在複製收件、commit、刪原件各窗口中斷，不遺失或重吃；同 ID 異內容報衝突。請求與回應未 commit 不送，tick 只重投相同 ID／bytes，執行不明仍 unknown、不自動重做；還原不撤銷外部效果，跨 repo／submodule 無共同交易。

### 程序與結果

daemon 或 VM 突然消失後，全殺舊 tick 與受管後代才重開；主程序已退、孫程序仍活也不能報清空。daemon 被 SIGKILL 後重開，仍有程序的 node cgroup 先收到 SIGTERM、寬限後才 `cgroup.kill`；正常 Ctrl-C 時在途 tick 也先收到信號。已 commit 狀態與完整結果保留，未 commit 還原；無可信結果的在途工作不能自動再跑。取消與完成競爭只發布一次結果，晚到舊結果不覆寫新嘗試，同一結果與用量不重複採計；沒有 OOM 證據不能只憑 SIGKILL 猜原因。

### 分層資源與 LLM

父層分給子層的 cgroup 上限與身分額度不能被子層加大；kernel 自訂、Linux 管不到的資源與隔離可以跟上層不同，上層不認得的不代管、不報錯（[T-06](terms.md)）。子層未裝某 module 不另記或另限，但父層限制仍有效。兩個 kernel 可各有 endpoint 池；同一 provider 限制怎麼分、要不要共用一池，照各 kernel 自己的資源政策（[T-06](terms.md)），不靠同名 scope 跨 node 同步。測 429 退避、送出後斷線及部分內容；部分回覆不能冒充完成，unknown 不因一般 retryable 標記而重試。

LLM 三檔（[S-301](scheduling/llm.md)）：預設 `schedule:aos` 的池做窗口與冷卻，`schedule:endpoint` 的池只轉發、不讀窗口設定，遇 429 也不重試；投給不是 node 的路徑、或沒有寫入權限，當場報一次錯、丟掉待送檔、不寫待辦、不重試；投給有 tick 但沒任務宣告的 node、或沒被 tick 的 node，分兩種情況驗，見下面「第十八批新增場景」的 LLM 段。指定 stream_path 時呼叫途中檔案持續變長，中途斷線任務非 0 結束、結果不算成功。

分開驗證 key 部署：無 helper 且代發／agent 同帳號時，或 agent 自己打 endpoint 的直連檔，文件須明說 key 不受保護；採獨立服務帳號保護時，整條投件鏈以外的 node 與工具不可讀 key；能投件給持 key node 的帳號等於能用它的身分，不在保護範圍內（[T-08](terms.md)）。上層查詢只取下層摘要，未授權者不能因猜 ID 讀內容。

### 第十八批新增場景

〔第十八批〕以下由各主責隊交來的驗收句依主題合併；正本仍在各條，句末標條號。版本演進的通則驗收見 [C-07](contracts.md)。

**daemon 啟動、熱重載與停機**

- 兩份設定用不同 socket、指向同一或重疊的 `cgroup_root`／`state_dir`：後啟動的回 125 拒絕，先啟動的不受影響（B-611）。git 低於 2.36 啟動報錯（B-605）。
- SIGHUP 後改 `interval_ms`、加一棵只用通用 user 的 root，立即生效；同時改 `socket_path` 或其他帳號的額度時，其餘照套、這些欄位回報要重開；壞設定整份不套、舊設定照跑（B-608）。
- `stop_mode:"drain"` 收 SIGTERM：新 once 被拒、已登記 node 照常開格、在途做完回 0；超過 `drain_timeout_ms` 或再按一次 Ctrl-C 改立即停（B-604）。
- 斷電模擬：commit 成功後才刪收件原件，重開後物件與 ref 都在（B-622、B-623）。

**登記、換父、額度與格次**

- 換父：子樹沒停、或新父在被搬的子樹裡，被拒；只有一方父的 owner 同意，被拒；搬好後框在新父下，`registration_id` 換新（B-606）。
- 前綴規則比不中 UID 小於 1000 的帳號；子額度寫了父沒有的前綴或更大的範圍，被拒（B-606）。上層收小身分額度後，重登被拒的成員只隔離那一項並記事項，其他成員照常（B-607、S-205）。
- 成員跑完一格、摘要沒變且牆鐘倒退，kernel 仍靠 `tick_seq` 認出新格；daemon 重啟後 `registration_id` 換了，kernel 重新核對、不空等（B-607、B-627）。
- 乾淨停機後 once 仍登記、`last_tick` 為 null，可以第一次叫醒；意外重開後沒有結果也沒有 `.err` 的 once 記 unknown、不再啟動（B-606、S-401）。
- 已解除的 once 紀錄超過容量或保留期就消失；`aos once clear` 帶父 node 只清整棵子樹下已結束、呼叫者有權清的紀錄，在跑的與別人的不動（B-610）。

**框、收尾與佈建**

- 取消在跑的 once：寬限後被殺、框被刪（B-203、B-604）。重啟逐層重建完仍沒人登記的空框被刪，重建途中不先刪（B-603）。
- node 自開的子框：預設重啟與解除後程序還在；設 `kill_escape_cgroups:true` 時被清空（B-605）。
- 任務吃滿 node 記憶體、tick 被 OOM 殺掉後，daemon 仍能清空 `tick` 與 `task-*`（B-204、B-604）。
- 多帳號部署下兩個 node 帳號靠 `group_create`、`group_add_member`、`chgrp` 交接檔案（B-609）。有程序在跑時調低記憶體上限，直接寫入、立即生效、不等全空，kernel 的資源狀態檔留 `over_limit`（B-609、S-205）。頂層額度改到小於已分出的合計：不自動收回，記 `over_allocated`、寫事項、停新派工，在跑的照跑（S-205）。

**tick 基底、method 與人手跑一格**

- 範本任務表沒有 system 類也能正常跑；`kind:"agent.review"` 照收，`system.x` 或任一項帶 `user` 整份拒收（B-620、B-626、C-07）。
- 在 daemon 的框外直接跑 `aos-tick` 回 2，不取鎖、不改檔、不開任務（B-627）。`aos node tick` 經 daemon：送 wake 後看到 `tick_seq` 變大才回 0，逾時回 101，paused 回 1 不等（B-627、H-004）。
- 沒人宣告的 method 回 -32601；有宣告但來源未授權回 -32000 加業務碼（B-501）。

**收件、投件與取消**

- 同一個壞收件連跑多格只有一件事項；過保留期由 `aos-clean` 刪，期內留著（B-623、B-404）。
- 同 ID 重送時補投的回應，是 git 歷史裡原待送回應的原 bytes；本地動作回應的 `stdout.path` 指向存在的 `.stdout` 檔（B-503、B-624）。
- 取消：node 根目錄擁有者與 inst 執行帳號不同時，兩者送的取消都收；其他人回 `cancel_not_authorized`，原工作照跑；once 自己 inst 的 user 被拒（B-203）。記了 canceling 的那格不 unregister；`not_registered` 又沒有可信證據時記 unknown；進 canceling 前已經有完整結果的照原結果（B-203、P-411）。
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

- LLM 池設定帶 `api_key`、agent／kernel 範本的任務表任一項帶 `user`，整份拒收；agent 設定、kernel 持久檔、LLM 池設定多一個不認得的欄位照樣讀進（C-07）。`work-result` 的 signal 65 拒收（P-403）。

### 設定、清理與待辦

驗重要設定暫停手改、確認提交再恢復；普通設定由任意可讀路徑經持同一把鎖的工具匯入，下格可讀；tick 內改設定不檢查或阻擋。滿碟或 commit／還原失敗不得假成功、刪原件或開新格。

清理依 [B-404](base/storage.md) 驗間隔、保留與去重證據；到期 unknown 可清，不認得的資料不碰也不回報。node 事項存 ignored `.aos/attention/`，daemon 自己事項才走 IPC；沿樹彙整清單。寫不進 node 只警告到 stdout，daemon 自己錯誤才到 stderr；啟停核對兩份 pid 檔，舊檔不拿來殺程序。show 只顯示建議，done 只將事項標完成。牆鐘大跳時到期工作仍依本 kernel 序號及額度分批放行，不重做 unknown。

## V-04．萬級穩態與冷啟動分開

〔建議預設，未拍板〕負載目標依 [T-05](terms.md)。同一台有配置紀錄的測試機，以 1,000→10,000 筆冷 node、相同少量活動量比較 daemon／kernel CPU、RSS、程序數、檔案與 history 讀取量、佇列等待、喚醒到啟動時間。

穩態不應每格掃全樹、讀全部 history 或替冷 node 開程序。冷啟動重建登記可以走完整棵樹，但成本另列；再分開量多層 kernel 的端到端喚醒延遲，含轉交鏈（agent→kernel→上層→池→回來）的來回延遲，每一跳至少一個 tick 間隔，要能看出收件通知或 wake 縮短了多少。萬級與多層時另量補查延遲與空轉負載，確認成員多時的配置指引（[S-202](scheduling/admission.md)）夠用：單層一萬成員照預設 64 個／60 秒，補查一輪約 2.6 小時；要分別量「單層加大批量或縮短間隔」與「分層（每個子 kernel 管幾百個）」兩種配置下，補查一輪的實際時間與每格讀摘要的負載。中間層 kernel 的失聯判斷（[S-206](scheduling/admission.md)）也不能變成每格掃全部成員。無排隊時 p95 約 0.5 秒僅作起始參考，不當已裁門檻，也不混入雲端等待。

## V-05．規格自身查核

〔主編補〕檢查路徑／錨點、正本、來源及故障場景；舊條款只留殘根，protocol 舊材料不當新主規格。

從 repo 根目錄跑 `bash wf/tools/wf-lint.sh proto6`，其中 spec 的 broken 須為 0；`python3 proto6/spec/check_ids.py --strict` 須為 0（條號有定義、沒有重號、沒有只剩索引列，V-01 預留的新條號都已寫出正文）。文件通過與產品運行時驗收分開回報。
