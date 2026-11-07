# fable 規劃：把「反向傳播式自我改進」做成 aos 的一部分——每層留一本帳、一隻審視者沿帳改函數
← [README](README.md)｜簡報 [01-簡報](01-簡報.md)

寫於 11-07 傍晚。資材只讀 01-簡報。大方向都是使用者的（§1 原話與想法 1～10），這份只在既定路上定細節；要使用者拍板的只有 §3 的衝突與 §4 的方向題。

---

## 一、白話總結

今天 arknights 知識庫那條線做出來的事，說白了是這樣：先讓聰明的師傅做一次，看他怎麼做；把他的做法寫成一張步驟表，能寫死的步驟全寫成腳本；剩下真的要「想」的步驟，換便宜一點的徒弟來做，看他哪裡出錯；出錯的地方再寫成腳本或改一下做法；改了一步，就把跟它相連的前後步驟一起重跑確認。這一輪一輪做下去，每個地點花的錢從五萬多 token 掉到六千多。現在這整件事是隊長（opus）用人工在做。

要讓系統自己做這件事，aos 其實只需要補兩樣東西，其他都已經有了。

**第一樣：每個函數都要有兩本帳。**一本是它自己說的（「我大概要跑多久、吃多少 token」），寫在定義旁邊的 `_metainfo.json`；另一本是叫它的人記下來的（「我叫了你三次，實際花了多少秒、回了多少字」），寫在叫它的人自己的地盤裡。這跟「履歷」和「主管考核表」的關係一樣：履歷是自己寫的，考核表是別人寫的，兩本不混在一起，也不互相改。現在 agent 範本已經有這本考核表（`observed.jsonl`），只差補幾個欄位讓它能對上「叫的是哪個定義、它的地盤在哪」。

**第二樣：一隻「審視者」agent。**它不是 aos 的新機制，就是一隻普通 agent，跟 thought 一樣是「做成工具，不做成機制」。它拿到一次跑完的結果，沿著地盤的樹（誰叫了誰，地盤就一層層套著）把所有考核表收起來加總，看出哪一步最貴、哪一步是 LLM 在做。然後照固定的順序試三招：先換便宜的模型試三次，過得了就換；換不了就看這一步的輸出是不是完全被輸入決定，是的話就請聰明模型寫成腳本；還不行就把這一步拆成「腳本先處理、LLM 只做小塊」。每改一個函數，就把叫它的、它叫的都標成「髒」，整棵重跑一次比對產出有沒有變；變了就退回。這就是使用者說的反向傳播：改了一個子函數，受影響的前後函數跟著重算、重量。

至於格式檢查、逐 byte 比對，那只是「門」：產出必須一樣才算過關。真正要壓低的是過關路上花的 token、呼叫次數、秒數。

其他幾個想法都能順著落下來：**成本寫成任意 JSON**，aos 只固定三個 key（token、calls、time_ms），其他想加錢、加「傲嬌度」都隨意，數字可以寫成公式。**連結路徑**全系統只認一種寫法 `a/b#/c/1`，但誰認、誰不認由各層自己說，aos-exec 不多管。**成千上萬的 agent**是指成千上萬個「定義資料夾」躺在磁碟上，叫到才起、用完就收，不是成千上萬個活著的行程；所以不需要新的喚醒機制。**嵌套 kernel**只要把試驗場已經做出來的轉交函數搬進 aos 的 lib 就好，每層 kernel 各記自己的帳，用量會一路帶上來。**本機模型一次只能載一個**，就是給它一個 kernel、一次只開一包。

需要使用者點頭的只有幾件：公式要多複雜、審視者自己能不能動手改程式、改好的東西誰拍板換上去、語意錯怎麼算進來。其他細節這份都定了。

---

## 二、設計

### 2.1 概念（五條，建議進 CONCEPTS）

