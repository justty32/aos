結論：proto7-2 現有核心足以承載「LLM 寫任務」與「adapt-llm」的第一個原型；需要補強的是包層的候選驗證、發布與恢復、單次模型呼叫回條、token 部分結算，以及慢結果的採用規則，目前沒有足夠理由把 LLM 語意加入 daemon／tick／tock。

# proto7-2：agent／LLM 作者與 adapt-llm 落地提案

## 一、審查範圍與證據界線

審查日期：2026-10-05。審查時 HEAD：

```text
6daebe2ef8227021745def649f4e3d86a3a8038c
```

本次由主線與五條子線平行唯讀審查，涵蓋：

- proto7-2 的核心契約、step／adapt／budget 的文件、實作與測試原始碼。
- `notes/layer-interfaces.md`、問題紀錄與既有試玩報告。
- proto7-1 的 kernel／agent、相關探針及實驗一、二、三。
- C++ `core/llm`、`core/agent` 的介面與執行流程。

**沒有修改檔案、建立報告檔、執行測試或探針、啟動 daemon、呼叫模型、commit 或 push。** 下文引用的測試成績都是 repo 已保存的歷史結果；本次提出的故障案例是待實作後驗證的計畫。

目前 README 記載 364 項測試，最近試玩紀錄包含 budget 核帳與 adapt 流速矩陣，但不能把這些成績延伸成「真實 LLM token 預算與遠端恢復已驗證」。[proto7-2/README.md](../../../README.md):48、[notes/play/README.md](../../play/README.md):14

另須注意：`layer-interfaces.md` 明寫是針對舊 commit 的調查，並非目前定案；其中部分缺口後來已修正或搬到模組。本文以現行程式與 spec 為準，沒有把歷史缺口全部當成現況。[notes/layer-interfaces.md](../../layer-interfaces.md):5

## 二、現有能力與歷史實驗告訴我們什麼

### 2.1 三個包已提供骨架，但各有明確邊界

| 組件 | 現在可沿用的能力 | 接 LLM 時仍缺什麼 |
|---|---|---|
| step | 步驟表、意圖先存、request／attempt 身分、槽外結果、有限重送、未知時停住 | 模型候選的可信編譯與語意驗證；模型呼叫結果與帳務狀態的對接 |
| adapt | 固定來源依據、確定性轉換鏈、來源與自身時鐘分開、`ok／unknown／absent` 暫存器 | 非同步模型工作、候選保存、慢結果採用政策、模型輸出驗證 |
| budget | 單一寫入者、先預留再執行再結算、同 K 去重、未知保留額度 | token 部分結算、真實模型 gateway、usage 契約、遠端結果不明時的恢復 |

依據：[step/spec.md](../../../packs/step/spec.md):56、[step/spec.md](../../../packs/step/spec.md):75、[adapt/spec.md](../../../packs/adapt/spec.md):46、[adapt/spec.md](../../../packs/adapt/spec.md):95、[budget/spec.md](../../../packs/budget/spec.md):47。

這些是落地所需的擴充，不應一律稱為既有程式的 bug：目前 budget 示範資源本來就是假 API 受理次數，adapt 本來就是確定性最新值轉接。[proto7-2/README.md](../../../README.md):108

### 2.2 實驗一、二支持把可靠性放在包層

**實驗一 namespace：服務介面、版本、在途工作都可以經檔案與掛載交接。** 換模型服務後，看不到舊請求的回條就報 unknown，沒有把舊件偷偷送到新服務；重新掛上 `model-prev` 才收尾。這很適合借用為 LLM 服務卡與切換端點的契約。

但它的去重靠 mock 服務自己的 `executed.jsonl`，不能據此認定任何真實模型 API 都能查詢、去重或恢復。[namespace/README.md](../../../../proto7-1/probes/namespace/README.md):5、[namespace/README.md](../../../../proto7-1/probes/namespace/README.md):16

**實驗二 ledger：未知在途不能因 worker 死亡而退款。** 探針中 worker 與帳本都重起、任務目錄歸檔後，預留的 1,000 仍保留；provider 回條到達才結算 900、退回 100。這是新 token gateway 應保留的語意，也證明部分結算已有可參考的舊實驗。[ledger/README.md](../../../../proto7-1/probes/ledger/README.md):33

它同時揭露限制：呼叫者身分是自報的，其他任務可以冒名使用外洩 grant。**守恆帳本不等於安全隔離。** 第一版應維持合作式任務的承諾範圍。[ledger/README.md](../../../../proto7-1/probes/ledger/README.md):37、[budget/spec.md](../../../packs/budget/spec.md):96

### 2.3 實驗三反對的是頻繁排程用途，沒有否定作者或轉換用途

hsched 的歷史結果：

| 方案 | 合格件數 | 互動 p95 等待，控制回合 | 背景最久等待 |
|---|---:|---:|---:|
| A：確定性規則 | 69 | 8 | 39 |
| Atuned：人工調整一次規則 | 71 | 4 | 34 |
| D：LLM 提政策、確定性 kernel 執行 | 71～73 | 5～7 | 41～53 |
| C：LLM 直接挑下一件 | 52～64 | 9～11 | 60 |

