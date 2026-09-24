## 1. 總評

三份目前不能定稿：`waits` 同時充當門與唯一工作索引，正常開門就會失去收件依據。
主要缺口是跨格、跨崩潰的批次紀錄，以及記憶／ack／state 之間的恢復規則。
下層接法大致正確，但 `Removed`、boot 清理、inst 重新序列化有實質錯誤。
同步工具、agent 託管方式、llm.json 放置仍留給使用者裁決；以下不代決。
本次全程唯讀，對照三份草稿、下層定稿、前輪報告、舊版與相關實作，未改檔。

## 2. A：上下層契約

**X-1｜`aos_client` 的送件、收件、ack 必須明確拆開。〔要修〕**

[放單與收回流程](../../spec/aos-agent.md:71) 沒有明確區分三個名字：

- kernel 行程名：`params.name=N`。
- 運輸檔名：`K/requests/N.json`，決定回音檔名。
- ack 的目標：`params.name="N.json"`，包含副檔名。

只填 `params.name`，不保證 client 取的運輸檔名也是 N。現行 `aos_client.call()` 又會同步等待、預設自動 ack，不能直接套進逐格流程；同池只有一顆工作 cpu 時，同步等子工作還可能卡住。

建議直接補：

> 送件使用 `submit(K,"add",params,name=N+".json")`，其中 `params.name=N`；送件格不等待工作完成。後續格先查原單、再查同名回音；結果持久保存後才呼叫 `ack(K,N+".json")`。ack 是沒有 id 的 notification，使用全新 `ack-*.json` 檔名。

`AlreadyExists`、`-32602` 也是後來收到的回音，不能與本地「放檔失敗」混成同一件事。

**X-2｜`Removed` 不是「沒跑」，也不是完成屏障。〔擋〕**

[工具結果表](../../spec/aos-agent.md:97) 把非 `Interrupted` 的 error 都列為「跑不起來」。但 [kernel 的 rm 契約](../../spec/kernel.md:191) 明定：running once 被 rm，當下就回 `Removed`，底層工作仍可能繼續。

應把 `Removed` 分出來：結果可能已生效、工作未必停止；不能據此立即清 inst／in／out。`Stopping` 才是 queued once 尚未派送就被取消，兩者不可合併。競態見 C-5。

**X-3｜`load_obj()` 回傳物件不能直接寫成 inst。〔擋〕**

[工具 inst 生成步驟](../../spec/aos-agent.md:85) 說解成字面 inst 再寫檔，但 [舊工具格式](../../../proto5.1/spec/tool-cpu.md) 已明示：它是內部結構，含串流的 `path/append/mkdir`、`cwd_mkdir`、`envs_clear`，不是原始 inst JSON。

直接 dump 會讓 aos-exec 拒絕串流物件；只抽 path 則丟掉選項。

> `_meta` 解析後須重新編碼成合法 inst JSON，保留 append／mkdir／inherit／merge／clear 等選項；不得直接序列化 `load_obj()` 的內部回傳物件。

**X-4｜路徑中心與環境來源沒有完全對齊。〔要修〕**

[agent 的 `_meta` 規則](../../spec/agent.md:99) 一概說中心是 agent 家，與 [inst-posix §3.1](../../spec/inst-posix.md:92) 不同：agent 家是 base；先解 cwd，之後串流與一般 `$ref` 以 cwd 為中心。

> 工具 inst 的 base 是 agent 家；cwd 及其他欄位依 inst-posix §3.1 解析。agent 補入的 stdin／stdout 使用工作區的絕對路徑；argv 的一般參數不擅自當成路徑改寫。

另一個缺口是 [think 的 timeout 來源](../../spec/aos-agent.md:72)：agent 要讀 llm.json 的 timeout，但 [llm.json 會整份展開](../../spec/aos-llm.md:30)，API key 可能只存在 llm 工作 cpu。若共用完整 loader，agent 送件前就可能因缺金鑰失敗。須定義 agent 可取得 timeout 的來源／解析方式，不能假設兩個池環境相同。

**X-5｜「孤兒回音到 boot 才清」沒有下層依據。〔要修〕**

[aos-agent 自癒段](../../spec/aos-agent.md:109) 的敘述錯誤。[kernel boot](../../spec/kernel.md:306) 保留在途帳本與 pending，沒有清 `K/responses/` 的步驟。

