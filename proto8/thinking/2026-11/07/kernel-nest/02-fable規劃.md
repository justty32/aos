# fable 規劃：kernel 嵌套只靠一支轉交函數，每層自己排、自己記、自己說錯，靠「期限往下帶、子信名往上帶」把帳與時間串起來

← [README](README.md)

## 白話總結

嵌套這件事已經能跑了：隊伍有一台自己的問腦總機（隊 kernel），收到隊員的問題後不自己打 API，而是把問題轉寄給真正打 API 的總機（主 kernel）。這份規劃不加新的大零件，只補四個小洞，讓這條鏈在記帳、排程、時間、報錯四件事上都「每層只管自己，但接得起來」。

第一個洞是帳對不起來。現在每層總機都記自己的流水帳，但隊層那筆和主層那筆用的是不同的信名，事後只能靠「數字剛好一樣」去猜哪筆對哪筆。補法是：轉交函數回話時多帶一句「我寄出去的那封信叫什麼名字」，隊層總機把它記進自己流水帳的 `child` 欄，然後不往上傳。這跟 evolve-design 定的「叫人的那層記下『我叫了誰』」是同一個規矩。這樣從最上面的 agent 一路往下翻：agent 記著隊層信名，隊層那行記著主層信名，主層那行就是真的花錢的地方。兩層的 token 數字是同一筆錢的兩次觀測，有 `child` 的那行是鏡子，統計時只加沒有 `child` 的行。

第二個洞是急件變成普通件、而且下層不知道上層等多久。現在轉交出去的信沒有帶優先序和期限，上層總機 120 秒後把轉交函數殺掉時，下層那封信可能剛剛才開始打 API，錢照花、結果沒人收。補法是：總機把每封信交給端點函數時，順手把優先序和一個期限一起交出去，期限就是「這封信本來的期限」和「我自己會在幾秒後放棄」兩者取早的那個。轉交函數把這兩樣原樣塞進下一封信。下層總機看到期限已過就直接回「來不及，沒跑」，不會白花錢。每層的排隊、留格、老化升級還是各自算各自的，不互相認識。

第三個洞是時間少記了一截。流水帳只記「掛上去之後跑了多久」，信在信箱裡排隊等了多久沒記。補法是在每行多記一個「第一次看到這封信」的時刻，排隊時間就是掛上時刻減它。本機換模型要載入的那幾十秒，自然會落在換模型後第一封信的耗時裡，總機知道自己剛換過模型，就在那行標一個 `switched`，事後拿有標的行跟沒標的行一比就知道換一次模型多貴。時間照使用者的意思當成本記，但不拿來排序，排序規則不動。

第四個洞是本機 LM Studio 一次只能載一個模型，而現在總機不知道這件事：兩個本機模型的包各自限一封在飛，總機會讓它們同時跑。補法是在總機設定裡宣告「後端」：幾個包共用同一個後端，後端有自己的總在飛上限，還可以說「同時最多只能有一種包在飛」。這樣互斥就自動成立，隊員不用再被要求「並行時只能用同一個模型」。要不要進一步讓同一個模型的信優先湊在一起跑、少換幾次模型，是要請使用者裁的方向題，我推薦在同級信之間優先排「現在已經載著的那個模型」，高優先的信照樣能插隊換模型。

報錯這邊，現在是一層包一層：到了 agent 手上，錯誤字串變成四層套娃，真正的原因埋在最裡面。補法是讓「轉交」真的透明：下層總機回的錯誤是一個標準的錯誤物件，轉交函數原樣印出來、用同樣的退出碼結束，上層總機看到端點函數交回來的是一個標準錯誤物件就原樣回給寄件人。結果是 agent 看到的錯跟沒嵌套時一模一樣，而每層總機自己的流水帳各記一筆。轉交函數自己出的錯（例如設定裡沒寫要轉去哪）才用自己的名字報。這條跟「每層只說自己的錯」的條文有張力，條文自己也說同型特例再出現要問一次，所以列成方向題請使用者裁。

另外還有一條要請使用者看的衝突：試驗場為了讓轉交函數找得到主總機，在隊 kernel 的 daemon 裡把整棵樹共用的環境變數改指主總機，這跟「hub 變數整棵樹一致、只在 root 層設」兩條規矩相撞。我推薦改成在隊 kernel 的設定裡，每個包直接寫「轉去哪台 kernel」的路徑，環境變數就不用動了，而且同一台隊 kernel 可以把不同的包轉去不同的下層總機，正好就是使用者說的「可以嵌套的專精 kernel」。

