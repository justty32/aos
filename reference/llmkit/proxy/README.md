# proxy

一個 LiteLLM proxy 的設定檔和啟動腳本。它把 DeepSeek 雲端、ChatGPT Pro 訂閱、Claude Pro
訂閱、遠端 Ollama、本機 LM Studio 收成**同一個 OpenAI 相容端點**（預設 `localhost:4000`），
所以換模型就只是換一個字串，程式碼不用動。

`llms` 預設就是打這裡。但它不是必需品 —— 有現成的 OpenAI 相容端點就直接
`LLM(url=..., key=...)` 指過去。

| 檔案 | 是什麼 |
|---|---|
| `litellm.yaml` | 有哪些模型、各自打到哪、各自做得到什麼 |
| `start_litellm.sh` | 啟動（Linux / macOS） |
| `start_litellm.ps1` | 啟動（Windows），參數一樣是 `(config, port)` |
| `chatgpt_auth_from_codex.py` | 把 codex CLI 登入過的 token 轉給 litellm 用，免再登入一次 |
| `claude_auth_from_claude_code.py` | litellm callback：每個請求從 Claude Code 登入檔拿最新 token 餵給 `claude-*`，順便補後端要的 system 前綴 |

## 起來

```bash
export DEEPSEEK_API_KEY=sk-...     # 只有要用 DeepSeek 才需要
./chatgpt_auth_from_codex.py       # 只有要用 ChatGPT 訂閱才需要，見下面「ChatGPT 訂閱」
                                   # Claude 訂閱不用做事，登入過 Claude Code 就行，見「Claude 訂閱」
./start_litellm.sh                 # 等同 ./start_litellm.sh litellm.yaml 4000
curl localhost:4000/v1/models      # 確認實際載入了哪些
```

**連不到的來源不會擋住啟動**，只有真的去呼叫它時才失敗 —— 所以沒開 LM Studio、
沒有 DeepSeek 金鑰、沒轉 ChatGPT token、沒登入 Claude Code，proxy 一樣起得來，剩下的模型照用。

litellm **不裝進任何 venv**，腳本用 `uv run --with` 臨時把它拉進來跑，不用先裝、
也不用維護第二個 venv。

### litellm 為什麼釘死 `==1.87.5`

2026-09-20 起直接釘 litellm 版本（它自己會帶 fastapi==0.124.4、uvicorn==0.33.0），
原因是 **ChatGPT 訂閱那條路只有這版能非串流用**：

- 後端（`chatgpt.com/backend-api/codex/responses`）只吃 Responses API 而且**一定要
  stream**，`response.completed` 事件裡的 `output` 又是空的，內容只在中途的
  `output_item.done` 事件裡。litellm 把 chat completion 橋接成 Responses 時，1.87.5
  會從串流紀錄裡把內容撈回來；**1.93.0 起到 1.103.0.dev2 都撈不回來**，非串流呼叫
  一律回 `Unknown items in responses API response: []`（串流呼叫新舊版都通）。
- 1.88～1.92 PyPI 上沒有，1.87.5 的下一版就是 1.93.0，沒得挑。
- 等 litellm 修好再升；升之前先用 `chatgpt-gpt-6-astra` 打一次非串流 chat 確認。

舊教訓保留（2026-08-06，當時是用 `fastapi<0.130` 間接解析出 1.87.5）：

- **fastapi `>=0.130`**：拿掉了舊 litellm 依賴的私有 API
  （`fastapi.dependencies.utils.get_flat_dependant`），proxy 開機就 crash。
  1.93+ 已改依 fastapi>=0.136，這個坑只對舊 litellm 有效。
- **fastapi `<0.119`**：會讓 uv 把 litellm 反向解析回 1.79.x 那種老版本。那個版本的
  **Ollama function calling 是假的** —— 它把工具定義用文字塞進 system prompt 叫
  模型自己接龍 JSON，不走 `/api/chat` 原生 `tools`。實測三個工具以上
  就常常漏答成純文字，根本不會進 `tool_calls`。

