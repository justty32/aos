# llm cpu：astra 原始調查報告（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-llm-cpu-report-astra.md](../notes/2026-09-22-llm-cpu-report-astra.md)

## 結論與調查邊界

proto4-7 的 agent 把問題交給 kernel 的 llm module，module 把請求放入檔案佇列，再開獨立背景 worker 同步打 HTTP。agent 保存**結果檔路徑**，之後重新執行時查檔；結果還沒到就退 101。kernel 收到 101 只調整後續排程，不知道 agent 在等哪個檔，也沒有檔案事件喚醒。

這裡叫「LLM cpu」的 worker，**並未登記成 `K/cpus/` 裡的普通 cpu**。module hook 在 kernel 行程內跑，HTTP 才在背景 worker 跑。proto5 當時已經有 agent lib 與 CLI，think 直接同步呼叫 `aos_llm_ask.call()`；不能依 README「還沒寫」判斷現況。

原調查是讀程式、讀測試及少量純記憶體替身驗證，未呼叫真模型、未執行會寫檔或啟動 worker 的測試，也未跑 build／ctest。下列崩潰與競態窗口是從寫入順序推導，不能當作已做過故障注入。

## 最重要的 28 件事實

### 第一層：一次同步問模型

| # | 主題 | 事實與使用上的意思 |
|---|---|---|
| 1 | 設定與命名 | endpoint 的 `name` 是路由名稱，URL 叫 `base_url`；只支援 `kind:"openai"`，process 範例尚未實作。第一層 timeout 可省略，預設 300000ms；第二層必填正整數 timeout 與 `max_concurrent` |
| 2 | 固定模型 | request 必須有非空 messages 陣列，頂層只要出現 model 就拒絕。模型由 endpoint 決定，stream 固定 false；沒有逐則檢查 messages 的 role／content |
| 3 | params 的權限 | 先組 model/messages/stream，再合併 params，最後保護 model、stream。因此 `params.messages` 可以蓋掉原 messages；頂層 tools、tool_choice 則蓋過 params 的同名值。tools 只驗為陣列，不逐項驗證 |
| 4 | API key | `api_key_env` 指向環境變數；省略就不送 Authorization，變數不存在回 no_api_key，空字串仍會送空 Bearer。worker 繼承排程行程環境，key 不是從 agent request 傳入 |
| 5 | strict model | 預設先 GET `/models`，成功但找不到 model 就不送 chat；預檢失敗仍送 chat，錯誤放 notes。chat 回覆 model 必須精確匹配；關掉 strict 才兩項都略過。預檢、chat 各用一份 timeout，並非共用總期限 |
| 6 | 回應包裝 | result 有 ok、id、endpoint、model、model_requested、text、finish_reason、usage、ms、raw、notes、error。tool_calls 留在 `raw.choices[0].message`；content 為 null 可成功，缺 content 則失敗。usage 缺值用 null，不補零、不計費 |
| 7 | 失敗與退出 | error 帶 kind/msg/status/retryable；HTTP 429、5xx、連線與 HTTP timeout 可標可重試，但沒有自動重試。CLI 模型成功退 0、模型失敗仍寫 result 並退 1；輸入／用法／輸出寫入問題退 2。畸形 usage 可能直接拋例外，只有 worker 會包成 internal |

### 第二層：檔案佇列與背景 worker

