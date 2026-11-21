# `knowledge/aos/tools/_index.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/_index.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**（index：鍵 → 一句說明）

| 鍵 | 說明 |
|---|---|
| `read.json` | 工具 read：把一個文字檔當成純文字行讀出來，檔案大就分段讀。 |
| `ls.json` | 工具 ls：列出一個資料夾，每個項目一行；long 和 json 看細節。 |
| `view.json` | 工具 view：一步一步看進一個檔案：JSON 一層一層看，大的文字檔先看大綱。 |
| `stat.json` | 工具 stat：關於一個檔案、資料夾或連結的資訊，用 JSON 給（類型、大小、行數、格式）。 |
| `grep.json` | 工具 grep：用正規表示式在檔案裡搜尋，像 grep -rn；每個符合的地方一行 PATH:LINE:TEXT。 |
| `glob.json` | 工具 glob：在一個資料夾底下用名字樣式（*、**、?）找檔案；每行一個路徑。 |
| `write.json` | 工具 write：寫入整個檔案（新的，或整個替換）。 |
| `edit.json` | 工具 edit：用一字不差的文字替換，改一個文字檔的一部分。 |
| `copy.json` | 工具 copy：把一個檔案或整個資料夾複製到新路徑。 |
| `move.json` | 工具 move：移動或改名一個檔案、資料夾或連結；也能把東西從垃圾桶拿回來。 |
| `mkdir.json` | 工具 mkdir：建立一個資料夾，連同它的上層；資料夾已經存在也沒關係。 |
| `json_get.json` | 工具 json_get：一個 FILE#/POINTER 位置的值，印成一行 JSON；超過 max_bytes 時是 [too big]。 |
| `json_ls.json` | 工具 json_ls：JSON 檔某個位置裡面有什麼，每行一個鍵或索引；long 看類型和大小。 |
| `json_search.json` | 工具 json_search：在某個位置底下（或它上面的幾層）找一個鍵和／或值；每找到一個就給一個 FILE#/POINTER。 |
| `json_set.json` | 工具 json_set：把 JSON 檔的某個位置設成一個值，照給的樣子原樣存；/- 是附加到最後。 |
| `json_add.json` | 工具 json_add：加入一個新的鍵或陣列項目（插入）；絕不覆蓋（KeyExists）。 |
| `json_del.json` | 工具 json_del：從 JSON 檔刪掉一個鍵或陣列項目。 |
| `json_len.json` | 工具 json_len：某個位置的長度：物件的鍵數、陣列的項目數、字串的字元數。 |
| `json_multi_get.json` | 工具 json_multi_get：一次取好幾個 FILE#/POINTER，每個位置一行；失敗按位置個別報，最後是 PlacesFailed。 |
| `json_multi_set.json` | 工具 json_multi_set：照順序設定好幾個位置，每個位置一行；其中一個失敗時，前面做過的都不會復原。 |
| `index_view.json` | 工具 index_view：透過一個節點的 index 看它（KEY<TAB>description）；這是一個視角，不是事實本身。 |
| `jsonx_get.json` | 工具 jsonx_get：給 aos 設定檔用的 json_get：跟著 $ref 走、解開 $ref/$env。 |
| `jsonx_ls.json` | 工具 jsonx_ls：給 aos 設定檔用的 json_ls：跟著 $ref 走、列出解開後的值。 |
| `jsonx_search.json` | 工具 jsonx_search：給 aos 設定檔用的 json_search：跟著 $ref 走、搜尋解開後的值。 |
| `jsonx_set.json` | 工具 jsonx_set：給 aos 設定檔用的 json_set：value、text 或 from；follow、resolve、check。 |
| `jsonx_add.json` | 工具 jsonx_add：給 aos 設定檔用的 json_add，選項跟 jsonx_set 一樣。 |
| `jsonx_del.json` | 工具 jsonx_del：給 aos 設定檔用的 json_del：路上的 $ref 受保護，除非給 follow。 |
| `jsonx_multi_get.json` | 工具 jsonx_multi_get：像 jsonx_get 那樣讀的 json_multi_get（每個位置都 follow、resolve）。 |
| `jsonx_multi_set.json` | 工具 jsonx_multi_set：像 jsonx_set 那樣做的 json_multi_set：每一項各自 value、text 或 from；follow、resolve、check 對全部適用。 |
| `trash.json` | 工具 trash：可以復原的刪除（移進你工作區的 .trash/）。 |
| `remove.json` | 工具 remove：真的刪除，像 rm；不能復原（資料夾要 recursive）。 |
| `shell.json` | 工具 shell：在你的工作區跑一行 bash 指令；輸出最後是 [exit code N]。 |
| `run_python.json` | 工具 run_python：跑一個短的 Python 3 程式；輸出最後是 [exit code N]。 |
| `peek_clock.json` | 工具 peek_clock：daemon clock 目前的週期，以及一個週期是多少 ms。 |
| `peek_now_time.json` | 工具 peek_now_time：目前的時間，預設是 UTC，給 {"local": true} 時是本地時間。 |
| `math.json` | 工具 math：計算一個算式；允許什麼、範例、ExprBad。 |
| `todo.json` | 工具 todo：長任務用的你自己的待辦清單（ls、set、add、mark）；存在你的對話歷史之外。 |
| `goal.json` | 工具 goal：你的目標，你自己停下時會被提醒；set、done、pause、resume。 |
| `../mailbox.json#/tools` | 指標。工具 mailbox_peek、mailbox_read、mailbox_send：看有哪些信在等、讀最舊的那封、寄一封。講在 aos/mailbox.json#/tools。 |
| `../user_zone.json#/send` | 指標。工具 user_send：寄一封 decide/verify/trial/chore/fyi 信到使用者區。講在 aos/user_zone.json#/send。 |
| `../user_zone.json#/answer` | 指標。工具 user_verify：檢查一封回覆信真的是從使用者區來的。講在 aos/user_zone.json#/answer。 |
| `../clock.json#/wake_me` | 指標。工具 clock_register：clock 每 N 個週期送來的信（add、rm、ls）；只送一次、在某個時間或 cron：aos/clock.json#/wake_at。講在 aos/clock.json#/wake_me。 |
| `../me/self_hook.json#/_description` | 指標。工具 self_hook：有事發生在你身上時，跑一個你的程式（你自己的 hook、on_clock 計時器）。講在 aos/me/self_hook.json。 |
| `../me/do_task.json#/_description` | 指標。工具 do_task（只有 agent-fsm）：在你自己的對話裡做一件任務，只留下它的摘要。講在 aos/me/do_task.json。 |
| `../me/self_tools.json#/_description` | 指標。工具 self_tools：改你自己的工具清單。講在 aos/me/self_tools.json。 |
| `../me/self_llm.json` | 指標。工具 self_llm：改你自己的腦的設定。講在 aos/me/self_llm.json（整個檔案是一段文字）。 |
| `../me/self_system.json` | 指標。工具 self_system：看或改你自己的系統文字。講在 aos/me/self_system.json（整個檔案是一段文字）。 |
| `../me/self_history.json#/_description` | 指標。工具 self_history：列出、刪除、摘要或替換你自己對話裡的訊息。講在 aos/me/self_history.json。 |
| `../me.json#/self_state` | 指標。工具 self_state：關於你自己的資訊和數字；它只讀。講在 aos/me.json#/self_state。 |
| `../me.json#/self_ctl` | 指標。工具 self_ctl：停止、暫停、讓你自己睡眠或移除你自己。講在 aos/me.json#/self_ctl。 |
| `../agents/subagent.json#/_description` | 指標。工具 subagent：啟動並管理屬於你的 agent（算在你的配額裡）。講在 aos/agents/subagent.json。 |
| `../agents.json#/agents_ctl` | 指標。工具 agents_ctl：對你 daemon 的表上任何一個 agent 用的 aos-agent ctl，不只是你的。講在 aos/agents.json#/agents_ctl。 |
| `../agents/fork.json#/_description` | 指標。工具 fork（只有 agent-fsm）：為了一個目標複製一份你自己；只有它簡短的結論會回來。講在 aos/agents/fork.json。 |
| `../agents.json#/agent_def` | 指標。工具 agent_def：從一個範本做出新的 agent 定義，或檢查一份。講在 aos/agents.json#/agent_def。 |
| `../tools_def.json#/tools_def` | 指標。工具 tools_def：從 Python 骨架做一個新工具，或檢查一個工具。講在 aos/tools_def.json#/tools_def。 |
| `../kernel.json#/gate` | 指標。工具 kernel_gate：當一個 kernel 閘門：其他 proc 的請求會被扣住，你一個一個放行或拒絕。講在 aos/kernel.json#/gate。 |
| `../cli/mcp_import.json#/errors` | 指標。mcp_tool：執行每一個匯入的外部 MCP 工具的程式（你從來不會用名字呼叫它）；它的錯誤代號。講在 aos/cli/mcp_import.json#/errors。 |
| `_description.json` | 每個在這裡有一頁的內建工具一個節點：它做什麼、什麼時候用、它的參數、附真實輸出的範例和錯誤；怎麼讀指標列（以 ../ 開頭的鍵）；工具包在 aos/packs.json。 |