## 設計

### 概念（四條）

1. **轉交型 kernel＝一台普通 llm kernel，端點函數換成轉交函數**。C-47 已承認「判斷後轉交給有權 kernel 的算 kernel」。它不加任何新角色：排程、留格、額度、流水帳全部照 llm kernel 現制；唯一不同是它的能力包不打 HTTP，而是寄一封信給另一台 kernel。深度不限，每層只看到「下一層的信箱」這個公開介面。
2. **一層只知一層**：上層只知道下層的信箱位置與回信形狀；下層只知道寄件人是誰（信封 `sender`，不驗）。串帳靠兩個「宣告」：上層把**期限**寫進交給端點函數的單子（往下帶），端點函數把**自己寄出去的子信名**寫進回話（往上帶一層，不再上傳）。
3. **鏡子行不加總**：每層 kernel 的 `ledger.jsonl` 是它對「自己端點函數」的他見（evolve-design 的兩本帳之一）。有 `child` 的行是下層那筆錢的鏡子；成本彙整時只加沒有 `child` 的行（葉子），或只看一層。
4. **後端是 kernel 自己的資源格**（C-09／C-10）：同一台實體後端（LM Studio）背後的多個包共用一個格數上限，並可宣告「同時只能有幾種包在飛」。只有實際打那台後端的 kernel 需要知道它；上層 kernel 不知道、也不該知道。

### 機制：一封信走過兩層

以 agent → 隊 kernel（`llm_team`，exec＝`llm_forward`）→ 主 kernel（`llm_kernel`，exec＝`llm_http`）為例。

1. agent 用 `aos-llm ask --full` 寄信到 `$AOS_LLM_KERNEL`（隊 kernel）。body `{"endpoint": "sol", "request": {...}, "priority": "high"}`。agent 的 `observed.jsonl` think 行記 `letter`＝這封信名（B3 已做）。
2. 隊 kernel 照現制排序、留格、額度判斷，掛成 `llm_<信名>` proc。**改一處**：寫給端點函數的 `request.json` 多一個 `priority`，內容正規化成 `{"val": <信宣告的級數>, "deadline": <min(信的 deadline, mounted_at + timeout_ms)>}`。沒宣告級數的信 `val` 寫 `"normal"`；aging 升上來的級數**不**寫進去（那是本層內部的事）。
3. 轉交函數 `llm_forward` 讀 stdin，從包裡拿 `to`（下層代號）與 `kernel`（下層 kernel 的 stack 路徑），組 body `{"endpoint": to, "request": 原樣, "priority": 原樣}`，以 `AOS_LLM_KERNEL=<kernel>` 跑 `aos-llm ask --full`。寄件人身份照 `aos-llm` 現制（`$AOS_WS` ＞ `$AOS_STACK` …）；隊 kernel daemon 的環境讓它落在隊 kernel 的 stack，所以下層看到的寄件人＝隊 kernel 一格。
4. 主 kernel 收到一封有 `priority.deadline` 的普通信：照現制排序（high 可用 `reserved`）；輪到時期限已過＝回 `DeadlineBad`、不跑、不花錢；跑了就照現制掛 `llm_http`、收成品、記自己的 ledger、回信。
5. `aos-llm ask --full` 在轉交函數這端印出回覆 body，**改一處**：多一個 `letter` 鍵＝它剛寄出的信名；失敗時 stdout 印錯誤 body `{"error": {"code", "msg"}}`（stderr 那一行與退出碼不變）。
6. 轉交函數成功時：把 `letter` 改名為 `child`，其餘原樣印出，退 0。下層回錯誤時：stdout 原樣印那個錯誤 body、用 `aos-llm` 的退出碼結束、**不加自己的前綴**（N-43「透明轉交別人的碼」）。轉交函數自己的錯（包沒 `kernel`、`aos-llm` 不在、被 kill）才印 `forward: error: <代號> <原因>` 退 1。
7. 隊 kernel 收成品，**改兩處**：（a）stdout 有 `child` 就記進 ledger 行、回信裡**拿掉**（上層 agent 不該知道兩層以下的信名）；（b）退非 0 且 `reply.json` 是合格的 `{"error": {"code", "msg"}}` ＝原樣當回信（透明轉交）；否則照舊 `EndpointFailed`＋第一行。每行另記 `code`（錯誤代號或 null）、`seen_at`（本層第一次在 `new/` 看到的時刻）。
8. agent 收到的成功回信與錯誤回信，**跟沒嵌套時形狀完全相同**。