**C-新1 函數有兩本帳：自稱與他見。**自稱寫在定義裡的 `_metainfo.json`，是估的、是宣告（可依輸入變化，可寫公式）。他見是叫它的那一層在自己 stack 記的實測，叫它的人只看得到自己看得到的（秒、位元組、結束碼、以及自己那層的 token），看不到對方裡面。兩本帳不互寫：跑的時候不改 `_metainfo`，觀測也不寫進對方定義。這條直接承 C-21（可預測性是觀察者的認識）與 C-52（不偷看下層）。

**C-新2 成本是任意 JSON 值；aos 只定三個通用 key。**`token`（`in`／`out`／`cached`）、`calls`、`time_ms`。其他 key 自由（錢、主觀評分、字串都行，承 C-14「人可任意附加特性」）。每個值都是 C-55 的雙形：純數，或展開成 `{"val", "unit"?, "max"?, "cal"?, "vars"?}`。`cal` 是字面上的公式字串，只有讀 metainfo 的人（審視者、kernel）會算它，aos-exec／directive 不碰（所以不違反 C-48 只有兩個指示詞、也不違反 C-56 寫什麼就做什麼——它寫的就是公式）。

**C-新3 呼叫樹＝stack 樹；帳沿樹走。**叫人的那層給對方一塊小格（N-50 已定），並在自己的帳上記下「我給了它哪塊小格」。觀測者只要拿到根 stack，就能沿著帳裡記的小格路徑往下走，碰到沒有帳的就是葉（腳本、或不認這套的程式）。不需要知道任何一層是什麼，不需要 daemon 表，不需要去對 kernel 的 ledger——token 從每層自己的 think 行就有。

**C-新4 審視者是 agent，不是機制。**改進迴圈是「量 → 挑 → 試 → 傳 → 記」五步，由一隻 agent 定義照規則跑。aos 本體只保證四件事：每層會留帳（C-新1）、帳走得到（C-新3）、定義寫得出來（`agents new`、寫資料夾）、改了之後量得到（跑一次就有新帳）。審視者改的是別人的定義**副本**（放自己工作區），不是正在跑的自己；換上去（採用）是另一個明確動作。這樣跟沙箱稿「self-improve 預設關」不衝突：運行中的 agent 改自己仍只能走 `self_tools` 覆蓋層。

**C-新5 門與目標分開。**門＝產出逐 byte 一致（或規則 lint 過）；目標＝門內的成本。優化永遠是「門過了之後比成本」，門沒過的不比。目標本身寫成一個 JSON 指標指進成本物件（例 `/token/in`），這部分使用者說以後再說，這裡只留位置、不設計。

### 2.2 各層誰負責

| 層 | 要做什麼 | 不做什麼 |
|---|---|---|
| aos-exec | **沒有新事。** | 不認新的路徑語法、不算公式、不管 metainfo。 |
| loop／fsm | **沒有新事。** | 不恢復 trace。 |
| daemon | 沒有新事；`max_running`／判官照舊。 | 不加「有信就醒」（見方向題 Q4）。 |
| llm kernel | 程式不改。多一個 kernel 定義範本 `kernel/llm-team/`（`exec` 指到 lib 的轉交函數）示範嵌套；本機模型一台 kernel、一次只開一包（`slots:1`）。 | 不讀 `_metainfo`（11-04 已拿掉，維持）；ledger 格式不動。 |
| agent 範本（agent-fsm） | `observed.jsonl` 補三處：起跑第一行 `self`；工具行加 `def`、`stack`；`interfaces.json` 宣告 `observed`。 | history 不動；不在範本裡放任何「改進」邏輯。 |
| lib 工具 | 新四支：`metainfo`（讀＋算公式的共用模組）、`forward`（llm 轉交）、`measure`（跑 N 次、走樹彙整、比對門）、`promote`（換上／退回定義）。改一支：`memory find` 認 `tags`。 | 不做 tag／連結的獨立工具（連結＝字串、追連結＝`memory read`、改連結＝`memory_write edit`，夠了）。 |
| 審視者（agent 定義） | 五步規則寫在 `system.txt`；階梯寫在 `ladder.json`；產出 `review.json` 與 `proposed/<定義>/`。 | 不直接改正在跑的定義；不自己算 token（用 measure）。 |
| 隊長（人／opus） | 定目標與門、定階梯、語意抽查、拍板採用（起步期）、寫條文。 | 不再手寫「哪步最貴」、「降哪級」、「前後成本」——這些審視者產。 |

