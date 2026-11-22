agent-fsm 每輪問腦的輸入成本重量（HEAD 139d8dd2b）：aos 送出的前綴每輪逐字穩定、沒有可在 aos 這側不改行為就修的快取問題；現在沒中快取的 token 八成來自上游偶發整段沒中（約 18% 的後續輪），其次是 LiteLLM 每輪自動加的約 1,620 token codex 指示，要再省都得使用者定。

← [2026-11-22](../README.md)｜進度 `prompt-cost-cache`｜前情：[session-key 實測 1121](../../21/session-key-實測-1121.md)、[工具說明瘦身 1121](../../21/tool-desc-瘦身-1121/README.md)｜線 `prompt-cost-1122`｜逐輪數字 [01-逐輪數字.json](01-逐輪數字.json)｜選項 A 實驗 [02-選項A實驗](02-選項A實驗.md)

## 一頁結論

- **「九成六是工具說明、快取沒命中」是 11-20 的舊數字。** 11-21 已加 `session_key`、工具說明瘦身、self 只開兩支。今天 HEAD 的起手 ann（36 支工具）問一句話：送出 25,142 bytes，其中工具 23,225 bytes（92%）；上游算的 6,225 token 裡，工具 4,199（67%）、instructions 2,011（其中約 1,620 是 LiteLLM 自己加在最前面的 codex 指示、約 391 是 aos 的系統文字）、對話 15。
- **快取現在大多會中，但不穩。** 暫存樹 sol 連問 19 輪（現行 responses 路線）：第 1 輪冷啟動本來就沒得中，後面 18 輪有 3 輪整段是 0，其他每輪中 6,144～6,528；整體命中 76.7%。chat 路線 5 輪也有 1 輪整段 0。活樹 `~/aos-home` 的 ann（唯讀看 llm kernel 帳本）33 封裡，間隔 60 秒內的 25 封也有 8 封整段 0。
- **沒中不是 aos 造成的。** 錄下 aos 真正送出去的每一封請求逐封比：工具清單、instructions 逐字相同，對話每輪只在後面接，session id 固定；沒中的那幾輪跟前一輪的間隔（1.7 秒）和有中的一樣。上游回覆的逐欄位歸屬也顯示：有中時工具 4,199 全中、instructions 中 1,945，沒中時兩欄都是 0，是整段落到沒有這份快取的地方。
- **現在沒中快取的 token，大頭就是那幾輪整段沒中。** 暫存樹後續 18 輪沒中快取合計 22,157 token，其中 18,995（86%）來自那 3 輪；活樹 25 封 109,089 裡 86,706（79%，8 封整段 0）。有中的輪每輪只付 100～200 token。
- **aos 這側「不改行為就能省」的：查過，沒有可做的**（下面「查了什麼」）。這條線沒改程式、範本、工具說明，**不用 install.py**。
- **要再省，五個選項都要你定**（下面「要你定的」）；影響最大的是 A（讓上游拿到每隻 agent 自己的快取鍵），但要改的是 LiteLLM 代理，不在 aos。

## 做法

- 乾淨複本：`git archive 139d8dd2b` 抄到 `~/.aos/scratch/prompt-cost-1122/src`、在複本裡 `install.py`；所有指令經一支 bash 腳本清掉 `AOS_*` 再跑。
- 記錄代理：自寫一支小 HTTP 伺服器（`recsrv.py`，暫存夾裡），把 llm_http 送出的每一封請求原樣存檔。`fake` 模式自己回答（第一次叫 peek_now_time、之後答 ok）；`forward` 模式轉給 4000 埠的 LiteLLM，連回覆一起存。
- 兩棵暫存樹（`templates/start-api` 抄的）：`tf` 掛兩隻走假模型，`ts` 掛兩隻走 sol，`sr`＝responses（範本現行）、`sc`＝chat；包的寫法照範本的 `sol`（同一個 `session_key`），只把 url 換成記錄代理。
- 真模型共叫 25 次：sr 19（15 句「Reply with one word: ok」加一題寫檔、讀回、列夾的小任務，那題 4 次）、sc 5、拿掉工具重送第一封 1 次（量工具佔多少）。
- 活樹只讀了 `~/aos-home/llm/kernel.json`、`agents/ann/tools.json` 與 llm kernel 的 `ledger.jsonl`（只有用量、沒有內容）。

