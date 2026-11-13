工具印的 `$AOS_STACK/…` 改成照叫它的那一方的 stack 算（fx-2:A 的施工結果：設計、盤點、代定、要補的條文）。

← [fixes-施工結果](fixes-施工結果.md)「要使用者裁的」第 2 題｜裁定落地見 [裁定落地-1113](裁定落地-1113.md)

## 決定

- **使用者裁定（11-13）**：「fx-2:A」＝全家一起改：`aos-tools` 多給工具一個「叫我的那方的 stack」，印路徑都照它算。
- **做法（隊長代定，可翻案）**：`aos-tools call` 多給工具一個環境變數 **`AOS_STACK_IN_CALLER=tools/<登記名>`**——工具的小格在叫方 stack 裡的**相對位置**。工具把自己小格裡的路徑印給叫方時，寫成 `$AOS_STACK/tools/<登記名>/…`；叫方（腦）讀到的 `$AOS_STACK` 是它自己的 stack，照字面找得到。
  - 誰設：只有 `aos-tools call`，每次 call 重設；登記格 `env` 與外面帶進來的同名值都蓋不掉。父沒設 `AOS_STACK`＝不給，外面有也拿掉。
  - 誰讀：`lib/tool_io.py` 的 `place`（Python 工具印路徑的共用入口）。不是 Python 的工具自己讀這個變數拼。
  - 沒設時：照原本的印法（`$AOS_STACK/檔`，從工具自己的小格算）——工具被人直接 `aos-exec` 叫時，讀的人看到的 `$AOS_STACK` 本來就是那一格。
  - 對不上時：變數的值跟工具自己的 `AOS_STACK` 結尾不一樣（例：工具自己另起了一支換過 `AOS_STACK` 的程式，把這個變數繼承過去）＝當沒設。值是絕對路徑、帶 `..`、空的，也當沒設。
  - 印出來的長相：`$AOS_STACK/tools/todo/todo.json`、小格本身＝`$AOS_STACK/tools/todo`。不印絕對路徑（結果行會進 history，N-67 ⑦）。
  - 工具再叫工具：裡面那支拿到的是 `tools/<裡面那支的名>`，印出來的路徑從外面那支工具的小格算——讀它輸出的就是外面那支，對得上。
- **為什麼給相對位置、不給叫方 stack 的絕對路徑**：CONVENTION P-17 寫「被叫的只看到自己的 stack、不知道上面有誰」。給絕對路徑＝直接把上面那層的位置交給工具，跟這句字面打架；給相對位置，工具仍然只認得自己的小格，只是多知道「讀我輸出的人怎麼稱呼這一格」。另外相對值就算被哪支工具不小心寫進檔，也不違反 N-67 ⑦（絕對路徑不落檔）。裁定原句是「多給一個叫我的那方的 stack」，這裡給的是「從那方的 stack 看我在哪」，效果（印的路徑都照叫方的 stack 算）一樣，機制比原句窄一點——**這一點是代定，使用者可翻成給絕對路徑**（翻的話變數改名 `AOS_CALLER_STACK`、P-17 那句要一起改）。
- **新增對外格式**：`AOS_STACK_IN_CALLER` 是新的 `AOS_` 環境變數。歸 [四種性質表](../../../docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md)的 ① 執行環境（跟 `AOS_STACK` 一樣每次叫別人時重設，只是設的人是 `aos-tools call`、不是 aos-exec）；歸哪一格也是代定。

## 盤點：哪些工具會把自己小格裡的路徑印給叫方（7 支，11-13）

| 工具 | 印什麼 | 怎麼跟上 |
|---|---|---|
| `lib/agent/todo` | `todo.json` 讀不到、壞掉、寫不進去的錯誤行（`ListBad`／`ReadFailed`／`WriteFailed`） | 本來就走 `tool_io.place`，程式不用動 |
| `lib/agent/do_task` | `tasks.json` 的 `StateBad`／`WriteFailed` 與「沒折疊」那句 | 同上 |
| `lib/agent/subagent` | `subagents.json` 的 `ReadFailed`／`WriteFailed` | 走 `place`；帳不是陣列那一句原本直接印絕對路徑，改走 `place` |
| `lib/agent/fork` | `children/` 建不出來、寫不進去、抄 stack 失敗的錯誤行 | 走 `place`（`fork_copy._place`），程式不用動 |
| `lib/agent/claude`、`lib/agent/codex` | 小格裡 `mcp.json` 等寫不進去的錯誤行（經共用的 `cli_cfg`／`cli_cell`／`cli_mcp`） | 走 `place`，程式不用動 |
| `lib/base/mcp_tool` | 存圖片／聲音的提示行、存不進去的 `WriteFailed` | 上午認小格形狀的 `shown_path` 拿掉，改走 `place` |