### 2.3 資料格式

命名照既有規矩：全小寫加底線；計數 `counter_*`、時間點 `*_at`、上限 `max_*`、時長 `*_ms`。

#### (a) `_metainfo.json`（自稱）

```json
{
  "summary": "Decide which mentions in one place become links",
  "timeout_ms": 120000,
  "resource": ["llm"],
  "side_effect": false,
  "idempotent": false,
  "deterministic": false,
  "cost": {
    "token": {"in": 7004, "out": {"val": 380, "max": 800}, "cached": 0},
    "calls": 1,
    "time_ms": {"cal": "4000 + in_bytes * 1.2", "vars": {"in_bytes": "stdin bytes"}}
  },
  "cost_basis": {"statistic": "median", "sample_count": 3, "case": "poshan"},
  "tsundere": 0.4
}
```

- `timeout_ms` 取代今天的 `time_ms.max`（逾時是行為，估時是成本，分開放）。`cost.time_ms` 是估時。
- `cost` 底下三個通用 key 之外隨意加（例 `tsundere` 這種主觀值也可以放頂層）。不認得的 key 一律忽略（C-48）。
- `cal` 的變數名只能來自：`_tooldef.json` 的 `parameters` 名、以及固定的 `in_bytes`。語言見方向題 Q1。
- `cost_basis` 選填，說這份估值從哪來；審視者發新版定義時填。**跑的時候誰都不寫這個檔。**

#### (b) `observed.jsonl`（他見，每個 agent 自己的 stack）

```json
{"kind": "self",  "def": "/abs/defs/linker", "ws": "/abs/ws", "endpoint": "terra", "started_at": 1794035284.78}
{"kind": "think", "letter": "0179...2843648", "endpoint": "terra", "model": "chatgpt-gpt-terra-low", "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "elapsed_ms": 15974.2}
{"kind": "tool",  "name": "memory", "def": "/abs/lib/agent/memory", "stack": "tools/memory", "code": 0, "elapsed_ms": 41.7, "in_bytes": 88, "out_bytes": 2310}
{"kind": "tool",  "name": "thought", "def": "/abs/lib/agent/thought", "stack": "tools/thought", "child_stack": "children/t-linker-1794035-3f2a", "code": 0, "elapsed_ms": 9800.0, "in_bytes": 412, "out_bytes": 388}
```

- `self` 行是這層對自己的認識（`AOS_CD`、`AOS_WS`、生效的 endpoint），一個 stack 一行，起跑時寫。
- `tool` 行的 `def` 是這層 `tools.json` 登記的絕對路徑（自己的登記簿，不是偷看）；`stack` 是這層給對方的小格（相對本 stack）。thought／agents 這類會另起 agent 的工具，多一欄 `child_stack`（它自己回報的子 stack 路徑；`thought keep:true` 今天已回傳）。
- 時間一律是**叫的那層量的牆鐘時間**（含排隊、本機載入），這是 C-52 下唯一誠實的量法，也符合代定 13。
- `bash` 行只有 bash 一層；裡面再叫什麼，帳就斷在這。要算就包成工具（C-77）。

#### (c) `measure.json`（measure 工具產出，一次量測一份）