## 數字

### 一封請求拆帳（第一輪，問一句話）

| 段 | bytes（aos 送出） | token（上游算） |
|---|---|---|
| 工具 36 支 | 23,225 | 4,199 |
| instructions | 1,634（aos 系統文字） | 2,011（加上 LiteLLM 補的 codex 指示，約 1,620） |
| 對話 | 113 | 15 |
| 合計 | 25,142 | 6,225 |

- 工具 token 是上游回覆的 `attribution.request_fields` 直接給的；拿掉工具重送同一封是 2,026 token，對得上。
- 上游的排列是「工具 → instructions → 對話」：有中時快取的是工具全部加 instructions 前 1,945，所以**工具一變，後面整段都失效**；instructions 或對話變，工具那段照中。
- 各包約多少 token（照 4,199 / 23,225 換算）：json 9 支 1,039、look 6 支 844、mailbox 3 支 421、change 5 支 401、self 2 支 379、gadgets 4 支 282、todo 184、index_view 178、shell 2 支 177、goal 154、delete 2 支 134。

### 快取逐輪（暫存樹，prompt／cached）

- sr（responses）19 輪：6225/0、6245/0、6265/6144、6285/6144、6305/6144、6325/6144、6345/6144、6365/0、6385/0、6405/6272 起連 6 輪 6272，小任務 4 輪 6553/6144、6596/6400、6636/6144、6690/6528。
- sc（chat）5 輪：6225/0、6245/6144、6265/0、6285/6144、6305/6144。
- 跟前一輪的間隔：中與沒中都是 1.7 秒（前一封回來到下一封進 kernel）。

### 改前改後（這條進度一路下來，同樣是起手 ann 問一句話）

| 時間 | 狀態 | 每輪 prompt token | 第 2 輪起快取 |
|---|---|---|---|
| 11-20 | 原樣 | 約 12,600 | 0 |
| 11-21 | 加 `session_key`（chat） | 12,553 | 約 99%（那天 4 輪全中） |
| 11-21 | 工具說明瘦身、self 只開兩支 | 5,837 | — |
| 11-22 今天 HEAD | 加上 responses 路線、系統文字多兩三句 | 6,225 | 82% 的輪整段中、18% 整段 0；整體 76.7% |

這條線自己沒改東西，所以沒有「這條線改前改後」；表上最後一列就是現況的量測。11-21 那 4 輪全中、今天有幾輪沒中，看起來是上游那邊的波動，跟 responses 或 chat 無關（兩條路今天都會掉）。

## 快取為什麼還會沒中：查了什麼

| 懷疑 | 結果 |
|---|---|
| 每輪有變動的東西（時間、亂數） | 沒有：錄下的請求（假模型 18 封、sol 24 封）每隻 agent 的 instructions、工具逐字相同；系統文字叫 agent 用 peek_now_time 查時間，不塞進提示 |
| 工具順序不穩 | 不會：照名字排序，每輪一樣。**加一支工具時**它照名字插在中間（加 self_history 排到第 28 支），那一輪插入點之後的工具與整段對話失效一次，之後又穩定。活樹帳本有兩輪只中 3,712，像是這種情況，ann 的 stack 已不在、沒法確認 |
| 對話被改寫 | 不會：每輪只在後面接；`/compact`、`/clear` 會改，那是設計如此 |
| session id 會變 | 不會：llm kernel 按寄件人 stack 算，固定 |
| 範本用了會砍工具或砍對話的開關 | 沒有：預設 fsm 沒給 `--max-tool-calls`、`--history` 是 full |
| responses 路線害的 | 不是：chat 路線同樣會整段 0 |
| 太快、快取還沒寫好 | 不是：中與沒中的間隔一樣 |
| 剩下的 | 上游（ChatGPT 訂閱的 codex 後端）分流：LiteLLM 1.87.5 只把 `litellm_session_id` 當成 `session_id` 表頭送出去，codex 自己還會在 body 送 `prompt_cache_key`，但 LiteLLM 的 chatgpt responses 轉換只放行 model、input、instructions、stream、store、include、tools、tool_choice、reasoning、previous_response_id、truncation，`prompt_cache_key` 帶了也會被丟掉 |

