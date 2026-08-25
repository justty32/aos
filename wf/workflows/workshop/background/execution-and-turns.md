# 名詞表：回合、執行與喚醒
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### world（世界／world folder）

**白話**：就是你交給 `aos exec` 的那個資料夾；資料夾現在長什麼樣，就是它現在的狀態。
**嚴格**：一個以檔案系統為耐久狀態容器、以 `<folder>/.aos/` 為指令區的執行單位；每次 `aos exec <folder>` 把它從一個回合推到下一個回合。
**在 aos 裡具體是什麼**：已存在；是任一經 `aos init <folder>` 建立 `.aos/` 的 `<folder>`，實際版面見 [aos-folder](../../../docs/aos-folder.md#三版面)。
**為什麼會冒出這個詞**：原始回合模型就把 folder 叫世界；[核心行程場](records/core-process-and-subprocess.md) 又用它來區分「耐久資料夾」與 OS process、lane。

### `kernel.json`（核心序言／尾聲描述檔）

**白話**：每批作業前後都必須跑的固定步驟，不靠上一批作業自己把它再塞回去。
**嚴格**：版本化的 per-world kernel descriptor，由 executor 在 claim 一批後合成 prologue＋業務 batch＋epilogue；本地完整檔或分層合成仍未定案。
**在 aos 裡具體是什麼**：目前還不存在 [aos-folder](../../../docs/aos-folder.md) 或程式中；使用者已表態「kernel.json 收」，但檔案內容、失敗邊界與升級機制尚未拍板。
**為什麼會冒出這個詞**：[核心行程場](records/core-process-and-subprocess.md) 四位都指出「尾指令自我複製」會因 crash 斷鏈或重跑增殖，所以提出類 init(1) 與 reset vector 的版本化開機流程。

### init(1) 與 reset vector

**白話**：一個是系統啟動後固定先起來的管理者，一個是處理器剛開機時固定從哪裡開始跑；都不靠上次工作自我複製。
**嚴格**：`init(1)` 是傳統 Unix 的第一個 userspace process 與服務生命週期根；reset vector 是 CPU reset 後的既定取指位置。這裡只借「啟動入口由機器保證」的直覺。
**在 aos 裡具體是什麼**：沒有 `init(1)` 或硬體 reset vector；對應的提案是 `aos exec` 每回合都從 `kernel.json` 取得序言／尾聲。所以可以照那個直覺理解，但差別是 aos 是回合級、不是開機級。
**為什麼會冒出這個詞**：[核心行程場](records/core-process-and-subprocess.md) 用它們解釋為何「永久序尾」應由 executor 套用，不是由尾指令重生自己。

### `.runi`（未完成回合現場／回合鎖）

**白話**：那批指令已經被拿走開始跑，但沒有人走到正常收尾，所以現場檔還留著。
**嚴格**：`inst.json` 被完整讀入後原子 rename 為 `inst.json.runi`，回合正常返回後刪除；存在時拒絕新 exec，表示上一回合沒跑完，不表示某個子指令成功或失敗。
**在 aos 裡具體是什麼**：已存在；`<world>/.aos/inst.json.runi`，規格見 [aos-folder](../../../docs/aos-folder.md#六交接協定三步每步一次-rename)，拒絕啟動的退出碼是 3。
**為什麼會冒出這個詞**：這是 T2 已落地的 claim/crash 邊界；後續研討常把它與 Effect `unknown`、lane 生命週期混用，所以必須明說它只管本地回合。

### tick（定期心跳／wake）

**白話**：外面每隔一段時間敲一下門，讓專案檢查有沒有今天到期、現在該做的事。
**嚴格**：一次性的 periodic dispatcher invocation，依序呼叫各定期 workflow，由各 workflow 判斷 due state 並執行；它不是一個常駐 scheduler 本體。
**在 aos 裡具體是什麼**：文件工作流已存在，入口是 `wf/workflows/tick.md` 與 `/wf-tick`；`aos wf` runtime 內建 wake 目前不存在。
**為什麼會冒出這個詞**：[workflows 場](records/workflows-on-aos.md) 想知道定時嗚醒是普遍需求還是這個 repo 的特例，因為它會決定是否值得長出 scheduler state。

### cursor（已處理位置／輪轉位置）

**白話**：一個書籤，記得上次做到哪裡或下次輪到誰，避免每次從頭來或總是先吃同一份。
**嚴格**：耐久 progress/scheduling pointer，可指向最後已 commit 的 event、下一個 ready job 或 round-robin 位置；必須在對應 Deliver/commit 成功後才前進。
**在 aos 裡具體是什麼**：目前沒有通用 cursor 格式；workflows task、agent history、有限資源公平排程都曾提出各自的 `cursor.json`。
**為什麼會冒出這個詞**：[核心行程場](records/core-process-and-subprocess.md) 的 `dofuncs`、[agent loop 場](records/agent-loop-architecture.md) 的 history commit 與[workflows 場](records/workflows-on-aos.md) 的 tick 都需要避免「先記已做、其實沒投遞成功」。

