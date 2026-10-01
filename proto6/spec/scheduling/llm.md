# LLM module 與 endpoint 池

← [node 樹與資源](README.md)｜[工作與 unknown](runs.md)

## S-301．三檔、池 node 與 quota scope

〔使用者方向 2026-09-30，第十八批〕**LLM 池是預設 kernel 範本的一種資源**，不是 aos 寫死的特例：本篇的三檔、兩條路線、份額、窗口、重試與 unknown 占用，都是預設範本的規則；kernel 可以不裝，也可以登記自己的任務種類與資源名稱另管（[T-06](../terms.md)）。LLM 池是「外部計算」（Linux 管不到的計算）的第一個實例；其他外部計算由各 kernel 以資源任務自訂，通用的外部資源池介面延後（[P-008](../protocol/README.md#p-008)）。

〔使用者方向 2026-09-29 晚〕LLM 呼叫分三檔，用兩個欄位切換：agent 設定的 `llm.target_node`，加上池設定裡每個池的 `schedule`。

| 檔 | 怎麼設 | 誰打 HTTP、誰管限流 |
|---|---|---|
| **自己排**（預設） | `llm.target_node` 填 node id；池的 `schedule` 為 `aos`（省略即此值） | 池 node 代發；aos 自己藏 key、限流、記帳、排隊 |
| **交給 endpoint** | 同上，池的 `schedule` 為 `endpoint` | 池 node 底下一件轉發任務把請求轉給外部 endpoint，只轉發；aos 只藏 key、記用量，429、限流、重試與額度全交給 endpoint |
| **直連** | `llm.target_node` 填 `null` | agent 自己打 endpoint，不經池；aos 完全不管（不限流、不排隊、不管串流） |

預設且首先實作的是「自己排」；另兩檔是可選項，之後再做。LiteLLM 不在標準內，只是「交給 endpoint」可以指向的一種 endpoint，和原廠 API、本機模型伺服器同級。多 endpoint 自動切換首版不做：一個池對一個 endpoint，要自動切換的人拿 LiteLLM 之類當 endpoint。

〔使用者方向 2026-09-29 晚〕**直連**（第十五批由「不管」改名，避開 kernel 份額路線的「kernel 不管」）：agent 自己打 endpoint，aos 完全不管。endpoint 是哪個、key 放哪、怎麼讀，都是 agent 自己的事，spec 不定義。**直連藏不住 key**：key 一定要 agent 的帳號讀得到，選這檔就是接受這點。

**池就是一個 node**〔使用者方向 2026-09-29 晚〕：不是另外的資料夾契約。agent 的某個任務遇到要呼叫 LLM，就把檔案承載的 JSON-RPC（`llm.chat`）投進目標 node 的 `requests/`，然後結束，tick 繼續跑下一個任務；這和「要別的 node 做事」的一般做法相同。對 agent 來說「自己排」和「交給 endpoint」完全一樣，差別只在池 node 裡裝的任務。回覆送到哪（請求的 `reply_to`）、串流寫到哪（業務 JSON 的 `stream_path`，見 S-305）都寫在請求裡，池照請求上寫的送。

〔使用者方向 2026-09-29 晚，第十五批〕投件照一般規則（[B-624](../settled/deferred/mq.md)）：只查目標是不是一個 node，不是就在投件那一步報錯（沒有寫入權限也一樣：報一次、丟掉待送檔），不寫待辦、不重試、不自動建池（`aos node new` 也不建池）。是 node 就投進去，之後分兩種情況〔第十八批補〕：

- **對方沒被 tick**（沒登記、暫停或停格）：請求堆在對方收件區。投件者可以設鬧鐘（`alarm_ms`），時間到了原件還在就報錯。
- **對方有 tick，但任務表裡沒有任務宣告 `llm.chat`**：tick 回 -32601 並清掉原件（[B-501](../base/transport.md)、[B-620](../settled/tick.md)）；原件已被取走，鬧鐘不會響，投件者收到的是 -32601 回應。

收件區、回覆檔、串流檔、key 的讀寫權限 aos 不安排，沒給權限就在投件時報錯（設定檢查不先擋，見 [P-701](../protocol/agent-tasks.md)）。〔使用者方向 2026-09-29，第十六批〕**LLM 結果回來就是投進 agent 的 `responses/` 收件**，跟其他收件一樣由所屬 kernel 看到後叫醒 agent（[P-305](../protocol/messages.md)、[P-803](../protocol/kernel-tasks.md)），不另設機制；串流檔（S-305）則不叫醒。池 node 裡誰收 `llm.chat` 見本篇 S-307。

〔使用者方向 2026-09-29〕kernel 的 LLM module 分配成員份額與執行機會；**每個池 node 的代發任務保管該池 key，處理真正共享的 provider 限制**。頂層或下層 kernel 都可以有自己的池，不要求全機只有一個池。〔使用者方向 2026-09-30，第十八批 方向 3、5；astra 核對第 1 項改正〕同一 provider 帳戶／模型的限制要**集中**在一處計數、還是**分片**由各池自管，由 kernel 決定，spec 不強制全機只有一個計數處。kernel 選擇把多個池當同一個共享限制時，才用同一個 `quota_scope`、交同一個池 node 統一分配序號、在途占用及冷卻，不能各開一份計數繞過它；不同 node 的同名 scope 不會自動共享計數（技術限制：計數存在各自的 node 裡）。〔使用者方向 2026-09-30，第十八批〕**上層的 LLM 份額只對經上層轉交的請求有效**；下層自建的池、或 agent 直投別的池 node，不受上層份額約束（上層頂多用用量收集事後看到）。下層沒裝 LLM module 只是不再細分；池端的共享限制照樣有效。這是上下層不必對齊的一例（[T-06](../terms.md)）。

〔使用者方向 2026-09-29；第十八批由 P-813 搬來〕`llm.target_node` 是 node id 時，`llm.chat` 的 params 是 `aos llm chat` 的 inst。開 agent 的 kernel 選兩條路線之一；這兩條路線講的是份額怎麼走，和上面三檔是兩回事。請求／結果格式相同（[P-406／407](../protocol/llm-work.md)），結果下次 tick 收：

| 工作 | kernel 全管 | kernel 不管 |
|---|---|---|
| LLM | `llm.target_node`＝本 kernel，裝 forward（[P-809](../protocol/kernel-tasks.md)），配本層 route／份額；由 forward 扣額度、排隊並交本地池或另一 kernel | `llm.target_node`＝管池的 node，直接授雙向投件權；池 node 自己收件（S-307） |
| 工具 | `tools.target_node`＝本 kernel，裝 work，代掛 once（經通道 `node.mount`，上層填成員，[P-402](../protocol/work.md)） | `tools.target_node`＝null，agent 自己掛 once，上層是 agent 自己 |
| 用量 | 由代辦 module 記，agent 記錄供核對 | agent 自記，父 kernel 裝 usage-collect 讀（[P-810](../protocol/kernel-tasks.md)） |

兩種工作可分別選路線。範本欄位怎麼填見 [kernel P-813](../protocol/kernel-tasks.md)。

**key 保護**〔使用者方向 2026-09-29；第十八批改窄〕：key 不放進請求、prompt、結果、inst、argv 或給成員的環境（格式約定見 [P-405](../protocol/llm-work.md)）。讀取權的界線是 OS 帳號：

- **投件權就是執行權，而且會傳遞**（[T-08](../terms.md)）：能投件給持 key 的池 node，就等於能用池的身分讀 key；A 能投給 K、K 能投給池，A 也一樣。所以 key 保護**只對整條投件鏈以外的帳號成立**。
- **沒有 root helper、代發與 agent 共用帳號時，key 不受保護**（第八批）；使用者接受這個界線。私有憑證檔放在 node 樹外也不算隔離，同 UID 仍讀得到。
- 〔建議預設，未拍板〕要保護 key，須用 helper 配合身分隔離，或另用不同帳號跑代發、限制 key 的讀取權限；代發任務用池 node 的帳號跑，與成員帳號分開（第九批），而且這些成員不在能投件給池的鏈上。身分權限依 [身分與 OS 資源](../base/identity-resources.md)。
- 直連檔藏不住 key（見上）。

請求參數及輸入材料見 [LLM 代發 P-406](../protocol/llm-work.md)。共享限制按 provider 的實際帳戶／模型關係判定，不把不同 URL 當作必定獨立。

驗收：同一份 agent 請求經自己的 kernel 轉交或直接交池 node，wire 格式不變（P-406／407）；轉交不能靠改 pool 名跳過份額（份額扣在 route 名上，S-302）；共用同一 `quota_scope` 的池遇 429 後一起冷卻（S-303）。路由成環回 `routing_loop`、來源未授權回 `work_not_authorized`、在途請求不改投別站（S-307）。kernel 把多個 endpoint 當同一共享限制（同一 `quota_scope`）時，由同一池 node 一起限流，不能換個 URL 就繞過；kernel 選分片時各池自管，不同 node 的同名 scope 不共享計數。有身分隔離的部署中，不在投件鏈上的帳號讀不到池 key；能投件給池（直接或經 kernel 轉交）的帳號不算在保護範圍；同帳號部署與直連不得宣稱保護了 key。投給不是 node 的路徑、或沒有寫入權限，當場報一次錯、丟掉待送檔、不重試。投給沒被 tick 的 node，請求留在對方收件區、不產生待辦，設了鬧鐘的到期後報錯；投給有 tick 但沒任務宣告 `llm.chat` 的 node，收到 -32601、原件被清、鬧鐘不響。下層自建池的請求不扣上層份額。

## S-302．預留與結算

〔使用者方向 2026-09-29〕kernel 只在已分到的份額內安排工作；池服務在真正送出前核對自己的共享限制。兩者不承諾跨 repo 一次同時占齊額度。請求提交與收件流程依 [tick](../settled/tick.md)，git 還原不會撤銷已送出的 LLM 呼叫。

〔建議預設，未拍板〕以請求 ID、必要的送出狀態及結果／usage 檔核對一次工作；同 ID 重收依[傳遞](../base/transport.md)，結果重複處理依 [C-03](../contracts.md)；去重承諾只涵蓋[儲存](../base/storage.md) 規定的保留期。只保存分配摘要及限流真正需要的窗口／用量。估算 token 要標明是估算；實際 usage 可得時照實記，不能因輸出短就假設 provider 已退還先前算過的速率額度。

〔建議預設，未拍板；第十八批由 kernel P-809 搬來〕**份額扣在誰身上**（kernel 轉交時，[P-505](../protocol/resources.md) 的成員份額）：直接成員扣自己的份額；代理成員扣 via 的本層份額；明授的外部池客戶不扣本層份額，只受池的共享限制。還沒結束的請求與 unknown 各占一份，unknown 何時還依 S-304；429 重試不多占一份。額度不足就排隊（queued），unknown 不重送。

〔建議預設，未拍板；第十八批由 kernel P-811 搬來〕**池的共享窗口**（預設範本的規則，只套「自己排」`schedule:aos` 的池；「交給 endpoint」的池不做窗口與並行）：

- 每個 quota scope 有並行上限、固定窗口長度、每窗口請求數與每窗口 token 數（欄位見 [kernel P-811](../protocol/kernel-tasks.md)）。kernel 選擇集中計數時，共享同一 provider 限制的池須同 node、同 scope，改名不代表獨立；選分片時各池各算（S-301）。
- **窗口**：該 scope 第一筆預留時開一個固定窗口，到期重設。時鐘倒退不提早釋放；重啟依已保存的證據重建，不能證明窗口已過期，就再等一個完整窗口。
- **預留**：每次 HTTP 嘗試（各有自己的 attempt）預留一個請求，同一 attempt 只算一次；已預留未啟動的也算在途。token 用估算：messages 與 tools 的 JSON UTF-8 bytes 加 `max_completion_tokens`，不保證是 tokenizer 的上界。
- **放不放行**：單筆請求本身就超過 scope 上限，拒收（`capacity_unavailable`，[P-404](../protocol/work.md)）；窗口滿、並行滿或冷卻中就等。
- **結算**：provider 回的 usage 原樣保存，不因實際少用 token 就退還窗口預留。

HTTP 無結果又不能證明未送出，就標 unknown，不自動再呼叫或把用量歸零。可證明未送出的工作才可立刻撤掉本次占用，後續是否重試仍依工作政策；unknown 的占用何時釋放見 S-304。

〔使用者方向 2026-09-29 晚〕LLM 預算首版只算 token。要算錢的部署可另備一份價格表（每個模型每千 token 多少錢），這份檔是可選的、由人手維護，aos 不自動上網抓價格。〔使用者方向 2026-09-29 晚，第十五批〕**token 預算先不做**：首版 LLM 只有並行份額（[P-505](../protocol/resources.md)），以後做預算時才照上面只算 token，見 [S-203](admission.md)。

驗收：請求提交後、取得結果前當機，能證明未送才可釋放本次占用；可能已送則留 unknown，不發第二次。重複結果只計一次。

## S-303．限流與可重試失敗

〔使用者方向 2026-09-29〕限流允許少數幾次重試。〔使用者方向 2026-09-29 晚，第十五批〕本條只適用「自己排」（`schedule:aos`）的池；「交給 endpoint」的池只轉發，429、限流與重試全交給 endpoint，aos 不重試。〔建議預設，未拍板〕LLM 每件工作預設最多 3 次嘗試，可設定其他有限值。429 或 adapter 明確判定請求未被處理的限流回應，保留本次失敗證據後可重試；即使一般政策不重試，也適用此例外，所有嘗試仍計入上限，達上限即失敗。其他不明確的 5xx、逾時或送出後斷線不適用；可能已執行者依 S-304，不自動重送。

重試不得早於有效 `Retry-After`；沒有提示則退避 `min(60000, 1000*2^(n-1))` 毫秒（n 是本工作剛完成的第幾次嘗試），加 0～250 毫秒 jitter，保存下次到期時間。同一共享限制的請求遵守冷卻，獨立池／限制不連帶停住。SDK 內建重試須停用或納入同一嘗試上限，不能暗中增加次數。

授權、帳務與無法執行的輸入錯誤不無限重試；明確未送出的連線建立失敗可按原工作政策重試，不混成 429 例外。

驗收：預設工作連續收到 3 次 429，共送 3 次且每次符合到期時間，之後失敗；獨立限制的其他工作仍可前進。改成不明確 500 或送出後斷線，不套用限流例外。

## S-304．取消與不確定性

〔使用者方向 2026-09-29〕once 的取消規則以 [B-203](../base/execution.md) 為正本（在跑的經通道砍掉，[B-613](../settled/deferred/daemon/channel.md)）；〔使用者方向 2026-09-30，第十八批〕LLM 請求的取消延後（[P-008](../protocol/README.md#p-008)），目前範本只有 kernel 的 work 任務收 `work.cancel`。已送出後關掉本機連線，不代表遠端停算。重啟的程序收尾依 [daemon](../settled/daemon/README.md)，不明結果依 [S-401](operations.md) 放著、不自動重做。完整結果才可成功，部分輸出不是完成證據；串流寫出的片段也只是過程（S-305）。〔建議預設，未拍板；第十九批依方案 A 由 llm-work P-407 搬來〕**結果怎麼判**（欄位見 [P-407](../protocol/llm-work.md)）：收到完整但格式不合或驗不過的回應（含非空 refusal）記 `response_invalid`，保留無 key 的證據，不自動再問、也不當空白成功；傳輸中斷或遠端結果不明記 `unknown`；串流中途斷掉不算完整回應。`finish_reason` 是 `length` 表示模型輸出達上限，不能當產品任務完成（[A-503](../agent/README.md)）。

〔第十八批補，建議預設，未拍板〕**兩個計數分開算**：

| 計數 | 是什麼 | 何時還 |
|---|---|---|
| 本機連線名額（池狀態的已知占用） | 這台機器上正在跑的 `aos-llm-call` HTTP 連線 | 本機 HTTP 確定關閉（程序結束、結果寫出或確認全空）就還 |
| 池的 unknown 份額 | 遠端可能還在算、占著 provider 限制的請求 | 〔暫定，使用者未答；選項：a 到 `timeout_ms` 到期／b 固定時間／c 預設不占，照 a〕預設從送出起算到該請求的 `timeout_ms` 到期後還；池所屬 kernel 可用 `unknown_hold_ms` 改（`0`＝不占，欄位在 [kernel-llm-limits](../protocol/kernel-tasks.md)，暫定放在那裡） |

兩者都算進 `concurrent_requests` 的占用，但分開記、分開還，不能互相抵。unknown 份額還了只表示不再占名額，結果仍是 unknown、不重送；資料保留另依 [P-606](../protocol/ops.md)，不再綁「隨定期清理才釋放」。kernel 轉交時扣的成員份額（[P-505](../protocol/resources.md)），unknown 的那份預設也照這個時間還。設定欄位的格式見 [kernel P-811](../protocol/kernel-tasks.md)。

驗收：遠端可能已完成而斷線，本機取消或重啟都不自動再問；可查 unknown 與不明用量，不能偽裝成零成本失敗。斷線後本機連線名額立刻還、unknown 份額到 `timeout_ms` 才還，兩個數字在池狀態裡分開看得到；unknown 份額還了以後工作仍是 unknown。

## S-305．串流〔使用者方向 2026-09-29 晚〕

（09-29 曾刪除；第十三批恢復，推翻首版「只收完整結果」。）

串流不另做機制。一次 LLM 呼叫就是掛在 tick 上的一件任務（池派出的 once 工作），它跑的時候直接打 HTTP；所謂串流，就是這件任務在跑的過程中，把收到的內容不斷寫進請求指定的檔案（`stream_path`，格式見[LLM 代發 P-406](../protocol/llm-work.md)）。沒指定就不串流。

中途斷線 aos 不管；頂多這件任務以非 0 結束、在 stderr 印錯，不必另補結果；沒有結果就照 [S-401](operations.md) 的證據規則處理。〔使用者方向 2026-09-29 晚〕stream_path 在送出 HTTP 前就開不了（沒權限、父目錄不在）時不送，結果記 failed／not_sent。結果照 S-304：只有完整結果才算成功，串流檔寫到一半不算；斷在送出後就是 unknown。串流檔誰能讀、寫好了誰叫醒 agent，aos 不管（完整結果照 S-301 投進收件區、照一般收件叫醒）。〔使用者方向 2026-09-29 晚，第十五批〕中斷後重試時串流檔怎麼寫不另規定，由任務自然處理。直連由 agent 自己打 endpoint，串流也由它自己處理。

驗收：指定串流檔時，呼叫途中檔案持續變長，最後的結果檔照常是完整結果；中途斷線時任務非 0 結束、stderr 有錯，結果不被當成成功。

## S-306．有限的 run 預算

（09-29 重寫：已刪；可選額度併入 [S-203](admission.md)，不足時的取消／可選 resume 見 [S-102](runs.md)。）

## S-307．池 node 的任務與收件〔建議預設，未拍板；第十八批補〕

**誰收 `llm.chat`**：由任務表裡宣告 `llm.chat` 的那項任務收件（[B-620](../settled/tick.md)，同一 method 只能一項任務宣告）。兩種部署：

| 部署 | 誰宣告 `llm.chat` | pool 任務（`aos-llm`）怎麼拿到請求 |
|---|---|---|
| 完整 kernel 範本（裝 forward＋pool） | forward（[P-809](../protocol/kernel-tasks.md)），核對路由與份額後接納 | 不宣告；讀同 node forward 已接納、已提交的材料派送 |
| 純池 node（只裝 pool，不裝 forward） | pool 自己 | 直接收 tick 交來的收件，核對池設定與共享限制後接納 |

同一支 `aos-llm` 兩種都跑：任務宣告了 `llm.chat` 就讀收件，否則讀 forward 的材料。agent 直投管池 node（S-301 的「kernel 不管」）與 kernel 轉交到別的池 node，收件的都是純池 node。兩者都沒有任務宣告 `llm.chat` 時，tick 回 -32601（S-301 第二種情況）。

**aos-llm 怎麼派**〔使用者方向 2026-09-29 晚〕：aos-llm 是短任務：收件（或讀 forward 材料）、核對共享限制、派送、收結果便退出。它為每個實際 HTTP 嘗試建 [P-402](../protocol/work.md) 的 once 資料夾，把本池那一項設定（只含 `key_ref`，不含 key）固定成 `W/llm-config.json`，inst 跑 `aos-llm-call --work-dir <絕對工作資料夾> --config <W/llm-config.json 的絕對路徑>`，用池 node 的帳號。〔使用者方向 2026-09-30，第十九批〕提交後，由下一格 `aos-llm` 經通道用 `node.mount` 把這份 inst 掛到 daemon（用 `AOS_DAEMON_SOCKET`、`AOS_TICK_TOKEN`，不帶 `parent_id`，資源歸池 node 自己，不帶 `identity_grant`；[B-613](../settled/deferred/daemon/channel.md)）。〔記錄者依追答 11 歸類：不在 daemon 底下的 tick，要通道的事一律算功能受限、不另設替代路〕池 node 不在 daemon 底下（cron 或人手跑）時沒有通道，`aos-llm` 掛不了 `aos-llm-call`，照 [P-408](../protocol/work.md) 報 `no_channel`、回 125（〔暫定〕），已提交的材料留著等下次有通道的格；不另設池自己直接跑 `aos-llm-call` 的路。HTTP 等待由這支掛載行程承擔，不占 node 的 tick。結果放工作資料夾，由後續池 tick 收齊這件請求的所有嘗試、按序組成 llm.chat 的 stdout JSON 後回件（格式見 [P-407](../protocol/llm-work.md)）；LLM 工作沿用 once 的清理與恢復界線。

**轉交**〔第十八批由 P-406 搬來〕：轉交 kernel 可把請求映到下一個 node 的 pool；model 原值沿路核對，終點才核對實際池設定。轉交仍用 `llm.chat`，不增加另一種 wrapper；保留原 node_id、job_id、attempt_id，另配轉交 RPC id 與 `reply_to`，由轉交者保存上下游關係。收到結果後沿用 stdout 的業務結果，以本 node 及原 RPC id 組成自己的指令結果回覆，不照抄下游指令識別。`stream_path` 沿路原樣保留，由最後實際打 HTTP 的 `aos-llm-call` 寫。agent 配對的可信回件來源始終是設定目標。

**轉交的路由與授權**〔第十九批依方案 A 從 kernel P-808 搬來；路由表格式見 [kernel P-808](../protocol/kernel-tasks.md)〕：
- **授權**：請求的來源（原發起者、明授的投件者或代理）不在該路由允許的來源內，回 `work_not_authorized`；依部署權限驗來源，共 UID 不宣稱隔離。找不到路由回 `pool_not_found`。
- **不成環**：路由配置不得成環；同一 origin／job／attempt 又回到本 node，報 `routing_loop`、不再轉交。
- **在途不改投**：接納時保存必要的路由與請求材料，在途的請求不因路由表之後改動而改投別站。

**重試的派出**〔第十八批由 P-407 搬來〕：轉交中間層只轉送、保存同一組結果，不重新計一次 HTTP、不自行再做 provider 重試。限流重試前，由池 tick 固定新 attempt ID 與前次結果、提交後才派出；後續 ID 由這條已提交關係核對，不必假裝仍是第一個 attempt。

**設定路徑**：任務表裡 `aos-llm --config` 的相對路徑依呼叫時的 cwd 解（tick 裡就是 node 根），範本寫 `config/llm-pools.json`；aos-llm 每格直接開這份檔，改了下一格生效，已派出的嘗試照它的 `W/llm-config.json`。

驗收：純池 node 只裝 pool 且宣告 `llm.chat`，agent 直投能收到結果；完整範本由 forward 收件、pool 不宣告；兩者都沒宣告時投件者收到 -32601。改 `config/llm-pools.json` 後，已派出的嘗試仍用派出時的設定。
