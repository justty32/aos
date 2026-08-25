# agent loop 的實作架構與基礎 `aos core` 功能
← [workshop](../README.md)｜前一場：[四個懸而未決的設計選擇](four-open-choices-tradeoffs.md)

| | |
|---|---|
| **主題** | agent loop 真的要做出來的話，架構長什麼樣、需要哪些基礎 `aos core` 功能 |
| **開場** | 2026-08-25 |
| **已跑輪數** | R1（各自發想）、R2（收攏成方向） |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與〈四個懸而未決的設計選擇〉是同一批人**（同一批 codex session 續下來），所以他們帶著那場的完整脈絡。兩場紀錄互相連結。 |

## 先讀這段（500 字懶人包）

**只能先做三樣時，四位選得完全相同：**

1. `publish`：原子發布檔案／目錄，是底座。
2. `deliver`：驗證、去重後投進 queue，是現有缺口。
3. `effect`（含 resolve）：記外呼的 done／unknown，避免盲目重付費。

三者可以疊起來：`deliver` 是「驗證＋key＋queue」的 publish；`effect` 也用 publish 記狀態，完成後
可再 deliver 下一回合。prompt 組裝、回覆解析、final／budget 仍留給腳本與 adapter，不進 core。

串行 loop 已夠用；還缺的是平行工具的 join，以及 crash 後對齊 event、cursor、receipt 與下一次
投遞的通用 reconcile。這兩項能否不帶 agent 語意，尚未收成 core 功能。

---

## R1 想法池

本場接續[前一場](four-open-choices-tradeoffs.md)的同一批四位參與者；他們帶著 World、kernel、
子行程拓樸與身分仍未拍板的完整脈絡。任務書明講：**不要假裝前四題已定案**，agent loop 的
形狀必須能容納那些選擇繼續懸著。

使用者開題的原話是：

> **討論關於 agent loop 在我們做實現的話，大概架構會長怎麼樣，
> 會需要啥樣的基礎 aos core 功能。**

roadmap T5 給的做法是先不加新的 C++，只用 `.aos/inst.json` 與幾支腳本跑出完整 loop；這一輪
因此不是先設計 `aos agent`，而是觀察腳本重複踩到哪一條協定：

> **這一階段的產出不是程式，是規格：腳本裡哪些地方重複、哪些地方難寫，
> 就是 `aos agent` 該收掉的東西。**

任務書另點名一個 agent loop 開始前就存在的缺口：三步交接協定已有彙整／取件／釋放，
**只有投遞仍是口頭約定，沒有函式。**

### 成形的方向

#### `aos core` 該收掉什麼

這一塊是本輪最集中的產出。**四位獨立地都先提出投遞，再提出一個可記錄 `unknown` 的外部效果
封裝**；差別主要在命名與它現在該公開多少。

| 子命令／函式（候選形狀，未拍板） | 簽名 | 誰提的 | 為什麼腳本自己做不好 |
|---|---|---|---|
| **原子投遞 `deliver`** | CLI：`aos core deliver --to BASE [--key K] [--durable] -`；lib：`deliver_instruction(rootfd, base, bytes, opts) -> receipt` | **四位獨立地都提了**；工程師／架構師／開發者放在 `aos core`，研究人員寫成 `aos deliver` | 腳本很容易短寫、撞名、只寫半份或重送；共用原語可統一 schema／大小檢查、同目錄唯一 temp、write-all、可選 fsync 與 rename。架構師另要求同 key 同內容回 Already、異內容回 Conflict |
| **外部效果 `effect run`／`invoke`／`capture`** | CLI：`aos core effect run --dir CALL --key K -- CMD...`；概念上的 lib：先落 request／key，再執行，最後原子提交 stdout、stderr、exit 與狀態 | **四位獨立地都提了**；命名分別是 capture、invoke、effect run、effect | LLM 或工具可能已被遠端接受、甚至已付費，本機卻在結果落盤前 crash；普通 shell redirection 看不出「沒執行」與「執行了但沒記下」的差別，也無法安全決定是否重跑 |
| **狀態發布 `publish`** | 工程師：`publish(rootfd, path, bytes, opts)`；架構師：`aos core publish EVENT.d TEMPD`，以一次 rename 發布整組檔案 | 工程師、架構師兩位明確要求公開；研究人員與開發者把同一動作包在 effect 完成裡 | cursor、事件與 commit 若逐檔可見，讀者可能看見一半狀態；腳本必須反覆重寫 temp／rename／同步順序。尚未決定它應是公開原語，還是 `deliver`／`effect` 的內部零件 |
| **人工恢復 `effect recover`** | 架構師候選：`recover N --retry|--lost|--import FILE`；研究人員另用 `adopt`，工程師用 retry／abandon，開發者用 reconcile | 架構師明確給 CLI；其餘三位獨立地都要求同一組人工決策，但未都主張由 core 提供命令 | `unknown` 沒有普遍正確的自動答案；把 retry、放棄、匯入／採納既有結果做成明示動作，才不會由腳本偷偷重複付費或重做副作用 |

