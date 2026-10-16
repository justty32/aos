# 2026-10-15 JSON 格式族：沿用現有幾族、不依賴指示詞

← [討論紀錄](README.md)｜概念：[C-48](../CONCEPTS/01-設計理念.md)｜相關：[N-35 `檔#/位置`](../NORMS/01-總則.md)、lib directives.md（10-15 深夜 KISS 批次 1 併進 `aos_cli.py`、本檔刪，見 git 歷史 cb20249a）、[LLM kernel「json 就是這點好」](2026-10-15-llm-kernel.md)

## 原文（10-15，照記）

「除非必要，否則不要增添新的json格式設計，盡量沿用現有的那幾族：inst族、ctl, state那些。善用json可以隨意添加key之類的東西的靈活性，還有value可以是任意東西的靈活性。不要把指示詞納入正規設計，指示詞是用來拆分json檔案和讀env變數的，設計中對此的認知只要有"自己的一些檔案可以透過指示詞拆成小檔"這樣就好，不要依賴她。」

使用者補充（同日）：「任意添加key，代表可以弄一些只有自己看得懂的key，從而和其他功能共享此json格式，只是要注意key不可重疊。value可以是任意東西，這塊雖然在實作上會導致一些麻煩，但我覺得收益是夠的，就是要稍微權衡一下，如果太麻煩那就算了。最主要在於，我常常用的一套方式，就是類似指示詞那樣，一個值，除去他的字面純值之外，也可以用obj代表，這就好比lisp的(3)和(+ 1 2)一樣」

## 決定（使用者 10-15 定）

- 新東西的 JSON 先套現有的族（inst 族；ctl／state 窗族），靠多加 key、value 任意來擴充；除非必要不開新格式。→ 列為概念 C-48。
- **私有 key**：各功能可以在同一份 JSON 放只有自己看得懂的 key，藉此共享格式（例：agent.json 既是 fsm 表又放 `brain`／`tools`；inst 裡放 `_tool`／`_metainfo`）；前提是 key 不重疊。
- **私有 key 慣例**（使用者 10-15 准：「私有 key 慣例寫進 C-48」）：`_` 開頭的 key＝附註，宿主程式忽略、給別人看（例 `_tool`、`_metainfo`）；共用同一份檔的私有 key 真的撞名了才加功能前綴（例 `agent_`）；各 lib 說明頁列出自己認得的 key。→ 寫進 C-48。
- **值的雙形**：一個值可以是字面純值，也可以是物件（展開形），像 Lisp 的 `3` 與 `(+ 1 2)`；指示詞是這招的一種用法，`priority`（`"low"` 或 `{"level", "deadline"}`）、fsm 的格（TARGET 字串或 `{"target", "next"}`）也是。實作麻煩就權衡；太麻煩的地方可以不支援物件形。
- 指示詞（`$ref`、`$env`）不進正規設計：它只是把 JSON 檔拆成小檔、讀環境變數的便利。規範與實作對它的認知只到「自己的一些檔案可以用指示詞拆成小檔」，不靠它才成立。

## 動工（10-15，使用者「都照建議」）

照 C-48 把現有幾處拉回 inst／ctl／state 族、去掉對指示詞的依賴：

1. **閘門的信＝inst 族**：信就是 target 那張 inst（key 攤在最上層、`cwd` 與串流路徑轉絕對、`_metainfo` 照留）＋私有 key `priority`、`reply`、`sent`（沒撞名，不加前綴）；呼叫者的 stdin 寫成旁檔 `reply/<名>.stdin`，信的 `stdin` 放路徑。kernel 把 `stdout`／`stderr` 填成 `reply/<名>.stdout`／`.stderr`，直接 `aos_inst.run(信)`。回信＝N-30 結果（錯＝N-29 形狀）。兩種 kernel 共用的信箱函式收進 `aos_mailbox.py`（`aos_kernel.py` 312 → 245 行）。
2. **fsm 格的 stdin**＝fsm 設定本身＋一個 key **`fsm_state`**（起格前讀到的 state 窗整份；不叫 `state`，因為設定裡 `state` 是窗的路徑）。原本 `{state, step, prev, cfg}` 與 prev 三種形狀作廢：被殺一半＝`fsm_state.running` 為 true；進 error 格＝`phase` error＋`last_error`＋新 key **`error_from`**（原狀態），`data` 照留。
3. **N-40 外層 cfg 當預設**：內層 fsm 被當格跑時，stdin（外層設定）裡內層沒寫的 key 才用；demo `think/fsm.json` 只寫表、不再 `$ref`。
4. 小改名：`ask` 的錯、tool 訊息、fsm 每拍那行都改成 N-29／N-30 形狀；LLM kernel 的 state 用 loop 骨架名（`runs`、`beat`…）；閘門 `kernel` → `mailbox`（`AOS_KERNEL` 照舊當後備）。
5. 規範去指示詞：N-22、N-35、N-37～N-40 修字；lib 說明的範例不以 `$ref`／`$env` 為預設，README 把 directives.md 移到最後當語法糖。
6. demo fsm／kernel 不靠指示詞：設定由 `run.py` 寫成暫存資料夾裡的完整檔（fsm 的 `bind()` 填執行期的 key，內層 state 用 `--state` 旗標）。

### 動工自定點

- 內層不繼承 fsm 自己的 key（`start`、`states`、`end`、`state`、`ctl`、`lock`、`max_steps`、`max_fails`）與 `fsm_state`：繼承外層 lock 會撞鎖、state 會撞窗。
- 內層只在 stdin 是**一般檔**時讀它當預設（fsm 跑格時就是）；終端機、pipe、/dev/null 不讀，不會卡住。這是 N-21「給 TARGET 就不讀 stdin」對內層 fsm 的例外，已寫進 N-40。
- fsm 每拍那行：沒起成格（查不到格、MaxSteps）時 N-30 欄位是 null；`error` 改成 `{"code", "msg"}`，state 窗的 `last_error` 照舊是「代號: 白話」字串。
- tool 訊息的錯誤代號：`UnknownTool`、`BadArguments`、`Skipped`、`Interrupted`，inst 起不來照 aos_inst 原代號。
- `ask` 的錯照舊吐在 stdout（讓 tool 格把它交給模型），只改形狀；`MaxTicks` 的 `partial` 放在旁邊。
- 旁檔放 `reply/`、兩邊都從回信路徑推（`.json` → `.stdin`／`.stdout`／`.stderr`）；閘門被殺在 kernel 拿走之後，旁檔留在 `reply/`（同以前的回信）。kernel 只在記憶體裡的信填 `stdout`／`stderr`，不回寫 `cur/` 的檔。
- LLM kernel 的 state 拿掉 `kind`；log 與 stdout 摘要的 `tick` 也改 `runs`。
