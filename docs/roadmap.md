# aos 接下來要做什麼

← [文件索引](README.md)｜[aos 是什麼](overview.md)｜模型來源 [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md)

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

這條路線會改寫 [overview.md](overview.md) 的「一句話」：aos 現在寫成「一組 POSIX
小工具的集合」，T1 落地後它會變成「一個資料夾的回合制執行器，外加一組 POSIX 小
工具」。**overview 要等 T1 真的能跑再改**，不要先改文件。

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

### T1 — `aos exec <folder>`：回合原語　【建議先做】

新子命令 `aos exec`，參數是資料夾，讀 `<folder>/.aos/inst.json`，語意是
「**消費一回合**」：

```text
完整讀入 → 立刻取走（見 T2）→ 以該資料夾為基準執行 → 結束
```

- 只動 `run.cpp`，不碰凍結層，不開新小專案。
- 沒有迴圈、沒有 daemon、沒有 `.aos/next/`。跑一次就是一回合。
- 沒有 instruction 檔時：安靜結束、退出碼 0（「停留在目前回合」不是錯誤）。

**驗收**：同一個資料夾連跑兩次 `aos exec <folder>`，第一次執行、第二次無事可做。
`.aos/inst.json` 在執行**之前**就已經不在原位。

### T2 — 取件與投遞協定：`.temp/` 與 `.runi`<a id="t2--取件與投遞協定temp--runi"></a>

協定由使用者指定，兩邊各一次 `rename`：

```text
生產者 ──▶ .aos/inst.json.temp/<pid>  ─彙整──▶ .aos/inst.json
消費者     .aos/inst.json  ──rename──▶  .aos/inst.json.runi   （取件，讀完立刻做）
```

