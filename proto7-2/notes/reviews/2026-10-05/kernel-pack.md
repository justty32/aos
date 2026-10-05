kernel 任務包可以不改 daemon／tick／tock 核心就成立；最小第一版的預設建議是「可接續的決策骨架＋綁定原始 run 的 kill」，讓 step、budget、adapt 保持獨立，並把完整 restart、排程及 aos7-pack 留作明確的後續選擇。

# kernel 任務包設計提案

## 1. 審查範圍與證據界線

本報告依據 `/home/guanyu/projs/aos` 的工作目錄內容，審查時 HEAD 為：

`6daebe2ef8227021745def649f4e3d86a3a8038c`

已閱讀指定筆記、核心契約與實作、三個現有任務包，以及 proto7-1 的 kernel 與相關探針；由主線加五條平行審查線交叉檢查。

本次只有讀檔與唯讀搜尋，**沒有修改檔案、執行測試、啟動原型、commit 或 push**。以下清楚區分：

- **現況**：目前文件或程式可以直接支持的行為。
- **靜態推論**：由執行順序推導的崩潰或競爭情境，本次未動態重現。
- **提案**：建議新增的契約，不代表已實作，也不代表使用者已選定方向。

有兩份文件需要保留其歷史定位：

1. `core-slimming.md` §10 明言「只出方案」，其中 `kernel-core`、`supervise`、`schedule`、`account` 與安裝器是分類及切分草案。不能將整張表視為第一版必須實現的功能。  
   證據：[proto7-2/notes/core-slimming.md](../../core-slimming.md):324、[同檔](../../core-slimming.md):381。

2. `layer-interfaces.md` 是針對較早 commit 的調查紀錄，並非目前全部行為的規格。它指出的介面風險應回到現行程式核對，不能直接沿用舊欄位、舊命令或舊缺口。  
   證據：[proto7-2/notes/layer-interfaces.md](../../layer-interfaces.md):5。

目前未找到 kernel 實作、`pack.json` 或 `aos7-pack`。本次使用的唯讀搜尋可重查：

```sh
rg --files --hidden --no-ignore proto7-2 |
  rg '(^|/)(pack\.json|aos7-pack|aos7-kernel|aos7_kernel[^/]*)$'
```

此搜尋無匹配；既有模組入口也仍將包格式、安裝器列為未完成事項。  
證據：[proto7-2/modules/README.md](../../../modules/README.md):22。

## 2. 設計定位：kernel 管決策接續，規則管用途

### 2.1 建議的職責卡

| 項目 | kernel-core 第一版提案 |
|---|---|
| 職責 | 接收自己的 tock、讀取指定來源、建立帶版本的快照、呼叫規則、驗證決定、保存意圖、送出控制、核對結果、崩潰後接續。 |
| 前置條件 | 普通 `keep` 任務、`max_live: 1`；固定設定與靜態 mounts；自己的 state 單一寫入者；每個受控槽有明確的單一控制者。 |
| 保證 | 未保存意圖前不送控制；恢復時保留原決定 ID 與原目標 run；讀取失敗不當成不存在；不把寫入成功當成動作完成。 |
| 明確不管 | 業務是否完成、任務是否「健康」、完整歷史、任意規則程式的隔離、跨檔交易、斷電持久性、多控制者仲裁、跨 node 重建後的身分接續。 |

這符合現行核心契約：kernel、agent 都只是任務；四類分類不增加 `tasks.json` 的任務種類，核心也沒有模組鉤子。  
證據：[proto7-2/notes/component-contracts.md](../../component-contracts.md):105、[同檔](../../component-contracts.md):121。

### 2.2 骨架與用途的依賴方向

建議分成：

- **`kernel-core`**：不知道「卡住」、「預算不足」、「agent 沒回信」的業務意義，只處理觀測、規則輸入輸出、意圖及控制結果。
- **規則／薄入口**：例如 supervise，負責定義何謂進度、多久算停滯、哪些任務可被控制。
- **現有任務包**：繼續自行執行；kernel 可以觀測其公開事實，不能接管其內部狀態。

依賴應由 supervise 指向 kernel-core；kernel-core 不反向匯入 supervise、budget 或 agent。第一版可先提供一個 supervise 範例，不急著宣稱已完成完整 supervisor 包。

這延續原筆記「依管的對象分類」的原則，也保留通用任務與 agent／LLM 任務的界線。  
證據：[proto7-2/notes/core-slimming.md](../../core-slimming.md):330、[同檔](../../core-slimming.md):353、[同檔](../../core-slimming.md):419。

## 3. 與核心的接點

### 3.1 檔案所有權

