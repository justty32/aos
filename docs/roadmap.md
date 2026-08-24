# aos 接下來要做什麼

← [文件索引](README.md)｜[aos 是什麼](overview.md)｜模型來源 [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md)

> **`.aos` 的規格已經抽成獨立文件：[`.aos` 資料夾標準](aos-folder.md)。** 版面、命名、
> 交接協定、路徑基準、退出碼、版本、git 邊界一律以那份為準；本檔只留「什麼時候做」與
> 「為什麼這樣排」。

這份只回答**順序**：既然回合制模型已經定了方向，接下來該先做哪一塊、哪些事要先問
使用者、哪些明確不做。**模型本身不在這裡定義**——它在
[回合制資料夾](../wf/workflows/ideas/turn-based-folder.md) 與
[全域 LLM CPU](../wf/workflows/ideas/llm-cpu.md)，本檔與那兩份衝突時以它們為準。

各階段標了狀態：**已定**（使用者拍過板）、**建議**（本檔的主張，可被推翻）、
**待拍板**（不能由我偷偷補成答案）。

---

## 一、一句話的方向

> aos 的本體是「**資料夾 + 回合 + inst**」。LLM、tool 這些都不是新機制，是疊在上面
> 的子命令。

所以主線**不是**繼續把 llmkit 移植完，而是**先把回合原語做出來**。移植出來的那兩個
小專案要等模型立起來之後，才知道它們該長什麼形狀。

