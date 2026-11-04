# LLM 排程器：決定、現況與自製 vs LiteLLM 的比較

← [筆記索引](README.md)｜裁定：[第十三批](verdicts/04-late-day-directions/01-下班前方向與第十三批.md#第十三批llm-排程器同日晚已落進-spec)｜spec：[S-301～S-305](archive/spec-2026-10-02/scheduling/llm.md)（S-306 已刪）

2026-09-29 晚，使用者改口：LiteLLM 不進標準，只當可選的 endpoint；aos 自己的 LLM 排程器也做成可選。原本的比較筆記（逐項清單、估時、拍板題）已封存，見 archive/2026-09-29-llm-scheduler-options.md（已封存檔 2026-09-29-llm-scheduler-options.md，索引見 [archive/README.md](archive/README.md)）。本頁只留決定、現況與以後還用得到的比較。

## 決定（第十三批，已落進 spec）

- **三檔**，agent 那邊看到的介面三檔一樣（投 `llm.chat` 請求、下一格從 `responses/` 收結果），差別只在請求投給誰、對面做多少事：

| 檔 | 誰打 HTTP | key 在誰手上 | 限流／預算／排隊 |
|---|---|---|---|
| 不管（現名直連） | agent 自己登記一件 once 直接打 | agent 帳號讀得到（藏不住，已接受、文件寫清楚） | aos 不管，只記自己的用量 |
| 交給 endpoint | 池 node 代發 | 只有池 node 帳號讀得到 | aos 只藏 key、記用量、照 429 等；限流與預算交給 endpoint（已被第十五批取代：只轉發、不重試，見 [llm.md](archive/spec-2026-10-02/scheduling/llm.md)） |
| 自己排 | 池 node 代發 | 只有池 node 帳號讀得到 | aos 全做：份額、窗口、冷卻、預算、排隊 |

- **預設「自己排」**（不照原建議的「不管」，現名「直連」）。沒有池 node 時，丟請求那一步直接報錯。
- **切換用兩個欄位**：agent 的 `llm.target_node`（`null`＝不管檔）、每池的 `schedule`。
- **預算首版只算 token**；算錢的價格表留成可選檔案、人手維護。（已被取代：token 預算先不做，見 [llm.md](archive/spec-2026-10-02/scheduling/llm.md)。）
- **多 endpoint 自動切換首版不做**，要的人拿 LiteLLM 當 endpoint。
- **串流要做**（推翻原本「只收完整結果」）：不另做機制，LLM 呼叫這件任務邊跑邊寫指定檔案（S-305）。
- **先做地基原型**：排程器最小可用版排在地基能跑完整 agent 循環之後。

## 現況

- proto6 還沒有程式；daemon、tick、once、git commit 流程都要先有，排程器才有地方跑。
- spec 已涵蓋：藏 key、並行份額、次數／token 窗口、`quota_scope` 共同冷卻、429 重試、逾時與結果不明、用量記帳、轉交、狀態查詢（細節見 [spec LLM 排程](archive/spec-2026-10-02/scheduling/llm.md)）。
- 三檔共用同一支 `aos-llm-call`（讀請求、打一次 HTTP、寫回結果與 usage）；「不管」（現名直連）檔由 agent 開它（已被第十五批取代：直連 aos 完全不管，見 [llm.md](archive/spec-2026-10-02/scheduling/llm.md)），另兩檔由池 node 開它。
- endpoint 可以是任何講 OpenAI Chat Completions 格式的 HTTP 服務（LiteLLM、原廠 API、LM Studio／llama.cpp／vLLM）；別種格式要多寫轉換器。

## 還有價值的比較

### 工作量估計（只算排程器，不含地基）

依 proto5 實際紀錄估；「一隊」是一個 Opus 或 Sonnet 隊做一段、含測試，不含每段後的試玩與審查（每段再加約 1 小時）。

- 最小可用版：`aos-llm-call` 共同底＋不管檔＋池 node 基本代發，再加「並行上限＋429 共同冷卻」。約 **3～4 隊、12～16 小時，牆上時間約 1 天**。
- 做滿（再加窗口、份額與轉交、token 預算、多 endpoint）：約 **8～10 隊次、30～45 小時，牆上時間約 2～3 天**。
- 不確定處：地基介面一改排程器就要跟著改；照 proto5 經驗，審查後的修補輪可能讓每塊再加 30～50%；價格表做多細差半天到兩天。

### 自己做 vs LiteLLM

| 面向 | 自己做 | LiteLLM |
|---|---|---|
| 依賴 | Linux 帳號＋git；不多開常駐服務 | 常駐 Python 服務；要虛擬 key、預算就還要 PostgreSQL |
| 藏 key | 靠 Linux 帳號權限，跟 aos 其他權限同一套 | 靠虛擬 key，等於多一套身分系統 |
| 跟 aos 額度整合 | 額度跟 node 樹一起分，用量檔跟 git 走 | node 要對應成 LiteLLM 的 user／team／key，兩邊各記一份帳 |
| 跟 cgroup 整合 | 代發程序就是 once 工作，受 cgroup 管 | 在 aos 外面，資源不算在任何 node 頭上 |
| 功能 | 只做 OpenAI 相容格式、並行＋窗口＋冷卻 | 上百家 provider、fallback、快取、價格表、管理網頁 |
| 維護 | provider 格式與價格要自己跟 | 升級就好，但升級可能改行為 |

**延遲**：交給池 node 時，每次呼叫多經收件、收結果兩格 tick（走全管路線再多兩格），每格是開程序＋跑任務表＋git commit。proto5 靠「一有結果就叫醒」把 aos 額外時間從 11.8 秒壓到 2.1 秒；proto6 照同樣做法，多兩格估計多幾百毫秒到一兩秒。雲端模型一次回應常是幾秒到幾十秒，批次 agent 感覺不大，人在旁邊等的對話會感覺到。LiteLLM 當 endpoint 只多一次本機 HTTP 轉手，但只要 aos 還走池 node 藏 key，這幾格省不掉。

**一句話**：自己做的好處是額度和 key 用 node 樹與 Linux 帳號管，不多一套身分、帳本和常駐服務；壞處是功能少，而且每次呼叫多經一兩格 tick。