```json
{
  "def": "/abs/defs/place_run",
  "case": "/abs/cases/poshan",
  "repeat": 3,
  "check": {"pass": true, "diff": []},
  "cost": {"token": {"in": 6635, "out": 380, "cached": 0}, "calls": 1, "time_ms": 9800},
  "tree": {
    "def": "/abs/defs/place_run", "kind": "script",
    "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "calls": 0, "time_ms": 9800},
    "children": [
      {"def": "/abs/defs/kb_store", "kind": "script", "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "calls": 0, "time_ms": 120}, "children": []},
      {"def": "/abs/defs/linker", "kind": "agent", "endpoint": "terra",
       "cost": {"token": {"in": 6635, "out": 380, "cached": 0}, "calls": 1, "time_ms": 9500},
       "children": [{"def": "/abs/lib/agent/memory", "kind": "script", "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "calls": 0, "time_ms": 41}, "children": []}]}
    ]
  },
  "samples": [{"cost": {"...": "每次一份"}}],
  "measured_at": 1794040000.0
}
```

- 根 `cost` 是三次的中位數；`tree` 是沿 stack 樹走出來的，每節點的 `cost.token`＝它自己 think 行的和（**不**加子樹，避免重算；要總和看根）；`time_ms` 是父親記的牆鐘。
- `kind` 只有兩種：有 `observed.jsonl` 的叫 `agent`，沒有的叫 `script`。不猜更多。
- `check.diff` 列出與期望產出不一致的檔名（相對 ws）。

#### (d) `review.json`（審視者一輪一份，寫在自己工作區）

```json
{
  "round": 3,
  "case": "/abs/cases/poshan",
  "before": {"token": {"in": 15848, "out": 1530, "cached": 0}, "calls": 7, "time_ms": 46500},
  "target": {"def": "/abs/defs/linker", "reason": "llm step with largest token.in share (0.68)"},
  "tried": [
    {"move": "downgrade", "from": "sol", "to": "terra", "agreement": [0.94, 0.94, 0.94], "pass": true},
    {"move": "downgrade", "from": "terra", "to": "luna", "agreement": [0.44, 0.88, 0.0], "pass": false}
  ],
  "adopted": {"move": "downgrade", "to": "terra"},
  "dirty": ["/abs/defs/kb_link", "/abs/defs/kb_lint2"],
  "after": {"token": {"in": 7107, "out": 650, "cached": 0}, "calls": 1, "time_ms": 22300},
  "proposed": "proposed/linker",
  "why": "一句人話：terra 三次都 94%，過門；luna 第三次全錯，退回。",
  "reviewed_at": 1794041000.0
}
```

- `move` 只有三種：`downgrade`（換低一級 endpoint）、`fix`（輸出由輸入完全決定 → 寫成腳本或規則）、`split`（腳本前處理＋更小的 LLM 步）。順序固定，一輪只試一個目標。
- `dirty`＝目標的呼叫者與被呼叫者（從 `measure.json` 的樹找：父節點與子節點）。採用前整棵重量、門要全過。
- `why` 一句，給人看的。

#### (e) `ladder.json`（審視者的階梯）

```json
{"ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_agreement": 0.9}
```

門檻就是 B3 用的：每級三次獨立實例、三次都 ≥0.9 才算過，取合格中最低級。使用者裁定的四級照寫。

#### (f) 知識庫的連結與 tag（memory 工具的約定，不是新機制）

- 連結值＝一個字串，寫法 `節點路徑#/JSON指標`，相對知識庫根；例 `"source": "lore/characters/夕#/aliases/1"`。追連結＝`memory read` 那個字串（P3 已認）。建連結、解連結＝`memory_write edit` 那個欄位。沒有第三種形式。
- tag＝節點 JSON（或資料夾節點 `README.md` 同層的 `_tags.json`）裡的 `"tags": ["地點","烏薩斯"]`；`memory find` 加 `tag` 參數，逐字比對。
- 規矩一句：**要讓工具沿著走的才做連結；只是提到，寫名字就好。**（承想法 6「別濫用」。）

#### (g) 嵌套 kernel（lib `forward` 函數＋範本，程式搬自試驗場 `llm_forward`）

