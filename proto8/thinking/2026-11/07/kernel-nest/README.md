# llm kernel 嵌套的設計：只靠一支轉交函數，每層自己排、自己記、自己說錯，靠「期限往下帶、子帳位置往上帶一層」串起帳與時間
← [2026-11-07](../README.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

使用者 11-07 方向題全裁（1、7 在 16:25，2～6 在傍晚，見「使用者裁定」）；隊長替他做的小決定在「代定」，每條可翻案。程式已在 [impl-plan](../impl-plan/README.md) 批 7 `433bb9705`、批 8 `de2bd66f2` 做完（[12](../impl-plan/12-批7施工結果.md)、[13](../impl-plan/13-批8施工結果.md)），二進位 11-07 19:58 已裝；試驗場隊 kernel 改接 `lib/aos/llm_forward` 由 arknights 第三輪（K11）做完。

## 結論

- 嵌套只靠一支轉交函數 `llm_forward`：轉交型 kernel 就是端點函數換成轉交函數的普通 llm kernel。
- 帳：轉交回話帶 `child`（下一本帳在哪台、信名），隊 kernel 記進自己的 ledger、不往上傳；兩層 token 是同一筆錢，加總只加一層（全鏈只加葉子行）。
- 期限：級數與期限往下帶（期限取信上寫的與本層會放棄的較早者），下層輪到時已過期就回 `DeadlineBad` 不跑。
- 時間：ledger 多記 `seen_at`（排隊時間）與 `switched`（換模型後第一封）；時間只記不排。
- 本機模型：kernel 設定宣告 `backends`，同後端互斥＋同模型黏著。
- 報錯：下層的合格錯誤物件原樣轉交（kn-5），agent 看到的跟沒嵌套一樣。
- 往下一層去哪寫在包的 `kernel` 鍵，hub 變數（`AOS_LLM_KERNEL`）整棵樹一個值；同一台隊 kernel 可以把不同的包轉給不同的下層總機（使用者說的「專精此道的kernel」）。
- 問腦鏈不經判官。

## 設計

### 概念（四條）

1. **轉交型 kernel＝一台普通 llm kernel，只是端點函數換成轉交函數**（C-47 11-05 加嚴：判斷後轉交給有權的 kernel 的算 kernel）。排程、留格、額度、流水帳全照 llm kernel 現制，它的包不打 HTTP，而是寄信給另一台 kernel。深度不限，每層只看得到下一層的信箱（N-42 (1)「對外只有信箱＋aos-llm」）。
2. **一層只知一層**：上層只知道下層的信箱位置與回信形狀；下層只知道寄件人是誰（信封 `sender`，不驗，10-15「先信任」）。串帳只靠兩個宣告：上層把期限與宣告級數寫進交給端點函數的單子（往下帶）；端點函數把自己寄出的子信在哪台、叫什麼寫進回話（往上帶一層，到此為止）。
3. **每層的帳是那層的他見；同一筆錢在每層都會出現一次，加總時只加一層**。有 `child` 的行是下層那筆錢的鏡子；全鏈 token 總數＝只加沒有 `child` 的行（葉子）；某一層的花費＝只看那一層。agent 的 `observed.jsonl` think 行也是鏡子。
4. **後端是 kernel 自己的資源格**（C-09／C-10）：同一台實體後端（LM Studio）背後的幾個包共用格數，並可宣告同時最多幾種包在飛。只有直接管那台後端的 kernel 知道它。互斥只在一台 kernel 之內成立，所以所有指向同一台 LM Studio 的包必須放在同一台 kernel（代定 7）。

### 拓撲

```
agent ──AOS_LLM_KERNEL──▶ 隊 kernel（exec＝llm_forward；每包寫 to＋kernel）
                              │ 包 sol/luna  ──▶ 主 kernel（exec＝llm_http；雲端包＋所有 LM Studio 包，寫 backends）
                              │ 包 local     ──▶ 同一台主 kernel 的 lm-* 包
                              └ 包 special   ──▶ 另一台專精 kernel（也可以再轉交）
```

- 每台 kernel 是一台 daemon 的身體（`daemon.json` 的 `exec`），問腦 proc 掛在它自己那台 daemon，不經判官（代定 8）。
- `AOS_LLM_KERNEL` 整棵樹只有一個值（agent 那邊指隊 kernel）；往下一層去哪裡寫在包的 `kernel` 鍵，由轉交函數讀。
- 起法照 C-78 四步；多一層＝多一台 daemon，由根 daemon 監督。

### 一封信走過兩層

以 agent → 隊 kernel（`llm_team`）→ 主 kernel（`llm_kernel`）為例。

1. agent 用 `aos-llm send`（agent-fsm 的 wait 格）或 `ask --full` 寄到隊 kernel：body `{"endpoint": "sol", "request": {...}, "priority": {"level": "high"}}`。agent 的 `observed.jsonl` think 行記 `letter`；`self` 行記 `llm_kernel`＝起動時的 `$AOS_LLM_KERNEL`（代定 2）。
2. 隊 kernel 照現制排序、留格、額度判斷，掛成 `llm_<信名>` proc：
   - `request.json` 頂層 `priority`＝`{"level": <信宣告的級數，沒寫＝"normal">, "deadline": <min(信的 deadline, 本層 mounted_at＋timeout_ms)>}`；沒有 `timeout_ms` 也沒有信的 deadline 就不寫 `deadline`。aging 升上來的級數不寫。key 用 `level`（方向題 7）。
   - `proc.json` 記 `seen_at`（本層第一次在 `new/` 看到這封的時刻，掛上時從 `queue.json` 的 `seen_at_ms` 抄過來）。
3. `llm_forward` 讀 stdin，從包裡拿 `to`（下層代號）與 `kernel`（下層 kernel 的 stack 絕對路徑），組 `{"endpoint": to, "request": 原樣, "priority": 原樣}`，以 `AOS_LLM_KERNEL=<kernel>` 只給自己的子行程跑 `aos-llm ask --full`。下層看到的寄件人是隊 kernel 一格。
4. 主 kernel 照現制排序（high 可用 `reserved`）；輪到時期限已過＝回 `DeadlineBad`、不跑；否則掛 `llm_http`、記自己的 ledger、回信。LM Studio 的包再過 `backends` 的格數與種數關。
5. `aos-llm ask --full`／`recv --full`：成功時輸出多頂層 `letter`＝那封信名；失敗時 stdout 印錯誤 body `{"error": {"code", "msg"}}` 一行，stderr 那一行與退出碼不變。
6. 轉交函數成功時：把 `letter` 換成 `child: {"kernel": <下層 stack>, "letter": <信名>}`（代定 1），其餘原樣印出、退 0。下層回錯誤時：stdout 原樣印那個錯誤 body、照 aos-llm 的退出碼結束、不加自己的錯誤行（N-43「透明轉交別人的碼」）。轉交函數自己的錯（包沒 `kernel`、aos-llm 不在、stdout 讀不懂）才印 `llm_forward: error: <代號> <原因>` 退 1。
7. 隊 kernel 收成品：（a）stdout 有 `child` 就記進 ledger 那行，回信裡拿掉；（b）退非 0 而 `reply.json` 整份是合格的 `{"error": {"code": 字串, "msg": 字串}}`＝原樣當回信，否則 `EndpointFailed`＋第一行；（c）ledger 每行有 `seen_at`、`code`、`child`、`switched`。
8. agent 收到的成功回信與錯誤回信，形狀跟沒嵌套時相同。

### 本機後端：互斥與批次

主 kernel 的 `kernel.json` 頂層 `backends`；包多一個 kernel 看的鍵 `backend`（五鍵：`exec`／`slots`／`budget`／`speed`／`backend`，其餘原樣交給端點函數）。

- **後端格數**：`backend` 相同的包，在飛總數 ≤ `backends.<名>.slots`；疊在包自己的 `slots` 與頂層 `slots` 之上，三關都過才掛。
- **同時幾種包**：`backends.<名>.max_packs`（選填，沒寫＝不限）。在飛的包種數到頂時，別種包的信跳過、看下一封（不停整列）。LM Studio 寫 `{"slots": 1, "max_packs": 1}`。
- **黏著**（kn-2）：排序在「deadline 近的先」之後、「包的 speed」之前插一條：同後端上，跟 `queue.json.backends.<名>.pack`（目前載著的包）相同的先。只在同級同期限時起作用；急件照樣能換模型。
- **狀態**：`queue.json` 多 `backends: {名: {"pack", "switched_at", "counter_switches"}}`；每次實際換包時更新，換包後第一封的 ledger 行 `switched: true`。
- **換模型成本**：不另量；事後「`switched: true` 行的中位耗時－同包其他行的中位耗時」。
- `backend` 是設定者宣告的（C-56），kernel 不從 url 推。
- **已知限制**（寫進 kernel 文件，不加機制）：kernel 只知道自己最後掛的是哪包，不知道 LM Studio 實際載著什麼——人手在 LM Studio 換模型、或 kernel 重起後第一封，`switched` 可能記錯；兩台 kernel 都放了本機包＝互斥失效（自擔）。

### 時間怎麼拆

每層 ledger 有 `seen_at`、`mounted_at`、`finished_at`、`elapsed_ms`：

| 要看的 | 怎麼算 | 誰的帳 |
|---|---|---|
| 這層排隊多久 | `mounted_at − seen_at` | 本層 |
| 這層跑一封多久（含等 daemon 套用、含下層全部） | `elapsed_ms` | 本層 |
| 轉交這一跳的開銷 | 上層 `elapsed_ms` －（下層排隊＋下層 `elapsed_ms`） | 兩層對帳（沿 `child`） |
| 全鏈總時間 | agent think 行的 `elapsed_ms` | agent |
| 換模型代價 | `switched` 行與一般行的差 | 管後端那層 |

時間只記、不排（排序除了黏著那條不動）；不回寫 `_metainfo`。估時寫 `_metainfo.json` 的 `cost.time_ms`、逾時寫 `timeout_ms`（evolve-design 格式）。

### 逾時與失敗

- **逾時層層包**（P-36，aos 不替人算）：每層 `timeout_ms` 從自己掛上起算，包含下層排隊與執行。上層 `timeout_ms` ≥ 下層 `timeout_ms`＋下層預期排隊時間；範本隊 kernel 180000、主 kernel 120000（代定 9）。
- **上層先放棄時**：轉交 proc 被 daemon 整群收 → 子行程 `aos-llm ask` 一起死、`sender.flock` 釋放 → 下層信若還在 `new/` 被收拾掉；若已掛上就跑完、花錢、回信被撤。往下帶的期限讓下層多半在輪到時就拒掉。
- **下層 kernel 死了或睡了**：信堆在下層 `new/`，上層等到 `timeout_ms` 回 `EndpointFailed`（不加偵測、不加健康檢查）。
- **轉交 proc 半路死**：照通則重掛一次（kn-6）。
- **ledger 的 `code`**：每層記自己回給寄件人的代號，成功＝null。透明轉交時隊層的 `code` 就是下層的代號，看 `child` 知道是誰說的。

### 資料格式

隊 kernel `kernel.json`（範本 `kernel/llm-team/`）：

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

kernel 給端點函數的 `request.json`（`deadline` 用 epoch 秒）：

```json
{"endpoint": {"to": "gpt-sol-low", "kernel": "/abs/llm_kernel", "summary": "..."},
 "request": {"messages": [{"role": "user", "content": "..."}]},
 "priority": {"level": "high", "deadline": 1794035404.787}}
```

轉交函數成功時的 stdout：

```json
{"message": {"role": "assistant", "content": "..."}, "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "model": "chatgpt-gpt-sol-low",
 "child": {"kernel": "/abs/llm_kernel", "letter": "01794035285110287381.1482882.2843709"}}
```

透明轉交下層錯誤（退出碼＝aos-llm 的，stderr 沒有 `llm_forward: error:` 行）：

```json
{"error": {"code": "EndpointFailed", "msg": "endpoint function exited with code 1: llm_http: error: EndpointFailed HTTP 500: ... Connection error."}}
```

隊 kernel 的 ledger 一行（時間 epoch 秒，代定 3）：

```json
{"id": "01794035284500175665.1482852.2843648", "endpoint": "sol", "sender": "/abs/ws", "model": "chatgpt-gpt-sol-low",
 "seen_at": 1794035284.512, "mounted_at": 1794035284.787, "finished_at": 1794035300.761, "elapsed_ms": 15974,
 "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "code": null,
 "child": {"kernel": "/abs/llm_kernel", "letter": "01794035285110287381.1482882.2843709"}, "switched": false}
```

主 kernel 同一筆換成本機模型後第一封（葉子：`child` null）：

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

kernel 定義夾頂層 `interfaces.json` 宣告帳（路徑相對 stack，代定 4）：

```json
{"aos-ledger": {"file": "ledger.jsonl"}}
```

`lib/aos/llm_forward/_metainfo.json`（自稱只說自己的開銷，代定 5）：

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
| 隊 kernel | 本層排序／留格／額度／`timeout_ms`；給端點函數 `priority`（含推得的期限）；ledger 記 `seen_at`、`code`、`child`；回信拿掉 `child`；合格錯誤物件原樣回 | 下層是誰、下層的帳、原寄件人（不往下傳） |
| 轉交函數 | 照包的 `to`／`kernel` 寄；`priority` 原樣帶；成功回 `child`；下層的錯透明轉交，自己的錯用自己名字 | 排程、額度、重試、等多久 |
| 主 kernel | 同隊 kernel；另加 `backends` 格數、`max_packs`、黏著、`switched` | 寄件人後面是誰（一隊一格）、上層等多久（只看期限） |
| 端點小 proc（`llm_http`） | 打 API、回 `{"message","usage","model"}`、錯了 stderr 一行 | 任何排程與上層資訊 |
| daemon | 掛／收 proc、`timeout_ms` 殺整群 | 優先權、排隊 |
| 判官 | 只管 agent 那類 proc 的掛不掛；不在問腦鏈上 | 問腦 |
| 審視者（evolve-design） | 沿 `letter → child` 翻帳；只加葉子行；用 `switched` 算換模型成本 | — |

### 這一版不做的

搶位（殺在飛的 low 讓 high 進）、包到頂自動降級、拿實測時間排序、kernel 公告「現在要排多久」（NORMS 待定照舊）、跨 kernel 的後端鎖、下游按原 agent 記額度。

## 跟既有條文的讀法（結論）

不開新條號，動的都是既有條的加註（N-42 (1)、C-52 續表 ③、N-63／P-39、C-48、kernel 文件）。

1. N-42 (1) 排序「級數＋aging → 時限 → speed → 等得久 → 先寄」：在時限與 speed 之間插黏著（kn-2）。
2. N-42 (1)／kernel docs 02 端點函數契約：stdin 多 `priority`；stdout 多選填 `child`；退非 0 而 stdout 是合格錯誤物件＝原樣回。既有端點函數不受影響（C-48 多的 key 忽略）。
3. C-52 表 ③、N-43、P-21、C-53「每層只說自己」：透明轉交以 N-43 既有的「透明轉交別人的碼」解釋，不開新例外；表 ③ 只剩葉子端點函數那一種（kn-5）。
4. P-39「`AOS_LLM_KERNEL` 整棵樹一致」、N-67 ⑨「跨樹 hub 只在 root 層設」：包寫 `kernel`，hub 整棵樹一個值；轉交函數只對自己那一個子行程設 `AOS_LLM_KERNEL`（aos-llm 只認環境變數）。
5. arknights-kb 代定 12「並行的本機級 agent 必須同一個模型」：由 `backends` 取代，agent 自由選本機包。
6. 下游 `senders` 一隊一格（kn-4 使用者裁定）：隊內帳在隊 kernel。
7. C-56「不為邊緣狀況加機制」：一次一模型是使用者硬規矩、C-09 意義下的真資源格，`backends` 不算邊緣；`max_packs` 之外不加別的。
8. kernel docs 02「回信＝reply.json 原樣」：例外是拿掉 `child`。
9. `_metainfo`「實測不回寫」：時間只寫 ledger，排序不看，無衝突。
10. C-48／C-55「展開形的原值固定在 `val`」vs 程式與 10-15 原文的 `{"level", "deadline"}`：程式不動，C-48 改成「推薦用 val」（方向題 7）。寫 `{"val": "high"}` 會被當成沒寫級數、默默變 normal、不報錯。
11. 使用者 11-05 `served.jsonl` 選「也刪」：ledger.jsonl 保留，明寫 11-07 翻案（方向題 1）。
12. evolve-design 的 llm kernel 那列與落地第 6 步（本機一台 kernel 只放一包、轉交回覆原樣印出、隊 kernel 改 hub）：由本設計取代（後端宣告、`child`、包寫 `kernel`）。
13. 「有寫 deadline 的排在沒寫的前面」：轉交來的信都帶推得的期限，同級時排在沒寫期限的信前面；接受並寫進文件（kn-3 的副作用）。agent 可能收到自己沒設過期限的 `DeadlineBad`。
14. ledger 與 observed 存同一筆 usage、jsonl 只長不清：各是一層的他見，加總只加一層；讀的人跳過壞行、用 `id`／`letter` 去重；kernel 不輪替，人或審視者清。

## 使用者裁定

### 11-07 16:25（選項框）

- 方向題 1 ledger 去留：「留，明寫是翻案（推薦）」——ledger.jsonl 保留，條文註明 11-07 翻 11-05「也刪」；各層都記、加總只加一層。
- 方向題 7 priority 展開形的 key：「程式不動，條文改成"推薦用val"」——程式照舊用 `level`，C-48 改成「推薦用 val」而非強制。

### 11-07 傍晚（40 題選項框）

回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)；回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進。

