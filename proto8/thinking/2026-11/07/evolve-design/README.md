# 反向傳播式自我改進的頂層設計：每個函數留帳、帳隨呼叫樹往上走、一隻審視者照帳一次改一個函數
← [2026-11-07](../README.md)｜簡報 [01-簡報](01-簡報.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

## 白話總結

今天 arknights 知識庫那條線跑出來的做法，說穿了是「師傅帶徒弟」：先讓聰明的模型做一次，把它走過的路寫成步驟表，能寫死的步驟改成腳本；剩下真要動腦的步驟換便宜模型做，看它哪裡錯；錯的地方再寫成腳本或改做法，改了一步就把前後相連的步驟一起重跑確認。這樣一輪一輪下來，一個地點從五萬多 token 掉到六七千。現在這件事全靠隊長人工在做，這份設計要讓它變成系統自己會做的事。

要做到這點，aos 只需要補兩樣東西。第一樣是「帳」。每個函數有兩本帳：一本是它自己說的（像履歷：「我大概跑多久、吃多少 token」），寫在定義旁的 `_metainfo.json`；另一本是叫它的人記下來的（像主管的考核表：「我叫了你三次，實際花了多少秒、多少 token」），寫在叫的人自己的地盤（stack）裡。兩本不混、不互改。

帳要能「往上收」。叫人的那一層，除了記自己花了多少，還要記「我叫了誰、它的帳放在哪」。這樣只要拿到最上層的那本帳，就能像翻族譜一樣一路往下翻，看到整棵呼叫樹每一節花了多少。子 agent 用完會被刪掉，所以刪之前要先把它的帳抄一份留在叫它的那層；腳本想被看穿，就自己也記帳，不記的就當它是一片葉子、只看外面量到的時間。

第二樣是「審視者」。它不是新機制，就是一隻普通 agent，照固定規則做幾件事：量一次、挑出最貴的那一步、試著改它、把相連的前後步驟一起重跑、寫下結果，換上之後再盯著看。改的方法有固定順序：先換便宜一級的模型試三次；不行就看這一步的輸出是不是完全由輸入決定，是的話寫成腳本；再不行就拆成「腳本先處理、模型只做一小塊」。它改的是一份副本，過了門又變便宜才換上去，換上後再盯幾個地點，真的變差才退回。一輪只動一個函數，這樣才說得清「前後差在哪」——這就是使用者說的反向傳播。

「格式對不對、產出一不一樣」只是門：過了門的版本才拿來比成本，真正要壓低的是過門路上花的 token、呼叫次數和秒數。其他想法都順著落下：成本是任意 JSON，aos 只固定三個常用欄位；數字可以寫成簡單公式；路徑全系統只有一種寫法 `a/b#/c/1`，誰認由各層自己說；「成千上萬個 agent」是成千上萬個躺在磁碟上的定義，叫到才起；llm kernel 嵌套只要一支轉交小程式。

使用者 11-07 已經裁了方向：公式用「語言名當 key」，先只做加減乘除，以後要更複雜就換成 lua、python，甚至交給一隻 agent 算；審視者先開處方、三個地點後放手自己寫程式，而且審視者自己的改進過程也記帳，之後可以被另一隻 agent 改進；改好的版本自動換上，變差自動退回，但要像訓練神經網路那樣容忍短暫退步，不是一變差就退；daemon 不加「有信就醒」；語意錯先交給高階模型當裁判，人抽查為輔；`_metainfo` 裡的「估時」和「逾時」拆開。

「容忍短暫退步」的具體做法是：品質不容忍，換上後只要有一次產出不合格就馬上退回；成本則容忍一段，換上後看三個地點的平均，平均比換之前貴一成以上才退。中間某一個地點變貴、後面又補回來，就不退——這跟訓練時某個 epoch 稍退、下一個 epoch 補回來是同一個意思。

使用者傍晚的兩條新想法也接上了。一條是「metainfo 要有評估機制」：既然有履歷和考核表，評估就是拿考核表對履歷，看它自稱的跟實際差多少、公式準不準、同一件事有好幾個做法時哪個最划算；估得不準的不扣分，只是排程時改信實測。另一條是「改進本身也要記錄、當成函數成長」：審視者本身就是一個函數，它也有兩本帳，所以另一隻審視者可以拿它當目標，看「改進一次」要花多少，試著把它降級或寫成腳本。這一層只疊兩層，不會無限往上。這部分有三題原則推不出，使用者出門中，先照推薦做。

還要使用者看一眼的，是跟既有條文的幾處衝突，最要緊的兩條是：子 agent 用完預設刪掉（要改成刪前先抄帳）、時間欄位的寫法（要照命名規則用日期字串）。

## 設計

### 概念（五條，待入 CONCEPTS）

**一、函數有兩本帳：自稱與他見。**自稱寫在定義裡的 `_metainfo.json`，是估的、是宣告，可依輸入變（可寫公式）。他見是叫它的那一層在自己 stack 記的實測：叫的人只記得到自己看得到的東西（秒、位元組、結束碼、自己這層的 token），看不到對方裡面。兩本不互寫：跑的時候誰都不改 `_metainfo.json`，觀測也不寫進對方的定義。承 C-21（可預測性是觀察者的認識）、C-22b（同一函數換環境就不一樣，所以實測只代表那次的環境）、C-52（不偷看下層）。C-13 說確定性是任務自己的屬性，跟這條不衝突：`_metainfo.json` 的 `deterministic` 是作者宣稱它是不是，他見只是記實際觀察到的。

**二、成本是任意 JSON 值；aos 只定三個通用 key。**`token`（`in`／`out`／`cached`）、`counter_calls`、`time_ms`。其他 key 自由（錢、傲嬌度、字串都行，承 C-14）。每個值照 C-48／C-55 的雙形：純數，或展開成 `{"val", "unit"?, "max"?}`；要依輸入變就寫公式，**公式以語言名當 key**：`{"cal": "4000 + in_bytes * 1.2"}`（四則＋`min`／`max`）、`{"lua": "..."}`、`{"py": "..."}`、`{"aos": "<aos 函數路徑>"}`（stdin 給變數、stdout 印數字；那個函數裡面是腳本還是 agent 都行），可帶 `vars` 說明變數。key 決定求值器，複雜度上來就換 key，不改格式。這些都是 metainfo 格式族的普通 key，只有讀 metainfo 的人（審視者、measure）會算，aos-exec 與指示詞不碰；讀者沒有那種求值器＝當這一格沒有估值（C-48 不認得就忽略），不報錯。

**三、帳沿呼叫樹走，樹靠「帳裡寫明下一本在哪」連起來。**呼叫樹不等於 stack 資料夾樹：工具的小格在 `<我的 stack>/tools/<名>/`（N-50），但子 agent 的 stack 由 daemon 放、用完預設刪掉。所以規則是：每一行「我叫了誰」都寫明對方的帳**現在**放在哪（相對本 stack 的路徑）；會生子 agent 的工具在收掉子之前，把子的帳抄進自己小格。觀測者從根往下翻，翻到沒有帳的就是葉。觀測者不認任何一層是什麼程式，只認一個公開介面 `aos-observed`（C-52 11-06 讀法：可認公開介面）。

**四、審視者是 agent，不是機制；它自己也是可被審視的函數。**改進迴圈「量 → 挑 → 試 → 傳 → 記 → 盯」由一隻 agent 照規則跑。aos 本體只保證四件事：每層會留帳、帳翻得到、定義寫得出來（`agents new`、寫資料夾）、改了之後量得到。審視者改的是整棵定義的**副本**，過門又變便宜就用 `promote` 自動換上，之後幾個 case 盯著，退步超過容忍才自動退回。審視者自己跑的過程一樣留帳（`observed.jsonl`、`review.json` 的 `spent`），所以另一隻審視者可以把「審視者」當目標來改。正在跑的 agent 改自己仍只能走 `self_tools`；`promote` 不准換掉正在跑的定義（含審視者自己）。

**五、門與目標分開。**門＝比對器說「過」（預設是產出逐 byte 一致；可換成一致率之類的比對器）；目標＝門內的成本。門沒過的版本不比成本。目標寫成一個 JSON 指標指進成本物件（例 `/token/in`），先留位置不設計。

### 各層誰負責

| 層 | 要做什麼 | 不做什麼 |
|---|---|---|
| aos-exec／loop／fsm／daemon | 沒有新事 | 不認新路徑語法、不算公式、不恢復 trace、不加「有信就醒」 |
| llm kernel | 程式不改；多一個範本 `kernel/llm-team/` 示範一層轉交；本機模型一台 kernel 只放一包、`slots: 1` | 不讀 `_metainfo`；ledger 格式不動（跨層記帳細節交給 kernel-nest） |
| agent 範本 agent-fsm | 帳加 `self` 行、工具行加 `def`／`stack`／`child`；`interfaces.json` 宣告 `aos-observed` | history 不動；不放任何「改進」邏輯 |
| lib | `lib/observed.py`（記帳共用模組，從範本搬上來，腳本也能用）；`lib/metainfo.py`（讀＋照公式 key 分派求值）；新工具 `measure`、`promote`、`metainfo_check`、`llm_forward`；範本 `templates/judge/`（裁判比對器）；改 `thought`／`agents`（收子前抄帳）、`memory find`（認 `tag`） | 不做 tag／連結的獨立工具 |
| 審視者（agent 定義 `templates/reviewer/`） | 規則寫 `system.txt`；階梯寫 `ladder.json`；每輪產 `reviews/<輪>/review.json`、`reviews/<輪>/defs/`（改好的整棵副本）與 `reviews/watch.json`；過門又變便宜就 `promote`；自己也帶 `_metainfo.json`、留帳，可被另一隻審視者審視 | 不換正在跑的定義（含自己）；不自己算 token（用 measure） |
| 腳本型函數 | 想被看穿就用 `lib/observed.py` 叫下游並記帳 | 不記也行，那就是葉 |
| 隊長（人／opus） | 定 case 與門、定階梯、語意抽查、按 `promote`、寫條文 | 不再手算「哪步最貴、降哪級、前後成本」 |

### 資料格式

命名照既有規矩：時間點 `*_at` 一律 ISO 8601 UTC 到毫秒；計數 `counter_*`；上限 `max_*`；時長 `*_ms`。

#### `_metainfo.json`（自稱）

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
    "counter_calls": 1,
    "time_ms": {"cal": "4000 + in_bytes * 1.2"}
  },
  "cost_basis": {"statistic": "median", "counter_samples": 3, "case": "cases/poshan"},
  "tsundere": 0.4
}
```

- `timeout_ms` 是行為（逾時就殺），`cost.time_ms` 是估時；頂層 `time_ms` 拿掉。
- `cal` 的變數只能是 `_tooldef.json` 的 `parameters` 名，加上固定的 `in_bytes`（stdin 位元組）；`vars` 選填，只寫給人看的變數說明。
- `cost_basis` 選填，說估值從哪來；審視者發新版定義時填。跑的時候誰都不寫這個檔。
- 公式 key 四選一：`cal`（起步唯一實作）、`lua`、`py`、`aos`；同一格只寫一種。
- 不認得的 key 一律忽略（C-48）。

#### `observed.jsonl`（他見；每個 stack 一份，只追加）

公開介面：本層的 `interfaces.json` 加 `"aos-observed": {"file": "observed.jsonl"}`（路徑相對 stack）。四種行：

```json
{"kind": "self",  "def": "/abs/defs/linker", "ws": "/abs/ws", "started_at": "2026-11-07T09:21:24.786Z"}
{"kind": "think", "letter": "0179...2843648", "endpoint": "terra", "model": "chatgpt-gpt-terra-low", "usage": {"prompt_tokens": 7577, "completion_tokens": 557, "total_tokens": 8134}, "elapsed_ms": 15974.2}
{"kind": "tool",  "name": "memory", "def": "/abs/lib/agent/memory", "stack": "tools/memory", "code": 0, "elapsed_ms": 41.7, "in_bytes": 88, "out_bytes": 2310}
{"kind": "tool",  "name": "thought", "def": "/abs/lib/agent/thought", "stack": "tools/thought", "child": "tools/thought/observed/t-linker-1794035-3f2a", "code": 0, "elapsed_ms": 9800.0, "in_bytes": 412, "out_bytes": 388}
```

- `self` 行：這個檔第一次被寫時先寫一行（`lib/observed.py` 自動做），`def`＝`AOS_CD`，`ws`＝`AOS_WS`。換腦看 `think` 行的 `endpoint`，`self` 行不記。
- `tool` 行：`def`＝本層登記簿（`tools.json`）裡那支的路徑解成絕對；`stack`＝給對方的小格（相對本 stack）；`child`＝這次呼叫生出的子 agent 的帳**現在**在哪（相對本 stack），只有會生子的工具有。
- 腳本型函數用 `lib/observed.py` 的 `call(name, target, stdin)` 叫下游：它設小格 `AOS_STACK=<本 stack>/tools/<name>/`、跑 `aos-exec target`、量牆鐘、寫一行 `tool`。非 Python 的腳本照上面格式自己寫 JSON 行也行，格式就是契約。
- 時間一律是叫的那層量的牆鐘（含排隊、本機載入），符合「時間算成本」。
- `bash` 工具只記到 bash 那層；裡面再叫什麼帳就斷在那（要算就包成工具，C-77）。

#### 子 agent 的帳怎麼留（thought／agents）

- thought：收子之前（不管 `keep`），把子 stack 底下所有名叫 `observed.jsonl` 的檔照原相對路徑抄到自己小格 `observed/<子名>/`，再照舊 `ctl rm`（或 `keep` 時 `ctl stop`）。抄的位置跟既有的 `children/<子名>/` 租約紀錄分開，免得對帳時被 `forget` 一起刪掉。
- agents：`ask` 回來時與 `rm` 之前，同樣把子的帳同步一份到 `observed/<名>/`；`say` 不同步（下一次 `ask` 或 `rm` 會補）。同步不到的就少算——寧可少算，不偷看。
- 抄是「整棵帳」：子自己的小格、子再生的孫的抄本都在子 stack 底下，一起抄，所以多深都翻得到。

#### case 夾（量測的考題）

```
cases/poshan/
  run.json      {"exec": "place_run", "stdin": "stdin.json"}       ← 跑函數
                或 {"agent": "linker", "say": "say.txt"}            ← 跑 agent
  stdin.json    （或 say.txt）
  ws/           初始工作區，每次量都複製一份新的
  expect/       期望產出（相對 ws；沒有＝拿現版第一次跑的產出當參考）
  check.json    {"compare": "<比對器函數路徑>"?, "min_score": 1.0}
