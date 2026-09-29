# proto6 spec 重寫逐條處置表

← [計畫入口](README.md)｜架構依據：[kernel 樹](../2026-09-29-kernel-tree.md)

> 09-29 規劃產出。規劃完成後使用者又定了第六批（身分額度、inst user 欄位、daemon 細節、Q1～Q4 照建議），以[裁定紀錄](../2026-09-29-verdicts.md)為準。

2026-09-29。這是改寫計畫，不是新規格、不是產品裁定；本次沒有修改 repo。條款來源以當前工作樹為準，範圍是 `proto6/spec/` 中 protocol/ 以外全部 23 個檔案，含 `base/methods.json`。C、T、B、A、S 共 74 條各列一次；conformance 的 V-01～05 與未編號入口另列同步處置，不混入 74 條統計。

## 1. 依據與刪減原則

最高依據是 [kernel-tree](../2026-09-29-kernel-tree.md) 的第五批方向，再對照全部 [使用者裁定](../2026-09-29-verdicts.md) 與 [兩條通則](../../spec/README.md)。kernel-tree 目前的「待定」在第七節，第六節是「照舊的」；本計畫不把那六個既有問題再算成新問題。

- daemon 管程序；kernel 是被 tick 推進的資料夾，負責自己成員的排程；agent 和 kernel 共用同一個 `aos-tick`。
- 不保留單一控制寫入者、帳本、SQLite、Proposal／checkpoint.commit、全樹一次准入交易。每個資料夾自己的 git 提交就是它的恢復基線，沒有跨 repo 原子交易。
- 資源 module 登記在 kernel 的任務註冊表；沒有裝的 module 不另做該層記帳或限制，但不會解除上層已施加的限制。LLM 與 CPU 等資源同樣往下分配；endpoint 池的 key 只留在該池代發服務。
- 同一份權限、同一個檔案或指令入口供人與獲授權 agent 使用；工具不另設行為禁令。root helper 的權限邊界、池 key 不可外流、既有危險處置 y/n 仍保留，不能藉「精簡」取消使用者明確裁定。
- 「刪除」是刪掉舊條款身分或重複制度，不是刪掉其中仍有效的使用者裁定；需保留的短句在去向欄點明。run 仍是軟性原則，不趁重寫決定任務中途新訊息歸屬。
- **不把帳本換皮成檔案**：去重只看該請求檔／已處理檔是否存在；先後用所屬 kernel 的序號；到期留一個必要時間欄；查詢讀狀態／摘要。不要重新要求每個請求都有 ledger、cursor、投影版本、reservation 收據、tombstone、outbox、全域索引六七份副本。必要的派出／unknown 證據仍要留，但只留足以辨識一次工作的資料。

proto5 的 kernel/ 與 daemon/ 兩組 README 及各節皆作為前例盤點。可沿用的是：daemon 定時或新單開 kernel tick、不讀家的內容、daemon 不重開同家一格且 tick 自己取鎖、通知只是提示、上層看摘要、正常路徑只處理有事成員。**不能照搬** `ledger.sqlite`、帳本 A/B/C/D 提交與出貨箱、CPU 常駐 worker 池、重啟保留孤兒 tick、未知工作反覆重排。前例以 [kernel/tick.md](../../../proto5/spec/kernel/tick.md)、[kernel/no-overlap.md](../../../proto5/spec/kernel/no-overlap.md)、[kernel/daemon-link.md](../../../proto5/spec/kernel/daemon-link.md)、[daemon/ticks.md](../../../proto5/spec/daemon/ticks.md)、[daemon/loop.md](../../../proto5/spec/daemon/loop.md) 最有用；proto6 第五批與重啟全殺裁定優先。

## 2. 新 spec 地圖

以下路徑相對 `proto6/spec/`；括號內「新增」是未來改寫工作，這次不建立。只新增兩個 md，合併掉兩個 md，移除一份舊 RPC 欄位表；篇數不膨脹，主要靠刪制度與縮短正文變小。

| 篇／檔案 | 管什麼 | 邊界與舊內容去向 |
|---|---|---|
| `README.md` | 兩條通則、平台、讀法、裁定優先序 | 移除「單一 writer 是本版預設」與 kernel 樹延後字樣；同機 kernel 樹不等於跨機分散式系統 |
| `terms.md`、`contracts.md` | 角色、身分／請求識別、共用結果及最少型別 | 不再替所有領域規定完整欄位表、資料庫 schema、四套狀態鏡像；詳細 JSON 留下輪 protocol |
| `daemon.md`（新增） | kernel tick 登記、定時／新單喚醒、程序啟停與重拉、清空程序、daemon 重啟／退役 | 承接 `base/lifecycle.md` 的程序面後刪舊檔；不讀 home 內容、不排任務、不分配資源 |
| `tick.md`（新增） | loop→inst→aos-tick、順序註冊表、group／needs、同家互斥、git 提交／還原與恢復 | 取代 C-05、A-501／502／506；A-503 只留 agent 完成證據到 agent 入口；不是 agent 專屬引擎 |
| `scheduling/README.md` | **kernel 樹入口與核心規則**：成員、登記鏈、摘要、權限設定、向下分配 | 不另加 kernel.md；本篇只有樹的共同骨架，機制往下連 |
| `scheduling/admission.md` | 各 kernel 的排序、到期、喚醒摘要、已裝資源 module 與下分額度 | 刪全域一次准入；CPU／memory／pids／LLM／磁碟／網路是同類 module，不做兩套外掛表 |
| `scheduling/llm.md` | LLM module、endpoint 池與每池代發、共享限制、429、unknown | 同篇分清 kernel 分配與池端實際送出的責任；不要求唯一全機池或新的常駐 LLM 排程總管 |
| `scheduling/runs.md`、`scheduling/operations.md` | 精簡工作生命週期、可選 run、unknown 處置、摘要查詢與 attention／aos-attend | run 預設不能變硬規定；清理只引用 storage；權限取代人／agent 兩套入口 |
| `base/identity-resources.md` | 一 agent 一 UID、可信登記、root helper、OS 資源限制如何落地 | 哪些 module 要裝由 kernel 決定；helper 只做固定特權步驟，不執行任意註冊任務 |
| `base/work.md`、`base/execution.md`、`base/README.md` | 普通工作材料、runner、可信結果、逾時取消、後代清空 | 不規定工具能做哪些事；不再內建控制端總帳本或資源總管 |
| `base/storage.md`、`base/transport.md` | 資料夾布局、ignored 收件區／追蹤區、檔案發布、簡單去重、保留與清理、投件授權 | git group 演算法只在 tick；root 安全只引用 helper；移除 `base/methods.json` 舊方法全集，protocol 下輪另定 |
| `agent/README.md`、`agent/configuration.md`、`agent/input.md`、`agent/memory.md`、`agent/tools.md` | agent 註冊任務、設定下一 tick 生效、內容／context、工具選擇及結果解讀、完成證據 | 刪 `agent/tick.md`；不重寫一套 claim／Proposal／恢復，也不以 agent 身分限制一般檔案與指令能力 |
| `conformance.md` | 新架構的局部與整合驗收入口 | 改測 git group、收件不中斷、kernel 階層分配、module 缺席、池與權限；不保留 SQL 測試 |

