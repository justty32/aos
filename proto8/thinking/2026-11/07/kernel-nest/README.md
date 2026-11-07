# llm kernel 嵌套的設計：只靠一支轉交函數，每層自己排、自己記、自己說錯，靠「期限往下帶、子帳位置往上帶一層」串起帳與時間
← [2026-11-07](../README.md)｜簡報 [01-簡報](01-簡報.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

## 白話總結

嵌套這件事其實已經能跑。試驗場裡，一個隊伍有自己的問腦總機（下面叫「隊 kernel」），隊員問問題時，隊 kernel 不自己打 API，而是把問題轉寄給真正打 API 的總機（「主 kernel」）。這份設計不加新的大零件，只補五個小洞，讓這條轉寄鏈在記帳、排程、時間、本機模型、報錯五件事上「每層只管自己，但接得起來」。

第一個洞是帳對不起來。兩層總機都各記一本流水帳，可是同一個問題在兩層用的是不同的信名，事後只能靠「數字剛好一樣」去猜哪筆對哪筆。補法是讓轉交函數回話時多說一句「我寄去哪台總機、那封信叫什麼」，隊 kernel 把這句記在自己那行帳上，不再往上傳。這樣從 agent 開始往下翻，就像翻族譜：agent 記著隊層信名，隊層那行記著主層在哪、信名是什麼，主層那行就是真正花錢的地方。兩層記的 token 是同一筆錢被看了兩次，所以加總時只能挑一層加，不能兩層相加。

第二個洞是急件到了下層變成普通件，下層也不知道上層只肯等多久。現在隊 kernel 在 120 秒後放棄時，主 kernel 那封可能才剛開始打 API，錢照花、結果沒人收。補法是總機把信交給轉交函數時，順手附上這封信的急迫程度和一個期限，期限取「信原本的期限」和「我自己會在什麼時候放棄」兩者中較早的那個。下層輪到它時如果已經過期，就直接回「來不及，沒跑」，不白花錢。每層的排隊、留位、等久升級還是各算各的，彼此不認識。

第三個洞是時間少記一截。流水帳只記「開始跑之後花了多久」，信在信箱裡排隊等了多久沒有記。補法是每行多記「第一次看到這封信」的時間，排隊多久就能算出來。換本機模型要載入的那幾十秒，會落在換模型之後第一封的耗時裡；總機知道自己剛換過，就在那行做個記號，事後把有記號和沒記號的比一比，就知道換一次模型要多花多少時間。時間照你說的當成本記下來，但這一版先不拿來排序。

第四個洞是本機 LM Studio 一次只能載一個模型，總機卻不知道這件事。現在兩個本機模型是兩個各自限一封的包，總機會讓它們同時跑。補法是在總機設定裡寫明「這幾個包背後是同一台機器，同時只能有一種在跑」，總機自己就會讓它們輪流，不用再要求隊員「並行時只能用同一個模型」。要不要讓同一個模型的信盡量湊在一起跑、少換幾次，推薦「只在急迫程度一樣時，先跑現在已經載著的那個」，急件照樣可以插隊換模型。這條要成立有個前提：所有本機模型的包都要放在同一台總機裡，兩台總機之間互相看不到。

第五個洞是報錯一層包一層。到了 agent 手上，錯誤訊息變成四層套娃，真正的原因（例如 LM Studio 沒開）埋在最裡面。補法是讓轉交真的「透明」：下層回的標準錯誤原封不動往上傳，agent 看到的跟沒嵌套時一模一樣；只有轉交函數自己出的錯，才用它自己的名字報。這條跟「每層只說自己的錯」那條原則有張力，條文也說同類例外再出現時要問一次，所以列成方向題。

另外有一個設定上的衝突要你知道：試驗場為了讓轉交函數找得到主總機，在隊 kernel 那台把「問腦總機在哪」這個全樹共用的環境變數改成指向主總機，跟「這種變數整棵樹一致、只在最上層設」兩條規矩相撞。推薦改成在隊 kernel 每個包的設定裡直接寫「轉去哪台總機」，環境變數就不用動；而且同一台隊 kernel 可以把不同的包轉給不同的下層總機，正好就是你說的「專精的 kernel」。

晚審點出的兩件事也跟這題有關。一件是逐封流水帳（ledger）本身就是把你 11-05 選了「也刪」的東西加了回來，沒有問你。這份設計的記帳、時間、換模型成本全部住在這本帳上，所以它的去留列成第一道方向題，推薦「留著，明說是翻案」。另一件是判官重起時可能答錯，那個問題不影響問腦這條鏈，因為問腦的工作從來不經過判官，這份設計把這點寫成規矩。

你出門前說不要問，下面的方向題當時一律標「未裁，暫照推薦」，11-07 已全部裁定（1、7 在 16:25，2～6 在傍晚，見文末「使用者裁定」），我替你做的小決定集中在「代定」一節，都可以翻案。

## 設計

### 概念（四條）

1. **轉交型 kernel＝一台普通 llm kernel，只是端點函數換成轉交函數**。C-47（11-05 加嚴）已承認「判斷後轉交給有權的 kernel 的算 kernel」。它不是新角色：排程、留格、額度、流水帳全照 llm kernel 現制，唯一差別是它的包不打 HTTP，而是寄一封信給另一台 kernel。深度不限，每層只看得到「下一層的信箱」這個公開介面（N-42 (1)「對外只有信箱＋aos-llm」）。
2. **一層只知一層**：上層只知道下層的信箱位置與回信形狀；下層只知道寄件人是誰（信封 `sender`，不驗，10-15「先信任」）。串帳只靠兩個宣告：上層把**期限與宣告級數**寫進交給端點函數的單子（往下帶）；端點函數把**自己寄出的子信在哪台、叫什麼**寫進回話（往上帶一層，到此為止）。這是 evolve-design 概念三「每一行『我叫了誰』都寫明對方的帳現在放在哪」在 kernel 這層的落法。
3. **每層的帳是那層的他見；同一筆錢在每層都會出現一次，加總時只加一層**。有 `child` 的行是下層那筆錢的鏡子。全鏈的 token 總數＝只加「沒有 `child` 的行」（葉子，就是真正打 API 的那台）；某一層的花費＝只看那一層。agent 的 `observed.jsonl` think 行也是鏡子（它看的是隊 kernel 回的 usage）。
4. **後端是 kernel 自己的資源格**（C-09／C-10「有限的就是資源，用格數表示」）：同一台實體後端（LM Studio）背後的幾個包共用格數，並可宣告「同時最多幾種包在飛」。只有直接管那台後端的 kernel 知道它；上層不知道、也不該知道。**互斥只在一台 kernel 之內成立**，所以所有指向同一台 LM Studio 的包必須放在同一台 kernel（部署規則，見代定 7）。

### 拓撲

```
agent ──AOS_LLM_KERNEL──▶ 隊 kernel（exec＝llm_forward；每包寫 to＋kernel）
                              │ 包 sol/luna  ──▶ 主 kernel（exec＝llm_http；雲端包＋所有 LM Studio 包，寫 backends）
                              │ 包 local     ──▶ 同一台主 kernel 的 lm-* 包
                              └ 包 special   ──▶ 另一台專精 kernel（也可以再轉交）
```

- 每台 kernel 照舊是一台 daemon 的身體（`daemon.json` 的 `exec`），問腦 proc 掛在**它自己那台 daemon**，不經判官（代定 8）。
- `AOS_LLM_KERNEL` 整棵樹只有一個值（agent 那邊指隊 kernel）；往下一層去哪裡，寫在包的 `kernel` 鍵裡，由轉交函數讀。
- 起法照 C-78 四步不變；多一層＝多一台 daemon，由根 daemon 監督（試驗場已是這樣）。

### 一封信走過兩層

以 agent → 隊 kernel（`llm_team`）→ 主 kernel（`llm_kernel`）為例。帶「改」的是相對現制要動的地方。

1. agent 用 `aos-llm send`（agent-fsm 的 wait 格）或 `ask --full` 寄到隊 kernel：body `{"endpoint": "sol", "request": {...}, "priority": {"level": "high"}}`。agent 的 `observed.jsonl` think 行記 `letter`＝這封信名（B3 已做）；`self` 行記 `llm_kernel`＝起動時的 `$AOS_LLM_KERNEL`（**改**，代定 2），讓審視者從 agent 的帳找得到隊 kernel 的帳。
2. 隊 kernel 照現制排序、留格、額度判斷，掛成 `llm_<信名>` proc。**改**：
   - `request.json` 多一個頂層 `priority`＝`{"level": <信宣告的級數，沒寫＝"normal">, "deadline": <min(信的 deadline, 本層 mounted_at＋timeout_ms)>}`；沒有 `timeout_ms` 也沒有信的 deadline 就不寫 `deadline`。aging 升上來的級數**不**寫（那是本層內部的事）。key 名照程式現在認的 `level`（見方向題 7）。
   - `proc.json` 多記 `seen_at`（本層第一次在 `new/` 看到這封的時刻，從 `queue.json` 的 `seen_at_ms` 帶過來；掛上後 `queue.json` 就刪那格，所以要在掛上時抄）。
3. 轉交函數 `llm_forward` 讀 stdin，從包裡拿 `to`（下層代號）與 `kernel`（下層 kernel 的 stack 絕對路徑），組 `{"endpoint": to, "request": 原樣, "priority": 原樣}`，以 `AOS_LLM_KERNEL=<kernel>` 只給自己的子行程跑 `aos-llm ask --full`。下層看到的寄件人照 aos-llm 現制決定，在隊 kernel daemon 的環境下就是隊 kernel 一格。
4. 主 kernel 收到一封帶 `priority.deadline` 的普通信，照現制排序（high 可用 `reserved`）；輪到時期限已過＝回 `DeadlineBad`、不跑、不花錢；否則掛 `llm_http`、收成品、記自己的 ledger、回信。若是 LM Studio 的包，再過 `backends` 的格數與種數關（見下節）。
5. **改** `aos-llm ask --full`／`recv --full`：成功時輸出多一個頂層 `letter`＝那封信名；失敗時 stdout 印錯誤 body `{"error": {"code", "msg"}}` 一行，stderr 那一行與退出碼不變。
6. 轉交函數成功時：把 `letter` 換成 `child: {"kernel": <下層 stack>, "letter": <信名>}`（**代定 1**：寫明下一本帳在哪，不只信名），其餘原樣印出、退 0。下層回錯誤時：stdout 原樣印那個錯誤 body、照 aos-llm 的退出碼結束、**不加自己的錯誤行**（N-43「透明轉交別人的碼」：沒有 `我的名字: error:` 那行＝下層的碼）。轉交函數自己的錯（包沒 `kernel`、aos-llm 不在、stdout 讀不懂）才印 `llm_forward: error: <代號> <原因>` 退 1。
7. 隊 kernel 收成品，**改**：（a）stdout 有 `child` 就記進 ledger 那行，回信裡**拿掉**（agent 不該知道兩層以下的信名）；（b）退非 0 而 `reply.json` 整份是合格的 `{"error": {"code": 字串, "msg": 字串}}`＝原樣當回信，否則照舊 `EndpointFailed`＋第一行；（c）ledger 每行多 `seen_at`、`code`、`child`、`switched`。
8. agent 收到的成功回信與錯誤回信，形狀跟沒嵌套時完全相同。

### 本機後端：互斥與批次

主 kernel 的 `kernel.json` 加頂層 `backends`；包多一個 kernel 看的鍵 `backend`（四鍵變五鍵：`exec`／`slots`／`budget`／`speed`／`backend`，其餘照舊原樣交給端點函數）。

- **後端格數**：`backend` 相同的包，在飛總數 ≤ `backends.<名>.slots`；疊在包自己的 `slots` 與頂層 `slots` 之上，三關都過才掛。
- **同時幾種包**：`backends.<名>.max_packs`（選填，沒寫＝不限）。在飛的包種數到頂時，別種包的信跳過、看下一封（跟包 `slots` 滿一樣，不停整列）。LM Studio 寫 `{"slots": 1, "max_packs": 1}`。
- **黏著**（方向題 2 推薦案）：排序在「deadline 近的先」之後、「包的 speed」之前插一條：同後端上，跟 `queue.json.backends.<名>.pack`（目前載著的包）相同的先。只在同級同期限時起作用。
- **狀態**：`queue.json` 多 `backends: {名: {"pack", "switched_at", "counter_switches"}}`；每次實際換包時更新，換包後第一封的 ledger 行 `switched: true`。
- **換模型成本**：不另量、不另猜；事後「`switched: true` 行的中位耗時－同包其他行的中位耗時」＝換一次的代價。
- `backend` 是設定者**宣告**的（C-56 寫什麼就做什麼），kernel 不從 url 推；本機包經 LiteLLM `:4000` 還是直打 `:1234` 都一樣。
- **已知限制**（寫進 kernel 文件，不加機制）：kernel 只知道「自己最後掛的是哪包」，不知道 LM Studio 實際載著什麼——人手在 LM Studio 換模型、或 kernel 重起後第一封，`switched` 可能記錯；兩台 kernel 都放了本機包＝互斥失效（部署規則違反，自擔）。

### 時間怎麼拆

每層 ledger 有 `seen_at`、`mounted_at`、`finished_at`、`elapsed_ms`，所以：

| 要看的 | 怎麼算 | 誰的帳 |
|---|---|---|
| 這層排隊多久 | `mounted_at − seen_at` | 本層 |
| 這層跑一封多久（含等 daemon 套用、含下層全部） | `elapsed_ms` | 本層 |
| 轉交這一跳的開銷 | 上層 `elapsed_ms` －（下層排隊＋下層 `elapsed_ms`） | 兩層對帳（沿 `child`） |
| 全鏈總時間 | agent think 行的 `elapsed_ms`（agent 自己量的牆鐘） | agent |
| 換模型代價 | `switched` 行與一般行的差 | 管後端那層 |

時間只記、不排（排序規則除了黏著那條不動）；不回寫 `_metainfo`（待定稿「實測不回寫」照舊）。估時寫在 `_metainfo.json` 的 `cost.time_ms`、逾時寫 `timeout_ms`，照 evolve-design 已裁的拆法。

### 逾時與失敗

- **逾時層層包**（P-36 精神，aos 不替人算）：每層 `timeout_ms` 從自己掛上起算，包含下層排隊與執行。設定時上層 `timeout_ms` ≥ 下層 `timeout_ms`＋下層預期排隊時間；範本隊 kernel 寫 180000、主 kernel 120000。
- **上層先放棄時**：轉交 proc 被 daemon 整群收 → 子行程 `aos-llm ask` 一起死、`sender.flock` 釋放 → 下層信若還在 `new/` 被收拾掉（現制、不花錢）；若已掛上就跑完、花錢、回信被撤。有了往下帶的期限，下層多半在「輪到時」就拒掉，這個窗口變窄。
- **下層 kernel 死了或睡了**：信堆在下層 `new/`，上層等到 `timeout_ms` 回 `EndpointFailed`（「寄信不回＝呼叫失敗」，不加偵測、不加健康檢查；父 daemon 只看它活不活著）。
- **轉交 proc 半路死**：照現制重掛一次（方向題 6）。
- **ledger 的 `code`**：每層記「自己回給寄件人的代號」，成功＝null。透明轉交時隊層的 `code` 就是下層的代號，看 `child` 知道是誰說的。

### 資料格式

隊 kernel `kernel.json`（範本 `kernel/llm-team/`；路徑在範本裡用 `$ref`／絕對路徑，照 kernel 文件現行做法）：

```json
{"slots": 4, "timeout_ms": 180000,
 "exec": "/abs/proto8/lib/aos/llm_forward", "endpoint": "luna",
 "endpoints": {
   "sol":   {"to": "gpt-sol-low",  "kernel": "/abs/llm_kernel", "speed": "normal", "summary": "forwarded to the main kernel"},
   "luna":  {"to": "gpt-luna-low", "kernel": "/abs/llm_kernel", "speed": "fast",   "summary": "forwarded to the main kernel"},
   "local": {"to": "lm-gemma",     "kernel": "/abs/llm_kernel", "speed": "slow",   "summary": "forwarded to the local model on the main kernel"}},
 "budget": {"max_calls": 3000, "window": "day", "senders": {"/abs/ws": {"max_calls": 3000}}}}
```

主 kernel 片段：

```json
{"backends": {"lmstudio": {"slots": 1, "max_packs": 1}},
 "endpoints": {
   "lm-gemma": {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "lm-gemma-4-12b-nothink", "backend": "lmstudio", "slots": 1, "speed": "slow", "cost": "free", "summary": "LM Studio gemma 4 12b; one local model at a time"},
   "lm-qwen":  {"exec": "endpoints/litellm", "url": "http://localhost:4000/v1", "model": "lm-qwen3.5-9b-nothink",  "backend": "lmstudio", "slots": 1, "speed": "slow", "cost": "free", "summary": "LM Studio qwen3.5 9b; one local model at a time"}}}
```

kernel 給端點函數的 `request.json`：

```json
{"endpoint": {"to": "gpt-sol-low", "kernel": "/abs/llm_kernel", "summary": "..."},
 "request": {"messages": [{"role": "user", "content": "..."}]},
 "priority": {"level": "high", "deadline": 1794035404.787}}
```

（`deadline` 用 epoch 秒，是 kernel 收信時已認的兩種寫法之一；寫死這一種。）

轉交函數成功時的 stdout：

```json
{"message": {"role": "assistant", "content": "..."}, "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "model": "chatgpt-gpt-sol-low",
 "child": {"kernel": "/abs/llm_kernel", "letter": "01794035285110287381.1482882.2843709"}}
```

透明轉交下層錯誤（退出碼＝aos-llm 的，stderr 沒有 `llm_forward: error:` 行）：

```json
{"error": {"code": "EndpointFailed", "msg": "endpoint function exited with code 1: llm_http: error: EndpointFailed HTTP 500: ... Connection error."}}
```

隊 kernel 的 ledger 一行（新欄 `seen_at`、`code`、`child`、`switched`；時間格式沿用 ledger 現制 epoch 秒，見代定 3）：

```json
{"id": "01794035284500175665.1482852.2843648", "endpoint": "sol", "sender": "/abs/ws", "model": "chatgpt-gpt-sol-low",
 "seen_at": 1794035284.512, "mounted_at": 1794035284.787, "finished_at": 1794035300.761, "elapsed_ms": 15974,
 "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "code": null,
 "child": {"kernel": "/abs/llm_kernel", "letter": "01794035285110287381.1482882.2843709"}, "switched": false}
```

主 kernel 同一筆換成本機模型後第一封的樣子（葉子：`child` null）：

```json
{"id": "01794035285110287381.1482882.2843709", "endpoint": "lm-gemma", "sender": "/abs/llm_team", "model": "lm-gemma-4-12b-nothink",
 "seen_at": 1794035285.106, "mounted_at": 1794035285.306, "finished_at": 1794035331.420, "elapsed_ms": 46114,
 "usage": {"total_tokens": 8134}, "code": null, "child": null, "switched": true}
```

主 kernel `queue.json`：

```json
{"counter_runs": 42, "seen_at_ms": {"<信名>": 1794013299459},
 "backends": {"lmstudio": {"pack": "lm-gemma", "switched_at": 1794035285.306, "counter_switches": 3}}}
```

kernel **定義夾**頂層 `interfaces.json` 宣告帳（路徑相對 stack，跟 evolve-design 的 `aos-observed` 同一種寫法，代定 4）：

```json
{"aos-ledger": {"file": "ledger.jsonl"}}
```

`lib/aos/llm_forward/_metainfo.json`（自稱只說自己的開銷；下層的錢在下層帳；照 evolve-design 已裁的 `cost`／`timeout_ms` 拆法，代定 5）：

```json
{"summary": "Forward one request to another llm kernel and return its reply unchanged",
 "timeout_ms": 180000, "resource": ["llm"],
 "side_effect": false, "idempotent": false, "deterministic": false,
 "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "counter_calls": 1, "time_ms": 700}}
```

### 各層誰負責什麼

| 層 | 負責 | 不管 |
|---|---|---|
| agent（寄件人） | 寫 `priority`；think 行記 `letter`、usage、自己量的牆鐘；`self` 行記 `llm_kernel` | 下面幾層、每層多久 |
| 隊 kernel | 本層排序／留格／額度／`timeout_ms`；給端點函數 `priority`（含推得的期限）；ledger 記 `seen_at`、`code`、`child`；回信拿掉 `child`；合格錯誤物件原樣回 | 下層是誰、下層的帳、原寄件人要不要往下傳（不傳） |
| 轉交函數 | 照包的 `to`／`kernel` 寄；`priority` 原樣帶；成功回 `child`；下層的錯透明轉交，自己的錯用自己名字 | 排程、額度、重試、等多久 |
| 主 kernel | 同隊 kernel 的事；另加 `backends` 格數、`max_packs`、黏著、`switched` | 寄件人後面是誰（一隊一格）、上層等多久（只看期限） |
| 端點小 proc（`llm_http`） | 打 API、回 `{"message","usage","model"}`、錯了 stderr 一行 | 任何排程與上層資訊 |
| daemon | 掛／收 proc、`timeout_ms` 殺整群 | 優先權、排隊 |
| 判官 | 只管 agent 那類 proc 的掛不掛；**不在問腦鏈上** | 問腦 |
| 審視者（evolve-design） | 沿 `letter → child` 翻帳；只加葉子行；用 `switched` 算換模型成本 | 本題不定它怎麼用 |

### 這一版不做的

搶位（殺在飛的 low 讓 high 進）、包到頂自動降級、拿實測時間排序、kernel 公告「現在要排多久」（NORMS 待定「kernel 公告」照舊待定）、跨 kernel 的後端鎖、下游按原 agent 記額度。

## 與既有條文的衝突

條文我回頭對過原文（N-42 (1)、C-47、C-52 續表、N-43、P-36、P-39、N-67 ⑨、C-48、程式 `letter.cpp`、`aos-llm` 的 `send.cpp`／`wait`、晚審報告）；fable 的引用除第 10 條方向弄反之外都對。第 11～14 條是補上的。

| # | 條文 | 衝突在哪 | 照新設計 | 照舊條文 |
|---|---|---|---|---|
| 1 | N-42 (1)：排序寫死「級數＋aging → 時限 → speed → 等得久 → 先寄」 | 黏著在時限與 speed 之間插一條 | 同級同期限時少換模型 | 本機信交替時每封都換，每次多幾十秒 |
| 2 | N-42 (1)／kernel docs 02：端點函數 stdin `{endpoint, request}`、stdout `{message, usage, model}`、退非 0＝`EndpointFailed`＋第一行 | stdin 多 `priority`；stdout 多選填 `child`；退非 0 而 stdout 是合格錯誤物件＝原樣回 | 轉交不丟急迫程度與期限、帳對得上、錯不套娃；既有端點函數不受影響（C-48 多的 key 忽略） | 轉交信永遠是普通件、沒期限；帳靠行序猜；錯四層套娃 |
| 3 | C-52 表 ③、N-43、P-21、C-53「每層只說自己」；C-52 續升格門檻 2「同型特例再出現時問一次」 | 每層 kernel 都要把原因透給寄件人，是同型再現 | 以 N-43 既有的「透明轉交別人的碼」解釋，不開新例外；表 ③ 只剩葉子端點函數那一種 | 每層包一層，字串隨深度變長 |
| 4 | P-39「`AOS_LLM_KERNEL` 整棵樹一致」、N-67 ⑨「跨樹 hub 只在 root 層設」 | 試驗場在隊 kernel 那台把子項的 hub 改指主 kernel；evolve-design 落地第 6 步也照這樣寫 | 包寫 `kernel`，hub 整棵樹一個值；剩一點：轉交函數只對自己那一個子行程設 `AOS_LLM_KERNEL`（aos-llm 只認環境變數） | 要嵌套就得在子樹改 hub，兩條規矩只能破一條 |
| 5 | arknights-kb 代定 12「並行的本機級 agent 必須同一個模型」 | `backends` 讓 kernel 自己互斥，agent 那邊的限制不必要了 | agent 自由選本機包，kernel 排成序 | 靠人協調，仍防不了兩包同時在飛 |
| 6 | arknights-kb 02 隊長代定「下游 senders 只見隊一格不改」 | 隊長代定，不是使用者裁的 | 維持一隊一格，隊內帳在隊 kernel | 若改成帶原寄件人，下層就認得上層內部（違 C-52） |
| 7 | C-56「不為邊緣狀況加機制」 | `backends` 是新機制 | 一次一模型是使用者硬規矩、C-09 意義下的真資源格，不算邊緣；`max_packs` 之外不加別的 | 只靠部署（一台一包） |
| 8 | kernel docs 02「回信＝reply.json 原樣」 | 要從回信拿掉 `child` | 上層只知一層 | 兩層以下的信名漏到 agent |
| 9 | `_metainfo` 待定「實測不回寫」 | 時間要進成本 | 無衝突：時間只寫 ledger（他見），排序不看 | — |
| 10 | **C-48／C-55「展開形的原值固定在 `val`」，例句寫 `priority` 是 `{"val", "deadline"}`** | 程式（`aos-llm-kernel/src/letter/letter.cpp:159`、`aos-llm/src/send/send.cpp:59`）、kernel 文件、給 agent 看的 `knowledge/aos/brain.md`、你 10-15 的原文都是 `{"level", "deadline"}`；fable 以為只是文件不合，其實是程式跟 C-48 不合。陷阱：寫 `{"val": "high"}` 會被當成沒寫級數、默默變 normal、不報錯 | 本設計照程式用 `level`，轉交時原樣帶就不會掉級；要不要改成 `val` 是方向題 7 | — |
| 11 | **使用者 11-05「`served.jsonl` 也刪」**（think-as-function 08 題 3） | P2 的 `ledger.jsonl` 等於把它加回來，沒有問你（晚審裁定 1）；本設計的 `seen_at`／`child`／`switched` 全住在它上面 | 留著、明說翻案（方向題 1） | 照 11-05 拿掉：本設計的記帳、排隊時間、換模型成本都沒地方放 |
| 12 | **evolve-design 的 llm kernel 那列與落地第 6 步**：「本機模型一台 kernel 只放一包」「轉交回覆原樣印出」「隊 kernel 那台的環境把 `AOS_LLM_KERNEL` 設成總機」 | 三處都被本設計取代：後端宣告、`child`、包寫 `kernel`。evolve 自己寫了「更深的嵌套與排程交給 kernel-nest」 | evolve 第 6 步改照本題第 5、8 步施工 | 兩份圖紙打架，gpt 照哪份施工都會跟另一份不合 |
| 13 | **llm kernel 排序「有寫 deadline 的排在沒寫的前面」** | 推得的期限讓所有轉交來的信都帶 deadline，同級時會排在直接寄來、沒寫期限的信前面 | 這個期限是真的（上層真的只等這麼久），接受並寫進文件（方向題 3 的副作用） | — |
| 14 | **晚審設計 6、8：ledger 與 observed 存同一筆 usage；兩個 jsonl 只長不清、可能有半行或重複行** | 嵌套後同一筆 usage 存三份以上 | 留著三份，各是一層的他見；定一條加總規則（只加一層），文件寫明讀的人跳過壞行、用 `id`／`letter` 去重；誰清：kernel 不輪替，人或審視者清 | 以哪份為準不定，彙整時遲早重算 |

不開新條號（同批 lift-to-norms 暫編 N-68、C-84，本題避開）；要動的都是既有條的加註：N-42 (1)、C-52 續表 ③、N-63／P-39、C-48（看方向題 7）、kernel 文件。

## 方向題（11-07 已全裁：1、7 在 16:25，2～6 在傍晚都選★）

1. **逐封帳 ledger 去留，與 token 以哪份為準**（晚審裁定 1、設計 6）
   - **A★ 留著，明說翻案**：寄件人不管是 agent、腳本還是人手 `ask` 都有逐封帳，嵌套的對帳、排隊時間、換模型成本都靠它。agent 的 observed 和 kernel 的 ledger 都留 usage（各是自己那層看到的），加總規則固定成「只加一層；要全鏈就只加葉子行」。代價：檔案一直長，誰清要寫明。
   - B 照 11-05 拿掉：逐封成本只剩 agent 的 observed；不是 agent 的寄件人自己記；本設計的 `seen_at`、`child`、`switched` 沒有家，排隊時間與換模型成本量不到，嵌套鏈翻不下去。
   - C 留著但只留最近 N 行：多一套輪替機制；審視者翻舊帳可能翻不到。
   - B'（晚審另提）observed 只留 `letter` 與耗時、usage 只在 ledger：少一份重複，但 agent 要看自己花多少就得去讀 kernel 的帳（經 `aos-ledger` 介面才合 C-52）。
2. **本機後端要不要按模型批次排**
   - A 只互斥不批次：規則最少；本機信交替時每封換一次模型。
   - **B★ 互斥＋黏著**：多一條排序規則；急件照樣能換模型，同級的自然湊批。
   - C 一台 kernel 只放一個本機包、換模型＝改設定重起（evolve-design 現案）：零新規則；跑的中途試不了另一個本機模型，降級階梯（sol→terra→luna→本機小模型）要人介入；而且若有人另起第二台放本機包，互斥同樣失效。
3. **上層會等多久要不要告訴下層**
   - A 不告訴（現制）：靠收拾與 `sender.flock`；已掛上的照跑照花錢。
   - **B★ 推得的期限寫進給端點函數的 `priority`，轉交函數原樣帶**：下層輪到時已過期就不跑。副作用：agent 可能收到自己沒設過期限的 `DeadlineBad`（訊息誠實：是轉交信的期限）；轉交來的信同級時排在沒寫期限的信前面（衝突 13）。
4. **下層看到的寄件人是一隊一格，還是帶原 agent**
   - **A★ 一隊一格**：下層只知道「這隊」，隊內分攤看隊 kernel 的帳；也就是分隊額度的本意。
   - B 轉交函數把原寄件人塞進下層信：下層可按 agent 設額度，但下層認得上層內部；而且寄件人本來就不驗，等於誰都能冒。
5. **嵌套的錯誤怎麼報**
   - A 每層包一層（現制）：忠於「每層只說自己」的字面；字串隨深度變長，真原因在最裡層。
   - **B★ 透明轉交**：合格錯誤物件原樣過；agent 看到的跟沒嵌套相同；每層 ledger 的 `code` 仍各記自己。照 N-43 既有例外解釋，不另開 C-52 例外。
6. **轉交 proc 半路死被重掛一次，可能寄兩封下層信、花兩次錢**
   - **A★ 照通則**（重掛一次，風險自擔，跟「睡醒或 kill -9 可能多花一次腦」同一態度）；有了期限，第一封多半在下層輪到時就被拒。
   - B 轉交包不重掛（包多一個鍵）：少花錢，多一條規則。
7. **`priority` 展開形的 key：`level` 還是 `val`**
   - **A★ 程式改認 `val`、不認 `level`**（C-48／C-55 是寫明的規則；proto8 不留相容）：改 kernel 的 `priority_of`、aos-llm 的驗證、文件與 `knowledge/aos/brain.md`。後果：你 10-15 原文的寫法跟著換；改完前後混用的人會默默掉級（C-48 不認的 key 忽略），所以要在同一個 commit 換完。
   - B 留 `level`，C-48 例句改成 `level` 並註明 priority 是「原值放 `val`」的例外：程式不動；規則多一個例外。

## 代定（我替你做的小決定，都可以翻案）

1. `child` 寫成 `{"kernel", "letter"}` 物件，不只信名（fable 原案只有信名）：照 evolve-design「我叫了誰要寫明對方的帳現在在哪」；同一台隊 kernel 可以轉給好幾台下層，只有信名找不到帳。
2. agent 的 `self` 行記 `llm_kernel`（evolve 交給本題、fable 又推回 evolve 的那一條，在這裡定掉）：審視者才能從 agent 的帳找到隊 kernel 的帳。
3. ledger 的時間欄（含新的 `seen_at`）照 ledger 現制用 epoch 秒，不在本題改成日期字串；evolve-design 衝突 10 裁了「新格式用 ISO 8601」之後，ledger 要不要一起換再跟那條一起定。
4. ledger 用定義夾頂層 `interfaces.json` 的 `aos-ledger` 宣告（路徑相對 stack），名字跟 evolve 的 `aos-observed` 分開，因為行的形狀不同。
5. 轉交函數 `_metainfo.json` 的估時寫純數 `700`（fable 寫成 `{"cal": "700"}`，沒有變數的公式就是純數，C-56）；`resource` 用現有的 `"llm"`，不新造 `"llm_kernel"`。
6. `seen_at` 在掛上那一刻從 `queue.json` 抄進 `proc.json`，收尾時寫進 ledger（`queue.json` 掛上後就刪那格，不抄就沒了）。
7. 部署規則：指向同一台 LM Studio 的包只放在一台 kernel；文件寫明，程式不檢查。
8. 問腦 proc 掛在 kernel 自己那台 daemon、不經判官：kernel 文件已有「起 llm daemon 的殼別設 `AOS_KERNEL`」，改寫成規則句；所以晚審必修 9（判官重起可能對已轉寄的信回 `applied:false`）不影響問腦鏈，照晚審建議另修。若有人硬把 `AOS_KERNEL` 指向判官，kernel 的掛信不帶 `reply_to`，被拒了也收不到，那一格會一直被佔著（推論，未實測）——列進 kernel 已知限制。
9. 範本隊 kernel `timeout_ms` 180000、主 kernel 120000（上層要比下層長，P-36）。
10. `aos-llm --full` 失敗時 stdout 印錯誤 body：agent-fsm 的 `wait.py` 用 `recv --full`，施工時要確認它失敗時不去解析 stdout，或解析了也不出錯。

## 落地順序（照圖施工的小步；程式步交 gpt，條文與文件步由 opus 寫）

0. （方向題 7 照推薦）kernel 與 aos-llm 的 priority 展開形改認 `val`；文件、`knowledge/aos/brain.md`、範例同一個 commit 換完。完成條件：`{"val": "high"}` 排在 normal 前面，`grep '"level"'` 在 impls、kernel、knowledge 下沒有 priority 的命中。（若裁 B，這步改成只改 C-48 例句，下面各步的 `val` 換回 `level`。）
1. llm kernel：`request.json` 加頂層 `priority`（宣告級數＋推得期限，epoch 秒）；掛上時 `proc.json` 記 `seen_at`。完成條件：fake 端點把 stdin 印出來，看得到 `priority`；既有 `llm_http`、`llm_fake` 測試照過。
2. llm kernel：收成品時 stdout 有 `child` 就進 ledger、回信拿掉；ledger 每行加 `seen_at`、`code`、`child`、`switched`（先一律 false）。完成條件：ledger 每行都有這四個鍵，kernel docs 02 逐封帳欄位表更新。
3. llm kernel：退非 0 而 `reply.json` 是合格 `{"error": {"code": 字串, "msg": 字串}}`＝原樣回；否則照舊。完成條件：兩種 fake 端點（印合格錯誤物件／只印一行）各得到預期回信。
4. aos-llm：`ask --full`、`recv --full` 成功輸出加 `letter`；失敗時 stdout 印錯誤 body，stderr 與退出碼不變。完成條件：成功與失敗各一次，stdout 都是一行合法 JSON；agent-fsm 範本測試照過（代定 10）。
5. 新函數 `lib/aos/llm_forward/`（搬自試驗場，取代 evolve-design 落地第 6 步的寫法）：包必填 `to`、`kernel`；只對子行程設 `AOS_LLM_KERNEL`；`priority` 原樣帶；成功把 `letter` 換成 `child` 物件；下層錯原樣印、同退出碼、不加錯誤行；包缺 `kernel`＝`llm_forward: error: CfgBad endpoint pack has no "kernel"` 退 1。附 `_tooldef.json`、`_metainfo.json`（代定 5）、README。完成條件：fake 下層兩層串起來，agent 端成功與錯誤回信跟直連主 kernel 時逐字相同。
6. llm kernel：認 `backends.<名>.{slots, max_packs}` 與包的 `backend`；`queue.json` 加 `backends`；換包後第一封 `switched: true`。完成條件：兩個 `backend: "lmstudio"` 的 fake 慢包各寄 3 封、`max_packs: 1`，daemon 表上任一時刻只有一種包在飛。
7. llm kernel：排序加黏著（方向題 2 照推薦）。完成條件：同級 6 封交替兩包的信，實跑只換一次包。
8. 範本：新增 `kernel/llm-team/`；主 kernel 範本本機包改掛 `backends`；`endpoints.json` 窗多列 `backend`；kernel 定義夾加 `interfaces.json`（`aos-ledger`）。完成條件：照範本起兩台 kernel，不改任何環境變數就能嵌套跑通。
9. agent-fsm：`self` 行記 `llm_kernel`（若 evolve-design 的 `self` 行已落地就加一欄，沒有就跟它同一步）。完成條件：起一隻範本 agent，`observed.jsonl` 的 `self` 行有 `llm_kernel`、值等於啟動時的 `$AOS_LLM_KERNEL`。
10. 文件與條文（opus）：N-42 (1) 端點函數契約（五鍵、`priority`、`child`、合格錯誤物件透明）與排序；C-52 續表 ③ 加註「透明轉交不是新例外」；N-63／P-39 加註「往下一層寫在包裡，不改 hub」；kernel 已知限制補 `switched` 的盲點、跨 kernel 互斥失效、`AOS_KERNEL` 指判官的窗口；ledger 寫明誰清、跳過壞行、用 `id` 去重、只加一層；代定 12 拿掉 agent 那句；「一隊一格」標成使用者裁定（方向題 4 已在 11-07 傍晚裁 A）；`impls/aos-llm-kernel/docs` 補 LM Studio 一節。完成條件：wf-lint 綠；`grep "LM Studio"` 在 impls docs 有命中。
11. 試驗場：`defs/llm_team` 改用 `lib/aos/llm_forward` 與包寫 `kernel`，拿掉 `_entry` 裡改 `AOS_LLM_KERNEL` 那行；重跑一個地點，對帳腳本改沿 `letter → child` 配對。完成條件：樣本 100% 靠 `child` 配對、不靠行序，兩層 usage 不相加。

## 同批其他題

- 成本 JSON 通用格式、審視者怎麼用這些帳、子 agent 收掉前抄帳：交給 evolve-design（本題只照它已裁的 `cost`／`timeout_ms` 寫轉交函數的自稱）。
- 本機模型大小階梯的實際試驗：交給 arknights-kb。
- 工具權限演進：交給 tool-evolve。知識庫全庫規模：交給 kb-scale。
- 條文落地與編號：lift-to-norms（暫編 N-68、C-84，本題不開新號）。

## 使用者裁定（11-07 16:25，選項框）

- 方向題 1 ledger 去留：「留，明寫是翻案（推薦）」——ledger.jsonl 保留，條文註明 11-07 翻 11-05「也刪」；各層都記、加總只加一層。
- 方向題 7 priority 展開形的 key：「程式不動，條文改成"推薦用val"」——程式照舊用 `level`，C-48 改成「推薦用 val」而非強制。

### 11-07 傍晚（40 題選項框）

使用者 11-07 傍晚在 40 題選項框裡裁定（回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)）；除特別註明，選的都是推薦。回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進，沒逐題寫備註的也一樣。

- **kn-2**（本機模型要只排成單次使用，還是順便把同模型的信湊一起？）：選 B「互斥＋黏著」。備註原話：「靈活改進」
- **kn-3**（往下轉交時，要把上層最多肯等多久一起帶下去嗎？）：選 B「推得的期限寫進給端點函數的 priority，轉交函數原樣帶」。
- **kn-4**（下層要只看見整隊，還是看見原來哪隻 agent？）：選 A「一隊一格」。
- **kn-5**（下層報錯時，上層要原樣轉交嗎？）：選 B「透明轉交」。
- **kn-6**（轉交程式半路死掉，還要照通則重跑一次嗎？）：選 A「照通則（重掛一次，風險自擔，跟「睡醒或 kill -9 可能多花一次腦」同一態度）」。

kn-2 備註「靈活改進」：互斥＋黏著的排序規則本身也可以再改，跟 C-84「判準本身也能被改進」同一個意思。