| 接點 | 第一版用法 | 不可混淆的界線 |
|---|---|---|
| 自己的環境變數、`tock.json` | 識別自己的 node／slot／run；觸發新一輪決策。 | 只收自己的有效通知；tock 只有最新一份，可能漏取樣。 |
| 成員的 `birth.json`、`exit.json`、回合摘要 | 取得被觀測任務的身分與核心發布的生命週期事實。 | 核心擁有的檔案只能讀；不能為了「修正觀測」寫回。 |
| 來源 `round.json` | 計算來源自身的時間進展。 | kernel 的回合不是成員的回合。 |
| 套件公開的 progress／結果／暫存器 | 按該套件契約解讀。 | 檔案存在不表示屬於目前 run，也不表示內容最新。 |
| 自己槽內的 state | 保存規則狀態、最後提交的 tock、待送意圖及結果。 | 正常同槽重起會保留；刪槽則不保證。 |
| 目標槽 `ctl.json` | 第一版只寫帶原始 `run` 的 kill。 | 是單一請求位置，不是佇列。 |
| 目標槽 `ctl-done.json` | 核對原請求及處理結果。 | 只保留最新回條，不能當永久去重資料庫。 |
| `tasks.json`、daemon ctl、動態 mount 請求 | 第一版執行期間不使用。 | 後续擴充時各自補契約及崩潰測試。 |

依據：[proto7-2/notes/component-contracts.md](../../component-contracts.md):25、[proto7-2/spec.md](../../../spec.md):185、[同檔](../../../spec.md):194、[同檔](../../../spec.md):237。

**可讀來源與可控制目標應是兩份設定。** 掛得到某個 node，只表示能依合作式約定存取；不能據此自動取得 kill 權限。核心目前不提供這種安全隔離或控制者仲裁。  
證據：[proto7-2/notes/component-contracts.md](../../component-contracts.md):101、[同檔](../../component-contracts.md):124。

### 3.2 快照必須保留身分、來源時鐘與未知

建議每個觀測項目至少保存：

| 欄位概念 | 用途 |
|---|---|
| 來源與範圍 | node、slot、檔案，以及它是 run 資料、槽內持續狀態，還是 job／budget 的持續資料。 |
| 身分 | run 資料必須攜帶、核對 run。 |
| 版本 | 來源宣告的 seq／rev，必要時附內容雜湊。 |
| 時間依據 | 來源 completed_tock；另外記錄 kernel 在哪個自己的回合讀到。 |
| 讀取狀態 | 有效、不存在、格式不合、I/O 未知；不能全部折成空物件。 |
| 原始依據 | 足以解釋此次判斷的值及相關欄位。 |

有三個特別重要的限制：

1. **跨檔快照不是原子快照。** 讀到舊 progress、新 birth，必須辨識成不一致，不能湊成「新 run 沒進度」。對 run 資料可在讀前後核對身分，但仍不宣稱跨檔交易。核心自己也以 run 排除舊的生命週期檔。  
   證據：[proto7-2/spec.md](../../../spec.md):204。

2. **不是所有資料都隨程序 run 作廢。** step frame、budget 帳本、adapt 的接續狀態有自己的生命週期；不能看到寫入者重起，就把持續資料全部當成過期。  
   證據：[proto7-2/packs/step/spec.md](../../../packs/step/spec.md):9、[proto7-2/packs/budget/spec.md](../../../packs/budget/spec.md):99、[proto7-2/packs/adapt/README.md](../../../packs/adapt/README.md):27。

3. **快照及 dry-run 不得呼叫會修復程序的判定路徑。** 現行 `judge_resolved()` 會進入 `resolve()`，可能收程序並寫 `exit.json`；它不是唯讀查詢。`judge()` 才明文不做破壞性動作。第一版以公開事實檔為主；若共用判定函式，必須保留其 `UNKNOWN`、`SUSPECT`、`LIVE + unsure`。  
   證據：[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):73、[同檔](../../../lib/aos7_task.py):118、[同檔](../../../lib/aos7_task.py):158。

### 3.3 tock 是通知，不是所有同層任務完成的屏障

核心會先寫本回合摘要，再通知任務；但不能因此推論 adapt 或其他 keep 已處理同一份 tock。核心通知後仍有完成回合的收尾步驟。  
證據：[proto7-2/lib/aos7_tock.py](../../../lib/aos7_tock.py):96、[proto7-2/packs/adapt/README.md](../../../packs/adapt/README.md):35。

第一版應接受：

- 自己的 tock 跳號時，處理最新觀測，不補造漏掉的事件。
- 相同 tock 重送，不重複提交新決定。
- 來源年齡採來源 completed_tock；可沿用既有包的「回合關閉取 round，尚開啟取 round−1」定義。
- 來源時鐘停止時，不能用 kernel 自己比較快的回合數將來源判成逾期。

依據：[proto7-2/packs/adapt/spec.md](../../../packs/adapt/spec.md):48、[proto7-2/notes/layer-interfaces/03-kernel-agent.md](../../layer-interfaces/03-kernel-agent.md):24。

## 4. 與 step、budget、adapt 的關係

### 4.1 各包保留自己的權威狀態

| 包 | 它已經負責的事 | kernel 可以做的事 | kernel 不應代做的事 |
|---|---|---|---|
| step | job frame、程式位置、request／attempt、派出 once、接受結果、未知時的重送。 | 觀測工作進度及停住原因；控制被明確允許的外層任務。 | 改 frame／result、替 step 判定完成、自行 restart step 子工作。 |
| budget | grant、預留、結算、帳本、以 K 去重、入口與後端結果。 | 讀取公開狀態；另做上層准入規則。 | 由 exit、kill、step fail 推論退款；直接修帳或補 usage。 |
| adapt | 固定依據的投影、basis、來源年齡、耐性、誤差界、unknown／absent。 | 消費其窄格式，依規則要求檢查 freshness。 | 重做轉換、把 `state: ok` 直接當成來源現在健康。 |