**縮減驗收建議，不是新產品要求：**現有非 protocol 共 141,511 bytes；改寫後以不超過原正文 65%（約 92 KB）為編輯目標，含新增兩篇與新增條款。達不到先找重複流程與已過時欄位，不靠刪故障保證或把整套帳本塞進新檔來達標；不把原文大量搬入附錄冒充變小。74 個舊 ID 的減少量與新條款數分開算，新增清單是待補內容，不要求每項另長一篇。

## 3. 逐條處置表

四種處置互斥：**保留**＝主要規則不變，只修引用；**改寫**＝核心責任／流程有變，移檔也算此類；**搬移**＝規則主要不變而更換正本位置；**刪除**＝撤掉獨立條款，必要短句併入已列正本。不是把「搬移且改寫」重複計數。

標記：**單**＝單一控制寫入者／受信控制端壟斷；**帳**＝帳本、Proposal、claim／cursor 投影等舊提交依賴；**SQL**＝明文 SQLite／DB；**全**＝全機統一准入／額度；**簡**＝兩條通則或重複內容可精簡；**註**＝被註冊式 tick／git group 取代；**模組**＝資源 module 選配影響。標記只是找改寫熱點，不表示 Linux 身分、同家互斥或 unknown 保證可刪。

### 3.1 共用 C、T（11 條）

| ID | 舊條款／來源 | 處置 | 去向 | 標記 | 理由與改寫要點 |
|---|---|---|---|---|---|
| C-01 | 基本型別與版本；`contracts.md` | 保留 | 原檔 | — | ID、版本、整數與經過時間仍適用；驗收的 generation/checkpoint 換成仍存在的欄位示例，不重新指定全套序列化。 |
| C-02 | Owner 與 run；`contracts.md` | 改寫 | `contracts.md`；登記細節引用 `base/identity-resources.md` | 單／帳／簡 | Owner 擴為 kernel／agent 的成員登記關係，run 資料降為採用該軟性預設時才需要；刪控制端配 generation 與不可變 bundle 指標制度，保留可信身分、下一 tick 換設定。 |
| C-03 | Job 與 attempt；`contracts.md` | 改寫 | 原檔 | 帳／全 | 只留工作／實際嘗試 ID、結果、unknown 與晚到結果不能覆蓋新嘗試；序號由所屬 kernel 管，不再是總帳本配發；普通檔案引用不強制經管理者 blob 庫。 |
| C-04 | 錯誤與 RPC 對應；`contracts.md` | 改寫 | 原檔 | 簡 | 留最小 Error、接件不等於完成、retryable 不授權 unknown 重做；RPC code／method 對照留待 protocol 下輪，不在本輪先設另一套 agent API。 |
| C-05 | Checkpoint proposal 與 fencing；`contracts.md` | 刪除 | `tick.md` 新 group／git 規則；工作證據引用 C-03 | 單／帳／SQL／全／簡／註 | 整套 Proposal、expected_revision、blob 導入、單 SQLite 交易與提交收據退出；不用檔案模擬同一控制交易。git 只提交本 repo，外部送出不受還原，接縫見 Q1～Q2。 |
| C-06 | 最小例子與保留；`contracts.md` | 刪除 | 保留政策併 `base/storage.md` B-404；簡單去重引用 B-503 | 帳／簡 | 舊 Job 大範例與另一套 tombstone／gone 正本沒有必要；保留 30 日、未結／unknown 不清的意思，只寫一次，不要求每個檔案再有摘要墓碑。 |
| T-01 | 來源與適用範圍；`terms.md` | 保留 | 原檔 | — | 繼續區分使用者方向、未裁預設與主編補；補明第五批優先，不能把本計畫的建議說成裁定。 |
| T-02 | 三層 owner；`terms.md` | 改寫 | 原檔，指向各責任篇 | 單／帳／簡 | 改成 daemon／kernel／agent／helper／每池代發責任，刪全機一個 writer；權限由設定授予，頂層 kernel 沒有另一種本質身分。 |
| T-03 | 四種工作識別與一次 RPC；`terms.md` | 改寫 | 原檔 | 帳／簡／註 | 只分辨穩定成員、請求、工作與一次實際嘗試；run 可選、RPC 非唯一入口，移除 Proposal 專用 generation；保留舊結果不能冒認新身分。 |
| T-04 | 控制狀態與觀測 phase 不混用；`terms.md` | 刪除 | 工作終局併 C-03／S-104；顯示引用 S-402 | 帳／簡 | 不再把 phase、run、job、attempt 四套狀態全集放名詞篇；保留「顯示不是成功證據、unknown 不自動重試」短句到各正本。 |
| T-05 | 一萬份本體與少量活動；`terms.md` | 改寫 | 原檔 | 全／簡 | 留負載目標、一 UID、冷本體無常駐程序；把准入交各 kernel 已裝 module，刪把 kernel 樹與父子一概延後的舊句，跨機仍不擴張。 |

### 3.2 基底 B（25 條）