| # | 主題 | 事實與使用上的意思 |
|---|---|---|
| 8 | 家與檔案 | 家內有 endpoints、state、usage、log。`requests/<id>.json` 排隊，移 `requests/running/` 執行，最後移 `requests/done/` 封存原請求；答案另在 `results/<id>.json`。state 只是 ticks／running 件數快照，實際狀態以資料夾為準 |
| 9 | ID 與 metadata | 排程 ID 來自 --name、ticket.id 或時間奈秒，不是 request body 的 id。允許英數、點、底線、減號，但不准單獨 .、.. 或以 .tmp 結尾。running 單的 `_aos` 記 endpoint、started、PID 等；worker 用檔名覆蓋 body.id |
| 10 | 一次 tick | 固定先讀 endpoints、收尾 running、驗 queued、排序、按容量派工，再寫 snapshot／log。排序是 priority 越大越先，其次 mtime，再檔名。設定整份讀壞就記 log 返回；獨立 tick 捕捉例外後仍退 0，不能只靠退出碼判斷健康 |
| 11 | 容量與公平 | 每個 endpoint 名稱有自己的 max_concurrent；同 URL 不同名稱分開算，沒有全域上限。一個 endpoint 額滿不擋其他 endpoint。沒有 queue 件數／bytes 上限、排隊期限、aging 或使用者公平配額 |
| 12 | 派工順序 | 先寫 pid:null 與 started，移 running，再開 worker，最後補 PID。worker 重新讀 endpoint 設定，同步問模型、原子寫結果、追加 usage、退出；下一 tick 才搬 done。設定沒有快照，排程與 worker 可能讀到不同版本 |
| 13 | 收尾規則 | result 只要存在就先搬 done，不解析內容；否則查 metadata／PID，無效就 worker_died。hard timeout 從 started 算 timeout 加 5 秒，只向單一 PID 送 TERM，立刻寫 timeout／搬 done；不等死、不升 KILL，且要有下一 tick 才檢查 |
| 14 | usage 不完整 | 只有 worker 寫 usage，記 token、耗時、ok 等，不記 key 或 prompt 本文。scheduler 退件、spawn 失敗、worker_died、hard timeout 都不補 usage；結果已寫但 usage 尚未寫就崩，也不補。因此不能把每份結果都期待有一筆帳 |
| 15 | 同名冪等範圍 | 獨立 submit 同名一律拒絕；module CLI／handler 才用 SHA-256 比內容，同名同內容接回舊單。指紋忽略 key 順序、空白及排程 metadata，卻不補預設值、不含 endpoint 設定。同名的舊失敗仍是失敗，不會重試 |
| 16 | 兩種部署 | 獨立模式自行 init、外部反覆 tick；module 家固定 K/llm，第一個 module tick 才建家。module 支援等結果、ls、rm。兩種都派同款 worker，llm-cpu 本身沒有常駐 loop |
| 17 | 收件與結果分兩段 | kernel CLI 先送 syscall、等 `{ok,msg}` 收件回音，時限 max(3秒,3×interval)；沒帶 --wait 也要等這段。帶 --wait 才從收件成功後另算結果等待，50ms 輪詢，不會替 kernel 跑 tick；結果逾時不取消工作 |
| 18 | 刪單不等於遠端取消 | `llm rm` 對 running worker 的 process group TERM、等 1 秒、再 KILL 等 1 秒；成功後刪 queued/running/done/result，保留 log、usage、舊快照。running 沒可殺 PID 會拒絕。沒有供應商取消 API，殺本機程序不保證遠端停止 |

### agent 與 kernel 如何接起來

| # | 主題 | 事實與使用上的意思 |
|---|---|---|
| 19 | agent 四格 | idle 一次收一個信件檔，ask 組請求，wait 查結果，act 接 assistant 並跑工具。messages 固定存在 messages.json，system 每次 ask 前置。有效新信清 errors/stuck/step，question 加一；收信按檔名排序，不看信內時間 |
| 20 | ask 交件 | agent 寫本地 request，由 helper 啟動 kernel CLI 投 syscall，不直接寫 K/llm/requests。ID 為 `<name>-e<epoch>-q<question>-s<step>`；收到接單成功後將結果絕對路徑存 state.request，轉 wait。request 不自填 endpoint、priority、timeout，使用預設設定 |
| 21 | wait 計數 | 查不到結果 1～599 次退 101，第 600 次記 timeout 回 idle，沒有撤單。600 是 agent 真正執行到 wait 的查檔次數，不是秒或 kernel tick。讀壞結果 JSON 退 1；ok=false、缺 choices 或空回答才算模型錯誤 |
| 22 | act 接回 | 正式 tool_calls 原樣接 assistant，再依序同步跑全部工具，每個接一則 tool 訊息，回 ask；純文字接 assistant 並寫 outbox，回 idle。結果檔留在 K，不消費。保存時先 messages、後 state，沒有跨檔交易 |
| 23 | 重試與 stuck | 模型／submit／文字工具修復失敗加 errors，不看 retryable；成功輪不歸零。同題累計 5 次就 stuck；未 stuck 且記憶尾巴是 user/tool 時，20 次 idle 後重問並用新 ID。步數上限預設 60，算 ask 次數。stop／reset 都不取消舊請求 |
| 24 | 工具邊界 | 每個工具經 aos-exec 同步跑、timeout 60 秒；參數只做 JSON 正規化，不驗 schema。非零退出、未知工具與壞參數都寫成 tool content，不加 errors。stdout 全收後才按字元截斷，預設 8000；普通工具 cwd 是工具目錄，內建 sh 才自行切回 agent 根 |
| 25 | 文字工具修復 | 只處理指定標記開頭或整段 JSON，取一個含 name 的物件，且名稱必須已知；成功只救出一個 call。不是完整 XML parser，也不會直接從 function 標籤取工具名。救不回才計模型錯誤 |
| 26 | module 分派 | modules 設在 K/config.json，hook 直接在 kernel 行程跑。tick 先處理 syscall，再跑 module.tick，再排普通 cpu，所以可同回合收 LLM 單並派工。module 重名或 OPS 重疊不拒絕，取第一個認領者 |
| 27 | syscall 回音 | 原單與 done 回音靠相同檔名關聯，回音固定只有 ok/msg。kernel 先寫回音、再刪原單；回音寫失敗仍可能刪原單，刪原單失敗則可能重讀。第一個 kernel tick 前送 LLM，可能因 llm 家還沒建立先被拒 |
| 28 | 101 的意思 | agent 已退出，不是 OS suspend。kernel 從 daemon 最新快照看見 wait_exit，記 waiting；有人排隊就讓位，沒人就留 cpu 繼續定期跑。101 不算一般非零錯誤；kernel 不保證看見中間每次退出。移除 agent 的普通排程也不會取消已送出的 LLM 工作 |