逾時疊法（P-36 精神，aos 不替人算）：隊層 `timeout_ms` 從隊層掛上起算，包含下層排隊、下層執行、兩層各約 0.3～0.9 秒拍子開銷；設定時隊層 `timeout_ms` ≥ 主層 `timeout_ms` ＋ 主層預期排隊時間。隊層先殺人時：轉交函數死 → `aos-llm ask` 的 `sender.flock` 釋放 → 下層信若還在 `new/` 被收掉（現制，不花錢）；若已掛上則跑完、花錢、回信無人收——但有了往下帶的 deadline，下層大多在「輪到時」就拒掉，窄化這個窗口。隊層「半路死重掛一次」照現制（風險自擔，見方向題 5）。

判官不進這條鏈：llm kernel 的 `llm_*` proc 掛自己那台 daemon、不經判官（現行文件「起 llm daemon 的殼別設 `AOS_KERNEL`」照舊）。判官只管 agent 格，llm kernel 只管問腦格；N-42「兩隻不併」維持。

### 機制：本機後端互斥與批次

主 kernel 的 `kernel.json` 新增頂層 `backends`，包多一個 kernel 看的鍵 `backend`（四鍵變五鍵：`exec`／`slots`／`budget`／`speed`／`backend`；其餘仍原樣交給端點函數）。

- **後端格數**：所有 `backend` 相同的包，在飛總數 ≤ `backends.<名>.slots`（疊在包自己的 `slots` 與 kernel 頂層 `slots` 之上；三者皆滿才算滿）。
- **同時幾種包**：`backends.<名>.max_packs`（選填，沒寫＝不限）。在飛的包種數到頂時，其他包的信跳過看下一封（跟包 `slots` 滿的處理相同，不停整列）。LM Studio 寫 `{"slots": 1, "max_packs": 1}`；若 LM Studio 開了同模型並行，`slots` 可調大、`max_packs` 仍 1。
- **黏著（方向題 1 推薦案）**：排序在「deadline 近的先」之後、「包的 `speed`」之前插一條：同後端上，**跟 `queue.json.backends.<名>.pack` 相同的包先**。只在同級同期限時起作用，高級信照樣可以換模型。
- **狀態窗**：`queue.json` 多一個 `backends` 鍵（這是排程狀態，放排程窗）；每次實際換包時更新 `pack`、`switched_at`，`counter_switches` 加一。
- **換模型成本**：載入時間落在換包後第一封的 `elapsed_ms`；該行 ledger 標 `switched: true`。事後「有標行中位 − 無標行中位」＝一次換模型的成本。kernel 不另量、不另猜。
- 本機包經 LiteLLM（`:4000`）還是直打 `:1234` 都一樣：`backend` 是設定者**宣告**的，kernel 不從 url 推。
- 本機包放在主 kernel、還是另立一台 `llm_local` kernel 只放本機包，都只是設定，機制相同；本機包放哪台，那台就寫 `backends`。

### 資料格式（JSON 例）

隊 kernel `kernel.json`（範本 `kernel/llm-team/`）：

```json
{
  "slots": 4,
  "timeout_ms": 180000,
  "exec": "/abs/lib/aos/llm_forward",
  "endpoint": "luna",
  "endpoints": {
    "sol":   {"to": "gpt-sol-low",   "kernel": "/abs/llm_kernel", "speed": "normal", "summary": "forwarded to the main kernel"},
    "luna":  {"to": "gpt-luna-low",  "kernel": "/abs/llm_kernel", "speed": "fast",   "summary": "forwarded to the main kernel"},
    "local": {"to": "lm-gemma",      "kernel": "/abs/llm_local",  "speed": "slow",   "summary": "forwarded to the local kernel"}
  },
  "budget": {"max_calls": 3000, "max_tokens": 20000000, "window": "day",
             "senders": {"/abs/ws": {"max_calls": 3000}}}
}
```

主 kernel `kernel.json` 片段（後端）：