## 現在有哪些模型

名字定義在 `litellm.yaml`（2026-09-20 共 130 條：ChatGPT 47、Claude 70、LM Studio 6、Ollama 4、DeepSeek 3）。
**思考深度統一成「換名字」**：基底名字＝後端預設、client 自己傳 `reasoning_effort` 也吃；
`-low` / `-medium` / `-high` / `-xhigh` / `-max` 是同一顆焊死深度的分身、`-nothink` 是關掉思考的分身。
哪顆有哪幾檔以實打為準，下面每家一段。

**ChatGPT Pro 訂閱**（codex 後端；全部看得到圖、會思考、叫得動工具、JSON schema 不行）：

| 基底名字 | 是誰 | 有哪些分身 |
|---|---|---|
| `chatgpt-gpt-6-astra` | codex 預設款、最強 | `-low` `-medium` `-high` `-xhigh` `-max`（**沒有 `-nothink`**，後端不吃 none） |
| `chatgpt-gpt-5.6-sol` | 最新 coding 款（後端預設深度是 low） | `-low` ～ `-max` ＋ `-nothink` |
| `chatgpt-gpt-5.6-terra` | 均衡款 | `-low` ～ `-max` ＋ `-nothink` |
| `chatgpt-gpt-5.6-luna` | 快、便宜 | `-low` ～ `-max` ＋ `-nothink` |
| `chatgpt-gpt-5.5` | 上一代，codex 說 2026-10-14 退役 | `-low` `-medium` `-high` `-xhigh` ＋ `-nothink`（**沒有 `-max`**，400） |
| `chatgpt-gpt-reserve` | codex 裡藏起來的（`visibility: hide`）快款 | `-low` ～ `-max` ＋ `-nothink` |
| `chatgpt-codex-auto-review` | codex 裡藏起來的自動 review 模型 | `-low` ～ `-max` ＋ `-nothink` |

**Claude Pro 訂閱**（Claude Code 的 token；全部看得到圖、叫得動工具、JSON schema、快取都通）：

| 基底名字 | 世代 | 有哪些分身 |
|---|---|---|
| `claude-fable-5-1` / `claude-fable-5` | adaptive，思考關不掉 | `-low` `-medium` `-high` `-xhigh` `-max`（**沒有 `-nothink`**，400） |
| `claude-opus-5` / `claude-sonnet-5` | adaptive，預設就會想 | `-low` ～ `-max` ＋ `-nothink` |
| `claude-opus-4-8` / `claude-opus-4-7` | adaptive，**預設不想** | `-low` ～ `-max` ＋ `-nothink` |
| `claude-opus-4-6` / `claude-sonnet-4-6` | adaptive，預設不想，思考內容拿得到 | `-low` `-medium` `-high` `-max` ＋ `-nothink`（沒有 `-xhigh`） |
| `claude-opus-4.5` / `claude-sonnet-4.5` / `claude-haiku-4.5` | 舊式 budget_tokens，預設不想，思考內容拿得到 | `-low` ～ `-max`（budget 1024 / 2048 / 4096 / 8192 / 16384，`max_tokens` 要比 budget 大）；預設就不想所以沒有 `-nothink` |

**其他**：

| 名字 | 來源 | 備註 |
|---|---|---|
| `deepseek-chat` / `deepseek-reasoner` | DeepSeek 雲端 | 舊名，現在打到 v4-flash 的非思考 / 思考模式 |
| `deepseek-v4-pro` | DeepSeek 雲端 | 會思考 |
| `lm-gemma-4-12b` / `lm-gemma-4-e4b` / `lm-qwen3.5-9b` | 本機 LM Studio | 三個都看得到圖、都會思考、都叫得動工具；各有 `-nothink` |
| `ollama-*` | 遠端 Ollama @ 192.168.1.146 | 只有連得到那台時才通 |

LM Studio 沒載入模型時第一次呼叫會由它自己 JIT 載入，會慢一下。

