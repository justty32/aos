# 指定資料夾的回合制演化模型

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

## 核心理想（基礎模型已定）

把 `inst` 視為「指定資料夾的狀態轉移函數」。它類似遊戲裡的 `process(delta_time)`：
輸入目前狀態，推進世界，再得到新的資料夾狀態；但 aos **不以經過時間作為語意輸入**，
而是採回合制。

- 指定資料夾是被演化的世界／狀態容器。
- `inst` 描述一次狀態轉移；每消費並執行一份 `inst`，就是切換到下一回合。
- daemon 的輪詢週期只是實作細節，不代表世界內的 `delta time`。
- 使用者可以在回合之間介入，影響資料夾狀態或下一回合的指令。

可把最小模型寫成：

```text
folder(state N) + inst(turn N → N+1) → folder(state N+1)
```

## `aos exec` 就是這個模型的實作（方向已定）

上面的狀態轉移不是另外做一套機制：**`aos exec` 針對指定資料夾底下的 `.aos/inst.json`
跑東西，這就是「持續變換」模型的實作本體**。

```text
aos exec <folder>   ==   folder(state N) + .aos/inst.json → folder(state N+1)
```

- 指定資料夾＝世界；`.aos/inst.json`＝這個世界待執行的指令流。
- 跑一次 `aos exec <folder>`＝推進一回合。
- `core/daemon` 因此不是另一種轉移機制，只是**反覆觸發同一個原語**的外殼：等待、
  觸發、彙整 `.aos/next/`、再等待。回合語意完全由 `inst` 這一層決定。

**關鍵性質：`inst` 執行的是 POSIX 指令，所以它可以承載任何東西**——包括 `aos` 自己。
上層要長出什麼能力，不必改回合模型，只要讓它成為某一筆 instruction 的 argv。這就是
下一節「抽象 CPU」能站在這層之上的原因。

## 擴充模型：抽象 CPU 疊在 inst 之上（方向已定）

LLM 這類「抽象 CPU」**建立在上述基礎之上**，不是與 `inst` 平起平坐的第二套原語。
做法是讓它以一筆普通 instruction 的身分出現在 `.aos/inst.json` 裡，例如：

```text
.aos/inst.json     ── 一筆 instruction: `aos llm exec`
                          ↓ （POSIX exec，對 exec 這顆 CPU 來說就是普通指令）
                    aos llm exec 讀 .aos/insts/llm.json（另一份 instruction 檔）
                          ↓
                    做「類似的事情」：取出、執行、推進該 CPU 的下一回合
```

- 每種抽象 CPU＝**一個 aos 子命令 + 它自己的 instruction 檔**，共用同一套「取出一
  筆、執行、寫下一回合」的形狀。
- 只有 process CPU 擁有原生的回合迴圈；其他 CPU 的回合是**被 `.aos/inst.json` 叫到時才
  取得的**——回合由下層授予，不必各自再養一支獨立迴圈。
- 新增處理器不需要新的核心機制，只需要新的子命令與新的 instruction 檔。
- **「轉介到另一顆 CPU」不是協定，就是 `exec`**：所謂把工作交給 LLM CPU，實際動作
  只是用 POSIX 跑另一支程式（`aos llm exec` 之類）。沒有訊息格式、
  沒有 IPC、沒有握手——**跨處理器的交接就是 fork/exec 本身**，要傳的東西走 argv、
  env、檔案系統（那份 instruction 檔）。
- 因此排程、隔離、資源上限這些問題都被推遲到「那支程式自己怎麼做」，而不是回合模型
  必須先回答的事。

完整的 LLM 排程、資源有限性與跨資料夾問題見 [全域 LLM CPU](llm-cpu.md)。

## 版面與交接協定（工作假設，**尚未定案**）

> **規格已經抽到 [`docs/aos-folder.md`](../../../docs/aos-folder.md)。** 版面、命名、
> 交接協定、路徑基準、版本、git 邊界一律以那份為準。下面這幾節留著是**脈絡**——記錄
> 這些形狀是怎麼想出來的、為什麼不是別的樣子。兩邊不一致時以規格為準。

以下是當初推導時的樣子。

### 命名標準（提前訂下來）

普通檔案的名字切成三段：

