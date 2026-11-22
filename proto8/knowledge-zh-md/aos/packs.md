# `knowledge/aos/packs.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/packs.md`，跟到正本 commit `c7bc08dae`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/packs.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

你的工具是一包一包來的。你有哪些工具包、每個工具做什麼（一句話），以及怎麼關掉一個工具包。

**`#/_index`**

# _index

- Tool packs: 工具包怎麼運作、agent-fsm 有哪幾包、每包的代價、怎麼加入或關掉一包。
- look: 工具包 look：read、ls、view、stat、grep、glob；看與搜尋檔案，什麼都不改。
- change: 工具包 change：write、edit、copy、move、mkdir；建立與修改檔案。
- delete: 工具包 delete：trash（可以復原）、remove（不能）。
- shell: 工具包 shell：shell、run_python；跑一個指令，讀它的輸出和結束碼。
- gadgets: 工具包 gadgets：peek_clock、peek_now_time、math、do_task（把你自己對話歷史裡的一件任務折成一段摘要；只有 agent-fsm）。
- events: 工具包 events：clock_register（送到你佇列的 clock 信：每 N 個週期、一次、在實際時鐘的某個時間，或 cron）、self_hook（有事發生在你身上時跑一個程式）。
- todo: 工具包 todo：todo（長任務用的你自己的待辦清單：ls、set、add、mark）。
- self: 工具包 self：self_tools、self_llm、self_system、self_history、self_state、self_ctl；看與修改你自己的那份副本。
- subagent: 工具包 subagent：subagent（你自己啟動的幫手）、agents_ctl（你 daemon 上的任何 agent）、fork（為了一個目標複製一份你自己；只有 agent-fsm）。
- def: 工具包 def：agent_def（新的 agent 定義）、tools_def（新的工具）。
- mailbox: 工具包 mailbox：mailbox_peek、mailbox_read、mailbox_send；agent 之間的信。
- goal: 工具包 goal：goal（你持續在做的一句話；你自己停下時會被提醒）。
- json: 工具包 json：json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set；用 FILE#/POINTER 一次處理 JSON 檔的一個位置。
- jsonx: 工具包 jsonx：jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_get、jsonx_multi_set；會跟著走或解開 $ref/$env 的 JSON 工具。
- comm: 工具包 comm：board_set、board_clear、board_wait、board_read、board_ls；一塊公開的看板，寫你在做什麼、在等誰。由配給包使用，不在任何內建定義裡。
- index: 工具包 index：index_view；透過一個節點的 index 看它，什麼都不改。
- kernel_gate: 工具包 kernel_gate：kernel_gate；當一個 kernel 閘門（請求來到你這裡，你決定，掛在你身上的一個站負責轉送）。不在任何內建定義裡。

**`#/Tool packs`**

# 工具包