| ID | 舊條款／來源 | 處置 | 去向 | 標記 | 理由與改寫要點 |
|---|---|---|---|---|---|
| B-000 | 責任與驗收；`base/README.md` | 刪除 | base/README.md 僅留導航 | 單／SQL／全 | 單一控制層總覽已失效，責任與驗收毋須各抄一次。 角色交給 terms、具體驗收各歸葉篇；不再保留「所有工作先經一個控制 writer」前提。 |
| B-101 | 固定工作材料；`base/work.md` | 改寫 | base/work.md | 帳／全 | 工作仍要能固定輸入，但不需控制者持有候選／blob 審批制度。 保留 argv、cwd、env、timeout、輸出上限與 job/attempt 識別；改為所屬 kernel 收件檔與固定工作材料，stdin 用一般檔案引用；快照只保證已接納材料，不凍結整個 workspace。 |
| B-102 | 特權與解析分界；`base/work.md` | 刪除 | 安全必要句併 base/identity-resources.md B-303 | 帳／簡 | 與 helper 的先查登記後降權重複，不再另外維護控制端 blob 快照通道。 B-303 留「root 不解析工作描述、不代開任意路徑；清憑證及 fd，降權後才讀 argv/cwd」；HOME/TMPDIR 預設屬 runner 環境，無須另起一份身份流程。 |
| B-103 | 結果格式；`base/work.md` | 改寫 | base/work.md | 簡 | 可見退出原因與 unknown 仍必要，三層結果包裝可縮成結果檔。 保留程序結果、退出碼、signal、截斷與有界輸出；刪 ExecResult→BlobRef→Outcome 的重複包裝，結果以 attempt ID 定址；程序 exit 0 不等於產品任務成功。 |
| B-201 | 啟動與狀態交接；`base/execution.md` | 改寫 | base/execution.md | 帳／SQL／全 | daemon 管程序、kernel 派工，不再以 DB 狀態機串接兩者。 保留固定 attempt ID、helper 安置資源／降權後啟動、啟動失敗清空；以最少啟動資料及結果檔支撐恢復，不重建 reserved/starting/running 交易帳本；不確定窗口統一 unknown、不自動重做。 |
| B-202 | 程序樹與完成；`base/execution.md` | 改寫 | base/execution.md | 帳 | 後代清空才算程序結束的保證可沿用，計量改交資源 module。 daemon／執行器保存安全程序識別並確認全部後代停止後才回結果與釋放名額；cgroup 結構改為 kernel 子樹；刪「歷史計量先存控制帳本」。 |
| B-203 | 取消與逾時競態；`base/execution.md` | 改寫 | base/execution.md | 帳 | 取消和成功仍須有唯一結果，但不需要全域交易先後。 保留 monotonic 逾時、先 TERM 再清理、未清空不算取消成功；由負責該工作的執行器產生單一結果檔，kernel 下格收結果；跨程序的取消／完成先後以明確持久結果規則裁定，不聲稱撤銷外部效果。 |
| B-204 | OOM 與啟動資源耗盡；`base/execution.md` | 改寫 | base/execution.md | 模組 | 失敗分類有用，但不存在每個 kernel 都必裝所有 cgroup 資源限制的前提。 有安裝記憶體／pids module 才讀對應證據；保留 errno、不用 SIGKILL 猜 OOM、控制程序不困在被管理成員的額度內；對應 module 未啟用不偽造計量。 |
| B-301 | 權限與額度歸屬；`base/identity-resources.md` | 改寫 | base/identity-resources.md | 全／簡 | agent 與工具相同 UID 的方向保留，額度改沿 kernel 樹而非單層全局域。 保留一 agent 一 UID、工具沿用同身份；資源限制由已裝 module 沿父子域分配；刪 proto5 bwrap 遷移敘事，不寫死「控制角色天生有特權」。 |
| B-302 | 部署與登記契約；`base/identity-resources.md` | 改寫 | base/identity-resources.md | 單／帳／全 | 管理者唯寫、控制層唯讀的固定角色與全局必備 profile 不符設定式權限。 只保留可信成員登記、身份與已配置能力驗證、attempt 身份不中途切換；改登記鏈與權限設定引用 kernel 篇；不強迫未裝的 quota／資源 module probe，刪 generation/checkpoint 對比。 |
| B-303 | 先限制、再降權、再工作；`base/identity-resources.md` | 改寫 | base/identity-resources.md | 單／帳／SQL／全／簡 | 極小 helper 必須保留，但「只信唯一 daemon UID」及全部資源必填會阻擋 kernel 樹。 helper 只查可信登記→在授權子樹建資源框→切帳號→exec 固定 runner；呼叫權限依 kernel-tree 待定題，不先替使用者選代開或直呼；刪工具一律不能碰設定的特例，遵一般檔案／指令授權；資源數值交已登記 module。 |
| B-304 | 容量與可寫路徑；`base/identity-resources.md` | 改寫 | base/identity-resources.md | 帳／全／註 | 磁碟只記帳且可選，可刪大段全局容量政策與 checkpoint 專屬例外。 磁碟作可選 module，只報其確能計量的落點，不宣稱硬邊界；保留共寫 workspace 由工具協調、磁碟與 tmpfs 歸屬；git 寫入失敗統一引用 B-404，不再停整個全局准入或寫帳本。 |
| B-401 | 權威與存放位置；`base/storage.md` | 改寫 | base/storage.md | 單／帳／SQL／全／簡／註 | 每個資料夾就是狀態，管理者 blob 庫＋pointer＋唯讀導出是應整套拿掉的舊前提。 每 agent/kernel 一個 git repo，追蹤區為已提交狀態、ignored 收件區收外部投件；以請求 ID 檔名、最少序號／到期欄位表達需要；無 DB、pointer、第二份 ready 投影及整份帳本視圖。 |
| B-402 | 發布與崩潰耐受；`base/storage.md` | 改寫 | base/storage.md | 單／帳／SQL／註 | 檔案完整發布可保留，DB/outbox 雙寫及巡檢交易整套刪去。 收件／結果以同檔案系統 temp→rename 完整發布；需要 durable 確認時保留檔案與目錄同步；group 的提交／回滾引用 tick 篇；不承諾跨資料夾 git 交易與外部副作用原子性。 |
| B-403 | checkpoint 提案交易；`base/storage.md` | 刪除 | 取代者 tick.md 的 group/git 條款 | 單／帳／註 | Proposal、可信 blob 導入及提案收據專為舊帳本提交模型而設。 整條刪除，不把提案 JSON、收據、revision、checkpoint pointer 改成同名檔案；容量與失敗只保留一般檔案規則。 |
| B-404 | 滿碟、保留與回收；`base/storage.md` | 改寫 | base/storage.md | 帳／SQL／全／簡／註 | aos-clean 與 30 日保留可沿用，控制交易取候選與 post 掛勾應刪。 aos-clean 是註冊任務，也可有權限者直接跑；只清無引用且已終局／消費的過期內容，預設封存、有批次上限；git commit 失敗不宣稱成功、不開下一格覆寫；刪控制帳本候選交易及另立去重墓碑體系。 保留結果保存不完整必須標示、缺失 bytes 不因 resume 長回來、不自動重跑找結果的 A-303 必要邊界；滿碟仍保留舊 commit 與可行的程序收尾。 |
| B-501 | 認證入口與 envelope；`base/transport.md` | 改寫 | base/transport.md | 單／帳／簡 | 正式投件不必全經單一 RPC gateway，人與 agent 共用受授權的普通入口。 保留不能相信 payload 身份、限長／純資料與完整發布；允許一般權限下向既定 ignored 收件區投檔；helper 的強身份驗證仍在 B-303；刪 claim 專用 checkpoint 接口，JSON-RPC 細節留 protocol 後續。 |
| B-502 | 最小操作集合；`base/transport.md` | 刪除 | base/methods.json 隨條款移除；可用語意歸 scheduling/operations.md | 單／帳／簡／註 | 方法全集把已廢棄 checkpoint.commit 與多個專用入口鎖成產品規定，且協議之後另處理。 刪此條及 methods.json 正本身份；需要的查詢、取消、暫停語意沿用 operations，不於本輪另定同義 RPC；result.ack 延後占位也刪。 |
| B-503 | 去重與三種確認；`base/transport.md` | 改寫 | base/transport.md | 單／帳／註 | 穩定 ID 防重復與「收件不等於完成」要留，不需四元鍵交易／三份確認紀錄。 請求 ID 在所屬目標的收件／已接納區定址；檔案還在即不重收，同 ID 不同內容報衝突；tick commit 表示已消費，結果檔表示完成，無獨立 ACK 資料表／tombstone 帳本；保留期後去重邊界見待決題。 |
| B-504 | 通知、重放與遺失；`base/transport.md` | 改寫 | daemon.md | 單／帳／SQL／全 | 通知可能遺失的保證仍要留，但 DB 巡檢與喚醒責任已換層，故算改寫。daemon 只依登記、時間與新檔通知開 tick，不讀正文；kernel 自行補查自身收件，重複通知不併發同家，不新增全域 outbox／游標帳本。 |
| B-505 | Blob 導入、讀出與對話輸出；`base/transport.md` | 刪除 | 檔案權限併 B-501；輸出可見性留 agent/input.md | 帳／簡／註 | 管理者持 blob、工具須經 adapter 的兩套檔案入口失去必要性。 刪 import_blob/export_blob 全套及文字必先換 BlobRef 的路徑；有權限就讀寫檔案，保留 root 不代開任意路徑與僅顯示已提交結果，不再複製一個匯入服務。 |
| B-601 | 按需執行；`base/lifecycle.md` | 搬移 | daemon.md | 全／註 | 登記與資料夾長存，短命 tick 與冷 agent 不空轉照舊；daemon 只負責實際啟動與程序生死，何時准許成員工作由所屬 kernel 決定，引用通用 tick 的先送後收規則。 |
| B-602 | claim 與單寫者；`base/lifecycle.md` | 改寫 | tick.md | 單／帳／全／簡／註 | 所需只是一資料夾一格 tick，claim/generation/revision/提案交易全可省。 每資料夾獨占鎖；舊程序全清且鎖可取才開下一格；無 global writer、claim 表、lease、proposal fence；git group 提交／還原由共用 tick 管，其他工具的寫入照一般權限與追蹤範圍，不另分工具身份。 |
| B-603 | 控制程序重啟；`base/lifecycle.md` | 改寫 | daemon.md | 單／帳／全／註 | daemon／VM 重啟清空在途程序；由執行器／所屬 kernel 讀最少結果證據，缺可信結果標 unknown、不自動重做。各家下格還原未 commit 變動、保留已 commit 組，git 恢復引用 tick.md；daemon 不讀家內狀態，不恢復總帳本或 Proposal 收據。 |
| B-604 | 停機與退役；`base/lifecycle.md` | 搬移 | daemon.md | 單／帳／全 | 停機與程序排空歸 daemon，停用成員只影響所屬子樹。 保留停止新啟動、等候可設定寬限、未清空報錯、UID/home 不自動回收；停用與退役由授權登記變更及所屬 kernel 處理；刪 claim／generation／控制 writer 前提。 |

