← [入口](README.md)｜涵蓋：實作步驟 5～8（跟 aos-agent 實作重疊的檔，排在它落地之後）｜上一份 [07-實作步驟](07-實作步驟.md)

# 實作步驟（續）：等 aos-agent 落地再做

重疊的檔：`bin/aos-tools`（aos-agent 加 `tools` 子介面會改它）、`impls/aos-daemon`（加 `exec` 欄）、`bin/aos-daemon-ctl` 與 `child.cpp`（`AOS_DAEMON` 改名）、N-63／N-28（改名加註）、`demo/agent-fsm`、`extras/human`／`extras/eca`（會刪）。**下面每步開工前先 `git log` 確認 aos-agent 的 commit 進了 main**，在它之上改，免得兩邊互蓋。

## 步 5：aos-tools——沒 stack 報錯（題 1）＋ `_metainfo.json`（題 8）

- `bin/aos-tools:311` 沒 `AOS_STACK` 時不再用暫存資料夾，報 `StackMissing`、退 1（`call` 要寫 `tool_call.json`）；README 與 usage 改。
- `_metainfo`→`_metainfo.json`：`git mv` lib 底下 22 個 `_metainfo`（`lib/agent/claude`、`codex`、`pyfix`、`lib/aos/check_inbox`、`memory`…全列用 `find proto8/lib -name _metainfo`）；aos-tools `:136-140` 只認帶 `.json` 的（`_tooldef.json`、`_metainfo.json`，不再先找不帶的）；`lib/base/ls/_entry:13`、`stat/_entry:74` 的 `AOS_MARKS` 改；`extras/ai_tools/bin/aos-mcp`、`extras/sandbox/bin/aos-sandbox` 讀 `_metainfo` 的地方改；步 0 那個 symlink 一起對。kernel 讀**單子裡**的 `_metainfo` key（`letter.cpp:186`）是 key 不是檔，不動。
- 驗證：`test_aos_tools.py`、`test_lib.py`、`test_file_tools.py`、`test_aos_mcp.py`、`test_sandbox.py`、llm-kernel ctest；加「沒 `AOS_STACK` 的 `call`＝`StackMissing`」「只有舊名 `_metainfo` 的工具＝`ls` 不列／`add` 報 `MetainfoMissing`」兩案。
- 條文：R10／R11 加註「11-04：`_` 開頭＝aos 認的固定檔（`_entry` 是程式、不帶副檔名；`_tooldef.json`、`_metainfo.json` 是資料、帶 `.json`）」；P-41 的 `tool.json` 字樣加註現名；lib README、`impls/docs/` 的 metainfo 說明；N-63 加「`AOS_STACK` 只有 aos-exec 給預設（它負責建），其他程式沒設＝`StackMissing`；替人下 aos-exec 的人殼指令算成那一跳、照 aos-exec 的預設」（題 1）。

## 步 6：daemon——三個名字可設（題 6）、信箱預設名（題 5 後半）、型別寫清楚（題 3）、不補名

- **三個名字可設**：daemon.json 頂層加 `procs_loop`（預設 `"loop.json"`）、`procs_exec`（`"exec.json"`）、`procs_stderr`（`"stderr.txt"`）——主題 `procs` 在前，跟 `procs_ctl`／`procs_state` 同一排（R7）；暫存檔跟著（`.<名>`）；**寫進 `procs_state.json` 頂層回報**（像 state 窗回報 `max`／`interval_ms`），讀小格的人（aos-daemon-ctl `pause`／`resume`／`stop` 讀小格 loop.json 的 `ctl` 那格、adopt、aos-agent）從窗拿名字、不寫死。動：`impls/aos-daemon/src/child/child.cpp:98,164-168,185-189`、`daemon.cpp`（讀 key、adopt 用同名）、`windows.cpp:209`（回報）、docs、README；`bin/aos-daemon-ctl:52-53,269`（改讀窗上的名字）。名字可翻案。
- **`procs_ctl_mailbox` 沒寫＝預設 `"procs_ctl_mailbox/"`、`null`＝不開**（跟 `procs_ctl` 同形；`daemon.cpp:291-300`）；aos-daemon-ctl 寫死的 `MAILBOX`（`:78`）改成讀 `procs_state.json` 回報的名字（daemon 同樣在窗上回報 `procs_ctl_mailbox`；回報欄名＝key 名）。
- **型別文件寫清楚（題 3，不改程式）**：`impls/aos-daemon/docs/01-用法.md` 與 N-28 加一段白話＋三個例子：字串／陣列＝exec 型（跑一次）；物件只有 `exec`（可加 `ws`、`stack`）＝exec 型；物件多任何一個 loop 的 key（`max`、`interval_ms`、`ctl`、`state`）＝loop 型；**要一直跑最少寫 `"interval_ms": 0`**；aos-daemon-ctl 替 loop 型補 `ctl`／`state` 就是為了這條。
- **不補名**：步 4 之後 aos-loop 自己有預設名，`child.cpp:152-157` 補 `ctl.json`／`state.json` 那段刪掉；`aos-daemon-ctl:132` 補名改成只在「loop.json 只有 `exec`」時補 `"interval_ms": 0`（讓 daemon 認成 loop 型，照題 3 的規則；補哪個 key 實作時代定）。
- 驗證：aos-daemon ctest（加：改三個名字後小格裡是新名、窗有回報；`procs_ctl_mailbox` 沒寫也開、`null` 不開）、`test_daemon.py`、`test_aos_daemon_ctl.py`（pause／resume 經窗上的名字找 ctl）；aos-agent 的測試全綠。
- 條文：N-28 加註（三個 key、預設、回報；信箱預設名；型別判法例子）；N-54（daemon ctl／信箱）加註；P-42／N-16 不動。

