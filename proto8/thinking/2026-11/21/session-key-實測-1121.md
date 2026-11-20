家機暫存樹實測 llm kernel 的 sol 那包加 `"session_key": "litellm_session_id"` 前後：不加每輪快取 0，加了從第 2 輪起每輪約 99% 命中。

← [2026-11-21](README.md)｜進度 `prompt-cost-cache`｜前情：[aos-home 瀏覽筆記 第 10 則](../20/aos-home-瀏覽筆記-1120.md)｜鍵的說明：[kernel_llm docs/01](../../../py/tools/aos/kernel_llm/docs/01-用法.md)

## 做法

線 `top-1121-skey`，11-21 清晨家機。照 `templates/start-api` 抄兩棵暫存樹（`~/.aos/scratch/top-1121-skey/a-nokey`、`b-key`），兩棵都把 `agents/ann/llm.json` 換成 `{"model": "sol"}`；只有 `b-key` 的 `llm/kernel.json` 在 `sol` 那包多寫 `"session_key": "litellm_session_id"`。各起一棵、對同一隻 ann 連問 4 句「Reply with one word: ok」，數字讀 ann 的 `observed.jsonl`。LiteLLM 用使用者起著的那台（1.87.5，埠 4000，模型 `chatgpt-gpt-6.1-sol`），沒改它的設定。真模型共叫 8 次。`~/aos-home`、`proto8/` 的程式與範本都沒動。

## 數字

| 輪 | 不加：prompt_tokens | 不加：cached_tokens | 加了：prompt_tokens | 加了：cached_tokens | 加了的命中率 |
|---|---|---|---|---|---|
| 1 | 12,553 | 0 | 12,553 | 0 | 0%（第一次，本來就沒得中） |
| 2 | 12,570 | 0 | 12,570 | 12,416 | 98.8% |
| 3 | 12,587 | 0 | 12,587 | 12,416 | 98.6% |
| 4 | 12,604 | 0 | 12,604 | 12,416 | 98.5% |
| 4 輪合計沒中快取的 | 50,314 | | 13,066 | | 少 74% |

送出去的請求兩邊一樣大（`request.json` 約 52 KB，其中 `tools` 50.8 KB）。加了只是讓上游把重複的那一大段當快取算，不會讓請求變小。

## 結論

- 加 `"session_key": "litellm_session_id"` 有效：同一隻 agent 第 2 輪起幾乎整段提示都命中快取。昨晚 `~/aos-home` 看到的 `cached_tokens` 0，原因就是沒寫這個鍵。
- 不加的那組 4 輪都是 0（11-14 公司機那次不加還有 18%／31%，是碰巧中；這次一次都沒中）。

## 已排除的其他原因（不加時 0 不是因為這些）

- 工具說明順序不穩：`b-key` 4 輪的 `tools` 逐項相同，`a-nokey` 第 4 輪跟 `b-key` 第 4 輪的 `tools` 也相同。
- system 裡有會變的東西（時間戳之類）：4 輪的第一則 system 訊息逐字相同。
- 前面的對話被改寫：第 1 輪的 `messages` 是第 4 輪的開頭，逐項相同，每輪只在後面接。
- 上游的快取門檻：一萬二千多 token 遠超過門檻，加了就中，所以不是門檻。
- LiteLLM 沒把欄位轉給上游：加了就中，代表 1.87.5 有把 `litellm_session_id` 當成上游的 session id 送出去。

另外看到的：加了之後命中的量停在 12,416，沒有隨對話變長往上長（每輪新增的那十幾 token 沒進快取）。原因沒查，對這次的結論沒影響。agent 自己 stack 的 `think/request.json` 裡看不到這個鍵是正常的，鍵是 llm kernel 交給端點函數時才加的（docs/01 有寫）。

## 建議改哪一行（要不要改由使用者定，這條線沒改）

