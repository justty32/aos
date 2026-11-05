# 主線階段 T0–T6

← [roadmap 導覽](README.md)｜[文件索引](../README.md)

> 這個檔裝的是：主線階段 T0～T6，每一階段做什麼、驗收條件是什麼。要知道「接下來做哪一塊」就查這裡。

## 三、主線階段

每階段獨立驗收，前一階段沒綠不進下一階段。

### T0 — `inst` 的 schema 擴充　**【已完成】**

`core/inst` 核心層已解凍。這一批要動 `format.cpp` 與 `exec.cpp`，兩件事排在一起做：

1. **[D3](decisions.md#d3) 的 non-blocking 欄位** — 每筆指令自帶「要不要開 thread」，`aos exec` 等
   所有 thread 收完才算回合結束。
2. **`$` 指示詞** — `$opt`／`$env`／`$ref`，設計與實作順序見
   [inst 的 `$` 指示詞](../inst-directives.md)。第一步 `$opt` + `stderr` merge 最小，直接
   解掉 [D5](decisions.md#d5)。

**驗收**：`stderr` 併流真的交錯（不是互相蓋寫）；non-blocking 那筆之後下一筆立刻啟動，
而回合仍等到所有 thread 收完。

### T1 — `aos exec <folder>` 與 `aos init`：回合原語　**【已完成】**

規格見 [`.aos` 標準](../aos-folder.md)。這一階段要做出來的是：

- **`aos init <folder>`** — 建立 `.aos/`，寫下 `version`。
- **`aos exec <folder>`** — 讀 `<folder>/.aos/inst.json`，消費一回合。沒有 `.aos/`
  就報錯，不自動建（[標準第十一節](../aos-folder.md)）。
- **路徑基準統一成 `<folder>`** — 最省事的作法是一開始就 `chdir` 過去
  （[標準第四節](../aos-folder.md)）。這會改變 `inst` 現有的路徑語意，是刻意的。
- **`version` 不認得就停**，不要盡力而為（[標準第九節](../aos-folder.md)）。
- 附一份 `.gitignore` 樣板：**整個 `.aos/` 都不進 git**（[標準第十節](../aos-folder.md)）。

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
| 兩支 `aos exec` 同時跑同一個資料夾 | `.runi` 已存在就**拒絕啟動**（[D6](decisions.md#d6) 已定） |

命名標準（[D1](decisions.md#d1)）：`<名字>.<副檔名>.<狀況>`——第一個 `.xxx` 是副檔名，第二個是當前
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
[`.aos` 標準第六節](../aos-folder.md)的「彙整的規則」：檔名字典序但投遞者不得假設順序、
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
約一整顆核心（見[標準第十二節](../aos-folder.md)）。

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

[D4](decisions.md#d4) 把 `core/llms`／`core/tooljson` 排到 agent loop 之後。乍看奇怪——沒有 LLM 函
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

> **⚠ 驗收最後那一句和 [D6](decisions.md#d6) 互相矛盾，還沒拍板。**
> D6 已定「`.runi` 存在 → 拒絕啟動、退出碼 3、把現場留給人」，那就**不可能**「再 `aos exec`
> 一次就從斷點繼續」。2026-08-25 的實測（[wf/workflows/experiments/t5-agent-loop.md](../../wf/workflows/experiments/t5-agent-loop.md)）
> 證實了這點：`--loop` 只在**回合邊界**能優雅停下；單次 `aos exec` 真的被打斷會留下 `.runi`，
> 只能整批重放，而外部效果可能已經發生。
>
> 兩條路擇一，**由使用者決定**：①改本節的措辭，承認「續跑」＝回合邊界，不是任意斷點；
> ②在規格裡長出真正的復原路徑（`aos recover`／逐筆記錄已完成的 instruction）。
> **在拍板之前，不要照這條驗收去實作。**

**這一階段的產出不是程式，是規格**：腳本裡哪些地方重複、哪些地方難寫，就是 `aos agent`
與 T6 要收掉的東西。實測已經替這一階段列出五支想要的子命令
（`aos deliver`／`recover`／`status --json`／`agent step`／`agent emit-context`），
見上面那份實驗紀錄。

### T6 — 把 LLM 內化：`aos llm exec <folder>`<a id="t6"></a>

> 這一階段才碰 `core/llms`／`core/tooljson`（[D4](decisions.md#d4)）。T5 沒跑出痛點之前不要開工。

**`aos llm` 是 module，不是 core**（已定）。它會是一層**薄殼**——實作時甚至可能直接把
工作轉交給 Python。這跟模型完全一致：交接本來就是 `exec`，所以「用什麼語言實作那顆
CPU」根本不是 aos 要回答的問題。

這也回頭改變了 `core/llms` 的處境：如果 `aos llm` 只是薄殼加外部程式，那顆 C++ 的 LLM
client **可能根本不會被復活**，而是被繞過。所以 [D4](decisions.md#d4) 的「先不動」不只是延後，也
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
