# LLM cpu 舊遺產盤點

這份只回答「以前怎麼做、這次撿不撿」。現在的邊界以 proto4 §21 為準：LLM cpu 是普通 cpu 反覆執行的一支排隊／分發程式；它只收請求、排序、派 endpoint、收結果，不跑 agent 迴圈，也不執行工具。

## 1. 各來源總覽

- `proto/`：把 LLM 做成一塊獨立的「地」，有收件匣、同步 `serve_once`、inflight／done、指定結果落點與 JSONL 帳簿；它本來就是玩的原型，且 FINDINGS 明寫 LLM 的圈與 `aos run` 的格是兩套，沒有接起來，後來被另起的 proto2 放下。
- `proto2/`：把 LLM 做成平鋪資料夾；短 tick 排程、背景 worker 打 endpoint、後續 tick 收尾，做到多引擎、並發、排分與 usage；後來骨幹膨脹成大量補丁，`aos-llm` 又把派工與四種介面塞成 1793 行，使用者改開 proto3 重寫骨幹。
- `proto3/`、`proto3-1/`：只在記憶體模擬一個有 FIFO 佇列與自己時鐘的 LLM 世界；沒有真 endpoint、磁碟與崩潰恢復。`proto3-1` 只是把世界改成可 eval 的 form，之後又往 proto3-2／proto4 的「檔案就是程式」走。
- `proto3-2/`：只補了同步 engine 的 agent form，明說之後才改成非同步 LLM 世界；沒有 LLM 排隊／endpoint 實作，隨後方向走到 proto4。
- `proto4-1/`、`proto4-2/`：grep 沒有 LLM／endpoint／DeepSeek 相關；只提供普通 cpu／kernel 遺產。`proto4-2` README 明標已被 proto4-3 取代。
- `reference/llmkit/`：是已定型的單發 OpenAI 相容 client、Reply／usage 正規化、preset 與可選 LiteLLM proxy；它沒有被放下，但刻意不管 queue、retry、logging、CLI、工具執行，正好可當 endpoint adapter 參考。
- `core/llm/`：定了 C++ `Message`／`Options`／`complete()`、OpenAI 相容非串流呼叫，以及以 `flock` 做的同步槽位／優先等待；README 沒寫為何放下，現方向則已改成由資料夾型 LLM cpu 集中排隊，不宜直接拿呼叫端搶槽當主架構。

## 2. 逐題比對

### (a) 請求長什麼樣

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | 投遞物是 JSON：系統補 `id/from/at/kind`，呼叫者給 `prompt` 檔、`result` 路徑、`tier`、整數 `priority`、`max_wait_ms`，可帶 `tools`；model／endpoint 在 unit 設定。 | 改採：保留 JSON 檔、id、messages、優先級；不採 prompt 與任意 result 路徑，改用同檔名結果，避免相對路徑基準與越界問題。 |
| proto2 | `requests/<名字>.json`；頂層原本就是 chat/completions body，另吃 `priority/requester/engine/params`，model 由 engine 固定，結果同檔名。 | 採：最貼近 v1；最小只要求 `messages`，檔名就是 request id，endpoint／priority／timeout／max_tokens 都可選。 |
| proto3 系 | 記憶體物件 `{id, from, messages, status, at}`，`ask` 的人直接塞進 queue。 | 改採：欄位夠小；改成磁碟 JSON，狀態不讓呼叫者物件原地突變。 |
| proto4-1/2 | 沒有 LLM 請求格式。 | 不採；只沿用普通 cpu 的 inst.json 外殼。 |
| llmkit | 沒有 queue 請求；`Bot.ask` 組 system/history/tool results，`LLM.think` 送 `model/messages/tools/tool_choice/params/stream`。 | 改採：只撿 OpenAI body 的組法；Bot/history/tools 屬 agent，不進 LLM cpu。 |
| core/llm | CLI 從 stdin 收單一 prompt，或讀 messages 陣列檔；url/model/timeout 是呼叫選項，沒有 request id 與回件位址。 | 不採作 queue 契約；可參考嚴格 messages 解析。 |

