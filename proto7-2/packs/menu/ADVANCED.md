# menu 進階（給寫選單的人）

← [README](README.md)｜完整規格 [spec.md](spec.md)｜[藍圖 scaffold1](../../notes/blueprint-scaffold1.md)｜[意圖卡](../../notes/intents/scaffold.md)

本頁講怎麼寫自己的選單、登記工具、看進度、被中斷怎麼辦、接真 AI。逐欄位的精確規則以 [spec.md](spec.md) 為準。下面的指令都在 repo 根打，`M=proto7-2/packs/menu`。

## 一覽與契約卡

| 項目 | 內容 |
|---|---|
| 指令 | `aos7-menu run <node> <menu.json> [--llm MODEL \| --reply FILE] [--run NAME] [--var K=V]… [--brief FILE]`；`aos7-menu status <node> [--run NAME] [--prompt]` |
| 職責 | 照選單一層一層問 AI（每次單獨一問、不帶對話紀錄），收編號與格子，走到葉子才寫檔或叫登記過的工具 |
| 保證 | 先存 state 再呼叫 AI；被殺後照原樣再跑，用同一個呼叫名，不重問、不重扣；AI 拿不到 shell，只能選編號 |
| 不保證 | 登記的工具被殺後會再跑一次（工具要能重跑）；AI 回得對不對（選單作者負責把題目出清楚） |
| 寫的檔 | `<node>/menu/<run>/` 底下：`state.json`、`log.jsonl`、`out/`、`.check/`（格子工具的暫存） |
| 程式 | `aos7_menu.py`（純函式）、`aos7_menu_check.py`（選單驗證、回法解析）、`aos7_menu_state.py`、`aos7_menu_run.py`（驅動與命令列）、`aos7_menu_io.py`（存檔、llmcall、工具）、`bin/aos7-menu`、工具目錄 `tools.json` |
| 範例／測試 | `examples/hello/`（menu.json、practice.json、send.py）；`tests/test_menu_*.py` |

## 選單 `menu.json` 怎麼寫

先看 [examples/hello/menu.json](examples/hello/menu.json)，三層各示範一種：

```json
{"v": 1, "name": "hello", "start": "who", "required": ["reply.txt"],
 "layers": {
  "who":  {"ask": "先回標為急件的那封信。小明：「急件：…」小華：「不急：…」先回誰？",
           "options": [{"text": "小明", "next": "line", "set": {"to": "小明", "request": "請確認收到開會通知。"}},
                       {"text": "小華", "next": "line", "set": {"to": "小華", "request": "請確認收到照片。"}}],
           "exit": {"text": "缺少判斷先回誰的必要資訊，請人補充"}},
  "line": {"ask": "{to} 的要求是「{request}」請寫一句回覆", "slot": {"max_bytes": 200, "max_lines": 1},
           "do": {"write": "out/reply.txt"}, "next": "send", "exit": {"text": "缺少回覆所需的必要資訊，請人補充"}},
  "send": {"do": {"tool": "hello-send", "args": {"to": "{to}"}}, "ok": "end", "fail": "line", "max_rounds": 3}}}
```

- 最上層：`v` 固定 1、`name`（也是預設的 run 名，英數 `_-`、≤40 字）、`start` 第一層、`layers`、可選 `required`（「該交齊的檔」，給選項的 `when` 用）。
- **選擇的層**（有 `ask`、有 `options`）：每個選項 `text`、`next`（下一層名或 `end`）、可選 `set`（記下變數，後面的層用 `{變數}` 取）。
- **寫字的層**（有 `ask`、有 `slot`、沒有 `options`）：AI 看到「1. 交出這一格」和出口兩個編號；交出的內容先過格子檢查，再由 `do.write` 寫進 `out/`，然後走 `next`。
- **做事的層**（沒有 `ask`、有 `do.tool`）：不問 AI，直接叫工具；工具成功走 `ok`、失敗走 `fail`（沒寫 `fail` 就停下）。`max_rounds`＝這層最多進幾次，防止「寫→寄失敗→再寫」繞不完。
- `do` 只有兩種：`{"write": "out/<路徑>"}`、`{"tool": 名字, "args": {參數: 模板}}`。沒有 shell、沒有任意指令。
- 模板 `{變數}` 從 `set`、`--var`、工具輸出取；另有內建 `{run}`、`{node}`、`{run_dir}`。字面括號寫 `{{`／`}}`。用到不存在的變數＝退 2。

### 規則一：每層 2～5 個編號，出口算在內