### 3.3 Agent A（19 條）

| ID | 舊條款／來源 | 處置 | 去向 | 標記 | 理由與改寫要點 |
|---|---|---|---|---|---|
| A-101 | 設定資料與責任；`agent/configuration.md` | 改寫 | 原檔 | 單／帳／簡 | 設定就是可依權限修改的檔案；刪控制端唯一持有、tick 只讀、強制不可變 bundle／BlobRef 的制度，只留身分引用、模型／工具／context／cwd 所需設定和載入驗證，Linux 身分授權交登記與權限篇。 |
| A-102 | 設定版本引用與更新；`agent/configuration.md` | 改寫 | 原檔 | 單／帳／簡 | 保留下一 tick 開始生效、tick 中固定、已送工作沿用派出設定；用該次採用的檔案版本或必要快照表達，刪 claim 交易、run 強制換版流水帳與專用發布機制，無效設定沿用上次有效值並寫待處理檔。 本格採用版本與必要換版資訊仍可查，不強制另維護一份 run 換版帳。 |
| A-103 | 人格與權限分界；`agent/configuration.md` | 刪除 | 由 spec/README 通則及 `base/identity-resources.md` 共通身分規則承接 | 簡 | prompt 不授權、cwd 不是存取邊界、工具沿用身分都可由既有共通規則說一次，無需 agent 再設一條。 |
| A-201 | 收件格式與確認；`agent/input.md` | 改寫 | 原檔 | 單／帳／簡 | 改成有權限即可投 `.gitignore` 收件區，請求 ID 作檔名與必要檔案去重，收件／消費分開；刪 agent.submit 專屬強制入口、帳本登記收件與 ready 交易、孤立 blob 制度，保留拒收錯誤及不把內容自稱身分當認證，實際發送者歸因按 §6.1 一般投遞權限處理，不增加 agent gateway。 |
| A-202 | 普通訊息的輪次邊界；`agent/input.md` | 刪除 | 結果配對併 A-403；消費原子性歸 `tick.md`；run 軟性說明只留 `scheduling/runs.md` | 單／帳／簡／註 | 沒有獨立於軟性 run 規則的新契約；刪此條與 proposal 消費 cursor，結果不冒充新訊息、已收不等於已處理各在唯一所屬條文簡述。 |
| A-203 | 暫停、取消與輸出；`agent/input.md` | 改寫 | 原檔 | 單／帳／簡／註 | 縮成正式輸出檔及 progress／final 的區別，正式可見性跟 group commit；暫停／取消只連共通操作，不保留 agent 專用控制入口或 Proposal／final_ref 提交套件，串流片段不等於已完成仍保留。 |
| A-301 | 持久內容與權威引用；`agent/memory.md` | 改寫 | 原檔 | 單／帳／SQL／簡／註 | 保留 history／notes／context 不同用途、來源可追查、缺資料不冒充成功；直接用資料夾檔案與 git commit／還原，刪 SQLite checkpoint pointer、帳本歷史尾端、強制 history_append 提案及「工具不能寫認可歷史」角色限制。 |
| A-302 | context 選擇與來源；`agent/memory.md` | 改寫 | 原檔 | 單／帳／全／簡 | 保留模型上限、必要材料、tool call 配對、引用與有界超限處理；刪 context 端重述各 scope reservation／固定 run 預算欄位，LLM 與摘要請求交所屬 kernel 已裝的 LLM module，先送後收，未裝 module 不由此條私設資源管理。 |
| A-303 | 容量不足與保存期限；`agent/memory.md` | 改寫 | 原檔 | 單／帳／全／簡 | 本篇只留有標記的工具結果預覽及不把截斷內容當完整資料；磁碟可選記帳、收件容量錯誤、結果保存失敗與清理全回儲存篇，刪控制庫關寫／持久登記後 ack 等帳本步驟。 |
| A-401 | 能力清單與參數；`agent/tools.md` | 改寫 | 原檔 | 單／帳／簡 | 保留工具描述、schema 檢查與模型 call 配對這個 adapter 真正需要的部分；工具／argv 是設定檔，刪不可變 exec_ref／可信 claim 補 owner 制度及為區隔工具而限定的入口，保留格式錯誤不派工和有限修補，詳細 JSON 字段之後再跟 protocol 對齊。 |
| A-402 | 委託執行邊界；`agent/tools.md` | 刪除 | spec/README 兩通則、`base/identity-resources.md`，LLM key 規則只在 `scheduling/llm.md` | 全／簡 | 工具就是使用相同帳號與權限的程式，不需再立委託專章；刪工具再次呼叫工具／LLM 的特製通道描述，身分不可由參數冒領與父層資源框約束仍由共通層保證。 |
| A-403 | 結果封套與解讀；`agent/tools.md` | 改寫 | 原檔 | 單／帳／簡／註 | 保留 call／工作結果配對、exit 0 與語意有效不同、完整結果與預覽不同、不得自動重跑；改讀收件結果檔，跟消費 group 一起 commit，刪中央控制層先登記結果的前提及獨立重送消費制度，必要欄位即可不保留多重權威封套。 |
| A-404 | LLM 與未知結果；`agent/tools.md` | 刪除 | 共通 LLM 行為由 `scheduling/llm.md` 承接；unknown 處置由 `scheduling/operations.md` 承接 | 單／帳／簡 | 此條把 LLM 代發責任與 unknown 人工恢復重寫一次；移除整條、README 連共通規則，保留重啟全殺／無結果 unknown／不自動重做的使用者裁定但只在恢復與操作篇定義一次。 |
| A-501 | 每次推進的責任；`agent/tick.md` | 刪除 | 由新 `tick.md` 與 `agent/README.md` 取代 | 單／帳／簡／註 | 可信 claim＋帳本唯讀視圖→C-05 Proposal 的整個模型已廢；改由通用 aos-tick 依註冊順序直接改資料夾與執行 group，agent 簡述先送請求／後續 tick 收結果，不設「只能提案」入口。 |
| A-502 | Checkpoint 與提交次序；`agent/tick.md` | 刪除 | 由新 `tick.md` git 提交／恢復規則取代；必要 agent 狀態簡述在 `agent/README.md`／A-401 | 單／帳／註 | checkpoint 與帳本互相補副本的設計已無對象；保留真正用到的語意狀態（如無效回覆計數）為普通檔案，刪 checkpoint schema、B-403 匯入、C-05 增量、權威 cursor 與歷史尾端互斥規則。 |
| A-503 | Phase 與完成契約；`agent/tick.md` | 改寫 | `agent/README.md` | 單／帳／簡／註 | 六種 phase 與 proposal finish 檢核不必自成契約；縮為 agent 任務必要收尾條件：不將未收結果／unknown 宣稱成功、final 隨本地 group commit、等待不忙轉，run 邊界仍是軟性預設，不把舊整套狀態機搬過來。 |
| A-504 | 冷本體與可觀測性；`agent/tick.md` | 搬移 | `agent/README.md` | 註 | agent 資料夾持久、按需 tick、沒有每 agent 常駐 worker 的使用者方向照舊；只更換喚醒來源的連結指向 daemon／kernel，保留 10,000 個閒置 agent 不生成對等程序的驗收。 |
| A-505 | 錯誤查詢與診斷；`agent/tick.md` | 刪除 | `scheduling/operations.md` 共通檔案查詢與待處理規則 | 單／帳／簡 | generation／checkpoint revision／拒絕 proposal 的查詢已過時；一般查詢讀檔與錯誤原因保留在操作篇一處，不為 agent 再訂一套查詢欄位。 |
| A-506 | tick 前後掛勾；`agent/tick.md` | 刪除 | 由新 `tick.md` 註冊表／group／needs 取代 | 單／帳／簡／註 | 第三批已明示取代 pre/post；刪兩種掛勾、when／on_failure／claim 時間分攤／專用 stdin／管理者限定寫死規則，aos-clean 與自訂程式都是註冊任務，root 固定動作仍在 helper。 |