`deliver` 的細節，四位給出的邊界也一致：CLI 與 lib 必須共用同一份實作；輸入無效時**直接拒絕，
不要發布**；只有繞過 API、直接塞進信箱的壞檔，才由既有彙整者隔離成 `.bad`。大小上限與
`--durable` 要明講，不能由每支 agent 腳本自行猜測。

這使「投遞沒有實作」成為最小、最獨立的缺口：它不是 agent 專用功能，任何外部處理器要安全地
把 instruction 放進三步協定，都需要它。四位也都把 effect 做成通用外呼，而不是 `llm` 子命令，
因為同一個 crash 空窗也會出現在有副作用的工具。

#### agent loop 是磁碟上的耐久狀態機，不是新的 `exec` 模式

**四位獨立地都把 agent 定義成「world＋driver／adapter＋已提交歷史」**。`aos exec` 仍只執行
普通 instruction，不知道眼前這個世界是不是 agent；driver 看目前狀態，決定要不要投遞下一批。
有投遞就還有下一回合，**沒有投遞就是停止**，不需要常駐 loop process。

四份版面名稱不同，但職責可以對齊：

| 區域 | 放什麼 | 讀寫規則 |
|---|---|---|
| `.aos/` | 既有 kernel、`inst.json`、交接暫存與 `.runi` | 照既有回合協定走；agent 不另造一套 executor |
| `agent/` | `system.md`、config、driver cursor | cursor **只指向已提交紀錄**，不能先指到尚未發布的 response |
| `events/`／`history/`／`turns/` | prompt、模型 response、plan、commit 等回合紀錄 | 已提交後不可變；driver 下一次從 commits fold 出狀態，不讀半成品 |
| `effects/`／`calls/` | request、key、status、stdout／response、exit | 至少能表示 pending／done／unknown；done 可回放，unknown 不可無聲重跑 |
| `tools/` | tool request 與 result | tool 結果提交後，再投遞模型／driver 的下一回合 |

資深工程師用 `turns/N/{request,attempt,response,commit}.json`；資深架構師用不可變
`events/N.d` 與 `calls/N.d`；研究人員分成 history、turns、tools、effects；要接工具的開發者則把
events、effects、tools 都放在 `agent/` 下。**已成形的是提交邊界，不是資料夾名稱**：下一回合只
相信 commit／done，看不到 commit 就不把前一步當完成。

#### 一個完整循環怎麼走

四位的步驟可以疊成同一條回合鏈：

1. driver 從已提交的 events／turns 與 cursor 組出 prompt。
2. 以 effect 原語先發布 call request／key，再呼叫 LLM CLI。
3. 成功時原子發布 response／event 與 done；中斷時留下 unknown。
4. adapter 解析 response，透過 `deliver` 投遞工具 instructions。
5. 工具執行並提交 results，再由 driver 投遞下一次模型回合。
6. response 是 final、或 driver 沒有投遞任何 next instruction 時，loop 自然停止。

這條鏈不要求模型、工具與 driver 同一回合跑完，也不要求 core 理解 prompt、tool call 或 final。
core 只保證「已發布的是完整資料」「同一 key 不會悄悄變成另一份內容」「外呼結果不明時有狀態
可診斷」。

#### 斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once

**四位獨立地都指出同一個無法消除的空窗**：provider 已收到請求，但本機還沒把 response
發布，這時 crash，重開後無法只看本機判斷要不要再呼叫。工程師叫它「attempt 有、response 無」，
其餘三位都叫 `unknown`／ambiguous。