### ChatGPT 訂閱（`chatgpt-*`）

走 litellm 內建的 `chatgpt/` provider，用 ChatGPT Pro 訂閱的額度打
`https://chatgpt.com/backend-api/codex/responses`（就是 codex CLI 用的那條），**不用
API key**。

**登入**：litellm 讀 `~/.config/litellm/chatgpt/auth.json`（環境變數
`CHATGPT_TOKEN_DIR` / `CHATGPT_AUTH_FILE` 可改），格式是攤平的
`{access_token, refresh_token, id_token, expires_at, account_id}`。codex CLI 的
`~/.codex/auth.json` 是把 token 包在 `tokens` 底下，**格式不同，不能直接 symlink**，
而且 litellm 會回寫這個檔（補 `expires_at`、refresh 後換新 token），symlink 會污染
codex 的。所以：

```bash
codex login                    # 沒登入過才要；會開瀏覽器
./chatgpt_auth_from_codex.py   # 從 ~/.codex/auth.json 轉一份到 litellm 的路徑
```

轉完就不用 device login。沒轉、或 token 整個失效時，litellm 會在**第一次呼叫時**
在 proxy 的 stdout 印 `Visit https://auth.openai.com/codex/device` 加一組 code，
要人去瀏覽器輸入，那個請求會卡到你輸完為止（15 分鐘逾時）。

**token 多久要重弄**：access_token 效期約 10 天（看 JWT 的 `exp`），到期 litellm
會自己拿 refresh_token 換，換到的新 token 只寫 litellm 自己那份。codex 那邊也會
自己 refresh。兩邊各自 refresh 會不會互相把對方的 refresh_token 弄失效，還沒驗過
（2026-09-20 兩邊都還在效期內）；哪一邊開始回 401 就重跑 `codex login` +
`chatgpt_auth_from_codex.py`。

**已知限制**（2026-09-20 實打 `chatgpt-gpt-6-astra`；思考深度那兩列七顆都打過）：

| | 結果 |
|---|---|
| 一般 chat completion | ✓ |
| `stream: true` | ✓ |
| function calling + 工具結果回填 | ✓ |
| `tool_choice: "required"` | ✓ 真的逼出呼叫 |
| parallel function calling | ✓ 一步 2 calls |
| 看圖（`image_url` base64 PNG） | ✓ |
| 思考深度 low / medium / high / xhigh / max | ✓ 七顆都吃到 xhigh；max 除了 gpt-5.5（400）都吃。reasoning_tokens 會隨檔變（astra 14 → 22 → 42） |
| 思考深度 none | astra ✗ 400 `Unsupported value: 'none' is not supported with the 'gpt-6-astra' model.`；**其他六顆 ✓** 200、reasoning_tokens 0（codex 的 cache 沒列 none，但後端真的收） |
| 思考深度 minimal / ultra | ✗ 400（ultra 是 codex 的多 agent 模式，API 不吃） |
| `response_format` JSON schema | ✗ 200 但被無聲丟掉，回 markdown（橋接時 `text.format` 沒傳過去） |
| prompt caching 指標 | △ `cached_tokens` 有時 1408、有時 0；只命中 codex 固定前綴，自己的長 prompt 沒命中過 |

其他要知道的：

- **每次呼叫都會被前置 codex 的 system prompt**（約 1400 tokens，「You are Codex…」），
  所以模型自稱 Codex、`prompt_tokens` 起跳就是 1638。你的 system message 會接在它後面。
  要換掉就設環境變數 `CHATGPT_DEFAULT_INSTRUCTIONS`。
- `model_info` 裡 `mode: responses` 和 `supports_native_streaming: true` 不是能力
  宣告，是**開關**：少了前者 litellm 會去打不存在的 `/chat/completions`（回一頁
  HTML）；少了後者 `stream: true` 會被 litellm 改成假串流，後端回 400
  `Stream must be set to true`。改那區不要順手刪。