## 會影響可靠性的窗口

| 中斷／競態 | 可能後果 |
|---|---|
| worker 已開，PID 還沒寫回 | 下次 tick 誤判 worker_died，原 worker 仍可能寫結果；若只是移 running 尚未開 worker，則判死且不重送 |
| hard timeout 已記失敗，worker 尚未終止 | worker 之後可能回寫同一結果。預檢與 chat 各可耗一個 timeout，scheduler 卻只給一個 timeout 加 5 秒 |
| CLI 收件逾時刪 syscall，kernel 已讀入記憶體 | 刪單成功也不代表沒有送出；原單沒有先被 rename 認領 |
| 兩個 tick／兩份 agent 同時跑 | 沒有鎖，會競爭 request、running、state、messages、outbox 與暫存檔 |
| 信搬 read 後、messages 尚未存 | 信不在未讀匣，沒有從 read 自動重播的機制 |
| ask 已收件、wait state 未存 | 重跑可能用同 ID 接回既有單；但 system/messages/tools 變了就指紋撞名，並非所有重入都安全 |
| act 工具已跑、messages 或 state 未存完 | 工具可能重跑，assistant/tool 可能重複；純文字 outbox 也可能重發。單檔 tmp/replace 無法保證整輪一次完成 |

## 文件跟程式對不上的 10 件要事

| # | 文件說法 | 實際情況 |
|---|---|---|
| 1 | proto5 agent 還沒寫，lib 模組仍是五支 | agent lib／CLI 已在，think 正在同步 call；lib 已有第六支模組 |
| 2 | 沒有取消 | 有 llm rm 殺 worker／刪單，以及收件逾時嘗試撤 syscall；仍不等於遠端取消 |
| 3 | 每一發都 append usage | 只有 worker 寫，scheduler 生成的終局沒有 usage |
| 4 | notes 是結果通用欄位、逾時都可重試 | scheduler 自產 error 沒 notes；hard timeout 的 retryable 是 false |
| 5 | syscall 原單還在，撤掉就代表沒送出 | kernel 可能已讀入，CLI 成功刪檔仍阻止不了排入 |
| 6 | kernel 沒活著就撤單、不排隊 | CLI 只用回音逾時推測；同名同內容甚至不送新 syscall，也不撤已有單 |
| 7 | call 永遠回 result | 畸形 usage detail 可拋 AttributeError，直接 CLI 沒總括捕捉 |
| 8 | agent 連錯五次／每題格數上限 | 實際同題累計五次，成功不清零；上限只算 ask 次數 |
| 9 | 工具名對不上就是模型錯誤 | 文字修復才如此；正式 tool_call 的未知工具回 tool content，不加 errors |
| 10 | 所有 JSON 都 tmp/rename | agent 的主要檔案如此，ask helper 的臨時 request 卻直接 write_text |

## 測試證據、建議與待拍板

| 證據 | 已知範圍與限制 |
|---|---|
| proto4-5 共 64 個測試方法 | 涵蓋第一層、建家、worker、priority／容量、timeout、module 收件與冪等、管理刪單；使用假 OpenAI server 與暫存家。本次只讀碼與統計，沒有宣告執行全綠 |
| proto4-7 共 31 個測試方法 | 涵蓋四格、600 次、第五次錯誤、20 次重試、工具、user CLI；fake kernel 複製請求，測試人工寫結果，不是實際 kernel→worker→HTTP 全程測試 |
| kernel 與純記憶體驗證 | 既有測試涵蓋 101 有／無競爭的排程；本次替身確認 params.messages 覆蓋及畸形 usage 例外。崩潰窗口未做故障注入 |

原始 astra 報告只調查事實，**沒有提出拍板題或 Claude 方案**。proto5 的方案、六道選擇題及 Claude 的建議另見 [llm cpu 總結精簡版](2026-09-22-llm-cpu-summary.md)；不要把這份對 proto4 的描述視為 proto5 已決定的設計。
