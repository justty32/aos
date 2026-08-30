# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **2026-08-30 晚：原型第二輪落地**（main）——`core/tool`（`aos tool`／`aos contact`／`aos say --to`）、
  `core/tick`（heartbeat on aos）、pi 當第二顆 CPU、排程保底 D（flock 槽，`aos llm --priority`）。
  **已知缺口**：`aos agent step` 走 lmstudio 那條還沒取槽（只對 `aos llm` 子命令成立）；使用者＝agent 住 `~`
  （say 的 `from`、`--to ~`）未做；pi 工具繞過 inst 先接受。試用 L1／L2 在跑，發現進
  [dispatch/trial](workflows/dispatch/trial/README.md)，之後開修 bug 隊與改進隊。

- **2026-08-30 最小原型已落地（main `adcb5bc`）**：五個新核心小專案 `core/exec`／`wire`／`loop`／`llm`／`agent`，
  指令 `aos run`／`deliver`／`llm`／`agent`；協定在 [dispatch/proto/PROTOCOL](workflows/dispatch/proto/PROTOCOL.md)，
  兩隊報告在 [proto/reports](workflows/dispatch/proto/reports/)。舊 `core/inst`／`llms`／`tooljson` 原地未動，
  **要不要刪、何時刪未定**。刻意跳過的邊緣狀況（無鎖、無崩潰恢復、不 fsync、agent 靜默死亡、stop）
  列在各小專案 README 與 [self-delivery-in-loop](workflows/ideas/self-delivery-in-loop.md)。pi 介面沒做 adapter，
  只交 [pi-interface](../core/agent/docs/pi-interface.md)。

> **等使用者一句話的項目已集中到 [WAIT_USER](WAIT_USER.md)**（2026-08-30）——下面各條保留
> 脈絡，但「還在等誰、卡在哪一句」以那份為單一入口，別在這裡逐條翻。

- **2026-08-29 `roadmap-run` 分支已凍結，系統要重新架構。** 那條分支跑完 M0–M2
  （instruction 執行器 ＋ `core/loop` 回合機，202 檔／+18,326 行／46 commits），
  使用者決定**不在既有結構上繼續改，全部打掉重來**——理由是一改再改的成本高過
  拿著已驗證的結論重寫。**M3／M4 的規劃就此作廢**（原文仍在那條分支上可查）。
  凍結點 `5b74b47`，tag `frozen/roadmap-run-2026-08`，**未 push**。
  **有價值的東西已打撈成 [wf/salvage/](salvage/README.md) 七篇**——`.aos/` 版面與交接協定
  裡哪些真的被攻擊腳本打過、踩過的坑（含併發重複執行那條）、哪些設計是刻意的、
  還沒解的問題、程式碼哪些值得抄、以及這套多隊協作流程本身的成敗。
  **要重寫這個系統的人，從那包開始讀，不要從 `roadmap-run` 開始讀。**

- **2026-08-28 拷問停打，轉入實作。** 新開 [roadmap](workflows/roadmap.md) 工作流：
  M0 立法（normative SPEC）→ M1 批 header → M2 deliver/PC/修 bug → M3 exec_loop 落地
  分層（§25/§26 必裁）→ M4 status/recover/check → M5 第二顆 CPU（四項存貨閘門）。
  動工前查 roadmap，裁決記回 ideas＋verdicts。

- **2026-08-28 對 aos 核心模型做了十輪拷問**（格式／原語／CPU 類比／交接協定／前作對照／
  機器形狀；第十輪由 Fable 重打「地位的承載物」，九條全未裁——使用者：邊實作邊想，
  記在 [machine-shape](workflows/ideas/machine-shape/README.md) 三檔 §22–30）。裁決總表在 [ideas/verdicts](workflows/ideas/verdicts.md)——**要重新拷問
  的人先讀那份**。open 的部分：**「批」沒有名字與 header**（一次卡住 ISA 版本、指令來源、
  loop 的旗標暫存器與去重）、**decode 卡在錯的一層**、外層契約還沒想好、跨資料夾排程歸屬
  未定。另有三筆「裁決相乘」的欠帳（兩顆 CPU 沒有記憶體模型、沒有中斷線、git 撞
  `.aos/` 暫態）記在 [machine-shape/debts](workflows/ideas/machine-shape/debts.md)。
  新驗證出的實作缺陷已進 [gotchas](workflows/common/gotchas.md)（`.runi` 不是鎖、沒有
  `fsync`、彙整崩潰窗口、`--loop 0` 是忙碌輪詢、失敗關掉節流閥）。