- 模型清單抄 codex 的 `~/.codex/models_cache.json`，2026-09-20 裡面就 7 顆、全是 chat 型（沒有
  embedding / image / tts 那種），連 `visibility: hide` 的 `gpt-reserve`、`codex-auto-review` 都打得通，
  所以全收。litellm 內建資料庫只認到 gpt-5.4，不認得這幾顆，旗標全部手填。
- **分身焊的是 `extra_body: {reasoning: {effort: X}}`，不是 `reasoning_effort`**：litellm 1.87.5 把 chat
  橋接成 Responses 時只認得字串 low / medium / high / xhigh，`max` 會被**靜靜丟掉**變後端預設（前一版
  yaml 的 `-max` 其實沒生效）。寫成 dict `{effort: max}` 對 astra / reserve / auto-review 有效，但名字含
  `gpt-5` 的（sol / terra / luna / 5.5）會先被 litellm 的 GPT-5 chat 設定壓回字串再丟掉。`extra_body` 裡的
  `reasoning` 會原樣併進 Responses 請求，七顆都通（看 `--detailed_debug` 的 `-d '{...}'` 那行確認）。
  你自己在 client 傳 `reasoning_effort` 打基底名字照樣有效，但一樣只到 xhigh；要 max / none 就用分身。
- 這是訂閱額度不是 API 計費，litellm 算不出成本是正常的。

### Claude 訂閱（`claude-*`）

走 litellm 內建的 `anthropic/` provider 打 `https://api.anthropic.com`，但 key 不是 API key，
是 **Claude Code 登入後的 OAuth access token**（`sk-ant-oat01-…`），額度算在 Claude Pro 訂閱上。
這違反 Anthropic 的使用條款，只拿來做少量實驗，風險自負。

**token 從哪來、要不要定期做事**：不用。Claude Code 登入後把 token 放在
`~/.claude/.credentials.json`（`claudeAiOauth.accessToken`，效期約 8 小時，`expiresAt` 是毫秒），
到期 Claude Code 自己會續、把檔案換新。`claude_auth_from_claude_code.py` 是掛在
`litellm_settings.callbacks` 上的 pre-call hook，**每個請求**進來時看它打到的 deployment 是不是
`api_key: claude-code-login`（yaml 裡的佔位值），是就讀登入檔的最新 token 塞進去（檔案 mtime 沒變就用
快取），所以只要這台機器上 Claude Code 常在跑，token 永遠是新的。它**只讀不寫**那個檔、不自己
refresh；token 過期而 Claude Code 又沒在跑時會回 401 `Claude Code 的 accessToken 已過期而且還沒續`，
開一下 `claude` 讓它續掉就好。登入檔路徑可用環境變數 `CLAUDE_CODE_CREDENTIALS_FILE` 改。

為什麼不像 DeepSeek 那樣 `api_key: os.environ/…`：litellm 的 `os.environ/` 是**啟動時解析一次**，
幾小時後就是死 token；1.87.5 也沒有專門讀 Claude Code 登入檔的 provider（有 `chatgpt/` 沒有
`claude_code/`），所以用 hook。litellm 1.87.5 看到 `sk-ant-oat01-` 開頭的 key 會自動改用
`Authorization: Bearer` 加 `anthropic-beta: oauth-2025-04-20`，header 不用另外設。

**system prompt 有被強制**（2026-09-20 實打）：`claude-opus-5` / `claude-sonnet-5` 要求 Anthropic
`system` 的**第一個 block 一字不差**是 `You are Claude Code, Anthropic's official CLI for Claude.`，
少了、放第二塊、同一塊裡接別的字、改大小寫都會回 **429 `rate_limit_error`、訊息只有 `"Error"`**
（不是 401，很誤導）；`claude-haiku-4.5` 不檢查。litellm 把每個 OpenAI system 訊息各自轉成一個
block、順序不變，所以 hook 在 `messages` 最前面插一條那句話的 system 訊息，你自己的 system 變成第二塊，
實測照樣生效（給 `You are a pirate.` 照樣回 Ahoy）。代價是每次多 14 個 prompt tokens。

