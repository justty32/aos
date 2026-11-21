llm kernel 加「思考程度」：信的 body 多一個 `reasoning_effort` 鍵，llm kernel 照每包的 `reasoning_efforts` 清單查收不收，`llm_http` 走 Responses API 把程度接成 input 最後一個 `configuration_update`，換程度後前綴快取照中；隊 kernel 也會轉。

← [2026-11-21](README.md)｜前情：[session_key 實測](session-key-實測-1121.md)｜程式說明：[kernel_llm docs/01](../../../py/tools/aos/kernel_llm/docs/01-用法.md)、[範本 kernel docs/01](../../../templates/kernel/docs/01-llm-kernel.md)

線 `top-1121-effort`，11-21 家機。

## 使用者原話

- 「對了，現在能調整思考程度嗎？」
- 「要測，然後全加。善用指示詞，不然json會很膨脹」
- 「或是llm kernel要接受的請求中，允許添加思考程度這個key，然後具體的則由llm kernel處理」
- 「走乙吧」

甲是「每個思考程度在 kernel.json 開一包（`sol-high` 這種）」，乙是「請求帶思考程度、llm kernel 自己換」。使用者選乙，甲沒做完就停了，沒留東西。

## 測了什麼

直接打 LiteLLM（localhost:4000，沒改它的設定），一題要想一下的小題：「{1..8} 的排列，每個位置最多移 2 格、而且不能留在原位，有幾種」（答案 45）；另外兩題比較簡單（答案 49、48）和一題比較難（{1..10}、最多移 3 格，答案 2692）。數字是上游回的 `reasoning_tokens` 和整趟秒數。

| 模型名 | 題 | 推理 token | 秒 | 答對 |
|---|---|---|---|---|
| sol-low | 45 | 1,245 | 42.6 | 對 |
| sol-high | 45 | 1,147 | 27.1 | 對 |
| sol-max | 45 | 1,334 | 29.5 | 對 |
| sol-low | 2692 | 2,059 | 182.7 | 對 |
| sol-high | 2692 | 3,132 | 65.9 | 對 |
| sol（不帶尾碼）、medium、high、xhigh、max | 49 | 14、15、15、29、32 | 2～3 | 都對 |
| sol-nothink | — | HTTP 400：`'none' is not supported with the 'gpt-6.1-sol' model` | | |
| luna-low／luna-high／luna-nothink | 45 | 1,077／49／0 | 21.3／2.2／1.2 | 錯／錯／錯 |
| terra-low／terra-high／terra-nothink | 45 | 962／979／0 | 18.8／18.9／1.3 | 錯／對／錯 |
| astra-low／astra-high | 45 | 516／515 | 20.3／16.1 | 對／對 |
| sol＋`reasoning_effort: low`／`xhigh` | 45 | 776／1,445 | 17.4／40.7 | 對／對 |
| sol＋`reasoning_effort: none` | — | HTTP 400（同上） | | |

換程度時快取（同一個 `litellm_session_id`、約 9,500 token 的長提示）：

| 依序 | 模型名 | cached |
|---|---|---|
| 1 | sol-low | 0（第一次） |
| 2 | sol-low | 9,344 |
| 3 | sol-high | 0 |
| 4 | sol-max | 0 |
| 5 | sol（不帶尾碼） | 0 |
| 6 | sol＋`reasoning_effort: xhigh` | 0 |
| 7 | sol-high | 0 |
| 8 | sol-low | 9,344 |
| 9 | sol＋`reasoning_effort: xhigh` | 9,344 |
| 10、11 | sol-high、sol-max | 9,344、9,344 |

真模型這次共叫約 43 次：直接打 37 次，暫存樹裡經 llm kernel 6 次。

## 結論