```text
<名字>.<副檔名>.<狀況>
   │       │        └── 第二個 .xxx：這個檔案／資料夾**目前的狀況**
   │       └────────── 第一個 .xxx：副檔名（.json 是 JSON、.d 是資料夾）
   └────────────────── 名字
```

- `inst.json` — 名叫 inst 的 JSON，沒有特別狀況（＝可以取用了）。
- `inst.json.temp` — 同一份東西，狀況是「還在生成，別碰」。
- `inst.json.runi` — 狀況是「已被取走、正在跑」。
- `inst.tempd` — 投遞匣**資料夾**（`.tempd` ＝ temp directory，是副檔名不是狀況）。
- `inst.d` — 一般的「名叫 inst 的資料夾」，留給「某顆 CPU 需要多份指令」那種用途。

> **狀況只用一個詞表示「還在生成」**：`.temp`（已定）。生產者寫到一半的投遞是
> `<pid>.json.temp`，彙整到一半的下一批是 `inst.json.temp`——兩者是同一種狀況，不必
> 有兩個字。整套狀況字彙目前只有兩個：**`.temp`（還在生成，別碰）**與
> **`.runi`（已取走、正在跑）**。

這條標準是為了 `.aos` 提前訂的，但它不限於 `.aos`；真的落地時應該升格進
[conventions](../common/conventions.md)。

### 檔案版面

```text
<folder>/.aos/
    inst.json          ← process CPU（aos exec）待執行的批次。最核心，所以放最上層
    inst.json.temp     ← 彙整中的下一批（彙整完 rename 蓋掉 inst.json）
    inst.json.runi     ← 已取走、正在跑的那一批
    inst.tempd/        ← 投遞匣：一個生產者一個檔
        <pid>.json     ← 投遞完成，等彙整
        <pid>.json.temp ← 還在寫，彙整者要略過
    insts/
        llm.json       ← 其他 CPU 各一份（各自配同名的 .temp／.runi／.tempd）
        <name>.json
```

核心 CPU 的 instruction 直接放 `.aos/inst.json`，其餘一律收在 `.aos/insts/` 底下——
**「反正 inst 就是這樣的佈局」**。

### 交接協定：投遞、彙整、取件

```text
P1 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┐
P2 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┤
P3 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┘
                            │
                            └彙整▶ inst.json.temp ─rename▶ inst.json ─rename▶ inst.json.runi
                                                                       （取件）
```

三步，每一步的交接都靠一次 `rename`：

- **投遞**：生產者先寫 `.aos/inst.tempd/<pid>.json.temp`，寫完 `rename` 成
  `<pid>.json`。**檔名帶 pid** 是必要的——`rename` 原子但「寫入」不是，共用檔名會互相
  蓋寫；**`.temp` 這個狀況**則讓彙整者不會讀到寫到一半的投遞。同目錄內的 `rename` 是
  原子的。
- **彙整**：彙整者把 `.aos/inst.tempd/` 底下所有**沒有 `.temp` 狀況**的投遞併成
  `.aos/inst.json.temp`，完成後 `rename` 蓋掉 `.aos/inst.json`。**這就是彙整這個功能的
  全部**——`.aos/next/` 那個另設匯流區的構想被它取代了。
- **取件**：`aos exec` 讀進來之後**立刻**把 `.aos/inst.json` `rename` 成
  `.aos/inst.json.runi`，然後才執行。這就是「先刪再跑」的實作——對 `inst.json` 那個
  位置來說它已經消失了，但現場被保留下來。
- **`.runi` 已存在時拒絕啟動**（已定）。它固定名稱，所以天生就是一把鎖：上一回合
  crash 留下的現場不會被靜靜蓋掉，也不會有兩支 `aos exec` 同時跑同一個資料夾。代價是
  crash 之後要人來處理，這是刻意的。
- **其他子模組（如 llm）最好也遵循同一套慣例，但不強迫**：`.aos/insts/llm.json` 配
  `llm.json.temp`、`llm.json.runi` 與 `llm.tempd/<pid>.json`。

### 一支命令，兩種節奏

```sh
aos exec <folder>            # 跑一回合
aos exec --loop 0 <folder>   # 持續讀、持續跑；數字是隔多久檢查一次
```