沒動的（不算這一題）：

- `fork` 的 `details:` 行印的是分身 stack 相對那台 daemon 的路徑（portable-flow 的寫法，跟 daemon 表、`subagent` 的 `stack` 同一套），不是 `$AOS_STACK/…` 寫法。
- `cli_cell` 寫 `session.txt` 失敗的提醒行印絕對路徑，但只到 stderr、腦看不到。
- `tools_def`、`agent_def`、`cli_cfg` 用 `place` 印的是定義或工作區裡的路徑，不在小格裡，印法不變。
- `lib/aos/measure` 等審查工具用 `observed.call` 自己替子程式換 `AOS_STACK`（不經 aos-tools）：子程式繼承到的 `AOS_STACK_IN_CALLER` 跟它的 `AOS_STACK` 結尾對不上，自動當沒設。

## 施工（都進 main）

| commit | 做了什麼 |
|---|---|
| `841e61912` | `aos-tools call` 給 `AOS_STACK_IN_CALLER`；`--help`、README；新測試 `cmd/aos-tools/tests/test_stack_in_caller.py` 三例 |
| `909b076ad` | `tool_io.place` 照它印；`lib/tests/test_tool_io_place.py` 加兩例 |
| `869fa19ff` | `subagent` 那一句改走 `place`；`subagent`、`todo` 各加一例（`todo` 那例真的經 `aos-tools call`，照印出的字面從叫方的 stack 找得到檔） |
| `829c07be5` | code map 生成冊跟上前兩個 commit |
| `1be8cbcb5` | `mcp_tool` 收回認形狀的做法；加一例 |
| `62dda2703` | 條文與知識庫：NORMS 四種性質表、CONVENTION P-17 與 P-39、lib/docs/01 規則 11、`knowledge/aos/world.json` 的環境變數清單 |

每個新測試都先在沒改的程式上看過紅（例名與紅的樣子寫在各 commit 訊息）。收線前把環境裡的 `AOS_*` 全拿掉重跑：`cmd/aos-tools` 124、`lib/agent` 76、`todo` 15、`subagent` 21、`do_task` 20、`fork` 13、`mcp_tool` 22、`tools_def` 12、`agent_def` 29 例全過；`lib/tests` 162 例紅 1 支 `test_aos_lib_missing` 的 `kernel_llm` 子例（別線剛進的新工具夾，跟這題無關）。

## 什麼時候生效

- **存檔就生效**：`cmd/aos-tools`（`~/.local/bin` 連到 repo）——現在每次叫工具都多給 `AOS_STACK_IN_CALLER`。`lib/tool_io.py` 被指令直接 import 的那一份也是新的，但指令自己不是被 `aos-tools call` 叫的、沒有那個變數，印法不變。
- **要重抄進 `~/aos-home` 才生效**：`lib` 的工具夾（含它們用的 `tool_io.py`）與 `knowledge`。
- **新舊混搭的這段時間**：舊工具不讀新變數，印的跟以前一樣（`$AOS_STACK/檔`，從小格算——也就是這題要修的舊毛病還在，沒有變更糟）。重抄後才變成 `$AOS_STACK/tools/<登記名>/檔`。

## 代定（可翻案）

1. 變數叫 `AOS_STACK_IN_CALLER`、值是相對位置 `tools/<登記名>`，不是叫方 stack 的絕對路徑（理由見上面「決定」）。
2. 值跟自己的 `AOS_STACK` 結尾對不上＝當沒設（不報錯、不提醒）。
3. 歸四種性質表的 ① 執行環境。
4. `fork` 的 `details:` 行不改寫法。
5. 知識庫多寫一句「工具印的 `$AOS_STACK/…` 從你的 stack 算」。

## 沒驗的

- 真的在 `~/aos-home` 那棵樹上、重抄 lib 之後，腦照印出的路徑去開檔（這次都在暫存夾用 `aos-tools call` 驗）。
- 不是 Python 的工具（可執行檔、JSON 工具）自己讀 `AOS_STACK_IN_CALLER`：現在沒有這種工具會印小格路徑，只驗了變數有給到。
- 進 `aos-sandbox` 的工具拿不拿得到這個變數沒試；拿不到就照舊印法。