- **2026-08-25 研討會收場**（[最後總結](workflows/workshop/records/final-summary.md)，
  1500 字，第一節就是「他不必回答的問題」）。八場的問題收成
  [OPEN-QUESTIONS](workflows/workshop/OPEN-QUESTIONS.md)，白話背景資料收成
  [BACKGROUND](workflows/workshop/BACKGROUND.md)（拆成 17 檔）。四個 codex session 已結束。
- **2026-08-25 第一次實測：[T5 agent loop](workflows/experiments/t5-agent-loop.md)**
  ——使用者說「不想看了，你直接去試」。**T5 驗收沒全過。** 假模型的三回合閉環跑通、
  回合之間人工插手下一回合看得到、沒有常駐 process；但**「Ctrl-C 之後從斷點繼續」
  只在 `--loop` 的優雅收尾下成立**，單次 `aos exec` 真被 SIGINT 中止會留 `.runi`、
  下一次固定退出 3，人工搬回去只能**重播整批**，而且外部作用可能已經做過。
  **這是 roadmap 的驗收條件與 `.aos` 規格第六節互相矛盾**，要拍板哪一邊改。
  另外抓到三處規格與實作對不上（退出碼表不完整、`<pid>.json` 無法表達同一 process
  多次投遞、SIGINT ＋ process group 會產生沒有恢復契約的 unknown）。
  產出五支子命令的規格：`aos deliver`／`aos recover`／`aos status --json`／
  `aos agent step`／`aos agent emit-context`。**真模型沒跑通**（codex 被沙盒擋、
  Claude OAuth 過期、WSL 沒裝 pi），下次要補。
- **研討會的紀錄全部在 [workshop/records/](workflows/workshop/README.md)**——2026-08-25
  這一天跑了七場（核心行程／四個懸而未決的選擇／agent loop 架構／回頭審視／隨意發想／
  用 aos 實現 workflows／跟現有工具協作），已收場，**過程不再列在這裡**。
  **仍然開著的只有下面三件：**
  - **四個設計選擇仍未拍板**（World 抽象、`kernel.json` 要不要分層合成、子行程拓樸
    A／B／先固定磁碟 ABI、親緣綁路徑還是 UUID）。使用者已表態的部分見
    [四選擇那份紀錄](workflows/workshop/records/four-open-choices-tradeoffs.md)。
    **他明講「窩不想看惹」**，所以方向是**用實測取代拍板**——見上面 T5 那條，
    以及各題的「最小的驗證方式」（[BACKGROUND](workflows/workshop/BACKGROUND.md)）。
    **2026-08-26 開了 [hackathon 工作流](workflows/hackathon/README.md)**（多 agent 各自動手做、只收坑），那 20 條就是它的題庫。
    **第一場已跑完三輪**（題目＝OPEN-QUESTIONS 第 2 題「近期 core 要回撤到哪裡」，    Carmack／Armstrong／Cantrill／Thompson 四個 persona 實作、Torvalds persona 評分）：
    紀錄在 [records/core-scope/](workflows/hackathon/records/core-scope/README.md)，    **從白話導讀讀起，等使用者拍板**。四位的場地留在 WSL `~/aos-hack/core-scope/`（thread id 在紀錄檔頭，還能續）。
  - **[辯論風格那場的四件轉交提案還沒拍板](workflows/workshop/records/pre-agent-loop-core.md)**：
    `deliver`／`aos enqueue` 插進 T5 之前、「回合中途死掉的洞」歸 roadmap 第六節、
    `k/`／`c/` 兩層命名進 `.aos` 標準、有限資源獨立成 idea。**都是改規格文件，要人拍板。**
  - **兩場更早的 workshop 沒收攏**：
    ① **[有限資源／CPU 怎麼指揮 GPU](workflows/workshop/records/finite-resource-queue.md)**
    只跑了 R1，五位一致要「使用者層級的 endpoint 佇列」，撞上 roadmap 第六節。
    **但 2026-08-25 使用者提出「外部處理器自己監控一個資料夾、甚至不必引用 aos lib」之後，
    這個衝突可能已經自己解掉了**（排隊是外部處理器的家務，不是 aos 的）——續場先確認這件事。
    ② **[lisp 在 .aos 裡長什麼樣](workflows/workshop/records/lisp-in-aos.md)**
    只跑了 3 位，**缺維運與獨立開發者**。

- **`core/llms` 與 `core/tooljson` 目前是失敗作，之後要重做**：使用者判定這兩個小專案
  不符合 aos 的回合制／抽象 CPU 模型（模型見
  [ideas/turn-based-folder](workflows/ideas/turn-based-folder.md) 與
  [ideas/llm-cpu](workflows/ideas/llm-cpu.md)），要**找時間讓它們符合這套模型**。還沒
  排期。**2026-08-24 使用者拍板：先不動、先不管，要排在 agent loop 之後**（[roadmap
  的 D4](../docs/roadmap.md)）。所以這兩個小專案現在是**擱置**，不是待修——別急著重寫，
  也別再往裡面投資。連帶：llmkit 移植的 S2／S5 一起停用。