### (b) 排隊與排序

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | `(priority, at, id)` 升冪，等於數字小先；`max_wait_ms` 只管送出前；一格同步處理至全域／unit 的筆數上限。 | 改採：保留排隊上限概念但先做可選；優先級改成數字大先、同分 FIFO，避免語意反直覺。 |
| proto2 | 每格重排：過 deadline 先，再算 level、kind、久等、費用、近期占用；每啟動一筆再重算，派到各 engine 滿載為止。 | 改採：只留「每格重排、滿的 endpoint 不擋別台」；v1 不搬 deadline／kind／費用／公平分數。 |
| proto3 系 | 純 FIFO；一格最多 `max-per-tick` 筆，而且同步做完。 | 採 FIFO 當同優先級 tie-break；不採同步做完。 |
| proto4-1/2 | 沒有 LLM queue。 | 不採。 |
| llmkit | 沒有排隊。 | 不採。 |
| core/llm | 槽滿時在呼叫端等，數字大先、同級先到先得；超過 `wait_ms` 回暫時失敗。 | 改採排序語意；不採「很多呼叫端各自 flock 等」的分散式 queue。 |

### (c) endpoint 怎麼描述、怎麼挑

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | `units[]` 每筆有 name、endpoint、model、tier、max_parallel、timeout_ms、api_key_env；依 tier 找第一台，找不到會退回第一台。 | 改採欄位；不採靜默 fallback，名字不認得就產 error。 |
| proto2 | `engines.json` 陣列；一台有 name/api/base_url/model/params/max_concurrent/api_key_env；請求指定 engine，否則 defaults／第一台，沒有輪流分流。 | 採：endpoint 名稱映射設定、每台各有容量；v1 也不做輪流或自動選最便宜。 |
| proto3 系 | engine 只是一個同步函式，沒有設定檔與多 endpoint 選擇。 | 不採實作；只留「排程器不懂模型內容、只叫 adapter」的分層。 |
| proto4-1/2 | 沒有 LLM endpoint。 | 不採。 |
| llmkit | preset 精簡成 id → endpoint、model、parameters；也可用 proxy 把 model 名映到上游。 | 採前半：endpoint＋model＋params；v1 不採 LiteLLM proxy 與能力資料庫。 |
| core/llm | url/model/key/timeout 是 Options；`engine` 只選槽名，不負責 url 映射。 | 改採 Options 的小介面；設定必須把 endpoint 名與連線資料放在同一筆。 |

### (d) 在飛中怎麼跨格記（最重要）

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | 送出前原子搬到 `llm-inflight/`，但同一個 `serve_once` 仍原地等 HTTP；重啟看到 inflight 就標 `result_unknown`，絕不重送。 | 採「先標在飛」與「結果不明不重送」；不採 tick 自己等數十秒。 |
| proto2 | tick 把請求搬到 `requests/running/`、記 engine/pid/started，開脫離的 worker 就返回；worker 原子寫 result、usage 紙條、done marker；後續 tick 依 pid／marker／result 收尾，死掉補 `worker died`。 | 採，這是最符合普通 cpu 短格的遺產；v1 應縮小欄位與 adapter 數量。 |
| proto3 系 | 同一格把 pending 改 running、同步呼叫、再改 done/failed；全在記憶體，進程死掉全失。 | 不採；沒有真正跨格。 |
| proto4-1/2 | 沒有 LLM inflight；普通 cpu 的一次子行程跑完前不能搶佔。 | 只當限制：不能讓 tick 本身握著 HTTP。 |
| llmkit | 一次呼叫的狀態只在 Python 物件／串流連線；中途斷線變 Reply.err，沒有磁碟恢復。 | 不採生命週期；adapter 可用它完成 worker 內的一發。 |
| core/llm | 槽由同步呼叫行程持有，行程死鎖自動釋放；沒有 request 的 durable inflight。 | 不採作跨格方案。 |

### (e) 結果怎麼回

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | 成功把純文字寫到請求指定的 result；失敗寫 `<result>.status.json`；原件歸檔，呼叫者用 await 看檔。 | 改採檔案完成訊號；不採任意落點與成功／失敗兩種檔形。 |
| proto2 | `results/<請求同名>` 放整包 JSON，呼叫者 poll；helper 預設讀完刪，原請求搬 done。 | 採同名結果；建議結果先保留，由呼叫者明確清理，別預設讀完即刪。 |
| proto3 系 | 寄 `{kind: llm-result, id, reply, error}` 到 requester inbox。 | 不採回件匣；目前 lisp 已能 `:read`＋`:json`，同名結果檔更直接。 |
| proto4-1/2 | 沒有 LLM 結果；proto4-2 daemon request 的 done 檔曾沒有好用的回覆通道。 | 不採。 |
| llmkit | 統一 Reply：text/calls/reasoning/finish_reason/usage/err，串流與否同形。 | 採欄位正規化；calls 不執行，原樣當資料回給之後的 agent。 |
| core/llm | stdout 只印 content，錯誤走 stderr＋exit code。 | 不採作資料夾協定；資訊太少，也不利跨格 poll。 |

