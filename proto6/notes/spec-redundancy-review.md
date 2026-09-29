# proto6 規格冗餘審查

← [概念入口](concepts.md)｜[規格草案](../spec/README.md)

審查日期：2026-09-28（Asia/Taipei）；關鍵來源最後重讀於 22:24。這是使用者要求的 Astra 唯讀架構審查，只新增本報告，不更動規格或產品。規格在審查期間仍由其他 agent 修訂，以下以交付前重讀的章節為準；不把草案預設當成使用者已批准的決定。尚無實作，所以「可省成本」是設計判斷，不是效能量測。

## 問題、方法與結論

問題是：目前拆出來的概念與介面，有沒有讓人多理解、讓程式多維護一套其實可省的東西？

已讀 concepts、base、agent、scheduling 四份概念稿、三層全部規格、terms/contracts，以及人類架構與負載紀錄。使用本地條款交叉核對，不新增 Linux 或外部協議事實。判準是 10,000 份登記、每小時不到 100 個活躍、單機及雲端 LLM；不把登記數直接當成高併發或分散式需求。

**三大責任分區值得保留；六塊基底、五塊 agent、數塊排程也可以是閱讀分區。冗餘主要長在細部資料與控制機制，並非三分法本身。** 最明顯的是 checkpoint 與帳本保存同一控制狀態、短 tick 疊上 lease/heartbeat、設定引用再另存三份版本。其次是每層各自完整重述控制規則，以及為尚未出現的消費端與串流先定介面。

以下 A 是不改產品原意的編輯去重；B 是可替換的實作建議，應先驗證等價性；C 是使用者可見政策，不能借「精簡」之名代為決定。本報告沒有要求使用者逐項回答，未採納者保留為草案討論材料即可。

## A．可直接去重的編輯問題

### A1．同一契約有數個完整的規範來源

證據：[C-05](../spec/contracts.md)、[B-403](../spec/base/storage.md)、[A-501／A-502](../spec/agent/tick.md) 都敘述 proposal 的 fencing、原子提交與重送；[B-602](../spec/base/lifecycle.md) 與 [S-103](../spec/scheduling/runs.md) 都定義 claim 活性與重派；[A-202／A-203](../spec/agent/input.md) 與 [S-101／S-102](../spec/scheduling/runs.md) 都定義輪次、暫停及取消。

這些篇章需要解釋自己的交界，但不需要各自保存一份完整規則。可指定 C-05 管資料與提交原子性、B-602 管程序互斥與活性、S-101／S-102 管任務轉移；其他篇只寫本層輸入、輸出、特有失敗及引用。驗收可以保留不同層的觀察視角，不必抄完整轉移或相同數字。

保留的不變量是原子消費與派工、舊寫者不能提交、停止與完成必須有證據。少掉的是改一條規則必改三處、讀者猜誰為準與規格漂移的成本。**無需另做產品裁決；去重時不可刪掉各層獨有條件。**

09-29 已落實：A1 的 proposal 部分以 C-05 統一定義資料、驗證與原子提交；B-403、A-501／A-502 改寫各層交界及引用。claim 活性與任務轉移的其餘去重不在本次主題。
09-29 已落實：A1 的 claim 部分以 B-602 為程序互斥與活性的唯一規範來源，claim 欄位集中於該條，S-103 只保留排程視角與引用；其餘 A1 主題由別隊處理。
09-29 已落實：輪次部分以 S-101／S-102 為唯一規範來源，A-202／A-203 改為 agent 視角與引用，保留結果路由、原子消費及輸出證據；輪次仍是軟性原則、新訊息歸屬未定案，needs_attention 的 resume 仍為可選出口，停止與完成的證據及重啟屏障不變。

## B．實作機制精簡建議

### B1．checkpoint 應保存 agent 尚未完成的思路，不必再抄控制帳本

證據：[B-401](../spec/base/storage.md) 把 jobs、attempts、run、cursor 與 checkpoint pointer 放 SQLite；[C-05](../spec/contracts.md) 的 Proposal 又帶 phase、消費 IDs、新 jobs；[A-502](../spec/agent/tick.md) 的 checkpoint 另存 phase、pending_job_ids、history_tail、input_seq、wait_reason、due_at_ms，並要求 pending_job_ids 等於帳本的未完成／未消費集合。

最確定的重複是 **pending_job_ids 與帳本 jobs＋消費狀態**，以及 **checkpoint.phase 與 Proposal.phase／提交後 phase**。input_seq/history_tail 與控制 cursor 也需明確說是獨有語意位置，還是同一進度的副本；目前讀者必須理解兩邊如何一致。不能將所有 cursor 都合併：收件、語意消費與通知水位可能指不同事件。