## 步 7：aos-daemon-ctl `add` 不看 `loop.json` 在不在，看入口最終指到的 JSON（題 4）

使用者：「add這塊，就是看最終指向的json的內部結構。」

- 做法：`add XXX` 照 aos-exec 的找法走到入口（N-61 的子集，Python 重寫一小段、不加新機制）：`XXX/$AOS_ENTRY`（預設 `_entry`；沒有補 `.json`）→ 可執行檔＝**exec 型**；JSON 陣列且 `[0]` 是 `aos-loop`＝第二個元素是 loop 設定檔、讀它；JSON 字串＝轉向、再來一遍（繞圈＝`EntryBad`）；JSON 物件有 `argv`＝單子＝exec 型；物件沒 `argv`、有 `exec`＝它就是 loop 設定；物件沒 `argv` 沒 `exec`＝取 `js["_entry"]` 再來。拿到 loop 設定（整份有 `exec`）＝**loop 型**，子項設定照現在的做法（`exec` 換 `<那份檔>#/exec`、相對路徑從那份檔的資料夾算）；走到頭不是 loop 設定＝exec 型。**不看檔名**：`loop.json` 這個名字不再出現在 aos-daemon-ctl 裡。
- `.env` 設的 `AOS_ENTRY` 這一步不讀（只為判型、不是真的跑；加一句到 README）；`#/` 入口照 N-62 切。
- 動：`bin/aos-daemon-ctl:123,232` 一帶、README；aos-agent `add` 底下叫它，行為自動跟上。
- 驗證：`test_aos_daemon_ctl.py` 加四案：`_entry`＝`["aos-loop","loop.json"]`（demo 兩個範本）→ loop 型；`_entry` 是 sh 檔（fixtures）→ exec 型；`_entry` 字串轉向到 `x.json` 有 `exec` → loop 型；入口 JSON 單子 → exec 型。aos-agent 測試全綠。
- 條文：N-28「aos-daemon-ctl add 的自動識別」那段加註「11-04 改看入口最終指到的 JSON 結構」；C-51 10-31 加註的「用檔名判斷」例子加一句已解。

## 步 8：條文收尾（題 2 與零碎加註）

- **N-63 加一張表「`AOS_` 變數的四種性質」**（題 2）：① 執行環境（aos-exec 每層設：`AOS_WS`／`STACK`／`CF`／`CD`／`CO`；`AOS_ENTRY` 是全樹繼承的旋鈕、使用者 11-01 裁留）② hub（值是資料夾、沒設＝`<名字>Missing`、繼承：`AOS_KERNEL`、`AOS_DAEMON`）③ 人殼預設（人在殼裡 export、程式之間不靠它傳：`AOS_AGENT`；11-04 晚裁的例外）④ 旋鈕（原則上不走環境變數——刪、改 argv、改檔；真要走帶 `AOS_`、寫在定義的 `.env`：腦三個等 kernel 收、`AOS_HEAP`／`AOS_ROSTER` 沒活主人、標瘦身候選）。每個活變數歸一格。R8 11-01 加註那句「條文原意改不改由使用者定」改成「11-04 定：見 N-63 表」。等 aos-agent 的 `AOS_DAEMON` 改名進了再寫，免得表上名字又變。
- 零碎：`identity()` 順序寫進 N-64 ③；`AOS_KERNEL_REPORT` 加註「kernel 重寫時改給腦的 `AOS_STACK`」；`MailboxMissing`→`KernelMissing`（`aos-llm-send/src/send/send.cpp:23` 一行）；aos-sandbox ENV_BASE 補 `AOS_DAEMON`、`AOS_KERNEL`；aos-mcp pop `AOS_ENTRY` 查原因後定；`env-vars.json` 標「11-01 快照、已過期」；文件殘留舊名加「已退場」註；`send_message`／`memory`（`AOS_ROSTER`／`AOS_HEAP`）列瘦身候選、問使用者封存不封存。
- 驗證：`wf-lint`（錨點、超標檔）；`grep -rn "state.txt\|_metainfo\b\|AOS_DAEMON_STACK" proto8 --include=*.md` 只剩 thinking 與加註。

## 順序一覽

07 步 0～4（現在就能做、互不依賴、可平行）→【aos-agent 落地】→ 08 步 5 → 6 → 7（7 的測試用到 6 的窗回報）→ 8。十題落點：1→5／8，2→8，3→6，4→7，5→4／6，6→6，7→2，8→5，9→1，10→3。

## 實作時代定（11-04 晚，使用者不在；可翻案）