證據：[proto7-2/packs/step/README.md](../../../packs/step/README.md):19、[proto7-2/packs/budget/README.md](../../../packs/budget/README.md):30、[proto7-2/packs/adapt/README.md](../../../packs/adapt/README.md):19。

原草案把 `account` 列為依賴 kernel-core，但目前 budget 已是能獨立運作的包。建議讓現況成立：**裝 kernel 不必連帶裝三包，裝三包也不必先裝 kernel。** 不為了符合較早分類表而加上反向依賴。  
證據：[proto7-2/notes/core-slimming.md](../../core-slimming.md):388、[proto7-2/packs/budget/README.md](../../../packs/budget/README.md):7、[proto7-2/packs/adapt/README.md](../../../packs/adapt/README.md):36。

### 4.2 step 的「結果未知」不等於命令回傳 unknown

這是第一版整合時最容易誤判的接點。

budget 在 reserve／入口／settle 尚無終局時，可能正常退出並回傳 **退出碼 3**。若命令由 `aos7-step-result` 包裝，包裝程式會產出一份正式結果：

- `code: 3`
- `ok: false`

step 收到這份有效結果，會走 `fail` 分支；沒有 `fail` 就停在 `halted/failed`。這和「程序遭殺、沒有結果檔」進入 `on_unknown: resend` 是兩條不同路徑。

因此，kernel 不能看到 budget 的 unknown，就宣稱 step 一定會自動重送；也不能替它把失敗結果改成缺失結果。若未來要讓兩種 unknown 統一，需要另定 wrapper／step 的映射契約。

證據：[proto7-2/packs/budget/spec.md](../../../packs/budget/spec.md):74、[proto7-2/packs/step/aos7_step_result.py](../../../packs/step/aos7_step_result.py):64、[proto7-2/packs/step/aos7_step.py](../../../packs/step/aos7_step.py):447。

另一个界線是：step 的 request 在重送時維持、attempt 改變；budget 的計費 K 不應跟著 attempt 或程序 run 改變。kernel 的控制 ID 也不能拿來取代它們。  
證據：[proto7-2/packs/step/spec.md](../../../packs/step/spec.md):54、[proto7-2/packs/budget/README.md](../../../packs/budget/README.md):36。

### 4.3 pause 不能充當硬性預算閘門

核心 pause 停止新回合，現有任務程序仍可能繼續跑。budget 的 ledger 以輪詢處理 inbox，並不是每次都等 tock 才處理；來源時鐘凍結也不等於帳本停止受理。

因此，未來若加上「預算不足就 pause node」的規則，它只能是協作政策，不能宣稱已阻止所有後端效果。硬性受理界線仍在 budget／gateway。  
證據：[proto7-2/spec.md](../../../spec.md):63、[proto7-2/packs/budget/aos7_budget.py](../../../packs/budget/aos7_budget.py):355。

### 4.4 adapt 的 `ok` 需要連同依據讀

adapt 在來源暫時未知時，可能在耐性內保留舊值；來源時鐘停止時，也不一定立刻翻成 unknown。`my_round` 前進只能證明 adapt 又處理了一輪，不能證明來源資料變新。

kernel 規則若要據此 kill，必須明定可接受的 `basis`、來源狀態、年齡與是否保留舊值，不能只查 `state == ok`。同一 tock 若 kernel 比 adapt 早醒，讀到上一版也是合法情況。

證據：[proto7-2/packs/adapt/README.md](../../../packs/adapt/README.md):22、[同檔](../../../packs/adapt/README.md):32、[proto7-2/packs/adapt/spec.md](../../../packs/adapt/spec.md):95。

## 5. 規則介面與最小 supervise 範例

### 5.1 第一版規則介面

預設建議先使用**已知、可測試的純函式規則**，輸入輸出限於 JSON 可表示的資料。

輸入包含：

- 協定版本、設定雜湊。
- 本次觸發的 tock。
- 帶來源身分、版本、時鐘與讀取狀態的快照。
- 該規則先前已提交的狀態。

輸出包含：

- 下一份規則狀態。
- 候選動作清單。
- 每個動作的理由與依據版本。

骨架先驗證整份輸出，再提交任何新動作。未知 op、錯誤型別、未授權目標、不合法 run 一律拒絕；同目標的重複候選合併，矛盾候選拒絕，不能靠規則排列順序偷偷決定優先權。

這是將原筆記的「純函式或程式」介面縮成第一版可驗證的子集。外部程式規則之後再補 timeout、輸出大小、退出碼、子程序回收及版本協定。純函式第一版也不能宣稱能隔離無限迴圈的任意外掛。

依據：[proto7-2/notes/core-slimming.md](../../core-slimming.md):347。

### 5.2 supervise 範例只監督「實際工作進度」

建議先用自願加入協定的示範 worker，提供：

| 欄位 | 建議語意 |
|---|---|
| `v` | progress 協定版本。 |
| `run` | 此份進度所屬 run。 |
| `seq` | 同一 run 內單調增加，只有完成並保存一個工作單位才增加。 |
| `round` | 寫出時的來源回合，供診斷；不單獨代表工作完成。 |