### 3.4 排程 S（19 條）

| ID | 舊條款／來源 | 處置 | 去向 | 標記 | 理由與改寫要點 |
|---|---|---|---|---|---|
| S-101 | 接件與輪次；`scheduling/runs.md` | 改寫 | scheduling/runs.md | 帳／簡／註 | 單筆輸入一 run／FIFO／新訊息排下一 run 只留為可替換例子，不能當 kernel 必須遵守的產品模型；去掉控制交易接件與「維護 tick 禁用 LLM／工具、必須另投可信輸入」的雙入口，任務按權限送請求、下格收結果；設定換版引用 A-102，不再重述。 |
| S-102 | Run 合法轉移；`scheduling/runs.md` | 改寫 | scheduling/runs.md | 帳／簡 | 縮成可選 run 分組的 pause／cancel／resume 效果，狀態寫本地檔並隨 group commit；取消要求不等於程序已停、unknown 不因 resume 重做、修復後 resume 仍是可選出口；刪逐 RPC 欄位與重複去重／版本／階段定義，不把 run 硬化。 |
| S-103 | 同 agent 一個狀態寫入者；`scheduling/runs.md` | 刪除 | 互斥只引用 `tick.md` 的 B-602；程序清空引用 `daemon.md` | 單／帳／註 | 這是 B-602 互斥條款的重複；刪 claim／ready 投影的二次規範，只由共用程序生命週期保證「同資料夾一格 tick，舊程序清乾淨才下一格」，不能誤刪該使用者要求。 |
| S-104 | Job、attempt 與 retry；`scheduling/runs.md` | 改寫 | scheduling/runs.md | 單／帳 | 保留每次嘗試獨立 ID、unknown 不自動重做、舊結果不蓋新嘗試、有限明確安全重試；用請求／結果與最小狀態檔表示，刪帳本事件史和繁複 reserved／starting／selected 投影，程序事實仍來自 daemon／runner；人工重試要明示重複副作用風險及先清空舊程序。 |
| S-201 | ready／due 的權威與讀取；`scheduling/admission.md` | 改寫 | scheduling/admission.md | 單／帳／SQL／註 | 刪 SQLite 索引、pending_seq／served_seq 投影、claim 提案交易與強制當前 run 門檻；每 kernel 只保存成員所需 ready／due 摘要，來源是收件檔與狀態檔，由自己的 tick 推進；冷成員不反覆空跑，上層不讀其內容。 |
| S-202 | 通知與補查；`scheduling/admission.md` | 改寫 | scheduling/admission.md | 帳／簡 | 通知可丟，收件檔還在就能補查；去掉「非正式入口直寫不接納」及專門匯入帳／游標架構，照相同格式和檔案權限直接投件；每 kernel 分批查自己的登記與收件，daemon 只掌管程序及喚醒，不讀家內內容；64／60 秒可留範例，不作新硬門檻。 |
| S-203 | 全局與每agent名額；`scheduling/admission.md` | 改寫 | scheduling/admission.md | 單／帳／全／註 | 刪所有部署必填全域上限、單帳本一次占齊各種票；改為父層分配、子層在所得範圍內分配，只有註冊的資源 module 記帳／限制；尚未清掉的程序不能憑 unknown 釋放實際占用；CPU 等硬限制由已啟用 module 配合 cgroup，磁碟仍只記帳，未裝 module 不自行加限制。 |
| S-204 | 可預測的簡單公平；`scheduling/admission.md` | 改寫 | scheduling/admission.md | 帳／全 | 保留使用者裁定的序號排序，配號改本 kernel 狀態檔或檔名、重啟不倒退，不要求跨樹全域序號；0／1 priority、60 秒老化縮成可選本地政策，不要求所有 kernel 同政策；額度不足略過、調低額度不自動當取消，父層限制仍有效。 |
| S-301 | 請求與 quota scope；`scheduling/llm.md` | 改寫 | scheduling/llm.md | 單／帳／全／簡 | 每 endpoint 池一個代發服務保管 key，頂層或下層皆可擁有池；kernel 的 LLM module 分配成員用量與機會，池服務處理真正共享的 provider 限流；agent／工具同樣投件，去掉唯一中央控制寫入者帳號假設與專用 agent 通道；payload 詳細 schema 留協議後續，key 不進家、不隨 job 傳。 |
| S-302 | 預留與結算；`scheduling/llm.md` | 改寫 | scheduling/llm.md | 單／帳／全 | 刪跨 scope＋run 一次交易、Reservation 狀態機、30 秒租約及成本帳／速率帳雙帳；kernel 保留必要分配摘要，池服務以請求 ID、送出狀態與結果／usage 檔核對一次，缺結果保守 unknown；只保留限流實際需要的用量與窗口，不建檔案版總帳，共享限制責任按 §6.1，不能保留跨 repo 同時占票保證。 |
| S-303 | 限流與可重試失敗；`scheduling/llm.md` | 保留 | scheduling/llm.md | — | 有限 429 重試、Retry-After／退避、獨立 scope 不連坐，以及不明 5xx／逾時不擅自重送，均和新架構相容；維持這些已獲授權的行為，僅調整舊 S-306 參照及「工具預設」重複文字，不引入新 retry 層。 |
| S-304 | 取消與不確定性；`scheduling/llm.md` | 改寫 | scheduling/llm.md | 帳／全 | 本機 HTTP 已停不代表遠端沒執行、缺結果標 unknown 不重送仍保留；必要的不確定用量留在所屬池／module 的最小狀態，去掉所有部署必填 uncertain_hold 與 profile 強保證的硬規定，估算釋放只作明示可選政策；完整結果才可成功併入此條。 |
| S-305 | 串流與 final；`scheduling/llm.md` | 刪除 | 完整結果一句併 S-304；首版 stream=false 簡註 S-301 | 簡 | 串流產品功能已延後，不留專條與片段狀態設計；不把部分內容當成功的必要邊界用一句保留即可。 |
| S-306 | 有限的 run 預算；`scheduling/llm.md` | 刪除 | 可選額度歸 S-203 的資源 module；已啟用預算不足出口引用 S-102 | 帳／全／簡 | 刪強制 run 四種預算、五個帳本計數及和 scope 綁定的原子 hold，避免把軟性 run 變資源硬核心；若 kernel 註冊對應 module 才談其額度，工具與 agent 調設定同按權限；保留使用者裁定的「不足時可取消、resume 加額可選」效果，不另做強制 run 帳本。 |
| S-401 | 人工解決 unknown；`scheduling/operations.md` | 改寫 | scheduling/operations.md | 帳／簡 | 保留先清空本機程序、明示接受重複副作用、舊 unknown 證據不偽改成功；刪 RPC 字段與 resolve 原子交易細節，經同一有權限的指令／檔案入口處置，由所屬 kernel 落最小檔案狀態；人與 agent 共用權限與確認邊界，不能以通則略過危險確認。 |
| S-402 | 查詢回應與拒絕理由；`scheduling/operations.md` | 改寫 | scheduling/operations.md | 單／帳／全 | 查詢直接讀允許的本地狀態／摘要，不為查詢開 agent、上層查詢只讀下層摘要；保留排隊、等待資源、等結果、unknown、暫停與部署不可用能辨別，刪長列 phase 推導與唯一中央 RPC schema；module 未安裝不算部署錯誤，已啟用卻無法滿足要求才報錯，結果保留引用儲存。 |
| S-403 | 最小量測與過載；`scheduling/operations.md` | 刪除 | 必要容量不足拒收／取消可行併 S-203 與 base/storage.md；其餘留實作計畫 | 帳／全 | 帳本提交耗時及一整組必備全域 metrics 已無對象，不為留住它另建彙總系統；過載與滿碟不得靜默丟件的必要邊界併已有排程／儲存條款，取消入口保持可用；具體量測清單與窗口留實作驗證。 |
| S-404 | 留存；`scheduling/operations.md` | 刪除 | base/storage.md 的 B-404 與共用保留邊界 | 帳／註 | 與 B-404／C-06 重複，刪 checkpoint／tombstone 套裝要求；30 天、尚被引用／未結不動與 `aos-clean` 都只在儲存篇定義，清理當註冊任務或直接手動跑；proto5 遷移段已移 plan，毋須再次新增。 |
| S-405 | 待處理資料夾；`scheduling/operations.md` | 改寫 | scheduling/operations.md | 單／帳／簡／註 | 保留使用者指定資料夾與 aos-attend、危險動作問 y/n、無終端不做危險動作；去掉「只有管理者能用、agent/tool 一律禁止」和「帳本通知副本、唯 RPC 可處置」，改按實際檔案／指令權限使用同一工具；事項是來源 kernel 狀態的摘要，刪通知不等於解除問題，採來源 ID 避免跨 kernel 撞名，不因此新建中央通知帳本。 |

