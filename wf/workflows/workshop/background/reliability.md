# 名詞表：外部效果、冪等與耐久性
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### Effect（外部效果／capture／invoke）

**白話**：對「可能已經付錢或改到外面」的呼叫，先留下要做什麼，做完再留完整結果，中間斷掉就老實標不知道。
**嚴格**：先耐久發布 request/key，再執行有外部副作用的 command，最後提交 response/stdout/stderr/exit 與 `done`；不完整證據落在 `unknown`，再由 resolve 明示重試、放棄或採納外部結果。
**在 aos 裡具體是什麼**：目前不存在，是已被近期 scope 延後的提案；目前若實驗 agent loop，由 provider adapter 記簡單 attempt，不明時停住交人。
**為什麼會冒出這個詞**：[agent loop 場](../records/agent-loop-architecture.md) 四位都看到「遠端已收到、本機尚未記錄」的 crash window；[回頭審視](../records/step-back-review.md) 認為先看真 CLI 會不會重複痛。

### idempotency key（冪等鍵）

**白話**：呼叫者為「同一件事」帶上同一個號碼，即使因網路不確定而重送，收件者也只做一次。
**嚴格**：由 caller 提供、在明確 scope 內穩定的 request identity；提供者必須耐久記錄 key 與內容／結果的綁定，同 key 同內容可回既有結果，同 key 異內容必須衝突。
**在 aos 裡具體是什麼**：目前沒有這項保證；Deliver `--key` 只是候選，若沒有耐久 ledger，aggregate 刪掉投遞檔後就無法辨識重送。
**為什麼會冒出這個詞**：這是分散系統與付費 API 的既有概念；所以可以照「HTTP 請求重送不重做」的直覺理解，但差別在 aos 目前還沒有保存舊事實的帳本；缺口由[回頭審視](../records/step-back-review.md)指出。

### ledger（耐久帳本／歷史表）

**白話**：不是只給當下一張收據，而是一直保留「哪些號碼曾經做過什麼」的帳。
**嚴格**：跨 queue 消費與回合邊界保留 key→payload hash→outcome 的耐久索引，含保留期、衝突、清理與恢復規則；是跨回合 Already/Conflict 承諾的必要證據。
**在 aos 裡具體是什麼**：目前不存在，是 Deliver key 四個選項中最重的提案；`.aos/inst.tempd/` 不是 ledger，因為彙整成功後會刪檔。
**為什麼會冒出這個詞**：[回頭審視](../records/step-back-review.md) 發現沒有 ledger 卻承諾跨回合冪等是無法實現的，因此將它變成 Deliver key 的核心取捨。

### `unknown`（無法判定外部效果）

**白話**：電話斷掉時，你不知道對方是還沒聽到、已經照做，還是照做了但回覆沒傳回來。
**嚴格**：外部系統可能已接受或完成請求，但本機沒有足夠證據將 attempt 判為 `done` 或「未執行」的 ambiguous outcome。
**在 aos 裡具體是什麼**：目前沒有通用狀態檔或 resolve 命令；`.runi` 只證明本地 batch 沒跑完，不能證明 provider 有沒有收件／計費。
**為什麼會冒出這個詞**：這是分散系統的既有不可判定窗口；[agent loop 場](../records/agent-loop-architecture.md) 與[有限資源場](../records/finite-resource-queue.md) 用它解釋為何「斷線後是否已計費」常無法從本機判斷。

### two-phase commit（兩階段提交）

**白話**：先問所有參與者「都準備好了嗎」，全部答應後再統一說「現在算數」；中途掛掉可能留下等管理者回來的人。
**嚴格**：分散交易的 prepare/commit protocol，由 coordinator 收集參與者的 prepared 狀態後廣播 commit/abort；能協調原子結果，但會阻塞且不消除遠端效果的 unknown。
**在 aos 裡具體是什麼**：目前沒有 two-phase commit；子結果 proposal→root commit、多檔發布等討論有類似直覺，但尚未形成此協定。所以可以照「先準備、後統一承認」理解，差別是目前只有提案中的單一 root 提交。
**為什麼會冒出這個詞**：多個 lane 先各自算、再由 root 一次發布的討論很像分散交易；這個外部概念用來提醒「協調原子性會帶來等待與恢復狀態」。

### visibility atomicity 與 power-loss durability

**白話**：「別人不會看到半份」和「斷電重開後一定還在」是兩件不同的事。
**嚴格**：同 filesystem `rename` 可作為 namespace visibility 的原子切換；要對 power loss 承諾 data 與 directory entry 耐久，還需定義 write completion、file `fsync`、directory `fsync`、錯誤傳遞與平台差異。
**在 aos 裡具體是什麼**：已實作的三步交接保可見性的完整切換，但目前不承諾斷電耐久，也沒有 `--durable`。
**為什麼會冒出這個詞**：[核心行程場](../records/core-process-and-subprocess.md)、[agent loop 場](../records/agent-loop-architecture.md)、[工具協作場](../records/tool-interop.md) 都警告不能把 rename 說成斷電不丟。

### terminal projection（終態投影）

**白話**：答案早已寫好，只差把「這件事結束了」那格補上；重開時只補那一格，不把事情再做一次。
**嚴格**：已有完整 response 或已提交 resolve decision 時，由既有耐久證據確定性地產生 terminal／done 狀態，不再次 dispatch 外部 effect。
**在 aos 裡具體是什麼**：目前沒有公開命令；`core-scope` 黑客松第 3 輪以私有 `effect.sh resolve` 試作，Effect／resolve 仍是提案。
**為什麼會冒出這個詞**：[core scope 黑客松第 3 輪](../../hackathon/records/core-scope.md)補測 response／decision 已提交、done 尚未提交的兩個中止窗口，重複 resolve 的 commit 與 provider ledger 增量都為零。
