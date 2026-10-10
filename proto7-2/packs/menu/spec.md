# menu 任務包 spec（scaffold1 MN1／MN2）

← [藍圖 scaffold1](../../notes/blueprint-scaffold1.md)｜[意圖卡](../../notes/intents/scaffold.md)｜錯誤 [blueprint-errors](../../notes/blueprint-errors.md)

選單＝人（或聰明模型）先搭好的一棵選擇樹（一個 JSON）。AI 每次只看一層、只回一個編號（頂多再填一格）；走到葉子才由**登記過的專用工具**或「寫進 out/」真做事。AI 拿不到 shell。程式：`aos7_menu.py`（純函式：選單驗證、提示、回法解析、格子檢查、`step`）、`aos7_menu_run.py`（驅動：AI、工具、status）、`aos7_menu_state.py`（state 與凍結 pending 驗證）、`bin/aos7-menu`、工具目錄 `tools.json`。

## 1. 指令

- `aos7-menu run <node> <menu.json> [--llm MODEL | --reply FILE] [--run NAME] [--var K=V]… [--brief FILE]`
  - 不給 `--llm`／`--reply`＝**練習用的 AI**：照選單旁的 `practice.json`（`{"v":1,"replies":["選：1", …]}`）回；本 run 第 k 次呼叫 AI（從 0 數，含重問）拿 `replies[k]`，用完＝停下退 1。腳本裡可以故意放一句回錯的，測重問。不開帳、不連網。
  - `--llm MODEL`：每次呼叫走 llmcall（帳 `<node>/budget/llm`，帳任務要在跑；沒在跑＝退 1 一行照轉 budget 那句，**不記成停下**，起好帳任務照原樣再跑會接續；llmcall 退 1／2＝確定沒做成、記成停下退 1，同 FX1 B10-11）。grant 的 `gateway` 是 `llm.litellm` 就送 `{"litellm":{"model":MODEL,"messages":[system, user]}}`；是 `llm.fake` 就送 `{"fake":{"mode":"ok","usage":字數//3+1,"text":練習腳本第 k 句}}`（測試用，可數真送幾次）。
  - `--reply FILE`：人手／測試走**一步**：把 FILE 全文當成目前這層的回答，處理完（含之後的寫檔與工具）停在下一個要問 AI 的地方，把那層完整提示印在 stdout；做完印「做完」。
  - `--run NAME`（預設＝選單 `name`，`^[A-Za-z0-9_-]{1,40}$`）、`--var K=V`（填選單模板，K 同 run 名規則）、`--brief FILE`（需求摘要 ≤1500 字，每層提示最上面附上）。三者只在第一次建 run 時收；接續時給了不同值＝退 2。
- `aos7-menu status <node> [--run NAME] [--prompt]`：一行白話，例「選單 hello：走到「寫一句」（第 3 步，這層重問 1 次）」「選單 hello：做完，寫了 out/reply.txt」「選單 hello：停下——連 3 次回得不像（層 line）」。沒給 `--run`＝最近更新的那個 run（還有別的 run 時句尾補「另有 N 個 run」）。`--prompt` 改印目前這層的完整提示（人手走用）；已停下時印狀態並補「這個 run 已停下，沒有正在等回答的提示」；已做完補「這個 run 已做完，沒有正在等回答的提示」；正在做事補「目前正在做事，沒有正在等回答的提示」，不前進。`status` 對還在走、做完、已停下的 run 都退 0；沒有 run＝退 1 一行；state 壞掉＝退 3。已停下的 run 用 `run` 重跑則退 1。

退出碼（blueprint-errors）：**0** 做完（`--reply` 時＝這步收下）／**1** 停下（連 3 次不像、輪數到上限、AI 選出口、練習腳本用完、帳任務沒在跑、llmcall 確定沒做成、工具退 1 而該層沒有 fail 分支）／**2** 你給的不對（選單錯、工具沒登記、參數、模板變數缺、選單在 run 中途改過、工具退 2）／**3** 不確定（llmcall 3 或未知碼、state 讀寫故障、檔案系統故障（如 EIO／EMFILE／EACCES）、工具退 3／逾時／輸出不是一行 JSON；工具或呼叫不確定時照原樣再跑會接續，state 毀損先修復原檔）。選單或練習檔不在時才說「<路徑> 不在」；檔案在但 JSON 壞掉＝退 2「<路徑> 第 N 行第 M 字不是合法 JSON」，行與字從 1 數。整個命令 stderr 最多一行 `aos7-menu: 發生什麼。怎麼辦`，3 以「不確定：」開頭；llmcall 退 4 收到回答立即設定對帳提醒；即使處理回答的 `step()` 發生模板錯誤，也保存回答與 journal 的 `unsettled: true` 證據，命令結束時合併成一行對帳提醒（有錯誤時接在同一行錯誤後）。已做完的 run 再跑＝印同一行做完、退 0、不呼叫 AI；已停下的再跑＝同一行、退 1（要重走換 `--run` 或刪 `<node>/menu/<run>/`）。

