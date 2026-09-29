# 雲端 LLM 入場控制與一萬 agent 的驗收

> 2026-09-28 交接快照；[原始來源](../../../proto5/notes/2026-09-28-ten-thousand-agents/llm-and-validation.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

> 後續註記（2026-09-29，依[裁定](../2026-09-29-verdicts.md) 9）：下文「兩種接法」已選第二種——中央代發服務保管 key、agent 與工具只投請求，延續 proto5 現況（見 spec S-301）。

2026-09-28。這是本輪架構規劃的一部分，所有數值門檻均為建議，未修改產品、未呼叫收費 API、未建立宿主帳號或資源限制。現版尚沒有這份規劃需要的整合式 limits／resources 管理。

## 先分清楚要承受的負載

一萬名已登記 agent 是資料與身分規模；每小時活躍的不同 agent 少於一百，是工作集規模。它不表示同時有一百個程序或 LLM 請求，也不保證低於一百：少數 agent 可以瞬間派出大量工具或模型工作。要另外量測同時執行 jobs、等待 LLM 的 requests、單一 agent 的 fan-out，以及各任務實際持續時間。

十幾個 endpoint 也不等於十幾份獨立容量。同廠商、同帳號／組織或同一共享 model quota 的不同 URL／key，可能仍吃同一份上限。URL 是連線位置，quota scope 是資源歸屬，兩者分開登記；識別 scope 用非秘密 ID，不把 API key 放入紀錄。

## 先用一個本機帳本，不增加另一套基礎設施

建議由單一可信控制流程負責 LLM 入場判斷，沿用 SQLite 的持久交易紀錄與檔案交接；JSON-RPC 可以放檔案中傳送，不要求 socket server。排隊、預留、派出意圖與結果分別落帳，回覆檔用原子發布。SQLite 交易不會讓網路呼叫自動成為同一筆交易，恢復仍要面對「已送出但結果未知」。

目前規模沒有足夠理由先引入 Redis、Kafka、分散式鎖或多機排程。先用索引查詢到期和就緒項目；不要為等待 quota 保留一個睡眠 worker，也不要每次挑一個 request 就重讀一萬個 agent 目錄。選擇資料庫不是對吞吐的保證，真正要測的是短交易、鎖等待、checkpoint、結果恢復與就緒查詢成本。

這是設計建議，現有 SQLite 帳本的存在不代表已具備下述入場控制。現行可見來源包括 [kernel store](../../../proto5/lib/aos_kernel_store.py)、[LLM 呼叫](../../../proto5/lib/aos_llm_call.py) 與 [LLM ask](../../../proto5/lib/aos_llm_ask.py)；本篇沒有修改它們。

## LLM 請求入場：同時檢查共享上限

每次嘗試先解析哪些 quota scope 適用，例如帳號整體、model family、project／workspace，以及 endpoint 自己的連線上限。只有全部有餘額才預留並派出；不能先占住一個 scope 等另一個，造成資源互鎖。各 scope 可包含 RPM、輸入 TPM、輸出 TPM、合併 TPM 與 concurrency，僅啟用供應商實際適用的維度，不假設每家都有完全相同限制。

請求在待派佇列裡不占用活躍 HTTP concurrency。入場交易記錄本次 request／attempt 的預留、預估 input tokens、要求的 output 上限與租期／恢復狀態。先預留再送 HTTP；成功取得 usage 後對帳，釋放本機連線席位。帳本的「預留」不是先付費，也不是遠端已接受。

要分開兩本帳：**成本帳**依實際 usage 記錄已知消耗；**速率帳**依供應商限流語意補差。有的供應商在接受時用要求的 token 上限估算 rate consumption，不能因回覆短，就把所有差額立即退回 TPM。若 usage 缺失、輸入 tokenizer 不相容、輸出量未知、遠端有其他消費者，保留估計與未知狀態；本機只能做有裕度的入場控制，不能硬保精準遠端預算。官方例子可見 [OpenAI 共享與速率上限](https://developers.openai.com/api/docs/guides/rate-limits) 與 [Claude RPM／輸入／輸出 TPM](https://platform.claude.com/docs/en/api/rate-limits)。

若工具內部也呼叫模型，想讓全局限制有效，就必須沿用委託 agent 身分經過同一個可信入場口。有兩種接法，尚未代替使用者選擇。第一種由 scheduler 發許可，agent UID／cgroup 下的 runner 直接呼 API；接線較少，但 agent 能讀取 key 且可任意出網時，可以繞過許可，因而只管理受管呼叫。第二種由中心 broker 保管 key、驗證委託身分後代發；這增加代理服務、鑑權、可用性和入口管理的成本，若要強制預算還需處理直連及其他憑證來源，不能宣稱完全不增加服務。

兩種接法都需要可信 request 歸屬。直接 runner 的本機消耗歸 agent cgroup；共享 broker 的 CPU／RAM 通常歸控制層，應另設全局上限並按 request 記 agent 的雲端消耗，不能假稱 broker 的程序資源自動記到每個 agent cgroup。工具仍沿用委託 agent 身分，不因呼叫 LLM 而取得改寫他人帳本的權限。

## 退避、取消和結果未知

429 先辨識暫時限流或帳務／額度不足。暫時限流尊重 `Retry-After` 的最早重試時間，再加 jitter，沒有提示時採有上限的指數退避。共享 scope 被限流就降低該 scope 的派送，不是換另一個相同帳號 URL 繼續轟；健康的獨立 scope 可以照常工作。永久帳務或授權錯誤應停住並呈現原因，不能無限重試。SDK 自帶重試與 aos 重試要只留一個清楚的總次數／時間預算，避免相乘。[Claude rate-limit 回應](https://platform.claude.com/docs/en/api/rate-limits)

必須區別尚未派出、已確定未送出、已開始傳送、已取得遠端結果、結果未知。若 HTTP timeout、connection reset 或 daemon 崩潰發生在可能送出之後，遠端可能已算 token，不能把 reservation 全部退回並盲目再問。若供應商提供適用的查詢／冪等機制才利用；否則記為未知，依明確任務策略決定是否以新 attempt 再試及承擔可能重複成本。LLM 結果去重也不能補救工具已執行的副作用。

取消未送出 request 可以移出佇列並取消預留；取消已送出的 HTTP 只能確定本機不再等待，不能據此保證遠端停止或不計費。本機 concurrency 席位和仍不確定的遠端工作分開記，對未知請求設可觀察的處置期限和保守容量估計，避免永久卡死，也避免假裝遠端立刻空出容量。第一版可先完整回覆；逐 token 串流不必和此輪入場控制綁在一起。

## 本機工作與公平性

雲端在等待時，本機仍有 socket、記憶體、解析和紀錄成本；一般工具還可能 fork 大量子程序。因此至少分本機執行 jobs、HTTP 活躍請求、pending queue 容量三種上限，再限制單 agent 的在途工作。cgroup 的 memory／pids／CPU 限制管真正程序消耗；scheduler 的 jobs 上限管派工，兩者不互相取代。

建議在各個可用 quota scope 內，先依 agent 做輪流派送，再考慮互動和背景任務優先序；給互動工作較快回應，同時用保留份額或 aging 讓背景工作仍前進。精確權重未定，不把「互動永遠最優先」寫成可餓死背景工作的規則。大 token request 也不能因小請求一直插隊而永遠等不到，須有等待時間或專用容量策略。超出單一 request 可用上限應立即回報不可執行，而不是永遠排隊。

## 先定最小識別與恢復語意

需要能追溯長期 task、某次 run、工具／模型 job 和每次 attempt。task 是持續追蹤的工作，run 是一段執行生命週期，job 是具體委託，attempt 是一次實際嘗試；名稱可以調整，但重送同一請求與重新執行工作不能混為一談。JSON-RPC 的 request id 負責一次請求回覆對應，不宜同時冒充所有層級的身分。

先約定可信的委託 agent 歸屬、去重依據、接受／拒絕／完成／未知狀態、查詢結果、取消、結果保留，以及重啟後如何辨識同一 attempt。重複結果只能結算一次；同 id 不同內容必須拒絕或明確報衝突。task 執行中收到新訊息歸目前 run 還是下一輪，仍沿用待定語意；不為了這份驗收計畫擅自定整套 JSON-RPC methods、schema 或串流協定。[JSON-RPC 2.0](https://www.jsonrpc.org/specification)

## 驗收要拆開，不用一萬個真帳號假造成功

**冷資料規模：** 建一萬筆登記 metadata 和代表性資料夾，不自動建立一萬個宿主使用者。無工作時檢查常駐程序、記憶體、每秒檔案操作與帳本查詢；將登記數從一千增至一萬，觀察閒置成本是否隨總數線性增加。量測冷啟動載入和 steady state 分開，不能用熱 cache 查詢假裝 cold start。

**真身分與資源整合：** 在可丟棄的 Linux VM／測試環境用少量帳號，例如 2–5 個，驗證 UID／group、工具委託繼承、cgroup 和 project quota。測超量寫入、inode、記憶體超限、fork 限額、外部 workspace 歸屬、工具孫程序，以及控制層是否仍可管理。這需要實際部署條件，不能用 mock 宣稱 Linux enforcement 通過；也不能把既有 Landlock 小測算作此輪已完成。正式登記一萬帳號的 NSS／帳號配置效能可另做隔離環境量測，不動使用者現有主機帳號庫。

**就緒突發：** 同時喚醒 1、10、100 個 agent，並另測少數 agent 各派大量 jobs。入場上限固定、供應商 mock 可控制延遲，觀察排隊時間和公平性；有資源時才用約 0.5 秒的回應偏好評估 wake-to-start，滿載等待不計為喚醒機制失效。沒有必要把一萬名登記 agent 一次全部變成可執行程序。

**每小時工作集：** 模擬 100 個不同 agent 在一小時內陸續活動，是「少於一百」前提的近邊界壓測。配置十幾個 mock endpoints，故意讓其中多個共用 account／model bucket；另含真正獨立 bucket。混合快慢回覆、長上下文、短輸出、不同 task 持續時間及背景工作，另測同樣總量集中於五分鐘的 burst。此階段只用 mock cloud，不產生實際 API 費用；它驗證本機控制，不驗證真供應商效能或計費。

**失敗情境：** 包含共享 bucket 429、錯誤／缺失 Retry-After、授權失敗、超大 request、usage 缺失或不同 schema、已送出後斷線、重複 completion、daemon 在預留後及送出後崩潰、帳本 busy／磁碟滿、取消競態、單一 agent 洪水，以及 endpoint 長期不可用。應看到有界的 pending、明確拒絕或等待原因、未知結果可查、已結算不重複、其他健康 scope 和 agent 可繼續。

## 建議量測與起始門檻

以下僅作為第一輪在固定家用測試機、相同輸入與已記錄版本上對照的建議，不是已承諾效能或產品限制。

- 一萬個冷登記不產生一萬個常駐程序；閒置不逐 agent 固定輪詢。建議 steady-state 控制層 CPU 平均低於單核 1%，一千增至一萬時閒置 RSS 增量低於 128 MiB；需記測試機和觀測區間，超標用 profile 找原因。
- 沒有排隊和遠端負載時，wake 到可執行工作的 p95 建議不超過 0.5 秒；同時記 p99、最大值和分段耗時，不把 mock 的回覆時間當本機耗時。
- 已配置本機 jobs、per-agent 在途與 HTTP concurrency 上限不得超過；mock 已知 token 計算下不得超過共享 scope 的規則。真遠端預估誤差另記，不能借 mock 的零超限宣稱遠端硬保證。
- 未知 attempt、未釋放預留、重複 usage 入帳皆可查；無故重複派送和重複結算目標為 0。恢復後工作不靜默消失，未知結果不被偽裝成功或確定失敗。
- 過載時佇列有界、持續回報 queue age；在至少十輪本機公平派送機會中，每個持續有可執行工作的 agent 都應得到進展。上游 quota 完全耗盡或 request 永遠放不進 bucket 時要另報原因，不拿它判定本機公平性。
- 同時記 registered／每小時 unique active／當下 active agent、ready depth、jobs／HTTP 在途、每 scope quota wait、token 預估誤差、429、重試、未知遠端結果、CPU／RSS／FD／資料庫 busy 時間。將分段資料放 JSON／CSV，不在 Markdown 堆每筆事件。

這些驗收目前都尚未執行。先把單一可丟棄 Linux 部署和 mock 測試做實，再討論其他主機、檔案系統或發行版的適用性，不能把多部署環境相容性提前寫成完成。