可安全自動恢復的情況只有兩種：provider 接受同一 idempotency key，重送不會再付一次；或
provider 能按 request ID 查回原結果。兩者都沒有時，四位都要求停住，讓人選 retry、abandon／
lost，或 import／adopt 一份外部找回的結果。**不得把 unknown 當作「沒跑過」自動重叫。**

資深工程師的一句話最直接：

> **rename 保發布，不保任意 LLM CLI 恰好付費一次。**

`.runi` 仍負責本地批次，commit／receipt／effect record 負責跨外呼的恢復；它們解的是不同層次。
優雅 Ctrl-C 可以讓 wrapper 主動寫出 unknown，但 hard kill 能否也自動留下可辨識狀態，仍是問題。

#### 前一場四個選擇可以繼續懸著

四位沒有把[前一場](four-open-choices-tradeoffs.md)的傾向偷寫成前提。共同的 agent 契約只要求
「有一個可推一步的 world」：

- World 尚未決定是否成為同 OS 行程 multiplex 的 handle；driver 可先呼叫普通 `aos exec <folder>`。
- kernel 可先視為該 world 執行時可取得；完整本地或分層來源不影響 events／effects 的提交語意。
- A 可把 queue／effects 放子世界，B 可放 root lane；工程師、架構師、研究人員明列兩種，開發者
  採子世界版本，但都沒有把其中一種寫成使用者已拍板。
- agent 的外部 handle 可用路徑、父域名稱＋generation 或日後其他身分；effect key／turn key 只需在
  當前契約下穩定，不必先假定 UUID。

所以「agent 是誰」也沒有被寫成一種新核心行程：工程師說它是 folder＋cursor＋turn log＋driver；
架構師說 world＋events＋queue；研究人員說 world＋kernel＋adapter；開發者說 world＋driver 狀態機。
**四位獨立地都把決定續跑／停止的權力放在 driver，不放在 `exec`。**

### 還在生長的想法

**CLI 名字與函式簽名尚未對齊。**`aos core deliver`、`aos deliver WORLD --to PATH`、
`deliver_instruction(path, json, opts)` 與 `deliver_at(rootfd, target, json, opt, receipt)` 表達的是同一
原語，但 world 從 cwd、路徑還是 root fd 傳入，正好受前一場 World 選擇影響。`key` 是否必填、
receipt 要含哪些欄位，也仍未成形。

**`publish` 要不要公開尚未成形。**工程師與架構師希望 cursor／整個 event directory 也能共用
原子發布；研究人員與開發者只要求 effect／deliver 內部正確發布。若公開，需說清它發布的是一個
檔、一個已寫好的 temp directory，還是含多檔的 transaction；若不公開，腳本更新 cursor 仍會
重寫一次同類協定。

**capture／invoke 屬於 core 還是 provider adapter，工程師明確標記沒把握。**core 可以通用地記
command、stdout、stderr、exit 與 unknown；但 request ID 查詢、provider idempotency key、回收
既有 response，必然依賴各家 CLI。邊界可能是 core 管效果日誌，adapter 管 provider 對帳。

**effect 是否包所有有副作用的 tool，還沒回答。**要接工具的開發者直接問這一題；若只包 LLM，
付費 API、寄信、部署等工具仍會落入同一個「做了但沒記下」空窗。若全部包，effect 就會成為比
agent 更底層、也更需要穩定的 core 契約。

**parallel tools 的 join 時機未定。**研究人員不確定 kernel 尾聲是否要等所有平行 tool；這會
決定 cursor／event commit 是每個結果各自推進，還是 barrier 後一次發布。

**耐久的承諾等級未定。**四位都提到檔案與目錄 fsync，但工程師與研究人員問的是要不要承諾
斷電後仍在；要接工具的開發者不確定 POSIX 目錄 fsync 是保證還是盡力。`--durable` 若存在，
規格必須把「只保證 rename 可見性」與「承諾 power-loss durability」分開。

### 大家問出來的問題