## 2. 選單 `menu.json`

```json
{"v": 1, "name": "hello", "start": "who", "required": ["reply.txt"],
 "layers": {
  "who":  {"ask": "要回誰的信？", "options": [
             {"text": "小明", "next": "line", "set": {"to": "小明"}},
             {"text": "小華", "next": "line", "set": {"to": "小華"}}],
           "exit": {"text": "缺少判斷先回誰的必要資訊，請人補充"}},
  "line": {"ask": "寫一句給 {to} 的回覆", "slot": {"max_bytes": 200, "max_lines": 1},
           "do": {"write": "out/reply.txt"}, "next": "send", "exit": {"text": "缺少回覆所需的必要資訊，請人補充"}},
  "send": {"do": {"tool": "hello-send", "args": {"to": "{to}"}}, "ok": "end", "fail": "line", "max_rounds": 3}}}
```

- **問的層**（有 `ask`）：`options` 是清單，或 `{"from": "done"}`（每個已寫出的檔一個選項：`text`＝檔名、`set`＝`{"file": 檔名}`、`next`＝本層 `next`；產生的 text／set 都是字面值，不再展開模板）。可選 `only: ["模板", …]`，只列模板展開後等於 done 項目的檔名；沒給 `only` 就全列。只有 `slot` 沒有 `options`＝隱含一個選項「交出這一格」，`next`＝本層 `next`。**每層必有 `exit`**，顯示成最後一個編號。
- **選項數**：顯示出來的編號（含出口）要 2～5 個。沒有 `when` 的層靜態檢查；有 `when` 或 `from` 的層在顯示時檢查，超出＝退 2，訊息報目前數量，例如「層 which options 含出口要 2～5 個，現在 6 個」。選項 `when`：`required_done`（`required` 全在 done）、`required_missing`、`new:<模板>`（該路徑不在 done）；不成立就不顯示。
- 選項欄位：`text`、`next`（層名或 `end`）、可選 `set`（{變數: 模板}）、`when`。層欄位：`ask`、`options`、`exit`、`slot`、`do`、`next`、`show`（`out/<模板>`，存在就把該檔全文附在提示裡「目前的內容」，≤8192 bytes，改檔時用）。
- **做事的層**（沒有 `ask`、有 `do.tool`）：跑工具，退 0 走 `ok`、退 1 走 `fail`（沒有 `fail`＝停下退 1）；工具退 0 或 1 都把一行 JSON 的字串／數字／布林欄位合進變數（內建變數不可蓋）；合併前只清目前仍歸該工具所有的鍵；其他工具覆寫時轉移歸屬，`set`／`--var` 的值沒有工具歸屬，不會被舊工具清除，字串超過 600 字取前 600 字再加「…」。`max_rounds`：本 run 進這層超過幾次＝停下退 1（計在 state 的 `gate_rounds[層]`）。
- `do`：只有 `{"write": "out/<模板>"}`（問的層用，把格子內容寫進 run 的 `out/`；write、`new:` 與 done 用同一正規化：相對 out/、去掉 `./`、拒絕任何 `..` 段與絕對路徑（退 2）；out/ 本身或路徑任一段是符號連結也退 2 拒寫；逐段開目錄失敗時，只有確認是符號連結或非資料夾才退 2，其他 OSError 保留原例外，由命令出口退 3；暫存檔用同資料夾隨機名與 `O_CREAT|O_EXCL|O_NOFOLLOW` 建立後 rename，寫完把 out 內相對路徑加進 `done`）與 `{"tool": 名字, "args": {參數: 模板}}`。**沒有 cmd／shell 動詞**。
- 模板：`{變數}` 從 state 的 vars 填（`--var`、`set`、工具輸出），`{{`／`}}` 是字面括號；變數不存在＝退 2。`required` 每項只在判斷 `required_done`／`required_missing` 時用目前 vars 展開；其他層不展開 required。slot 的 `prefix` 與 `sections` 每項也用目前 vars 展開。內建唯讀變數 `run`、`node`、`run_dir`。
- **靜態驗證（載入時，錯＝退 2）**：`v`＝1、`name` 合 run 名規則、`start` 與所有 `next`／`ok`／`fail` 指得到（或 `end`）、層名合 run 名規則、每個問的層有 `exit`（缺時點名層，說明「出口字由你定」，並提示 `"exit": {"text": "缺少判斷先回誰的必要資訊，請人補充"}`；指不到的 `next`／`ok`／`fail` 也報出所指名字，其他選單錯也點名層與欄位）、沒有 `when` 的層選項數 2～5、`do` 只有 write／tool、`slot` 只有 `max_bytes`／`max_lines`／`prefix`／`sections`／`tool`、工具名在目錄裡且 `args` 的鍵與登記的參數一致、做事的層有 `ok`、沒有不認得的鍵。