### (f) 帳簿

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | 全域 `ledger.jsonl` 每發一行：時間、request/from/unit/tier、輸入／輸出／思考 token、來源、毫秒、outcome。 | 採一發一行與 reported/estimated；路徑改放 LLM cpu 自己家。 |
| proto2 | worker 先寫 `usage/pending/` 紙條，tick 折進每日 JSON；按 model 與 requester 累加，所有數字欄攤平。 | 改採單一 writer 的 pending 紙條；v1 先留逐發 JSONL，不做兩張聚合表與工具成本分攤。 |
| proto3 系 | 只按 requester 累加呼叫次數。 | 不採，資訊不足。 |
| proto4-1/2 | 沒有 LLM 帳簿。 | 不採。 |
| llmkit | usage 正規化成 prompt/completion/total/cached/reasoning，缺值留 null；自己不 logging。 | 採這五欄與缺值語意。 |
| core/llm | 沒有 usage 介面。 | 不採。 |

### (g) 逾時、重試、錯誤

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | 分 queue timeout 與 backend timeout；辨別部分 HTTP 是否 retryable，但不自動重試；崩潰後是不可重試的 result_unknown。 | 採錯誤分類與不自動重送。 |
| proto2 | HTTP／CLI 上限 300 秒，先用 10 秒探 TCP；壞請求、未知 engine、worker died 都產 error result；明寫不做 retry／backoff。 | 採「每請求都要有終局結果」；TCP 預探是特定環境補丁，v1 不先搬。 |
| proto3 系 | protect 捕捉 engine 例外變 failed；agent 另有等待逾時，但 LLM queue 沒 durable timeout／retry。 | 不採。 |
| proto4-1/2 | 普通 inst 有 timeout 與退出碼；沒有 LLM 級重試。 | 採外層硬上限當最後保險，但 worker 仍要寫結構化 error。 |
| llmkit | client 本身不 retry；例外收進 Reply.err；proxy 設了 2 次 retry 與 600 秒 timeout。 | 採 Reply.err 形狀；不採 v1 proxy 隱含重試，避免不清楚一發送了幾次。 |
| core/llm | 連線／HTTP／JSON／模型不符回 1；等槽逾時回暫時失敗 75。 | 改採「資源等不到」與「請求失敗」分開；個別結果不可只靠整支 tick 的退出碼。 |

### (h) 本機模型載入／卸載

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | README 告訴人手動 load，換模型前手動 unload；程式完全不管。 | 採 v1 的人工管理，endpoint 綁定目前載入的 model。 |
| proto2 | LM Studio 設 `max_concurrent: 1`，但不 load/unload，也沒處理兩個本機 model 請求衝突。 | 只採容量 1。 |
| proto3 系、proto4-1/2 | 沒有處理。 | 不採。 |
| llmkit | proxy 可讓 LM Studio JIT load，筆記仍提醒大模型前先手動 unload；沒有「一次一顆」排程器。 | 不採 JIT 當保證；它不能解釋切模的排程與成本。 |
| core/llm | README 明寫不載入或卸載模型。 | 採這個邊界。 |

### (i) 測試怎麼做

| 來源 | 它怎麼做 | 採不採 |
|---|---|---|
| proto | `echo:/fail:/slow:` 假 backend，加 monkeypatch HTTP；測無網路、排序、wait 邊界、inflight 原件、重啟 unknown、usage reasoning。 | 採三種假 endpoint 與崩潰恢復案例，可直接照語意重寫。 |
| proto2 | shell 起本機假 HTTP server／假 CLI；測排序、公平、帳本、協定翻譯、錯誤、worker 完成標記，全程不碰真服務。 | 採假 server、假子行程與跨 tick pump；不搬 agent cost 測試到 LLM cpu。 |
| proto3 系 | script engine 回固定序列，測 FIFO、每格上限、三態與回信。 | 採最小 scheduler 單元測試。 |
| proto4-1/2 | 沒有 LLM 測試。 | 不採；普通 cpu 整合測試可另拿來包住一格。 |
| llmkit | Reply 有離線 checks，其餘主要靠對真模型 smoke；proxy 能力旗標來自實打。 | 改採 Reply 離線形狀；v1 回歸不得依賴真 endpoint。 |
| core/llm | 本次只看 README／標頭，沒有深入測試。 | 不從這裡搬測試。 |