| 問題 | 誰問的 | 它卡住什麼 |
|---|---|---|
| hard kill 也要能自動恢復嗎，還是只保優雅 Ctrl-C？ | 資深工程師 | 決定 effect wrapper 是否要額外 supervisor／子行程協定；無論如何，遠端已收而本機未記仍只能是 unknown |
| unknown 預設停住，還是自動重付費？ | 資深架構師；其餘三位也各自要求 unknown 不自動重跑 | 決定最危險的預設行為，以及是否必須提供人工 recover |
| LLM CLI／provider 是否一定有 idempotency key 或 request ID 查詢？ | **四位都問到或標記不確定** | 沒有時不能自動把 unknown 恢復成 done，只能交給人 retry／adopt |
| `--durable` 是否承諾斷電後仍存在？目錄 fsync 是保證還是盡力？ | 工程師、研究人員、開發者 | 決定 deliver／publish 的跨平台契約重量 |
| capture／invoke 應在 core，還是 provider adapter？ | 工程師 | 決定 core API 是只記通用外部效果，還是也理解供應商對帳 |
| 有副作用的 tool 是否也必須走 effect？ | 要接工具的開發者 | 決定 unknown／冪等保護只涵蓋模型費用，還是涵蓋所有不可隨便重做的動作 |
| kernel 尾聲是否等待 parallel tools 全部 join？ | 研究人員 | 決定 event／cursor 的提交粒度與下一回合何時可見 |

### 明顯的坑

- **直接用 shell 把 JSON 寫進 `inst.tempd`，把投遞繼續留成口頭約定**。**四位獨立地都把這列為
  第一個該收進 core 的原語**：短寫、撞名、半寫、重送與耐久選項不該每支腳本各做一次。

- **先呼叫 LLM，成功後才開始記 call。**若付費後、落盤前 crash，本機連「曾經嘗試過」都不知道；
  四位都要求先發布 request／key，再啟動外呼。

- **把 `unknown` 自動當失敗重跑**。**四位獨立地都警告**：這可能重複付費，也可能把有副作用
  的工具做兩次。只有 provider 冪等或可查回結果時才有安全自動路徑。

- **把 rename 說成 exactly-once 或斷電耐久。**rename 只保本機發布時不露半份；遠端效果是否
  發生是另一個故障域，檔案／目錄是否 fsync 又是另一層承諾。

- **cursor 先前進，response／event 後提交。**四位版面雖不同，都要求 cursor 只指 commit；
  反過來會讓重啟後跳過一個其實沒有完整結果的回合。

- **core 開始理解 prompt、tool call、final 或 agent 身分**。**四位獨立地都把 core 邊界壓在
  deliver、publish、effect 與恢復狀態**；agent 語意留給 driver／adapter，否則 T5 還沒用腳本
  驗證重複點，C++ 介面就先定死。

- **把無效輸入發布成正常 instruction，再等 aggregate 收拾。**四位都要求 deliver 在 rename 前
  拒絕；`.bad` 是隔離繞過 API 的壞檔，不是正常錯誤處理路徑。

- **把前一場未拍板的 A／B、World、kernel 或 UUID 偷寫進 agent ABI。**前三位保留兩種 queue
  位置，開發者採子世界版本；四位都讓 driver 只依賴可推一步的 world，沒有把自己的版本寫成
  使用者已拍板。

---

## R2 想法池（收攏成方向）

這輪不再發散新介面，而是把 R1 的不同命名收成最少的功能組。使用者給的任務只有一句：

> **把 `aos core` 那塊收攏成方向。**

### 合併後的功能清單

四份清單最後只剩 **Publish、Deliver、Effect** 三個功能家族。下表的簽名是四位輸出的共同形狀，
仍是候選介面，不代表使用者已拍板名稱或參數。