## 3. 回法（凍結）與重問

- AI 第一行（略過開頭空行與前後空白）`選：N`（冒號全形半形都收，數字可全形）；有格子而選了非出口時，下一行以 `格：`（或 `格:`）開頭，**之後到結尾**是內容（同一行冒號後若空就從下一行起；原樣、不加圍欄，全文後面不要再寫任何字；整段剛好被一對 ``` 包住時本機剝掉；第一行是以 ``` 開頭的圍欄、最後一行是 ``` 後面僅有空白，或誤抄以「這格」開頭的限制說明（前面可有空白及全形／半形標點，例如「```；這格限制：max_bytes=8192」「```這格的限制…」）時，剝掉頭尾圍欄並丟掉尾行的限制說明；尾行接其他文字則原樣保留、不剝；剝掉時在 log 記 `fence`）。結尾空白收成一個換行。
- 不合（沒有選行、N 不在顯示的範圍、缺格子、格子檢查沒過）＝本機重問同層：提示最上面加一行「上一次不行：<原因>。照回法重回一次」＋同層完整提示；**這層連續第 3 次不合＝停下退 1**。換層時重問次數歸零。
- 選了出口＝停下退 1，stderr「AI 選了出口：<出口文字>」。
- 格子五種檢查：`max_bytes`（UTF-8 位元組）、`max_lines`、`prefix`（第一行以它開頭）、`sections`（每項都要有一行以它開頭）、`tool`（把內容用同目錄隨機名與 `O_CREAT|O_EXCL|O_NOFOLLOW` 暫存再 rename 寫進 run 的 `.check/`，拒絕路徑中符號連結、以參數 `path` 呼叫；退 0 過、退 1 不過且 stderr 最後一行當原因（≤200 字）、其他照 §5）。

## 4. 提示的形狀（每次呼叫 AI 都是單獨一問，不帶對話紀錄）

system 固定一段：「你在走一份選單。每次只回答這一層。所需資料都在下面，不用找檔案或工具。照回法回，不要多寫別的。」user 依序：重問提醒（若有）→ `需求：`＋brief（若有）→ `已交：`檔名（若有，**只列名、不附內容**）→ 本層 `ask` → 「目前的內容」（`show` 指的檔存在時）→ 編號選項 → 回法段。不附上層內容、不附整棵樹。回法第一行固定「回法：第一行 選：N」；有格子時另加以下兩行（限制只列實際設定的項目）：

~~~~text
第二行起：先寫「格：」，後面（同一行或下一行起）到結尾放全文，原樣、不加 ``` 圍欄，全文後面不要再寫任何字
這格的限制（只是說明，不要抄進格子）：<人話限制，以「、」分隔>
~~~~

限制 `max_bytes` 顯示「最多 N bytes」、`max_lines` 顯示「最多 N 行」、`prefix` 顯示「第一行以「…」開頭」、`sections` 每項顯示「要有一行以「…」開頭」、`tool` 顯示「會再用工具檢查」；prefix／sections 先展開模板。

## 5. 工具目錄 `tools.json`（只有它登記的名字能被叫）

```json
{"v": 1, "tools": {"hello-send": {"about": "把回覆交給收件人（玩具）", "argv": ["{py}", "{pack}/examples/hello/send.py", "{run_dir}", "{to}"], "args": ["to"], "out": "json-line", "timeout": 30}}}
```

- argv 不經 shell，只把 `{參數}` 換成模板填好的值；另有內建 `{py}`（目前的 Python）、`{top}`（proto7-2/）、`{pack}`（packs/menu/）、`{node}`、`{run_dir}`。工作目錄＝node。`out`：`json-line`（退 0／1 的 stdout 最後一行非空要是 JSON 物件；退 1 沒印 JSON 可當空物件）或 `code`（只看退出碼）。`timeout` 預設 300 秒。
- 退出碼：0 過、1 沒過（走 `fail`）、2＝menu 退 2、3／逾時／被訊號殺／json-line 輸出壞＝menu 退 3（再跑會**重跑這個工具**：登記的工具要能重跑）。
- 目錄位置固定 `packs/menu/tools.json`；測試可用環境變數 `AOS7_MENU_TOOLS` 換一份。既有指令直接登記、不改它們的碼（範例：`aos7-gates check`、`aos7-skills pick`、`aos7-ctl`）。AI 看不到目錄。