這條路線有個容易被忽略的紅利：**因為 `inst` 跑的是 POSIX 指令，agent loop 不需要等
`core/llms`**——「呼叫一次模型」可以先用任何一支現成的 LLM CLI 頂著（[T5](#t5)）。自家
的 LLM CPU 是之後把它換掉（[T6](#t6)），不是前置條件。

這條路線已經改寫了 [overview.md](overview.md) 的「一句話」：aos 原本寫成「一組 POSIX
小工具的集合」，T1 落地之後改成「一個資料夾的回合制執行器，外加一組 POSIX 小工具」。

## 二、現況盤點

### `core/inst` — 可用，而且它就是回合原語缺的那一半

`aos inst [file]`（[D8](#d8) 已定要改名成 `aos exec`）目前的語意是：讀完整份 JSON（單筆物件或陣列）、**全部驗證通過才
開始執行**、依序 blocking 跑完。這正好就是一回合要的東西——「一批指令，要嘛整批合
法，要嘛一筆都不跑」。

關鍵的好消息：**folder 模式可以完全在 CLI 層做完**。凍結範圍是
`inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep`／`wait`／`capi*`；
[`core/inst/src/run.cpp`](../core/inst/src/run.cpp) 不在凍結名單裡
（見 [code map](../wf/workflows/common/code-map.md)）。T1 不需要解凍任何東西。

### `core/tooljson` — 底下對，介面錯

有用的是 spec 載入、schema 驗證與 exec 配方的 **argv 展開**——那一步**正是「把一個
tool call 翻譯成一筆 instruction」**，是模型真正需要的東西。

錯的是 `Body::run(args_json)` 這個形狀：它假設工具由 tooljson 自己跑起來。在回合模型
裡 tooljson **不該執行任何東西**，它應該**產出 instruction** 交給 inst。目前
`ExecBody::run()` 還回一句「尚未實作」，等於這條錯路還沒鋪下去——這是運氣好。

### `core/llms` — 底下對，介面錯（同一個病）

有用的是 transport 那一層：curl、endpoint preset、串流、capability 三態。這些是實測
過會動的水電。

錯的是 `Bot::ask()` 這個形狀：**同步問一句、回一個 `Reply`、對話狀態留在記憶體裡**。
模型要的是反過來的東西——**一次 LLM 回合的產出是「下一回合的 instruction」，狀態留在
資料夾裡**。一支 `aos llm exec <folder>` 跑完就結束，記憶體什麼都不留。

### 一句話的診斷

> 兩個小專案都把自己寫成「**函式庫，等別人呼叫**」；模型要的是「**一顆 CPU，被 inst
> `exec` 起來，讀自己的 instruction 檔，寫下一回合**」。

失敗的是**介面與狀態放哪裡**，不是底下的水電。所以是改造，不是全部丟掉——見
[決策 D4](#d4)。

---

## 三、主線階段

每階段獨立驗收，前一階段沒綠不進下一階段。

### T0 — `inst` 的 schema 擴充　**【已完成】**

`core/inst` 核心層已解凍。這一批要動 `format.cpp` 與 `exec.cpp`，兩件事排在一起做：

1. **[D3](#d3) 的 non-blocking 欄位** — 每筆指令自帶「要不要開 thread」，`aos exec` 等
   所有 thread 收完才算回合結束。
2. **`$` 指示詞** — `$opt`／`$env`／`$ref`，設計與實作順序見
   [inst 的 `$` 指示詞](inst-directives.md)。第一步 `$opt` + `stderr` merge 最小，直接
   解掉 [D5](#d5)。

**驗收**：`stderr` 併流真的交錯（不是互相蓋寫）；non-blocking 那筆之後下一筆立刻啟動，
而回合仍等到所有 thread 收完。

### T1 — `aos exec <folder>` 與 `aos init`：回合原語　**【已完成】**

規格見 [`.aos` 標準](aos-folder.md)。這一階段要做出來的是：

- **`aos init <folder>`** — 建立 `.aos/`，寫下 `version`。
- **`aos exec <folder>`** — 讀 `<folder>/.aos/inst.json`，消費一回合。沒有 `.aos/`
  就報錯，不自動建（[標準第十一節](aos-folder.md)）。
- **路徑基準統一成 `<folder>`** — 最省事的作法是一開始就 `chdir` 過去
  （[標準第四節](aos-folder.md)）。這會改變 `inst` 現有的路徑語意，是刻意的。
- **`version` 不認得就停**，不要盡力而為（[標準第九節](aos-folder.md)）。
- 附一份 `.gitignore` 樣板：**整個 `.aos/` 都不進 git**（[標準第十節](aos-folder.md)）。

語意是「**消費一回合**」：

```text
完整讀入 → 立刻取走（見 T2）→ 以該資料夾為基準執行 → 結束
```

- 只動 `run.cpp`，不碰凍結層，不開新小專案。
- 沒有迴圈、沒有 daemon、沒有 `.aos/next/`。跑一次就是一回合。
- 沒有 instruction 檔時：安靜結束、退出碼 0（「停留在目前回合」不是錯誤）。

**驗收**：同一個資料夾連跑兩次 `aos exec <folder>`，第一次執行、第二次無事可做。
`.aos/inst.json` 在執行**之前**就已經不在原位。

### T2 — 取件與投遞協定：`inst.tempd/`、`.temp`、`.runi`<a id="t2"></a>　**【已完成，但投遞那一步只有協定沒有 API】**

協定由使用者指定，兩邊各一次 `rename`：

三步，每一步的交接都靠一次 `rename`：

```text
投遞  inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json
彙整  併成 inst.json.temp        ─rename─▶ inst.json
取件  inst.json                  ─rename─▶ inst.json.runi
```

| 問題 | 這樣就解掉 |
|---|---|
| 兩個生產者互相蓋寫 | 投遞匣是目錄 `inst.tempd/`，一個生產者一個 `<pid>.json` |
| 彙整者讀到寫到一半的投遞 | 寫作中帶 `.temp` 狀況，彙整者略過；寫完才 `rename` |
| 原子取件 + crash 後查得到 | 讀完立刻 `rename` 成 `.runi`，然後才執行 |
| 兩支 `aos exec` 同時跑同一個資料夾 | `.runi` 已存在就**拒絕啟動**（[D6](#d6) 已定） |

命名標準（[D1](#d1)）：`<名字>.<副檔名>.<狀況>`——第一個 `.xxx` 是副檔名，第二個是當前
狀況。狀況目前只有兩個字：`.temp`（還在生成，別碰）與 `.runi`（已取走、正在跑）。

對回合語意來說，`rename` 走了就等於刪了——「先刪再跑」不變。但它順手保留了現場：
crash 之後那份 `.runi` 還在，**要不要恢復是之後的決定，不是現在要做的功能**。
第一版只要求「留著、不自動重跑」。

其他 CPU（如 `aos llm exec`）**最好也遵循同一套慣例，但不強迫**：`.aos/insts/llm.json`
配 `llm.json.temp`、`llm.json.runi` 與投遞匣 `llm.tempd/`。

**驗收**：在取件前、取件後執行前、執行中三個點殺掉 process，資料夾都只會呈現
「完整的舊狀態」或「完整的新狀態」，不會出現半份 JSON，也不會自動重放已經發生的
副作用。

### T3 — 彙整與發布：接出下一回合　**【已完成】**

彙整**就是把 `.aos/inst.tempd/` 底下所有投遞併成 `.aos/inst.json.temp`，再 `rename` 蓋掉
`.aos/inst.json`**。原本另設 `.aos/next/` 匯流區的構想被它取代了——投遞匣和彙整來源是
同一個地方，少一個概念。

當初列為「還沒定」的五個細節**全部已經拍板並實作**，規則寫在
[`.aos` 標準第六節](aos-folder.md)的「彙整的規則」：檔名字典序但投遞者不得假設順序、
彙整併進 `aos exec` 每回合跑一次（但實作上解耦）、`inst.json` 已有一份就這輪不發布、
發布成功之後才刪投遞、壞投遞就地改名加 `.bad` 並繼續處理其餘的。

最尖的那個角（`rename` 會無聲吃掉沒被讀走的批次）是用「已經有一份就不發布」解掉的
——不覆蓋、不合併，這是「一回合＝一整批」的直接推論。

**驗收**：一個資料夾能自己接兩回合——第一回合的指令投遞到 `.aos/inst.tempd/`，
第二次呼叫 `aos exec <folder>` 就跑到了下一回合的內容。

### T4 — 迴圈：`aos exec --loop <毫秒>`，不做 `core/daemon`　**【已完成】**

daemon **不是另一支程式，是同一條命令的一個旗標**：`--loop <間隔>`，數字是隔多久檢查
一次。迴圈體就是 fetch–execute：彙整 → 取件 → 執行 → 再來一次。**單位是毫秒**；
**`0` 會印警告然後當成 `1`**，因為零間隔的字面意思是「沒事做時也全速重跑」，實測會吃掉
約一整顆核心（見[標準第十二節](aos-folder.md)）。

在它之前可以先用 shell 驗一遍，成本是零：

```bash
while true; do aos exec ./myfolder; sleep 1; done
```

shell loop 撐不住的地方，就是 `--loop` 要補的東西（間隔語意或改用 inotify、信號怎麼
收尾、沒有 `inst.json` 時等待還是結束）。

**注意**<a id="t4-的注意事項"></a>：`.runi` 存在就拒絕啟動這條規則在 `--loop` 底下意味著 **crash 之後迴圈
會永遠拒絕啟動**。這是預期行為（要人來看），但可能需要一條「清掉現場」的命令配套。

**驗收**：`aos exec --loop 0` 能連續推進多回合；crash 留下 `.runi` 之後它停住而不
是繞過去。

### T5 — agent loop：**不需要 `core/llms`**<a id="t5"></a>

[D4](#d4) 把 `core/llms`／`core/tooljson` 排到 agent loop 之後。乍看奇怪——沒有 LLM 函
式庫怎麼做 agent loop？答案就是這套模型最大的紅利：

> **`inst` 跑的是 POSIX 指令，所以「呼叫一次模型」可以是任何一支已經存在的 CLI。**

```text
.aos/inst.json 的一筆 instruction:
    ["some-llm-cli", "-p", "@prompt.txt", ...]   ← 隨便哪支現成的 LLM CLI
        ↓ 對 aos exec 而言就是普通指令
    輸出寫到檔案（stdout 重導向）
        ↓
    一支小腳本把輸出翻成 instruction，投遞到 .aos/inst.tempd/<pid>.json
        ↓
    下一回合由 aos exec 執行工具、再排下一次模型呼叫
```

整個 loop **可以完全不含任何 aos 的新 C++**：T0–T4 做完之後，agent loop 是一份
`.aos/inst.json` 加幾支腳本。這跟 [T4](#t4-的注意事項) 先用 shell loop 當 daemon 是同
一個做法——**先用最便宜的方式證明模型會動，會痛的地方才是下一階段的規格書**。

具體要證的東西：

- 一次模型呼叫是**一回合**，狀態全在資料夾裡，沒有常駐 process。
- 模型要求的 tool call 在**下一回合**真的被執行，結果回到資料夾。
- 再下一回合模型看得到那個結果，並能決定繼續或停止。
- 使用者可以在回合之間插手改資料夾，下一回合就看得到。

**驗收**：一個資料夾裡跑完一次「模型 → 工具 → 模型看到結果」的完整來回，全程沒有常駐
process，中途 `Ctrl-C` 之後再 `aos exec` 一次能從斷點繼續。

**這一階段的產出不是程式，是規格**：腳本裡哪些地方重複、哪些地方難寫，就是 `aos agent`
與 T6 要收掉的東西。

### T6 — 把 LLM 內化：`aos llm exec <folder>`<a id="t6"></a>

> 這一階段才碰 `core/llms`／`core/tooljson`（[D4](#d4)）。T5 沒跑出痛點之前不要開工。

**`aos llm` 是 module，不是 core**（已定）。它會是一層**薄殼**——實作時甚至可能直接把
工作轉交給 Python。這跟模型完全一致：交接本來就是 `exec`，所以「用什麼語言實作那顆
CPU」根本不是 aos 要回答的問題。

這也回頭改變了 `core/llms` 的處境：如果 `aos llm` 只是薄殼加外部程式，那顆 C++ 的 LLM
client **可能根本不會被復活**，而是被繞過。所以 [D4](#d4) 的「先不動」不只是延後，也
可能是「永遠不用動」。要不要把 `core/llms`／`core/tooljson` 從 `core/` 移到 `modules/`
是同一批要問的事——但那要等真的動它的時候。

形狀已經定了：它是**被 `aos exec` 起來的一支普通程式**——和 T5 裡那支外部 CLI 站在完全
相同的位置，只是換成自家的。

```text
.aos/inst.json 的一筆 instruction: ["aos","llm","exec","."]
        ↓ （對 aos exec 而言只是普通 POSIX 指令）
讀 .aos/insts/llm.json（對話、system、可用工具）
        ↓
呼叫一次模型
        ↓
把模型要的 tool call 用 tooljson 展開成 instruction
        ↓
投遞到 .aos/inst.tempd/<pid>.json → 下一回合由 aos exec 執行
        ↓
結束，記憶體不留任何東西
```

這一步同時把兩個小專案矯正回來：`llms` 從「同步 ask」變成「turn producer」，
`tooljson` 從「自己 run」變成「emitter」。**T5 已經證明過這個位置能動**，所以 T6 是
「把外部 CLI 換成自家的」，不是「賭一個沒驗證過的形狀」。

**驗收**：一個資料夾裡，模型要求呼叫一個工具 → 工具在**下一回合**由 inst 真的跑起來
→ 結果回到資料夾 → 再下一回合模型看得到它。全程沒有任何常駐 process。

---

## 四、決策紀錄

**已定**：[D1](#d1) 版面與命名標準（工作假設）、[D2](#d2) 一回合一整批、
[D3](#d3) 回合內並行、[D4](#d4) llms／tooljson 先不動、[D6](#d6) `.runi` 拒絕啟動、
[D7](#d7) 投遞匣 `inst.tempd/`、[D8](#d8) 砍掉 `aos inst`、
[D9](#d9) `aos exec` 是唯一入口。

**已定（續）**：[D5](#d5) 用 `{"$opt":"merge"}` 並引進 `$ref`／`$env`；
[D10](#d10) 退出碼四碼；[`$` 指示詞設計](inst-directives.md)裡原本標「待拍板」的全部
——解析獨立成 resolve 層、`$opt` 只開 `merge`、`$ref` 不限深度但禁止循環。

**沒有在等使用者的了。** D1～D10 全部拍板（[D4](#d4) 的拍板內容就是「先不動」），
下一步是 [T5](#t5) agent loop。

### D1 — `.aos` 的版面<a id="d1"></a>　**已定，且已實作**

使用者給的方向（我原本建議的目錄式沒被採用）：

```text
.aos/inst.json               ← process CPU。它是最核心的 CPU，所以直接放 .aos 底下
.aos/inst.json.temp          ← 彙整中的下一批
.aos/inst.json.runi          ← 已取走、正在跑的那一批
.aos/inst.tempd/<pid>.json   ← 投遞匣（寫作中是 <pid>.json.temp）
.aos/insts/<name>.json       ← 其餘 CPU（各自配同名的 .temp／.runi／.tempd）
```

配套的**命名標準**：`<名字>.<副檔名>.<狀況>`。第一個 `.xxx` 是副檔名，第二個是這個
檔案／資料夾當前的狀況。這條標準是為 `.aos` 提前訂的，但不限於 `.aos`——真的落地時
應該升格進 [conventions](../wf/workflows/common/conventions.md)。

核心 CPU 被刻意放在特權位置，其餘一律收進 `insts/`。這比我建議的全目錄式**更直接
表達「哪顆是核心」**，代價是「列出所有 CPU 的佇列」要對頂層特例化——那是小代價。

配套的 [D6](#d6)／[D7](#d7)／[D8](#d8) 也都已經落地。規格以
[aos-folder](aos-folder.md) 為準，本節保留的是當初為什麼這樣選。

### D2 — 一回合＝一整批，還是一筆？<a id="d2"></a>　**已定：一整批**

`inst` 現在就是批次語意，而且有「整批驗證過才開跑」這個保證，一回合一整批直接沿用它。

### D3 — 阻塞還是非阻塞？<a id="d3"></a>　**已定：回合內並行，回合邊界不變**

`inst.json` 的**每筆指令**自帶一個欄位，決定要不要開 thread 用 non-blocking 的方式跑；
但 **`aos exec` 仍會等所有 thread 跑完**才算本回合結束。

我原本建議「先全部 blocking」，理由是「本回合何時算執行完畢」沒有單純答案——這個方案
直接把那題定義掉了：**答案是所有 thread 都收完**。回合邊界依然是硬的，並行只發生在
回合**之內**。細節與剩下的開放問題見
[inst-execution](../wf/workflows/ideas/inst-execution.md)。

⚠ **這一項會撞到凍結層**：新增 JSON 欄位一定要改 `format.cpp`（它對不認得的 key 直接
回 `UnknownKey`），thread 化要改 `exec.cpp`／`run.cpp`。**落地前需要明確解凍**，繞不
過去。這也讓 D3 從「T4／T5 的事」變成「和 T1 同一批要處理的事」。

### D4 — llms／tooljson 是原地改造還是重長一次？<a id="d4"></a>　**已定：先不動**

使用者的決定：**先不動、先不管，那要排在 agent loop 之後。**

所以 `core/llms` 與 `core/tooljson` 現在的狀態是**擱置**——不是失敗待修，是「等前面的
東西立起來再回頭處理」。在那之前不要投資這兩個小專案，也不要因為它們現在的形狀不對
而急著重寫。

連帶影響：原本的 T5 變成 **[T6](#t6)**，前面插進 **[T5 agent loop](#t5)**。這個順序
是通的——**agent loop 不需要 `core/llms`**，因為 `inst` 跑的是 POSIX 指令，「呼叫一次
模型」可以是任何一支現成的 LLM CLI。我原本「原地改造、保留 transport 與 argv 展開」的
建議留著，等真的動它時再拿出來討論。

### D5 — `inst` 要不要長出「stderr 併進 stdout」？<a id="d5"></a>（跟著 D4 一起延後）

**這題在講什麼**（從頭解釋，因為脈絡散在好幾個檔）：

freepy 的 `tooljson` 格式裡，一個工具可以用 `_type: "exec"` 描述成「跑一支程式」。它的
規格有個欄位 `stderr.mode`，其中一個值是 `"merge"`——意思是**把子行程的 stderr 併進
stdout 那條流**，兩邊的輸出交錯在同一份輸出裡，就是 shell 的 `2>&1`。

`inst` 做不到這件事，原因在重導向的形狀：

```text
inst 的做法：stdout 和 stderr 各是一個「檔案路徑」
             exec.cpp 對兩個路徑各 open() 一次，各帶 O_TRUNC
             ↓ 給同一個路徑的話
             兩次 open 各自截斷、各自有獨立的檔案偏移量
             → 兩條流互相蓋寫，不是交錯

真正的 2>&1：dup2(fd_out, 2)
             兩條流共用同一個 open file description、同一個偏移量
             → 才會是交錯
```

所以要支援 merge，`inst` 得長出一個哨兵值或布林欄位（例如 `stderr: "merge"`），讓
`exec.cpp` 走 `dup2` 而不是第二次 `open`。**這是 `format.cpp` 加 `exec.cpp` 的改動，
兩個都在凍結名單上。**

原本的決策 A 問的是「tooljson 自己寫 exec 引擎，還是接 `core/inst`」。回合模型把前半
消滅了——tooljson 不再執行任何東西，它只產出 instruction，所以**一定**走 inst。剩下的
就只是：inst 要不要支援 merge。

**已定：要做，而且做法不是哨兵字串。** 使用者拍板用
`"stderr": {"$opt": "merge"}`，並順便把 `../freepy` 那套 `$ref`／`$env` 一起引進
`inst` 的 JSON。完整設計見 **[inst 的 `$` 指示詞](inst-directives.md)**。

物件形式而非 `"stderr": "merge"` 這個選擇是對的：哨兵字串會讓你永遠無法重導向到一個
真的叫 `merge` 的檔案，物件形式讓字面字串永遠是字面。

`core/inst` 核心層**已解凍**（使用者批准），所以這題不再有前置成本。

### D6 — `.runi` 存在時代表什麼？<a id="d6"></a>　**已定：拒絕啟動**

`.aos/inst.json.runi` 已經在 → `aos exec` **拒絕啟動**。它固定名稱，所以天生就是一把
鎖：crash 現場不會被靜靜蓋掉，也不會有兩支 `aos exec` 同時跑同一個資料夾。代價是
crash 之後要人處理，這是刻意的。連帶影響見 [T4](#t4-的注意事項)。

### D7 — 投遞怎麼避免撞名？<a id="d7"></a>　**已定：投遞匣是目錄 `inst.tempd/`**

一個生產者一個 `<pid>.json` 檔，寫作中帶 `.temp` 狀況。攤在 `.aos/` 底下會愈積愈亂，
收進目錄就乾淨了。

這一步同時把「彙整」定義掉了：**彙整就是把 `inst.tempd/` 底下所有投遞併成
`inst.json.temp`，再 `rename` 蓋掉 `inst.json`**——`.aos/next/` 那個另設匯流區的構想
不需要了。

投遞匣叫 `inst.tempd/`（temp directory），`.d` 因此空出來留給「某顆 CPU 需要多份指令」
那種一般資料夾用途，不再一詞多義。

### D8 — `aos inst` 這條子命令留不留？<a id="d8"></a>　**已定：直接刪掉**

只留 `aos exec`。`aos inst jobs.json` 這條檔案模式直接砍，不留相容層。

**小專案本身不用改名**：`inst` 是名詞（資料格式、`core/inst`、`<aos/inst.hpp>`、
`libaos_inst.so`），`exec` 是動詞（子命令）。改名的波及面只有 CLI 那一層，函式庫、
標頭、C ABI 都不動。

### D10 — 回合的退出碼怎麼算？<a id="d10"></a>　**已定：沿用現有契約，加一個 3**

「thread 裡的指令失敗了，整回合的退出碼算什麼」——這題**已經被 `inst` 現有的契約回答
了**，thread 沒有改變任何東西。

現有契約（見 [`core/inst/docs/exec.md`](../core/inst/docs/exec.md)）：**子行程的退出碼
不是 aos 的退出碼**。非零狀態、被訊號殺掉、PATH 找不到、逾時——這些都算「一次**完成**
的執行」，CLI 仍然回 0。只有**函式庫層的失敗**（fork 失敗、父行程 setpgid 失敗、wait
失敗、寫 `exit` 狀態檔失敗）才讓 CLI 最後回 1。

這個切法在回合模型裡剛好是對的：

> `aos exec` 的退出碼只回答「**這個回合有沒有正常跑完**」，不回答「回合裡的指令做得好
> 不好」。

那「做得好不好」誰來讀？**不是退出碼，是檔案**。每筆 instruction 本來就能用 `exit`
欄位把自己的狀態寫進一個檔；下一回合的生產者去讀那些檔，決定接下來要投遞什麼。
**回合之間靠檔案傳結果，退出碼只給跑 `aos exec` 的那個人／那個 shell 看。**

所以 thread 化不需要新語意：某個 thread 的子行程回 3 → 回合照樣 0，狀態進它的 `exit`
檔；某個 thread `fork` 失敗 → 那是函式庫層失敗 → 回合回 1。

**唯一建議新增的一個碼**：`.runi` 已存在而**拒絕啟動**（[D6](#d6)）應該有自己的退出碼，
否則 shell loop 分不出「拒絕啟動」和「跑失敗」。整套會是：

| 碼 | 意思 |
|---|---|
| 0 | 回合正常跑完（**包含**「沒有 `inst.json`，無事可做」） |
| 1 | 有函式庫層失敗 |
| 2 | 用法錯誤 |
| 3 | 拒絕啟動：`.runi` 已存在 |

`--loop` 遇到回合回 1 **不停**，繼續下一回合；只有退出碼 3 會讓迴圈退出——那是
「需要人來處理」的狀態，繼續轉沒有意義。

### D9 — `aos exec` 就是那個「唯一入口」<a id="d9"></a>　**已定**

llm-cpu 舊文的「方案 A：單一巨型入口」和現在的 `aos exec` **合流了**，但方式和 A 原本
設想的不同：`aos exec` 確實是唯一入口（所有工作都經由 `.aos/inst.json`，連持續跑都只
是 `--loop` 旗標），**但它沒有吞下任何職責**——因為交接是 `exec`，`aos exec` 這
支程式裡永遠不會有 LLM 的程式碼、金鑰或連線。**process 邊界就是隔離邊界**，A 原本
「單點故障域過大」的風險因此不成立。

---

## 五、三條鐵律

從 [`../agent-machine`](../../agent-machine/START-HERE.md) 借的——**只借這三條**，不借
它整套 Task tree／Receipt／中央 store：

1. **先寫下意圖，再造成外部作用；證據不完整就停住，不自動重跑。** 回合模型的「先取走
   再執行」已經是這條的一半；缺的是「停住不自動重跑」要寫進 T2 的驗收。
2. **可攜的語意，和「這台機器上正在跑什麼」，要分開放。** `.aos` 若之後要進 git，
   `running/`、PID、鎖這類東西**一定不能**跟著進去，否則 clone 到別台機器會以為舊
   process 還活著。T2 建立 `running/` 的同時就要把它 gitignore 掉。
3. **原型的檔名、JSON 欄位、目錄名都不是 ABI。** T1–T3 的版面可以改；真的要凍結是
   之後另外一次決定。

## 六、明確不做的事

寫在這裡免得被當成漏做：

- **不做中央 store、scheduler、Task tree、Receipt、crash recovery 的完整矩陣。**
  那是 `../agent-machine/full/` 的重量級設計；aos 目前的模型刻意輕。
- **不做 `core/daemon` 這個小專案。** 持續執行是 `aos exec --loop 0` 這個旗標。
- **不做全域 LLM daemon 與跨資料夾排程。** 那要等「一個資料夾跑得動」之後才有意義。
- **不做 Git checkpoint、FUSE、VFS。**
- **不繼續 llmkit 移植的 S2／S5**（見 [`reference/PORTING.md`](../reference/PORTING.md)）。
  [D4](#d4) 已定：`core/llms`／`core/tooljson` 先不動，要排在 agent loop 之後。
  **`reference/` 仍然不要刪**：之後改造時還要拿 llmkit 原文對照。
- **不碰 `core/llms`／`core/tooljson`。** 它們現在的形狀不符合模型，但那是**擱置**，
  不是待修——別急著重寫，也別再往裡面投資。
- **不先改 `docs/overview.md`。** 等 T1 能跑再改。

## 七、和既有紀錄的關係

| 檔案 | 關係 |
|---|---|
| [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md) | **模型真源**。本檔只排順序，不定義模型 |
| [`wf/SESSION-LOG.md`](../wf/SESSION-LOG.md) | open 活狀態。llms／tooljson 是失敗作那條，落地方式就是本檔的 T5 |
| [`wf/WAIT_USER.md`](../wf/WAIT_USER.md) | S2 的決策已被 [D5](#d5) 改寫，並跟著 [D4](#d4) 一起延後 |
| [`reference/PORTING.md`](../reference/PORTING.md) | S1／S3／S4 已落地的部分仍然有效；S2／S5 停用，改由 T5 決定 |

## 八、參考來源借了什麼

- [`../agent-machine`](../../agent-machine/START-HERE.md)：借的是**第五節那三條鐵律**與
  「先提交意圖 → 造成作用 → 驗證證據 → 才算完成」的次序感。**沒借**它的
  Function／Task／Receipt 詞彙與中央 store 架構——那套是為了 exactly-once 與 crash
  recovery 付的代價，aos 現在不付。
- [`../freepy`](../../freepy/README.md)：借的是 `llmkit`／`tooljson` 的**格式與錯誤
  契約**（已經在 `reference/llmkit/` 有原文）。**沒借** `agentloop` 的 Round／Handle
  ／Controller——那是「常駐在記憶體裡的 loop」，正好是第二節診斷出來的那個病。
