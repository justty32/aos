# 彙編語言與指令鏈 — 導航

← [ideas](../README.md)｜上游 [game-process-model](../game-process-model.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

使用者口述（**2026-09-01**）的第四個心智模型，與 [game-process-model](../game-process-model.md)
同源（都在回答**機器怎麼跑**），但問的是更上面一格：**在這台機器上，一段「程式」是什麼形狀，
它怎麼往下走一步。** [turing-to-os](../turing-to-os.md) 講憑什麼是 CPU、
[program-form](../program-form.md) 講程式長什麼形、遊戲那篇講一格怎麼跑，這篇講**格與格之間**。

同日續述再往上走一級：**C 語言與彙編的區別怎麼對應到 inst serie**——那條線長出
**寫 → 編譯 → 執行**的三段式生產線。

> **節號 §一–§二十六 連續編號、跨檔沿用**（拆資料夾前的 §一–§十三 編號不變），
> 所以外部寫「§七」「§十一」「§十三」的引用照舊指得到。
> **使用者原話／裁決與 AI 觀察在每個檔裡分節標明**，別混引。

## 若只挑一件事看

**`B1`（批沒有名字／header）是全局最超載的未決點**——CPU 線、REPL 線、彙編線三頭同壓
（[series §十](series.md)）。

**彙編那條線**（上午口述，§一–§十三）：

| 檔案 | 裡面有什麼 |
|---|---|
| [interrupts](interrupts.md) | §一–§八。中斷＝外部換掉下一格／跳轉＝自己改下一格；一段彙編＝一連串 `insts.json`，只有「當前」和「下個」；規劃多步只能**指令自供給**；**裁決：留著批**。觀察：**pending 投遞位就是 PC**、中斷只落 tick 邊界、**碰撞規則是中斷語意的前置** |
| [series](series.md) | §九–§十三。觀察：自供給＝CPS，容錯／`G16`／GOAP 三處付錢；`inst`／鏈／批＝指令／行程／tick，鏈要 id →`B1`。口述：**loop 另讀 `series.json`**——一份檔兼行程表／PC／排程輸入／可見窗口，`B2` 有答案方向 |

**C 語言那條線**（同日續述，§十四–§二十六）：

| 檔案 | 裡面有什麼 |
|---|---|
| [c-language](c-language.md) | §十四–§十九。提問：C 與彙編的區別怎麼對應 inst serie。觀察：函數＝串模板、堆疊框＝臨時資料夾（**差別只在壽命不在住處**）、`f(g(x))` 拆平所以 `B3` 不用改、型別正面壓上 `B5`。裁決：串中可用**代號**；**暫存器與堆疊框兩種壽命都要** |
| [compile-pipeline](compile-pipeline.md) | §二十–§二十一。**裁決：複雜式另存新 json，由「我們的程式」確定性拆平才進 series，LLM 不出場**。觀察：於是有**寫（不確定）→編譯→執行（都確定）**三段式，`G19` 關在上游、replay 變可能，`G07` 自然長出 |
| [source-and-ir](source-and-ir.md) | §二十二–§二十六。那份新 json 是什麼檔。裁決依時序：源碼與 IR **兩個檔案** → **lisp 從源碼／IR 進場、界線在 `inst`** → 收工前改判**「lisp 太理想了」、全塔統一 json**，lisp 只留哲學 |

## 相關

- [game-process-model](../game-process-model.md)——同日同源：一次 exec ＝一格 `_process(delta)`
- [turing-to-os](../turing-to-os.md)——上游：agent loop ＝ CPU
- [program-form](../program-form.md)——程式的形式、REPL 讀法、資料夾無序那條裂縫
- [theses-review](../theses-review.md)——同像性的承重點是自我改寫、批 header 是共同地基
- [self-delivery-in-loop](../self-delivery-in-loop.md)——自我投遞埋不埋進 loop
- [machine-shape/instruction](../machine-shape/instruction.md)、[machine-shape/debts](../machine-shape/debts.md)
- [verdicts](../verdicts.md)、[cpu-to-os-gaps](../cpu-to-os-gaps.json)
