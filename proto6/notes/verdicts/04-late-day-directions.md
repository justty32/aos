# 2026-09-29 使用者裁定（四）：下班前的方向、LLM 排程器

← [裁定索引](README.md)｜[筆記索引](../README.md)

本份收：「下班前的方向」、第十三批（LLM 排程器，含「LLM 呼叫池＝一個 node」）。全部裁定後批優先，見[裁定索引](README.md)。

## 下班前的方向（同日；systemd 那條已被第十四批取代，LiteLLM 那條已落進 spec）

- **daemon 站在 systemd 上面**〔使用者方向 2026-09-29〕：登記、定時叫醒、暫停、切帳號、cgroup 資源框、殺乾淨程序樹，盡量交給 systemd（如 `systemd-run --uid … -p MemoryMax=…`、timer），不重造輪子；安全性這塊要小心設計。逐條拆分見 2026-09-29-systemd-split.md（已封存檔 2026-09-29-systemd-split.md，索引見 [archive/README.md](../archive/README.md)）。（已被第十四批「初版不用 systemd」取代；取代後的做法已落進 spec，見 [B-605](../../spec/daemon.md)。）
- **LiteLLM 不進標準，只是可選的 endpoint**〔使用者方向 2026-09-29 晚，取代同日稍早「LLM 池基礎功能接 LiteLLM proxy」〕：它是額外依賴，違反以 Linux 為中心、少外部依賴的原則。aos 自己的 LLM 排程器做成**分檔可選**：不管（直接打 endpoint）／自己排（aos 自己藏 key、限流、記帳、排隊）／交給 endpoint（endpoint 可以是 LiteLLM、原廠 API 或本機模型伺服器）。工作量與利弊調查見 LLM 排程器選項（已封存檔 2026-09-29-llm-scheduler-options.md，索引見 [archive/README.md](../archive/README.md)）。（已落進 spec，見 [S-301](../../spec/scheduling/llm.md)。）
- **可參考**：Maildir（收件做法）、Erlang/OTP supervisor 樹、Kubernetes controller 對帳；後續慢慢調查。AIOS 不參考（使用者評價：垃圾）。
- **待辦**：跑不跑得動之後實測，最擔心的是工具呼叫延遲；搬家／備份做一個輔助工具；aos 自身升級（格式 v2、既有 node 遷移）要考慮；log 先不管，daemon 之後慢慢改進。
- **降低工具呼叫延遲的三條路**〔使用者認可 2026-09-29，之後實測再定〕：
  1. 工具走「kernel 不管」路線：agent 自己在底下登記 once 工作，不經 kernel 轉手，一次工具呼叫約少兩格 tick。
  2. once 工作一結束，daemon 馬上叫醒它的 parent，不等下一次定期 tick；延遲主要剩程序啟動＋git commit。
  3. 換成 systemd 後先量 `systemd-run` 開短命程序的成本；若每次多等幾百毫秒，就考慮讓工具在 agent 那格 tick 裡直接跑，不另開 once 工作。
     - 實測見 [probes/systemd-run-latency.md](../probes/systemd-run-latency.md)：`systemd-run --user --wait` 開短命程序比直接開多約 5 毫秒（加記憶體／CPU／程序數三個限制約 25 毫秒），一次 git commit 約 2 毫秒，沒有到幾百毫秒。

## 第十三批：LLM 排程器（同日晚，已落進 spec）

針對LLM 排程器選項（已封存檔 2026-09-29-llm-scheduler-options.md，索引見 [archive/README.md](../archive/README.md)）最後八題的裁定。

1. **三檔**〔使用者方向 2026-09-29 晚〕：不管（agent 直接打 endpoint）／交給 endpoint（池 node 代發，限流交給 endpoint）／自己排（aos 自己藏 key、限流、記帳、排隊）。照建議。
2. **預設「自己排」**〔使用者方向 2026-09-29 晚，不照建議〕：建議原是預設「不管」。理由：LiteLLM 一開始預設跟 aos 無關，所以預設走 aos 自己的排程。
3. **切換用兩個欄位**〔使用者方向 2026-09-29 晚〕：agent 的 `llm.target_node`（可為 `null`）加每池的 `schedule`。照建議。
4. **預算首版只算 token**〔使用者方向 2026-09-29 晚〕：算錢的價格表留成可選檔案、人手維護、不自動抓網路。照建議。
5. **多 endpoint 自動切換首版不做**〔使用者方向 2026-09-29 晚〕：要的人拿 LiteLLM 當 endpoint。照建議。
6. **串流要做**〔使用者方向 2026-09-29 晚，不照建議〕：推翻 S-301 首版「只收完整結果」。
7. **「不管」檔藏不住 key，接受**〔使用者方向 2026-09-29 晚〕：文件要寫清楚。照建議。
8. **先做地基原型**〔使用者方向 2026-09-29 晚〕：排程器最小可用版排在地基能跑完整 agent 循環之後。照建議。

### 裁定帶出的待釐清處

只列問題，不替使用者決定。

- **預設「自己排」要有池 node**：
  - 問題：沒有池 node 時，agent 的請求怎麼辦？
  - 裁定〔使用者方向 2026-09-29 晚〕：`aos node new` 不自動建池。~~agent 發 LLM 請求卻找不到池時，寫一筆待辦（attention）告訴人「先建池」，請求先擱著。~~
  - 改寫〔使用者方向 2026-09-29 晚〕（改自前一版：原為寫待辦）：目標 node 不存在，丟請求那一步直接報錯，不寫待辦；跟「沒給權限就報錯」同一個態度。目標 node 存在但沒人處理，aos 不管，請求就堆著。（又改自前一版：原為池資料夾）