D 六次執行只有一次達到 p95 改善門檻，背景等待都變差；C 會把空位留著等模型，結果更差。真模型共 223 次呼叫、186,071 token。[hsched/README.md](../../../../proto7-1/probes/hsched/README.md):107、[hsched/README.md](../../../../proto7-1/probes/hsched/README.md):135、[hsched/README.md](../../../../proto7-1/probes/hsched/README.md):155

這支持兩個設計判斷：

1. 不讓模型延遲卡住確定性的排程與准入。
2. 讓模型產生可保存、可驗證、能重複使用的成果，再量是否值得。

結論也有範圍：只有一份 trace、100 回合、固定一秒回合；「每萬 token 合格」不是實際金額，也沒量人工修正時間。README「Atuned 每個指標都贏」說得太滿，因為 D 有一次合格 73 件，高於 Atuned 的 71 件。[hsched/README.md](../../../../proto7-1/probes/hsched/README.md):104、[hsched/README.md](../../../../proto7-1/probes/hsched/README.md):165

### 2.4 作者原型最該防的是「做出結果，但執行或交付語意錯了」

三項舊證據直接影響新原型：

- `selfprog` 三個模型都算對結果，但「每檔只算一次」是 0／3：一次性工作被寫成反覆執行。作者不能只通過 JSON 檢查，還要驗任務模式與實際執行次數。[probes/README.md](../../../../proto7-1/probes/README.md):34
- `llmkernel` 曾以 2～5 秒的模型迴圈追 400 ms 回合，等看到再 pause 已經超跑；新操作卡能改善，但模型還曾自行改 interval。准入、期限與可修改範圍應由確定性程式限制。[llmkernel/README.md](../../../../proto7-1/probes/llmkernel/README.md):49、[llmkernel/README.md](../../../../proto7-1/probes/llmkernel/README.md):72
- 真模型協作場景三次都有 DONE，其中一次最終交付檔不合格。驗收過的內容與交付內容必須綁同一份雜湊。[proto7-1/README.md](../../../../proto7-1/README.md):14、[2026-10-03-real-2.md](../../../../proto7-1/notes/runs/2026-10-03-real-2.md):24

### 2.5 C++ 現況可借設計，不能直接充當完整 LLM gateway

`core/llm` 是單次非串流文字 completion：

- `Options` 有 URL、model、key、timeout。
- `complete()` 回字串，可另外取 served model。
- 公開回傳介面沒有 usage、finish reason 或完整 provider receipt；請求建構也沒有完整 token 預算契約。[llm.hpp](../../../../core/llm/include/aos/llm.hpp):17、[llm.hpp](../../../../core/llm/include/aos/llm.hpp):48、[llm.cpp](../../../../core/llm/src/llm.cpp):173

`core/agent` 有值得沿用的觀念：沒有新訊息或工具結果就不呼叫模型、工具錯誤有結構化回覆、completion 可注入假回覆。但它接的是既有 `core/loop` 世界與三回合工具往返，並非 proto7-2 的 slot／run 協定。[core/agent/README.md](../../../../core/agent/README.md):114、[core/agent/README.md](../../../../core/agent/README.md):128

靜態讀碼還看到兩個不能照搬的提交順序：

- 成功取得模型回覆後，先刪輸入訊息，再寫 history。
- 先投遞工具，再寫 pending。

程序若在兩者之間死亡，會留下恢復證據不足的窗口；本次沒有執行故障注入確認其完整後果。[core/agent/src/step.cpp](../../../../core/agent/src/step.cpp):320、[core/agent/src/step.cpp](../../../../core/agent/src/step.cpp):347

此外，pi 引擎可以在一次 step 內直接使用自己的工具；一次 pi 子程序不能當成一次付費生成的計量單位。[core/agent/README.md](../../../../core/agent/README.md):169

**建議借用介面分離與離線注入方式；第一版仍以 Python 標準庫的一次呼叫包實作。** 若日後選 C++ 作傳輸後端，需先擴充完整回條與用量介面，再作為可選依賴。

## 三、核心、通用包、agent 與 LLM 包的責任

現行核心明確提供 A 任務、B argv 包裝程式、C 工具三種接法，不同步呼叫模組，也不理解模組語意；新增核心能力還要回答為何這三種接面做不到。[proto7-2/spec.md](../../../spec.md):269、[proto7-2/README.md](../../../README.md):75

建議分工如下；包名僅為提案：

