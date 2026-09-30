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
| 05 | 寬限與強殺 | B-604（「收尾」：TERM→`shutdown_grace_ms`→`cgroup.kill`→確認全空；重啟、停機、解除、helper 停程序、取消在跑的 once 都用它）＋B-202（執行器：attempt 逾時照 inst 的寬限；`task-*` 殘留直接 `cgroup.kill`） | P-101 `shutdown_grace_ms`；P-108 helper 停程序帶設定值，不寫死 2 秒 | P-108、B-603 的寬限句；inst 的 2 秒只指 inst 自己的逾時 | T2、T3 |
| 06 | pause 批次存檔 | B-603 | P-116 存檔格式；P-101 `pause_save_interval_ms` | P-116 行為句、H-004（刪「每秒」） | T2、T6 |
| 07 | 故障停格與 node 事項 | 停格：B-607（新，從 P-105 搬上）；事項：S-405 | P-601 事項檔位置與 `daemon.attention.*` 表；P-203 結束碼表 | P-105、P-205、P-609、P-601 行為句、B-601 的事項句 | T2、T5（S-405）、T3（P-203、P-205、P-601、P-609） |
| 08 | tick 任務表 | B-620（新編號，tick.md「任務註冊表」節：順序、類別與自訂種類、`methods` 欄的意思、一個 module 一項任務） | P-202 欄位表、JSON、schema | tick.md 欄位表刪、H-004 | T3、T6 |
| 09 | Q1／Q2 | B-623（Q1）、B-624（Q2）（新編號，tick.md 兩節；P-206 的交接行為搬上） | P-206 只留待送檔與鬧鐘檔格式 | P-003、P-206、P-305、B-402、B-503、A-201、agent/README、P-704、P-800 | T3、T1（P-003）、T6、T5（P-800） |
| 10 | 投件失敗、鬧鐘 | B-624 | P-206 鬧鐘與待送檔欄位 | S-301、P-303、P-701、P-706、V-03、H-004 | T3、T4（S-301）、T6、T1（V-03） |
| 11 | method 開放、-32601 | B-501（method 就是指令；-32601 只表示沒任務宣告或 argv 不符，未授權走 -32000 業務碼；投件權即執行權）＋B-620（`methods` 欄） | P-202 `methods` 格式；P-306 method 目錄 | P-004、P-306（兩處）、H-030 | T3、T1（P-004）、T6（H-030） |
| 12 | 去重、同 ID 衝突、重送 | B-503（P-304 的重送與補投回應規則搬上） | P-304 只留檔名與比對格式 | P-003、P-304、C-03 | T3、T1（P-003、C-03） |
| 13 | 工作材料、attempt、結果 | T-03（識別）＋B-101（固定材料與預設值）＋B-103（結果） | P-401～403 只留 payload、工作目錄命名、結果 JSON | C-03、B-201、P-400～403 行為句、S-104 | T3、T4（P-400～403）、T5（S-104） |
| 14 | 取消 | B-203（核權的兩種主人、排隊中拿掉、在跑的請 daemon 收尾；只適用 once，其他任務的取消延後） | P-411 只留 `work.cancel` 請求、回應、錯誤碼 | P-411 行為句、P-306 表、P-806、S-102、S-304 | T3（B-203）、T4（P-411、S-304）、T5（P-806、S-102） |
| 15 | unknown 放著不重做 | S-401（原則＋證據判斷，從 P-807 搬上） | — | P-404、C-03、S-104、P-807、B-404、P-606、P-814、P-716、A-503 | T5、T4（P-404）、T1（C-03）、T3（B-404、P-606）、T6（P-716、A-503） |
| 16 | once、從未啟動證據 | B-606（once 登記、跑一格自動解除、資源歸 parent）＋S-401（從未啟動證據的判讀） | P-104 once 欄位；P-110 `.err` 格式 | P-402、P-709、P-807、P-008 | T2、T5、T4（P-402）、T6（P-709）、T1（P-008） |
| 17 | 資源 module、配額 | S-203（改寫：aos 只給框架，六類是預設範本的資源，kernel 可自訂資源名；cgroup 與身分額度維持巢狀） | P-500～507 只留配額、用量檔格式與 cgroup 檔對照 | B-301、B-304、B-605、P-107、P-804、V-03 | T5、T2、T3、T1（V-03） |
| 18 | LLM：三檔、兩條路線、份額、key、重試 | S-301～305（兩條路線表只留 S-301，從 P-813 搬上） | P-405～407 池設定、請求、結果；P-505 份額格式；P-811 池狀態格式；P-813 只留範本欄位怎麼填 | H-004、A-101、P-400、P-701、P-809、V-03 | T4、T5（P-505、P-811、P-813）、T6、T1（V-03） |
| 19 | agent 設定原則、`in_reply_to` | A-102（原則）＋A-201（`in_reply_to` 配對，從 P-705 搬上） | P-705 欄位 | P-203、P-701、P-805 的原則句；其餘 `in_reply_to` 各處 | T6、T3（P-203）、T5（P-805） |
| 20 | 清理、保留期、待辦 | B-404（清理資格、保留期）＋S-405（`aos attend` 三個動作） | P-605／606 清理設定與報告；P-603 argv 與輸出 | P-601、P-716、P-814、H-004、P-603 行為句 | T3、T5、T6 |
| 21 | 錯誤碼與結束碼 | C-04（原則）；碼值屬格式，正本 P-005／P-006 與各篇碼表 | 各篇自己的碼表；集中碼表在 P-006 | H-002 連集中碼表；設定檢查 kernel 2、agent 1 的不一致延後 | T1、各隊 |
| 22 | helper | B-303（角色與界線）＋B-609（新：固定動作清單與各動作做什麼，含新加的動作，從 P-107 搬上） | P-107 參數；P-108 私有通道 | B-601、P-102、H-004、B-605 | T3（B-303）、T2、T6 |
| 23 | inst | [inst](base/inst.md)（新增「inst 目標：檔案或資料夾」節，從 P-010 搬上） | node-inst schema | P-010（inst 篇寫好後由 T1 縮成殘根）、P-200、P-201、P-109 | T3、T1、T2（P-109） |
| 24 | 結構問題 | — | — | B-504：transport 的標題改成非標題的一行殘根；P-100～116 條號表只留 daemon/README，protocol/daemon.md 縮成一句連結；P-001 改寫 | T3、T2、T1 |