**思考**：opus-5 / sonnet-5 是 adaptive thinking，**沒給任何參數就會想**，而且走 OAuth 拿不到思考
內容 —— 回應裡 `thinking_blocks` 只有 signature、`reasoning_content` 是空字串、
`usage.completion_tokens_details.reasoning_tokens` 永遠 0（思考的 token 混在 `completion_tokens` 裡）。
yaml 標了 `supports_adaptive_thinking: true`，litellm 會把 `reasoning_effort` 轉成
`thinking: {type: adaptive}` + `output_config: {effort: …}`（吃 low / medium / high / xhigh / max，4.6 世代沒有 xhigh）；
`reasoning_effort: "none"` 只是不送 thinking、後端照樣想，真的要關要送 `thinking: {type: disabled}`，
`-nothink` 分身焊的就是這個。haiku-4.5 是舊式：預設不想，`reasoning_effort` low / medium / high 變
`thinking.budget_tokens` 1024 / 2048 / 4096，**`max_tokens` 一定要比 budget 大**不然 400
`max_tokens must be greater than thinking.budget_tokens`；它的思考內容拿得到。

**實測表**（2026-09-20，經 proxy 打；上半是三顆的完整功能，下半是 11 顆的思考檔位）：

| | opus-5 | sonnet-5 | haiku-4.5 |
|---|---|---|---|
| 一般 chat completion | ✓ | ✓ | ✓ |
| `stream: true` | ✓ | ✓ | ✓ |
| function calling + 工具結果回填 | ✓ | ✓ | ✓ |
| `tool_choice: "required"` | ✓ 真的逼出呼叫 | ✓ | ✓ |
| parallel function calling | ✓ 一步 2 calls | ✓ 一步 2 calls | ✓ 一步 2 calls |
| 看圖（`image_url` base64 PNG） | ✓（`max_tokens` 要夠，見下） | ✓ | ✓ |
| `reasoning_effort` low / high | ✓ 兩者都有 thinking block，low 省一半 token | ✓ high 有 block；low 沒有（它自己決定不想） | ✓ low 有 `reasoning_content`；medium / high 要 `max_tokens` > budget |
| `-nothink` / `thinking: disabled` | ✓ 沒有 thinking block | ✓ | 不適用（預設就不想） |
| `-xhigh` / `-max` | ✓ 有 thinking block | ✓ | ✓（budget 8192 / 16384） |
| `response_format` JSON schema | ✓ 回純 JSON | ✓ | ✓ |
| prompt caching（system block 加 `cache_control`） | ✓ 第二次 `cached_tokens: 3096` | ✓ 3097 | ✓ 但 prompt 要 **≥ 4096 tokens** 才會開始快取（2011 / 3331 都 0，5531 才命中） |

其他要知道的：

- **opus-5 的 `max_tokens` 別給太小**：它一定會先吐一個 thinking block，`max_tokens: 20` 會被
  吃光、`finish_reason: length`、`content` 是 `None`；給 200 就正常。
- **`-nothink` 不能標 `supports_reasoning: false`**（跟 `lm-*-nothink` 不一樣）：litellm 把
  model_info 註冊在後端模型名底下、同一顆的所有分身共用、最後一筆贏，標了 false 會讓 `thinking` /
  `reasoning_effort` 變成不支援參數被 `drop_params` 吞掉，整組 opus-5 的分身一起失效（踩過一次）。
- 沒掛 callback 就打 `claude-*` 會回 401 `invalid x-api-key`（佔位值被當真 key 送出去了），
  這是刻意的失敗方式。
- `/v1/messages`（Anthropic 原生格式的 pass-through）沒接：hook 只處理 chat completions 的
  `messages`，走原生格式 system 前綴不會自動補。