- **主線是回合制模型的 T0–T6**：`.aos` 規格在
  [`docs/aos-folder.md`](../docs/aos-folder.md)（**唯一真源**），指示詞設計在
  [`docs/inst-directives.md`](../docs/inst-directives.md)，順序在
  [`docs/roadmap.md`](../docs/roadmap.md)，模型的理由在
  [`wf/workflows/ideas/`](workflows/ideas/README.md)。`core/inst` 已解凍。
  **進度**：**T0–T4 全部落地，`core/inst` 這一輪要做的都做完了**——三個指示詞
  （`$opt`／`$env`／`$ref`）、`resolve` 分層、`parallel` 欄位、`aos init`／
  `aos exec [folder]`／`aos exec --loop <毫秒>`、handoff 分層（彙整／取件／釋放，
  公開 API 且以 instruction 檔路徑為參數，所以其他 CPU 可以直接重用同一套協定）。
  `aos inst` 子命令已刪。`core/inst/src` 現在有五個分層：inst ← format ← handoff、
  inst ← format ← resolve、inst ← exec。
  **下一步照 roadmap 是 T5 agent loop**——用外部 LLM CLI，**不需要新的 C++**，
  產出是規格（哪裡痛就是 `aos agent` 該收掉的東西），不是程式。
- **2026-08-24 回頭審查整套東西**，抓到兩個 bug（都已修，`b70a016`）：`--loop 0`
  會空轉吃掉一顆核心（實測 3 秒 292 個 CPU tick，修正後 13）、以及合法但沒有任何
  instruction 的空投遞永遠不會被消化。文件也回頭同步了（`9701f21`）——規格開頭還
  寫著「尚未實作」。
  **審查找到但還沒做的兩個缺口**，已記進
  [`.aos` 標準第十二節](../docs/aos-folder.md)的「仍然開著的」：
  1. **投遞那一步沒有實作**。三步協定裡彙整／取件／釋放都有函式，只有投遞
     （先寫 `.temp` 再 `rename`）沒有。整套協定的安全性靠的就是這一步，現在它是
     口頭約定。**這是 T5 最直接的前置條件**——agent loop 的第一個動作就是產生指令。
  2. **「世界」本身沒有抽象**。handoff 三支以 instruction 檔路徑為參數（所以已經
     能對 `insts/llm.json` 用），但「`.aos` 在不在」「`version` 認不認得」
     「`chdir` 到哪」寫死在 `aos exec` 裡。等 `aos llm exec` 出現要嘛複製一份、
     要嘛那時再抽。
- **程式由 codex 寫、我審查**：codex 裝在 WSL（`~/.local/bin/codex`），任務書放
  `/tmp/aos-task*.md`。我出規格與驗收條件、審 diff、獨立重跑 ctest，再決定 commit。
- **建置環境是 WSL**：vcpkg 在 WSL 的 `~/dev/vcpkg`（Windows 那側沒有）。
  `git clone --depth 1` 的 vcpkg 會缺 `vcpkg.json` 指定的 baseline commit，
  要 `git fetch --depth 1 origin <sha>` 補，不必 unshallow。repo 在 `/mnt/c` 上，
  建置比原生慢，且會出現 clock skew 警告。
- **llmkit 移植還沒完**：`reference/llmkit/` 是從 freepy 搬來的 python 原文，計畫與五個階段在 [`reference/PORTING.md`](../reference/PORTING.md)。S1／S3／S4 已落地（`core/tooljson` 外殼與 `core/llms` 全部），**S2 卡在待使用者的決策**（見 [WAIT_USER](WAIT_USER.md)），**S5 未開始**（兩個小專案的 `docs/`、外部消費測試、刪掉整個 `reference/`）。`reference/` 在移植驗完之前不要刪。
- **`aos tooljson run` 還不能用**：S1 只做到「讀 spec、驗證、展開 argv」，`ExecBody::run()` 目前回一句「尚未實作」。要能真的跑起來得先做 S2。
- **C ABI 尚未補齊**：目前只有 `inst` 有 `<aos/inst.h>`；`tooljson` 與 `llms` 都還沒有。使用者明確表示這塊之後再慢慢加，現階段不動它。
- **相依管理**：`aos_common_private`（`common/CMakeLists.txt`）目前仍只有 nlohmann。curl 這顆重量級相依 2026-08-23 進來了，但**照判準直接走 `core/llms` 的 `PRIVATE_DEPS`**，沒有進 `aos_common_private`，所以還不需要「具名 bundle」那層。真正的觸發點是相依長到四五個以上，判準見 [`docs/subprojects.md`](../docs/subprojects.md)。

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
