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
> [`docs/roadmap.md`](../../../docs/roadmap.md)。那份只排順序，模型定義仍以本目錄為準。

新增內容優先歸入既有主題；出現獨立方向時才新增內容檔。構想被正式 spec／plan 取代後，
在這裡改留指標，不讓 idea 文件與已拍板規格形成兩份真相。