你的工具是一包一包註冊的：每個工具包是 $AOS_HOME/lib/packs/<pack>.json 裡的一份工具清單，而定義的 tools.json 用 "$override" 把它要的工具包疊起來。agent-fsm 有十一個工具包（look、change、delete、shell、gadgets、todo、self、mailbox、goal、json、index），其中四個 self 工具是關掉的：共 36 個工具。self 工具包裡只開了 self_tools 和 self_state；需要時自己加入 self_llm、self_system、self_history 或 self_ctl：self_tools {"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_llm"}}。另外還有四個可選的工具包，不在任何內建範本（agent-fsm 或 eca）裡：events、subagent、def 和 jsonx。配給包（aos/kits.md）還會用到 comm 工具包（看板：你在做什麼、在等誰）。eca-claude 有五個（gadgets、self、mailbox、json、index；沒有 look、change、delete、shell、subagent、goal 或 todo 工具包：它的 CLI 有自己的檔案工具、shell、幫手、目標和待辦清單；也沒有 events、def 或 jsonx 工具包），並關掉 do_task（只有 agent-fsm）以及跟 agent-fsm 一樣的四個 self 工具（self_llm、self_system、self_history、self_ctl）：共 18 個工具；eca-pi 的清單一樣。在 eca 上，需要 events、def 或 jsonx 的某個工具時，自己一次加一個：self_tools {"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}}（clock_register、agent_def 和 tools_def 也在 /lib/tools/agent/ 裡；jsonx 的工具在 /lib/tools/aos/ 裡，像 /lib/tools/aos/jsonx_get）。eca 的子 agent（tools_sub.json）沒有 jsonx。還有一個工具包 kernel_gate，不在任何內建定義裡：用 self_tools 自己加入它的工具（`aos/kernel.md#/Being a kernel yourself: kernel_gate`）。

還有一個可選的工具包 ws-write（工具 ws_write），只在你自己的工作區裡寫文字檔（建立、附加、替換；每次呼叫 262144 位元組；在你自己的 stack 或定義裡的路徑、其他 agent 的 stack，或任何 .stack 資料夾都會被拒絕）。它不在任何內建定義裡；定義要在它的 "$override" 裡加上 lib/packs/ws-write.json。

一個工具包的代價：你有的每個工具包，都會隨著每次對你的腦提問一起送出（每個工具的名字、說明和參數）。每個工具包送出時的字元數：

| 工具包 | 工具數 | 字元數 |
|---|---|---|
| look | 6 | 4,743 |
| change | 5 | 2,284 |
| delete | 2 | 771 |
| shell | 2 | 1,006 |
| gadgets | 4 | 1,615 |
| todo | 1 | 1,032 |
| self | 6 | 5,439 |
| mailbox | 3 | 2,367 |
| goal | 1 | 865 |
| json | 9 | 5,856 |
| index | 1 | 998 |
| events（可選） | 2 | 10,263 |
| subagent（可選） | 3 | 10,940 |
| def（可選） | 2 | 6,427 |
| jsonx（可選） | 8 | 11,961 |
| comm（可選） | 5 | 6,120 |
| ws-write（可選） | 1 | 1,067 |
| kernel_gate（可選） | 1 | 1,442 |

怎麼加入一個工具包：做定義的人在它 tools.json 的 "$override" 裡加一項，例如 {"$env": "AOS_HOME", "$path": "/lib/packs/subagent.json"}；配給包也可以加（aos/kits.md）。在做定義時就加，不要在 agent 跑的時候加：self_tools add 一次只加一個工具，而你工具清單的每次改動，都會讓腦失去你對話開頭的快取。

- 看你每個工具從哪裡來：self_tools {"op": "ls", "long": true}（FROM 欄顯示 lib/packs/<pack>.json）。
- 替你自己關掉一個工具：self_tools {"op": "rm", "name": "shell"}。
- 要關掉整個工具包，就把它從定義 tools.json 的 "$override" 清單裡移掉（這是人或定義的改動，不是一次工具呼叫）。
- 說明開頭是 `[MCP server NAME]` 的工具，來自外部的 MCP server，不是內建工具包：`aos/cli/mcp_import.md#/Where an external tool comes from`。

**`#/look`**

# look

工具包 look：只讀的檔案工具：read（一個文字檔）、ls（一個資料夾）、view（一個檔案，附它的類型）、stat（關於一個路徑的資訊）、grep（在檔案裡搜尋，像 grep -rn）、glob（用名字樣式找檔案）。每個工具一個節點：aos/tools/read.md、aos/tools/ls.md、aos/tools/view.md、aos/tools/stat.md、aos/tools/grep.md、aos/tools/glob.md。

**`#/change`**

# change

工具包 change：編輯檔案：write（整個檔案）、edit（替換一字不差的文字）、copy、move（也能改名）、mkdir。每個工具一個節點：aos/tools/write.md、aos/tools/edit.md、aos/tools/copy.md、aos/tools/move.md、aos/tools/mkdir.md。

**`#/delete`**

# delete

工具包 delete：trash（移進你工作區的 .trash/，可以移回來）和 remove（真的刪除；資料夾要 recursive）。每個工具一個節點：aos/tools/trash.md、aos/tools/remove.md。

**`#/shell`**

# shell

工具包 shell：shell（一個 bash 指令；不是沙盒）和 run_python（一個短的 Python 程式）。每個工具一個節點：aos/tools/shell.md、aos/tools/run_python.md。

**`#/gadgets`**

# gadgets

工具包 gadgets：好用的小工具：peek_clock（daemon 的 clock：目前的週期和 interval_ms；你沒有 daemon clock 時是 ClockMissing）、peek_now_time（目前的 UTC 時間，或給 local: true 時是本地時間）、math（一個算式）、do_task（只有 agent-fsm：在你自己的對話裡開始一件任務，結束時用一段摘要取代它的訊息；看 aos/me/do_task.md）。

**`#/events`**

# events

工具包 events：之後才會跑的東西：clock_register（固定的一封信，每 N 個週期、N 個週期後一次、在實際時鐘的某個時間，或用 cron；不給 box 就是叫醒你自己；aos/clock.md）和 self_hook（有事發生在你身上時跑一個程式）。

**`#/self`**

# self

工具包 self：看與修改你自己：self_tools（你的工具）、self_llm（你的腦的設定）、self_system（你的系統文字）、self_state（關於你的資訊和數字）、self_ctl（停止、暫停、睡眠或移除你自己）、self_history（你的對話）。出廠時的 agent-fsm 只開了 self_tools 和 self_state；其他的用 self_tools 加入。

**`#/subagent`**

# subagent

工具包 subagent：其他 agent：subagent（你自己啟動的 agent；算在你的配額裡）和 agents_ctl（你 daemon 的表上任何一個 agent；不算），以及 fork（只有 agent-fsm：為了一個目標複製一份你自己，連設定和整段對話；只有它簡短的結論會回來；看 aos/agents/fork.md）。

**`#/def`**

# def

工具包 def：定義：agent_def（把一個範本複製成新的 agent 定義，或檢查一份）和 tools_def（從 Python 骨架做一個新工具，或檢查一個工具）。

**`#/mailbox`**

# mailbox

工具包 mailbox：信：mailbox_peek（有什麼在等，不拿走）、mailbox_read（讀最舊的那封）、mailbox_send（寄一封）。

**`#/goal`**

# goal

工具包 goal：goal 在你的 stack 裡保存你正在做的一句話（get、set、done、pause、resume）。當你自己停下（你的回覆沒有呼叫任何工具）而且沒有信在等時，aos 會給你一個簡短的「[aos] goal: ...」提醒；done 或 pause 會停止提醒。在 agent-fsm 裡，你暫停自己的目標之後又來了一則訊息時，你會收到一則「[aos] goal: paused ...」的提示，問你要繼續、完成，還是繼續等；目標本身不會被恢復。一個節點：aos/tools/goal.md。

**`#/todo`**

# todo

工具包 todo：todo 在你的 stack 裡、在你的對話歷史之外，保存長任務用的你自己的待辦清單（ls、set、add、mark）；它不會自己顯示給你，所以要再看就呼叫 ls。一個節點：aos/tools/todo.md。

**`#/json`**

# json

工具包 json：一般的 JSON，一次一個位置，路徑一律是 `FILE#/POINTER`：json_get（一個值）、json_ls（裡面有什麼，像 ls）、json_search（找一個鍵或值）、json_len（長度：鍵數、項目數或字元數）、json_set（設定一個值）、json_add（加一個鍵或陣列項目，絕不覆蓋）、json_del（刪掉一個）；json_multi_get 和 json_multi_set 一次呼叫處理好幾個位置，每個一行結果。值照給的樣子原樣存；`$ref`/`$env` 物件就當一般物件。每個工具一個節點：aos/tools/json_get.md、aos/tools/json_ls.md、aos/tools/json_search.md、aos/tools/json_len.md、aos/tools/json_set.md、aos/tools/json_add.md、aos/tools/json_del.md、aos/tools/json_multi_get.md、aos/tools/json_multi_set.md。

**`#/jsonx`**

# jsonx

工具包 jsonx：給有 `$ref`/`$env` 的 aos 設定檔用：jsonx_get、jsonx_ls 和 jsonx_search（follow、resolve），jsonx_set 和 jsonx_add（value、text 或 from；follow、resolve、check），jsonx_del（follow）；jsonx_multi_get 和 jsonx_multi_set 一次呼叫處理好幾個位置，選項設一次就全部適用。沒有任何內建範本有它（agent-fsm、eca-claude、eca-pi）；由定義加入，或你用 self_tools 一次加一個工具。每個工具一個節點：aos/tools/jsonx_get.md、aos/tools/jsonx_ls.md、aos/tools/jsonx_search.md、aos/tools/jsonx_set.md、aos/tools/jsonx_add.md、aos/tools/jsonx_del.md、aos/tools/jsonx_multi_get.md、aos/tools/jsonx_multi_set.md。

**`#/comm`**

# comm

工具包 comm：看板（board），是你 stack 上一則簡短的公開便條，寫你在做什麼、在等誰，讓別人（以及使用者的總覽頁）在寄信給你之前可以先讀：board_set（貼出你的看板：狀態 here、busy、dnd 或 away，你在做什麼，什麼時候回來）、board_clear（撤下）、board_wait（加入或移除一行你在等誰）、board_read（讀一塊看板：某個 agent 的、使用者的或你自己的）和 board_ls（你 daemon 的表上的每一個）。不在任何內建定義裡；配給包會加入它（aos/kits.md）。這些工具還沒有自己的頁面：每個工具的說明會講怎麼呼叫。

**`#/index`**

# index

工具包 index：index_view，透過一個節點的 index（agent 們對它底下有什麼所記的筆記）看它；要改 index 就用 json 工具。一個節點：aos/tools/index_view.md。

**`#/kernel_gate`**

# kernel_gate

工具包 kernel_gate：kernel_gate 讓你成為一個 kernel 閘門：其他 proc 把要啟動或改變 proc 的請求寄到你的一個信箱，一個掛在你身上的 kernel 站（station）把每個請求先扣住，你會收到通知（「[aos] kernel_hold: ...」），然後用 op pass 或 op refuse 決定，站再把你放行的轉送出去。不在任何內建定義裡；用 self_tools {"op": "add", "path": "<AOS_HOME>/lib/tools/agent/kernel_gate"} 加入。看 `aos/kernel.md#/Being a kernel yourself: kernel_gate`。
