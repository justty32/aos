← [入口](README.md)｜涵蓋：實作步驟 5～8（跟 aos-agent 實作重疊的檔，排在它落地之後）｜上一份 [07-實作步驟](07-實作步驟.md)｜下一份 [09-邊緣狀況實測-11-04-夜](09-邊緣狀況實測-11-04-夜.md)

# 實作步驟 5～8（11-04 晚已實作，在 aos-agent 之後）

## 步 5：aos-tools——沒 stack 報錯（題 1）＋ `_metainfo.json`（題 8）

aos-tools 沒 `AOS_STACK` 報 `StackMissing`、退 1。lib 底下的 `_metainfo` 一律改名 `_metainfo.json`，aos-tools、aos-mcp、aos-sandbox、`ls`／`stat` 工具只認帶 `.json` 的；單子裡的 `_metainfo` key 不動。條文：R10／R11 加註「`_` 開頭＝aos 認的固定檔（`_entry` 是程式、不帶副檔名；`_tooldef.json`、`_metainfo.json` 是資料、帶 `.json`）」；N-63 加「`AOS_STACK` 只有 aos-exec 給預設，其他程式沒設＝`StackMissing`；替人下 aos-exec 的人殼指令算成那一跳」。

## 步 6：daemon——三個名字可設（題 6）、信箱預設名（題 5 後半）、型別寫清楚（題 3）

- daemon.json 頂層 `procs_loop`（預設 `"loop.json"`）、`procs_exec`（`"exec.json"`）、`procs_stderr`（`"stderr.txt"`），暫存檔跟著（`.<名>`）；寫進 `procs_state.json` 頂層回報，aos-daemon-ctl、aos-agent 從窗拿名字、不寫死。
- `procs_ctl_mailbox` 沒寫＝`"procs_ctl_mailbox/"`、`null`＝不開；窗上回報，aos-daemon-ctl 從窗讀。
- 型別判法（N-28 與 aos-daemon 用法文件）：字串／陣列＝exec 型（跑一次）；物件只有 `exec`（可加 `ws`、`stack`）＝exec 型；物件多任何一個 loop 的 key＝loop 型；要一直跑最少寫 `"interval_ms": 0`。
- aos-loop 自己有預設名後，daemon 不再替子項補 `ctl`／`state`；aos-daemon-ctl add 只在 loop.json 只有 `exec` 這類 key 時補 `"interval_ms": 0`。

## 步 7：aos-daemon-ctl `add` 看入口最終指到的 JSON（題 4）

使用者：「add這塊，就是看最終指向的json的內部結構。」

`add XXX` 照 aos-exec 的找法走到入口：`XXX/$AOS_ENTRY`（預設 `_entry`，沒有補 `.json`）→ 可執行檔＝exec 型；JSON 陣列且 `[0]` 是 `aos-loop`＝讀第二個元素那份 loop 設定；JSON 字串＝轉向再來（繞圈＝`EntryBad`）；物件有 `argv`＝單子＝exec 型；物件沒 `argv`、有 `exec`＝loop 設定；都沒有＝取 `js["_entry"]` 再來。拿到 loop 設定＝loop 型，走到頭不是＝exec 型。`loop.json` 這個名字不再出現在 aos-daemon-ctl 裡；`.env` 設的 `AOS_ENTRY` 不讀（只為判型）。條文 N-28 加註。

## 步 8：條文收尾（題 2 與零碎）

- N-63 尾巴加「`AOS_` 變數的四種性質」表：① 執行環境（aos-exec 每層設；`AOS_ENTRY` 是全樹繼承的旋鈕）② hub（值是資料夾、沒設＝`<名字>Missing`、繼承）③ 人殼預設（`AOS_AGENT`）④ 旋鈕（原則上不走環境變數；真要走帶 `AOS_`、寫在定義的 `.env`）。R8 那句「條文原意改不改由使用者定」改指這張表。
- 零碎：`identity()` 順序寫進 N-64 ③；aos-llm-send 的 `AOS_KERNEL` 錯改 `KernelMissing`；aos-sandbox ENV_BASE 補 hub 型；`env-vars.json` 的說明檔標「11-01 快照、已過期」；條文裡 `state.txt` 補「〔11-04 起叫 `stage.txt`〕」。

## 實作時代定（11-04 晚，使用者不在；可翻案）

使用者 11-04 晚：可以直接做、隨意 push，小決策頂層代定、寫進這裡。

- **步 5**：舊名 `_metainfo`（不帶 `.json`）＝當沒有（選填，不報錯，不加 `MetainfoMissing`）；舊名 `_tooldef`＝`ToolDefMissing`、訊息提示改名。`ls`／`stat` 的 `AOS_MARKS` 留 `_entry`、`_entry.json`，拿掉不帶副檔名的兩個。
- **步 6**：三個名字只收檔名（非空、不含 `/`、不以 `.` 開頭），不收 `null`、壞＝`CfgBad`；可以用指示詞。窗上回報四欄 `procs_loop`／`procs_exec`／`procs_stderr`／`procs_ctl_mailbox`（信箱沒開＝`null`），欄名＝key 名。`procs_state.json` 本身的名字不回報：aos-daemon-ctl 只能用預設名（改了＝`StateMissing`）。窗上沒這幾欄（11-04 前的 daemon）＝用預設名。名字中途改再開，adopt 照新名字找——使用者自己承擔。aos-daemon-ctl add 補 `"interval_ms": 0` 的條件＝loop.json（去掉 `_entry`）的 key 只在 `exec`、`ws`、`stack`、`def` 之內（跟 daemon 的 `is_once` 同一套）。aos-agent 讀小格的 loop.json、stderr 提示的檔名照窗上的名字。
- **步 7**：`["aos-loop", X]` 只認 X 是第二個元素、字串、不以 `-` 開頭（前面有旗標＝當 exec 型，表上沒有 pause／stop）；X 從那份 JSON 的資料夾算、可帶 `#/指標`。`$AOS_ENTRY` 照 add 當下殼裡的值。入口找不到＝當 exec 型交給 daemon（aos-exec 報、寫在小格 stderr）。入口 JSON 讀不懂、指標指不到、繞圈＝`EntryBad`；X 讀不懂＝`LoopBad`。`_entry` 是 sh 檔（例 `exec aos-loop loop.json`）＝exec 型；要 loop 型就把 `_entry` 改成 `["aos-loop", "loop.json"]`。
- **步 8**：N-63 表的錨點 `aos-變數的四種性質11-04`；`AOS_STACK` 歸 ①（表上寫明它也是 hub 的實例）、`AOS_KERNEL_REPORT` 歸 ①。`KernelMissing` 加在 aos-util 共用代號，信箱裡少格照舊 `MailboxMissing`。**aos-mcp 不再 pop `AOS_ENTRY`**（P-39 一路繼承、使用者 11-01 裁留 `AOS_ENTRY`；改回 pop 只要一行）。`env-vars.json` 本身不動（wf-table 契約）。附錄的作廢條與出處表不加註。`send_message`／`memory`（`AOS_ROSTER`／`AOS_HEAP`）使用者 11-04 晚裁「封存」、已封存。