| 層 | 應負責 |
|---|---|
| 核心 | 起程序、slot／run 身分、程序存亡、掛載、tock 最新通知、短暫表鎖、`x` 透傳 |
| 事件保存包 | 保存輸入與識別、消費進度、重播；不能只靠最新 tock 還原漏掉的工作 |
| step | 執行確定的步驟表，保存 request／attempt、結果與進度 |
| budget | 通用整數資源的預留、部分結算、去重與守恆 |
| LLM 呼叫包 | 一次生成的固定請求、傳輸、原始回覆、usage、timeout、遠端未知 |
| 作者包 | 將需求變成候選，驗證後編譯為 steps 與 tasks 增量，保存發布回條 |
| adapt-llm | 固定來源快照、非同步轉換、驗證候選、判斷何時可採用 |
| 較完整的 agent | 何時需要再思考、對話或工作記憶、工具選擇、完成條件；可在作者原型之後增加 |

### 與「事件保存」的最小交接

作者輸入至少要有穩定 `logical_request_id`、固定內容或內容雜湊，以及可恢復的處理狀態。採用結果保存後才確認輸入已處理；不能只因模型回覆到記憶體就消費掉輸入。

目前 `history.py` 是取樣器，會漏回合；沒有 `gap` 也不代表歷史完整。daemon 的 `log.on` 則保存 daemon 事件，不能代替模型請求與候選的保存契約。[modules/README.md](../../../modules/README.md):24

第一版可以只需要「固定輸入檔＋穩定 ID＋處理回條」，不必為了接作者先做一套通用交易系統。

## 四、LLM 當任務作者：候選、驗證、發布分開

### 4.1 模型應產生什麼

最小原型可讓模型選擇已知工具並組合步驟，輸出：

- 使用哪些固定版本的工具與輸入。
- 步驟順序、依賴與預期產物。
- 成功、失敗及等待的分支。
- 可供人讀的意圖說明。

由可信編譯器產生實際 `steps.json` 與要新增的 `tasks.json` 項目。模型也可以直接提出這兩種格式的候選，但仍必須經過相同驗證，不能直接覆蓋執行中的全表。

這樣能把任務模式、實際 argv、輸出範圍、重試性質放在可信工具卡中。`finite: true`、`idempotent: true` 不能只是模型自行宣告：現有 step checker 檢查的是宣告與圖形結構，沒有證明任意命令真的有限或冪等。[step/spec.md](../../../packs/step/spec.md):90

### 4.2 驗證要分三層

**第一層：格式與展開。**

沿用 step checker，再補候選入口的嚴格檢查：

- 工具、參數、路徑、大小與型別符合允許的契約。
- 展開後 argv 能通過核心任務檢查。
- `${req:前一步}` 所指結果在所有可達路徑上確實會先被採用。
- failure、timeout 路徑有明確終點。

目前 checker 會檢查 run argv／expect 的變數，但不等於證明所有執行路徑都能展開；執行時引用尚未採用的 request 仍會停住。run 字串檢查也沒有排除 NUL，不能把 checker 通過當成核心一定能啟動。[aos7_step.py](../../../packs/step/aos7_step.py):192、[aos7_step.py](../../../packs/step/aos7_step.py):404

**第二層：工具契約。**

有限性、可重算性、副作用範圍與重送上限由可信工具卡決定。第一版可以只允許寫自己的版本輸出；任意 shell／任意新程式是另一個切片。

**第三層：實際成果。**

step 的 `ok` 目前表示退出碼 0 且預期檔案存在，並記錄雜湊；它不驗證內容符合使用者要求。原型必須另有獨立答案檢查器，且發布的是同一份驗過的內容。[aos7_step_result.py](../../../packs/step/aos7_step_result.py):63

### 4.3 發布最小契約

建議第一版只做「新增一份獨立工作」，不做執行中換版：

1. 完成候選與 manifest，固定 steps、腳本、輸入及工具卡版本。
2. 保存驗證結果，綁定同一份 payload 雜湊。
3. 保存 publication intent。
4. 短暫取得 `tasks.json.lock`，重讀並合併自己的新項目。
5. 保存「曾完成登記」的回條。

模型呼叫與驗證都在表鎖外進行。核心表鎖是短時間交接用，`addmany` 的原子性也只涵蓋一次表檔提交，不涵蓋候選、表與回條三者。[proto7-2/spec.md](../../../spec.md):157、[proto7-2/spec.md](../../../spec.md):165

必要細節：

- 每份版本使用不同 `job` 與輸出路徑；只換資料夾名不夠，子工作槽名含表內的 `job`。[step/spec.md](../../../packs/step/spec.md):57
- 固定的是來源部分；`frame／results／error／out` 仍需可寫。[step/spec.md](../../../packs/step/spec.md):11
- `x.author` 放 owner、candidate ID 與部署內容識別，供 birth 正證據核對。
- 合併時保留其他任務、`launch` 與頂層設定。前置條件只比自己的項目，不比整份 tasks 雜湊，因 tick 合法地會修改 once 項目。[aos7_tick.py](../../../lib/aos7_tick.py):157
- 同一 publication 重送只查詢或补回條；不得暗中重新啟用已被移除或 disabled 的工作。

最重要的恢復規則是：

| 中斷後證據 | 動作 |
|---|---|
| 有成功回條 | 回同一份歷史回條，不補表 |
| 有完全相符的表項 | 補回條，不再追加 |
| 表項已消失，但有相符 birth／工作 frame | 可確認曾登記或啟動；保持表項不存在 |
| 只有 intent，沒有相符表項或其他正證據 | unknown，不自動補加 |
| 同名項目已被修改或停用 | conflict／modified，保留現況 |