| 名字（子命令／函式） | 簽名（候選共同形狀） | 它解決什麼 | 不做的話腳本要自己幹什麼 | 誰提的 |
|---|---|---|---|---|
| **Publish**（也涵蓋 commit／bundle） | CLI：`aos core publish TARGET TEMP [--durable]`；lib：`publish_at(rootfd, target, source, opts) -> receipt` | 用一次提交發布完整檔案或目錄；選擇是否連檔案與目錄一起 fsync，不讓 cursor／event 露出半套 | 每支腳本都要自造同目錄 temp、write-all、fsync、rename，還要避免 cursor 先前進；檔案與目錄又會各寫一套 | 工程師、架構師**兩位獨立地明確提出**；研究人員與開發者在 R2 也把它列進合併清單，但標明另外兩人的 Deliver／Effect 原本已內含同一動作 |
| **Deliver** | CLI：`aos core deliver --to BASE [--key K] [--durable] -`；lib：`deliver_at(rootfd, base, key, json, opts) -> receipt` | 驗 schema／大小，以 key 去重，再把完整 instruction 投入 queue；同一投遞可回 receipt | 腳本要自行配檔名、檢查 JSON、處理短寫、撞名、覆蓋與重送，仍可能把半份 payload 暴露給彙整者 | **四位獨立地都提了**；也是四位一致指出的現存投遞缺口 |
| **Effect**（合併 capture／invoke／run；含 resolve） | CLI：`aos core effect run CALL --key K -- CMD...`；`aos core effect resolve CALL retry\|lost\|abandon\|adopt [FILE]`；lib：`effect_run(...)`／`effect_resolve(...)` | 先記 request／key，再執行外呼；原子提交輸出與 done，crash 留 unknown；resolve 讓人明示重試、放棄或採納外部結果 | shell 只能看到「本機沒有結果」，分不出命令未跑與遠端已收費但尚未落盤；重開後只好盲目重跑，或各自發明 recover 檔案 | **四位獨立地都提了**；capture／invoke／effect 是同一件事，retry／lost／import／reconcile／adopt 被收進同一個 resolve 家族 |

Publish 的「檔案／目錄」仍有一個簽名差異：工程師、架構師、研究人員傳已寫好的 temp／source，
開發者的候選函式可直接收 payload。R2 只把共同提交邊界收成一項，沒有替使用者決定 public API
接收哪一種。

### 其實是同一件事的／可以疊在一起的

**四位各自都做出相同的合併**：

- R1 的 capture、invoke、effect run 都是 **Effect run**：先留下 request／key，再執行 command，
  最後把 stdout／stderr／exit 與狀態一起提交。
- retry、lost、abandon、import、reconcile、adopt 都是在回答 unknown，收成 **Effect resolve**；
  動詞仍可再減，但不再各長一個功能。
- 檔案 commit、目錄 bundle、temp＋rename 都是 **Publish**；差別只在 payload 是檔還是整個目錄。

三個功能也不是平行三座島，而是一條依賴鏈：

```text
Publish
├─ Deliver = schema／上限／key／queue ＋ Publish
└─ Effect  = request／done／unknown／resolve ＋ Publish
                                      └─ 完成的 result／receipt 可再交給 Deliver
```

資深工程師說「Publish 是底座，receipt 可再 Deliver」；資深架構師與研究人員都寫成
「deliver 管 queue、effect 管外呼」；要接工具的開發者則把三者縮成「publish 保完整、deliver 保
交接、effect 保外呼恢復」。**四位獨立地都把 agent 語意留在這條鏈外面。**

### 只能先做三樣的話

四位沒有各選一套不同的三樣；**四位都選中同樣三項，而且依賴順序也相同**：

| 順序 | 功能 | 入選情況 | 四位給的理由 |
|---|---|---|---|
| 1 | **Publish** | **4／4 都選** | 工程師、架構師、研究人員把它稱為 Deliver／Effect 的底座；開發者同樣按此依賴順序排列。先統一完整發布，後兩項才不必各自重寫 temp／fsync／rename |
| 2 | **Deliver** | **4／4 都選** | 這不是為 agent 新想出的功能，而是三步交接早就缺的投遞原語；不補，T5 每支 driver／adapter 都得自行投 queue，繼續承擔半寫、撞名與重送 |
| 3 | **Effect（含 resolve）** | **4／4 都選** | LLM 與其他外呼有付費／副作用，unknown 若沒有日誌與人工出口，crash 後只能盲目重做；resolve 被併進 Effect，沒有占第四個名額 |

這是 R2 最強的訊號：**Publish 的原始明確提案來自兩位，但到了「只能留三樣」時，四位都把它
選為第一層；Deliver 與 Effect 則從 R1 起就是四位獨立提出，R2 又被四位全數保留。**

### 不該進 `aos core` 的

四位收攏時也一起砍掉了 agent 專用政策：