隊 kernel 的 `kernel.json`：`{"exec": "<lib>/forward", "endpoints": {"sol": {"to": "sol"}, "terra": {"to": "terra"}}, "budget": {...}}`。`forward` 讀 stdin `{"endpoint","request"}`，用 `aos-llm ask --full` 問 `$AOS_LLM_KERNEL`，回覆原樣印出。兩層各記各的 `ledger.jsonl`／`used.json`；上層不讀下層帳，用量靠回信帶。本機模型：一台 kernel 只放一包、`slots:1`，換模型＝換包＝隊長或審視者的明確動作，不在跑的中途切。

### 2.4 審視者的一輪（規則，寫進它的 system.txt）

1. **量**：`measure` 跑 case，拿 `measure.json`。
2. **挑**：樹裡 `kind=agent` 的節點，按 `token.in` 占比排，取最大；沒有 agent 節點就按 `time_ms` 取最大（這時只能 `split` 或結束）。
3. **試**：對目標依序試 `downgrade` → `fix` → `split`，一個成功就停。
   - `downgrade`：階梯往下一級，`measure` 三次，三次門都過且一致率 ≥ `min_agreement`。
   - `fix` 的訊號（09 已定）：三次輸出逐 byte 一樣、且 `--check` 說輸出由輸入完全決定；成立就請一隻聰明模型子 agent（thought）照輸入／輸出對寫腳本到 `proposed/<定義>/`，再量。
   - `split`：請聰明模型子 agent 把這步分成「腳本前處理＋更小的 LLM 步」兩個定義，再量。
4. **傳**：採用前把 `dirty`（目標的父與子）列出，整棵重量、門要全過；任一不過就退回，記在 `tried`。
5. **記**：寫 `review.json`；新定義留在 `proposed/`，由 `promote` 換上（誰按見 Q3）。
6. **長**：連三個 case 沒在任何樹裡出現的定義，記進 `review.json` 的 `retire` 建議；連兩個 case 出現同一組「同工具集＋同目標模板」的 thought 子 agent，建議 `agents new` 成專精定義。這兩條只建議，不自動做。

一輪只動一個目標，是刻意的：梯度一次走一步，才能說清楚「前後差在哪」。

---

## 三、與既有 CONCEPTS／NORMS 的衝突

