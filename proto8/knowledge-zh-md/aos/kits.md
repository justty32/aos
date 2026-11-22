# `knowledge/aos/kits.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/kits.md`，跟到正本 commit `d9c9e2d79`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/kits.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

**`#/Kits: ready-made system text and tools for one agent role`**

# 配給包：給某一種 agent 角色、現成的系統文字與工具

配給包是給一種角色（收集者、審查者）的一份系統文字加一組工具，蓋在一個新的 agent-fsm 定義上。配給包放在範本資料夾裡，在 `agent-fsm/` 旁邊的 `templates/kits/`；那裡的 `kits.json` 列出它們。配給包本身不是範本：它是一個放著 system.txt 和 tools.json 的資料夾。你先做一個 agent-fsm 定義，再把配給包的檔案複製蓋上去（人也可以改成把這個資料夾交給 `aos-agent ctl add --kit`）。

- 怎麼用配給包做 agent：`aos/kits.md#/Make an agent from a kit`。
- 配給包的系統文字怎麼由幾層組成：`aos/kits.md#/Layers of a kit's system text`。
- 配給包為什麼砍工具，又砍掉了哪些：`aos/kits.md#/Why a kit cuts tools`。
- 配給包還沒強制的事：`aos/kits.md#/What a kit does not enforce yet`。

**`#/Make an agent from a kit`**

# 用配給包做 agent

1. agent_def {"op": "new", "template": "agent-fsm", "path": "defs/gather"}
2. 把 `templates/kits/gather/system.txt` 和 `templates/kits/gather/tools.json` 複製蓋到 `defs/gather/system.txt` 和 `defs/gather/tools.json`（tools.json 用 {"$env": "AOS_HOME"} 指名它的工具包，所以複製到哪裡都能用）。
3. 在 `defs/gather/llm.json` 設定腦（aos/brain.md）。
4. agent_def {"op": "check", "path": "defs/gather"}：問題清單是空的＝好了。
5. 用 subagent add 啟動它，並給它一份交辦（brief）：唯一的任務、它可以讀寫的路徑、要在 out/ 交出什麼、完成條件（它會把這個抄進它的目標），以及知識資料夾的路徑。

審查者的話，用 `templates/kits/review/` 做一樣的事（它的 tools.json 跟 gather 的一樣）。同一種角色的好幾個 agent 可以共用一個定義。

人從 shell 接上 agent 時不用複製：`aos-agent ctl add --kit KIT-FOLDER ...`（或 `ctl set-def --kit KIT-FOLDER NAME DEF`）會把配給包的 system.txt 和 tools.json 寫進那個 agent 的 stack，當成它自己的副本，定義則保持原樣。stack 裡已經有的自己的副本會被取代，所以給另一個配給包就是換配給包。eca 定義也收配給包：它的系統文字接在 CLI 自己的後面，它的 tools.json 取代 aos 工具，但 CLI 內建的工具（Bash、Read...）還在，所以配給包的工具限制在 eca 上不成立。`aos-agent system reset` 和 `aos-agent tools reset` 會再把配給包拿掉。

**`#/Layers of a kit's system text`**

# 配給包系統文字的層次

系統文字沒有 include 也沒有變數：每次腦呼叫都整份送出，所以它在做定義時組一次，由上到下：

1. 通用：`kits/general.A.txt`（A 級＝強的通用模型）：開始（self_state、讀知識庫、設目標）、工作區資料夾（notes.md、out/、trash/）、工作、回報（給領頭的人一次 mailbox_send）、卡住、公告板（notice board）、停止。
2. 現場（site，可選，沒附）：你自己的規則（要回報給誰、語言、當地的禁止事項、公告板在哪裡）。放在通用和角色之間。
3. 角色：`kits/roles/gather.txt` 或 `kits/roles/review.txt`。
4. 任務：交辦，放在啟動 agent 的那封信裡寄；不在 system.txt 裡。

general.A.txt 有佔位字：`<KNOWLEDGE>`（知識資料夾的路徑）、`<BOARD>`（怎麼讀公告板：一個指令，或一個要讀的檔；沒有就刪掉這一行）、`<OWN_BOARD>`（agent 怎麼公告它在等誰，或刪掉這一行）。附的 `gather/system.txt` 和 `review/system.txt` 寫明交辦會點出知識資料夾，把 BOARD 落實成 board_read（who＝被等的那位，或用 "user" 看使用者的公告），把 OWN_BOARD 落實成 board_wait（停下來等時寫 who 和 what，回覆來了寫 done = true），而且都在 3,500 字元以內。如果你改了某一層，照同樣順序再組一次。

**`#/Why a kit cuts tools`**

# 配給包為什麼砍工具

每個工具的定義每次腦呼叫都會送出，所以工具清單是最大的固定成本，比系統文字還大。每個工具包的字元數：`aos/packs.md#/Tool packs`。

gather 的工具組保留 look、change（只有 write、edit、mkdir）、gadgets（不含 do_task）、todo、mailbox、comm（只有 board_read 和 board_wait；board_set、board_clear 和 board_ls 關掉）、goal、json（只讀）、index 和 self_state。它砍掉 shell、delete、events、subagent、def、jsonx 和 kernel_gate。self_tools、self_system、self_llm、self_history 和 self_ctl 關掉，所以 agent 沒辦法把工具還給自己，也沒辦法改寫自己的規則。單一工具怎麼關掉：aos/packs.md。

**`#/What a kit does not enforce yet`**

# 配給包還沒強制的事

- 只在工作區裡寫，是系統文字裡的一條規則；檔案工具本身不會擋住工作區外的路徑，也還沒有 hook 強制它。
- 只有 A 級通用文字和兩種角色（收集者、審查者）。小模型可能略過開始和停止規則的一部分（notes.md、交接）。