```json
{
  "backends": {"lmstudio": {"slots": 1, "max_packs": 1}},
  "endpoints": {
    "lm-gemma": {"url": "http://localhost:1234/v1", "model": "google/gemma-4-12b", "backend": "lmstudio", "slots": 1, "speed": "slow", "cost": "free", "context": 8192, "summary": "LM Studio gemma 4 12b; one local model at a time"},
    "lm-qwen":  {"url": "http://localhost:1234/v1", "model": "qwen3.5-9b",         "backend": "lmstudio", "slots": 1, "speed": "slow", "cost": "free", "context": 8192, "summary": "LM Studio qwen3.5 9b; one local model at a time"}
  }
}
```

kernel 交給端點函數的 `request.json`（stdin）：

```json
{"endpoint": {"to": "gpt-sol-low", "kernel": "/abs/llm_kernel", "summary": "..."},
 "request": {"model": null, "messages": [{"role": "user", "content": "..."}]},
 "priority": {"val": "high", "deadline": "2026-11-07T15:32:10.512+08:00"}}
```

（`deadline` 格式照 kernel 現在收信時認的那兩種：帶時區 ISO 8601 或 epoch 秒，取一種寫死。簡報 §2 寫展開形是 `{"level", "deadline"}`，C-48 寫 `{"val", "deadline"}`；施工時以程式與 C-48 為準，兩邊不一致就改文件。）

端點函數 stdout（成功）：

```json
{"message": {"role": "assistant", "content": "..."}, "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "model": "chatgpt-gpt-sol-low", "child": "01794035285110287381.1482882.2843709"}
```

端點函數 stdout（下層回錯、透明轉交；退出碼＝`aos-llm` 的）：

```json
{"error": {"code": "EndpointFailed", "msg": "llm_http: error: EndpointFailed HTTP 500: {\"error\":{\"message\":\"litellm.InternalServerError: ... Connection error.\"}}"}}
```

`aos-llm ask --full` 成功輸出（多 `letter`）：

```json
{"message": {...}, "usage": {...}, "model": "chatgpt-gpt-sol-low", "letter": "01794035285110287381.1482882.2843709"}
```

隊 kernel `ledger.jsonl` 一行（新欄 `seen_at`、`code`、`child`、`switched`；時間欄寫法沿用現制 epoch 秒，是否改日期字串跟 evolve-design 那條一起裁）：

```json
{"id": "01794035284500175665.1482852.2843648", "endpoint": "sol", "sender": "/abs/ws", "model": "chatgpt-gpt-sol-low", "seen_at": 1794035284.512, "mounted_at": 1794035284.787, "finished_at": 1794035300.761, "elapsed_ms": 15974, "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "code": null, "child": "01794035285110287381.1482882.2843709", "switched": false}
```

主 kernel 同一筆（葉子：`child` null；本機換模型後第一封的樣子）：

```json
{"id": "01794035285110287381.1482882.2843709", "endpoint": "lm-gemma", "sender": "/abs/llm_team", "model": "google/gemma-4-12b", "seen_at": 1794035285.106, "mounted_at": 1794035285.306, "finished_at": 1794035331.420, "elapsed_ms": 46114, "usage": {...}, "code": null, "child": null, "switched": true}
```

主 kernel `queue.json`（多 `backends`）：

```json
{"counter_runs": 42, "seen_at_ms": {"<信名>": 1794013299459}, "seen_at_ticks": {},
 "backends": {"lmstudio": {"pack": "lm-gemma", "switched_at": 1794035285.306, "counter_switches": 3}}}
```

`lib/aos/llm_forward/_metainfo.json`（自稱；只說自己的開銷，下層的錢在下層 ledger）：

```json
{"summary": "Forward one request to another llm kernel and return its reply unchanged",
 "timeout_ms": 180000,
 "resource": ["llm_kernel"],
 "side_effect": false, "idempotent": false, "deterministic": false,
 "cost": {"token": {"in": 0, "out": 0}, "counter_calls": 1, "time_ms": {"cal": "700"}},
 "cost_basis": {"statistic": "median", "counter_samples": 42, "case": "playground-ak round 2 (team minus main elapsed)"}}
```

kernel stack 的 `interfaces.json`：`{"aos-ledger": {"file": "ledger.jsonl"}}`，讓審視者照宣告找帳。

### 各層誰負責什麼