建議把 Proposal 分成「受限控制增量」與「agent 語意 continuation」。控制增量只有本次消費、新增 jobs、歷史／輸出新增及完成提案；pending 集合、控制 cursor、等待工具／quota 原因由帳本產生唯讀視圖，tick 不再回寫整份副本。history_append／outputs 是本次提交增量，可放 Proposal，不必混進每份持久 checkpoint 的狀態格式。checkpoint 保留真正不能從帳本推回的 agent 決策、必要計數與 continuation。

小型控制增量可直接納入同一 DB 交易；大段文字及語意內容仍可引用已驗證 blob。不必為了「看得懂」改成任意工具都能改權威 state.json，也不必把所有內容塞進控制 DB。

保留：一次交易提交消費與派工、可重放、owner 驗證、fencing、quota、完整性與「尚有未知工作不能完成」。少掉：同一欄位的雙寫、交叉驗證、schema 遷移及人工排查兩份狀態的負擔。**主要是 B 類實作選擇；只要人仍可匯出閱讀、編輯來源並受控導入，不需改任務語意。**

09-29 已落實：Proposal 分為受限控制增量與 agent 語意 continuation；checkpoint 移除 pending、phase、等待與控制進度副本，input_seq／history_tail 明定為帳本進度而刪除；歷史／回覆增量移至 Proposal，唯讀視圖與提交安全檢查仍由控制帳本負責。

### B2．單機短 tick 的 lease/heartbeat 可先延後

證據：[B-602](../spec/base/lifecycle.md)、[S-103](../spec/scheduling/runs.md) 同時有 live claim、generation、checkpoint revision、home lock、30 秒 lease、10 秒 heartbeat；[B-201～B-203](../spec/base/execution.md) 已另有程序監看、執行逾時與清空程序樹的條件。lease 過期仍必須先核對舊程序，不能直接接手。

因此 lease 在這個版本主要是「提醒去對帳」，不是提供接手的安全證據。首版可保留 claim、提交 fence、受管程序觀測、tick deadline 及重啟對帳，用退出事件／deadline 觸發回收，暫不做第二套定期 heartbeat、suspect 狀態及租期續寫。若將來出現 supervisor 與控制端可獨立長期失聯、需要特定故障偵測時間的部署，再加入活性協議。

這不是建議同時刪掉鎖、generation、revision：互斥、拒絕遲來提案、拒絕過期快照各自仍有用途。是否能以 current attempt token 取代 generation，也須先證明所有寫者與重放情境，不能僅因 ID 多就合併。

保留：每 agent 至多一個有效 tick、確認舊受管範圍清空才重派、舊提交無效、卡住工作仍會逾時及對帳。少掉：定時續租寫入、時鐘與續租失敗分支、heartbeat owner 爭議及其測試矩陣。**B 類建議；若使用者另要求獨立控制端的失聯偵測 SLA，則需先保留該要求。**

09-29 已落實：B-602 改由程序退出事件／tick deadline 觸發回收，首版移除 lease、heartbeat、suspect 與續租，保留 claim、generation、checkpoint revision、home lock、提交 fence、受管程序觀測及重啟對帳；同步 S-103、S-402 與 V-03，維持裁定 7 的重啟全殺／在途 unknown，獨立長期失聯部署才另加活性協議。

### B3．一個設定 bundle revision 已可固定工具與 context 版本

證據：[A-101](../spec/agent/configuration.md) 的不可變 config 已指向不可變 context_policy_ref 和 tool_manifest_ref；[A-102](../spec/agent/configuration.md)、[C-02](../spec/contracts.md)、[S-101](../spec/scheduling/runs.md) 又要求每 run 保存 config_revision、context_revision、tools_revision 三項。

如果後兩項就是該 config 指定的內容，三個引用形成必須額外檢查一致性的組合。首版讓 run 只固定一個 config/bundle revision，由它引用工具、context、模型設定即可。人仍可分檔編輯各部分；發布時組成一份不可變 bundle，並不要求把所有工具正文複製進同一檔。查詢可展開顯示各子版本，無須把展開值當另一份權威。

保留：已接納 run 不因來源修改而悄悄換版、引用可追溯、非終態版本不得回收、秘密不進快照。少掉：三引用的合法組合驗證、三指標更新及缺一版本時的分支。**B 類建議；只有要讓 run 額外覆寫 config 的工具／context 組合時才需要更多欄位，而該功能目前沒有明確需求。**

