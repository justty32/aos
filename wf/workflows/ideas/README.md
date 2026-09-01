# ideas — 構想記錄入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

記錄尚未進入 spec／plan／feature-dev 的產品構想。這裡保存的是**方向、心智模型與待釐清
問題**，不是已實作行為；構想準備落地時，再轉交對應工作流。

> **要重新拷問 aos 的人：先讀 [verdicts](verdicts.md)。** 九輪拷問的裁決已經收成一張表
> （已裁決／仍開著／欠帳／已驗證的實作缺陷），別重問已經拍板的東西。不該被改掉的優點在
> [call-format/keep](call-format/keep.md)。

## 目前構想

| 檔案 | 內容 |
|------|------|
| [verdicts](verdicts.md) | **九輪拷問的裁決總表**：已裁決（不必再問）／仍開著（值得打）／欠帳（裁決相乘產生的）／已驗證的實作缺陷。重新拷問的入口 |
| [turing-to-os](turing-to-os.md) | **根基論證**：圖靈完備三要件（可計算／可條件分支＝對環境反應、可連續執行自身＝體積不能無限膨脹）分別由 LLM／tooling／agent loop 擔當 → agent loop ＝ CPU → aos ＝ 以 agent loop 為計算單元的作業系統；檔案系統同時是記憶體與程式（含行程）的載體，lisp 是哲學參照。**中間推導的缺口已展開成 26 條**（[cpu-to-os-gaps.json](cpu-to-os-gaps.json)，五層：CPU 前提／OS 核心機制／資源管理／方便人／橫向對比失效處），逐條待對應；另含使用者對「作業系統＝方便人使用」的四層定義 |
| [program-form](program-form.md) | **在 aos 上寫程式的形式**：類似 lisp，但原語是**檔案**、複合是**資料夾**，程式的載體就是資料夾；同像性的落點因此從 JSON 搬到檔案系統（改寫了 `G24`）。「只有 lisp 承載得了」**使用者同日收回**（改記為偏好，Python／Lua 也適合，因此同像性在撐什麼成了新問題），與四條邊緣狀況（資料夾無序、檔案更像 binding、哪棵樹正在被求值、quote 從哪來）。另含**寫的方式也是 lisp 的：REPL**——agent loop 就是 read-eval-print-loop、資料夾就是 image，以及它的四條裂縫——**使用者已裁決**：節奏差一個數量級不是缺陷（快／慢世界＋同時多個 REPL＋一次跑十幾分鐘很正常），其餘三條實作時自然有解 |
| [game-process-model](game-process-model.md) | **一次 `aos exec` ＝ 一格 `_process(delta)`**（2026-09-01 使用者口述）：能存取到的資料夾＝世界、cwd＝本體；決策照遊戲 AI 的 **GOAP**（觀察→目的→決策→行動）；超過預算的事等下一格。一次回應 `G01`（時鐘就是 tick）／`G09`（引擎從不搶佔，自願返回）／`G04`（GOAP plan ＝可存檔的架構狀態），但把 footprint 從「值得做」升為**必要條件**。同檔第三部分是同日口述的 **L1/L2 cache 類比**：判別式「刪掉它，世界語意變不變」——`run.pid`／`every/.last/` 是 cache、`every/<stem>.json` 不是、`turn` 之後會升格；ownership table 與 `.gitignore` 政策的分類判準 |
| [assembly-and-chains](assembly-and-chains.md) | **一段彙編語言＝一連串 `insts.json`**（2026-09-01 使用者口述）：`aos exec` 讀完就不管，下個指令從投遞收取——這台機器只有「當前」和「下個」，**沒有「未來十個」**；跳轉＝自己改下一格、中斷＝外部整個換掉；要規劃多步只能**指令自供給**。**裁決：留著批**，不退回單指令。觀察：中斷／跳轉可壓縮成「誰寫下一格」→ **pending 的投遞位就是 PC**；批式管線使中斷只落在 tick 邊界，C 區「沒有中斷線」可結；`deliver` 撞名的**碰撞規則是中斷語意的前置**（新開放項）；自供給＝CPS，容錯／`G16`／GOAP 三處付錢，建議 plan 檔＋游標檔（＝`G14` 載入器）；`inst`／鏈／批＝指令／行程／tick 三層，**`B1` 被三條線同時需要** |
| [theses-review](theses-review.md) | **根基三論的複審**（2026-09-01，主 session ＋兩個 fork；**全是 AI 觀察，不是裁決**）：同像性的承重點是**自我改寫**不是表達力（`G24` 該重問成「跑著的資料夾能不能被改寫再放回去跑」，`G07` 是它的代價、那個標記就是 quote）；CPU 與 REPL 唯一不矛盾的映射是**一句＝一回合＝一批、依賴一律跨回合**，兩讀法都靠批 header 餵飽；三要件分派錯位——**分支發生在 LLM 不在 tooling**，代價就是 `G05`；缺口分流——`G13` 與 `G18` 是唯二拖了會鎖死的，`fsync` 該插隊第一位 |
| [turn-based-folder](turn-based-folder.md) | 指定資料夾的回合制演化模型；`aos exec` 就是它的實作，抽象 CPU 疊在其上；`.aos` 版面、`.temp`／`.runi` 交接協定、`core/daemon` 與 agent loop |
| [llm-cpu](llm-cpu.md) | LLM CPU 疊在 `inst` 之上（`aos llm exec` + `.aos/insts/llm.json`）、自跑推理或當全域 daemon client 的取捨、跨資料夾排程與 I/O 交換區 |
| [inst-execution](inst-execution.md) | `inst` 的 env 繼承開關與非阻塞／背景執行策略 |
| [agent-messaging](agent-messaging.md) | agent 間訊息傳遞的語意失真為何無法用數學糾正、錯誤如何層層放大成錯誤風暴；三條對策：關鍵節點人類審核、多 agent 冗餘審核、固化 |
| [core-layering](core-layering.md) | `aos/core` 該切成哪幾個小專案：最核心 `exec`（`inst_t` + 執行它的函數，連 `timeout_ms` 都不要）→ `exec_loop` → 匯聚（注入式 lib）→ 再外面就當普通 inst，不繼續往外包 ；**已拿 [top-down-cli](top-down-cli.md) 的成品試跑過 B12 判準**：core 只差一個「分支」就封閉，agent 整套不進 core |
| [call-format](call-format.md) | 對 inst-POSIX 呼叫格式的兩輪拷問（已拆資料夾）：格式與序列化的九個缺口、fork/exec 是呼叫**機制**不是呼叫**約定**及界外六樣、以及不該動搖的部分。**使用者已逐條裁決** |
| [prior-work](prior-work.md) | 跨 repo 前作對照：`simple_tools/docs` 的 agent-world 設計（2026-08-12，比 aos 早兩天）逐條對上 aos 模型——Step／Round／tick 三尺度塌成一個「回合」、git 買不到 replay、path 不是 capability、「資料夾是世界」把表示當本體 |
| [top-down-cli](top-down-cli.md) | **從上到下的指令面**（2026-08-30，唯一從使用者介面倒推的一篇）：`aos pu init`／`aos pu run --step --interval`、`aos agent init`／`say`／`listen`／`talk --interface`／`state`；agent loop 靠「自我複製投遞」安插進 pu 迴圈；LLM 思考＝投遞到另一顆 llm pu 的 tempd |
| [machine-shape](machine-shape.md) | 這台機器的形狀（已拆資料夾）：真正的指令是**「批」而批沒有名字／header**、loop 沒有可分支的旗標、loop 現在住在 `core/inst` 裡與分層規劃相反、`.aos` 命名標準延伸不到 events／status、**唯一由外部生產者執行的投遞沒有實作**、規範已有三份真相 |

> **現況落差**：使用者已判定 `core/llms` 與 `core/tooljson` 是失敗作——它們不符合這裡
> 記的回合制／抽象 CPU 模型，之後要找時間改到符合。所以讀這些構想時別把現有程式碼
> 當成它們的實作。open 狀態記在 [SESSION-LOG](../../SESSION-LOG.md)。

> **落地順序**：這些構想要照什麼順序做、哪些決策擋著哪一階段，見
> [`roadmap`](../roadmap.md)。那份只排順序，模型定義仍以本目錄為準。

新增內容優先歸入既有主題；出現獨立方向時才新增內容檔。構想被正式 spec／plan 取代後，
在這裡改留指標，不讓 idea 文件與已拍板規格形成兩份真相。