- **kn-2**（本機模型要只排成單次使用，還是順便把同模型的信湊一起？）：選 B「互斥＋黏著」。備註原話：「靈活改進」——排序規則本身也可以再改（C-84「判準本身也能被改進」）。
- **kn-3**（往下轉交時，要把上層最多肯等多久一起帶下去嗎？）：選 B「推得的期限寫進給端點函數的 priority，轉交函數原樣帶」。
- **kn-4**（下層要只看見整隊，還是看見原來哪隻 agent？）：選 A「一隊一格」。
- **kn-5**（下層報錯時，上層要原樣轉交嗎？）：選 B「透明轉交」。
- **kn-6**（轉交程式半路死掉，還要照通則重跑一次嗎？）：選 A「照通則（重掛一次，風險自擔，跟「睡醒或 kill -9 可能多花一次腦」同一態度）」。

## 代定（隊長替使用者做的小決定，每條可翻案）

1. `child` 寫成 `{"kernel", "letter"}` 物件，不只信名：同一台隊 kernel 可以轉給好幾台下層，只有信名找不到帳。
2. agent 的 `self` 行記 `llm_kernel`：審視者才能從 agent 的帳找到隊 kernel 的帳。
3. ledger 的時間欄（含 `seen_at`）用 epoch 秒；要不要換 ISO 8601 跟 evolve-design 衝突 10 一起定。
4. ledger 用定義夾頂層 `interfaces.json` 的 `aos-ledger` 宣告（路徑相對 stack），名字跟 evolve 的 `aos-observed` 分開。
5. 轉交函數 `_metainfo.json` 的估時寫純數 `700`；`resource` 用 `"llm"`。
6. `seen_at` 在掛上那一刻從 `queue.json` 抄進 `proc.json`，收尾時寫進 ledger。
7. 部署規則：指向同一台 LM Studio 的包只放在一台 kernel；文件寫明，程式不檢查。
8. 問腦 proc 掛在 kernel 自己那台 daemon、不經判官（起 llm daemon 的殼別設 `AOS_KERNEL`）；晚審必修 9（判官重起可能回 `applied:false`）不影響問腦鏈。若有人硬把 `AOS_KERNEL` 指向判官，kernel 的掛信不帶 `reply_to`，被拒了收不到，那一格會一直被佔著（推論，未實測）——列進 kernel 已知限制。
9. 範本隊 kernel `timeout_ms` 180000、主 kernel 120000。
10. `aos-llm --full` 失敗時 stdout 印錯誤 body：agent-fsm 的 `wait.py` 用 `recv --full`，失敗時不解析 stdout 或解析了也不出錯。

## 同批其他題

- 成本 JSON 通用格式、審視者怎麼用這些帳、子 agent 收掉前抄帳：[evolve-design](../evolve-design/README.md)。
- 本機模型大小階梯的實際試驗：arknights-kb。
- 工具權限演進：[tool-evolve](../tool-evolve/README.md)；知識庫全庫規模：[kb-scale](../kb-scale/README.md)。
- 條文落地與編號：[lift-to-norms](../lift-to-norms/README.md)（本題不開新號）。
