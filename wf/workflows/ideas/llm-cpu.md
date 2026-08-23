# 全域 LLM CPU 與跨資料夾排程

← [ideas](README.md)｜[回合制資料夾](turn-based-folder.md)｜[WORKFLOWS](../../WORKFLOWS.md)

## 目前的工作模型（尚未最終拍板）

基礎的 `aos daemon` 可以用 CPU 的 fetch–execute loop 理解：定期檢查指定資料夾的
instruction，抓取下一條，執行它，然後再抓下一條。資料夾是世界狀態，instruction
檔案則是等待處理器取得的指令流。

LLM 是另一種 CPU，但它是有限資源，不能假設每個資料夾都擁有一顆。因此
`aos llm daemon` 是**全域服務**：管理所有已納管資料夾的 LLM instruction queue，
並安排它們使用 LLM CPU 的先後順序。

這是目前偏向的分離式模型，不是不可更改的結論。更早的構想是讓 `aos exec` 成為所有
工作的唯一入口，LLM 導向與排程都藏在 `aos exec` 內部；使用者仍在考慮兩者取捨。

```text
folder A/.aos/inst/llm.json ─┐
folder B/.aos/inst/llm.json ─┼→ aos llm daemon → 全域排程 → LLM CPU
folder C/.aos/inst/llm.json ─┘                         ↓
                                      思考／使用工具／推進對應 folder
```

- 每個資料夾仍以 `.aos/inst/llm.json` 提交自己的 LLM instruction。
- 全域 daemon 負責發現／管理這些資料夾，而不是每個資料夾各自啟動一支 LLM daemon。
- daemon 從所有待處理 instruction 中選出下一筆，取得有限的 LLM 執行資源，並把結果
  作用回該 instruction 所屬的資料夾。
- agent loop 是 LLM CPU 的離散 fetch–execute 循環：一個 LLM 回合結束後，如需繼續，
  再為該資料夾排入下一條 LLM instruction。
- 一般 process daemon 與全域 LLM daemon 是兩種不同處理器：前者執行 process
  instruction，後者負責跨資料夾調度推理資源。

## 入口架構的兩個方向（尚未拍板）

### A：單一 `aos exec` 入口

最早的模型是讓 `aos exec` 承擔全部職責：所有 instruction 都先進 `aos exec`，需要
LLM 的工作由它在內部辨識、導向並排程模型呼叫。

優點：

- 對使用者只有一個入口與一套投遞方式，模型簡單。
- process／LLM／其他處理器的路由細節都藏在內部。
- 可以在同一處統一 instruction 順序、狀態與錯誤回報。

風險：

- 解析、process 執行、LLM 金鑰、網路、排程與長期狀態都集中在同一個行程。
- 任一類工作造成 crash、deadlock、記憶體耗盡或安全問題，都可能拖垮所有功能。
- 權限與資源邊界難切；`aos exec` 會成為過大的單點故障域。

### B：處理器分離，透過 I/O 交換區溝通

目前的全域 LLM daemon 構想更像硬體 I/O：一般 CPU 想使用 GPU 時，先準備輸入、開闢
特定交換區並提交指令；提交後 CPU 不必同步等 GPU，可以繼續自己的 instruction。
等 CPU 之後真的需要結果時，再回來檢查交換區中的狀態與輸出。

```text
process CPU
    準備 LLM input／交換區
    提交 LLM instruction
    繼續執行其他 instruction ───────────────┐
                                             │
global LLM CPU daemon                        │
    排程 → 推理／工具 → 寫回狀態與結果       │
                                             │
process CPU 需要結果時 ← 回來查交換區 ──────┘
```

這裡的 `.aos/inst/llm.json` 是「向 LLM CPU 發指令」的候選入口；實際交換區還需要能
表達 request identity、輸入快照、pending／running／done／error 狀態與結果。確切布局
尚未決定。

優點是故障、權限與資源可以隔離，LLM 的有限容量也由專門調度器管理；代價則是協定、
狀態機、交換區清理與跨處理器同步都比單一入口複雜。

> 目前不把 A 或 B 寫成定案。後續思考可能選其中一個，也可能保留 `aos exec` 作為表面
> 單一入口，但在內部用獨立行程／daemon 實作風險隔離。

## 排程器的責任

- 維護納管資料夾與其待處理 LLM instruction。
- 控制同時使用的 LLM 資源數量，不能因資料夾增加就無上限並行呼叫模型。
- 決定不同資料夾之間的服務順序，並避免某個長期 agent 永久餓死其他資料夾。
- 將執行中的 LLM 工作、結果與錯誤準確歸屬回原資料夾。
- daemon 重啟後仍能辨認尚未處理、正在處理或需要恢復的工作。

## 開放問題（尚未拍板）

- 「全域」的邊界：每個 OS 使用者、每台機器，還是某個明示 workspace 集合一支 daemon。
- 資料夾如何註冊、移除與被發現；daemon 是否掃描固定根目錄，或維護持久 registry。
- 正式命令名稱是 `aos llm daemon`，還是配合目前小專案名稱 `llms` 使用
  `aos llms daemon`。
- 排程策略：FIFO、round-robin、優先權、配額或可插拔策略；使用者介入能否提高優先權。
- LLM 容量如何建模：全域單一 slot、每 endpoint／model／key 各自限流，或同時受多層
  concurrency 與 rate limit 約束。
- 一次 agent tool loop 會持續占用 LLM slot，還是每次模型呼叫後釋放、下回合重新排隊。
- LLM instruction 是否沿用「完整讀入 → 立刻刪除 → 執行」；全域 daemon crash 時如何
  恢復已取得但未完成的工作。
- 多個 daemon instance 如何互斥，避免同一份 instruction 被重複取得。
- LLM CPU 與一般 process CPU 同時修改同一資料夾時的鎖定、回合順序與因果關係。
- LLM CPU 產生的下一回合寫入共用 `.aos/next/`，還是 processor 專屬 queue。
- `.aos/inst.json` 與 `.aos/inst/llm.json` 最終是否統一成
  `.aos/inst/<processor>.json` 布局。
- 是否能同時保留 A 的簡單介面與 B 的隔離：`aos exec` 只當 router／client，真正執行
  交給不同 daemon，而不是全部職責都留在 `aos exec` 行程內。
- I/O 交換區的 request ID、狀態機、結果格式、持久化、取消、逾時與垃圾回收協定。
- process CPU 何時、用 polling／通知或後續 instruction 回來取得 LLM 結果。
- 提交 LLM 工作後，哪些後續 process instruction 可先執行，哪些必須宣告依賴並等待結果。