### 新條號

〔主編補，第十八批〕正本表用到的新條號先在下表預留；主責隊照這裡的號碼與主題開條，標題格式照該篇現有寫法。B-6xx 由 daemon.md 與 tick.md 共用，所以 daemon.md 從 606 起、tick.md 從 620 起，tick.md 現有沒編號的各節照下表補號（補號不算重編）。

<!-- check_ids:reserved -->
| 條號 | 檔 | 主題 | 落筆 |
|---|---|---|---|
| B-606 | daemon.md | 登記、解除（收尾）、換父、前綴／範圍額度、once 登記 | T2 |
| B-607 | daemon.md | 叫醒、暫停與故障停格 | T2 |
| B-608 | daemon.md | 熱重載與「即時改／要重開」表 | T2 |
| B-609 | daemon.md | 佈建固定動作與 helper 動作 | T2 |
| B-610 | daemon.md | once 診斷的淘汰與清除 | T2 |
| B-620 | tick.md | 任務註冊表（原「任務註冊表」節補號） | T3 |
| B-621 | tick.md | group 與 needs（原節補號） | T3 |
| B-622 | tick.md | git 提交與還原（原節補號） | T3 |
| B-623 | tick.md | 收件：commit 後才刪原件（Q1）（原節補號） | T3 |
| B-624 | tick.md | 派出：先 commit 請求，再送出（Q2）（原節補號） | T3 |
| B-625 | tick.md | 當機恢復、設定與清理（原節補號） | T3 |
| B-626 | tick.md | tick 是基底：系統性任務的範圍 | T3 |
| B-627 | tick.md | 人手跑一格：不在正確的框就拒跑 | T3 |

預留表以外要開新條，就接各篇下一號，不必先登記：

| 篇 | 下一號 |
|---|---|
| daemon.md | B 611 起（到 619 為止） |
| tick.md | B 628 起 |
| base/work.md、execution.md、identity-resources.md、storage.md、transport.md | B 104、205、306、405、506 起（305 是已刪的舊號，不要再用） |
| scheduling/runs.md、admission.md、llm.md、operations.md | S 105、205、307、406 起 |
| agent/configuration.md、input.md、memory.md、tools.md、README.md | A 104、204、304、405、507 起 |
| cli/ | H 037 起 |
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