- `/v1/models` 用這個 token 直打 Anthropic 看得到 11 顆，yaml 全收；它回的 `capabilities` 就是旗標的依據
  （哪顆吃 adaptive、哪顆 effort 有 xhigh / max）。API id 帶日期的三顆（`claude-opus-4-5-20251101`、
  `claude-sonnet-4-5-20250929`、`claude-haiku-4-5-20251001`）名字用短的 `claude-opus-4.5` 那種。
  **每顆都要 `supports_xhigh_reasoning_effort` / `supports_max_reasoning_effort`** 標對：litellm 靠這兩個旗標
  決定要不要送 `output_config.effort`，沒標就當不支援、`drop_params` 靜靜丟掉，你以為 xhigh 其實是預設。
- **11 顆的思考檔位**（2026-09-20，每顆每檔各打一次；prompt 太簡單時 adaptive 會自己決定不想，
  所以用「1～1000 被 3 或 5 整除但不被 15 整除」那題）：

  | | 預設 | low ～ max | nothink |
  |---|---|---|---|
  | fable-5-1 / fable-5 | 會想 | ✓ 五檔（低檔常直接在正文裡推、不出 thinking block） | ✗ 400 `"thinking.type.disabled" is not supported for this model` |
  | opus-5 / sonnet-5 | 會想 | ✓ 五檔（sonnet low 常不想） | ✓ |
  | opus-4-8 / opus-4-7 | **不想** | ✓ 五檔（低檔常不想，xhigh / max 一定想） | ✓（跟預設一樣） |
  | opus-4-6 / sonnet-4-6 | 不想 | ✓ 四檔（沒 xhigh），**思考內容拿得到**（`reasoning_content`） | ✓ |
  | opus-4.5 / sonnet-4.5 / haiku-4.5 | 不想 | ✓ 五檔都是 budget_tokens，思考內容拿得到；`max_tokens` ≤ budget 就 400 | 不適用 |
- 這是訂閱額度不是 API 計費，litellm 算不出成本是正常的；回應 header 有
  `anthropic-ratelimit-unified-5h-utilization` / `-7d-utilization` 可以看用了多少（proxy 不轉出來，
  要看得直打）。

**開關思考統一成「換名字」**：兩家的機制其實不同，是 yaml 把它們包成同一種用法。
DeepSeek 本來就只能換名字（也**不吃** `reasoning_effort`，2026-08-05 給 `"none"`
照樣想了 92 字）；LM Studio 吃 `reasoning_effort`，所以每顆模型多開一個 `-nothink`
分身，把 `reasoning_effort: "none"` 焊死在 `litellm_params` 裡。程式端永遠只換模型
字串，不用記哪顆用哪個旋鈕。

### `drop_params: true` 會無聲吞掉參數

這份設定開了 `drop_params: true`，而 litellm 的支援參數清單裡**沒有**
`reasoning_effort`（`/model/info` 的 `supported_openai_params` 可以查）。
於是它會被**丟掉而且不報錯、不警告** —— 你以為關掉思考了，其實沒有。

解法是那三個 `lm-*` 都加 `allowed_openai_params: ["reasoning_effort"]` 強制放行。
這是 `drop_params: true` 的一般性代價：**以後任何「參數送了沒反應」都先往這裡查。**

試過但沒用的兩招，別再繞回去：`chat_template_kwargs: {enable_thinking: false}`
（無效，思考照舊）、prompt 尾巴加 `/no_think`（反效果，它會開始思考「什麼是
/no_think」，思考字數反而翻倍）。

LM Studio 那區用 **YAML anchor**（`&lm` / `<<: *lm`）收掉重複。`-12b-nothink` 是唯一
沒有自己覆寫 `model:` 的一筆，完全靠繼承 —— 改那區之後要特別驗它有沒有打到正確的
模型（看 LM Studio 實際載入了哪顆）。

## `model_info` 是實測出來的，不要信 litellm 的內建資料庫

`/model/info` 的答案有兩個來源：`litellm.yaml` 裡手寫的 `model_info`，
和 litellm 自己帶的模型資料庫。**後者對雲端模型也會過期**：