原因是「intent 後、merge 前死亡」與「merge 後、回條前死亡，接著被別人移除」可能留下相同檔案。自動補加會撤銷他人的停止決定。第一版接受這個 unknown，就不需要新增核心 CAS 或跨檔交易。

### 4.4 `ended` 不能當成舊版本已完全停工

step 的 `on_timeout: fail` 會跳往失敗分支，不會先收掉舊子工作；跳轉還會清掉 pending。因此工作 frame 已 `ended`，不代表舊子工作不會再寫檔。[aos7_step.py](../../../packs/step/aos7_step.py):436、[aos7_step.py](../../../packs/step/aos7_step.py):582

第一刀可用獨立版本輸出避開：不覆寫舊腳本、不共用可變輸出、不自動 close／retire 舊工作，並固定 `restart_on_end: false`。若兩版會碰相同外部副作用，就需要另做停止、互斥與交接契約。

## 五、adapt-llm：固定依據，非同步生成，再決定能不能用

### 5.1 不宜直接把 `run_chain()` 換成模型呼叫

現行 adapt 每圈會讀來源並執行確定性鏈；即使同一份依據，也仍呼叫 `run_chain()`。來源雜湊涵蓋整份 JSON，包含 round 等欄位。[aos7_adapt.py](../../../packs/adapt/aos7_adapt.py):288、[aos7_adapt.py](../../../packs/adapt/aos7_adapt.py):306

直接替換會造成兩件事：

- 慢模型讓 adapt 本身無法及時更新狀態。
- 來源只是更新時間欄位，也可能觸發新一輪付費生成。

建議分成：

- **controller**：普通 keep 任務，每個自己的 tock 更新狀態與採用決策。
- **有限 worker**：處理一次固定輸入的模型呼叫，保存回條與候選。
- **validator**：驗同一份候選。
- **register publisher**：由 controller 在自己的回合發布。

第一版最多一笔未解決 call，加一份最新待處理來源。A 處理中出現 B、C，就保留 A 與最新 C；B 可被合併掉。這只適用「最新值」需求；若每一事件都必須處理，應接事件保存的逐件消費契約。

### 5.2 每次候選必須綁固定版本

至少保存：

- 來源快照與雜湊、來源識別、seq／round。
- 來源重建的 epoch。
- chain、prompt、輸出格式與 validator 版本。
- 請求的端點、模型與參數；回覆後另記實際回傳的模型識別。
- call ID、候選原文及候選雜湊。
- 驗證結果與採用結果。

現有 adapt 能偵測「觀察到的倒鐘」，但來源重建後若已追過舊水位，就不一定辨識得出。若要保證不跨來源重建誤用結果，需由來源發布者提供 epoch；daemon 重啟世代不宜直接等同資料來源換代。[aos7_adapt.py](../../../packs/adapt/aos7_adapt.py):277

### 5.3 慢結果有兩種合理政策，必須明選

假設模型看 A，回覆時來源已是 C：

| 政策 | 規則 | 代價 |
|---|---|---|
| `current_only` | 只有依據仍是目前版本才採用 | 來源一直變時，可能永遠沒有可用結果 |
| `within_age` | 仍用原本 A 的身分；通過 epoch、版本、效期與驗證即可採用 | 消費者必須知道它落後於 C |

不能把 A 的答案改標成 C；也不能因為答案剛回來，就把來源年齡歸零。

現行 `max_age` 用來源回合，`patience` 用自己的回合；來源 pause 不增加來源年齡，dst pause 不增加自己的耐性。因此 `within_age` 也不保證一定有產出：效期若短於模型延遲，仍會全部過期。[adapt/spec.md](../../../packs/adapt/spec.md):48

第一個非控制用途可試 `within_age`，同時顯示原始 basis 與落後程度；要求最新狀態的用途則試 `current_only`。两者的有效交付率都應量測，不能只驗「舊結果成功被拒絕」。

### 5.4 JSON 合法與引文存在，不等於轉換正確

建議第一個題目採有限欄位擷取或短摘要，驗證：

- 格式、型別、大小、必要欄位與數值有效性。
- 指定引文或來源位置確實存在。
- 題目要求保留的否定、例外、單位與條件。
- 最終採用內容與驗過的候選雜湊一致。

但「引文存在」仍不能證明結論由引文支持，也不能證明沒有遺漏。這部分需用獨立標準答案或人工驗收量品質。

現有 adapt 的 `err` 是數值轉換的誤差界，不能拿來填模型自報的信心分數。LLM 驗證資訊應放在另一組欄位。[adapt/spec.md](../../../packs/adapt/spec.md):40、[adapt/spec.md](../../../packs/adapt/spec.md):102

### 5.5 消費端也要驗新鮮度