| 層 | 負責 | 不管 |
|---|---|---|
| agent（寄件人） | 寫 `priority`（級數、deadline）；記 think 行（`letter`、usage、自己量的牆鐘，含所有層排隊） | 下面有幾層、每層花多久 |
| 隊 kernel | 自己的排序／留格／額度／`timeout_ms`；給端點函數 `priority`（含推得的 deadline）；ledger 記 `seen_at`、`code`、`child`；回信拿掉 `child`；合格錯誤物件原樣回 | 下層是誰、下層的帳、原寄件人要不要傳下去（不傳） |
| 轉交函數 | 照包的 `to`／`kernel` 寄信；`priority` 原樣帶；回話加 `child`；下層的錯透明轉交、自己的錯用自己名字 | 排程、額度、重試、等多久 |
| 主 kernel | 同隊 kernel 的所有事；另加 `backends` 的格數、`max_packs`、黏著、`switched` | 寄件人後面是誰（一隊一格）、上層等多久（只看 deadline） |
| 端點小 proc（`llm_http`） | 打 API、回 `{"message","usage","model"}`、錯了 stderr 一行 | 任何排程、任何上層資訊 |
| daemon | 掛／收 proc、`timeout_ms` 殺人 | 優先權、排隊 |
| 審視者（evolve-design） | 沿 `letter → child` 翻帳；只加葉子行；用 `switched` 算換模型成本 | 本題不定它怎麼用 |

### 對 0a ①～⑤ 的直接回答

- ① 記帳：usage 已由 `--full` 帶上來（P1）；本題補 `child` 讓兩層行能對上，補「鏡子行不加總」規則，寄件人在下層仍是一隊一格。
- ② 排程疊法：每層各排各的（級數、aging、`reserved`、包 slots 全在本層）；跨層只帶 `priority`（宣告級數＋期限）；判官不在鏈上；`keep_ordered` 與問腦信無關（問腦信是普通信）。
- ③ 時間成本：每層 ledger 加 `seen_at`，排隊時間＝`mounted_at − seen_at`；agent 自量的牆鐘是全鏈總時間；時間只記不排（排序規則不動）。
- ④ 一次一個模型：`backends` 格數＋`max_packs: 1`；批次用黏著 tie-break（方向題 1）；換模型成本靠 `switched` 標記事後比。
- ⑤ 失敗與逾時：合格錯誤物件透明轉交，agent 看到的錯跟沒嵌套一樣；每層 ledger `code` 記自己那筆；逾時由每層 `timeout_ms` 各管各的，deadline 往下帶縮小「上層已放棄、下層還在花錢」的窗口；下層 kernel 死了＝信堆在 `new/`、上層等到 `timeout_ms` 回 `EndpointFailed`（「寄信不回＝呼叫失敗」，不加偵測）。

## 與既有條文的衝突

| # | 條文 | 衝突在哪 | 照新設計 | 照舊條文 | 推薦 |
|---|---|---|---|---|---|
| 1 | N-42 (1)：排序寫死「級數＋aging → 時限 → speed → 等得久 → 先寄」 | 黏著 tie-break 在時限之後、speed 之前插一條 | 同級同期限時少換模型；順序多一條要改文件與程式 | 本機信交替時每封都換模型，每次多幾十秒；時間成本照記，但白花 | 加這一條（方向題 1） |
| 2 | N-42 (1)／KD-02 端點函數契約：stdin `{endpoint, request}`、stdout `{message, usage, model}`、退非 0＝`EndpointFailed`＋第一行 | stdin 多 `priority`；stdout 多選填 `child`；退非 0 且 stdout 是合格錯誤物件＝原樣回 | 轉交不丟優先序與期限、帳能對上、錯不套娃；既有端點函數不受影響（C-48 多 key 忽略、少 key 照舊路徑） | 轉交信永遠是普通件、沒期限；帳靠行序猜；錯四層套娃 | 改契約，三處都是加法 |
| 3 | C-52 表 ③、N-43、P-21、C-53「每層只說自己」；C-52 續「同型特例再出現時問一次」 | 嵌套後每層 kernel 都要透原因給寄件人，是同型再現 | 用 N-43 已有的「透明轉交別人的碼」解釋：轉交函數與 kernel 對合格錯誤物件都是透明轉交，不是新例外；C-52 ③ 只剩「葉子端點函數 stderr 第一行」這一種 | 每層包一層，字串隨深度長，真原因在最裡層 | 透明轉交（方向題 4，條文要求問一次） |
| 4 | P-39「`AOS_LLM_KERNEL` 整棵樹一致」、N-67 ⑨「跨樹 hub 只在 root 層設」 | 試驗場隊 kernel daemon 把子項的 `AOS_LLM_KERNEL` 改指主 kernel | 包級 `kernel` 路徑取代 env 覆寫；env 整棵樹只有一個值；一台隊 kernel 可轉不同下層 | 要嵌套就必須在子樹改 hub，兩條規矩只能選一條破 | 包級 `kernel`，必填、不給預設（預設會指回自己成迴圈） |
| 5 | 代定 12（隊長代定）：「並行的本機級 agent 必須同一個模型」 | `backends` 讓 kernel 自己互斥，agent 側限制失去必要 | agent 自由選本機包，kernel 排成序 | agent 側人工協調、仍防不了兩個包同時在飛 | 退掉代定 12 的 agent 側那句 |
| 6 | AK/02 隊長代定「下游 `senders` 只見隊一格不改」 | 是隊長代定，未經使用者 | 下層不知隊內誰用多少，隊內帳在隊 kernel | 若改成帶原寄件人，下層知道上層內部（違 C-52） | 維持一隊一格（方向題 3） |
| 7 | C-56「不為邊緣狀況加機制」 | `backends` 是新機制 | — | — | 不算邊緣：一次一模型是使用者硬規矩，且是 C-09 意義下的真實資源格；`max_packs` 之外不加別的 |
| 8 | `_metainfo` 待定「實測不回寫」 | 時間成本要進帳 | 無衝突：時間只寫 ledger（他見），不回寫 `_metainfo`；排序不看 | — | 照設計，不碰待定 |
| 9 | KD-02 回信「原樣」 | kernel 要從回信拿掉 `child` | 上層只知一層 | 兩層以下的信名漏到 agent，誰都能拿去偷看 | 拿掉（一行程式） |
| 10 | C-48 `{"val", "deadline"}` vs 簡報 §2 `{"level", "deadline"}` | 文件互相不合 | — | — | 施工時查程式，文件改成跟程式與 C-48 一致 |

