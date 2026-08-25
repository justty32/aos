# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [DEV-GUIDE「結構整理原則」](DEV-GUIDE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **2026-08-25 再開一場：[四個懸而未決的設計選擇，各自的優缺點](workflows/workshop/records/four-open-choices-tradeoffs.md)**
  （R1 跑完；四位**全新的人**，同樣四種身份）。使用者原話「我還沒想好，我想多了解這四件事的
  優缺點」——四題是 World 抽象、`kernel.json` 要不要分層合成、拓樸 A／B／先固定磁碟 ABI、
  親緣綁路徑還是 UUID。**紀錄由「書記」寫的**（見 [workshop README](workflows/workshop/README.md)
  的〈書記〉），主持人沒有讀內容，只確認他沒動別的檔。**四題都還沒拍板。**
- **2026-08-25 新開一場 workshop：[核心行程、子行程，與外部處理器的契約](workflows/workshop/records/core-process-and-subprocess.md)**
  （R1 跑完，四位：工程師／架構師／研究人員（OS）／外部開發者；`xhigh`；**普通用戶被使用者
  拿掉**，所以缺「人看不看得懂」的視角）。**最該讓使用者知道的一件事**：使用者提的
  「尾部指令把下個系統指令放回 `inst.json`」，**四位獨立地都反對，而且給出同一個替代版本**
  ——用一份版本化的 `.aos/kernel.json` 宣告序言／尾聲，`aos exec` 在取件時合成
  「序言＋批次＋尾聲」；系統指令仍是普通 instruction、仍在頭尾，只是**耐久性歸機器不歸指令**。
  理由是尾指令失敗一次就永久斷鏈、crash 會遺失、重跑會增殖。第二件：**多核＝多個 lane，
  不是多個 writer**——`.runi` 只鎖 queue、鎖不住世界，四位都點名。
  **轉交提案兩條，未拍板**（World 抽象、`kernel.json` 要不要進 `.aos` 標準版面）。
  R1 的四個 codex session 留著沒關，session id 記在紀錄檔裡，R2 用 `codex exec resume` 接續
  （**只在公司那台 Windows 有效**）。
- **兩場 workshop 開著沒收攏**（[workshop](workflows/workshop/README.md)，2026-08-24 開場）：
  ① **[有限資源／CPU 怎麼指揮 GPU](workflows/workshop/records/finite-resource-queue.md)**
  ——R1 五位都發言了，還沒 R2。**最該讓使用者知道的一件事**：五位獨立地都把 endpoint 佇列
  放到**使用者層級**（`$XDG_STATE_HOME/aos/llm/<endpoint>/`），這**直接撞上 roadmap 第六節
  「不做全域 daemon 與跨資料夾排程」**，而且不是為了挑戰它，是從「endpoint 是跨資料夾共享的」
  推出來的。② **[lisp 在 .aos 裡長什麼樣](workflows/workshop/records/lisp-in-aos.md)**
  ——只跑了 3 位（**缺維運與獨立開發者**，續場先補這兩位）。
  兩場的**轉交提案都還沒拍板**，主持人不自己改 `docs/`。
  > **①這場的 R2 先擱著**：2026-08-25 使用者提出「外部處理器自己監控一個資料夾、
  > 甚至不必引用 aos lib」，這把佇列的歸屬從 aos 挪到外部處理器身上——
  > **roadmap 第六節「不做全域排程」與五位要的「使用者層級佇列」就不再打架**（排隊是外部
  > 處理器的家務）。等核心行程那場談完，R2 會準得多。
- **[辯論風格那場的轉交提案等使用者拍板](workflows/workshop/records/pre-agent-loop-core.md)**：
  `deliver`／`aos enqueue` 插進 T5 之前、「回合中途死掉的洞」歸 roadmap 第六節、
  `k/`／`c/` 兩層命名進 `.aos` 標準、有限資源獨立成 idea。**這四件都是改規格文件，要人拍板。**
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

> 〔模板說明〕某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