adapt 活著時能把無效值改成 `unknown`；但 adapt 自己死亡或 dst pause 後，暫存器可能一直留著舊 `ok`。

step 的 `num` 條件只讀數字比較，不檢查整份暫存器的 `state`、`my_round` 或更新年齡。因此不能把「數字仍在」當成「目前可用」。[aos7_step.py](../../../packs/step/aos7_step.py):417

第一版可提供確定性的消費工具，同時檢查狀態、basis、驗證結果，以及相對消費者時鐘的更新期限。這仍可放在包層，不必新增 step 專用的 LLM 條件。

## 六、共同的 LLM 呼叫契約與 token 預算

### 6.1 分開三種識別

| 識別 | 意義 |
|---|---|
| `logical_request_id` | 上層使用者需求、作者工作或來源轉換意圖 |
| `call_id` | 一次可能計費的模型生成 |
| `attempt` | 本地程序啟動或恢復次数 |

建議 budget 的 `K.request = call_id`。同一 call 的本地恢復不換 ID；修正 prompt 再生成則是新 call，必須另預留。

`logical_request → call_id → 固定請求雜湊` 的對應要先保存，再 reserve／送出。不能重啟後才另造 call ID，也不能把這份對應放在會被 step close 清掉的 results 中。現有 step 已區分穩定 request 與遞增 attempt，可沿用這個觀念。[step/spec.md](../../../packs/step/spec.md):56、[aos7_step.py](../../../packs/step/aos7_step.py):689

### 6.2 真實 gateway 不能照抄假後端的恢復

現行 budget gateway 遇到既存 intent，會再次呼叫假後端；之所以安全，是假後端能依 K 去重。cancel 查不到效果就退款，也只因這個假後端可確定查詢。[budget/spec.md](../../../packs/budget/spec.md):55

新 LLM gateway 建議採以下順序：

```text
固定請求與 call ID
    → 預留成功
    → 保存 send_intent
    → 發出一次請求
    → 保存原始回覆與 usage
    → 驗證候選／結算／採用
```

`send_intent` 只表示「可能開始送」，不能命名成已確定送达。

| 中斷位置 | 恢復行為 |
|---|---|
| 確定沒有 send_intent | 核對預留與准入後，可進行第一次送出 |
| 有 send_intent，沒有保存回覆 | 查 provider；沒有可依賴的查詢／去重能力就 unknown，不自動再送 |
| 回覆只在記憶體，尚未保存 | 同上 |
| 已保存原始回覆 | 只重做解析、驗證、結算與發布，不再問模型 |
| 已結算但回條未交付 | 依帳本重播同一結果，不重扣 |

每個 call 必須互斥；讀不到 intent 不能當成沒有 intent。原始回覆與 usage 應由同一份提交證據綁住，並先保存再解析模型內容。

這會保守地犧牲一個情況：intent 已存、實際 HTTP 尚未發出就死亡，也會停在 unknown。若 provider 沒有可依賴的查詢或去重能力，這份不確定性無法靠本地檔案消除。

現行 budget spec 已寫明：不可查回後端的 intent 取消只能記 `cancel_requested`，不得寫成 `cancelled`。[budget/spec.md](../../../packs/budget/spec.md):64

### 6.3 token 接入的第一個實作缺口：部分結算

目前 `amount` 可以是任何正整數，但 settlement 明確只接受：

```text
used = 0 或 used = amount
```

所以預留 1,000、實用 623，會被判 unknown；不是已經能直接接 token。[aos7_budget.py](../../../packs/budget/aos7_budget.py):254、[aos7_budget.py](../../../packs/budget/aos7_budget.py):284

建議 budget 包增加通用的部分結算：

```text
0 ≤ U ≤ R
available -= R
inflight  += R

結算後：
inflight  -= R
used      += U
available += R - U
```

例如初始 1,000、預留 300、實用 120，結算後應是：

```text
available=880，inflight=0，used=120
```

結算證據要綁同一個 K、請求 digest 與計量版本；不能只因某檔有 `stage:done` 與整數 `used` 就信任。現有 terminal reader 的檢查相當精簡，真實 gateway 要補齊這份契約。[aos7_budget.py](../../../packs/budget/aos7_budget.py):224

### 6.4 計量單位先固定一種，不先做價格帳

第一版建議固定端點、模型設定與一種 token meter：

- 保存 provider 原始 usage。
- 分清欄位缺失與數值 0。
- 依已驗證的端點契約決定使用哪個總量。
- 不把 input、output、cached、reasoning 等欄位直接全部相加，避免重複計量。
- 必要 usage 缺失時保留預留額；可選明細缺失不必阻擋已可確定的總量。

舊 Python client 在傳輸／JSON 解析失敗時回 tokens 0，usage 缺失也預設 0；這只能作粗略觀測，不能沿用為精確帳務。它還會預設因模型 JSON 不合法而再問一次，這筆生成不能藏在一次 call 內。[proto7-1/aos7_llm.py](../../../../proto7-1/lib/aos7_llm.py):90、[proto7-1/aos7_llm.py](../../../../proto7-1/lib/aos7_llm.py):123