## 方向題

1. **本機後端要不要按模型批次排？**
   - A 只互斥不批次：規則最少；本機信交替時每封換一次模型，每次幾十秒照記進時間成本。
   - B 互斥＋黏著 tie-break（同級同期限時先排已載著的包）：多一條排序規則；高級信照樣能換模型，低級信自然湊批。
   - C 一個模型一台 kernel、換模型＝改設定重起：零新規則；跑的中途無法試另一個本機模型，階梯試驗要人介入。
   - **推薦 B**。
2. **上層會等多久要不要告訴下層？**
   - A 不告訴（現制）：靠 kill 與 `sender.flock`；下層已掛上的信照跑照花錢。
   - B kernel 把 `deadline＝min(信的 deadline, mounted_at＋timeout_ms)` 寫進給端點函數的 `priority`，轉交函數原樣帶下去：下層輪到時已過期就 `DeadlineBad` 不跑；多的只是一個已存在的欄位。
   - **推薦 B**。副作用：agent 可能收到自己沒設過期限的 `DeadlineBad`（訊息誠實：是轉交信的期限），比等到 `EndpointFailed` 逾時便宜。
3. **下層看到的寄件人是隊一格，還是帶原 agent？**
   - A 一隊一格：下層只知道「這隊」；隊內分攤看隊 kernel 自己的 ledger。
   - B 轉交函數把原寄件人塞進下層信：下層可按 agent 設額度，但下層認得上層內部、`sender` 從「不驗」變「可冒」。
   - **推薦 A**（C-52；也是試驗場既有代定）。
4. **嵌套錯誤怎麼報？**
   - A 每層包一層（現制）：忠於「每層只說自己」字面；字串隨深度成長，真原因在最裡層，程式與腦都難讀。
   - B 透明轉交：合格的 `{"error": {"code", "msg"}}` 原樣過關，轉交函數不加前綴；agent 看到的跟沒嵌套相同；每層 ledger `code` 仍各記自己。
   - **推薦 B**，依 N-43 唯一例外「透明轉交別人的碼」解釋，不另開 C-52 例外。
5. **轉交函數半路死被重掛一次，可能寄兩封下層信、花兩次錢。**
   - A 照通則（重掛一次，風險自擔，與「睡醒或 kill -9 可能多花一次腦」同一態度）。
   - B 轉交包不重掛（包多一個鍵）：少花錢，多一個鍵、多一條規則。
   - **推薦 A**；有了方向題 2 的 deadline，第一封多半在下層輪到時就被拒，重複花錢的窗口已小。