- **2026-08-05**：litellm 說 `deepseek-reasoner` 的 `supports_function_calling` 是
  `False`，但實際打過去它照樣回 tool_calls。所以 yaml 裡覆寫成 `true` ——
  不覆寫的話 `llms` 會在本地就把你擋死，請求根本送不出去。**（謊報成 False）**
- **2026-08-08**：litellm 說 DeepSeek 的 `supports_response_schema` 是 `True`，
  實際送 `response_format` 回 **400 `This response_format type is unavailable
  now`**。yaml 覆寫成 `false`。**（謊報成 True）**
- 本機模型（Ollama、LM Studio）litellm 一律不認得，不宣告就全是 `None`。

兩個方向都會錯，所以規矩是：**要宣告某個旗標之前，先實打一次。**

2026-08-08 對 `deepseek-chat` 和 `lm-gemma-4-e4b` 各打了一輪，七項全部有結論：

| | DeepSeek | LM Studio |
|---|---|---|
| `tool_choice`（`"required"` 真的逼得出呼叫） | ✓ | ✓ |
| `parallel_function_calling`（一步吐 2 個 call） | ✓ | ✓ |
| `response_schema` | ✗ 400 | ✓ |
| `prompt_caching`（`usage.cached` 真的有數字） | ✓ 512 | ✗ 一直是 None |

2026-08-10 遠端 Ollama 恢復連線後，把四顆都經 proxy 實打了一輪：

| | qwen3-32b | qwen2.5-14b | deepseek-r1-8b | gemma3-1b |
|---|---:|---:|---:|---:|
| 一般／串流對話 | ✓ | ✓ | ✓ | ✓ |
| `reasoning_effort: "none"` | ✓ | 不適用 | ✓ | 不適用 |
| function calling | ✓ | ✓ | ✗ | ✗ |
| `tool_choice: "required"` | ✗ 無聲忽略 | ✗ 無聲忽略 | 不適用 | 不適用 |
| parallel function calling | ✓（一步 2 calls） | ✓（一步 2 calls） | ✗ | ✗ |
| JSON schema | ✓ | ✓ | ✓ | ✓ |
| prompt caching 指標 | ✗ | ✗ | ✗ | ✗ |

最後一列是指 OpenAI usage 裡可觀察到的 cache hit；同一份 800+ token prompt 連打兩次，
四顆的 `prompt_tokens_details` 都是 `None`。Ollama 內部可能仍重用 KV cache，但 proxy
呼叫端看不到，能力表因此保守宣告為 `false`。

`tool_choice` 要特別小心：請求不會報錯，但模型會違反 `required` 直接回答文字，所以
不能只看 HTTP 200 就宣告支援。`/api/show` 回報的原生能力也吻合：兩顆 Qwen 有
`tools`，qwen3 / DeepSeek R1 有 `thinking`，四顆都沒有 `vision`。

qwen2.5 的 tool calling **有能力但不穩**：英文「use the available tool」能正常回
`tool_calls`，中文「台北天氣如何？」直打 Ollama `/api/chat`（temperature 0）連續
5 次都只回泰文夾中文的普通文字；經 proxy 也曾把 `<tool_call>` 當正文吐出。
同一份 schema 換 qwen3-32b 則能完成中文 tool call 和工具結果回填。需要可靠工具鏈時
優先用 qwen3，不要把 qwen2.5 的 `supports_function_calling: true` 解讀成每次都會叫。

## 改完設定要做兩件事

1. **重啟 proxy** —— 設定不會熱載入。
2. 程式端 `LLM.clear_caps_cache()` —— 能力表是照 proxy 根位址快取的，
   **查不到的空表也算查過**，不會自動重試。

## 踩過的

- **PowerShell 預設擋 `.ps1`**，`start_litellm.ps1` 跑不動時多半是 ExecutionPolicy
  的問題，不是腳本錯。
- **`.gitattributes` 是必要的，不是潔癖。** 沒有它，Windows checkout 會把 `.sh`
  轉成 CRLF，回到 Linux 執行就是 `bad interpreter: /usr/bin/env bash^M`。