停滯規則的預設：

1. 首次有效 progress 建立基準，不立即控制。
2. `seq` 增加時更新基準。
3. 以來源 completed_tock 計算「距最後一次有效進度的回合數」。
4. 達設定的 `no_progress_rounds`，才產生綁定當時 run 的候選 kill。
5. 來源未知、run 不合、seq 倒退時，不產生新 kill；恢復有效觀測後重新建立測量基準。
6. 尚未收到第一份有效 progress，不納入停滯判斷；啟動逾時另列後續功能。

第五點避免將「第 10 回合後讀不到，第 100 回合恢復」誤算成已證實停滯 90 回合。

這個範例只適用於預期持續產出工作進度的任務。等待外部事件、正常閒置、等待 LLM 的任務需要各自的規則，不能直接套用。

proto7-1 已記錄「progress 含 round、心跳持續更新，但工作沒進度」的問題；舊規則比較整份 progress，不能原樣沿用。  
證據：[proto7-1/notes/problems-kernel.md](../../../../proto7-1/notes/problems-kernel.md):48、[proto7-1/lib/aos7_kernel_rules.py](../../../../proto7-1/lib/aos7_kernel_rules.py):119。

## 6. 崩潰語意：先保存意圖，再送控制

### 6.1 單一 state 是恢復依據

建議自己的 state 至少包含：

| 資料 | 用途 |
|---|---|
| schema、設定雜湊、固定 instance ID | 拒絕不相容狀態或錯誤部署接續。 |
| state revision、決定序號 | 辨识提交順序；決定 ID 在 kernel 重起後維持。 |
| 最後提交的 tock | 避免同回合重複建立新決定。 |
| 各規則狀態 | 保存進度基準、已處理版本等。 |
| pending intents | 完整保存原目標、原 run、op、ID、理由與依據。 |
| 必要的最近結果／去重水位 | 避免同一目標 run 再度觸發；不累積永久歷史。 |

規則新狀態、tock 水位及新 pending 必須在**同一次 state rename** 中提交。人看的最近決策檔可以另寫，但只是衍生輸出，不得成為第二份恢復真相。

proto7-1 的順序是先 apply 控制，再寫紀錄及 state；控制寫入失敗後也可能繼續保存新的規則狀態。這會留下「已做未記」與「未做卻已記」兩種空窗，不適合作為新包的恢復契約。  
證據：[proto7-1/lib/aos7_kernel.py](../../../../proto7-1/lib/aos7_kernel.py):125。

### 6.2 建議執行順序

1. 讀取並驗證設定、state。
2. **先核對既有 pending**；重起後第一次恢復不必等待新的 tock。
3. 收到新的有效 tock 後取快照、執行規則。
4. 驗證整份候選；提交前再次核對重要依據及目標身分。
5. 原子保存規則狀態、tock 水位、完整意圖。
6. 送出原意圖的控制請求。
7. 之後依回條、目標生命週期證據更新結果。

state 寫入失敗時，記憶體中的已處理水位也不能先前進。既有 pending 的交付不再依賴重新執行規則；否則規則保存了「已發出」後，崩潰接續可能永遠漏送。

設定雜湊不合時，預設停止新的提交與送出、保留 pending，待恢復相同設定或走明確遷移程序。這不代表先前已送到核心的控制被取消。

### 6.3 kill 的最小交付契約

請求包含 `id`、`op: kill`、原始整數 `run`、`by`、`why`。

目前 `aos7-ctl kill` 沒有 `--id`，`task_ctl()` 也不接收這個欄位；但是合法 kill JSON 可以攜帶 `id`，核心會把原請求一起寫入回條。控制包的 restart 也已使用此形式。因此第一版可以由包內薄轉接層寫入，不必修改核心。

**ID 只負責關聯；防止誤殺下一個 run 的保護來自 `run`。**

證據：[proto7-2/modules/tools/aos7_ctl.py](../../../modules/tools/aos7_ctl.py):98、[同檔](../../../modules/tools/aos7_ctl.py):169、[proto7-2/modules/control/aos7_control.py](../../../modules/control/aos7_control.py):131、[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):240。

核對回條時要比：

- 目標位置。
- 原請求的 `id`、`op`、`run`。
- 若宣告成功，再核對 `result.ok` 及 `result.run`。

不能只比 `result.run`：原請求指定 A，但槽已是 B 時，拒絕回條中的 `result.run` 可能是 B。  
證據：[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):233。

每個槽最多一份 pending；其他目標可繼續處理。遇到不同 ID 的現存 `ctl.json` 應報控制衝突，不能覆蓋。也不能在上一份請求仍待核心清除時，把該位置當成已空出的佇列格。

### 6.4 結果分類

| 狀態概念 | 可以宣稱的事 |
|---|---|
| 已保存意圖 | 本地已承諾接續這件控制。 |
| 已送出 | 請求檔已寫入；尚不能宣稱核心處理。 |
| 已確認處理成功 | 收到匹配且成功的 kill 回條；核心確認目標程序已不在。 |
| 觀測到目標已結束 | 有生命週期證據；不宣稱是 kernel 造成。 |
| 已被後續 run 取代 | 原目標已不是現在的 run；絕不改成 kill 新 run。 |
| 拒絕 | 核心回覆明確拒絕。 |
| 未知 | 讀寫失敗、證據不足或處理結果尚不能確定。 |

