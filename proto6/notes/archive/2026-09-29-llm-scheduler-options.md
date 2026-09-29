> 封存 2026-09-29：拍板題已由裁定第十三批回答。由 [縮短版](../2026-09-29-llm-scheduler-options.md) 取代（決定＋現況＋比較）。

# 不用 LiteLLM 的話：自製 LLM 排程器要多久、好壞在哪

← [筆記索引](../README.md)｜起因見[裁定紀錄「下班前的方向」](../verdicts/04-late-day-directions.md#下班前的方向同日systemd-那條已被第十四批取代litellm-那條已落進-spec)

2026-09-29 晚，使用者改口：LiteLLM 不進標準，只當可選的 endpoint；aos 自己的 LLM 排程器也要做成可選。本篇回答三件事：自己做要做哪些事、要花多久、跟 LiteLLM 比好壞在哪。最後列出要使用者拍板的題目。

**先講結論：**

- proto6 spec 其實已經把「自己排」寫得差不多了（藏 key、並行份額、每分鐘次數／token 窗口、429 冷卻、結果不明怎麼辦、用量收集都有條文）。缺的主要是**算錢的預算**、**多 endpoint 自動切換**、**串流**三塊。
- 真正的難處不是排程器本身，而是它**踩在還沒做的地基上**：proto6 目前沒有程式，daemon、tick、once 工作、git commit 流程都要先有，排程器才有地方跑。
- 估時（只算排程器，不含地基）：最小可用版約 **3～4 隊、1 天左右**；做滿約 **8～10 隊、2～3 天**。

## 一、自製排程器要做的事

下表逐項說：這件事是什麼、在 aos 裡怎麼做、spec 現在有沒有。「池 node」指專門管一組 endpoint 的 node，它的 tick 裡裝一支 `aos-llm` 任務，每次真的打 HTTP 時另開一件 once 工作（`aos-llm-call`）去等回應，不占住 tick。

| 要做的事 | 在 aos 裡怎麼做 | spec 現況 |
|---|---|---|
| 藏 key | key 檔放在 node 樹外，只有池 node 的 Linux 帳號讀得到；agent 用別的帳號，讀不到。請求裡、git 裡、日誌裡都不放 key | **已有**（S-301、P-405）。沒有 root helper、全部同一個帳號時藏不住，已接受 |
| 限流（並行數） | 父 kernel 給每個成員一個「同時最多幾件」的份額，池也有自己的總並行上限 | **已有**（P-505 `concurrent_requests`、P-811） |
| 限流（每分鐘次數／token） | 池 node 以固定時間窗口記數，滿了就等下個窗口；token 用「請求大小＋輸出上限」估算 | **已有**（P-811 `llm-limits.json`） |
| 共用限制不被繞過 | 同一個 provider 帳號的多個 endpoint 標同一個 `quota_scope`，一起記數、一起冷卻 | **已有**（S-301、P-811） |
| 用量記帳 | 每次 HTTP 的 usage 原樣存成檔案；kernel 用「用量收集」任務去讀成員記的帳，按 attempt 去重 | **已有**（P-407、P-502、P-810） |
| 預算（token 總量） | 父 kernel 給成員一個 token 額度，池或轉交 kernel 每次扣，扣完就等或寫待辦 | **缺**。現在配額只有並行數；S-203 只說「額度不足可等待或寫待辦」 |
| 預算（錢） | 要一張「每個模型每千 token 多少錢」的價格表，由 usage 換算成錢再扣 | **缺**。價格表要有人維護，這是 LiteLLM 最省事的地方 |
| 排隊與先後 | kernel 配發遞增序號，依序號排；可選一般／優先兩級，等太久提高機會 | 序號**已有**（S-204）；優先級只是建議預設 |
| 重試 | 429 最多重試幾次、照 `Retry-After` 或退避等；其他不明錯誤不自動重送 | **已有**（S-303、P-407） |
| 逾時與結果不明 | 請求帶 `timeout_ms`；送出後斷線就標 unknown，不再送第二次，占用留到定期清理 | **已有**（S-304、P-406） |
| 額度用完怎麼辦 | 等下一個窗口／等父層加額；卡太久寫一筆待辦到 `.aos/attention/` 給人看 | 原則**已有**（S-203），「卡多久算太久」沒定 |
| 多 endpoint 切換 | 一個池名底下掛多個 endpoint，一個 429 或掛掉就換下一個 | **缺**。現在一個池對一個 endpoint |
| 串流 | 邊生成邊把片段寫檔，agent 邊讀 | **刻意不做**（S-301 首版只收完整結果）。跟「tick 一格一格跑」的模型不合 |
| 轉交給上層或別的 kernel | 裝「LLM 轉交」任務，扣本層份額後再投給下一站 | **已有**（P-505 全管路線、P-808 路由表、P-809 轉交任務） |
| 查詢狀態 | `aos llm pool usage` 讀池的狀態檔，顯示在途、unknown、冷卻 | **已有**（P-812） |

小結：**要新加的 spec 只有三塊**：token／錢的預算、多 endpoint 切換、額度卡住多久寫待辦。串流建議繼續不做。

## 二、分檔設計

使用者要的是「排程器可選」。建議分三檔，但**agent 那邊看到的介面三檔完全一樣**：都是把 `llm.chat` 請求（同一種 JSON）投出去，下一格 tick 從自己的 `responses/` 收同一種結果。差別只在「請求投給誰」和「對面做多少事」。

| 檔 | 誰打 HTTP | key 在誰手上 | 限流／預算／排隊 | 適合 |
|---|---|---|---|---|
| **不管** | agent 自己登記一件 once 直接打 endpoint | agent 自己的帳號讀得到 | aos 都不管；只記自己的用量。429 照 S-303 自己退避，但不會跟別的 agent 一起冷卻 | 一個人、幾個 agent、本機模型伺服器或自己的 key |
| **交給 endpoint** | 池 node 代發 | 只有池 node 帳號讀得到 | aos 只藏 key、記用量、遇到 429 照對方說的時間等；限流和預算交給 endpoint 自己（LiteLLM 的虛擬 key、原廠後台的專案限額等） | 已經有 LiteLLM 或想靠原廠後台管額度 |
| **自己排** | 池 node 代發 | 只有池 node 帳號讀得到 | aos 全做：份額、窗口、冷卻、預算、排隊 | 很多 agent 共用少數 key，想讓額度跟 node 樹一起分 |

**怎麼切換：兩個欄位就夠。**

1. agent 設定的 `llm.target_node`：填 `null`＝「不管」檔，自己直接打；填某個 node id＝交給那個 node。這和工具的 `tools.target_node` 同一套想法（A-401）。
2. 池 node 的池設定每個池加一欄，例如 `"schedule": "endpoint"` 或 `"schedule": "aos"`。`endpoint` 時只做代發和記帳，`aos` 時才讀 `llm-limits.json` 做窗口與份額。

換檔不用改 agent 的程式，只改設定；已派出的請求照舊跑完，下一格 tick 起用新設定（A-102）。

**三檔共用同一支 `aos-llm-call`**：它只做「讀請求、打一次 HTTP、把結果和 usage 寫回」。「不管」檔由 agent 自己開它，另外兩檔由池 node 開它。所以做完最底層，三檔都能動；「自己排」只是在池 node 上多裝幾項任務。

**endpoint 可以是什麼**：任何講 OpenAI Chat Completions 格式的 HTTP 服務都行，包括 LiteLLM、原廠 API（OpenAI 等）、本機的 LM Studio／llama.cpp／vLLM。講別種格式的原廠（例如只給原生 API 的）要多寫一個轉換器，或前面擋一層相容的 endpoint。

## 三、工作量估計

**估計依據**：proto5 的實際紀錄。`aos-llm-call` 第一段（一次 HTTP、正規化、usage，附一百多條測試）是一隊一段做完；財務部的帳本＋預算（`aos team cost`）約半天；市場機制（五家公司、額度撥發、倒閉合併）約一天、中間修了好幾輪。以下「一隊」是一個 Opus 或 Sonnet 隊做一段、含測試，**不含**每段後的試玩與審查（每段再加約 1 小時）。

| 塊 | 內容 | 需要的檔 | 隊數 | 每隊時數 |
|---|---|---|---|---|
| 1 共同底 | `aos-llm-call`：一次 HTTP、正規化結果、usage、reason 分類；agent 端發請求、收結果、配對 | 三檔都要 | 1 Opus | 3～4 |
| 2 不管檔 | `llm.target_node=null`：agent 自己登記 once、自己記用量、自己退避 | 不管 | 1 Sonnet | 2 |
| 3 池 node 基本 | `aos-llm` 任務：收件、先 commit 再送、每次 HTTP 一件 once、結果投回、unknown 處理、key 放池帳號 | 交給 endpoint | 1 Opus | 4～6 |
| 4 限流 | 並行、次數／token 窗口、`quota_scope` 共同冷卻、429 重試排程、狀態檔與查詢 | 自己排 | 1 Opus | 4～6 |
| 5 份額與轉交 | 父給子的份額、LLM 轉交任務、用量收集任務、按 attempt 去重 | 自己排 | 1～2 Opus | 6～8 合計 |
| 6 預算 | token 額度（要先補 spec）；可選的價格表算錢；卡住寫待辦 | 自己排 | 1 Opus＋1 Sonnet | 3～4 |
| 7 多 endpoint 切換 | 一池多 endpoint、失敗換下一個（要先補 spec） | 自己排（可選） | 1 Opus | 3～4 |
| 8 串流 | 不建議做；真要做約一天，且要改 tick 模型 | — | — | — |

**做滿（塊 1～7）**：約 8～10 隊次、30～45 小時的隊伍工時。能並行的塊（2 跟 3、6 跟 7）一起派，牆上時間約 **2～3 天**。

**最小可用版**：塊 1＋2＋3，再加塊 4 裡的「並行上限＋429 共同冷卻」（先不做次數／token 窗口）。約 **3～4 隊、12～16 小時，牆上時間約 1 天**。做完就有：三檔都能切、key 藏得住、多個 agent 共用一把 key 不會一起撞 429、用量有檔可查。還沒有：預算、窗口、份額樹、多 endpoint。

**不確定的地方**：

- **地基還沒有**。proto6 目前只有 spec，沒有 daemon、tick、once、git commit 的程式。以上估計假設這些已經能跑；若排程器跟地基一起做，工時會被地基吃掉一大塊，而且地基的介面一改排程器就要跟著改。
- **systemd 方向**。下班前決定 daemon 站在 systemd 上；once 工作若改用 `systemd-run` 開，塊 1、3 的開程序方式會變。
- **spec 條文很細**。unknown、attempt 去重、先 commit 再送這些規定在 proto5 修過好幾輪，proto6 寫得更嚴；照 proto5 經驗，審查後的修補輪可能讓每塊再加 30～50%。
- 價格表要不要做、做到多細，差別可以是半天到兩天。

## 四、跟 LiteLLM 比

| 面向 | 自己做 | LiteLLM |
|---|---|---|
| 依賴 | 只要 Python（或任何語言）＋Linux 帳號＋git；不多開一個常駐服務 | 一個常駐的 Python 服務；要虛擬 key、預算、用量紀錄就還要一個 PostgreSQL。版本更新頻繁 |
| 藏 key | 靠 Linux 帳號權限：池帳號讀得到、agent 帳號讀不到，跟 aos 其他權限同一套 | 靠虛擬 key：真 key 在 LiteLLM 手上，agent 拿一把假 key。等於在 Linux 帳號之外多一套身分系統 |
| 跟 aos 額度整合 | 額度跟 node 樹一起分（父給子、子再分），用量檔就在 node 裡、跟 git 一起走；unknown、attempt 的算法照 spec | 要把 aos 的 node 對應成 LiteLLM 的 user／team／key，兩邊各記一份帳，要人對帳 |
| 跟 cgroup／帳號整合 | 代發程序本身就是 aos 的 once 工作，受 cgroup 管、算進 node 的資源 | LiteLLM 是 aos 外面的服務，它的 CPU／記憶體不算在任何 node 頭上 |
| 功能覆蓋 | 只做我們要的：OpenAI 相容格式、非串流、並行＋窗口＋冷卻 | 遠多：上百家 provider 的轉換、串流、自動 fallback、快取、價格表、管理網頁 |
| 可控性 | 行為全在 spec 裡，出事可以逐檔看；想改就改 | 行為在它的程式與設定裡；有些細節（例如重試、結果不明時怎麼算帳）不一定跟 aos 的規定一致 |
| 維護成本 | provider 格式變了、價格變了要自己跟；只接 OpenAI 相容格式可以少掉大半 | 升級就好，但升級可能改行為；出問題要去讀別人的程式 |
| 延遲 | 見下 | 見下 |

**延遲：每次 LLM 呼叫多經幾格 tick。**

- 「不管」檔：agent 這格送出 → once 打 HTTP → 結果回來、agent 下一格收。跟用 LiteLLM 當 endpoint 一樣多格。
- 「交給 endpoint」「自己排」：多了池 node 收件的一格、收結果的一格；走「全管」路線再多轉交 kernel 的兩格。每格的成本是開程序＋跑任務表＋git commit。
- proto5 量過：單個 agent 問一題，aos 本身的額外時間從 11.8 秒壓到 2.1 秒（`proto5/notes/2026-09-24-tick-gap`），靠的是「一有結果就叫醒」。proto6 若照[三條路](../verdicts/04-late-day-directions.md#下班前的方向同日systemd-那條已被第十四批取代litellm-那條已落進-spec)第 2 條做（once 一結束馬上叫醒 parent），多兩格估計多**幾百毫秒到一兩秒**。雲端模型一次回應常是幾秒到幾十秒，批次跑的 agent 感覺不大；人在旁邊等回覆的對話會感覺到。
- 對照：LiteLLM 當 endpoint 時，多的只是一次本機 HTTP 轉手，幾毫秒。但若 aos 還是要走池 node 藏 key，這幾格 tick 一樣省不掉，差別只在「限流算在哪」。

**一句話**：最大的好處是**額度跟 key 用 aos 原本的 node 樹和 Linux 帳號管，不多一套身分和帳本、不多一個常駐服務**；最大的壞處是**功能少（沒串流、沒自動 fallback、沒現成價格表），而且每次呼叫多經一兩格 tick**。

## 五、之後要動 spec 的地方（這輪不動）

- A-101／P-701：`llm.target_node` 允許 `null`＝不管檔。
- P-405／`llm-config`：每池加 `schedule` 欄。
- P-505／P-501：配額加 token（或錢）預算欄；S-203 定「卡多久寫待辦」。
- P-811：若做多 endpoint，一池可掛多個 endpoint 與切換規則。
- S-301：LiteLLM 只是「一種 endpoint」，不在標準裡特別提。

## 需要使用者拍板的問題

已裁定，見 [verdicts 第十三批](../verdicts/04-late-day-directions.md#第十三批llm-排程器同日晚已落進-spec)。

1. **三檔還是兩檔？**「不管」和「交給 endpoint」差在 key 藏不藏、有沒有池 node。
   建議：保留三檔，但前兩檔是同一支程式、只差「誰開它」，實作上幾乎不多花。
2. **預設哪一檔？**
   建議：`aos node new` 的範本預設「不管」，新使用者不用先建池就能跑；多個 agent 要共用一把 key 時才切到另外兩檔。
3. **切換用這兩個欄位行不行？**（agent 的 `llm.target_node` 可填 `null`；池設定每池一個 `schedule`）
   建議：可以，跟工具的 `tools.target_node` 對稱。
4. **預算算 token 還是算錢？**
   建議：首版只算 token；算錢要價格表，留成可選檔案，由人手維護，不自動抓網路價格。
5. **多 endpoint 自動切換要不要自己做？**
   建議：首版不做。需要的人把 LiteLLM 當 endpoint，讓它去切。
6. **串流要不要做？**
   建議：不做，維持 S-301 的「只收完整結果」。
7. **「不管」檔的 key 藏不住，接受嗎？** agent 自己打 HTTP，key 一定要 agent 帳號讀得到。
   建議：接受，文件寫清楚，跟第八批「沒 helper 時 key 不受保護」同一個態度。
8. **什麼時候做？** 排程器依賴 daemon／tick／once 的地基。
   建議：先做地基原型；排程器的最小可用版排在地基能跑一整套 agent 循環之後，跟[三條路](../verdicts/04-late-day-directions.md#下班前的方向同日systemd-那條已被第十四批取代litellm-那條已落進-spec)的延遲實測一起做。