引用的 `cpu §10-4` 只講名字不重用，不是孤兒回收政策。

> 未 ack 的回音不會因 boot 消失；失去工作名的 agent 無法自動完成收件與清理。

**X-6｜`kind=aos` 沒有草稿想取的「一行原因」。〔要修〕**

[工具結果表](../../spec/aos-agent.md:97) 要輸出原因，但 [exec result](../../spec/cpu.md:182) 只有 `code/kind/timed_out/stopped/ms`；只有 RPC error 才有 `message`。

最小修法是固定文字：

> `kind=aos` 回「工具 xxx 無法執行（kind=aos, code=1）」；詳細診斷查執行日誌。

若要把詳細原因交給模型，須另外定義診斷保存與讀取來源，不能假設 response 帶著它。

**X-7｜工作名、原子寫入有兩個衝突。〔要修〕**

[工作名](../../spec/aos-agent.md:21) 直接以資料夾名開頭；家叫 `ack-bob`／`stop-bob` 時，会撞 [管理 request 前綴](../../spec/cpu.md:207)。加固定安全前綴即可，例如 `work-<agent>-<ns>-<pid>`。

[「程式寫檔一律 tmp 再 rename」](../../spec/agent.md:42) 也過度概括：

> 自家 JSON 用 tmp＋rename；投到 K/requests 的 request／ack 用 cpu §3.1 的唯一 tmp＋link。工具 stdout 是重導向產物，不承諾原子發布，須依執行結果決定何時讀取。

**X-8｜託管範例缺 K；預設 llm pool 不保證存在。〔要修〕**

[託管範例](../../spec/aos-agent.md:129) 少了位置參數：

```sh
aos-kernel add /abs/K /abs/agent-bob/tick.json --name agent-bob
```

這只能標成「若採反覆行程託管」的範例，不能把待裁決假設写成既定事實。

`llm.pool:"llm"` 與 kernel 示範設定相符，但 `init` 不保證建出 llm 池；須明寫首次使用前配置該池，否則會回 `-32602`。

**核對無誤的部分：** `cpu §4.1／§3.3`、`kernel §1.1／§2` 引用正確；`target/name/once/pool/timeout_ms` 鍵名正確；絕對 inst target 不附 `args` 正確；回音與 stdout 分開正確；think 的成功四條件正確；工具將 `Interrupted`／`stopped:true` 視為結果不明、不自行重跑，方向正確。

## 3. B：崩潰窗口與競態

**C-1｜開門就刪掉唯一工作索引。嚴重度：擋。**

- **時序：** 回音到 → [§2 劃掉 waits 並寫回](../../spec/aos-agent.md:35) → §3 又只靠 waits 判在途。
- **後果：** 正常流程即可被當成「沒有在途」而重送；N、stdout、ack 對象都失去。即使先把 N 暫存記憶體，清門後崩潰仍無法恢復。反過來把門留到 ack 後，回音消失又會永久關門。
- **建議：** 門與工作身分分開。用一份持久批次紀錄保存 N、call 對應及收件進度；已接回、待 ack 清理的工作不再受回音存在性門阻擋。

**C-2｜記憶落盤後，自癒不足以完成 ack 與結清。嚴重度：擋。**

- **時序：** [記憶 → ack → 清檔 → state](../../spec/aos-agent.md:78)，任一縫崩潰。
- **後果：** 普通 assistant 回答沒有 think 自癒分支；帶 tool_calls 的分支沒寫補 ack、清理、errors 歸零。act 的「尾巴不是 assistant」又包含下一列「整批 tool 已接回」，優先序不明。部分 ack／清檔後，單靠內容與 waits 更難復原。
- **建議：** 明訂未接回、已接回待結清、已結清的恢復行為，並能辨識記憶已包含本批。整批 tool 要核對 call 數量及 id 順序；普通 assistant 也必須可恢復。不要只用「尾巴長得像」判完成。

**C-3｜放單後、加 waits 前崩潰，可能重複工具副作用。嚴重度：要修。**

- **時序：** [寫 inst／arguments → 部分 add 已送 → waits 未寫就崩](../../spec/aos-agent.md:85) → 下次換 N 整批再送。
- **後果：** 工具可能執行兩次，第一批回音與工作檔失聯；boot 不會回收。只寫完 inst 尚未放單就崩，也會留下孤檔。
- **建議：** 先保存批次身分，再規定對帳／補送。注意 kernel once 的原單可先消失、回音稍後才到，不能照搬「兩檔皆無＝未送」的 cpu 推論。若仍接受重送，須把「可能重複副作用、孤檔不自動回收」列為取捨，不能當成下層已承擔。