09-29 已落實：A-101／A-102、C-02 與 S-101 改為單一 config_revision 引用不可變 bundle，工具、context policy 與模型設定由 bundle 解析，查詢展開值不另作權威；保留引用追溯、非終態引用不得回收及秘密不進快照，依裁定 2(b) 保留整輪固定為建議與可記錄的 tick 邊界換版。

### B4．agent phase 可少當一張獨立控制狀態機

證據：[T-04](../spec/terms.md) 保存 agent.phase、run.state、job.state、attempt.state；[A-503](../spec/agent/tick.md) 要控制層檢查完整 phase 轉移表；[S-102](../spec/scheduling/runs.md) 另管理 paused、needs_attention、cancel_requested 等屏障。agent 的 paused/error 同時反映當前 run 的控制狀態；wait_reason 又與 [S-402](../spec/scheduling/operations.md) 的查詢理由交疊。

不建議把 run/job/attempt 合成一種狀態。較小的改法是：run 暫停、取消、錯誤屏障保留權威；agent 顯示的 paused/error 與「等待工具／額度」由控制事實推導。think/act 若沒有必須單獨恢復的中間決策，就不用為顯示一次 act 而新增一次持久轉移；有 continuation 才保存真正的語意位置。

保留：agent 語意步驟仍可觀察、idle 不代表 run 成功、暫停後不得派工、未知結果不被掩蓋。少掉：phase × run × job 的非法組合驗證與恢復同步，控制端也不必理解不影響授權或耐久性的每個思考步驟。**B 類建議；若 phase 本身是外部可寫契約而非觀測值，才會涉及 C 類改動。**

09-29 已落實：phase 六值改為由控制事實與語意 continuation 推導的唯讀觀測值，wait_reason 統一由 S-402 定義；run 屏障、完成證據與 unknown 保護維持不變。

### B5．保留必要 RPC，但先不把每個內部交接做成通用介面

證據：[B-502](../spec/base/transport.md) 提供 result.ack，但同段已要求 tick 的結果消費 ack 與 checkpoint 交易一起提交，獨立 method 留給「其他可信接收端」；[S-305](../spec/scheduling/llm.md) 宣告首版 stream=false，卻先規定未來 chunk_seq／ephemeral／片段去重。

首版若只有目前列出的消費者，可先不公開 result.ack 操作；保留內部的持久消費事實與回收條件。等出現確定的第二種消費者，再給它專用的提交／確認契約。串流只保留「目前不支援；部分片段不是 final」的不變量，片段 schema 移到未來設計材料。這不改已接受的 JSON-RPC 檔案交接，也不要求改成其他協議。

同一程序內的 owner 模組不必為每個函式呼叫再包 JSON-RPC／outbox；只有跨故障邊界、需要持久交接的地方才使用該機制。這是實作提醒：現稿沒有明文強迫每個模組都走 RPC，不能說它已經做了這種浪費。

保留：接件、執行終局、已消費三種事實仍分開，未消費結果不能刪、重送不能重複結算。少掉：暫無呼叫者的 API、權限矩陣及未實作串流的驗收承諾。**B 類首版範圍建議；若已有未列出的外部消費者，先保留它的需求。**

09-29 已落實：B-501～B-503 與 methods.json 已將 result.ack 標為首版不公開，保留內部持久消費、checkpoint 原子提交、回收條件與重送不重複結算，並補上同程序模組不必包 JSON-RPC／outbox；S-305 移除未來片段 schema 與展示驗收承諾，首版拒絕 stream=true，保留部分內容不算 final。

## C．不能當作純去重的產品政策

### C1．「可修改」與完整版本／內容庫制度之間仍需有人用的接點

證據：[B-401](../spec/base/storage.md)、[C-05](../spec/contracts.md) 明定受管不可變 blob 與控制 pointer；[A-301](../spec/agent/memory.md) 禁止覆寫已提交 history／notes 版本；[A-102](../spec/agent/configuration.md) 要修改現有 queued/active run 的設定時取消再建。這是比概念稿「資料夾是本體」更具體的新預設，現稿已正確標為可替換，不能宣稱使用者早已接受整套制度。

可信快照有必要性：不應把可由同 UID 工具改寫的檔案直接信任為控制結果。但「人修改一份 notes／人格」不必因此理解 blob key、revision、匯入器與 GC。建議人用入口維持可讀來源與一次 apply；runtime 只保留必要的已提交快照。相同內容可共用引用，候選檔與正式快照不必永久各留一份；實際送給模型的 context 可與 LLM messages_ref 引用同一 blob，不另複製一份「記憶層 context」。只有調查需要且未被其他權威引用涵蓋的內容才增加快照。