- **程度真的有送到上游**：sol 帶 `none` 兩種寫法都被上游擋（400，訊息列出它收的五檔），luna、terra 的 `-nothink` 推理 token 歸 0。
- **推理 token 跟程度不是一直線**：模型會看題目難度自己決定想多久；小題各檔差不多，難題 high 比 low 多想五成（3,132 對 2,059）。luna 這題三檔都答錯，terra 只有 high 答對。
- **帶尾碼的模型名與 `reasoning_effort` 參數都有效**，但代理文件（`~/repo/llm_proxy/docs/chatgpt.md`）寫明 `reasoning_effort` 只到 xhigh，`max` 會被 LiteLLM 靜靜丟掉、`none` 也只能走分身；所以 llm kernel 範本用**模型名加尾碼**，五檔加 none 都走得到。
- **不帶尾碼＝上游預設程度**：LiteLLM 那一條不帶 `reasoning`；codex 的 `~/.codex/models_cache.json` 寫的預設是 gpt-6.1-sol、gpt-6.1-terra 為 low，gpt-6-luna、gpt-6-astra 為 medium（推理 token 太吵，量不出來，以這份為準）。
- **哪幾檔收**：sol（6.1）、astra 收 low、medium、high、xhigh、max；luna、terra 再多收 none。
- **換程度會讓那一輪沒中快取**：上游看起來每個程度各有一份快取，第一次用某個程度沒中，之後同程度照中，換回用過的程度多半也中（第 7 輪 sol-high 第二次仍沒中，第 10 輪才中，所以不保證）。帶尾碼或帶參數都一樣。

## 做法（乙，第一版；已被下面「第二輪」取代）

- **信**：`{"endpoint": "sol", "effort": "high", "request": {...}}`。`effort` 跟 `endpoint` 並排、不放進 `request`：它是給 llm kernel 看的，跟 `endpoint` 一樣由 kernel 換成上游要的樣子。
- **包**：`"efforts": {程度名: 字串或物件}`。字串＝接在 `model` 後面（`"high": "-high"` 讓 `chatgpt-gpt-6.1-sol` 變成 `chatgpt-gpt-6.1-sol-high`），物件＝疊到那包上再交給 endpoint 函數（`fixed` 一個鍵一個鍵合併，例如 `{"fixed": {"reasoning_effort": "low"}}`，給不走 LiteLLM 分身的上游用）。kernel 自己看的鍵（`exec`、`slots`、`budget`、`speed`、`backend`、`session_key`、`efforts`、`effort`）物件裡不能改。包可另寫 `"effort": "low"`＝信沒寫程度時用哪一檔。
- **指示詞**：兩張尾碼表放 kernel.json 頂層 `effort_suffixes`，各包用現成的 `$ref`（陣列＝合併）指過去，一包只多一行：

```json
 "effort_suffixes": {"litellm": {"low": "-low", "medium": "-medium", "high": "-high", "xhigh": "-xhigh", "max": "-max"},
                     "litellm_none": {"none": "-nothink"}},
 ...
   "luna":  {..., "model": "chatgpt-gpt-6-luna", ...,
             "efforts": {"$ref": ["#/effort_suffixes/litellm", "#/effort_suffixes/litellm_none"]}, "effort": "low", ...},
   "terra": {..., "efforts": {"$ref": ["#/effort_suffixes/litellm", "#/effort_suffixes/litellm_none"]}, ...},
   "sol":   {..., "efforts": {"$ref": "#/effort_suffixes/litellm"}, ...},
   "astra": {..., "efforts": {"$ref": "#/effort_suffixes/litellm"}, ...},
```

  kernel.json 5,983 → 6,553 位元組（多 570）。
- **包沒寫 `efforts`**：信裡的 `effort` 不理、請求原樣送（C-48 不認得的鍵就忽略），所以換到 `fake`、`stupid-fast` 不會出錯。
- **包有寫、但沒有那一檔**：`RequestBad effort "none" is not offered by endpoint sol (it offers: low, medium, high, xhigh, max)`，不打上游。`effort` 不是非空字串＝`RequestBad`。
- **原本四包不帶程度時照舊**：sol、terra、astra 沒有預設檔＝原本的模型名；luna 原本的模型名就是 `chatgpt-gpt-6-luna-low`，改成 `chatgpt-gpt-6-luna`＋`"effort": "low"`，暫存樹實測不帶程度時上游收到的仍是 `chatgpt-gpt-6-luna-low`。
- **窗**：`endpoints.json` 每包多 `efforts`（程度名陣列）與 `effort`（預設檔），`aos-llm ls --json` 看得到；`aos-llm ls` 的文字欄位是 C++ 固定的，沒加。
- **agent-fsm**：`llm.json` 的 `effort` 由 `brain.py` 填進信的 `effort`；`llm_settings.KEYS` 與 `interfaces.json` 的 `llm_keys` 加了 `effort`，所以 `aos-agent llm set effort=high` 不會跳警告。值不是非空字串＝`CfgBad`（defs check 也擋）。