| 留在腳本／adapter／module 的事 | 誰這樣劃界 | 為什麼不進 core |
|---|---|---|
| prompt 組裝、system message、對話裁切 | 工程師、架構師、研究人員；開發者也把組 prompt 留給 driver | 它們隨模型、上下文策略與產品需求變，不是原子交接問題 |
| response 解析、provider／tool schema、response→tool call | **四位獨立地都留在 adapter** | 每家 CLI 與 tool 格式不同；core 只需安全發布 bytes 與外呼狀態，不必理解內容 |
| final 判斷、stop／budget 政策 | **四位都排除** | 「何時不再投遞」是 driver 的 agent 政策；core 只看有沒有下一批 instruction |
| provider request ID 查詢與對帳 | 架構師、研究人員明確排除；工程師也不確定 capture 是否該含 provider adapter | 這是供應商能力；通用 Effect 只表示 unknown，adapter 才知道去哪裡查回結果 |

所以三個 core 原語合起來仍然**不會成為 `aos agent`**。T5 的腳本仍要組 prompt、呼叫正確 adapter、
解出 tool calls、判斷 final；這些不是漏收，而是四位刻意保留的可變部分。

### 還缺的一塊

只跑**串行**模型→工具→模型時，四位認為 Publish＋Deliver＋Effect 已足以支撐；剩下的 script
工作正是 T5 要觀察的 agent 語意。真正還沒被三項功能吃掉的 core 候選有兩塊：

1. **平行工具 join。**資深工程師提出 `effect_join(keys)`：沒有它，driver 必須掃多個 effect，
   判斷是否全 done／是否有 unknown，並防止尚未收齊就提交下一回合。研究人員也不確定 kernel
   尾聲是否要等 parallel tools；其餘兩位沒有把 join 選進前三項。
2. **turn reconcile／barrier。**要接工具的開發者指出，crash 後仍要對齊 event、cursor、receipts
   與 next delivery：哪一個已提交、哪一個只差同 key 補投。若沒有通用功能，driver 要逐一掃檔。
   他自己也標記不確定：若 reconcile 必須理解 turn／final，它就不再是通用 core 原語。

另有一個條件式缺口：研究人員指出，**若 Publish 不支援目錄**，event 與 cursor 仍可能分兩次
可見，腳本就得自行補交易。這不是第四項功能，而是 Publish 是否真的涵蓋 directory bundle 的
規格問題。

provider 對帳仍然得靠 adapter；三個 core 原語最多把狀態誠實地停在 unknown，不能替不同 LLM
CLI 查帳。這同樣是四位刻意留下的邊界，不是要求 core 補 provider-specific 功能。

### 大家問出來的問題

| 問題 | 誰問的 | 它卡住什麼 |
|---|---|---|
| key 由 caller 給還是 core 配？範圍是單 queue、單 world，還是跨 world？ | 工程師問是否跨 world；研究人員問誰配號；開發者問 key 範圍 | 決定去重邊界，也決定兩個世界用同一個 `K` 會不會誤認成同一次投遞／外呼 |
| receipt 的共同格式是什麼？ | 開發者直接問；工程師把 Effect receipt 接到 Deliver | 沒有共同欄位，Effect done 就不能在 crash 後可靠地判斷下一次 Deliver 是否已做 |
| Publish 是否公開？接受 temp/source 還是 payload？ | 開發者直接問；四位的 lib 簽名有兩種 | 決定它是穩定 API，還是 Deliver／Effect 的內部實作零件 |
| 目錄 Publish 是否只限同 filesystem？跨平台 no-replace 與目錄 fsync 保證到哪裡？ | 工程師、架構師、研究人員；架構師另標記跨平台保證不確定 | 決定 `--durable` 與 directory bundle 能承諾什麼，而不是只在目前機器可用 |
| Effect 是否包所有有副作用的命令？ | 架構師 | 若只包 LLM，其他付費 API／寫外部狀態仍有同一個 unknown 空窗 |
| join／reconcile 能否通用化而不理解 agent turn？ | 開發者直接標記不確定；工程師提出 `effect_join(keys)` | 決定它們是下一個 core 原語，還是應先留給 T5 腳本暴露共同形狀 |

### 明顯的坑