**C-4｜未送出的 call 沒有跨格紀錄。嚴重度：擋。**

- **時序：** [工具不存在／`_meta` 解失敗／本地送件失敗](../../spec/aos-agent.md:84)，其他 call 成功送出 → waits 只存已送路徑 → 退出。
- **後果：** 下格不知道各 call 是沒開始、已送，還是本地失敗，也取不回原失敗原因。全部未送時，空 `all` 更無法代表已完成的批次。
- **建議：** 每個 call 持久保存「request 名」或「本地終局結果」；全部本地失敗可直接接回整批 tool 訊息。`_meta` 解析錯要明定歸屬，不能漏掉。

**C-5｜收到取消回音就清檔，會與仍在跑的工作競態。嚴重度：擋。**

- **時序：** 工作 running → rm → `Removed` 到 → [agent ack 並刪 inst／in／out](../../spec/aos-agent.md:101) → 工作仍讀寫。
- **後果：** 尚未開啟的輸入可能被刪；仍寫入的 stdout 被 unlink；模型還被告知「跑不起來」。think 也受同一清理問題影響。
- **建議：** 清理前須有工作結束的依據；`Removed` 本身不夠。拿不到依據就保留並明訂後續清理責任。一般清檔應可重做，已不存在視為完成；結果與必要恢復憑據保存後才清。

**C-6｜consume 已 rename、門未落盤，會重新關死。嚴重度：要修。**

- **時序：** [continue.json rename 成 .done](../../spec/aos-agent.md:35) → waits 尚未寫回就崩。
- **後果：** 下次仍等已被搬走的原檔；使用者明明繼續過，卻要再 touch。多檔 consume 中途崩也一樣。
- **建議：** 補可恢復的消費進度或本次 token 身分；不能把任意舊 `.done` 當本次完成證據。既有 `continue.json` 會直接開啟新暫停門，也應明說是否接受。

**C-7｜連敗計數可能漏算，壞模型輸出又繞過三敗。嚴重度：要修。**

- **時序：** [失敗 → errors 加一 → ack → state 未寫就崩](../../spec/aos-agent.md:52)；或 exec 成功但 message 無效，退 1、不 ack。
- **後果：** 前者失敗證據消失、計數沒留下；後者不算引擎失敗，可能改由外層 kernel 的 `bad_after` 停派，而非「三敗 touch 繼續」。
- **建議：** errors 與本回音已處理的憑據一起落盤，再 ack；重讀不得重算。明定壞模型輸出屬引擎失敗還是人工修復錯誤，以及恢復方式。

**C-8｜idle 接輸入有重複與停滯兩個窗口。嚴重度：要修。**

- **時序：** [接記憶 → rename 輸入 → state 改 think](../../spec/aos-agent.md:47)。
- **後果：** 接完未 rename 就崩，下次重接；rename 完未改 state 就崩，idle 看不到輸入，已有的新記憶可能一直不被回答。
- **建議：** 補輸入接收憑據／恢复規則，多輸入檔也要涵蓋。若接受此限制，須明列，不能用「I/O 中斷下次自癒」概括。

**C-9｜stop／boot 的等待與保留界線沒說清楚。嚴重度：要修。**

- **時序：** 已送 once → [kernel stopping](../../spec/kernel.md:238) → queued 回 `Stopping`，running 收完；agent 的反覆行程不再派送。
- **後果：** agent 可能要等下次 boot 才接回；停止後送出的 request／ack 也留待 boot。這不是遺失，但 timeout 並不限制這段等待。
- **建議：** 明寫保留在途紀錄與工作檔，boot 後接續；`Stopping` 表示未派送即取消；`timeout_ms` 只限制工作執行，不含排隊、停機與等待回音。不得因等太久自行判成未送而重投。

**C-10｜同家雙跑可列保證外，但操作限制要完整。嚴重度：可先放。**