## 暫存樹實測（經 llm kernel）

`~/.aos/scratch/top-1121-effort/tree`（`git archive HEAD` 的乾淨複本疊上這條線的檔、在複本裡 `install.py`，抄 `templates/start-api`，ann 的 `llm.json` 換成 `{"model": "sol"}`）：

| 輪 | ann 的設定 | 上游收到的模型 | prompt | cached |
|---|---|---|---|---|
| 1 | 沒設程度 | chatgpt-gpt-6.1-sol | 12,553 | 0 |
| 2 | 沒設程度 | chatgpt-gpt-6.1-sol | 12,570 | 12,416 |
| 3 | `effort=high` | chatgpt-gpt-6.1-sol-high | 12,587 | 0 |
| 4 | `effort=high` | chatgpt-gpt-6.1-sol-high | 12,604 | 12,416 |
| 5 | `llm rm effort` | chatgpt-gpt-6.1-sol | 12,621 | 12,416 |

另外 `aos-llm ask` 直寄：sol 帶 `none` 回上面那行 `RequestBad`；luna 不帶程度，帳本記的模型是 `chatgpt-gpt-6-luna-low`；fake 帶 `high` 照答 `FAKE ANSWER`。

## 改了什麼

- `py/tools/aos/kernel_llm/packs.py`：讀 `efforts`／`effort`、驗形狀、換那組；窗多兩個鍵。測試 `tests/test_effort.py`（新，11 支）。說明 `docs/01-用法.md`。
- `templates/kernel/llm-kernel/kernel.json`、`templates/start-api/llm/kernel.json`（逐字相同）：上面那段。
- `templates/agent-fsm/{brain.py,llm_settings.py,interfaces.json}` 與 `templates/start-api/agents/ann/` 的同名三檔（逐字相同）：`effort` 鍵。測試 `templates/tests/agent-fsm/test_effort_setting.py`（新，4 支）。
- `templates/kernel/docs/01-llm-kernel.md`：包表補 `astra`、加一段思考程度。
- 知識庫 `aos/brain.json`、`aos/me/self_llm.json`：各補一句。

測試（`git archive HEAD` 46dee22f7 的兩份乾淨複本，一份原樣、一份只疊上面這些檔，各自 `install.py`，unittest）：`py/tests` 723／723 兩邊都過；`kernel_llm` 80 → 91；`templates/tests/agent-fsm` 215 → 219；`templates/tests` 頂層 29 兩邊都過（含 `test_start` 比對兩份逐字相同）；`kernel-chain-check` 兩邊都過。`apps/feedback` 18 個錯、`image-move-check` 逾時，原樣那份一樣，是複本沒有 `wf/` 與機器環境的關係，跟這次無關。

## 還沒做、要知道的

- **`py/aos/agent_spec_parts.py` 的 `LLM_KEYS` 沒加 `effort`**：那個檔有線 `top-1121-hook5` 沒交的改動，照規矩不碰。影響：用 `agent.py` 編譯定義時在 `llm` 寫 `effort` 會被擋（`llm key 'effort' is not one of llm_keys`），編譯出的 `interfaces.json` 也不列它（`aos-agent llm set` 會跳警告但照存、照用）。hook5 交了之後補一行。
- **隊 kernel（`llm_forward`）不轉 `effort`**：它只轉 `endpoint`、`request`、`priority`，隊 kernel 的包也沒宣告 `efforts`，所以經隊 kernel 的 agent 設了程度不會生效。
- **順手發現（沒改）**：文件說一包可以整包寫成 `{"$ref": "packs/x.json"}`，但這樣寫時窗 `endpoints.json` 只剩 `speed`（`cost`、`summary`、`slots`、`efforts` 都不見），因為 `_read_packs` 先挑鍵再解指示詞。暫存複本實測 `{'a': {'speed': 'normal'}}`。請求本身照常。
- **跟 11-10 那條的關係**：11-10 使用者「model所指向的東西，他就是可以得到快取優勢的東西，然後agent能調的，就是一些與快取無關的」，當時代定「reasoning 類不開」（[self-tools/05](../10/self-tools/05-llm設定改名與ls.md)）。這次使用者自己要請求帶程度；實測換程度只讓第一次用那檔時沒中，之後照中，不是整份快取失效。`proto8/docs` 沒改，建議加註的地方：CONCEPTS／NORMS 講問腦的信的格式處，加「body 另有選填的 `effort`（11-21），由 llm kernel 照包的 `efforts` 換；換程度那一輪多半不中快取」。
- **`~/aos-home` 沒碰**。要吃到：repo 跑 `python3 install.py`（換 `lib/` 的 packs.py 與範本），`~/aos-home/llm/kernel.json` 照上面那段加 `effort_suffixes` 與四包的 `efforts`（luna 那包的 `model` 改成 `chatgpt-gpt-6-luna`、加 `"effort": "low"`），ann 等 agent 的定義夾是 agent-fsm 的抄本，要另外換上新的 `brain.py`、`llm_settings.py`、`interfaces.json` 才認 `effort`；之後 `aos-agent -d .stack --target ann llm set effort=high`。