父層分給子層的 cgroup 上限與身分額度不能被子層加大；kernel 自訂、Linux 管不到的資源與隔離可以跟上層不同，上層不認得的不代管、不報錯（[T-06](terms.md)）。子層未裝某 module 不另記或另限，但父層限制仍有效。兩個 kernel 可各有 endpoint 池，各池核對真正共享的 provider 限制。測 429 退避、送出後斷線及部分內容；部分回覆不能冒充完成，unknown 不因一般 retryable 標記而重試。

LLM 三檔（[S-301](scheduling/llm.md)）：預設 `schedule:aos` 的池做窗口與冷卻，`schedule:endpoint` 的池只轉發、不讀窗口設定，遇 429 也不重試；投給不是 node 的路徑、或沒有寫入權限，當場報一次錯、丟掉待送檔、不寫待辦、不重試，投給沒人處理的 node 就堆著，設了 `alarm_ms` 的到期後原件還在就報 `request_not_handled`。指定 stream_path 時呼叫途中檔案持續變長，中途斷線任務非 0 結束、結果不算成功。

分開驗證 key 部署：無 helper 且代發／agent 同帳號時，或 agent 自己打 endpoint 的直連檔，文件須明說 key 不受保護；採獨立服務帳號保護時，整條投件鏈以外的 node 與工具不可讀 key；能投件給持 key node 的帳號等於能用它的身分，不在保護範圍內（[T-08](terms.md)）。上層查詢只取下層摘要，未授權者不能因猜 ID 讀內容。

### 第十八批新增場景

〔第十八批〕熱重載、排空停機、換父、前綴額度、cgroup 上限隨時改、人手跑 tick、版本演進與禁止鍵等新規則的驗收句，由各主責隊交來後依主題補在本節；正本仍在各篇。版本演進的驗收見 [C-07](contracts.md)。

### 設定、清理與待辦

驗重要設定暫停手改、確認提交再恢復；普通設定由任意可讀路徑經持同一把鎖的工具匯入，下格可讀；tick 內改設定不檢查或阻擋。滿碟或 commit／還原失敗不得假成功、刪原件或開新格。

清理依 [B-404](base/storage.md) 驗間隔、保留與去重證據；到期 unknown 可清，不認得的資料不碰也不回報。node 事項存 ignored `.aos/attention/`，daemon 自己事項才走 IPC；沿樹彙整清單。寫不進 node 只警告到 stdout，daemon 自己錯誤才到 stderr；啟停核對兩份 pid 檔，舊檔不拿來殺程序。show 只顯示建議，done 只將事項標完成。牆鐘大跳時到期工作仍依本 kernel 序號及額度分批放行，不重做 unknown。

## V-04．萬級穩態與冷啟動分開

〔建議預設，未拍板〕負載目標依 [T-05](terms.md)。同一台有配置紀錄的測試機，以 1,000→10,000 筆冷 node、相同少量活動量比較 daemon／kernel CPU、RSS、程序數、檔案與 history 讀取量、佇列等待、喚醒到啟動時間。

穩態不應每格掃全樹、讀全部 history 或替冷 node 開程序。冷啟動重建登記可以走完整棵樹，但成本另列；再分開量多層 kernel 的端到端喚醒延遲，含轉交鏈（agent→kernel→上層→池→回來）的來回延遲，每一跳至少一個 tick 間隔，要能看出收件通知或 wake 縮短了多少。萬級與多層時另量補查延遲與空轉負載，確認成員多時的配置指引（[P-801](protocol/kernel-tasks.md)）夠用。無排隊時 p95 約 0.5 秒僅作起始參考，不當已裁門檻，也不混入雲端等待。

## V-05．規格自身查核

〔主編補〕檢查路徑／錨點、正本、來源及故障場景；舊條款只留殘根，protocol 舊材料不當新主規格。

從 repo 根目錄跑 `bash wf/tools/wf-lint.sh proto6`，其中 spec 的 broken 須為 0；`python3 proto6/spec/check_ids.py --strict` 須為 0（條號有定義、沒有重號、沒有只剩索引列，V-01 預留的新條號都已寫出正文）。文件通過與產品運行時驗收分開回報。