- **把三項當成三份互不相干的 temp／rename 實作**。**四位都把 Publish 放底座**；Deliver 與
  Effect 若各自複製一套，短寫、durable 與目錄發布語意很快就會分叉。

- **因為 Publish 被 4／4 選中，就倒推成四位都在 R1 獨立發明它。**原始來源是工程師、架構師
  兩位明確提出；研究人員、開發者在收攏輪把原先內含的動作升成共同底座。兩種訊號都重要，
  不能混寫。

- **把 Effect resolve 拆成第四套 recover 功能。**retry／lost／abandon／import／adopt 都是在處理
  同一個 unknown；分開會讓狀態字、key 與稽核紀錄各走各的。

- **Publish 只支援檔案，卻拿它承諾 event＋cursor 一起提交。**研究人員直接指出：沒有 directory
  publish，兩者仍會裂開可見，cursor 仍可能超前。

- **key 範圍未定就承諾冪等。**同 key 究竟在 BASE、world 還是全域內唯一，會直接改變 Already／
  Conflict 與 effect replay 的含義。

- **把 join／reconcile 急著收進 core，順手把 turn、tool、final 也帶進去。**工程師與開發者只
  提出缺口，沒有證明它能脫離 agent 語意；四位反而都明確排除 prompt、解析與停止政策。

- **三項做完就宣稱 agent loop 不再需要腳本。**四位都留下 driver／adapter；T5 原本就要用這些
  腳本找出下一批重複點，不能把「core 不該收」誤當成「工作已消失」。

---

## 續場資訊

與[前一場](four-open-choices-tradeoffs.md)相同的四個 codex session 仍保留 context，後續用同一批
接續。session id **只在 office Windows 那台機器有效**；`codex exec resume <id>` **不吃 `-s`
與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

---

## 轉交提案（未拍板，不自行改規格／roadmap）

R2 把候選功能收成三項，但**還沒有替使用者把它們排進 roadmap，也沒有定下公開 API**。等拍板
的是：

1. **是否按 Publish → Deliver → Effect 的順序成為前三項基礎 `aos core` 功能。**四位在「只能
   做三樣」時全部選中這三項；Publish 統一完整發布，Deliver 補現存投遞缺口，Effect＋resolve
   處理昂貴外呼的 done／unknown。要由使用者決定它們是在 T5 腳本之前先做，還是讓 T5 先用
   腳本驗證簽名後再排進 roadmap。

2. **Publish 是否公開，以及公開到哪一層。**需拍板只作 Deliver／Effect 的內部底座，還是提供
   `aos core publish`／`publish_at` 給 cursor、event、tool result 共用；同時決定接收 temp/source
   還是 payload、檔案與目錄是否都支援、是否限制同 filesystem，以及 `--durable` 對 fsync 與
   斷電的承諾。

3. **Deliver 的 key 與 receipt 契約。**需拍板 key 是否必填、由 caller 還是 core 產生、唯一範圍
   是 BASE／world／跨 world，以及 Already／Conflict 的判定；receipt 至少要讓 crash 後能辨認
   同一次投遞是否已發布。CLI namespace、payload 上限與 target 傳法也仍待定。

4. **Effect 的通用邊界與 resolve 動作。**需拍板它只包 LLM，還是包所有有副作用的 command；
   unknown 是否一律停住；人工動作收成 retry、lost／abandon、adopt／import 哪幾個狀態。provider
   查詢與 idempotency 仍由 adapter 處理，不放進 core。

5. **平行 join／turn reconcile 先留腳本，還是成為下一個 core 候選。**工程師只提出
   `effect_join(keys)`，開發者只指出 event／cursor／receipt／next delivery 的 barrier；兩人都還
   沒證明它們能完全脫離 agent 語意。可由使用者選擇現在排規格，或照 T5 原意先讓腳本硬做，等
   重複形狀出現再收。

6. **T5 的 agent 專用部分繼續留在腳本。**四位都排除 prompt、對話裁切、provider／tool parser、
   final、stop／budget；這些不是待加入 core 的漏項。前一場的 World、kernel、A／B／C、路徑或
   UUID 也仍未拍板，本場三項原語不替[前一場紀錄](four-open-choices-tradeoffs.md)作決定。