## 3. 建議的 LLM cpu v1 骨架（等使用者拍板）

### 資料夾

```text
llm-cpu/
  inst.json                 # argv 跑 `llm-cpu tick .`，cwd 就是本資料夾
  endpoints.json            # endpoint 與容量
  defaults.json             # 可省略：default_endpoint、priority、queue_timeout_ms
  requests/*.json           # 排隊；檔名就是 request id
  requests/running/*.json   # 已派，內加保留欄 `_aos`：endpoint/pid/started
  requests/done/*.json      # 成功、失敗、結果不明都歸檔
  results/<同請求檔名>       # 統一 JSON 終局結果，原子寫
  usage/pending/*.json      # worker 的逐發紙條
  usage/<YYYY-MM-DD>.jsonl  # tick 單一 writer 收帳
  logs/<同請求檔名>.log
  state.json                # tick、served、errors；不是請求真源
```

放上普通 cpu 的 inst 可直接沿用 proto4-3：`{"argv":["/abs/llm-cpu","tick","."],"cwd":"/abs/llm-cpu"}`。程式自己 append log；不要把累積 log 綁到 inst 的 stdout/stderr，因為 aos-exec 每格會截斷檔案。

### 最小請求

```json
{"messages":[{"role":"user","content":"你好"}]}
```

檔名提供 id、result 固定同檔名，所以不用再放 `id` 或 `reply_to`。選填只留：`endpoint`、整數 `priority`、`timeout_ms`、`params`；`max_tokens` 放 `params.max_tokens`。`model` 預設不准請求覆寫，由 endpoint 設定固定，避免 LM Studio 被兩個 model 名同時排到。請求由呼叫者用「寫 `.tmp` → rename」投進 `requests/`；之後可包一支小 submit 程式給 lisp 透過 inst 呼叫，但不是 LLM cpu 自己做 agent 行為。

### 一格做什麼

1. 把 `usage/pending/` 收進帳簿。
2. 巡 `running/`：有完成標記／result 就搬 done；pid 死且無結果就寫 `worker_died`；送出後狀態無法判定則寫 `result_unknown`，不自動重送。
3. 驗證新 request；壞的當格寫 error result 並搬 done。
4. 依 `priority` 大者先、同分 mtime／檔名先排序；endpoint 滿了就跳看別台。
5. 每台派到 `max_concurrent` 為止：先搬 running，再開脫離 worker，記 pid，tick 隨即返回。

跨格有兩案：A「同步 tick」最少碼，但一次推論會霸住 cpu 幾十秒，kernel 也只能等當次結束；B「背景 worker」讓 tick 維持短格，用 running＋pid＋result＋marker 在後續格收尾。推薦 B；它是 proto2 已跑過的形狀，也正面解掉「一格幾秒、推論幾十秒」的衝突。代價是必須接受送出後崩潰的 exactly-once 不可證明，因此預設 `result_unknown`、由呼叫者決定是否另投新 id。

### endpoint 最小設定

```json
[
  {"name":"local","kind":"openai","base_url":"http://localhost:1234/v1","model":"loaded-model-id","max_concurrent":1,"timeout_ms":300000},
  {"name":"deepseek","kind":"openai","base_url":"https://api.deepseek.com/v1","model":"deepseek-chat","api_key_env":"DEEPSEEK_API_KEY","max_concurrent":2,"timeout_ms":300000},
  {"name":"pi","kind":"process","argv":["pi","-p"],"max_concurrent":1,"timeout_ms":300000,"enabled":false}
]
```

OpenAI worker 組非串流 `chat/completions`，回傳保留整包 choices、finish_reason、usage，另正規化 cached／reasoning；key 只按 `api_key_env` 的名字讀。`pi` 先只佔設定槽並 disabled，等後面真的定 CLI 輸入／輸出契約再啟用。

### v1 明確不做