kill 成功不等於工作成功，也不等於已重起或重起後健康。keep 是否再起，還取決於表項、enabled、時間範圍、pause 等條件。  
證據：[proto7-2/spec.md](../../../spec.md):131、[同檔](../../../spec.md):243。

### 6.5 崩潰點與恢復

| 崩潰位置／情況 | 建議恢復行為 |
|---|---|
| state 提交前 | 不應有遠端控制；下次重新觀測。 |
| 意圖已保存、ctl 尚未寫 | 以原 ID、原 run 補送。 |
| ctl 已寫、本地尚未記送出 | 先找匹配回條及現存請求；需要補送時仍用原 ID、原 run。 |
| 核心已處理、kernel 尚未保存結果 | 由回條／生命週期證據恢復，不建立新決定。 |
| 目標已換 run | 將舊意圖記為被取代，不追著新 run 送。 |
| 目標或回條讀不到 | 保留 pending，不當成空槽或成功。 |
| 目標 node pause | pending 等待；其他目標繼續；不擅自 resume。 |
| state 缺失、毀損或 schema 不合 | 停止控制，不能自動換成空 state。 |
| 核心處理前槽狀態未知 | 核心保留請求，等待重看。 |
| kill 嘗試後回 `unknown` | 請求可能已消耗；依匹配回條記未知，不能誤認仍在佇列。 |

最後兩列是不同情況。現行核心在槽判定未知時提早返回；實際 kill 回 `ok:false/unknown` 則仍寫回條並刪請求。  
證據：[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):230、[同檔](../../../lib/aos7_task.py):238、[proto7-2/modules/diag/README.md](../../../modules/diag/README.md):63。

### 6.6 必須明說的政策：提交後是否仍可撤回

預設建議採：

> **提交後不自動撤回的 kill 意圖；始終釘在原 run。**

理由是「保存意圖後、送出前」與「送出後、保存送出狀態前」可能留下完全相同的本地狀態。ctl 不見也可能是已被消耗，不能證明從未送出。

因此，即使同一 run 後來恢復進度，已提交的 kill 仍可能稍後生效。提交前重查 progress 只能縮小空窗，無法把「條件仍成立」與核心執行 kill 綁成一個原子動作。

若使用者希望恢復進度就撤回，應先選擇僅觀測模式，或另設 freshness／取消契約。單純停止重送只能叫「停止重送、交付結果未知」，不能回報「已取消」。

這是本提案需要使用者選擇的實際行為，不應藏在重試實作裡。其依據是單檔請求、非交易式回條及先回條後刪請求的現況。  
證據：[proto7-2/notes/component-contracts.md](../../component-contracts.md):94、[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):240。

### 6.7 保存範圍

建議提供明確的初始化步驟：

- 初始化只建立尚未存在的 kernel state。
- 執行模式不自動初始化。
- 已存在但壞掉、讀不到或不相容的 state，不可被初始化覆蓋。
- dry-run 的模擬決定不放入可交付 pending；切換正式模式不能把舊模擬意圖送出去。

這類「初始化與恢復分開」已有 budget 可參考。  
證據：[proto7-2/packs/budget/spec.md](../../../packs/budget/spec.md):46。

同槽正常重起保留自己的 state，但移除任務後整槽可能被刪除。第一版的接續保證應止於**同一部署、同一 node 生命週期、同一槽**；卸載、重建 node、重設時鐘要建立新部署識別。daemon 的 gen 不能替代這個識別。  
證據：[proto7-2/spec.md](../../../spec.md):195、[同檔](../../../spec.md):205、[同檔](../../../spec.md):209。

另外，現行 `write_json()` 使用暫存檔及 `os.replace()`，沒有 fsync。這份提案可談程序崩潰接續，不能據此承諾斷電時跨檔寫入順序仍成立。  
證據：[proto7-2/lib/aos7_fs.py](../../../lib/aos7_fs.py):119、[proto7-2/notes/component-contracts.md](../../component-contracts.md):51。

## 7. proto7-1 探針帶來的限制與可沿用部分

### 7.1 可沿用：分層、來源時鐘、提案與驗證分離

舊探針有價值的是問題切分與可重現情境，不是整套程式直接搬移。

| 探針／紀錄 | 對新包的啟示 |
|---|---|
| kernel 問題筆記 | 停滯必須用成員時鐘；pause 會讓控制等待；progress 心跳不等於工作進展。 |
| supervisor | 核心 keep 的補起與 supervisor 的退避政策可能互相競爭；真正要管 backoff，必須先決定誰是啟動者。 |
| sched | pause 請求被接受不代表立即停止；不能宣稱硬性排程或資源上限。 |
| hsched | 慢速提案者可與確定性執行器分開；提案需要版本、效期及驗證。 |
| gang | 合作式 prepare／commit 不等於核心提供原子成組啟動。 |

