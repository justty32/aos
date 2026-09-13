# proto4 筆記 §23：逐步 JSON、逐步 Python（2026-09-13，使用者手機插播）

← [索引](2026-09-08-ideas.md)｜逐步 lisp 見 [§20](20-21-step-lisp-and-next.md)

## 23.1 使用者原話（照錄）

> 插播一個需求，關於剛剛那個逐行 lisp，我要你以這個為基礎，去做逐 python 執行的，要最簡單的方式：狀態儲存於檔案，並且是 json，最重要的是 ai 容易看懂，容易產出。在 llm cpu 結束後來做。
> 啊，在那之前可以現做最簡單的：一個 json arr 檔案，裡面每個元素都是 inst 格式，逐一執行，狀態儲存於外部 json。

## 23.2 順序

1. **現在就做**：逐步 JSON（`proto4-6/aos-step-json`）——一個 `.json` 檔是陣列，每個元素是一份 inst（跟 inst.json 七欄一模一樣），每叫一次跑下一個元素，狀態放旁邊的 `<PROG>.state.json`。全跑完回 100（跟 aos-step、kernel 的 done 約定一致）。
2. **LLM cpu 收完後**：逐步 Python——同一個骨架，元素從「一份 inst」變成「一段 python」，狀態一樣是 JSON 檔、AI 一眼看懂、也容易生成。怎麼跨格保存 Python 的變數（Janet 那邊用 image；Python 沒有等價物，大概是「狀態就是一個 JSON dict，每段程式拿到 `state` 改完存回去」）到時再定。

## 23.3 逐步 JSON 的定案（Fable，任務書 `proto4-6/notes/codex-task-1.md`）

- 元素＝inst 物件；相對 `cwd` 以 PROG 所在資料夾為準、沒寫＝PROG 所在資料夾（跟 `aos-kernel add` 同一條規則）；其他相對路徑照 inst 規則以 cwd 為準。每格把那個元素（cwd 轉成絕對）寫成一份暫存 inst.json 交給 `proto4-3/aos-exec` 跑，自己不解析指示詞。
- 狀態檔 `<PROG>.state.json`：`{"pc":2,"n":5,"done":false,"src":{…改動偵測…},"last":{"pc":1,"exit":0,"kind":"child","at":"…"},"history":[…]}`，人跟 AI 都能直接讀。
- 元素回 0 → pc+1；非 0 → 停在原地、退出碼原樣回（不推 pc，修好重跑同一格）；aos-exec 自己失敗 → 125；全部跑完 → 100。`--status`、`--reset`、改動偵測警告，跟 aos-step 同一套。

**23.3 落地補記（2026-09-13）**：做出來了（codex gpt-sol）：`proto4-6/aos-step-json`＋`aos_step_json.py` 211 行、15 條測試、README 84 行。我照 README 的 `job.json` 範例手跑：三格各回 0、第四次回 100，`result.txt` 是 `HELLO`，狀態檔 `job.state.json` 一眼看得懂。跟逐步 lisp 同一套約定（pc、`--status`、`--reset`、改動偵測、做完回 100、可以直接放上 kernel）。**逐步 Python 等 LLM cpu 收完再開**——現在 LLM cpu 已收（§22.8），所以下一段就是它；要先定「Python 的變數怎麼跨格」（§23.2）。

## 23.4 逐步 Python 的定案（Fable，任務書 `proto4-6/notes/codex-task-2.md`）

使用者要的：最簡單、狀態在 JSON 檔、AI 一眼看懂也容易生成。定案：

- **程式就是一支普通 `.py`**（AI 最會寫的東西），用 `ast` 切成頂層 statement——跟 Janet 版「一格一個頂層 form」完全同構。
- **只有 `state`（一個 dict）跨格活著**，存在 `<PROG>.state.json` 的 `"state"` 欄，必須 JSON 化得了（放不進去的東西當場失敗、pc 不動）。Python 沒有 Janet image 那種東西，也不需要：使用者要的就是「狀態是 JSON」。
- **`import`／`def`／`class` 這三種頂層 statement 不算格**，每格開跑前全部重放一次（便宜、確定性），所以前面定義的函式後面每格都能用；只有資料走 `state`。
- 每格拿到的名字：`state`、`here`（程式所在資料夾）、`pc`、`aos`（一個小模組：`aos.call`／`call_dir`／`call_json`／`llm`，就是 proto4-4 函式庫的 Python 版，底下一樣叫 `aos-exec`／`aos-llm`）。
- 其餘約定跟逐步 JSON、逐步 lisp 一樣：`--status`、`--reset`、`--stderr`、改動偵測、失敗 pc 不動、做完回 100、可直接放上 kernel。

## 23.5 使用者放鬆：不用太嚴格（2026-09-13）

原話：「Python 逐步這塊，不用太嚴格，可以是逐 python 函數，或逐 python 檔案或 module，來做執行。」

§23.4 的「用 ast 切頂層 statement、定義每格重放」太講究，作廢（派出去的 codex 停掉、半成品丟掉）。改成**逐函數**，最簡單的一種：

- 程式是一支普通 `.py`。**每個頂層 `def` 就是一格**，照檔案順序；名字以 `_` 開頭的是 helper，不算格。簽名 `def 名字(state)`，`state` 是 dict、跨格活著、存 JSON。
- 執行器每格 `importlib` 重新載入整支檔（所以 import、helper、常數都正常存在），叫第 pc 個 step 函式，成功就把 `state` 寫回 JSON、pc+1。
- 狀態檔多記 step 的名字（`"last":{"step":"fetch_data",…}`），比純數字好讀。
- 想「逐檔案」就在某格裡 `aos.call("./other.py")`；想「逐 module」就 import 它然後叫——都不用執行器多做事。