## 第二輪：換程度要接上快取、改名、隊 kernel 轉送（11-21 稍晚）

使用者原話：「換了思考程度就沒了快取，不對吧，理論上應該是要可以的，去想辦法。effort...改叫reasoning_effort吧，說清楚。kernel轉送不帶effort...要補。」

### 快取斷在哪一層（真模型，同一個 `litellm_session_id`、約 9,500 token 的長提示、每組換一個新開頭）

| 組 | 依序送的 | cached |
|---|---|---|
| A：不帶尾碼＋`reasoning_effort` 參數 | low、low、high、low、high | 0、0、0、9,344、9,344 |
| B：同上，每次隔 8 秒 | low、low、low、high、high、low | 1,408、0、9,344、1,408、9,344、9,344 |
| C：接著 B，換成帶尾碼的名字 | sol-low、sol-high、sol-xhigh、sol-xhigh | 9,344、9,344、0、9,344 |
| D：LiteLLM 的 `/v1/responses`，頂層 `reasoning.effort` 固定 low | 不接／不接／接 `configuration_update` high／接 max／頂層改 high | 0、9,344、9,344、9,344、1,408 |

另外兩次確認 `configuration_update` 真的有作用：sol 接 `none` 被上游擋（400，跟頂層寫 none 同一句）；terra 頂層 `none`（推理歸 0）再接 `xhigh`，推理 1,034 token、答對。

- **不是 LiteLLM 的分身名**：C 組 sol-low、sol-high 直接吃到 B 組用參數暖好的快取；LiteLLM 送上游的請求只有 `model`（分身名換回本名）、`input`、`instructions`、`reasoning` 這幾個鍵（`llms/chatgpt/responses/transformation.py` 的 `allowed_keys`），session id 放在標頭，同一個寄件人不變。
- **不是我們的 `session_key`**：值只由寄件人的 stack 路徑決定（`session.py`），換程度不變；暫存樹裡 ann 換程度前後是同一個值。
- **是上游**：頂層的 `reasoning.effort` 換了，快取就從頭算；每個程度第一次沒中、之後中，就是上游一個程度一份快取。OpenAI 文件說換頂層程度會改寫藏起來的系統指示，要保住前綴就把程度寫成 input 最後一個 `{"type": "configuration_update", "reasoning": {"effort": "high"}}`（[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)，支援的是 GPT-6 以後的模型）。D 組實測：接這個項目快取照中，改頂層就只剩 1,408。
- 另外看到：就算程度不換，同一個開頭剛開始的頭兩次偶爾也會沒中（A、B 組第 2 次），之後才穩。是上游的事，跟程度無關。

### 修法

chat completions 帶不了 `configuration_update`（LiteLLM 1.87.5 把 chat 轉成 Responses 時只轉訊息，見 `completion_extras/litellm_responses_transformation`），所以：

- `llm_http` 加 `endpoint.api`：沒寫或 `"chat"` 照舊；`"responses"` 改送 `{url}/responses`，請求從 chat 的樣子換過去（system→instructions、工具呼叫與結果、圖片），回覆與 usage 換回 chat 的樣子（新檔 `responses_api.py`）。llm kernel 給的思考程度：`responses` 時接成 input 最後一個 `configuration_update`、頂層不動；`chat` 時填成請求的 `reasoning_effort` 參數（那樣換程度就會斷快取，給只有 chat 的端點用）。
- 範本 sol、luna、terra、astra 四包加 `"api": "responses"`。不帶程度時送給上游的東西跟以前一樣（同一個模型名、同樣沒有程度）。
- 帶尾碼的模型名不用了：程度一律走 `configuration_update`，max、none 也走得到。luna 的模型名維持 `chatgpt-gpt-6-luna-low`（low 由 LiteLLM 那一條帶在頂層、一直不變），所以拿掉第一版的「包的預設程度」。