- **時序：** [同家用兩個行程名登記，或排程中手動再跑](../../spec/aos-agent.md:129) → 各讀舊 state／history → 交錯覆寫。
- **後果：** 唯一工作名保不住共享記憶與 waits，仍會丟更新、重送工具。外部同時往 waits 加條目也可能被覆蓋。
- **建議：** 明寫同一 agent 家只由一個驅動者執行；kernel 按行程名排程，不按 agent 家去重；外部修改 state 也需避開讀改寫期間。此輪不必因此新增鎖。

## 4. C：刪除能力與舊版自癒

| 編號 | 刪除項 | 判斷 |
|---|---|---|
| **K-1** | `engine.cpu`／`tool_cpu` | **可砍。** kernel＋pool 已接手路由；舊 cpu 身分驗證、私有佇列與收屍機制不必搬回。 |
| **K-2** | `_run`／同步工具 | **留待使用者裁決。** 損失不只 tick 延遲：舊純同步批次依序跑，新版只保證結果接回順序，另改變執行環境與 kernel 依賴。應完整列出代價；若採新版，有先後依賴的操作須合成一工具或分輪呼叫。 |
| **K-3** | waits `mtime`／`any` | **內建流程可砍，通用能力確有縮減。** 固定檔更新、任一來源到達不能用 exists＋all 等價表示。新版仍允許外部門，所以「agent 只等回音」不是完整理由；目前無證據要求恢復。 |
| **K-4** | `ask-result.json`／`tool-results/` | **檔名可砍，持久定位不能砍。** 舊固定路徑讓 waits 消失後仍找得到結果；新唯一檔名避免遲到結果混用，卻需要持久當批索引接手。見 C-1。 |
| **K-5** | 結果先讀驗、再劃門 | **必要，須保留。** 舊版明定模型／整批工具結果先驗，壞資料不消掉收件依據；新版先清 waits 才讀 stdout，失去此保證。 |
| **K-6** | 記憶尾端自癒細則 | **不能只留「自癒」兩字。** 舊版有正規化結果與尾端相等、tool 筆數與 call id 順序吻合、errors 歸零及剩餘結果封存。新版須接手精確判定與 ack／清理，並補普通 assistant 分支。見 C-2。 |
| **K-7** | 本地失敗結果保存 | **必要，漏接。** 舊版 `_meta` 解失敗也產生該 call 的結果，其他照送；新版跨格後沒有保存失敗原因的地方。見 C-4。 |
| **K-8** | 舊 tool stdout 封裝 | **改檔案可行，解碼規則要搬。** 舊 [tool-cpu](../../../proto5.1/spec/tool-cpu.md) 明定 UTF-8、非法位元組替換與逾時部分輸出；新版「整份文字」不足，還須定未建立輸出檔與讀取失敗如何區分。 |

上述舊自癒依據在 `HEAD~1:proto5/spec/aos-agent.md` 的第 58–59、73–79 行。

**K-9｜合併 aos-llm-ask 與 HTTP，也改掉了請求快照邊界。**

舊版送出 agent 已組好的 body；新版[只傳 agent 路徑](../../spec/aos-agent.md:65)，等 llm 工作執行時才讀檔。

因此排隊期間修改人格、history、工具或模型設定，會改變已送出的問；info 裡的 `$env` 又可能在 agent cpu 與 llm cpu 解成不同值。這不要求恢復 llm cpu 種類，但須明定「送件時」或「執行時」讀取，以及兩端需一致的路徑／模型解析契約。

## 5. D：清楚度與 KISS

**R-1｜三份一句話應反映跨格與待裁決邊界。**

建議改成：

> **aos-llm-call：**讀 agent 的模型輸入與連線設定，呼叫一次模型，把一則 assistant message 印到 stdout。

> **agent：**agent 資料夾保存設定、對話記憶與跨次執行的進度，讓 aos-agent 每次接著做。

> **aos-agent：**每次只送出或接回一批工作，更新記憶與進度後退出；未收到結果時保留進度，留待下次呼叫。

「像純函式」不精確，它依賴檔案、環境、HTTP；「agent 自己就是反覆行程」則應標為待裁決假設。

**R-2｜名詞表缺的是身分與生命週期，不是更多比喻。**

[目前名詞表](../../spec/aos-agent.md:12) 建議補：

> 工作名 N 是 kernel 行程名；request 檔名 N.json 決定回音位置。工具批次包含同一則 assistant 的全部 tool_calls，每個 call 都須有可恢復的處理結果。

> 回音含 result 或 error；有回音不保證程式成功，取消回音也不一律保證程式已停止。