- 不做 agent history、agent 狀態機、工具執行、MCP、Claude／Codex agent loop。
- 不做串流、取消、批次、deadline、kind／費用／公平分數、自動挑便宜模型。
- 不做自動 retry／backoff；只回 `retryable` 情報，重送由呼叫者用新 id 決定。
- 不做 LiteLLM proxy、能力探測、多機、跨主機鎖、精準 cost 聚合。
- 不替 LM Studio load/unload 或自動換模型；local endpoint 永遠容量 1，model 不符就明確失敗。

## 4. 要問使用者的（最多五條）

1. 跨格是否拍板用背景 worker？我的預設：是，tick 絕不等網路。
2. 請求是否只指定 endpoint 名、model 固定在設定？我的預設：是，尤其本機不能讓請求任意切模。
3. priority 是否定成「整數越大越先，同分 FIFO」？我的預設：是，不先做 proto2 複合分數。
4. worker 在送出後失聯是否一律 `result_unknown`、禁止自動重送？我的預設：是，避免重複扣款與雙回覆。
5. v1 是否完全不管 LM Studio load/unload？我的預設：是，只驗回應 model 是否符合目前設定。

## 5. 附：讀過的檔案（行數）

- 現方向：`proto4/notes/20-21-step-lisp-and-next.md` 143；`proto4/notes/07-10-inst-json-cpu.md` 144；`proto4-3/README.md` 182；`proto4-3/docs/exec.md` 147；`proto4-3/docs/kernel.md` 126；`proto4-4/README.md` 161。
- proto：`proto/aosp/llm.py` 892；`proto/README.md` 166；`proto/FINDINGS.md` 273；`proto/tests/test_llm.py` 372。
- proto 範例：`proto/examples/llm-echo/README.md` 34；`main.aos.json` 25；`run.sh` 53；`.aos/config.json` 7；`.aos/layout.json` 4；`.aos/program/main.json` 26；`.aos/series.json` 23。
- proto2 主體：`proto2/aos_llm.py` 143；`proto2/aos-llm` 1793；`proto2/README.md` 283；`proto2/notes/2026-09-06-ideas-vs-proto2.md` 163。
- proto2 文件：`proto2/docs/llm-scheduling.md` 269；`proto2/docs/cost.md` 57；`proto2/notes/tools/cost-metering.md` 113。
- proto2 測試：`proto2/tests/sched.sh` 124；`cost.sh` 99；`anthropic.sh` 288；`claude_cli.sh` 291。
- proto3：`proto3/README.md` 51；`src/llm.janet` 54；`src/agent.janet` 73；`src/main.janet` 56；`test/basic.janet` 102；`notes/2026-09-08-backbone-pains.md` 469；`notes/2026-09-08-ideas.md` 48；`notes/2026-09-08-packs-contract.md` 369。
- proto3 CL 對照：`proto3/variant-cl/README.md` 50；`src/llm.lisp` 49；`src/agent.lisp` 68；`src/main.lisp` 58；`test/basic.lisp` 101。
- proto3-1：`proto3-1/README.md` 90；`src/llm.janet` 60；`src/agent.janet` 94；`src/main.janet` 63；`test/basic.janet` 157；`notes/2026-09-08-design.md` 68；`notes/2026-09-08-ideas.md` 20。
- proto3-1 CL 對照：`proto3-1/variant-cl/README.md` 98；`src/llm.lisp` 50；`src/agent.lisp` 74；`src/main.lisp` 66；`test/basic.lisp` 150。
- proto3-2：`proto3-2/README.md` 21；`src/agent.janet` 72；`notes/2026-09-08-ideas.md` 22。
- proto4 舊版：`proto4-1/README.md` 63；`proto4-2/README.md` 172；兩目錄的 grep 結果均無 LLM 相關檔。
- llmkit：`reference/llmkit/README.md` 101；`llms/client.py` 119；`engine.py` 85；`presets.json` 106；`presets.py` 68；`usage.py` 23；`caps.py` 72；`reply.py` 154；`llms/README.md` 143；`llms/USAGE.md` 131。
- llmkit proxy：`reference/llmkit/proxy/litellm.yaml` 144；`proxy/README.md` 143。
- C++：`core/llm/README.md` 67；`core/llm/include/aos/llm.hpp` 52；`core/llm/include/aos/slot.hpp` 81。