證據：[proto7-1/notes/problems-kernel.md](../../../../proto7-1/notes/problems-kernel.md):14、[同檔](../../../../proto7-1/notes/problems-kernel.md):28、[proto7-1/probes/supervisor/README.md](../../../../proto7-1/probes/supervisor/README.md):28、[proto7-1/probes/sched/README.md](../../../../proto7-1/probes/sched/README.md):23、[proto7-1/probes/hsched/README.md](../../../../proto7-1/probes/hsched/README.md):41、[proto7-2/spec.md](../../../spec.md):294。

### 7.2 靜態反例：有票不等於已交付

hsched 的 dispatch 先寫公開 ticket，再寫 worker 的 assignment。恢復邏輯看到 ticket 後，可以將工作標成 dispatched，但該段恢復邏輯沒有補出缺少的 assignment。

**靜態推論**：若恰好死在兩次寫入之間，就可能有票、有 dispatched 狀態，worker 卻收不到工作。本次沒有執行此切點測試。

這支持 kernel-core 的一項必要契約：**保存意圖後，要能補做實際交付；不能只把 state 改成「已派出」。**

證據：[proto7-1/probes/hsched/kernel.py](../../../../proto7-1/probes/hsched/kernel.py):72、[同檔](../../../../proto7-1/probes/hsched/kernel.py):161、[proto7-1/probes/hsched/worker.py](../../../../proto7-1/probes/hsched/worker.py):47。

### 7.3 完整 restart 不宜直接列入最小版

目前控制包 `restart()` 的目標是「呼叫當下槽裡的 run」。它沒有接收 durable `expected_run`；去重證據主要在待執行 once 或目前 birth 的 `req_id`。

**靜態推論**：舊 kernel 意圖原本針對 N；崩潰很久後，槽已進到 N+2，舊 `req_id` 證據也離開目前 birth。此時單純以舊 ID 再呼叫 restart，可能操作當下的 N+2。

kernel 在呼叫前自己比一次 run，仍有檢查與使用之間的競爭空窗。只加 tasks 鎖內檢查也不能直接宣稱完整解決，因為 tick 的規劃與實際起槽不是全部留在 tasks 鎖內。

證據：[proto7-2/modules/control/aos7_control.py](../../../modules/control/aos7_control.py):71、[同檔](../../../modules/control/aos7_control.py):85、[同檔](../../../modules/control/aos7_control.py):107、[proto7-2/lib/aos7_tick.py](../../../lib/aos7_tick.py):312、[同檔](../../../lib/aos7_tick.py):339。

因此第一版若只做 kill，應誠實稱為 kill。依 keep 補起是既有核心行為，不能包裝成完整 restart 保證。

## 8. 最小第一版切法與 aos7-pack 的界線

### 8.1 建議交付物

| 交付物 | 最小內容 |
|---|---|
| 契約文件 | 四欄契約卡、檔案所有權、規則 schema、身分與時鐘、意圖提交／恢復語意。 |
| kernel-core 執行骨架 | 普通 keep；固定設定、靜態 mounts、快照、純函式規則、state、pending、kill 轉接。 |
| 操作入口 | 明確初始化、執行、讀取狀態；dry-run 不產生可交付意圖。 |
| supervise 範例 | 兩個自願提供 progress 的 worker：一個前進、一個停滯；可切換來源與 kernel 的快慢回合。 |
| 測試 | 規則、快照、崩潰切點、控制回條、跨包界線、有限長跑。 |
| 使用說明 | 手動放設定及登記普通 tasks 項目；說清楚生效與接續邊界。 |

建議第一版暫不納入：

- runtime 改 tasks、restart／reload。
- daemon pause／resume／wake／rounds。
- 動態 ask_mounts。
- supervisor 樹、退避、排程、gang、多控制者 arbiter。
- LLM 規則、agent 名冊與通訊。
- 通用安裝器。

這是對 `core-slimming.md:339–347` 原骨架清單的**刻意縮限提案**，不是說那些功能不值得做。先讓「觀測—決定—提交—交付—恢復」有一條完整可驗證的路徑，再逐項擴大動作集合。

### 8.2 aos7-pack 可以分開完成

第一版 kernel 可以和現有三包一樣，以普通任務方式使用，不必等待安裝器。

但若之後落實「複製到 `<node>/packs/<包>`」，需要先處理兩件事：

1. **可搬移的 runtime 依賴。** 現有三包會由 `__file__` 的父目錄推導 repo 的 `lib`／`modules/tools`；測試也使用原 repo 的入口。直接複製 package 資料夾，不等於可獨立安裝。必須選共享 runtime，或明確打包依賴及版本。  
   證據：[proto7-2/packs/step/aos7_step.py](../../../packs/step/aos7_step.py):21、[proto7-2/packs/budget/aos7_budget.py](../../../packs/budget/aos7_budget.py):20、[proto7-2/packs/adapt/aos7_adapt.py](../../../packs/adapt/aos7_adapt.py):19。

2. **安裝、卸載的中斷語意。** 安裝宜先完成檔案與設定，再以鎖保護的一次表更新發布任務；重跑不能重複加項。卸載不能只刪表項就立即刪程式及 state，因為表項移除不代表既有程序已停止，pending 也可能已送出。budget 更有獨立退役與保存契約。  
   證據：[proto7-2/notes/core-slimming.md](../../core-slimming.md):406、[proto7-2/spec.md](../../../spec.md):205、[proto7-2/packs/budget/spec.md](../../../packs/budget/spec.md):101。