**74 條處置統計：保留 3、改寫 47、搬移 3、刪除 21。**刪除約 28%；其餘多數只保留必要意思並大幅縮短，不保證舊段長度。

| 類別 | 保留 | 改寫 | 搬移 | 刪除 | 合計 |
|---|---:|---:|---:|---:|---:|
| C | 1 | 3 | 0 | 2 | 6 |
| T | 1 | 3 | 0 | 1 | 5 |
| B | 0 | 18 | 2 | 5 | 25 |
| A | 0 | 10 | 1 | 8 | 19 |
| S | 1 | 13 | 0 | 5 | 19 |

### 3.5 未列入 74 條統計、但必須同步處置的檔案

- `README.md`、`base/README.md`、`agent/README.md`、`scheduling/README.md`：照新地圖改責任與導航；刪單一 writer、只准提案、kernel 樹延後等舊前提。B-000 已在表內，不再算一次。
- `base/methods.json`：12 筆均已盤點（agent.submit/get、run.get/pause/resume/resolve/cancel/outputs、attempt.get/cancel、checkpoint.commit、result.ack）；整檔隨 B-502 撤除。checkpoint.commit 及 result.ack 延後占位不保留；其他動作的必要意思留在領域篇，不在本輪改造 RPC 欄位表。
- `conformance.md`：V-01、V-05 保留編輯／驗收原則，改正本與連結；V-02 改成 mock→Linux 兩身分與已裝 module→萬級冷資料三層驗證；V-03 整體改寫，刪帳本／提案／SQL／全域准入故障窗口，改測 group 成敗、收件搬移、跨家派送、daemon 全殺、已 commit 保留、無結果 unknown；V-04 保留萬級穩態與冷啟動分開量測，去掉 SQL 熱路徑要求，改測不每格掃全樹、讀所有 history 或替所有冷 agent 開程序，分層喚醒另量端到端延遲。V-02 舊「分散式 kernel 延後」只可指跨機，不能排除這次已裁定的同機 kernel 樹。
- `base/lifecycle.md`、`agent/tick.md`：依逐條表分拆／合併後刪掉，不留另一份有效規則或全文轉址副本。
- `protocol/`：本次不讀改其條款、不更新 schema／examples、不以它限制新主規格；主入口註明它仍反映舊架構、下輪處理。舊 protocol 指向已撤條款的引用列為下輪清單，不讓這輪被迫把舊制度保留下來。

