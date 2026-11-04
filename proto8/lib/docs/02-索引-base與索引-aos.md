← [回入口 README.md](../README.md)｜段落：索引：base、索引：aos｜上一份：[01-分層等](01-分層等.md)｜下一份：[03-索引-agent等](03-索引-agent等.md)

## 索引：base

回 JSON 的工具裡，計數（幾個、幾行、幾字）的 key 一律 `counter_<被數的東西>`（10-25 使用者「計數這塊，幫我改成counter_*」，C-54 命名方法 R6）；陣列本身（`items`、`keys` 清單）不加。aos 那幾個：信的是 `counter_hops`、memory 頂層索引的是 `counter_active`。

| 工具 | 一句話 | 參數 | 回什麼 |
|---|---|---|---|
| [read](../base/read/) | 讀工作區裡一個文字檔，太長從頭截 | `path`、`offset`、`max_lines` | 內容（不加行號）；被截時尾巴寫從第幾行接著讀 |
| [write](../base/write/) | 整份寫進一個檔（建或蓋）、上層資料夾自動建 | `path`、`content` | 一行：寫了幾 bytes |
| [edit](../base/edit/) | 幾處照字面替換，一處不合整個不改 | `path`、`edits[{old_text, new_text}]` | 一行：換了幾處 |
| [bash](../base/bash/) | 在工作區用 bash 跑一行指令 | `command`、`timeout_s`（30／300） | stdout＋stderr 合在一起、尾巴寫結束碼；留最後 2000 行／50KB |
| [ls](../base/ls/) | 列一個資料夾的子項，一次一頁 | `path`、`offset`、`max_items`（100／500）、`hidden` | JSON：`counter_items`（一共幾項）、`items[{name, type, size, mtime}]`（資料夾多 `counter_children`、`aos`，檔多 `exec`，`.json` 多 `keys`）、`next_offset`、`counter_hidden` |
| [stat](../base/stat/) | 單一個檔或資料夾的屬性 | `path` | JSON：`type`、`mtime`、`mode`；檔多 `size`、`exec`、`text`、`counter_lines`、`format`、`top` |
| [view](../base/view/) | 漸進看一個檔：JSON 照指標一次一層、大文字檔先給大綱 | `path`、`pointer` 或 `start`／`end` | JSON：`value` 或 `children`；文字的 `text` 或 `outline` |
| [json_read](../base/json_read/) | 看一份 JSON 檔的某個位置，大的摺起來 | `path`、`pointer`、`depth`（1／10） | JSON：`value`，物件摺成 `{type, keys}`、陣列 `{type, counter_items}`、長字串 `{type, counter_chars, head}` |
| [json_edit](../base/json_edit/) | 照指標改幾個位置，一處不合整份不寫 | `path`、`set{指標: 值}`、`del[指標]` | JSON：`counter_set`、`counter_del`（改了幾個）、頂層 key |
| [mkdir](../base/mkdir/) | 建資料夾（上層一起建；已有＝沒事） | `path` | JSON：`path`、`created` |
| [move](../base/move/) | 搬移或改名（to 有東西就不搬） | `from`、`to` | JSON：`from`、`to` |
| [copy](../base/copy/) | 複製檔或整個資料夾（捷徑照捷徑） | `from`、`to` | JSON：`from`、`to`、`counter_files` |
| [trash](../base/trash/) | 丟進 `.trash/<時間>/`（不真的刪，move 救回） | `path` | JSON：`path`、`to` |
| [math](../base/math/) | 算一個算術式子（不用 eval） | `expr` | 結果 |
| [clock](../base/clock/) | 現在的 UTC 時間 | （無） | `2026-10-23T08:00:00Z` |
| [run_python](../base/run_python/) | 跑一段 Python，回結束碼與輸出 | `code`、`timeout_s`（60／300） | 第一行「結束碼 N」、接著輸出 |

不碰工作區的三個（`math`、`clock`、`run_python`）不收路徑、不看 `$AOS_WS`；`run_python` 把程式寫進自己的小格再跑（規則 8 的例外：拿小格當草稿區，不跨呼叫留東西）。
每個工具的細節看它 `_entry` 開頭的幾行說明與 `_tooldef.json`。

## 索引：aos

| 工具 | 一句話 | 參數 | 回什麼 |
|---|---|---|---|
| [memory](../aos/memory/) | 長期記憶庫：存、找、讀、忘（庫在 `$AOS_HEAP`，沒設＝`$AOS_WS/.heap/`） | `op`（save／search／read／forget）、`kind`、`title`、`text`、`tags`、`query`、`max_results`、`id`、`reason` | 給模型看的文字 |
| [send_message](../aos/send_message/) | 寄信給名冊（`$AOS_ROSTER`）上的成員或群組 | `to`、`subject`、`body`、`expect_reply` | 一行：寄了幾封、對話串第幾手 |
| [check_inbox](../aos/check_inbox/) | 看自己信箱還沒處理的（只看不拿） | （無） | 一封一行摘要 |

這幾個的「模型的錯」也照規則 3 退 1；回不回給腦由用它們的 agent 的 act 決定（11-04 前的例子 agent-meg、talk 的 member 都回給腦、不停，同 agent-pip；隨 demo 刪了）。
`memory` 的 `$AOS_HEAP`、`send_message` 的 `$AOS_ROSTER`是規則 4「只碰 `$AOS_WS`」的例外，照原樣留著（放哪由叫的人決定，像 stack）。

**共用模組 [aos_ws.py](../aos/aos_ws.py)**（不是工具、沒有 `_entry`）：「寄信、等答案、讀 stack」；照 agent 對話協議（[CONVENTION P-42](../../docs/CONVENTION/02-題目stack停錯腦/02-P-42.md)）只碰 stack——`stack_of`、`letter_key`（信件名稱的處理順序：有序 `^[0-9]{12}\.` 在前照名字、無序在後照名字，同 aos-post；11-03）、`names`（照 `letter_key` 排）／`where`／`waiting`（queue 的 new／cur／archive）、`put`（一則 user message，`aos-post init`＋`send --ordered`，PATH 上要有 aos-post）、`history`／`answers`／`exchanges`（回答＝沒有 tool_calls 的 assistant）；不認舊協議的工作區 `new/`／`out/`。給人用的 [proto8/extras/human](../../extras/human/README.md)（aos-say／listen）用 realpath 找到這個資料夾 import（11-03 aos-ai 刪了，只服務它的 `loop_state`、`tail_jsonl` 跟著拿掉）。
