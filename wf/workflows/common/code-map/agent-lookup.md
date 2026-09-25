← [code map 總圖](../code-map.md)｜[各分冊導覽](README.md)

### 常查的東西在哪

| 我想找… | 去哪 |
|---------|------|
| agent 每回合怎麼被執行、預設工具何時安裝 | `core/agent/src/init.cpp` 的 `aos_program_path()`／`initialize()`：建版面、世界 registry 為空時安裝預設工具，並把目前 aos 的絕對路徑寫進 `.aos/every/agent-<name>.json`；loop 每回合複製它，`step` 不自我投遞。 |
| agent 訊息何時才會從 say 刪除、失敗怎麼記 | `core/agent/src/step.cpp` 與 `engine_pi.cpp`：成功取得回覆後才記 history／log 並刪 say；失敗寫 `status=error`、journal note 與連線／API key 指引，pi 回 1。 |
| `state`／`listen`／`talk` 的未讀與 runner 判斷在哪 | 共用 `state_text()`、未讀列印、`run.lock` 檢查與輪詢在 `core/agent/src/run.cpp`；頂層入口在 `run_top.cpp`。 |
| 世界工具登記表與 agent 白名單怎麼合併 | spec JSON 在 `core/tool/src/spec.cpp:116-180`，registry 掃檔在 `core/tool/src/registry.cpp:85-108`；`core/agent/src/tools.cpp:119-142` 讀整張世界表，`tools.json` 存在時再取白名單交集。 |
| 工具怎麼表述、`list`／`string`／`none` 怎麼展開 argv | `core/agent/src/tools.cpp:85-117` 每工具組一行 prompt；`core/agent/src/tools.cpp:144-168` 對 list 追加 token、對 string 替換所有 `{args}`（沒有占位符就追加一個 argv）、對 none 保留固定 argv。 |
| 怎麼從 LLM 回覆裡抽出工具呼叫 | `core/agent/src/tools.cpp:170-241`：由回覆末行往上找完整 JSON object 行，先查工具是否在可用表，再依其 `args` 登記驗字串陣列／字串／省略或空值；未知工具與形狀錯誤都回傳具名錯誤，不再靜默忽略。 |
| 工具結果與呼叫錯誤怎麼回給模型 | `core/agent/src/step.cpp` 的 `execution_tool_result()`／`step()`：等 `pending.turn + 1` 的 out 全到齊後加入 execution 結果，或在抽取當回合立即加入未知工具／args 錯誤。 |
| `aos say --to` 怎麼找對方世界 | `core/agent/src/run_top.cpp` 的 `say_dispatch()`／`validate_world()`：查目前世界 `.aos/contacts.json`，以目前世界為基準組出 contact folder，驗世界與 agent；contact 沒寫 agent 時解析目標世界唯一 agent，再呼叫 `say()` 並印實際 inbox。 |
| LM Studio 端點與模型怎麼設 | 全域預設從 `core/llm/src/llm.cpp` 的 `options_from_env()` 讀 `AOS_LLM_URL`／`AOS_LLM_MODEL`／`AOS_LLM_KEY`；agent 的 `engine.json` 若有 model，`core/agent/src/step.cpp` 的 `complete_locally()` 會覆蓋環境模型。 |
| LLM 並行上限住哪、怎麼排隊 | `<AOS_HOME>/cpus.json`（權威）與 `<world>/.aos/llm.json`（只能往下限）；實作在 `core/llm/src/slot.cpp`；用 `aos llm --slots` 看現況。 |
| 取槽等太久會怎樣 | stderr 一行 `waiting-llm`、exit 75（`EX_TEMPFAIL`）；agent 走 lmstudio 或 pi 時 status 都寫 `waiting-llm`，訊息還沒被吃掉，下回合重試。 |
| loop 替身在哪、怎麼跑 | `core/agent/tests/fake_loop.py`；repo 根執行 `python3 core/agent/tests/fake_loop.py <folder> --step N --interval 100`。完整 smoke 是 `bash core/agent/tests/smoke.sh`（使用 `build/bin/aos`）。 |

every 常駐投遞的裁決已封存（ideas/archive/self-delivery-in-loop.md），新構想見 ideas/07-daemon.md；pi 終端介面調查與建議接法見 [`core/agent/docs/pi-interface.md`](../../../../core/agent/docs/pi-interface.md)。

## `core/agent` 的可選 LLM CPU

`agents/<name>/engine.json` 選擇既有的 lmstudio 引擎或 pi coding agent；pi 分支在同一次
`step` 裡完成模型思考與內建工具操作，不進 `tools.json`／pending 的三回合往返。

| 檔案 | 負責什麼 |
|------|----------|
| `core/agent/src/engine.cpp` | `engine.json` 的讀寫與驗證（含 lmstudio model）、lmstudio／pi 預設值、共用 LLM priority 解析，以及 pi session 使用的 v4 UUID 產生。 |
| `core/agent/src/engine_pi.cpp` | pi 引擎的 step 分支：組 argv 與 stdin、執行 pi、解析 JSONL 最終回覆；成功後才刪 say，失敗寫 error／note、`No API key` 指向 provider 環境變數並回 1；step 期間佔 provider 槽，等不到回 75。 |
| `core/agent/tests/test_agent_engine.cpp` | engine 選擇、設定相容性、假 pi 插銷、JSONL 解析與 pi step 行為測試。 |
| `core/agent/docs/pi-cpu.md` | pi 0.84.2 的 provider／JSONL／session 實測、aos 接法，以及相對於 `aos llm` 的取捨。 |