## 4. 必須補的內容（N 是本計畫追蹤號，不是預先決定的新 spec ID）

以下每項只補一個必要缺口，能併入重寫條款就併，不要求另開 16 條長文；未裁事項只留待定引用。

| 項 | 位置 | 一句要點與依據 |
|---|---|---|
| N-01 | `scheduling/README.md` | kernel 和 agent 同是資料夾＋aos-tick＋註冊表，kernel 只管直接成員、下層 kernel 在父層是一件工作；依 kernel-tree §一、二、四。 |
| N-02 | `scheduling/README.md` → `base/identity-resources.md` | 成員登記能表達父 kernel、成員身分與 home 並向上追鏈，防止冒名使用別隊資源；這是應補格式，授權者／下層 UID／helper 路徑仍依既有 §七 1～3 待裁。 |
| N-03 | `scheduling/admission.md` | 父層分資源給子層、子層只能在所分範圍再分，cgroup 層級對上 kernel／成員層級；依 §二，不加全樹原子占票。 |
| N-04 | `scheduling/admission.md`、`tick.md` | CPU、memory、pids、LLM、磁碟與網路 module 均以同一註冊表項目啟用，沒裝就不在該層另記／另限，已生效的父層限制照舊；依第五批與 §二。 |
| N-05 | `base/identity-resources.md` | kernel 權限是登記／設定所授予，頂層不是特殊程式種類，root 步驟固定在 helper、註冊任務永不因此取得 root；依 §三與第三批。 |
| N-06 | `scheduling/llm.md` | LLM module 管成員份額與排程，每個 endpoint 池自己的代發持 key，各 kernel 都可有池，上層不取代池的 provider 限流責任；依 §二、三與裁定 9。 |
| N-07 | `daemon.md` | daemon 按 kernel 登記、定時或新單開 tick，只看程序資料與喚醒信號、不讀家內正文，父 kernel 決定成員可跑條件而 daemon 實際啟動；依 §一與 proto5 daemon/ticks 前例，具體 helper／層級喚醒路徑沿既有待定。 |
| N-08 | `tick.md` | 最小註冊表草案只列 `id`、普通程式／參數、任務類別與順序、可選 `group`／`needs`，按系統性→kernel 或 agent→自訂順序跑，不保留 pre/post 第二套表；依第三批，欄位拼法只是本次建議。 |
| N-09 | `tick.md` | group 全成功才提交、任一失敗整組不生效，needs 只在前置成功時執行；依第三批與第五批，組連續／缺依賴／循環／組失敗後 needs 的最小規則列下方工程預設。 |
| N-10 | `tick.md` → `base/storage.md` | 每家一個 git repo，成功組 commit、失敗組還原至最近 commit，前面已成功組不撤回，ignored 與外部不可逆後果不算；依 §五。 |
| N-11 | `base/storage.md`、`tick.md` | 外部訊息與工具／LLM 結果進 ignored 收件區，消費內容進追蹤區並與組一同生效；依第五批，物理搬移保原件接縫需 Q1。 |
| N-12 | `daemon.md`、`tick.md` | daemon／VM 重啟先清舊程序，下一格還原未 commit 組，已存結果與已 commit 狀態保留，在途缺結果 unknown 且不自動重做；依 §五、六。 |
| N-13 | `base/storage.md`、`base/transport.md` | 去重靠請求 ID 檔名、先後靠本 kernel 序號、到期靠必要時間欄、查詢靠檔案／摘要，不加帳本、SQLite 或平行狀態副本；依第五批確認。 |
| N-14 | `tick.md`、`agent/README.md` | 註冊任務要 LLM／工具就先送請求、下一格收結果，tick 不同步等遠端；依第三批，外部派出與 git 提交邊界需 Q2。 |
| N-15 | `base/transport.md` | 跨 kernel 投件沿一般權限、相同收件格式、結果識別與喚醒規則，不為 agent 另做一套入口；依通則，是否直投或轉送仍引用 §七第 5 題，這次不拍板。 |
| N-16 | `scheduling/operations.md` | 下層只提供上層需要的摘要，所有待人處理事項仍能進指定 attention_dir 並帶來源識別，aos-attend 使用同一授權入口且危險動作照舊問 y/n；依 §二、第二批及通則。 |

## 5. 六份平行工作包

這是未來改寫的分工，**這次只產計畫**。檔案歸屬以完整清單為準；沒有列到的檔不得順手改。各包都自行修自己檔案的引用與驗收，不能要求「整合者最後再替所有檔修一次」。protocol 不屬任何包。

| 包 | 獨占檔案（相對 proto6/spec/） | 舊條款與新增內容 | 完成界線 |
|---|---|---|---|
| P1 總入口與共用契約 | `README.md`、`terms.md`、`contracts.md`、`conformance.md` | C-01～06、T-01～05、V-01～05；新地圖、標記、統計與整合驗收 | 刪 Proposal 與重複狀態全集；只修改自己四檔，讀其他包輸出做一致性核驗 |
| P2 kernel 樹與資源 | `scheduling/README.md`、`scheduling/runs.md`、`scheduling/admission.md`、`scheduling/llm.md`、`scheduling/operations.md` | S-101～104、S-201～204、S-301～306、S-401～405；N-01～04、06、16 | 樹、module、LLM 池、軟性 run、操作各有單一正本，不把全域帳本換名 |
| P3 daemon 與通用 tick | 新 `daemon.md`、新 `tick.md`、`base/lifecycle.md`（移完刪） | B-601～604；接收 B-504 核心；N-07～12、14 | 程序面與 group/git 面分開；不改 agent/tick.md，也不改 transport.md |
| P4 工作執行與身分 | `base/README.md`、`base/work.md`、`base/execution.md`、`base/identity-resources.md` | B-000、B-101～103、B-201～204、B-301～304；N-02、05 的身分落地 | 保留 helper 極小與可靠程序收尾；資源政策引用 P2，無權代定原 §七問題 |
| P5 檔案、投件與清理 | `base/storage.md`、`base/transport.md`、`base/methods.json`（刪） | B-401～404、B-501～505；吸收 C-06 留存短句；N-11、13、15 | 刪中央 blob adapter／RPC 全集；B-504 的源段由本包移除，新 daemon 正文只由 P3 寫 |
| P6 agent 任務 | `agent/README.md`、`agent/configuration.md`、`agent/input.md`、`agent/memory.md`、`agent/tools.md`、`agent/tick.md`（刪） | A-101～103、A-201～203、A-301～303、A-401～404、A-501～506；N-14 的 agent 預設任務 | 只留 agent 內容與選擇，提交／互斥／恢復引用 P3；必要狀態是普通檔案 |

**跨包搬移的接法：**來源檔的主人刪舊段，目的檔的主人照本表寫新正本；傳遞條文要點即可，不互改檔。B-504 為 P5→P3，C-06 為 P1→P5，C-05 廢制由 P1 刪、P3 寫替代機制；A-501／502／506 同理由 P6 刪、P3 寫通用規則。B-102→B-303、A-503／504→agent/README 都在單包內。P1 只查核其他包，需修正時交回該檔主人。

