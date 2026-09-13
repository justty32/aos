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

## 23.6 使用者再加：Lua 版（2026-09-13）

原話：「做一個 lua 版本也不錯，一些 binary 資料可以用 base64。」

定案（Fable）：`proto4-6/aos-step-lua PROG.lua`，跟 Python 版同一套約定——每個頂層函式一格（Lua 沒有「頂層 def 順序」可反射，改成程式最後 `return {step_a, step_b, …}` 回一個有序陣列，或回一張表 `{ {"load", load}, … }`；選前者＋函式名用 `debug.getinfo` 抓不到就用序號，**所以定成 `return { {name="load", fn=load}, … }`**，名字明寫，AI 好產出）；`state` 是 table、存 JSON。機器上是 Lua 5.4（`/usr/bin/lua5.4`），沒有 JSON 函式庫，所以執行器自帶一個小 JSON＋base64（純 Lua，一檔）。

**binary 用 base64 的約定（Python 版也照這個）**：state 裡的值若是「放不進 JSON 的位元組串」（Lua：不是合法 UTF-8 的字串；Python：`bytes`），存檔時自動變成 `{"$b64":"…"}`，載入時自動還原；也給 `aos.b64`／`aos.unb64` 讓人手動用。JSON 裡其他 `{"$b64":…}` 形狀的物件只要 key 只有這一個就會被當 binary 還原。

**23.5／23.6 落地補記（2026-09-13 深夜）**：三支都在 `proto4-6/`，同一套約定（pc、`--status`、`--reset`、`--stderr`、改動偵測、失敗 pc 不動、做完回 100、可直接放上 kernel），狀態檔同形（`state` 放最前、`steps` 列流程）：
- `aos-step-json`（陣列、每元素一份 inst）——15 條測試。
- `aos-step-py`（逐函數：每個頂層 def 一格、`_` 開頭是 helper；`aos.call`／`call_dir`／`call_json`／`llm`）——15 條。README 的 `job.py` 我手跑：四格→100，`state` 裡 values 與工具回傳都在。
- `aos-step-lua`（`return {{name=,fn=},…}`；自帶 `lua/json.lua`、`base64.lua`、`aos.lua`；不合法 UTF-8 的字串自動存成 `{"$b64":…}`）——22 條。README 的 `job.lua` 我手跑：四格→100，`raw` 存成 `{"$b64":"AP8B"}`。
- Python 版的 `$b64`（bytes）另派一本小任務補齊（codex-task-4）。
- 這三支加上 proto4-4 的逐步 lisp，就是「一格跑一步、狀態落檔、做完回 100」這個形狀的四種寫法；kernel 一視同仁。

## 23.7 等待語意定案：宣告要等的檔（使用者 2026-09-13 選的）

四個選項（宣告要等的檔／特殊回傳值再來一次／同步到底／kernel sleep-wake），使用者選**宣告要等的檔**。規則（四支執行器一模一樣）：

- 一格可以宣告「我在等 X 檔」：Python `return aos.wait_for("out.json")`、Lua `return aos.wait_for("out.json")`、lisp 那個 form 的值是 `(aos/wait-for "out.json")`、JSON 元素多一欄 `"wait_for": "out.json"`。路徑相對於程式所在資料夾（`here`）。一次只等一個檔。
- 執行器看到宣告：**這格算做完**（pc+1），狀態檔多一欄 `"waiting": {"for": "/abs/out.json", "since": "…", "after_pc": k, "checks": 0}`，退出 0。
- 之後每次被叫：先看 `waiting`——檔不在 → `checks`+1、退出 0、**什麼都不跑**；檔在了 → 清掉 `waiting`、照常跑第 pc 格（那格自己去讀檔）。
- `--status` 印得出在等什麼、等多久；`--reset` 連 `waiting` 一起清。
- 沒有逾時、沒有多檔、沒有 kernel 叫醒（那是選項 D，以後真的痛再做）；等待中的行程還是會被 kernel 輪到，只是每格立刻退出。
- 搭配 LLM：`aos.llm_submit(K, req, name)`（直接跑 `aos-kernel llm K req.json --name name`，不等）回結果檔路徑 → `return aos.wait_for(那條路徑)` → 下一格讀結果。lisp／Lua 同名。