使用者 11-04 晚：可以直接做、隨意 push，小決策頂層代定、寫進這裡。11-04 起測試全刪，上面各步的「驗證：test_xxx／ctest／加案」不再適用，改成 build 得過＋手跑幾行。

- **步 5**：舊名 `_metainfo`（不帶 `.json`）留在資料夾裡＝**當沒有**（`_metainfo` 本來就選填，`get` 不給 `metainfo`、不報錯）；舊名 `_tooldef`＝`ToolDefMissing`、訊息提示改名。08 寫的 `MetainfoMissing` 代號不加（選填的東西沒有「缺」）。`ls`／`stat` 工具的 `AOS_MARKS` 拿掉不帶副檔名的 `_metainfo`、`_tooldef`，留 `_entry`、`_entry.json`（入口本來兩種都認，N-61）。JSON 檔與單子裡的 key 仍叫 `_metainfo`（key 不是檔，不動）。
- **步 6**：三個名字只收「檔名」（非空、不含 `/`、不以 `.` 開頭），不收 `null`（這三個檔 daemon 一定要寫）、壞＝`CfgBad`；可以用指示詞（同 `procs_ctl`）。窗上回報四欄 `procs_loop`／`procs_exec`／`procs_stderr`／`procs_ctl_mailbox`（信箱沒開＝`null`），欄名＝key 名。**`procs_state.json` 本身的名字不回報**：它是找其他名字的起點，aos-daemon-ctl 只能用預設名（daemon.json 改了 `procs_state`＝aos-daemon-ctl 報 `StateMissing`）。aos-daemon-ctl／aos-agent 讀不到窗或窗上沒這幾欄（11-04 前的 daemon）＝用預設名。daemon 換了名字再開，adopt 接回的舊小格照新名字找（舊名的檔不認）——名字中途改是使用者自己承擔。aos-daemon-ctl add 補 `"interval_ms": 0` 的條件＝loop.json（去掉 `_entry`）的 key 只在 `exec`、`ws`、`stack`、`def` 之內（跟 daemon 的 `is_once` 同一套）。aos-agent 跟著改：讀小格的 loop.json、stderr 提示的檔名照窗上的 `procs_loop`／`procs_stderr`。
- **步 7**：`["aos-loop", X]` 只認 X 是第二個元素、是字串、不以 `-` 開頭（前面有旗標的 `["aos-loop", "--max", "3", "loop.json"]`＝當 exec 型：daemon 照樣 `aos-exec XXX` 跑它，只是表上沒有 pause／stop）；X 從那份 JSON 的資料夾算、可帶 `#/指標`。`$AOS_ENTRY` 照 add 當下殼裡的值（沒設＝`_entry`）。入口找不到＝當 exec 型交給 daemon（aos-exec 會報，寫在小格的 stderr），不在 add 擋。入口 JSON 讀不懂、指標指不到、繞圈＝`EntryBad`；`["aos-loop", X]` 的 X 讀不懂＝`LoopBad`。**行為變了的一處**：`_entry` 是 sh 檔（例 `lib/agent/pyfix/agent` 的 `exec aos-loop loop.json`）以前因為旁邊有 `loop.json` 算 loop 型，現在是可執行檔＝exec 型（照題 4「看最終指向的json」；要 loop 型就把 `_entry` 改成 `["aos-loop", "loop.json"]`）。C-51 的 10-31 加註裡沒有「用檔名判斷」的例子，沒加註。
- **步 8**：N-63 表放在 N-63 那份檔的尾巴（`### AOS_ 變數的四種性質（11-04）`，錨點 `aos-變數的四種性質11-04`）；`AOS_STACK` 歸 ①（它也是 hub 的實例，表上寫明）、`AOS_KERNEL_REPORT` 歸 ①（kernel 每封信設給腦）。`MailboxMissing`→`KernelMissing`：在 aos-util 的共用代號加 `KernelMissing`，aos-llm-send 兩處 `AOS_KERNEL` 的錯改用它（信箱裡少格照舊 `MailboxMissing`）。aos-sandbox 的 ENV_BASE 補 `AOS_DAEMON`、`AOS_KERNEL`。**aos-mcp 不再 pop `AOS_ENTRY`**：原因是怕外面殘留的值讓工具找錯入口，但 P-39 是一路繼承、使用者 11-01 裁留 `AOS_ENTRY`，外面設了就是要它（可翻案：改回 pop 只要一行）。`env-vars.json` 不動 JSON 本身（wf-table 契約），在它的說明檔 `01-環境變數盤點.md` 加「11-01 快照、已過期」。條文裡沒加註的 `state.txt` 補「〔11-04 起叫 `stage.txt`〕」（P-20、NORMS 01 導覽列、NORMS 07 開頭②、N-38、N-39 的 aos-eca-turn 那句、N-13 的 relay 那句）；附錄的作廢條與出處表是歷史、不加。`AOS_ROUND_*` 在條文裡的幾處都已有「已刪／拿掉」的加註，不再加。`send_message`／`memory` 封存不封存是要使用者裁的，記在 [WAIT_USER](../../../../../wf/WAIT_USER.md)、沒動。