**平行前先共用這份責任表即可**，不用先寫完整協議。P3／P5／P6 可先刪過時制度並寫已裁部分；Q1～Q4 未裁時把相應段落明標「待裁」，不得自選方案聲稱 spec 已閉合。其餘包可獨立前進。收線檢查：74 個舊 ID 均有對應、無兩份正本、檔案所有權無重疊、主規格本地引用有效、剩餘 SQLite／帳本／Proposal 等字樣只出現在撤除說明、所有故障驗收指向新責任。這次未執行改寫，故沒有 build／ctest，也沒有聲稱運行時保證已驗證。

## 6. 原待定以外，真正需要使用者決定的四題

以下都是本次發現的規則衝突，各選項目前都只是建議；不重問 kernel-tree §七那六題。

| 題 | 衝突與影響 | 建議 | 另一條路及代價 |
|---|---|---|---|
| Q1 消費收件的「搬」，能否延後刪原件？ | §五要求 ignored 收件搬進追蹤區，又要求未 commit 組全還原；若先移走唯一原件再崩潰，還原會把訊息／結果一起弄丟。 | **允許邏輯搬移**：先保留原件，組 commit 後才清來源；已 commit 的同 ID 檔就是已消費證據，恢復多留一份不重吃，不加收件帳本。 | 堅持先搬掉唯一原件，就需要另一份可靠恢復證據；不能只承諾正常失敗時搬回，因為突然崩潰做不到。 |
| Q2 發出工具／LLM 前，是否先提交最小請求？ | group 中已對外投件，後面失敗把本地紀錄還原，下一格可能再送；這和 unknown 不自動重做衝突，git 也無法撤銷外部效果。 | **先 commit 請求檔與固定 ID，再交接**；真正執行端缺结果且不能證明未送則 unknown、不自動補做，對方可用同 ID 抑制重收；只留工作檔，不做通用 outbox 帳本。 | 允許任務在可回滾組裡直接送出，必須接受組失敗後仍有外部工作且需人工核對，不能宣稱整組外部效果當沒發生。 |
| Q3 直接改設定，怎麼避開下格的 dirty 還原？ | A-102 已裁定人／有權限 agent 可直接改設定，下格生效；若來源設定及註冊表也受追蹤，下一格會先還原掉合法修改。 | **可編輯來源放 ignored，tick 驗證後保存本格採用的必要快照到追蹤區**；仍是一套檔案權限，不增加更新服務；註冊表來源一併定義。 | 要來源也受追蹤，修改者就要協調 tick 並自行 commit；這會改變「只改檔即可下格生效」的使用方式，不能暗中加要求。 |
| Q4 30 日清理，要不要回收本家的 Git 歷史占用？ | B-404 原本預設封存，不一定永久刪除；現在移出追蹤工作樹後，舊 bytes 仍在 `.git`、繼續占家裡磁碟，滿碟不會因 git rm 自動好轉。 | **先只承諾移出日常檔案／context**，清楚顯示 Git 歷史仍占空間，真正歷史回收另列管理維護，不先選改寫歷史或 blob 庫。 | 若清理必須實際降低本家磁碟用量，需另選歷史保留與大內容布局；這會影響能回到哪些 commit，不能把一般 git gc 當答案。 |

### 6.1 也發現了，但可直接寫成最小工程邊界，不必增加使用者題目

以下是改寫建議／由已裁方向推出的界線，不冒充已裁的具體實作選擇。

- **group／needs 最小語意**：建議同組任務連續，同一任務只屬一組，needs 只指向前面任務；不存在／循環引用拒絕載入。前置所在組回滾，該成功不算已生效；其他不依賴它的組可繼續。未寫 group 可視為單任務一組。這只是符合順序執行的最小預設，不增加跨 tick DAG、並行任務排程器或 lease；若要非連續 group／循環執行，再另提需求。
- **git 原子範圍**：只承諾同一 repo 的已提交版本與恢復，不承諾工作樹每一刻多檔同時切換。正式輸出／一致查詢讀同一 commit；收件、另一家、外部 API 不在交易內。未 add 的本組新增檔也需撤回；不能只還原已追蹤清單而漏掉新檔，更不能清掉 ignored 收件。group 起點的管理範圍要固定，不能讓失敗任務臨時改 `.gitignore` 躲還原；如何做到留實作驗證。
- **工具、人與 tick 都可能寫本家**：同家一格 tick 不等於任何其他程式都被鎖住；需要 group 保證的追蹤區寫者必須協調，這義務對人／agent／工具相同。不協調的改動可能一起 commit／還原，不因此恢復「工具不能寫 checkpoint」特例；不想納入的資料用 ignored 或外部 workspace。
- **跨家原子與 LLM 共享池**：kernel 在已分到的額度內排程，池代發管理該池真正共享的 provider 限制；刪舊「跨全樹多 scope＋run 一次占齊、零部分占用」保證，不另造分散式交易。子層沒裝 module 只是不再細分記帳，不能讓上層已生效的 cgroup／池限制失效；有限額度用完可等待，unknown 不假裝釋放外部用量。
- **投件身分及去重期限**：請求 ID 可帶發件家識別，序號只比較該 kernel 排隊，不引入全域配號服務。payload 自稱 sender 不可作授權依據；直投怎麼保留可信來源由一般 OS 權限／可信投遞資料支撐，純顯示名稱可標自述，不另造 agent gateway。去重承諾需和保留期一起寫；仍在承諾期內的最小請求證據不能先清，不為了無限期去重保留永久墓碑。
- **喚醒與集中待辦不是新的總帳本**：daemon 可依登記、時間與新檔名稱／通知觸發 kernel，不讀正文；kernel 才核對自己的收件與成員摘要。attention_dir 收來源 kernel 的必要摘要並用來源＋item ID 防撞名，不公開下層內容；通知被刪不等於問題解除。
- **系統性註冊任務仍非 root**：第三批保留控制側專用帳號的系統任務，不能因刪 A-506 就全部偷偷改成 agent UID。用既有可信登記／固定 runner 安排需要的非 root 身分；表內任意 `uid` 不成授權、任意 argv 也不能被 root 解析。具體下層 helper 呼叫方式仍等原 §七題目，不另加特權外掛。

## 7. 本計畫的核查方式

以現有 Markdown 標題抽取 C-/T-/B-/A-/S- 集合，對本表驗證每條恰好一列，再依四擇一處置計數；另比對 23 個非 protocol 檔案都落在六包清單裡，兩個新檔各只有一包持有。全文未把第三批舊「只撤回帳本結果」當現行規則。這是文件計畫核查，沒有執行任何 reset／clean／commit 或產品測試；repo 寫入不在本任務範圍。

**本次核查結果：**74/74 個舊條款各一列、無缺漏與重複，處置加總一致；23 個現有非 protocol 檔案與 2 個擬新增檔案全部分配到六包，沒有同檔兩個主人；8 個來源連結均有效。另經一次獨立架構唯讀審查，未發現違反最高裁定或跨包責任互撞的必修問題。完成時 `git status --porcelain` 與 `git diff --stat` 均無輸出，repo 沒有變更。