### 改名對照（不留舊名）

| 第一版 | 現在 |
|---|---|
| 信的 body `effort` | `reasoning_effort`（給 kernel 看，跟 `endpoint` 並排；不是 `request` 裡送上游的同名參數） |
| 包的 `efforts`（程度→尾碼或物件） | `reasoning_efforts`：收哪些程度的名字陣列，或 `"forward"`（不查、交給下一層 kernel） |
| 包的 `effort`（預設程度） | 拿掉 |
| 頂層 `effort_suffixes` | `reasoning_effort_levels`：`{"gpt": ["low", "medium", "high", "xhigh", "max"], "gpt_none": ["none"]}` |
| agent `llm.json` 的 `effort`、`aos-agent llm set effort=high` | `reasoning_effort`、`aos-agent llm set reasoning_effort=high` |
| `llm_settings.effort_of` | `reasoning_effort_of` |

kernel 收了的程度寫進交給端點函數的 `request.json` 頂層 `reasoning_effort`，也記進帳本 `ledger.jsonl` 那一列。

### 隊 kernel

`llm_forward` 把 stdin 的 `reasoning_effort` 原樣放進轉寄信；`templates/kernel/llm-team/kernel.json` 的 sol、terra、luna 三包寫 `"reasoning_efforts": "forward"`，由主 kernel 查。

### 暫存樹實測（`tree3`：`git archive HEAD` 19020832c 疊上這一輪的檔；ann 用 sol；另掛一台隊 kernel `team`）

| 輪 | ann 的設定 | cached |
|---|---|---|
| 1 | 沒設 | 0（第一次） |
| 2 | 沒設 | 12,416 |
| 3 | `reasoning_effort=high` | 12,416（換了照中） |
| 4 | high | 0（上游偶爾沒中，同上面 A、B 組） |
| 5 | `reasoning_effort=low` | 10,496 |
| 6 | 拿掉 | 10,496 |
| 7 | high | 12,544 |
| 8 | high | 12,544 |
| 9 | `reasoning_effort=medium` | 12,416（換了照中） |
| 10、11 | medium，叫一次工具再回答 | 12,544、12,544 |

工具呼叫走 Responses 一來一回正常（`peek_now_time` 叫了、回了時間）。帳本每列記了 `reasoning_effort`。隊 kernel：寄 `team` 的 sol 帶 `xhigh`，主 kernel 帳本記 `sol xhigh`、寄件人是隊 kernel；帶 `none` 由主 kernel 回 `RequestBad reasoning_effort "none" is not offered by endpoint sol (...)`，隊 kernel 原樣轉回。

真模型這一輪約 37 次（直接打 25、暫存樹 12）。

測試（`git archive HEAD` 19020832c 兩份乾淨複本，一份原樣、一份疊這一輪的檔，各自 `install.py`，unittest，兩份同時跑）：`py/tests` 728／728 兩邊都過；`kernel_llm` 91 → 89（`test_effort.py` 重寫成 9 支，原本 11 支）；`llm_http` 39 → 47（新 `test_responses.py` 8 支）；`llm_forward` 6 → 7；`templates/tests/agent-fsm` 219 兩邊都過；`templates/tests` 頂層 29 兩邊都過（含 `test_start`：兩份 kernel.json 逐字相同）；`kernel-chain-check` 兩邊都過。`apps/gdb` 的 live 測試兩邊都有 ctrl-c 那兩支沒過，疊檔那份多一支 `test_04`，單獨重跑會過，是兩份同時跑太擠；`apps/feedback`、`image-move-check` 跟第一輪一樣是複本環境的關係。

### 還沒做

- `py/aos/agent_spec_parts.py` 的 `LLM_KEYS`：線 `top-1121-hookfire` 改那個檔時順手加 `reasoning_effort`，這條線沒碰。
- `~/aos-home` 沒碰；要吃到見回報。