## 不改行為就能省的：沒有可做的

上面每一項 aos 能控制的都已經穩定；剩下的沒中與 codex 指示都在 LiteLLM 或上游。所以這條線照任務書只寫選項、不動程式。

## 要你定的

| 選項 | 省多少 | 後果 |
|---|---|---|
| **A. 讓上游拿到快取鍵**：改 LiteLLM 代理（`~/repo/llm_proxy`，第三方套件 1.87.5 的 chatgpt 轉換），放行 `prompt_cache_key`（順便 `prompt_cache_retention`，上游回覆裡看得到 12 小時那一檔），aos 的 `session_key` 改成同時送這個鍵 | 如果它能把那 18% 的整段沒中壓掉，穩定期每輪沒中快取的 token 從平均約 1,230 降到約 210（−80% 上下）；12 小時那檔若也接得上，隔半小時以上的第一輪也能中 | **沒驗證過有效**（要先在暫存的 LiteLLM 上試）；要改第三方套件或等新版，屬於代理專案；aos 這邊 `session_key` 現在只能寫一個鍵，要送兩個得改 kernel 一小段 |
| B. 縮短 LiteLLM 自動加的 codex 指示（代理的環境變數 `CHATGPT_DEFAULT_INSTRUCTIONS`） | 每輪少約 1,600 token，第一輪 −26% | 沒驗過上游收不收別的指示；模型現在被告知自己是「Codex CLI 裡的 coding agent」，拿掉之後行為會變（可能變好也可能變差）；影響所有走這台代理的 chatgpt 呼叫 |
| C. 再縮預設工具（例：json 包 9 支改成要用再 `self_tools add`） | 每輪少約 1,039 token，第一輪 −17% | 跟你 11-21 定的預設包（只關 self 四支）不同；JSON 設定檔改用 read＋edit；要用時先 add，那一輪整段快取失效 |
| D. agent 自己加的工具排在最後，不照名字插中間 | 每加一支，那一輪少付插入點之後的工具（平均約 2,000 token），一次性 | 模型看到的工具順序變；`aos-tools ls` 或 brain.py 要改排法；加工具不常發生，效益小，**推薦不做** |
| E. 都不做 | 0 | 現況：每輪約 6,200 token，八成多的輪只付 100～200 token |

推薦先做 A 的「試」那一步（在暫存的 LiteLLM 上改白名單量 20 輪，看整段沒中有沒有消失），量到有效再決定要不要真的改代理；B、C 是方向題，照你的偏好。

**A 已試過（11-22，線 prompt-cache-key-1122，使用者答「做A」）：無效。** 上游本來就拿 `session_id` 表頭當快取鍵，body 送的鍵會被蓋掉；改前改後各 20 輪的沒中 token 一樣。見 [02-選項A實驗](02-選項A實驗.md)。

## 看到的事（照實列，沒修）

1. **sol 包的 `fixed: {"temperature": 0.2}` 沒送到上游**：LiteLLM 的 chatgpt 轉換只放行上面那十一個鍵，`temperature`、`max_output_tokens` 都被丟掉。知識庫與範本說 sol「固定 temperature 0.2」，實際上上游用它自己的預設。跟成本無關，交給管 llm kernel 範本的線。
2. **instructions 最後約 66 token 每輪都不中**：上游快取以 128 token 一格算，沒滿一格的不進快取；這是上游的規則，aos 不能改。
3. 範本裡 claude-haiku 的兩包（`smart-high`、`judge`）沒有快取斷點（Claude 要明寫 `cache_control` 才會快取），用到的話每輪都全價；活樹帳本 31 封全是 sol，目前沒人用。

## 收尾狀態

- 暫存：`~/.aos/scratch/prompt-cost-1122/`（`src` 乾淨複本、`trees/tf`、`trees/ts` 都已 shutdown、`rec/` 錄下的請求與回覆、`recsrv.py`、`analyze.py`、`tokens.py`）。兩支記錄代理已用自己記的 pid 收掉。
- repo 的程式、範本、工具說明、知識庫都沒動；`~/aos-home` 只讀。
- 開工前與收尾的 `pgrep -u "$USER" -af aos-daemon` 都是活樹那 5 台（2667、2671、157198、206339、256227），頂層 stack 的條目前後一樣。
