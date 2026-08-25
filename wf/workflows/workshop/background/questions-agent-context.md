# 題目導讀：agent context、session 與工具集合
← [BACKGROUND](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS.md)

### 題目：coding agent 的 stdin 要吃 request file、`status --json`，還是新的 `aos prompt／emit`？

**這題其實在問什麼**：送給 agent 的「這次請做什麼、現在狀態是什麼」究竟從哪個穩定、有來源的機器介面產生。
**為什麼會有這題**：`aos exec` stdout 會混入任意子指令輸出，平行時還可能交錯；四位已一致排除它，但只定了回程用 Deliver，去程仍缺 envelope。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| request file | 最直接，driver 把已提交的請求原檔送進 stdin | 每個 driver 要自己選檔、組 context | 多個 agent/adapter 重複同一套選取與 envelope 邏輯 |
| `status --json` | 沿用查詢工具，不新增命令 | Status 可能被迫塞進大量 prompt/history 內容 | 人只想查 queue，卻得到又大又穩定包袱的 agent context |
| 專用 `prompt/emit` | 可明確帶 turn/source/schema envelope，針對 stdin 安定輸出 | 多一支公開 tool，要定義它與 driver/prompt 政策的邊界 | 它開始組 system message、裁對話，把 agent-specific 政策拖進 core |

**如果現在不決定會怎樣**：會擋住 stdout→stdin 的穩定閉環與 adapter 契約；第一條 golden slice 可直接選一個 request file 當私有實驗格式，不先宣告公開 API。
**最小的驗證方式**：用同一份 1–2 KB 玩具 context，各以 request file 直送、假 `status --json`、假 `emit` 三種方式 pipe 給選定的 agent CLI；後面再增加第二個 turn，看哪一種不需重複組裝且不把 prompt 政策塞進 core。

### 題目：第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？

**這題其實在問什麼**：每次呼叫 agent 要靠 world 檔案重新喂完整前情，還是平常靠宿主已存的對話狀態加速，只在它丟了時才重建。
**為什麼會有這題**：session 的旗標、定址與 final event 還沒實測、也未必跨版穩定；但完全每次重喂歷史可能慢且貴。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| `--no-session` 可攜預設 | world 單獨就能重建，換機/換 agent 較誠實 | 每回 context token、延遲與輸出格式成本較高 | 長對話中大量重複傳輸，快取明明存在卻不用 |
| session 快取優先 | 續談快，少重傳前情 | 得驗並綁定特定宿主旗標/事件，仍需 fallback | 宿主升級或 session 消失時才發現 world 根本不足以重建 |
| RPC/JSONL adapter 優先 | 先把 final/exit/session 捕捉的實際介面驗穩 | 會先投資 provider-specific adapter，不直接回答預設是否續 session | 介面並沒穩定承諾，測完仍得在 no-session/session 之間取捨 |

**如果現在不決定會怎樣**：會擋住 T5 driver 每回如何呼叫選定 CLI、world 需保存多少歷史；可先以 no-session 當單次實驗，但不把它寫成永久產品預設。
**最小的驗證方式**：對選定 CLI 做一次兩回對話：一組每回 no-session 重喂 1–2 KB 前情，一組建 session 後 resume；記錄延遲、傳輸量、取回 session id 難度，然後刪掉／移走 session 驗證 world 能否 fallback。

### 題目：首版只公開 Deliver，公開 Deliver＋Status＋Exec，還是再把 Init 放進同一組？

**這題其實在問什麼**：第一版給 coding agent 的 aos 工具箱，是只准它排工作，還要讓它查現況、推一回，甚至自己建一個新 world。
**為什麼會有這題**：[工具協作場](records/tool-interop.md) 四位對 runtime 最小三支都選 Deliver/Status/Exec，但[回頭審視](records/step-back-review.md) 的近期 core 又只保留 Deliver；Init 被三位提到，但是否屬 runtime 未定。
**選項差在哪**：

| 選項 | 你會得到什麼 | 你會賠掉什麼 | 什麼時候會後悔 |
|---|---|---|---|
| 只有 Deliver | 公開面最小，只補現存投遞缺口 | agent 得靠現有檔案工具查狀態，Exec 由人/外部 driver 做 | agent 投完無法結構化確認 queue/`.runi`，每次都需人接手 |
| Deliver＋Status＋Exec | 有投遞、觀察、推進的最小閉環，Exec 可單獨授權 | 要同時定 Status JSON 與 Exec 的 agent 權限表面 | 首版本來只想驗原子投遞，卻把查詢與高權執行也綁成同一次發布 |
| 再加 Init | agent 可從空目錄建 world 到跑一回全自助 | 建置期與 runtime 權限混在同一 tool set，誤路徑可新建 `.aos` | 絕大多數 agent 只操作已存 world，Init 增加危險而很少用 |

**如果現在不決定會怎樣**：會擋住 skill/MCP 第一版 schema、權限面與驗收範圍；Deliver CLI 本身可以先獨立完成，其他工具後加。
**最小的驗證方式**：用一個已 `aos init` 的玩具 world，給 agent 三張逐步增加的假工具表：只 Deliver、加 Status/Exec、再加 Init；請它完成「投一批、確認、推一回」，並故意給一個未初始化目錄。記錄它何時真需要各工具，以及哪個動作應該人工批准。