`--loop <間隔>` 就是 daemon：**daemon 不是另一支程式，是同一條命令的一個旗標**。
迴圈體就是 fetch–execute：彙整 → 取件 → 執行 → 再來一次。間隔的單位與 `0` 的確切
語意等實作時再定。

### 名詞與動詞

`inst` 是**名詞**（instruction 這個資料格式、`.aos/inst.json`、`core/inst` 這顆函式
庫）；`exec` 是**動詞**（`aos exec` 這條子命令）。子命令改名不代表小專案要跟著改名。

> 舊文裡「方案 A 的 `aos exec`」（一個吞下所有職責的巨型入口）**和這裡的 `aos exec`
> 合起來了**：`aos exec` 確實是唯一入口，但它只跑核心 CPU 的 `inst.json`，其他處理器
> 是它 `exec` 出去的子行程。理由見 [llm-cpu](llm-cpu.md)。

## 最基礎的 aos 使用方式（方向已定）

1. 給 aos 一個指定資料夾，跑 `aos exec --loop 0 <folder>`。
2. 它持續查詢 `.aos/inst.json` 有沒有待執行內容。
3. instruction 出現後，先完整讀進記憶體，**立刻**把 `inst.json` `rename` 成
   `inst.json.runi`，然後才執行其中的指令。
4. 指令造成的資料夾變化構成下一回合的狀態；執行期間要排入下一回合的生產者，把
   instruction 投遞到 `.aos/inst.tempd/<pid>.json`。
5. 本回合執行完畢後，彙整 `.aos/inst.tempd/` 底下所有投遞，發布成新的 `.aos/inst.json`。
6. 新的 `inst.json` 成為下一回合輸入，再次消費，形成循環。

因此它不是靠時間連續更新資料夾，而是等待離散的 instruction 批次；沒有新的
`inst.json` 就停留在目前回合。

## agent loop 如何建立在回合模型上

```text
aos exec --loop 0 監看 folder
        ↓
使用者在 folder 執行 aos agent start
        ↓
準備 .aos/ 與 agent 所需資料
        ↓
下一回合加入 aos agent init ...
        ↓
載入 folder 資訊、LLM、工具、人格與記憶
        ↓
啟動一次 LLM，完成 agent 的本回合動作
        ↓
需要繼續時，在結束前把下一步投遞到 inst.tempd/
        ↺
```

> **第一版 agent loop 不需要 `core/llms`**：`inst` 跑的是 POSIX 指令，所以「呼叫一次
> 模型」可以先用任何一支現成的 LLM CLI 頂著，整個 loop 就是一份 `.aos/inst.json` 加幾
> 支腳本。自家的 LLM CPU 是之後把它換掉，不是前置條件。見
> [roadmap 的 T5／T6](../../../docs/roadmap.md)。

- `aos agent start` 是使用者在指定資料夾內啟動 agent 的入口；它準備所需內容，並讓
  `.aos/inst.json` 的下一回合包含 `aos agent init ...`。
- `aos agent init ...` 會載入該資料夾的各類資訊，包括使用哪個 LLM 思考引擎、可用
  工具、核心人格與記憶，然後觸發 agent 的第一次 LLM 動作。
- agent loop 不必是一個永遠不返回的函式。需要跨多回合長期運作的工作，在本回合快
  結束時把下一次動作投遞到 `.aos/inst.tempd/<pid>.json`；回合結束後彙整並發布下一份
  `inst.json`，下一次消費它就形成下一回合。
- 使用者介入也成為回合模型的一部分：可以在後續 instruction 被消費前改變世界狀態，
  或提供會影響下一回合的輸入。

## 與目前 aos 元件的關係

- `core/inst` 提供「執行一次狀態轉移」的底層能力，`aos exec` 是它的子命令。
- `core/llms` 與 `core/tooljson` 可提供 agent 回合中的思考與工具能力——但兩者目前的
  形狀不符合本模型，要改造（見 [SESSION-LOG](../../SESSION-LOG.md) 與
  [roadmap](../../../docs/roadmap.md)）。
- **不再需要獨立的 `core/daemon`**：持續執行是 `aos exec --loop 0` 這個旗標，
  不是另一個小專案。
- agent 初始化與 LLM 回合邏輯仍是建立在 `exec`／`inst` 之上的後續能力，不混進回合
  原語的基礎職責。