這些是安裝器自己的設計題，不應偷偷塞進 kernel 主迴圈。

## 9. 驗收測試清單

**以下全部是提議的驗收項目，本次未執行。** 每個崩潰測試都應確認切點確實命中，並檢查檔案、run 與效果，不能只看程式最後退出 0。

### 9.1 骨架與觀測

| ID | 情境 | 必須斷言 |
|---|---|---|
| K01 | 最小安裝與啟動 | 核心無修改、沒有新任務 kind／hook；不裝 step／budget／adapt 也能跑。 |
| K02 | dry-run，含疑似 lost 槽 | 不改目標檔、不收程序；模擬意圖不能於重起或切模式後交付。 |
| K03 | 規則輸出錯型別、未知 op、例外、矛盾動作 | 不部分送出；留下可診斷原因。 |
| K04 | tock 提早到、重送、舊 run、跳號 | 同一有效回合不重複提交；舊 run 不採用；漏回合不補造事件。 |
| K05 | 讀取期間 birth 換 run | 舊 progress 不會套在新 run；無法形成一致依據時不產生 kill。 |
| K06 | 檔案缺失、壞 JSON、FIFO、讀取錯誤、LIVE unsure | 不合併成空槽；不以未知推出「已死」。 |
| K07 | kernel 快／慢、來源 pause | 停滯只按來源回合老化；來源鐘停止不增加停滯年齡。 |
| K08 | 只有 progress 的 round／時間更新 | 未完成工作不算進度；seq 真增加才重設基準。 |
| K09 | 未知區間後恢復、首次 progress、run 更換 | 未知間隔不算已證實停滯；首次樣本及新 run 重新建立基準。 |

來源依據：[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):73、[proto7-2/modules/tools/aos7_taskside.py](../../../modules/tools/aos7_taskside.py):30、[proto7-2/packs/adapt/spec.md](../../../packs/adapt/spec.md):48、[proto7-1/notes/problems-kernel.md](../../../../proto7-1/notes/problems-kernel.md):48。

### 9.2 state、交付與崩潰

| ID | 情境 | 必須斷言 |
|---|---|---|
| K10 | state 缺失、毀損、不相容、設定變更 | run 不自動初始化；pending 不消失；沒有新控制。 |
| K11 | state rename 前殺 kernel | 遠端沒有新 ctl；記憶體水位不造成下一代漏處理。 |
| K12 | state 提交後、ctl 前殺 kernel | 不等新 tock 也能接續；ID、run、payload 不變。 |
| K13 | ctl 後、本地送出紀錄前殺 kernel | 不产生新 ID；不誤殺後續 run。 |
| K14 | 核心處理後、kernel 保存結果前崩潰 | 從匹配證據恢復；不再建立同一 run 的新決定。 |
| K15 | 回條 ID／op／原請求 run 不符 | 不認領；特別測 `result.run` 是新 run 的拒絕回條。 |
| K16 | 寫 ctl 失敗、讀回條失敗 | 保留 pending，沒有虛報成功。 |
| K17 | 目標先後處於 UNKNOWN、kill 回 unknown | 區分「請求仍留著」與「已消耗但結果未知」。 |
| K18 | 送出前或處理前目標換 run | 舊意圖不能轉向新 run。 |
| K19 | 意圖提交後，同一 run 恢復進度 | 按選定契約驗收可能晚到的 kill；不得假稱已撤回。 |
| K20 | 目標 pause、其他目標正常 | pending 不阻塞全部成員；不自動 resume。 |
| K21 | 同槽存在其他 ID 請求、規則重複候選 | 不覆蓋 чуж有請求；同槽至多一份 pending。 |
| K22 | kill 成功但 keep disabled／過期／表不合 | 不回報 restart 成功或健康。 |
| K23 | 正常同槽重起、刪槽後重建 | 前者接續；後者依明確初始化邊界處理，不能冒認舊部署。 |
| K24 | 至少 300 回合，多次 kernel 重起 | state 大小按目標／規則／在途數量成長，不累積每個歷史 run；檢查內容大小及效果數。 |

來源依據：[proto7-2/lib/aos7_task.py](../../../lib/aos7_task.py):209、[proto7-2/spec.md](../../../spec.md):195、[proto7-2/spec.md](../../../spec.md):243、[proto7-2/lib/aos7_fs.py](../../../lib/aos7_fs.py):119。

### 9.3 與現有包的整合

