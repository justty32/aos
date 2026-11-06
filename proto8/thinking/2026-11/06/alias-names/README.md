# 2026-11-06 llm kernel 模型代號的命名想法：使用者原話，加現況盤點（alias-names）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)

## 使用者原文（11-06 晚）

脈絡：在講 llm kernel 的模型代號（現在是 `smart-high`、`stupid-fast` 這種）。

> 這塊我原本的想法是，代號更加靈活，比如writing-bad-1, lyric-fasion-y...

（只留原文，沒有解讀、沒有改條文。）

## 現況盤點（只是盤點，不是決定）

盤點範圍：`proto8/` 的程式、範本、知識庫、工具，加試驗場 `~/code/playground`；thinking 與 docs 內的舉例不列。查的是「寫死特定代號」與「對代號名字有格式限制」。

### A. 寫死了特定代號名字

| 檔:行 | 寫死了什麼 | 作用 |
|---|---|---|
| `kernel/llm-kernel/kernel.json:3` | 預設 `"endpoint": "fake"` | 信裡沒帶 endpoint 時用的預設代號；是資料，改了就行 |
| `kernel/llm-kernel/kernel.json:6,9,16,18,25,33,52,54` | 範本裡的 `smart-high`、`stupid-fast`、`fake`、`fake-demo-*` | 範本的代號表；是資料。`fake-demo-*` 另被 kernel/docs 03 的示範劇本照名引用 |
| `kernel/llm-kernel/kernel.json:36,43` | 劇本裡 `"llm": {"endpoint": "fake"}` | 假腦示範時叫 agents 工具開小弟用的代號 |
| `lib/agent/thought/_tooldef.json:67`（試驗場副本同） | 說明字句舉例 `stupid-fast to save money` | 只是給腦看的說明文字，不是邏輯 |
| `lib/agent/agents/_tooldef.json:11`、`lib/agent/agents/_entry:279` | 說明與錯誤訊息舉例 `{"endpoint": "fake"}` | 只是舉例字句，不做比對 |
| `knowledge/aos/brain.md:11`、`knowledge/aos/cli/talk_settings.md:10`、`knowledge/aos/cli/flags.md:12`（試驗場副本同） | 舉例 `smart-high`、`stupid-fast`、`aos-agent llm --target bob set endpoint=smart-high` | 給 agent 讀的知識庫；寫成「例如」，不是限制 |
| `kernel/README.md:7` | `（smart-high、stupid-fast…）` | 說明字句 |
| `impls/aos-llm-kernel/src/pack/pack.hpp:1` | 註解「代號就是能力名：smart-high、stupid-fast…」 | 註解 |
| `impls/aos-llm-kernel/README.md:20,33-38` | 範例與預期輸出裡的 `smart-high`；`luna`、`sol` 共用金鑰說明 | 說明文件，輸出範例 |
| `kernel/docs/01-llm-kernel.md:23` 附近 | 代號表列 `smart-high` 等 | 說明文件 |
| `~/code/playground/README.md:54,60` | `set endpoint=stupid-fast` 與 `stupid-fast` 對應 LM Studio 的說明 | 試驗場說明 |

結論一句：C++、Python 程式邏輯裡沒找到拿代號字串去比對（`== "smart-high"`、`"fast"` 當代號）的地方；搜到的都是資料、範例字句、說明文字。只有 `fake` 在範本資料裡當預設，程式端不認它。

### B. 對代號名字有格式限制或固定詞彙

| 檔:行 | 限制 | 作用 |
|---|---|---|
| `impls/aos-llm-kernel/src/serve/scan.cpp:36-37` | 信裡的 endpoint 必須是 kernel.json `endpoints` 的鍵，否則 `EndpointUnknown` | 這是「要存在」，沒限制字元或前綴 |
| `impls/aos-llm-kernel/src/serve/config.cpp:60-66` | 預設 endpoint 必須是 `endpoints` 裡的名字，否則 `CfgBad` | 同上 |
| `impls/aos-llm-kernel/src/pack/pack.cpp:10,99` | 每包允許的鍵只有 `exec slots budget speed cost context summary fixed`（欄位名，不是代號名） | 限制的是包內欄位，不是代號 |
| `impls/aos-llm-kernel/src/pack/pack.cpp:45-54` | 包的 `speed` 只准 `"fast"`、`"normal"`、`"slow"`（enum） | 影響排序（整級 fast 先）；這是屬性值，不是代號 |
| `cmd/aos-agent/aos_agent/llm.py:107`（註解） | agent 端 `llm` 設定「鍵由身體認、這裡不認不擋、值一律字串」 | 代號字串不被 aos-agent 檢查 |
| `lib/agent/agents/_entry:65,143` | `NAME_RE = [A-Za-z0-9_][A-Za-z0-9_-]{0,63}` | 這個是 agent 名字的格式，**不是**模型代號；列出來只為免得混淆 |
| `templates/agent-fsm/brain.py:167-169` | `endpoint` 必須是非空字串，原樣放進請求 | 只擋空字串 |

結論一句：代號名字沒有字元集、前綴、長度的檢查；只要求「非空字串」且「在 kernel.json 的 endpoints 裡」。`writing-bad-1`、`lyric-fasion-y` 這類名字照現況就能用。

### C. 還沒查清楚的

- `endpoint_dirs` 由 `eps.dir_of(k)`（`config.cpp:60`）來，這是 endpoints 載入（定義資料夾合併）那層，沒進去看代號名字有沒有被當檔名或路徑片段用過（例如有斜線或點的名字）。
- `aos-llm` 命令列（`impls/aos-llm`）沒逐行看。
- 單元測試與 thinking／docs 裡的舉例沒列。

## 使用者回覆（11-06 晚）

脈絡：頂層追問「靈活」指什麼：是單純照用途自由取名，還是另有意思，例如一個代號背後換不同模型、一隻 agent 用好幾個代號。

使用者原話：

> 就是自由取名

結論：照上面「現況盤點」，現況已支援（代號只要是 kernel.json `endpoints` 的鍵、非空字串，無字元／前綴限制），不需要改程式。「還沒查清楚的」那兩點（代號含斜線或點被當檔名時、`aos-llm` 命令列）留著，之後碰到再查。