## 單回合流程（已定）

```text
等待 .aos/inst.json
        ↓
完整讀入記憶體
        ↓
立刻 rename 成 .aos/inst.json.runi   ← 對 inst.json 那個位置來說就是刪除了
        ↓
執行本回合 instruction（資料夾狀態轉移）
        ↓
掃描 .aos/inst.tempd/ 下所有投遞（略過 .temp）
        ↓
彙整成 .aos/inst.json.temp，再 rename 蓋掉 .aos/inst.json
        ↓
進入下一回合
```

先讓當前 `inst.json` 從那個位置消失再執行，是基礎協定的一部分，不等執行成功才做。
`.aos/inst.tempd/` 則是本回合各個生產者提交後續動作的投遞匣；只在本回合執行結束後收集
它們。

## 已經定下來的（不必再問）

- `aos inst` 這條子命令**直接刪掉**，只留 `aos exec`。
- 取件用 `rename` 成 `.runi`；`.runi` 已存在時**拒絕啟動**。
- 投遞寫進 `.aos/inst.tempd/<pid>.json`；彙整就是把它們併成 `.aos/inst.json.temp`，
  再 `rename` 蓋掉 `.aos/inst.json`。
- **一回合＝一整批**，不是一次一筆。
- 每筆 instruction 自己帶一個欄位，決定要不要開 thread 用 non-blocking 的方式跑；
  但 **`aos exec` 仍會等所有 thread 跑完才算本回合結束**。遇到 non-blocking 那筆之後，
  **下一筆立刻啟動**（真並行，不排隊）。
- 命名標準：`<名字>.<副檔名>.<狀況>`，第一個 `.xxx` 是副檔名、第二個是當前狀況。
- 持續執行是 `aos exec --loop 0`，不另做 `core/daemon`。

## 開放問題（尚未拍板）

- non-blocking 欄位會動到**凍結的核心層**：新增 JSON 欄位要改 `format.cpp`
  （不認得的 key 會被拒），thread 化要改 `exec.cpp`／`run.cpp`。落地前必須明確解凍。
- `aos exec --loop 0` 只監看一個資料夾，還是能同時管理多個；其生命週期與啟停介面。
- `aos agent start`／`init` 是否必須冪等，重複執行時要保留、重建還是拒絕既有狀態。
- 回合失敗的語意：停在原回合、進入失敗回合、重試，或交由使用者另投 instruction。
- 指令以指定資料夾為 cwd 執行時的信任、安全與權限邊界。
- **彙整用 `rename` 蓋掉 `inst.json` 會無聲吃掉沒被讀走的批次**（見下一條）。
- 彙整的**順序**：多份投遞併成一批時誰先誰後。pid 排序是確定性的但無意義；
  mtime 有意義但會平手。
- 彙整者**什麼時候跑**、由誰跑：`aos exec` 每回合自己跑一次，還是獨立的一步。
- 彙整時 `inst.json` 位置上已經有一份沒被讀走的批次：附加、等下一輪，還是拒絕。
- 彙整完的 `inst.tempd/<pid>.json` 何時刪除，以及刪除與發布 `inst.json` 的先後。
- 某份投遞內容無效時：隔離該檔繼續、整批停住，還是拒絕發布。
- `--loop` 的細節：間隔單位、`0` 的語意、要不要改用 inotify、收到信號怎麼收尾、沒有 `inst.json`
  時是等待還是結束。另外它遇到 `.runi` 會**永遠拒絕啟動**（因為規則是拒絕），這是
  預期行為還是要另開一個「清掉現場」的命令。
- 核心 CPU 在 `.aos/inst.json`、其餘在 `.aos/insts/` 是刻意的不對稱。代價是「列出所有
  CPU 的佇列」這種操作要對頂層那個特例化；可接受與否還沒確認。
- 抽象 CPU 的回合由 `.aos/inst.json` 授予後，該 CPU 要在本回合內同步跑完
  （`aos llm exec` 阻塞直到模型回覆），還是只做投遞、結果之後再取；這與
  [inst 執行策略](inst-execution.md) 的非阻塞欄位是同一個決定。

> 本條目的「核心理想」與「最基礎使用方式」已由使用者定案；開放問題只是在落地前
> 必須回答的設計點，不改變上述回合制模型。