| 問題 | 這樣就解掉 |
|---|---|
| 兩個生產者互相蓋寫 | 投遞匣是目錄，一個生產者一個 `<pid>` 檔 |
| 原子取件 + crash 後查得到 | 消費者讀完立刻 `rename` 成 `.runi`，然後才執行 |
| 兩支 `aos exec` 同時跑同一個資料夾 | `.runi` 已存在就**拒絕啟動**（[D6](#d6) 已定） |

命名規則：**`<目標>.temp/` 是投遞匣，`<目標>.runi` 是執行中的現場**，都掛在它們服務
的那份 instruction 檔旁邊。

對回合語意來說，`rename` 走了就等於刪了——「先刪再跑」不變。但它順手保留了現場：
crash 之後那份 `.runi` 還在，**要不要恢復是之後的決定，不是現在要做的功能**。
第一版只要求「留著、不自動重跑」。

其他 CPU（如 `aos llm exec`）**最好也遵循同一套慣例，但不強迫**：`.aos/insts/llm.json`
配 `.aos/insts/llm.json.temp/<pid>` 與 `.aos/insts/llm.json.runi`。

**還缺一筆**：「寫到一半」和「可以彙整了」目前是同一個檔名，彙整者可能讀到寫到一半的
投遞。補法很便宜——先寫同目錄下彙整者會略過的名字（例如 `.<pid>.writing`），寫完
`rename` 成 `<pid>`。

**驗收**：在取件前、取件後執行前、執行中三個點殺掉 process，資料夾都只會呈現
「完整的舊狀態」或「完整的新狀態」，不會出現半份 JSON，也不會自動重放已經發生的
副作用。

### T3 — 彙整與發布：接出下一回合

彙整**就是把 `.aos/inst.json.temp/` 底下所有投遞併成一份 `.aos/inst.json`**。原本另設
`.aos/next/` 匯流區的構想被它取代了——投遞匣和彙整來源是同一個地方，少一個概念。

還沒定的細節：

- 合併**順序**（pid 排序確定性但無意義；mtime 有意義但會平手）。
- 彙整**什麼時候跑**：`aos exec` 每回合自己跑一次，還是獨立一步。
- `inst.json` 位置上已經有一份沒被讀走的批次時：附加、等下一輪，還是拒絕。
- 彙整完的投遞何時刪除，與發布 `inst.json` 的先後。
- 某份投遞內容無效：隔離該檔繼續、整批停住，還是拒絕發布（建議隔離並繼續）。

**驗收**：一個資料夾能自己接兩回合——第一回合的指令投遞到 `.aos/inst.json.temp/`，
第二次呼叫 `aos exec <folder>` 就跑到了下一回合的內容。

### T4 — 迴圈：`aos exec --keep-doing`，不做 `core/daemon`

daemon **不是另一支程式，是同一條命令的一個旗標**（`--keep-doing` 是暫名）。迴圈體就
是 fetch–execute：彙整 → 取件 → 執行 → 再來一次。

在它之前可以先用 shell 驗一遍，成本是零：

```bash
while true; do aos exec ./myfolder; sleep 1; done
```

shell loop 撐不住的地方，就是 `--keep-doing` 要補的東西（輪詢間隔或 inotify、信號怎麼
收尾、沒有 `inst.json` 時等待還是結束）。

**注意**<a id="t4-的注意事項"></a>：`.runi` 存在就拒絕啟動這條規則在 `--keep-doing` 底下意味著 **crash 之後迴圈
會永遠拒絕啟動**。這是預期行為（要人來看），但可能需要一條「清掉現場」的命令配套。

**驗收**：`aos exec --keep-doing` 能連續推進多回合；crash 留下 `.runi` 之後它停住而不
是繞過去。

### T5 — 第一顆抽象 CPU：`aos llm exec <folder>`

到這裡才碰 llms／tooljson。形狀已經定了：它是**被 inst `exec` 起來的一支普通程式**。

```text
.aos/inst.json 的一筆 instruction: ["aos","llm","exec","."]
        ↓ （對 aos exec 而言只是普通 POSIX 指令）
讀 .aos/insts/llm.json（對話、system、可用工具）
        ↓
呼叫一次模型
        ↓
把模型要的 tool call 用 tooljson 展開成 instruction
        ↓
寫進 .aos/next/ → 下一回合由 inst 執行
        ↓
結束，記憶體不留任何東西
```

這一步同時把兩個小專案矯正回來：`llms` 從「同步 ask」變成「turn producer」，
`tooljson` 從「自己 run」變成「emitter」。

**驗收**：一個資料夾裡，模型要求呼叫一個工具 → 工具在**下一回合**由 inst 真的跑起來
→ 結果回到資料夾 → 再下一回合模型看得到它。全程沒有任何常駐 process。

---

## 四、決策紀錄

**已定**：[D1](#d1) 版面（工作假設）、[D6](#d6) `.runi` 拒絕啟動、
[D7](#d7) 投遞匣是目錄、[D8](#d8) 砍掉 `aos inst`、[D9](#d9) `aos exec` 是唯一入口。

**還等使用者**：[D2](#d2) 回合粒度、[D3](#d3) 阻塞與否、[D4](#d4) 改造或重長、
[D5](#d5) `stderr` merge。這四題標「建議」的都只是我的主張，**我不會自己選**。

### D1 — `.aos` 的版面<a id="d1"></a>（擋 T1）　**已有工作假設，尚未定案**

使用者給的方向（我原本建議的目錄式沒被採用）：

```text
.aos/inst.json               ← process CPU。它是最核心的 CPU，所以直接放 .aos 底下
.aos/inst.json.temp/<pid>    ← 投遞匣（目錄，一個生產者一個檔）
.aos/inst.json.runi          ← 執行中的現場
.aos/insts/<name>.json       ← 其餘 CPU（各自配同樣的 .temp/ 與 .runi）
.aos/insts/<name>/xxx.json   ← 那顆 CPU 需要多份時再開一層
```

核心 CPU 被刻意放在特權位置，其餘一律收進 `insts/`。這比我建議的全目錄式**更直接
表達「哪顆是核心」**，代價是「列出所有 CPU 的佇列」要對頂層特例化——那是小代價。

還沒定案，但配套的 [D6](#d6)／[D7](#d7)／[D8](#d8) 都已經有答案了。

### D2 — 一回合＝一整批，還是一筆？<a id="d2"></a>（擋 T1／T3）

**建議：一整批。** `inst` 現在就是批次語意，而且有「整批驗證過才開跑」這個保證；改成
一次一筆等於丟掉它。附帶影響：T3 的「已有 instruction 檔時不覆蓋」在批次語意下最單純
的答案是**延後發布到下一輪**，不是合併兩批。

### D3 — 阻塞還是非阻塞？<a id="d3"></a>（擋 T4／T5）

**建議：T1–T5 全部 blocking，不做非阻塞。** 理由是
[inst-execution](../wf/workflows/ideas/inst-execution.md) 那條開放問題——「daemon 何時
算本回合執行完畢」——只要引入非阻塞就沒有單純答案。長 LLM 呼叫會卡住該資料夾的回合，
**這是可接受的**：那個資料夾本來就在等它。真的痛了再回來開這題。

### D4 — llms／tooljson 是原地改造還是重長一次？<a id="d4"></a>（擋 T5）

**建議：原地改造，保留兩層、砍掉一層。** 保留 llms 的 transport／串流／preset 與
tooljson 的 spec 驗證／argv 展開（都有實測價值），砍掉 `Bot::ask` 與 `Body::run` 這層
介面，換成 turn producer／emitter。全部重長會把已經驗過的 curl 與 schema 一起丟掉。

### D5 — `stderr` merge 這題還算不算數？<a id="d5"></a>（擋 T5，可延後）

[WAIT_USER](../wf/WAIT_USER.md) 上卡著「tooljson 的 exec 引擎自己寫還是動
`core/inst`」。回合模型把這題**改寫了一半**：tooljson 不再需要自己的 exec 引擎（那是
inst 的事），所以「誰擁有 exec」不用選了。但**沒有整個消滅**——tooljson 的 exec 配方
要求 `stderr.mode: "merge"`（兩條流真的共用一條管子），而 `inst` 的重導向走檔案路徑、
對 stdout 與 stderr 各開一次 `O_TRUNC`。這題現在變成「**`inst` 要不要長出 stderr merge
欄位**」，而那會動到凍結的 `exec.cpp`。

**建議：延後到 T5 真的踩到再問。** 在那之前 WAIT_USER 那條改記成「已被 T5 取代，等
T5 再重問」，不要當成 S2 的前置條件卡著。

### D6 — `.runi` 存在時代表什麼？<a id="d6"></a>　**已定：拒絕啟動**

`.aos/inst.json.runi` 已經在 → `aos exec` **拒絕啟動**。它固定名稱，所以天生就是一把
鎖：crash 現場不會被靜靜蓋掉，也不會有兩支 `aos exec` 同時跑同一個資料夾。代價是
crash 之後要人處理，這是刻意的。連帶影響見 [T4](#t4-的注意事項)。

### D7 — 投遞怎麼避免撞名？<a id="d7"></a>　**已定：投遞匣是目錄**

`.aos/inst.json.temp/` 是一個**目錄**，一個生產者一個 `<pid>` 檔。攤在 `.aos/` 底下會
愈積愈亂，收進目錄就乾淨了。

這一步同時把「彙整」定義掉了：**彙整就是把這個目錄底下所有投遞併成一份
`inst.json`**，`.aos/next/` 那個另設匯流區的構想不需要了。

還缺一筆：「寫到一半」與「可以彙整了」目前同名，見 [T2](#t2--取件與投遞協定temp--runi)
的補法。

### D8 — `aos inst` 這條子命令留不留？<a id="d8"></a>　**已定：直接刪掉**

只留 `aos exec`。`aos inst jobs.json` 這條檔案模式直接砍，不留相容層。

**小專案本身不用改名**：`inst` 是名詞（資料格式、`core/inst`、`<aos/inst.hpp>`、
`libaos_inst.so`），`exec` 是動詞（子命令）。改名的波及面只有 CLI 那一層，函式庫、
標頭、C ABI 都不動。

### D9 — `aos exec` 就是那個「唯一入口」<a id="d9"></a>　**已定**

llm-cpu 舊文的「方案 A：單一巨型入口」和現在的 `aos exec` **合流了**，但方式和 A 原本
設想的不同：`aos exec` 確實是唯一入口（所有工作都經由 `.aos/inst.json`，連持續跑都只
是 `--keep-doing` 旗標），**但它沒有吞下任何職責**——因為交接是 `exec`，`aos exec` 這
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
- **不做 `core/daemon` 這個小專案。** 持續執行是 `aos exec --keep-doing` 這個旗標。
- **不做全域 LLM daemon 與跨資料夾排程。** 那要等「一個資料夾跑得動」之後才有意義，
  而且它的前提（非阻塞）在 [D3](#d3) 被建議推遲了。
- **不做 Git checkpoint、FUSE、VFS。**
- **不繼續 llmkit 移植的 S2／S5**（見 [`reference/PORTING.md`](../reference/PORTING.md)）。
  S2 的前置決策已被 [D5](#d5) 改寫，S5 的收尾
  對象（`core/llms`／`core/tooljson` 的 docs）會在 T5 被改形狀——現在寫等於白寫。
  **`reference/` 仍然不要刪**：T5 改造時還要拿 llmkit 原文對照。
- **不先改 `docs/overview.md`。** 等 T1 能跑再改。

## 七、和既有紀錄的關係

| 檔案 | 關係 |
|---|---|
| [`wf/workflows/ideas/`](../wf/workflows/ideas/README.md) | **模型真源**。本檔只排順序，不定義模型 |
| [`wf/SESSION-LOG.md`](../wf/SESSION-LOG.md) | open 活狀態。llms／tooljson 是失敗作那條，落地方式就是本檔的 T5 |
| [`wf/WAIT_USER.md`](../wf/WAIT_USER.md) | S2 的決策已被 [D5](#d5) 改寫 |
| [`reference/PORTING.md`](../reference/PORTING.md) | S1／S3／S4 已落地的部分仍然有效；S2／S5 停用，改由 T5 決定 |

## 八、參考來源借了什麼

- [`../agent-machine`](../../agent-machine/START-HERE.md)：借的是**第五節那三條鐵律**與
  「先提交意圖 → 造成作用 → 驗證證據 → 才算完成」的次序感。**沒借**它的
  Function／Task／Receipt 詞彙與中央 store 架構——那套是為了 exactly-once 與 crash
  recovery 付的代價，aos 現在不付。
- [`../freepy`](../../freepy/README.md)：借的是 `llmkit`／`tooljson` 的**格式與錯誤
  契約**（已經在 `reference/llmkit/` 有原文）。**沒借** `agentloop` 的 Round／Handle
  ／Controller——那是「常駐在記憶體裡的 loop」，正好是第二節診斷出來的那個病。