仍需使用者選的是：人手改了來源何時生效、能否修改目前 run、哪些歷史允許修訂。**不能藉省資料副本，取消來源追溯或已接納工作的固定輸入；也不能反過來把所有內容永久唯讀當成既定方向。** 成本在日常修改步骤、留存與容量，不只是儲存 bytes。

### C2．人工處置與輪次政策不是安全機制的唯一推論

證據：[A-202](../spec/agent/input.md)、[S-101](../spec/scheduling/runs.md) 規定一則訊息一 run、普通新訊息永遠排後輪；[A-401／A-404](../spec/agent/tools.md) 規定兩次無效模型回覆或未知 LLM 結果後人工處置；[A-302／A-303](../spec/agent/memory.md) 將超預算、容量恢復交人工；[C-06](../spec/contracts.md)、[B-404](../spec/base/storage.md)、[S-404](../spec/scheduling/operations.md) 規定 30 日留存。

這些可能是合理預設，但會直接決定「一句改算另一檔為何沒生效」、「偶發雲端斷線為何整輪等人」、「改錯設定是否必須重開任務」。安全要求是不能偷偷重複副作用、不能越過持久屏障，不是所有 LLM 呼叫都永遠只能人工確認後重試。使用者若願意對無工具執行的純模型呼叫接受有限重複費用，可另定有上限且先授權的政策；有外部副作用的工具仍維持 unknown 保守處理。

同樣地，一 run 一 input 現在令 input_ids 陣列只含一項，但是否縮成單一引用取決於輪次政策是否真要定案，不能從目前預設倒推刪掉未決能力。數字留存、公平老化門檻與暫停是否擋後輪也是政策。**本審查不代拍，也不要求立刻追加一串確認；先以一個人用流程試讀，再決定哪些預設值得留下。**

## 看似重複但應保留的區分

**agent／run／job／attempt／request 的語意不同。** T-03、C-02／C-03 與 S-104 已給出重試與遲到結果的用途：一次人的要求跨很多工具，一個工具可有多次嘗試，一個 RPC 重送不能重建任務。實體上可用外鍵、派生 owner 或查詢視圖少存資料，但不要把這些語意抹平。model call_id 也只在模型回覆的範圍內有效，不能不經命名空間就當全局 job_id。

**身分、執行資源、自有容量不是三套同義權限。** B-301 所述 UID、cgroup、project quota 與全局准入各限制不同事情；全局上限與每 agent 上限也都要保留。工具沿用 caller，不需另造「正式員工／臨時員工」身份層。現稿未重新引入那一層，這點是好的。

**程序退出、受管後代清空、結果 durable、結果已消費是不同完成點。** B-202、B-402、B-503 的區分有恢復用途；可以減少傳輸副本或合併交易，不能因字面都叫完成就刪掉證據。取消意圖不是已停止，外部 unknown 不是普通 failed。

**history、notes、context 也不是同一份記憶。** A-301／A-302 的用途區分應保留；同一內容多處使用時共享引用即可，不必每個概念各持一份正文。原始結果與模型可讀的受限預覽也有不同用途，預覽不能冒充完整證據。

**概念導讀與規格不是兩個競爭正本。** notes 說用途與未決邊界，spec 列候選契約及驗收，重疊的簡短例子有閱讀價值。真正應避免的是三篇 spec 各自定義同一控制規則，或把三層閱讀分區實作成三套服務、資料庫與交接機器。

## 建議採納順序與驗證邊界

先做 A1 的單一規範來源；再試 B1 的 checkpoint 去副本與 B3 的單 bundle；接著檢驗 B2 能否用既有程序觀測與 deadline 代替續租。這三項最能減少程式與人同時維護兩套概念。B4／B5 隨首版介面一起縮，不需要另啟大型重構。

每項 B 建議需用同一組核心情境證明：提交前後中斷、遲到舊提案、結果重送、未知副作用、quota 滿、新輸入與 tick 結束競爭。現有驗收的安全結果不降低，才算等價精簡。此輪沒有改 runtime 或 spec 正文，也沒有執行產品測試；只驗報告引用及重读來源。部署外牆尚未選定，本文不判定其具體啟動方案，也不把 metadata 可恢復誤當整體 Linux 隔離完成。

重讀時確認已修正、不列為現存缺陷：A-403 已改為讀取 B-103 ExecResult 的 adapter，不再另定權威工具結果；S-103 已對齊 B-602，由可信 supervisor 更新活性；A-302 已區分組 context 的預算快照與 S-302 實際占票。因此本報告的 A1 是維護上的重複來源問題，B2 是是否需要續租的機制問題，不再指控這些已修的矛盾。