`proto8/templates/kernel/llm-kernel/kernel.json` 與 `proto8/templates/start-api/llm/kernel.json`（後者是前者的逐字抄本，`templates/tests/test_start.py` 會比對，兩份要一起改）的 `sol` 那包：

```json
"sol":         {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6.1-sol", "fixed": {"temperature": 0.2}, "session_key": "litellm_session_id", "cost": "high", "context": 272000,
```

同一個 chatgpt 後端的 `luna`、`terra` 照理也一樣，這次沒量。`~/aos-home/llm/kernel.json` 是活樹，要改也是使用者或頂層的事。

## 續量：luna、terra、astra（線 top-1121-skey2，11-21 家機）

使用者：「luna/terra/astra也都順便去量，astra好像還沒被納入，那就也派線去做。」

### 做法

照 `templates/start-api`（`git archive HEAD`，d3882e9c5）抄兩棵暫存樹 `~/.aos/scratch/top-1121-skey2/a-nokey`、`b-key`。兩棵的 `llm/kernel.json` 都在 `sol` 後面加一包 `astra`（模型 `chatgpt-gpt-6-astra`，LiteLLM 那邊本來就有，`GET /v1/models` 列得到、`~/repo/llm_proxy/models/chatgpt.yaml` 第 21 行；沒改代理）；只有 `b-key` 在 `luna`、`terra`、`sol`、`astra` 四包加 `"session_key": "litellm_session_id"`。每棵掛三隻 agent-fsm（`ann` 的抄本，`llm.json` 各指 `luna`／`terra`／`astra`），每隻連問「Reply with one word: ok」：luna、terra 各 4 輪，astra 貴、各 3 輪。先跑完不加的整棵、關掉，再跑加了的。數字讀各隻的 `observed.jsonl`。

### 數字（每格是 prompt_tokens／cached_tokens）

| 輪 | luna 不加 | luna 加了 | terra 不加 | terra 加了 | astra 不加 | astra 加了 |
|---|---|---|---|---|---|---|
| 1 | 12,553／0 | 12,553／12,416 | 12,553／0 | 12,553／12,416 | 12,553／0 | 12,553／12,416 |
| 2 | 12,570／12,416 | 12,570／12,416 | 12,570／0 | 12,570／12,416 | 12,570／0 | 12,570／12,416 |
| 3 | 12,587／0 | 12,587／12,416 | 12,587／0 | 12,587／12,416 | 12,587／0 | 12,587／12,416 |
| 4 | 12,604／0 | 12,604／12,416 | 12,604／12,416 | 12,604／12,416 | — | — |
| 沒中快取的合計 | 37,898 | 650 | 37,898 | 650 | 37,710 | 462 |

- luna 實際模型 `chatgpt-gpt-6-luna-low`、terra `chatgpt-gpt-6.1-terra`（都照範本），astra `chatgpt-gpt-6-astra`。三個都能問能答，回 `ok`。
- 加了的那組連第 1 輪也中，是因為一兩分鐘前不加的那組剛送過一模一樣的開頭（兩棵樹、各隻的 system 與 `tools` 逐字相同），上游還留著。換成隔很久第一次問，第 1 輪會像早上 sol 一樣是 0；要比的是第 2 輪起。
- 不加的那組偶爾中一次（luna 第 2 輪、terra 第 4 輪），astra 3 輪都沒中，跟 11-14 公司機「不加還有兩三成」一樣是碰運氣。

### 結論

- luna、terra、astra 跟 sol 一樣：加 `"session_key": "litellm_session_id"` 之後每輪都中約 99%，不加大多是 0。四個都走 LiteLLM 的 chatgpt 後端，行為一致。
- 這次沒有「加了仍是 0」的模型，不用另外查原因。

### 命中量為什麼停在 12,416

不是快取只停在工具說明＋system 後面。另外用 sol 加了 `session_key` 的一隻 agent 問 4 輪，第 1、3 輪各塞一長串數字：