| # | 既有條文 | 新想法 | 衝突在哪 | 建議與後果 |
|---|---|---|---|---|
| 1 | N-62：`#/` 只用在 aos-exec 入口路徑、`$ref` 檔名、argv[0]；C-51 互通「不進規範」 | 想法 1：資料與資料的關聯統一寫 `a/b#/c/1` | 條文把寫法綁在 aos-exec 這一層，新想法要它當通用的「指」法 | **鬆綁一句**：寫法全系統只有這一種（RFC 6901、第一個 `#` 切、`#` 後必 `/`、檔名不含 `#`），**誰認由各讀者自己宣告**（aos-exec 認入口、memory 認節點、aos-json 認檔）。`$env` 仍不認 `#`。後果：只改 NORMS 文字，程式零改；不把「跨檔一條路徑」塞進 aos-exec，避開 N-61 同名歧義。 |
| 2 | 待定稿：`_metainfo` 實測不回寫；C-46 定義呼叫時不變 | 想法 5：他者觀測也是 metainfo；試驗場把 `_observed.json` 寫進 `defs/<名>/` | 觀測寫進定義資料夾，就是回寫、就是定義變 | **守舊條**：他見住在觀測者自己的 stack／工作區，定義資料夾只有自稱。後果：試驗場的 `_observed.json` 作法不進 aos；審視者發新版時可以把量到的數寫進**新版**的 `_metainfo.json` 當宣告（那是作者在寫，不是跑的在寫）。 |
| 3 | 現行 `_metainfo.time_ms.{val,max}`（act.py／aos-mcp 讀 `max` 當逾時）；待定稿寫「只有 `timeout_ms` 強制」 | 想法 4／10：時間是成本一維，成本放 `cost` 物件 | 同一個 `time_ms` 混了「估時」和「逾時」；待定稿與實作本來就不一致 | 推薦 **`cost.time_ms`＝估時、`timeout_ms`＝逾時**，頂層 `time_ms` 拿掉。後果：33 支工具的 `_metainfo.json` 用腳本一次改完，act.py／aos-mcp 各改一行；不寫相容。另一選項是保留頂層 `time_ms` 不動、只加 `cost.token`／`cost.calls`，後果是時間寫兩處、以後必亂。 |
| 4 | C-48 指示詞只有 `$env`／`$ref`；C-56「寫什麼就做什麼」 | 想法 5：成本可寫公式 `{"cal": "x*2"}` | 像是在加第三種會「變身」的值 | **不是指示詞**：`cal` 是 metainfo 格式族的普通 key，aos-exec／directive 不碰，只有讀 metainfo 的人算它；值字面上就是公式。後果：NORMS 加一句「`cal` 由讀者求值、不由 aos-exec 求值」即可。語言多複雜見 Q1。 |
| 5 | N-39／N-30 把 fsm／loop 的 `trace.jsonl` 拿掉；N-13 窗沒有歷史 | 想法 5／7：每層要留實測帳（`observed.jsonl` 只追加） | 剛拿掉一種逐筆紀錄，又加一種 | 兩者不同性質：trace 是「跑到哪格」的內部過程，observed 是「花了多少」的成本帳，而成本是使用者點名的優化目標。**只准這一種帳**，而且要在 `interfaces.json` 宣告為公開輸出，外人才可讀（C-52 認公開介面）。 |
| 6 | 沙箱稿：self-improve 預設關；C-46 定義不變、漂移只在 stack | 想法 7／C-42：系統自己改函數 | 審視者寫新定義、換掉舊定義，就是在改系統 | 分兩段：審視者只寫到自己工作區的 `proposed/`，**換上去是另一個工具 `promote`**，受判官 `allowed` 管、預設不開。正在跑的 agent 改自己仍只能走 `self_tools`。後果：self-improve 預設關這條不用改。 |
| 7 | C-20「很多 agent 時誰先用腦」是最核心題；`max_children`／`max_running` 兩道關；C-78 啟動步驟少 | 想法 7／8：agent 成千上萬、可 sleep | 若是成千上萬個活著的 proc，排程題與 daemon 負荷都爆 | 讀成「成千上萬個**定義**，叫到才起（C-40 拋棄式函數），用完即收，stack 留在磁碟就是 sleep（C-16）」。後果：daemon 零改，排程題還是 kernel 原題；見 Q4。 |
| 8 | C-47 轉交型 kernel「建議不要濫用」；N-42 兩種 kernel 不併 | 想法 7：llm kernel 可嵌套 | 嵌套就是轉交 | 嵌套只為兩件事：分隊額度、本機模型一次一包。**只開一層**（隊→總機），不再往下疊；兩種 kernel 照舊不併。後果：一支 lib 函數＋一個範本，kernel 程式不動。 |

沒有衝突、只是要補條文的：C-新1～C-新5（§2.1）；`observed.jsonl` 三種行的格式；`measure.json`／`review.json` 格式；memory 的連結與 tag 約定。

---

## 四、方向題（原則推不出，請使用者點）

**Q1 公式 `cal` 的語言多大？**
- (a) 只四則運算、括號、數字、變數名，外加 `min`／`max`。約 30 行就能寫個安全求值器。
- (b) Python 運算式子集（含 `len`、比較、三元）。表達力強，但要防注入、要定義錯誤。
- (c) 先不做公式，只准常數＋`cost_basis` 說明。
- 後果：(a) 夠寫「隨輸入長度線性變」這類使用者舉的例子；(b) 以後有人會把邏輯塞進字串；(c) 想法 5 的「依輸入變化」就寫不出來。
- **推薦 (a)。**