- 每個問 AI 的層都**必須有 `exit`**，它固定顯示成最後一個編號。AI 選它＝停下、退 1，stderr 印出口文字，等人決定。
- 顯示出來的編號（含出口）要 2～5 個。所以一般選項最多 4 個。超過或缺出口，載入時就擋下、退 2，例如 `aos7-menu: 層 who options 含出口要 2～5 個。請改好選單再跑`。
- 選項多於 4 個時，拆成兩層（先選大類、再選小項），或用 `when` 把暫時不該出現的藏起來：`required_done`（`required` 全交齊才顯示）、`required_missing`、`new:<模板>`（那個檔還沒寫過才顯示）。有 `when` 的層在顯示當下才數，那時超過也退 2。
- `options` 也可以寫 `{"from": "done"}`：每個已寫出的檔變成一個選項（改檔用），可加 `only: [模板, …]` 篩選；搭配層的 `show: "out/<模板>"` 把那個檔目前的全文附進提示。

### 規則二：這層決定要的資訊，要放在這層

每次問 AI 都是**單獨一問**：它只看到這層的 `ask`、選項、回法（以及 `--brief` 的需求摘要、已交的檔名），**看不到上一層的題目、看不到檔案內容**。所以做這個決定需要的東西，要寫進這層的 `ask`，或在上一層用 `set` 帶下來再用 `{變數}` 填進去。

實例（MN1）：hello 第一版第一層只問「要回誰的信？」、沒附信的內容，真 AI（luna）10 次全選了出口——它照實說「資訊不夠」。改成把兩封短信寫進該層 `ask`、第二層用 `set` 帶著對方那句話後，10 次全過。AI 一直選出口時，先檢查這層題目夠不夠它做決定。

### 格子檢查（`slot`）

五種，可以混用；不過＝要求 AI 重回同一層：

| 鍵 | 檢查 |
|---|---|
| `max_bytes` | 內容 UTF-8 位元組數上限 |
| `max_lines` | 行數上限 |
| `prefix` | 第一行要以它開頭（可用模板） |
| `sections` | 清單，每項都要有一行以它開頭（例 `["## 第一次跑"]`，可用模板） |
| `tool` | 登記過、參數只有 `path` 的工具：內容寫成暫存檔給它，退 0 過、退 1 不過（stderr 最後一行當原因給 AI 看） |

### AI 的回法（固定）

```text
選：2
格：這裡開始到結尾都是內容（只有寫字的層要）
```

冒號全形半形都收。回得不像（沒有選行、編號超出、缺格子、格子沒過）＝在提示最上面加一行「上一次不行：原因」，重問同一層；**同一層連 3 次不像＝停下、退 1**。換到下一層時次數歸零。

## 練習用的 AI：先不花錢把選單走通

不給 `--llm` 時，回答照**選單同資料夾**的 `practice.json` 一句一句給（本 run 第幾次問 AI 就拿第幾句，重問也算一次）：

```json
{"v": 1, "replies": ["選：1", "選：1\n格：小明，開會通知已收到，謝謝！"]}
```

句子用完＝停下、退 1「練習腳本用完了」。可以故意放一句錯的，看重問提示長怎樣。自己的選單建議先複製 `examples/hello/` 整個資料夾來改。

## 一步一步人手走：`--reply` 與 `status --prompt`

- `aos7-menu run <node> <menu.json> --reply 回答.txt`：把檔案全文當作「目前這層」的回答，處理完停在下一個要問 AI 的地方，**把那層完整的提示印出來**（AI 實際會看到的樣子，system 那段除外）。走完印「做完」。
- `aos7-menu status <node> --prompt`：只印目前這層的提示，不前進。
- 用這兩個可以自己當 AI 走一遍，檢查每層題目是不是夠清楚。

## 工具目錄 `tools.json`：登記專用工具

葉子要做的事（寄出、驗證、跑檢查）由**登記在 `packs/menu/tools.json` 的工具**做；選單只能寫名字，AI 完全看不到目錄。一列長這樣：

```json
{"v": 1, "tools": {
  "hello-send": {"about": "把回覆交給收件人（玩具）",
                 "argv": ["{py}", "{pack}/examples/hello/send.py", "{run_dir}", "{to}"],
                 "args": ["to"], "out": "json-line", "timeout": 30}}}
```

- `argv` 不經 shell，只把 `{參數}` 換成值。可用的佔位：`args` 列的參數、`{py}`（目前的 Python）、`{top}`（proto7-2/）、`{pack}`（packs/menu/）、`{node}`、`{run_dir}`。工作目錄是 node。
- 選單裡 `do.args` 的鍵要跟登記的 `args` **完全一樣**，不然載入就退 2「工具沒登記」或參數不合。
- `out`：`json-line`＝stdout 最後一行是一個 JSON 物件，裡面的字串／數字／布林會變成選單變數（後面的層可以 `{鍵}` 用，例如把檢查失敗原因帶給「改哪個檔」那層）；`code`＝只看退出碼。`timeout` 預設 300 秒。
- 工具的退出碼：0 成功（走 `ok`）、1 失敗（走 `fail`）、2 參數不對（menu 退 2）、3／逾時／被殺／輸出壞（menu 退 3，再跑會**重跑這個工具**）。所以工具要能安全重跑（同樣輸入寫同樣結果）。
- 既有指令（`aos7-gates`、`aos7-skills` 等）直接登記一列就能用，不用改它們的碼。測試想換一份目錄，設環境變數 `AOS7_MENU_TOOLS=<路徑>`。