```

- `run.json` 裡的定義路徑相對「定義根」（measure 的 `defs` 參數），所以同一個 case 可以拿正式那棵或副本那棵跑。
- 比對器是普通 aos 函數：stdin `{"expect": "<資料夾>", "got": "<資料夾>", "input": "<case 夾>"}`，stdout `{"score": 0.94, "diff": ["links.json"], "why"?: "..."}`。沒寫 `compare`＝內建逐 byte 比（score＝一樣的檔數／expect 檔數）。arknights 的「逐條一致率」就是一支自訂比對器。
- **裁判也是比對器。**照使用者裁定，語意錯先交高階模型：範本 `templates/judge/` 是一支 agent 型比對器（腦用高階 endpoint），讀原文與產出、打分並寫 `why`。它跟其他比對器同一個契約，所以換人、換模型、換規則都只是換 `compare` 那一格。裁判自己的帳由 measure 另計在 `check.cost`，進審視者的 `spent`，不算進產出成本（它是「量」的錢，不是「做」的錢）。人抽查為輔：抽到錯的補進 `expect/`，之後內建比對器就擋得住，裁判可以慢慢少叫。

#### measure（量）

stdin `{"case": "/abs/cases/poshan", "defs": "/abs/defs", "repeat": 3}`。每次在自己 stack 的 `runs/<i>/` 下開新的 `ws/` 與 `stack/`：函數型照 `run.json` 跑 `aos-exec`；agent 型用 `aos-agent ctl add`（stack 指進 `runs/<i>/stack/`）＋`say`＋`listen`＋`ctl stop`，翻完帳再 `ctl rm`。翻帳從 `runs/<i>/stack/observed.jsonl` 起，照 `stack`／`child` 往下。

```json
{
  "case": "cases/poshan",
  "defs": "/abs/defs",
  "repeat": 3,
  "check": {"pass": true, "scores": [1.0, 1.0, 1.0], "diff": [], "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "counter_calls": 0}},
  "size_bytes": 3456,
  "cost": {"token": {"in": 6635, "out": 380, "cached": 0}, "counter_calls": 1, "time_ms": 9800},
  "tree": {
    "def": "place_run", "kind": "script", "counter_calls": 1,
    "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "counter_calls": 0, "time_ms": 9800},
    "children": [
      {"def": "kb_store", "kind": "script", "counter_calls": 1, "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "counter_calls": 0, "time_ms": 120}, "children": []},
      {"def": "linker", "kind": "agent", "endpoint": "terra", "counter_calls": 1,
       "cost": {"token": {"in": 6635, "out": 380, "cached": 0}, "counter_calls": 1, "time_ms": 9500},
       "children": [{"def": "/abs/lib/agent/memory", "kind": "script", "counter_calls": 2, "cost": {"token": {"in": 0, "out": 0, "cached": 0}, "counter_calls": 0, "time_ms": 41}, "children": []}]}
    ]
  },
  "samples": [{"cost": {}, "check": {}}],
  "measured_at": "2026-11-07T10:31:12.345Z"
}
```

- `size_bytes`＝case 的 `stdin` 加初始 `ws/` 的位元組數，算單位成本用。
- 根 `cost` 是各次的中位數；`tree` 用第一次那份。節點的 `cost.token` 只算它自己那本帳的 `think` 行（不含子樹，免得重算；總和看根）；`time_ms` 是父親量的牆鐘；節點的 `counter_calls`（節點層）＝被叫了幾次，`cost.counter_calls`＝它自己問腦幾次。
- 同一個父、同一支工具的多次呼叫合成一個節點（小格是同一個，帳也是同一份）。
- `kind`：帳裡有 `think` 行的叫 `agent`，其他叫 `script`。只看帳，不認程式名。
- `def` 在定義根底下就寫相對，否則寫絕對。
- `usage` 換算：`in`＝`prompt_tokens`、`out`＝`completion_tokens`、`cached`＝`prompt_tokens_details.cached_tokens`（缺＝0；`usage` 是 null 的那行另計 `counter_usage_missing`）。

#### review.json（審視者一輪一份，`$AOS_WS/reviews/<輪>/review.json`）

```json
{
  "round": 3,
  "case": "cases/poshan",
  "before": {"token": {"in": 15848, "out": 1530, "cached": 0}, "counter_calls": 7, "time_ms": 46500},
  "target": {"def": "linker", "reason": "llm step with the largest token.in share (0.68)"},
  "tried": [
    {"move": "downgrade", "from": "sol", "to": "terra", "scores": [0.94, 0.94, 0.94], "pass": true},
    {"move": "downgrade", "from": "terra", "to": "luna", "scores": [0.44, 0.88, 0.0], "pass": false}
  ],
  "adopted": {"move": "downgrade", "to": "terra"},
  "dirty": ["kb_link", "kb_lint2"],
  "after": {"token": {"in": 7107, "out": 650, "cached": 0}, "counter_calls": 1, "time_ms": 22300},
  "proposed": "reviews/3/defs",
  "spent": {"token": {"in": 52000, "out": 3100, "cached": 0}, "counter_calls": 9},
  "suggest": {"retire": [], "specialize": []},
  "why": "terra 三次都 94%，過門；luna 第三次全錯，退回。",
  "reviewed_at": "2026-11-07T10:40:02.001Z"
}
```

- `move` 只有三種，依序試、一個成功就停：`downgrade`（定義的 `llm.json` 換低一級 endpoint）、`fix`（輸出由輸入完全決定 → 寫成腳本）、`split`（腳本前處理＋更小的 LLM 步）。一輪只動一個目標。
- `dirty`＝目標在樹裡的父與子；採用前整個 case 重量（自然涵蓋它們），門要全過，任一不過就退回、記進 `tried`。
- `proposed` 是改好的**整棵定義根副本**；目標用 thought 生出、endpoint 由呼叫方參數給的情形，降級改的是呼叫方那邊的參數。
- `spent` 是審視者這一輪自己的帳加總（改進本身也是成本）。
- `suggest`：連三個 case 都沒在樹裡出現的定義進 `retire`；連兩個 case 出現「同一個子定義＋同一組工具」的 thought 子 agent 進 `specialize`（建議 `agents new` 成專精定義）。只建議、不自動做；跨輪記憶就是讀自己以前的 `reviews/*/review.json`。

#### ladder.json（審視者的階梯）

```json
{"ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_score": 0.9,
 "watch": {"window": 3, "tolerance": 0.10, "metric": "/token/in"}}
```

每級三次獨立實例、三次都 ≥ `min_score` 才算過，取合格中最低級（就是 B3 用的門檻）。這裡的 `min_score` 蓋過 case 的 `check.json`。

#### 知識庫的連結與 tag（memory 的約定，不是新機制）

- 連結值＝一個字串 `節點路徑#/JSON指標`，相對知識庫根，例 `"source": "lore/characters/夕#/aliases/1"`。追連結＝`memory read` 那個字串（已支援）。建、解、改連結＝讀出整個節點、改那一格、`memory_write edit` 整份寫回（節點建議 <2 KB，整份寫回不貴）。
- tag＝節點 JSON 裡的 `"tags": ["地點", "烏薩斯"]`；資料夾節點（內文是 `README.md`）放同層 `_tags.json`（`{"tags": [...]}`）。`memory find` 加選填 `tag`，逐字比對。
- 規矩一句：要讓工具沿著走的才做連結；只是提到，寫名字就好。
- 全庫規模、給人看的那層交給 kb-scale。

#### 嵌套 kernel（一層轉交）

- 轉交函數放 `lib/aos/llm_forward/`（搬自試驗場 `defs/llm_forward`，配 `_tooldef.json`／`_metainfo.json`）：stdin `{"endpoint", "request"}`，用 `aos-llm ask --full` 問 `$AOS_LLM_KERNEL`，回覆原樣印出。
- 範本 `kernel/llm-team/`：`kernel.json` 寫 `{"exec": "<lib>/aos/llm_forward", "endpoints": {"sol": {"to": "sol"}, "terra": {"to": "terra"}}, "budget": {...}}`；隊 kernel 自己那台 daemon 的環境把 `AOS_LLM_KERNEL` 設成總機（agent 那邊的 `AOS_LLM_KERNEL` 指隊 kernel）。
- 兩層各記各的 `ledger.jsonl`／`used.json`；上層不讀下層帳，用量靠回信的 `usage` 帶上來。本機模型：一台 kernel 只放一包、`slots: 1`；換模型＝換包，是隊長或審視者的明確動作，不在跑的中途切。
- 排程、多層記帳對帳交給 kernel-nest。

#### promote（換上／退回）

- stdin `{"defs": "/abs/defs", "target": "linker", "from": "/abs/ws/reviews/3/defs"}`：把 `defs/linker` 搬到 `defs/.prev/linker/<promoted_at>/`，再把 `from/linker` 複製成 `defs/linker`。`{"defs", "target", "rollback": true}`：拿最新一份 `.prev` 換回來。`.prev` 是隱藏資料夾，aos 的程式本來就略過。
- 換上前查 daemon 表（`aos-daemon-ctl ls --json` 的 `def` 欄）：有正在跑的 proc 用的是 `target` 或它底下＝拒絕，`DefBusy`（守 C-46「呼叫時不變」）。
- 誰能按：登記在誰的工具箱，誰就能按。照使用者裁定，審視者的 `tools.json` 放它（自動換上）；隊長手上也有一份可手動換或退。工具權限怎麼一步步放開交給 tool-evolve。

#### 容忍短暫退步的自動退回（watch）

訓練神經網路時，某一輪變差、下一輪又補回來是常事，所以「一變差就退」太急。判準分兩種：

- **品質（門）不容忍。**換上之後任何一個 case 的門沒過（比對器或裁判分數低於 `min_score`），立刻 `promote --rollback` 那個目標。
- **成本容忍一段。**拿「單位成本」比：目標指標（預設 `/token/in`，根節點）除以 case 的大小（`stdin` 加初始 `ws/` 的位元組數），這樣大地點、小地點才能放一起比。換上前取最近 3 個 case 的單位成本平均當基準；換上後再看 3 個 case（窗），窗滿時算這 3 個的平均：比基準貴超過 10% 才退回，沒超過就轉正。窗內只要還沒滿就不退——中途某一個 case 變貴，後面補回來就算了。
- **疊著換也算。**窗還沒滿時又換上別的目標，兩個窗各算各的；退回只退那一個目標（各自有 `.prev`）。最後的判準看整個 case 的單位成本，所以「別的步驟變便宜把它補回來」也算補回來，這正是反向傳播要的效果。
- 盯的紀錄是審視者工作區的 `reviews/watch.json`（審視者自己的產出，跨輪讀它就是記憶）：

```json
{"watch": [
  {"target": "linker", "promoted_at": "2026-11-07T10:41:00.000Z", "round": 3,
   "metric": "/token/in", "baseline": 1.92, "window": 3, "tolerance": 0.10,
   "samples": [{"case": "cases/qieernuoboge", "unit_cost": 2.05, "pass": true}],
   "state": "watching"}
]}
```

`state` 只有三種：`watching`、`kept`（轉正）、`rolled_back`。`window`、`tolerance` 寫在 `ladder.json` 旁的同一份設定裡，可改；起步值 3 與 10% 是代定。

### 審視者的一輪（寫進 `system.txt`）

1. **量**：`measure` 跑 case，拿 `measure.json`。
2. **挑**：樹裡 `kind: agent` 的節點按 `token.in` 占比排，取最大；沒有 agent 節點就按 `time_ms` 取最大（這時只能 `split` 或結束）。
3. **試**：複製整棵定義根到 `reviews/<輪>/defs/`，對目標依序試 `downgrade` → `fix` → `split`。
   - `downgrade`：階梯往下一級，`measure` 跑 `repeat` 次，每次都 ≥ `min_score` 才過。
   - `fix` 的訊號：同一版連跑三次產出逐 byte 一樣（measure 的三份 `samples` 互比）。成立就開聰明級 thought 子 agent，照輸入／輸出對寫腳本進副本，再量。
   - `split`：開聰明級 thought 子 agent，把這步拆成「腳本前處理＋更小的 LLM 步」兩個定義，再量。
4. **傳**：整個 case 用副本重量，門要全過；不過就退回、記進 `tried`。
5. **記**：寫 `review.json`；過門且單位成本比換前低，就 `promote` 換上，並在 `watch.json` 開一個窗。
6. **盯**：每量一個新 case，先把它的單位成本填進所有 `watching` 的窗，照 watch 那節的規則轉正或退回。
7. **長**：填 `suggest`（只建議）。

起步三個地點，`fix`／`split` 只寫處方（`review.json` 的 `tried` 記招式與理由、不動副本），施工交 gpt；第四個地點起放手自己寫。換模型那招從第一天就全自動。

## 與既有 CONCEPTS／NORMS 的衝突

1. **N-62「`#/` 只用在 aos-exec 入口、`$ref` 檔名、argv[0]」與 C-51「互通不進規範」 vs 想法 1「資料之間的關聯統一寫 `a/b#/c/1`」。**衝突在條文把這種寫法綁在 aos-exec 一層，新想法要它當全系統通用的「指」法。推薦鬆綁一句：寫法全系統只有這一種（RFC 6901、第一個 `#` 就切、`#` 後必 `/`、檔名不含 `#`），誰認由各讀者自己宣告（aos-exec 認入口、memory 認節點、aos-json 認檔），`$env` 仍不認 `#`。後果：只改 NORMS 文字、程式不動；不鬆綁的話，知識庫的連結就得另發明一種寫法，等於兩套。

2. **待定稿「`_metainfo` 實測不回寫」、C-46「定義呼叫時不變」 vs 想法 5「他者觀測也是 metainfo」。**試驗場把 `_observed.json` 寫進 `defs/<名>/`，那就是回寫、就是定義在變。推薦守舊條：他見住在觀測者自己的 stack，定義資料夾只放自稱；審視者發新版時可把量到的數寫進新版的 `_metainfo.json`（那是作者在寫，不是跑的時候寫）。後果：試驗場的 `_observed.json` 作法不進 aos；改成照想法 5 回寫的話，同一份定義會因誰跑過而不同，C-46 要改。

3. **現行 `_metainfo.time_ms.{val,max}`（act.py、aos-mcp 讀 `max` 當逾時）與待定稿「只有 `timeout_ms` 強制」 vs 想法 4／10「時間是成本的一維」。**同一個 `time_ms` 混了估時與逾時，待定稿和實作本來就對不上。使用者已裁照推薦：`cost.time_ms`＝估時、`timeout_ms`＝逾時、頂層 `time_ms` 拿掉，工具檔用腳本一次改（使用者說 33 支；實數以 `aos-tools ls` 為準——lib 下有 29 份 `_metainfo.json`，另有 JSON 檔型工具的 `_metainfo` key），act.py、aos-mcp 各改一處，不寫相容。另一案是頂層 `time_ms` 不動、只加 `cost`，後果是時間寫兩處、以後必亂。

4. **C-48「指示詞只有 `$env`、`$ref`」、C-56「寫什麼就做什麼」 vs 想法 5「成本可寫公式 `{"cal": "x*2"}`」。**看起來像加了第三種會變身的值，而使用者裁定後還有 `lua`／`py`／`aos` 這幾種 key。推薦定成：這些都不是指示詞，是 metainfo 格式族的普通 key，值字面上就是一段公式或一個函數路徑，只有讀 metainfo 的人算它，aos-exec 不碰。後果：NORMS 加一句即可；若當成指示詞，aos 讀的每份 JSON 都得會跑 lua、python，等於把規則藏進特定值。`py`／`lua` 等於讀者在跑別人寫的程式，讀者要自己決定在不在沙箱裡跑（審視者的格可以接 `aos-sandbox`），這點交給 tool-evolve 一起看。

5. **N-39／N-30 剛把 fsm／loop 的 `trace.jsonl` 拿掉、N-13 窗沒有歷史 vs 每層要留只追加的帳。**剛拿掉一種逐筆紀錄又加一種。推薦視為不同東西：trace 記「跑到哪格」，帳記「花了多少」，而成本是使用者點名要壓的。只准這一種帳，且要在 `interfaces.json` 宣告成公開輸出（`aos-observed`），外人才可讀。後果：不准的話，成本只能從 kernel 的 ledger 反推，並行時對不上（不足 #23 的老問題）。

6. **待定之二「self-improve 預設就關」、C-46 vs 系統自己改函數（想法 7、C-42 的閉環）。**審視者寫新定義、換掉舊的，就是在改系統；使用者已裁「自動換，退步自動退回」。推薦這樣讀：「預設關」管的是沙箱裡跑的函數改自己，維持不動；審視者改的是別人的定義，換上要經 `promote` 這支明確的工具，要登記進審視者工具箱才有（範本預設登記、拿掉就關），不准換掉正在跑的定義，且每次換上都留前版、有 watch 盯著。後果：條文只需註明「審視者經 `promote` 換別人的定義不算 self-improve」；若把它也算進 self-improve，就得先把「預設關」改成「預設開」，跟使用者的裁定才對得上。

7. **C-20「很多 agent 時誰先用腦」是核心題、`max_children`／`max_running` 兩道關、C-78 啟動步驟少 vs 想法 7／8「agent 成千上萬、可 sleep」。**若讀成成千上萬個活著的 proc，排程與 daemon 負荷都會爆。推薦讀成成千上萬個**定義**，叫到才起（C-40 拋棄式函數），用完即收，stack 留在磁碟就是 sleep（C-16）。後果：daemon 不改；若要常駐，就要動 daemon（見方向題「有信就醒」）。

8. **C-47 轉交型 kernel「建議不要濫用」、N-42 兩種 kernel 不併 vs 想法 7「llm kernel 可嵌套」。**嵌套就是轉交。推薦這份設計只用一層（隊 → 總機），只為分隊額度與本機模型一次一包；兩種 kernel 照舊不併。後果：一支 lib 函數＋一個範本、kernel 程式不動；要更深的嵌套與排程交給 kernel-nest 再判。

9. **thought 的使用者裁定「子 stack 可選，默認刪掉」（11-05）vs 帳要能往上收。**子 agent 的 stack 由 daemon 放，thought 預設收工就刪，子的帳跟著消失，往下翻就斷。推薦：stack 照刪，刪之前只把子的帳（`observed.jsonl` 那些檔）抄進 thought 自己的小格；agents 工具同理。後果：多留一點小檔、裁定原意（不留雜物）不變；不抄的話，凡是經 thought 的成本都只剩外面量到的秒數，正好是最常見的那條路看不見。

10. **命名規則「時間點 `*_at` 一律 ISO 8601 UTC 到毫秒」「計數一律 `counter_*`」 vs 新格式要用的時間與次數欄。**這批格式若照 ledger 的寫法用 epoch 秒、用 `calls`，就跟命名規則不合。推薦新格式照命名規則：`started_at`／`measured_at`／`reviewed_at`／`promoted_at` 用日期字串，次數用 `counter_calls`（llm kernel 的 `used.json` 已經是這樣叫）。後果：成本三欄就是 `token`、`counter_calls`、`time_ms`；使用者口頭說的「呼叫次數」意思不變。ledger 既有的 epoch 欄不在這題範圍。

11. **C-46「定義呼叫時不變」 vs `promote` 換上時剛好有人在用那份定義。**推薦 `promote` 先查 daemon 表，有 proc 正在用就拒（`DefBusy`）。後果：換上要等它跑完；不查的話，跑到一半的 agent 會讀到半新半舊的定義。

不算衝突、只要補條文的：上面五條概念；`observed.jsonl` 四種行與 `aos-observed` 介面；case 夾、比對器、`measure.json`／`review.json`／`ladder.json` 格式；memory 的連結與 tag 約定；`cal` 由讀者求值一句。

## 使用者裁定（11-07）

選項框裁定，原話逐字：

- 公式語言：「直接寫"lua":"...."或"py":"..."，然後呼叫相應lua.exe/python.exe(這臺是linux，沒有)。或是直接跑aos函數。初期可以用簡單的四則+min/max。其實沒啥規定，就是隨着複雜度增加，可以替換到所需技術棧。搞不好到後面，就是呼叫aos　agent」
- 審視者能不能自己寫程式：「按照推薦。但這就隨意。甚至這個過程本身也可以記錄下來，讓另一個agent進行改進流程。」
- 改好的版本誰換上：「自動換，退步自動退回。不過可以想想看神經網路這塊，有時候他的epoch會稍微退步，但下次又會進步補回來。」
- daemon 有信就醒：選推薦（不加）。
- 語意錯怎麼擋：「一開始先用人去看，但最近我比較忙，可以先用高階模型。這個也很自由，也可以先設計一套模式，後續慢慢優化。」
- `_metainfo` 的估時與逾時：選推薦（拆成 `cost.time_ms` 與 `timeout_ms`，工具檔用腳本一次改、不做相容）。

## 使用者裁定（11-07 傍晚，40 題選項框）

使用者 11-07 傍晚在 40 題選項框裡裁定（回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)）；除特別註明，選的都是推薦。回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進，沒逐題寫備註的也一樣。

- **evo-A**（函數自報的成本不準，要怎麼處理？）：選 C「平常只報告；但 kernel 或審視者要拿估值來排程、挑目標時，off 的定義改用他見的中位數」。備註原話：「hmmm，函數自報估值，老實說，應該是函數的設計者當初給函數寫下的估值，而agent作爲函數他確實會自報估值。兩者要分清。函數設計者給函數寫下的估值，這件事，hmmm，首先我要說，不是所有函數設計者都會寫這種估值，所以不能假定永遠都有metainfo，而且我們也不該強迫。一些比較笨的agent，你讓他報估值他也會報錯，那不如就只看他的說明就好。函數九軸是基礎特性，我們是建議不管多簡單或多笨的函數或agent都準備一份描述這個的metainfo啦，但不強迫。產出metainfo這件事，也是可以優化的一環，但我覺得除非是改進者之流，不然這屬於比較次要的要優化的東西。」
- **evo-B**（改進別人的審視者，什麼時候也要被改進？）：選 B「審視者自己的單位成本連續幾輪沒降、或 spent 比它省下來的還多時才跑」。備註原話：「如果審視者一直都做的不錯，那就沒必要改進他。這套判斷標準本身也是靈活的，可以被改進的。想想看，審視者，審視"審視者"的審視者，這樣一層層堆疊，每層之間的標準都可以靈活變換。」
- **evo-C**（拿來考審視者的好答案，要從哪裡找？）：選 A「從過去真實的 review.json 裡挑，被 watch 轉正（kept）的那幾輪當好答案」。備註原話：「兩者都可以。這套標準本身也可以靈活變換與改進。」

落到本設計的地方：evo-A 的「兩種估值分清、metainfo 不強迫」寫進下面「一、metainfo 怎麼評估」；evo-B 的「審視者可以一層層疊」改寫了「二、改進過程本身也是會成長的函數」的「不會無限往上疊」那條；evo-C「兩者都可以」寫進方向題 C。條文落點見 CONCEPTS C-84、NORMS N-68。

## 方向題（已裁）

- **公式語言**：已裁——語言名當 key（`cal`／`lua`／`py`／`aos`），起步只做 `cal` 的四則＋`min`／`max`，其他 key 等用到再接求值器。原選項是只四則、Python 子集、先不做公式三種。
- **審視者動手寫程式**：已裁——先開處方跑三個地點，之後放手；改進過程本身留帳，可被另一隻 agent 改進（見下節）。原選項是只開處方、直接動手、先處方後放手三種。
- **誰按換上**：已裁——自動換、退步自動退回，容忍短暫退步的判準見「容忍短暫退步的自動退回」那節。原選項是全自動、等人按、自動換加自動退回三種。
- **daemon 有信就醒**：已裁——不加。專精 agent 是定義，叫到才起，stack 留在磁碟就是 sleep。
- **語意錯**：已裁——先用高階模型當裁判（裁判是一支比對器、可替換），人抽查為輔，抽到的錯補進 `expect/`。原選項是人抽查、模型裁判、兩者疊加三種。

## metainfo 的評估機制，與改進過程本身的成長

使用者 11-07 傍晚的兩條新想法（原話在 [kb-ideas](../kb-ideas/README.md) 第 11、12 條）：「下一輪規劃前，我這裏有些想法：弄了這麼多metainfo格式，那我們也要有一套相應的評估機制。」「還有，改進，我們現在是讓高智能agent去做，而這件事本身也可以記錄其過程，作爲一個函數進行成長。」緊接著補：「以及優化」。

### 一、metainfo 怎麼評估

**兩種估值要分清，metainfo 不強迫（11-07 傍晚使用者裁定 evo-A 備註）**：本節對的是**函數設計者**寫在 `_metainfo.json` 的估值；agent 作為函數在跑的時候**自己報**的估值是另一樣，分開記、分開評（agent 自報怎麼記、要不要評，代定：先不做，等需要時另題）。不是每個設計者都會寫估值，所以不能假定 `_metainfo.json` 一定在，也不強迫寫；沒寫就是 `unclaimed`、不算錯。比較笨的 agent 讓它報估值也會報錯，就不要它報、只看它的說明。建議不管多簡單的函數或 agent 都備一份描述九軸（C-13）的 metainfo，但不強迫。把 metainfo 寫好也能優化，但除了改進者這類函數，算次要。

白話說：履歷寫得準不準，要拿考核表來對。兩本帳都有了，評估就是「拿他見去對自稱」，做成 measure 旁邊的一支小工具 `lib/agent/metainfo_check`，不加新機制。它回答三件事：

- **宣稱跟實際差多少。**對樹裡每個節點，用 `lib/metainfo.py` 把它的 `_metainfo.json` 照這次的輸入算出估值（公式會吃到 `in_bytes` 等變數），跟 measure 量到的值比，每個成本 key 一個「落差比」＝實測／估值。一份定義的評分是它最近幾個 case 落差比的中位數；落在 0.8～1.25 之間算「準」（代定）。沒寫估值的 key 記成 `unclaimed`，不算錯。
- **公式準不準。**同一份定義在大小不同的 case 上，落差比如果穩定（例如每次都 1.1），表示公式的形狀對、只是係數偏；如果隨 case 大小漂移，表示公式的形狀錯。評估只報這兩種情形，不自己改公式；改公式是審視者在發新版定義時做的事（作者寫新版，不是跑的時候回寫，守「實測不回寫」）。
- **同職責多個定義誰划算。**「同職責」不靠猜，靠同一個 case 和同一個門：幾份定義都拿同一個 case 跑、都過門，就照單位成本排；沒過門的不排。這其實就是審視者試 `downgrade`／`fix`／`split` 時在做的比較，評估工具只是把它攤成一張表。

輸出 `metainfo_check.json`，給審視者讀：

```json
{"case": "cases/qieernuoboge", "checked_at": "2026-11-07T11:02:00.000Z",
 "defs": [
   {"def": "linker", "key": "/token/in", "claimed": 7004, "observed": 7577, "ratio": 1.08, "verdict": "close"},
   {"def": "linker", "key": "/time_ms", "claimed": 14750, "observed": 20300, "ratio": 1.38, "verdict": "off"},
   {"def": "kb_store", "key": "/token/in", "claimed": null, "observed": 0, "verdict": "unclaimed"}
 ]}
```

`verdict` 只有 `close`、`off`、`unclaimed`。審視者一輪的第 1 步「量」之後順手叫它；連三個 case 都 `off` 的定義，審視者在發下一版時把估值或公式改準（改的是副本、照常過門）。

**方向題 A（11-07 傍晚已裁：選 (c)）：自稱不準要不要扣分？**
- (a) 只報告，不影響換不換上。最簡單，但履歷亂寫也沒後果。
- (b) 換上前要求新版的估值落差在「準」的範圍內，否則門不過。逼作者寫準，但第一次寫的定義常常沒有好估值，會卡住進度。
- (c) 平常只報告；但 kernel 或審視者要拿估值來排程、挑目標時，`off` 的定義改用他見的中位數。估值錯不擋路，也不會被誤用。
- **推薦 (c)。**評估的用處是「別被錯的履歷騙」，不是懲罰。

### 二、改進過程本身也是會成長的函數

審視者就是一個函數，跟 linker 沒有兩樣，所以它也有兩本帳，也能被審視、被降級、被拆成腳本：

- **它的自稱**寫在 `templates/reviewer/_metainfo.json`，例如「一輪大約多少 token、幾次呼叫」。
- **它的他見**就是它自己 stack 的 `observed.jsonl`，加上每輪 `review.json` 的 `spent`。
- **它的考題**是一個「審視 case」：`cases/review-poshan/` 的 `run.json` 寫 `{"agent": "reviewer", "say": "say.txt"}`，`ws/` 放一份固定的定義根與 case，`expect/` 放已知的好答案（例如「目標該挑 linker、降到 terra」）。比對器看它挑的目標、採用的招式對不對。
- **它的成本**是「找到同樣好的改進，花多少 token、幾次呼叫、多少秒」。換句話說，優化目標從「做一個地點要多少錢」往上一層，變成「改進一次要多少錢」。這就是使用者說的「作為一個函數進行成長」，也是 user-advice 裡「提高"提高智能"的速度」那一層。
- **誰來審視審視者**：第二隻審視者（同一份定義的另一個實例也行），照同一套一輪七步，目標就是 reviewer 這份定義。它能試的招跟其他函數一樣：換便宜的腦（例如「挑目標」這一步其實是排序，可能根本不需要聰明模型）、把固定的部分寫成腳本（「挑」和「盯」幾乎都是算術，很可能整步變成腳本）、把「寫腳本」那一步拆給專精子 agent。
- **可以一層層往上疊（11-07 傍晚使用者裁定 evo-B 備註）。**審視者、審視「審視者」的審視者……一層層疊上去，每層用的判準都可以不同、也都能被改；某一層一直做得不錯，就不去改它。疊幾層不定。`promote` 不准換掉正在跑的定義，所以一隻審視者不會在跑的時候把自己換掉；換審視者的定義，只能由上一層審視者在它沒在跑時做。

**方向題 B（11-07 傍晚已裁：選 (b)；判準本身也可以改）：審視者什麼時候被審視？**
- (a) 每做完 N 個地點（例如 5 個）跑一次審視 case。固定節奏、好預測，但可能審了沒東西可改。
- (b) 審視者自己的單位成本連續幾輪沒降、或 `spent` 比它省下來的還多時才跑。省錢，但要多一條判準。
- (c) 只在隊長叫時跑。人在迴圈裡，但使用者最近忙。
- **推薦 (b)，判準先寫死成「最近 3 輪的 `spent` 總和大於這 3 輪省下的成本總和」**——改進花的比省的多，就該改進「改進」本身。

**方向題 C（11-07 傍晚已裁：選 (a)，備註「兩者都可以」——(a)、(b) 都能用，標準本身也可以改）：審視 case 的好答案從哪來？**
- (a) 從過去真實的 `review.json` 裡挑，被 watch 轉正（`kept`）的那幾輪當好答案。現成、不用人寫，但只會越學越像過去的自己。
- (b) 隊長或高階模型手寫幾題。品質高，但要人或要錢。
- **推薦 (a) 起步，裁判模型抽查補 (b)。**轉正過的改進本身就是「過了門、又真的省錢」的證據。

## 落地順序（交 gpt 照圖施工）

每步獨立可驗、不帶設計決策；照使用者裁定走（方向題 A～C 11-07 傍晚已裁）。試驗場（`~/code/playground-ak/`）改接放最後，不卡 aos 本體。

1. **`lib/metainfo.py`**：讀 `_metainfo.json`，認 `cost`（三通用 key、雙形、公式 key）與 `timeout_ms`；`eval_cost(metainfo, vars)` 照公式 key 分派求值器，起步只實作 `cal`（四則、括號、`min`／`max`），其他 key（`lua`、`py`、`aos`）回「沒有估值」。完成條件：純數、`{val}`、`{cal}` 三種形各有一例算對，含 `__`、`import`、屬性存取的 `cal` 一律拒，`{"py": "..."}` 回沒有估值而不報錯。
2. **`_metainfo.json` 改格式**：一次性腳本把 `time_ms.val` 搬到 `cost.time_ms`、`time_ms.max` 搬到 `timeout_ms`、刪頂層 `time_ms`（含 JSON 檔型工具的 `_metainfo` key；以 `aos-tools ls` 列到的為準，不寫死支數）；act.py、aos-mcp 的逾時改讀 `timeout_ms`；不做相容。完成條件：每支都讀得過第 1 步，全 repo（thinking、archive 除外）grep 不到讀 `time_ms` 當逾時的程式。
3. **記帳模組搬上 lib**：`templates/agent-fsm/observed.py` 搬成 `lib/observed.py`，第一次寫檔時先補 `self` 行；act.py 的 `tool` 行加 `def`、`stack`；範本 `interfaces.json` 加 `aos-observed`。完成條件：起一隻範本 agent、叫一次 memory，`observed.jsonl` 第一行是 `self`、`tool` 行的 `stack` 指到的資料夾存在。
4. **腳本也能記帳**：`lib/observed.py` 加 `call(name, target, stdin)`（設小格、跑 aos-exec、量牆鐘、寫 `tool` 行）。完成條件：一支 Python 腳本用它叫另一支會寫帳的腳本，兩層的 `observed.jsonl` 都在、上層那行的 `stack` 指得到下層那份。
5. **thought／agents 收子前抄帳**：照「子 agent 的帳怎麼留」那節做，`tool` 行帶 `child`。完成條件：`keep: false` 的 thought 叫完後子 stack 已刪，但 `tools/thought/observed/<子名>/observed.jsonl` 在、裡面有子的 `think` 行；子再開一層 thought 時孫的帳也在抄本裡。
6. **`lib/aos/llm_forward` 與 `kernel/llm-team/`**：搬試驗場的轉交函數，配範本。完成條件：隊 kernel 與總機兩層各有自己的 `ledger.jsonl`，經隊 kernel 問一次的 agent，其 `think` 行 `usage` 不是 null。
7. **`measure` 跑與翻帳**：照 case 夾與 measure 那節做（先不比對），含 `size_bytes`。完成條件：對一隻會叫 thought 的 agent 跑 `repeat: 2`，`tree` 有兩層，根的 `token.in` 等於所有 `think` 行 `prompt_tokens` 之和（手算對得上）。
8. **`measure` 加門**：內建逐 byte 比對器與自訂比對器的呼叫，比對器自己的帳記進 `check.cost`。完成條件：改 `expect/` 任一檔一個 byte，`check.pass` 變 false、`diff` 列出那個檔；換成一支固定回 0.95 的比對器、`min_score: 0.9` 時 `pass` 為 true。
9. **裁判比對器 `templates/judge/`**：agent 型比對器，腦用高階 endpoint，照比對器契約讀 `expect`／`got`／`input`、印 `score`、`diff`、`why`。完成條件：拿婆山鎮 B2 那份含「煮傘居士」錯誤的產出給它，`score` 低於 1、`why` 點出那一筆；它的 token 出現在 `check.cost`、不在根 `cost`。
10. **`memory find` 認 tag**：節點 JSON 的 `tags`、資料夾節點的 `_tags.json`；`_tooldef.json` 的 `path` 說明補連結寫法一句。完成條件：兩個節點帶不同 tag，`find {"tag": X}` 只回帶 X 的那個；`read "a/b#/c/1"` 回那個陣列元素。
11. **`promote`**：照 promote 那節做。完成條件：換上後 `measure` 門仍過；`rollback` 後目標與換上前逐 byte 相同；有 proc 正用著目標時回 `DefBusy`、什麼都沒動。
12. **審視者 `templates/reviewer/`（`downgrade` 全自動，`fix`／`split` 只開處方）**：`system.txt` 寫一輪七步；工具給 measure、promote、memory、memory_write、thought、agents；`ladder.json` 照格式；帶自己的 `_metainfo.json`。完成條件：對婆山鎮 case 跑一輪，`review.json` 的 `target` 是 linker、`tried` 有 sol→terra 三次分數、`adopted` 是 terra、`dirty` 含 kb_link，正式定義的 `linker/llm.json` 已換成 terra、`.prev/linker/` 有前版、`watch.json` 有一個 `watching` 的窗。
13. **watch（盯與自動退回）**：照「容忍短暫退步」那節做。完成條件：餵三個假 case 結果——第一個單位成本貴 30%、後兩個便宜到平均只貴 5%——窗轉 `kept`、沒退回；改成平均貴 15% 時退回成前版、`state` 為 `rolled_back`；任一個門沒過時當場退回。
14. **`lib/agent/metainfo_check`**：照「metainfo 怎麼評估」那節做。完成條件：給一份估值寫 7004、實測 7577 的定義，回 `close`；估 14750、實測 20300 回 `off`；沒寫估值的回 `unclaimed`。
15. **審視者加 `fix`／`split` 施工（第四個地點起）**：兩招都開聰明級 thought 寫進副本、再 measure，門不過就退回。完成條件：給一個輸出完全由輸入決定的假 LLM 步，審視者產出腳本版、門過、`after.token.in` 為 0。
16. **審視 case 與第二層審視**：建 `cases/review-poshan/`（好答案取轉正過的那輪），讓第二隻審視者以 reviewer 為目標跑一輪。完成條件：產出一份 `target` 是 reviewer 的 `review.json`，`before`／`after` 是「審視一輪」的成本。
17. **試驗場改接**：`place_run` 的步驟改用 `lib/observed.py` 記帳、用 measure 量；`meta_observe` 與 `defs/*/_observed.json` 退役；地點 3 起由審視者出 `review.json`。完成條件：地點 3 的 `review.md` 數字段全由 `review.json` 生成，隊長只填「為什麼」一段（語意改由裁判比對器）。

條文（不交 gpt，由 opus 寫）：五條概念入 CONCEPTS；NORMS 補 `_metainfo.cost`／`timeout_ms`、公式 key 由讀者求值、`aos-observed` 介面與四種行、case 夾與比對器契約（含裁判）、`measure.json`／`review.json`／`watch.json`、N-62 鬆綁一句、memory 連結與 tag 約定、thought／agents 收子前抄帳、「審視者經 `promote` 換別人的定義不算 self-improve」；待定稿「實測不回寫」維持並註明他見住處。

## 同批其他題

- llm kernel 的多層嵌套、排程與跨層記帳對帳：交給 [kernel-nest](../kernel-nest/)。
- 知識庫全庫規模、查詢與給人看的那層：交給 [kb-scale](../kb-scale/)。
- 工具權限怎麼從開放走到專屬（含誰能按 `promote`）、確定性怎麼量：交給 [tool-evolve](../tool-evolve/)。

## opus 註

- **呼叫樹不是 stack 資料夾樹。**規劃原稿說「呼叫樹＝stack 樹、叫的人給對方小格」，這只對工具成立；子 agent 的 stack 由 daemon 放（thought 回的路徑相對 `$AOS_DAEMON`），而且 thought 預設收工就刪。所以改成「帳裡寫明下一本在哪」，加上收子前抄帳（衝突 9）。
- **腳本不記帳就看不穿。**原稿的 `measure.json` 範例裡，腳本 place_run 底下有子節點，但它同時規定「沒帳的就是葉」，兩者矛盾。所以把記帳模組搬上 lib、給腳本一個 `call`，`kind` 改成看帳裡有沒有 `think` 行。
- **門要有比對器。**原稿說門是逐 byte 一致，但降級試驗用的是 0.9 一致率，linker 的產出本來就不會逐 byte 一樣。所以門統一成「比對器打分、過 `min_score`」，逐 byte 只是預設比對器。
- **`promote` 不能靠判官管。**判官的 `allowed` 只判「掛不掛某個名字的 proc」，`promote` 是 act 格裡跑的工具、不是 proc，判官管不到。所以改成「登記在誰的工具箱誰才能按」（C-61：agent 只看得到自己的工具）。前版也不放在目標資料夾裡面（資料夾搬不進自己的子資料夾，而且會被當成定義的一部分），改放定義根的隱藏 `.prev/`。
- **試穿要用整棵副本。**只複製目標一個資料夾，呼叫它的上游還是指著正式那份，量不到改後的效果；所以副本是整個定義根，case 的路徑相對定義根。
- **「同目標模板」看不到。**帳裡只有參數的位元組數、沒有內容，所以專精建議改用「同一個子定義＋同一組工具」來分組。
- **`fix` 的訊號用 measure 的三份樣本。**原稿用的 `place_run --check` 是試驗場自己的旗標，不是通用介面。
- **轉交函數放 `lib/aos/`**，不放 `lib/agent/`：它是 kernel 的端點函數，不是 agent 的工具。