pool 的「派去 llm 那顆」改成「派往 pool 標籤相符的工作 cpu」，避免誤讀成固定單顆。

**R-3｜waits 格式有直接矛盾。**

[欄位表](../../spec/agent.md:115) 允許單條，[§4.2](../../spec/agent.md:134) 卻要求原始值必為陣列。

若維持欄位表，直接寫：

> waits 可為字面單條或字面陣列；讀入時正規化為條目列表，程式寫回時統一使用陣列。省略或空陣列表示沒有等待條件。

另須定 `all:[]`、consume 資料夾／多檔時處理哪些檔；這些都會直接影響 C-4、C-6。

**R-4｜llm.json 與 message 驗證還不足以直接實作。**

[llm 設定](../../spec/aos-llm.md:25) 有 `_metainfo` 範例，卻沒寫是否必填、如何驗；`api_key` 沒完整型別；正整數也應明說 bool 不算。`ConfigInvalid` 並非舊 llm-cpu 設定錯誤的原名，舊文用的是 `EngineInvalid`。

建議至少補：

> api_key 可省、null 或字串；timeout_ms 為正整數，bool 不算。明訂 llm_config 的身分與版本驗證，以及設定讀取、JSON 語法、指示詞錯誤各用何種代號。

[模型輸出](../../spec/aos-llm.md:51) 也不能只檢查 message 存在：

> 成功輸出必須是 role=assistant 的訊息；有 tool_calls 時，逐項驗證 id、type、function.name 與字串 arguments，並定義空陣列與重複 id 的處理。

否則 agent.md 的一般訊息驗證可能接受 user／tool，或讓畸形 call 到 act 才炸。

**R-5｜四個工作資料夾不是主要複雜度，可先留。**

真正昂貴的是四處檔案沒有共同的批次定位與清理依據。此輪先修紀錄與生命週期，不必為了 KISS 同時搬目錄。

可補：

> 工具 arguments 保存原始字串；stdout 保存任意文字，不要求 JSON。輸出檔副檔名使用 `.txt` 或 `.stdout`，讀取採 UTF-8 並替換非法位元組。

之後若要簡化，可評估單一 `work/N/` 收整批 inst／in／out；那只是布局選擇，不能取代恢復紀錄。

**R-6｜新版不能依賴「跟第 1 版一樣」才能實作。**

[人格／記憶段](../../spec/agent.md:82) 把兩個小節合成標題，卻被別處當獨立 §3.2 引用；舊版又預計被取代。應拆回獨立小節，直接保留必要驗證條款，去掉「一字不改」等版本依賴。

同理，「讀驗錯什麼都不寫」須限定：

> 起始設定讀驗失敗不寫檔；送件或收件開始後的錯誤依恢復流程處理，不能保證本格尚未產生任何變更。

## 6. 定稿前必改

1. **C-1、C-4、K-4：**補持久當批紀錄，分開 waits 與工作身分，保存未送 call 的結果。
2. **C-2、K-5、K-6：**定義結果讀驗、記憶提交、補 ack、清理與 state 的恢復流程及判定優先序。
3. **C-3、X-5：**補送件中斷的對帳／重送政策，刪掉 boot 自動清孤兒回音的錯誤承諾。
4. **X-2、C-5：**分清 `Removed`、`Stopping`、`Interrupted`、`stopped`，訂工作檔安全清理條件。
5. **C-6、C-8：**補 consume 與 input rename 前後的恢復規則。
6. **C-7：**讓連敗計數可恢復且不重算；明定壞模型輸出的錯誤歸屬。
7. **X-1、X-7：**補完整 client 送收契約、三種名字、ack 形狀、安全前綴與 link 發布規則。
8. **X-3、X-4：**保證 `_meta` 轉成合法 inst，保留選項並正確解析 cwd／路徑。
9. **X-4、K-9：**定 timeout 的解析責任、兩端環境一致性與請求快照邊界。
10. **X-6、K-8、R-3、R-4：**補齊 waits、設定、message、工具文字輸出與錯誤原因的最小資料契約。
11. **C-9、X-8：**補 stop／boot 接續、timeout 範圍、合法登記範例及 llm pool 前置設定。
12. **K-2、R-1、R-6：**將三項待裁決選擇與既定契約分開，完整列同步工具刪除代價，移除實作必須回翻舊版的敘述。