**Q2 審視者能不能自己動手寫程式（`fix`／`split` 那兩招）？**
- (a) 審視者只出處方（`review.json` 的 `target`＋`move`＋`why`），施工交 gpt／codex 人工流程。
- (b) 審視者直接開聰明模型子 agent 寫腳本到 `proposed/`，自己量。
- (c) 先 (a) 跑三個地點，看處方準不準，再開 (b)。
- 後果：(a) 人還在迴圈裡但風險最低；(b) 一步到位但壞處方會被直接施工；(c) 多三個地點的時間。
- **推薦 (c)。**降級那招從第一天就全自動（它不寫程式）。

**Q3 `proposed/` 裡的新定義誰按「換上去」？**
- (a) 全自動：門過、成本降，`promote` 直接換。
- (b) 審視者寫好等人按，一鍵 `promote`。
- (c) 自動換、但留前版，下一個地點語意抽查錯就自動 `promote --rollback`。
- 後果：(a) 最快、語意錯會漏；(b) 人成瓶頸但這階段本來就要抽查；(c) 中間，多一個「自動退回」的機制。
- **推薦 (b) 起步，`promote` 從第一天就留前版（`prev/`），之後要走 (c) 不用改格式。**

**Q4 要不要給 daemon 加「有信就醒」？**
- (a) 不加。專精 agent 是定義，叫到才 `agents add`，用完 `rm`；stack 留在磁碟就是 sleep。
- (b) 加：睡著的 proc 有信進 queue 就被 daemon 叫醒。
- 後果：(a) 零改、不碰 C-20 的排程題，但「一隻 agent 長期記得事」要靠共用 stack 路徑；(b) daemon 多一個機制、多一條啟動設定（C-78）。
- **推薦 (a)。**等真的出現「非要常駐」的例子再談。

**Q5 語意錯（格式過了、內容錯，像「煮傘居士」建成另一個人）怎麼進門？**
- (a) 人抽查，錯的補進 case 的期望產出，下次門就會擋。
- (b) 加一隻高階模型當裁判，裁判的 token 算進成本。
- (c) 先 (b) 擋一道、人再抽查裁判。
- 後果：(a) 門會越來越準但要人；(b) 貴且裁判也會錯；(c) 最穩但成本兩層。
- **推薦 (a) 現在、(c) 到第 5 個地點以後。**理由：這階段地點少，人抽查便宜；期望產出累積起來就是最便宜的裁判。

---

## 五、落地順序（交 gpt 照圖施工；每步一句完成條件）

原則：每步獨立可測、不帶設計決策；Q1～Q5 沒點之前，照推薦走。試驗場（`~/code/playground-ak/`）改接新工具放在最後，不卡 aos 本體。

**S1 `lib/metainfo.py` 共用模組。**讀 `_metainfo.json`，認 `cost`（三通用 key、值雙形、`cal`＋`vars`）與 `timeout_ms`；提供 `eval_cost(metainfo, vars)` 用四則＋`min`／`max` 求值。
完成條件：單元測試覆蓋純數、`{val}`、`{cal}` 三種形，非法運算子（如 `__`、`import`）必拒。

**S2 33 支工具的 `_metainfo.json` 改格式。**寫一支一次性腳本：頂層 `time_ms.val` → `cost.time_ms`，`time_ms.max` → `timeout_ms`，刪頂層 `time_ms`；act.py 與 aos-mcp 的逾時改讀 `timeout_ms`。
完成條件：`aos-tools ls` 全部工具通過 S1 的讀取、既有測試全綠、repo 內 grep 不到 `time_ms.max`。

**S3 `observed.jsonl` 補欄。**agent-fsm 起跑寫 `self` 行；act.py 的 `tool` 行加 `def`（取自 `tools.json`）與 `stack`（相對本 stack）；thought／agents 工具在 stdout 回傳子 stack 路徑時，act.py 把它記成 `child_stack`；`interfaces.json` 加 `"observed": "observed.jsonl"`。
完成條件：起一隻範本 agent、叫一次 memory 與一次 thought，`observed.jsonl` 有 `self` 一行、`tool` 兩行，且兩行的 `stack`／`child_stack` 指到的目錄都存在並各有自己的檔案。