## 看進度：`status`

`aos7-menu status <node>` 印一行白話，看最近更新的那個 run：

- `選單 hello：走到「<這層的題目>」（第 2 步，這層重問 0 次）`——還在走；有別的 run 時句尾補「另有 N 個 run」。
- `選單 hello：做完，寫了 out/reply.txt`
- `選單 hello：停下——連 3 次回得不像（層 line）：…。請換 --run 重走`

`--run NAME` 指定看哪一個。每一步的細節在 `<node>/menu/<run>/log.jsonl`（一步一行：問了、選了、回錯、寫檔、叫工具、做完／停下）；每次呼叫用了多少 token 在 `state.json` 的 `calls[].used`。

## 被中斷、改了東西、要重走

- **被殺／斷電**：照原樣再打同一個 `run` 就接著走。問 AI 之前已先存好「正要問哪一層、呼叫名」，所以剛好在等 AI 時被殺，再跑會用同一個呼叫名，不會重問、不會重扣；寫檔與工具被殺會再做一次。
- **已做完**的 run 再跑：印同一行做完、退 0、不問 AI。**已停下**的再跑：印同一行停下原因、退 1。
- **選單改過**（跟這個 run 開始時不一樣）：退 2「這個 run 用的選單改過了。改回原樣，或換 --run 重走」。
- **要重走**：換一個名字 `--run try2`，或刪掉 `<node>/menu/<run>/`。`--run`、`--var`、`--brief` 只在第一次建 run 時收，接續時給不同的值＝退 2。
- 同一個 run 同時只能有一個在走；另一個正在跑時退 3「另一個 aos7-menu 正在走這個 run」。

## 接真 AI：`--llm`

`--llm MODEL` 改由真模型回答，每次呼叫經 [llmcall](../llmcall/README.md) 記帳，所以 node 要有帳（`<node>/budget/llm/`）而且帳任務在跑。最省事的做法是用 [aos7-up](../../modules/up/README.md) 起一個真 AI 的 node，帳就一起裝好、跟著心跳跑：

```sh
python3 proto7-2/modules/up/aos7-up /tmp/aos/real --model chatgpt-gpt-6-luna -d
python3 $M/bin/aos7-menu run /tmp/aos/real $M/examples/hello/menu.json --llm chatgpt-gpt-6-luna
python3 proto7-2/modules/up/aos7-up stop /tmp/aos/real     # 用完停掉心跳
```

- `MODEL` 填 LiteLLM 設定裡的模型名（`curl -s http://localhost:4000/v1/models` 查）；LiteLLM 位址與金鑰的環境變數（`AOS7_LITELLM_URL`、`AOS7_LITELLM_KEY`）見 [up ADVANCED](../../modules/up/ADVANCED.md)。
- 帳任務沒在跑＝退 1，什麼都沒送，那行會附可以直接複製的起帳指令；起好後照原樣再跑會接續（不算停下）。
- 每次呼叫先預留 20000 token，用多少扣多少。hello 用 luna 走一次約 2 次呼叫、共 3.5k token（2026-10-10 實測）。
- `--brief FILE`：需求摘要（≤1500 字），每層提示最上面都附上——全程都要知道的背景放這裡，比每層重寫省事。
- `--var K=V`：開 run 時先填好的變數（可給多次），選單裡用 `{K}`。

## 退出碼與錯誤訊息

整個命令 stderr 最多一行 `aos7-menu: 發生什麼。怎麼辦`。

| 碼 | 意思 | 例 |
|---|---|---|
| 0 | 做完（`--reply` 時＝這一步收下了） | `選單 hello：做完，寫了 out/reply.txt` |
| 1 | 停下，要人看 | AI 選了出口、連 3 次不像、`max_rounds` 到了、練習腳本用完、帳任務沒在跑、工具失敗而該層沒 `fail` |
| 2 | 你給的不對 | 選單錯（缺出口、編號超過 5、next 指不到、工具沒登記）、node 不在、模板變數缺、選單中途改過 |
| 3 | 不確定，照原樣再跑通常會接上 | 呼叫結果不確定、工具逾時、state 讀不出來、另一個正在走同一個 run |

## 不做

AI 自己寫選單、自由文字層、shell 指令、自動換模型、多 node。學徒寫 aos 工具的選單在 `examples/aos-tool/`（MN2）。