| 輪 | 問了什麼 | prompt_tokens | cached_tokens |
|---|---|---|---|
| 1 | 一長串數字＋ok | 14,669 | 0 |
| 2 | 短句 | 14,686 | 14,592 |
| 3 | 又一長串數字＋ok | 15,918 | 14,592 |
| 4 | 短句 | 15,935 | 15,744 |

第 2 輪的命中把第 1 輪那串數字也算進去了，第 4 輪又長到 15,744，所以快取會跟著對話往後長。看起來的規律（從這幾個數字推的，沒找到上游文件對照）：

- 命中量一律是 128 的倍數（12,416＝97×128、14,592＝114×128、15,744＝123×128）。
- 上一輪請求最後大約 47～77 個 token 這一輪用不到（由上面幾組數字夾出來的範圍；是哪幾個 token 沒查）。

所以短句每輪只多 17 個 token，4 輪加起來才 51 個，跨不過下一個 128 的格子，看起來就像卡在 12,416。對話長到多出一百多個 token 就會往上長。這對成本的影響很小（每輪沒中的只有一兩百個 token）。

### 建議寫進範本的幾行（這條線沒改，要不要改由使用者定）

`proto8/templates/kernel/llm-kernel/kernel.json` 與 `proto8/templates/start-api/llm/kernel.json`（兩份逐字一樣，要一起改）的 `luna`、`terra`、`sol` 三包都加 `session_key`，`sol` 後面新增 `astra` 一包：

```json
   "luna":        {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6-luna-low", "session_key": "litellm_session_id", "cost": "high", "context": 272000,
                   "summary": "LiteLLM gpt-6 luna, low effort"},
   "terra":       {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6.1-terra", "session_key": "litellm_session_id", "cost": "high", "context": 272000,
                   "summary": "LiteLLM gpt-6.1 terra"},
   "sol":         {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6.1-sol", "fixed": {"temperature": 0.2}, "session_key": "litellm_session_id", "cost": "high", "context": 272000,
                   "summary": "LiteLLM gpt-6.1 sol"},
   "astra":       {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6-astra", "session_key": "litellm_session_id", "cost": "high", "context": 272000,
                   "summary": "LiteLLM gpt-6 astra: images and creative work, about 3x sol's price"},
```

`astra` 的 `context` 272000 是代理 `models/chatgpt.yaml` 裡 chatgpt 那組共用的 `max_input_tokens`；沒加 `fixed`（`luna`、`terra` 也沒有）；`summary` 那句價格照 [team-model/grades](../../../../wf/workflows/team-model/grades.md)「astra 實際價格約 sol 的 3 倍」。`~/aos-home/llm/kernel.json` 是活樹，沒碰。

真模型這次共叫 26 次（luna 8、terra 8、astra 6、sol 長句 4）。

## 範本與 ~/aos-home 已改（11-21）

線 top-1121-skey3。

- 改了三個檔：`proto8/templates/kernel/llm-kernel/kernel.json`、`proto8/templates/start-api/llm/kernel.json`（兩份逐字相同）、`~/aos-home/llm/kernel.json`。`luna`、`terra`、`sol` 三包各加 `"session_key": "litellm_session_id"`，`sol` 後面新增 `astra` 一包。`~/aos-home` 那份有備份 `kernel.json.bak-1121`。
- 使用者原話：
  - 「範本可以改，aos-home也改，改之前跟我說你要怎麼改，會怎麽影響我，我該做啥。luna/terra/astra也都順便去量，astra好像還沒被納入，那就也派線去做。」
  - 「可以，就這樣。不過litellm_session_id...」
  - 「沒事，這個OK。只是說以後公開發佈的時候，我怕別人誤以爲aos需要依賴litellm」
- 最後這點只記錄，沒有動手；`session_key` 的值是欄位名（LiteLLM 認的那個），換別家代理就填那家的欄位名。