### 6.5 預留額必須有上界依據，才能宣稱硬 token 預算

`R` 至少要涵蓋已驗證的輸入上界與輸出上界。純標準庫不會自動提供所有模型的精確 tokenizer；也不能只憑「字數除以四」或一個名叫 `max_tokens` 的參數，就保證所有端點的計費上界。

因此應區分：

- **已驗證上界**：可在合作式、全部經 gateway 的前提下承諾 token 准入限制。
- **估算預留**：只能稱軟性 token 預算，不能宣稱不超支。
- **金額上限**：还需要另一份價格與計费契約，本切片不必處理。

若出現 `U > R`，要保存真實用量與超額事實，停止新的准入並對帳；不能把 U 截成 R，再說守恆成立。若宣稱停的是整份共用 budget，帳本與 gateway 必須共同處理其他呼叫者及已預留、尚未送出的 call；只停一個 adapt 任務並不夠。

### 6.6 內容可用與帳務已結是兩回事

可能收到合法候選，但 usage 不完整。建議保存：

```text
candidate: valid
billing: pending
```

候選是否可交付由使用情境決定；預留額仍保留。第一版 adapt 若限制一筆未解 call，這筆 billing pending 仍占用該名額，不能另造 ID 繞過。

目前 `budget call` 必須結算後才交終局結果，所以不能直接把它當成這個雙狀態介面；需由新的 LLM 包處理。[budget/spec.md](../../../packs/budget/spec.md):74

另外，`usage.json` 的每 run 取樣加總，本來就只是已觀測用量下界。它可作診斷，不能取代 gateway 帳，也不能再加一次到已結算 token 上。[notes/problems.md](../../problems.md):397

## 七、延遲、失敗、unknown 與 lost 的對應

### 7.1 三個層次必須分開

1. **核心程序事實**：活著、結束、判不出、lost。
2. **操作事實**：模型請求是否可能受理、有無回覆、候選是否可用。
3. **帳務事實**：未預留、預留中、已結算、用量未知。

核心 `lost` 是經本地身分掃描後確定的程序結果；它不證明遠端請求未執行。相反地，本地 lost 但槽外已保存完整回覆，操作仍可恢復成已知。[proto7-2/spec.md](../../../spec.md):220

| 情境 | 核心看到什麼 | 作者／adapt 應表示什麼 | budget |
|---|---|---|---|
| 模型尚在正常等待 | 通常 live | pending；不阻塞 tick／tock | 保留 R |
| 模型內容不是合法 JSON | 通常正常 ended | candidate invalid；不發布為可用值 | 有可信 usage 就照實結算 |
| HTTP 回覆本身無法解析 | ended 或仍待收尾 | 保留原文；受理與用量可能 unknown | 無證據不退款 |
| timeout／連線中斷，可能已送達 | 不會因此自動 lost | call unknown，不盲目重送 | 保留 R |
| worker／runner 意外死亡 | 依核心證據 ended 或 lost | 先查槽外回條，再判操作是否 unknown | 不因程序死亡退款 |
| 本地額度不足 | 普通失敗退出 | denied，沒有送 HTTP | 不新增扣款 |
| provider 回配額／限流錯誤 | 普通失敗退出 | 分辨可確定拒絕與原因不明；避免反覆立即重試 | 只有確定未計費才用 0 結算 |
| 有效答案太晚、依據過期 | 正常 ended | stale；本次不可採用 | 已花 token 仍要結算 |
| 來源確定不存在 | adapt 程序可仍 live | absent | 不新增呼叫 |
| 來源或自身狀態讀不到 | 依故障位置而定 | unknown，不當成不存在 | 保留既有證據與預留 |
| 內容有效、usage 缺失 | 正常 ended | 候選可有效，billing pending | 保留 R |
| 本地 kill 成功 | 該 run 已結束 | 不等於遠端取消成功 | 不自動退款 |

模型亂回 JSON 屬候選輸入不合，應在包層拒收；不應冒充核心事實損壞，讓整個 node 進入核心 unknown。核心的 `fact()` 本來就要求依「誰寫的檔」決定壞 JSON 的歸類。[aos7_fs.py](../../../lib/aos7_fs.py):84

### 7.2 特別容易接錯：退出碼 3 不會穿透所有層

`budget call` 的 rc 3 表示操作 unknown；但 `aos7-step-result` 會正常寫出：

```text
code: 3
ok: false
```

step 接著走 fail，或停在 `halt.kind=failed`。它不會因 rc 3 自動進入 `on_unknown: resend`。[budget/spec.md](../../../packs/budget/spec.md):74、[aos7_step_result.py](../../../packs/step/aos7_step_result.py):75、[aos7_step.py](../../../packs/step/aos7_step.py):447

第一刀可以避開修改 step：作者與 adapt controller 自己讀 LLM 操作回條，step 只執行已產生的確定性工作。若之後要在 step 中直接呼叫 LLM，必须明定包層如何表示「已有結果檔，但操作仍未知」；不能只設定 `on_unknown: resend` 就以為完成整合。