## 落地小步（交 gpt 照圖施工）

1. llm kernel：寫 `request.json` 時加 `priority`（`{"val", "deadline"}`，deadline 取信的 deadline 與 `mounted_at＋timeout_ms` 較早者；沒級數寫 `"normal"`）。完成條件：任一端點函數的 stdin 都看得到 `priority`，既有 `llm_http` 不受影響、測試全綠。
2. llm kernel：收成品時，stdout 有 `child`（字串）就記進 ledger、回信中移除；ledger 行加 `seen_at`（本層首次看到的時刻）、`code`（錯誤代號或 null）、`child`（或 null）、`switched`（布林，先一律 false）。完成條件：ledger 每行都有這四個鍵，KD-02 逐封帳欄位表更新。
3. llm kernel：端點函數退非 0 且 `reply.json` 解得出 `{"error": {"code": 字串, "msg": 字串}}` ＝原樣當回信；否則照舊 `EndpointFailed`＋第一行。完成條件：兩種 fake 端點（一種印合格錯誤物件、一種只印一行）各得到預期回信。
4. aos-llm：`ask --full` 成功輸出加頂層 `letter`＝寄出的信名；失敗時 stdout 印錯誤 body、stderr 行與退出碼不變。完成條件：`aos-llm ask --full` 對 fake 包的成功與失敗各一次，stdout 皆為一行合法 JSON。
5. 新函數 `lib/aos/llm_forward/`（搬自試驗場 `defs/llm_forward`）：包必填 `to`、`kernel`（絕對路徑）；`AOS_LLM_KERNEL=<kernel>` 跑 `aos-llm ask --full`；`priority` 原樣帶；成功把 `letter` 改名 `child` 印出；下層錯誤原樣印、同退出碼、不加前綴；包缺 `kernel` 印 `forward: error: CfgBad endpoint pack has no "kernel"` 退 1。附 `_tooldef.json`、`_metainfo.json`、README。完成條件：fake 下層兩層串起來，agent 端成功與錯誤回信跟直連主 kernel 時逐字相同。
6. llm kernel：`kernel.json` 認頂層 `backends.<名>.{slots, max_packs}` 與包的 `backend`；排程時同後端在飛 ≤ `slots`、在飛包種數 ≤ `max_packs`；`queue.json` 加 `backends.<名>.{pack, switched_at, counter_switches}`；換包後第一封 ledger `switched: true`。完成條件：兩個 `backend: "lmstudio"` 包各寄 3 封、`max_packs: 1`，daemon 表上任一時刻只有一種包在飛。
7. llm kernel：排序在 deadline 之後、speed 之前加「同後端與 `queue.json.backends.<名>.pack` 相同的包先」（方向題 1 裁 B 才做）。完成條件：同級 6 封交替兩包的信，實跑只換模型一次。
8. 範本：`kernel/llm-team/kernel.json`（本文例）、主 kernel 範本本機包改掛 `backends`；`endpoints.json` 窗多列 `backend`；kernel stack 寫 `interfaces.json` `{"aos-ledger": {"file": "ledger.jsonl"}}`。完成條件：照範本起兩台 kernel 不改任何 env 就能嵌套跑通。
9. 文件：N-42 (1) 排序與端點函數契約（五鍵、`priority`、`child`、合格錯誤物件透明）；C-52 續表 ③ 加註「透明轉交不是例外」；N-67／P-39 加註「轉去哪台 kernel 寫在包裡，不改 hub」；代定 12 退掉 agent 側那句；AK/02「一隊一格」改成使用者裁定（方向題 3）。完成條件：wf-lint 綠、`grep LM Studio` 在 impls docs 有命中。
10. 試驗場：`defs/llm_team` 改用 `lib/aos/llm_forward` 與包級 `kernel`，拿掉 `_entry` 裡的 `AOS_LLM_KERNEL` 覆寫；重跑一個地點，對帳腳本改沿 `letter → child` 配對。完成條件：42 筆級別的樣本 100% 由 `child` 配對（不靠行序），且兩層 usage 不相加。

交給別題的：agent `observed.jsonl` 的 `self` 行要不要記 `llm_kernel` 路徑（讓審視者從 agent 帳找到隊 kernel 帳）交給 evolve-design；本機模型階梯（gemma／qwen 大小）試驗交給 arknights-kb；成本 JSON 通用格式歸 evolve-design，本題只用它的 `cost` 形狀寫 `_metainfo`。