## 6. 狀態 `<node>/menu/<run>/`

- `state.json`（唯一恢復真相，每次整份寫暫存再 rename）：`{"v":1,"menu":"<menu.json 絕對路徑>","menu_sha":"<sha256 前 16>","run","layer","vars":{},"brief","done":[],"tries":0,"step":0,"calls":[{"layer","call_id","rc","used"}],"gate_rounds":{},"pending":null,"status":"walking|done|stuck","why":null}`；另有 `var_owner: {鍵: 工具名}`（記每個鍵目前的工具歸屬，鍵必須存在於 vars 且不能是內建鍵）、`nonce`（每次新建 run 隨機產生的 16 hex，接續沿用）、`initial_vars`（第一次給的 `--var`，必須是 dict，接續時核對）、`journal`（log 每步一行的來源，`log.jsonl` 每次存 state 時照它重寫，所以被殺在 rename 之後也不漏行）、`fence`（這步剝了圍欄）、`code`（停下時的退出碼）。
- **先存再呼叫**：要問 AI 時先把 `pending`＝`{"call_id","layer"}` 存進 state，再呼叫；處理回答失敗時，pending 另存 `received: {reply, used, rc}`，journal 記 `reply-error`；接續優先使用這份已收回答，不再次呼叫 AI，calls 在回答成功處理後才追加。`call_id`＝`menu/<run>/<層>/<這層第幾次>`（從 1 數，本 run 內累計）。被殺後重跑看到 `pending` 就用同一個 call_id（llmcall 同名不重問；練習用的 AI 照第 k 次給同一句）。llmcall 的 `--call` 名一律＝`menu-` 加 `sha256(nonce + "\n" + call_id)` 前 32 碼；`--logical menu/<run>`。
- 工具與寫檔：pending 建立時就凍結完整動作值（write 路徑、工具 args 已展開），先存 `pending`＝`{"act": …}` 再做、做完存結果；被殺重跑會再做一次（寫檔同內容覆寫，工具要能重跑）。
- run 鎖不等待（`timeout=0`）；拿不到退 3「另一個 aos7-menu 正在走這個 run。等它結束再跑」。接續先驗 state 的必要欄位與 pending 是否符合目前層：凍結動作只驗精確欄位、動作／工具種類、args 結構與路徑安全，不用目前 vars 重新展開或比對原模板；純工具層的 pending 只有 act，不准帶 next，成功／失敗只能走該層 ok／fail；自己的 state 壞掉退 3、保留原檔。state.json 讀不出來時說「不確定：<run> 的 state.json 讀不出來（原檔留著）。要接續就把它修回合法 JSON；要放棄就刪掉 <node>/menu/<run>/ 或換 --run 重走」。
- 每次啟動對 `menu_sha`：跟 state 不同＝退 2「這個 run 用的選單改過了。改回原樣，或換 --run 重走」。
- `log.jsonl` 每步一行：`{"at","step","layer","kind":"ask|bad|pick|write|tool|exit|done|stuck|reply-error","call_id","prompt_chars","reply_chars","used","rc","why"}`。`out/` 是 `do.write` 寫出的東西。

## 7. 純函式介面（`aos7_menu.py`，不讀寫檔、不呼叫程式、不改傳入物件）

- `load(obj, tools) -> menu`：靜態驗證，錯丟 `MenuError`（一行白話＋怎麼改）。
- `new_state(menu, run, vars, brief, menu_sha) -> state`：產生隨機 nonce，其他核心函式不讀寫檔、不呼叫程式、不改傳入物件。
- `view(menu, state) -> next`：目前要做什麼。
- `render(menu, state, shown=None, reminder=None) -> str`：本層 user 提示。
- `step(menu, state, reply) -> (state2, next)`：收一個 AI 回答。
- `after(menu, state, result) -> (state2, next)`：收一個動作結果（寫檔 `{"ok": true}`；工具 `{"rc", "out", "err"}`）。
- `next` 形狀：`{"kind":"ask","layer","call_id","reminder"}`｜`{"kind":"act","act":{"write":相對 run 的路徑,"text"}｜{"tool","args"}｜{"check":工具,"text"}}`｜`{"kind":"done"}`｜`{"kind":"stuck","code":1|2|3,"why"}`（工具不確定時 pending 留著、state 仍是 walking，再跑重做那個動作）。

## 8. 不做

AI 寫選單的流程、自由文字層、shell、自動換模型、多 node、改 author／brain／核心。README／ADVANCED 由 MN4 寫，學徒 aos-tool 選單由 MN2 做。