### 7.3 四種時間不能混用

| 時間／期限 | 現有意義 | LLM 接入注意事項 |
|---|---|---|
| daemon `action_timeout` | tick／tock 動作期限 | 不會替普通 LLM 任務限制 HTTP 時間 |
| 模型呼叫 deadline | 新 LLM 包自己的牆鐘期限 | 應限制整次等待；單次 socket timeout 不等同總期限 |
| step／budget `patience` | 自己 node 的回合數 | pause 時不走，不能直接當秒數 |
| adapt `max_age` | 來源回合數 | 來源 pause 時年齡不長，必要時另看 stall |
| task／grant 的 until | 新工作或新請求的准入期限 | 不會自動殺掉已准入的遠端工作 |

依據：[proto7-2/spec.md](../../../spec.md):85、[step/spec.md](../../../packs/step/spec.md):83、[budget/spec.md](../../../packs/budget/spec.md):57、[budget/spec.md](../../../packs/budget/spec.md):79、[adapt/spec.md](../../../packs/adapt/spec.md):48。

node pause 只停止新回合，既有程序仍可能繼續；任務 kill 又要等 tick／tock 才處理。因此模型 worker 的等待期限不能只靠 controller 的回合耐性。worker 可以在 dst pause 期間保存候選，但若沿用 adapt 的發布時序，暫存器應等 resume 後的自身回合再更新。[proto7-2/spec.md](../../../spec.md):76、[proto7-2/spec.md](../../../spec.md):243

## 八、保存與恢復的承諾範圍

模型呼叫回條、未結算用量、來源快照與候選，應放在普通任務槽之外。核心會重用槽，也會刪除已移除且結束的槽；step close 另會清理自己的 results。[proto7-2/spec.md](../../../spec.md):265、[step/spec.md](../../../packs/step/spec.md):76

最低保存規則：

- 未解 call 不清。
- 尚未結算的回條與用量證據不清。
- 尚未確認消費的輸入、候選及採用證據不清。
- 已完成資料的清理要有自己的退役或保留政策，不能跟著 slot 消失。
- 第一次原型可以先不做壓縮，但須承認資料會隨 call 數成長。

現有 budget 本來就保存到預算明確退役；這是可沿用的起點。[budget/spec.md](../../../packs/budget/spec.md):95

另有一條需要寫清楚的界線：核心 `write_json()` 是暫存檔加 `os.replace()`，沒有 fsync 流程。它提供原子可見性，不能直接宣稱斷電後的金融級持久性。[aos7_fs.py](../../../lib/aos7_fs.py):119

第一版可先限定驗證「程序被殺、程序重啟」；若要求斷電後仍不重送、不漏帳，需另行定義資料與目錄的持久化顺序。

## 九、最小可試切法與驗收計畫

以下是建議的拆法，不代表替使用者選定產品方向；所有執行均屬後續工作，本次未跑。

### 第一刀：固定工具的作者，先驗完整交付路徑

使用現有 CSV 範例的 convert → stats 兩步作題目。它已使用 request 核對上一步產物，而且只寫自己的 out，適合隔離版本。[examples/csv/steps.json](../../../packs/step/examples/csv/steps.json):1

切片包含：

1. 一份需求輸入與穩定 ID。
2. 固定工具卡。
3. 假模型候選注入點。
4. 候選驗證與確定性編譯。
5. 新工作發布與回條。
6. 現有 step 執行。
7. 獨立檢查實際 CSV／JSON 結果與執行次數。

先放合法、壞 JSON、錯參數、不成立的依賴、錯模式、假冪等宣告等固定候選，驗證「接受正確的，也拒絕錯誤的」。這一步不需要完整聊天 agent，也不需要模型進排程迴圈。

通過後，再以一個真實模型 call 取代假候選。真呼叫前要具備下一刀的最低呼叫與預算契約；自動 JSON 修復先設為零。

### 第二刀：單次 LLM gateway＋token 結算

範圍固定為一個端點、一種計量、單次非串流生成：

- 固定 call ID 與請求內容。
- 部分結算。
- 原始回覆與 usage 保存。
- intent 後不明就 unknown。
- 沒有隱藏生成重試。
- 明確區分估算預留與已驗證上界。

這層可同時供作者與 adapt-llm 使用。它的驗收先用假傳輸，不必用付費模型製造故障。

### 第三刀：一條非控制用途的 adapt-llm

選一個有獨立答案的有限擷取或摘要任務：

- 固定來源版本。
- 一筆未解 call＋一份最新待處理來源。
- 驗證後才發布。
- 分別試 `current_only` 與 `within_age`。
- 模擬快／慢來源、快／慢模型及 pause。
- 消費工具確認暫存器沒有凍結在過期的 `ok`。

這一刀主要回答「慢答案仍有多少可用价值」，不只驗證拒絕機制。

### 必要故障矩陣