- **串流怎麼跟「tick 一格一格跑」相容**：
  - 問題：串流要怎麼跟 tick 相容？
  - 裁定〔使用者方向 2026-09-29 晚〕：不為串流另做機制。一次 LLM 呼叫就是掛在 tick 上的一件任務，tick 執行時它直接跑；所謂串流，就是這件任務在跑的過程中不斷寫入一個指定的檔案。
  - 中途斷線不管；頂多這件任務以非 0 exit status 結束、在 stderr 噴錯。
  - 「不管」檔（agent 自己打 HTTP）aos 不管，串流也不管。
- **spec 裡寫「只收完整結果」「不做串流」的條文之後要改**（只列、不改；串流改動方向是「任務邊跑邊寫指定檔案」，不加新機制）：
  - `spec/scheduling/llm.md`：S-301（「首版只支援非串流」）、S-305（已刪的串流與 final，要恢復）、S-304 的完整結果邊界。
  - `spec/protocol/work.md`：P-406（`stream` 只准 false 或省略、HTTP body 送 stream:false）、P-405 附近及 llm.chat 結果那段（「只接完整非串流結果」、usage 規則）。
  - `spec/protocol/schemas/llm-payload.schema.json`、`llm-request.schema.json` 的 `stream` 欄，以及 `examples/work/llm-payload.streaming.invalid.json`（現在是反例）。
  - `spec/README.md` 第 35 行「串流產品介面不在本輪交付範圍」。
  - 另有 P-701／P-706（agent 發 LLM）、P-403（結果與串流）、P-811（池與共享窗口）、conformance.md 可能連帶要看。

### LLM 呼叫池＝一個 node

〔使用者方向 2026-09-29 晚〕（改自前一版：原為「目標資料夾、池用什麼實現都可以」，已作廢）

**定調**：tick 某個 agent，遇到需要 LLM 呼叫時，那個任務把 JSON-RPC 請求投進池 node 的 `requests/`，然後結束，tick 繼續跑下一個任務。這照既有慣例：要別的 node 做事，就是把檔案承載的 JSON-RPC 投進對方收件區。池就是一個 node，不是另外的資料夾契約。

~~舊說法：指定資料夾就是 LLM 呼叫池，「一個會處理資料夾內各類請求的東西」，用 aos 體系或另寫獨立程式都可以；池的標準只規定「資料夾＋JSON-RPC 格式」。~~（已作廢）

**對前面三檔的意義**：

- 「自己排」與「交給 endpoint」，對 agent 來說一樣：都是把請求投給池 node、等回覆。差別只在池 node 裡裝的任務。
- 「自己排」＝池 node 裡裝 aos 自己排隊、限流、記帳的任務。
- 「交給 endpoint」＝池 node 底下的一件轉發任務，把請求轉給 LiteLLM 之類的 endpoint（不再是跟 aos 無關的獨立程式）。
- 「不管」不變：agent 自己打 HTTP，不經池，aos 不管。

**待釐清四題已裁定**〔使用者方向 2026-09-29 晚〕：

- **回覆送回哪裡**：
  - 問題：請求要不要帶回覆位址與串流檔路徑？池怎麼知道寫到哪？
  - 裁定〔使用者方向 2026-09-29 晚〕：寫在 JSON-RPC 請求裡。回覆位址、串流檔路徑都是這份請求本來就要寫好的內容，池 node 照請求上寫的送。
- **權限**：
  - 問題：池 node 的收件區、回覆檔、key 的讀寫權限怎麼安排？
  - 裁定〔使用者方向 2026-09-29 晚〕：aos 不管。沒給權限，就報錯。
- **回覆到了誰叫醒 agent**：
  - 問題：池 node 裡的轉發任務要不要呼叫 daemon 叫醒 agent？
  - 裁定〔使用者方向 2026-09-29 晚〕：aos 不管。agent 要自己寫監控程式，或用別的方式知道回覆到了，都可以。
- **沒有池怎麼辦**（原標題「沒有池就寫待辦」，兩度改寫）：
  - 問題：node 不存在算沒有池？還是存在但一直沒人處理？要等多久？
  - ~~舊裁定：不管，aos 不定義怎麼偵測「沒有池」；「找不到池就寫待辦」保留。~~（已作廢）
  - 裁定〔使用者方向 2026-09-29 晚〕（改自前一版：原為「池資料夾不存在就報錯」）：
    - 目標 node 不存在：丟請求那一步直接報錯，不寫待辦。跟「沒給權限就報錯」同一個態度。
    - 目標 node 存在但沒人處理（例如沒裝任務、沒被 tick）：aos 不管，請求就堆著，也不等、不逾時。
  - 跟上面「`aos node new` 不自動建池」那條的關係：不自動建池仍保留，但沒池時的處理是報錯，不寫待辦。
- **現有 spec 之後要改的部分**（只列、不改）：現有 spec 本來就把池寫成 node，大致相符。實際看過 P-505（agent 只按一個 node 位址投 `llm.chat`）、P-808～P-809（路由表與 `aos-kernel-llm-forward`，轉給下一個 kernel）、P-811（池是 tick 任務，沒有常駐池 daemon）、P-812（唯讀查詢），都是 node 模型，不用重寫。之後只需補：串流（見上面「串流」那條清單）、「交給 endpoint」的轉發任務（現在的 forward 只轉給下層／上層 kernel，沒有轉給外部 endpoint 的任務）、`llm.target_node` 可為 `null`（不管）與每池 `schedule` 兩欄位、目標 node 不存在時報錯的行為。