| ID | 情境 | 必須斷言 |
|---|---|---|
| I01 | kernel 被殺，三包繼續跑 | 三包沒有因 kernel 消失而失去必要服務。 |
| I02 | step interpreter 重起、已有子工作仍在 | kernel 不另派工作、不改 request／attempt、不製造第二個結果寫入者。 |
| I03 | budget wrapper 在後端效果後遭殺，step 重送 | 同 K、不同 attempt，後端效果與扣帳不重複。 |
| I04 | budget 正常回退出碼 3，wrapper 成功發布結果 | step 走既有 fail／halted 路徑；不能誤判成缺結果的 `on_unknown`；預留不被 kernel 退款。 |
| I05 | step close、之後開新 instance | 舊帳不因 close 消失；新 instance 的交易識別符合既有契約。 |
| I06 | budget node pause，但 ledger 程序仍在 | 測出實際可處理請求的行為；不以 pause 作硬性效果上限斷言。 |
| I07 | adapt 保留舊 ok、來源停鐘、my_round 前進 | kernel 保留 basis／freshness 差異，不把舊資料當新證據。 |
| I08 | 同一 tock，kernel 比 adapt 先醒 | 可讀上一版，但不能標成已取得本回合新來源。 |
| I09 | 包的寫入程序換 run，持續資料仍有效 | run 層資料與 job／budget／slot 持續資料依各自契約判定。 |

可沿用的測試材料：

- step 崩潰及結果缺失：[proto7-2/packs/step/tests/test_step.py](../../../packs/step/tests/test_step.py):372。
- budget＋step 重送及一次效果：[proto7-2/packs/budget/tests/test_budget_step.py](../../../packs/budget/tests/test_budget_step.py):161。
- budget＋step close／新 instance：[同檔](../../../packs/budget/tests/test_budget_step.py):82。
- adapt 快慢、pause 與接續：[proto7-2/packs/adapt/tests/test_adapt_flow.py](../../../packs/adapt/tests/test_adapt_flow.py):117、[同檔](../../../packs/adapt/tests/test_adapt_flow.py):316。

I04 應補為明確整合案例；不能用「wrapper 被 SIGKILL，沒有結果」的既有測試代替。

### 9.4 擴充功能的進入條件

| 後續功能 | 納入前必須補的驗收 |
|---|---|
| restart／reload | 舊意圖 N、目前 N+2、去重證據已離開 birth；以及 tick 規劃與起槽之間的競爭。 |
| tasks 編輯 | 保存意圖後崩潰、once 已消耗後重試，不重複追加或重跑。 |
| daemon 控制 | 接受與生效分開；pause／resume owner、控制順序、daemon 重起後 `rounds` 的保存界線。 |
| 動態 mounts | 請求／連結／birth 各切點崩潰；新 run 掛載重建。 |
| 多控制者 | 請求覆蓋、所有權交接、舊控制者恢復後不得重新接管。 |
| 外部／LLM 規則 | 超時、錯型別、過期 epoch／版本、崩潰、子程序回收、過期提案拒絕。 |
| aos7-pack | 脫離原 repo 路徑可執行；重複安裝；半途崩潰；未停止程序及未完成 pending 的卸載。 |

依據：[proto7-2/lib/aos7_daemon.py](../../../lib/aos7_daemon.py):530、[proto7-2/spec.md](../../../spec.md):185、[proto7-2/modules/control/aos7_control.py](../../../modules/control/aos7_control.py):71。

未來實作後，可使用既有 runner；新測試檔名須全域唯一。以下是**未來驗收指令，本次未執行**：

```sh
python3 proto7-2/tests/run_all.py packs/kernel-core/tests
python3 proto7-2/tests/run_all.py
```

runner 會自動收集 `packs/*/tests`。  
證據：[proto7-2/tests/run_all.py](../../../tests/run_all.py):2、[同檔](../../../tests/run_all.py):22。

## 10. 待決題與預設建議

下列預設供使用者評估，尚未代表已選定產品方向。

| 待決題 | 預設建議 | 選其他方向的影響 |
|---|---|---|
| 第一版先證明什麼價值？ | kernel 骨架＋明確加入協定的進度監督範例，只提供觀測與 run-bound kill。 | 若先做排程、完整 supervisor 或資源分配，必須先決定啟動者、控制者與准入權威。 |
| 規則先用純函式，還是外部程式？ | 已知純函式、JSON 型別邊界，由薄入口注入。 | 外部程式需要額外程序生命週期與失敗協定；任意外掛需要隔離承諾。 |
| 同一 run 恢復進度後，已提交 kill 是否仍可生效？ | 提交後不自動撤回，始終釘原 run；狀態明示可能延後生效。 | 若不可接受，第一版採僅觀測，或先設計 freshness／取消協定；停止重送不足以證明取消。 |
| 接續保證要跨多大的生命週期？ | 同部署、同 node、同槽；初始化與執行分開。 | 若要跨卸載、刪槽或 node 重建，需要槽外持續儲存與不會重用的部署／node 身分。 |
| 誰可以控制同一槽？ | 明確列出單一控制者；觀測權與控制權分開。 | 多控制者要先有仲裁及交接協定，不能靠不同 `by` 或檔名解決槽 ctl 互蓋。 |
| 三個現有包要不要改成 kernel 插件？ | 保持獨立；kernel 只消費其公開契約，必要整合另做薄層。 | 若要接管重試、帳本或 freshness，等於重劃權威狀態，需另案設計及遷移。 |
| aos7-pack 是否綁第一版一起做？ | 分開；kernel 先採既有手動任務登記方式。 | 若第一版就要求可攜安裝，須一併決定 runtime 打包、版本依賴、安裝發布與卸載保存契約。 |