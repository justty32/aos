# 2026-10-15 JSON 格式族：沿用現有幾族、不依賴指示詞

← [討論紀錄](README.md)｜概念：[C-48](../docs/CONCEPTS/01-設計理念.md)｜相關：[N-35 `檔#/位置`](../docs/NORMS/01-總則.md)、[LLM kernel「json 就是這點好」](2026-10-15-llm-kernel.md)

## 原文（10-15，照記）

「除非必要，否則不要增添新的json格式設計，盡量沿用現有的那幾族：inst族、ctl, state那些。善用json可以隨意添加key之類的東西的靈活性，還有value可以是任意東西的靈活性。不要把指示詞納入正規設計，指示詞是用來拆分json檔案和讀env變數的，設計中對此的認知只要有"自己的一些檔案可以透過指示詞拆成小檔"這樣就好，不要依賴她。」

使用者補充（同日）：「任意添加key，代表可以弄一些只有自己看得懂的key，從而和其他功能共享此json格式，只是要注意key不可重疊。value可以是任意東西，這塊雖然在實作上會導致一些麻煩，但我覺得收益是夠的，就是要稍微權衡一下，如果太麻煩那就算了。最主要在於，我常常用的一套方式，就是類似指示詞那樣，一個值，除去他的字面純值之外，也可以用obj代表，這就好比lisp的(3)和(+ 1 2)一樣」

## 決定（使用者 10-15 定）

- 新東西的 JSON 先套現有的族（inst 族；ctl／state 窗族），靠多加 key、value 任意來擴充；除非必要不開新格式。→ 列為概念 C-48。
- **私有 key**：各功能可以在同一份 JSON 放只有自己看得懂的 key，藉此共享格式（例：agent.json 既是 fsm 表又放 `brain`／`tools`；inst 裡放 `_tool`／`_metainfo`）；前提是 key 不重疊。
- **私有 key 慣例**（使用者 10-15 准：「私有 key 慣例寫進 C-48」）：`_` 開頭的 key＝附註，宿主程式忽略、給別人看（例 `_tool`、`_metainfo`）；共用同一份檔的私有 key 真的撞名了才加功能前綴（例 `agent_`）；各 lib 說明頁列出自己認得的 key。→ 寫進 C-48。
- **值的雙形**：一個值可以是字面純值，也可以是物件（展開形），像 Lisp 的 `3` 與 `(+ 1 2)`；指示詞是這招的一種用法，`priority`（`"low"` 或 `{"level", "deadline"}`）、fsm 的格（一張 inst 或 `{"val", "next"}`）也是。實作麻煩就權衡；太麻煩的地方可以不支援物件形。
- 指示詞（`$ref`、`$env`）不進正規設計：它只是把 JSON 檔拆成小檔、讀環境變數的便利。規範與實作對它的認知只到「自己的一些檔案可以用指示詞拆成小檔」，不靠它才成立。

## 動工（10-15，使用者「都照建議」）

照 C-48 把現有幾處拉回 inst／ctl／state 族、去掉對指示詞的依賴：

1. **閘門的信＝inst 族**：信就是 target 那張 inst（key 攤在最上層、`cwd` 與串流路徑轉絕對、`_metainfo` 照留）＋私有 key `priority`、`reply`、`sent`（沒撞名，不加前綴）；呼叫者的 stdin 寫成旁檔 `reply/<名>.stdin`，信的 `stdin` 放路徑。kernel 把 `stdout`／`stderr` 填成 `reply/<名>.stdout`／`.stderr`（只在記憶體裡的信填，不回寫 `cur/` 的檔），直接跑那張信。回信＝N-30 結果（錯＝N-29 形狀）。兩種 kernel 共用同一套信箱函式。
2. fsm 格的 stdin：見 [意見 1～4](2026-10-15-opinions-1-4.md) Q2（fsm 不給格 stdin）。
3. 錯、tool 訊息、fsm 每拍那行都用 N-29／N-30 形狀；LLM kernel 的 state 用 loop 骨架名（`runs`、`beat`…）；閘門指信箱的 key 叫 `mailbox`。
4. 規範與 lib 說明的範例不以 `$ref`／`$env` 為預設；demo 的設定由 `run.py` 寫成完整檔，不靠指示詞。

### 動工自定點

- fsm 每拍那行：沒起成格（查不到格、MaxSteps）時 N-30 欄位是 null；`error` 是 `{"code", "msg"}`。
- tool 訊息的錯：不認得的工具、引數壞（代號主詞在前，`ToolUnknown`、`ArgumentsBad`，[命名盤點](2026-10-15-naming/盤點.md) P7）；inst 起不來照 inst 原代號。現行新程式的錯只有 stderr 一行、沒有代號（CONVENTION P-21）。
- 信的旁檔放 `reply/`、兩邊都從回信路徑推（`.json` → `.stdin`／`.stdout`／`.stderr`）；閘門被殺在 kernel 拿走之後，旁檔留在 `reply/`。