| 組別 | 應注入的情境 | 必須成立 |
|---|---|---|
| 呼叫提交 | reserve 前後、intent 前後、遠端受理後但本地未存回覆 | 不因恢復另造 call；證據不足留 unknown |
| 回覆恢復 | 原始回覆已存、解析前死亡；結算後、回條前死亡 | 不再問模型；不重扣 |
| token | 部分使用、usage 缺失、U>R、兩件搶最後額度 | 差額正確；未知不退款；超額不偽裝成功 |
| 取消 | 已有 intent 但無回覆時 kill／cancel | 不宣稱遠端未執行 |
| step 接口 | 正常 rc 3、整組 SIGKILL、產物存在但結果未寫 | 分清 failed、缺結果 unknown 與業務 unknown |
| 作者發布 | merge 前後死亡；回條前表項被移除或 disabled | 不重加、不恢復他人停掉的工作 |
| 版本 | 驗證後換檔；新舊工作同時存在；timeout fail 後舊 child 晚寫 | 不交付未驗版本；不污染新輸出 |
| adapt | A 在途時 B、C 到；回覆過期；來源換 epoch；dst pause | 不把 A 標成 C；依政策採用；發布時序一致 |
| 消費端 | adapter 死亡而暫存器仍是 ok | 不無限使用凍結舊值 |
| 清理 | worker 槽消失、step close、工作結束但帳未結 | 回條與未解預留仍可追查 |

可延伸的現有測試位置：

- step 意圖、结果與 unknown：[packs/step/tests/test_step.py](../../../packs/step/tests/test_step.py)
- budget 帳本與 step 接合：[packs/budget/tests/test_budget_ledger.py](../../../packs/budget/tests/test_budget_ledger.py)、[test_budget_step.py](../../../packs/budget/tests/test_budget_step.py)
- adapt 流速、pause 與恢復：[packs/adapt/tests/test_adapt_flow.py](../../../packs/adapt/tests/test_adapt_flow.py)
- 歷史三實驗：[namespace/probe.py](../../../../proto7-1/probes/namespace/probe.py)、[ledger/probe.py](../../../../proto7-1/probes/ledger/probe.py)、[hsched/probe.py](../../../../proto7-1/probes/hsched/probe.py)

### 真模型試驗應量什麼

作者與 adapt 分別記錄：

- 獨立驗收通過率，以及最終交付是否就是驗過的那份。
- 實際付費 call 數與已知 token；未知用量另列。
- 候選產生、驗證、發布與完成的延遲。
- 人工修正次數與時間。
- 重複執行、重複預留、重複結算。
- adapt 的過期拒收率、有效交付率與採用時來源年齡。

作者要和手寫步驟表比較；adapt 要和原值／確定性轉換基準比較。少量真模型試跑可以找出問題，但不宜據此宣稱穩定成功率。

## 十、待決題與預設建議

| 待決題 | 預設建議 | 影響 |
|---|---|---|
| 第一個要證明的是作者價值，還是跨 node 語意轉換價值？ | 先做 CSV 固定工具作者，因已有 step 範例與獨立答案 | 這是驗證成本較低的起點；若優先需求在跨 node，順序可以交換 |
| 作者可組合既有工具，還是可寫任意程式？ | 第一刀只組合可信工具 | 任意程式需要另外處理執行範圍、驗收與副作用 |
| 候選是否自動發布？ | 預設先產生可審查候選；已明確授權的固定試驗可自動發布 | 發布權限是部署政策，不由模型自行決定 |
| 是否需要執行中替換舊工作？ | 第一版只新增獨立版本 | 避免把 `ended` 誤當成所有舊副作用已停止 |
| adapt 必須等於最新來源嗎？ | 非控制用途先試 `within_age`；必須最新的用途用 `current_only` | 決定慢模型會提供落後答案，或可能長期無答案 |
| 每個來源事件都要處理，還是只需最新值？ | 明確分開；最新值可合併，逐件需求接事件保存 | 不能用 coalescing 默默丟掉必須處理的工作 |
| 第一個 token meter 與上界如何定義？ | 一個端點、一種已確認計量；無法證明上界就標示軟預算 | 決定能否宣稱硬 token 限制 |
| 遠端結果不明時，要成本確定性還是自動前進？ | 保留 R，不自動重送；新生成須是另有記錄的明確政策 | 可能永久卡住部分額度，但避免恢復時重複付費 |
| 候選有效、usage 未知，能否交付？ | 可保存並顯示有效候選與 billing pending；仍保留預留額 | 內容交付與帳務結清分開，不以假退款換取前進 |
| adapt 的語意驗收標準是什麼？ | 先列有限欄位、必要否定／例外與獨立答案 | 沒有這份標準，就只能驗格式與來源，不能宣稱轉換正確 |
| 保存要承諾到什麼故障等級？ | 第一版驗程序中斷；未結算／未確認消費資料不清 | 斷電持久性與長期清理另訂契約 |
| 何時值得升級成完整 agent？ | 作者與單次呼叫價值確認後，再加入多輪記憶與工具選擇 | 避免在尚未量到交付收益前，先增加呼叫與恢復狀態 |