**S4 `lib/agent/forward`。**把試驗場 `defs/llm_forward/_entry` 搬進 lib，加 `_tooldef.json`／`_metainfo.json`；新增 kernel 範本 `kernel/llm-team/`（`exec` 指 forward、`endpoints` 用 `{"to"}`）。
完成條件：隊 kernel → 總機兩層各有自己的 `ledger.jsonl`，經隊 kernel 問一次的 agent，其 `observed.jsonl` 的 `think` 行 `usage` 不是 null。

**S5 `lib/agent/measure`（量）。**stdin `{"def","case","repeat","stack"}`；跑 `repeat` 次，每次沿根 stack 走 `observed.jsonl` 樹，彙整成 §2.3(c) 的 `measure.json`（根 cost 取中位數）。
完成條件：對一隻會叫 thought 的 agent 跑 `repeat:2`，`tree` 有兩層、根的 `token.in` 總和等於所有 `think` 行 `prompt_tokens` 之和（手算對得上）。

**S6 `measure` 加門。**case 夾內 `input.json`＋`expect/`；跑完比對 ws 產出與 `expect/` 逐 byte，寫進 `check`。
完成條件：改 `expect/` 任一檔一個 byte，`check.pass` 變 false 且 `diff` 列出該檔名。

**S7 `memory find` 認 tag。**節點 JSON 的 `tags` 陣列（資料夾節點用同層 `_tags.json`）；`find` 加選填參數 `tag`，逐字比對；`_tooldef.json` 的 `path` 說明補一句連結寫法 `節點#/指標`。
完成條件：兩個節點帶不同 tag，`find {"tag": X}` 只回帶 X 的那個；`read "a/b#/c/1"` 回該陣列元素。

**S8 `lib/agent/promote`（換上／退回）。**stdin `{"proposed","target"}`：把 `target` 現版搬到 `target/prev/`，`proposed` 覆蓋成新版；`{"target","rollback":true}` 反向。受判官 `allowed` 管。
完成條件：promote 後 `measure` 門仍過；rollback 後 `target` 與 promote 前逐 byte 相同。

**S9 審視者定義 `templates/reviewer/`。**system.txt 寫 §2.4 六條規則；工具只給 measure、memory、memory_write、thought、agents、bash_logged；`ladder.json` 照 §2.3(e)。第一版只做 `downgrade`（Q2 推薦）。
完成條件：對婆山鎮 case 跑一輪，產出 `review.json` 的 `target` 是 linker、`tried` 含 sol→terra 三次一致率、`adopted` 為 terra、`dirty` 列出 kb_link。

**S10 審視者加 `fix`／`split`（等 Q2 點頭後）。**兩招都是開 thought 子 agent（聰明級）寫到 `proposed/`，再呼叫 measure；門不過自動退回。
完成條件：給一個輸出完全由輸入決定的假 LLM 步，審視者產出腳本版、門過、`after.token.in` 為 0。

**S11 試驗場改接。**`place_run` 的步驟表改用 S5 的 measure 量、`meta_observe` 退役（不再讀 ledger、不再寫 `defs/*/_observed.json`）；地點 3 起由審視者出 `review.json`。
完成條件：地點 3 的 `review.md` 數字段全由 `review.json` 生成，隊長只填「語意抽查」與「為什麼」兩段。

**給 opus（不交 gpt）：**C-新1～C-新5 入 CONCEPTS；NORMS 補 `_metainfo.cost`／`timeout_ms`、`observed.jsonl` 三種行、`measure.json`／`review.json`、N-62 鬆綁一句、`cal` 由讀者求值一句、memory 連結與 tag 約定；待定稿「實測不回寫」維持並加註他見住處。
