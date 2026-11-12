# packs — 工具分包，每包一份工具清單

使用者 11-10：「最基礎的就是read/ls/view/stat要有。然後是普通的編輯如write/edit/copy/move/mkdir，再來是trash/remove，最後是shell。就是說，這是一包一包的」；「1.預設開到第四包，想要安全就自行限制」。agent 工具的分法：「clock_register,self_hook兩個分一組，self_tools/llm/state/ctl/history一組。agents一組。mailbox_*一組，memory_*一組。peek_clock一組。」「agent_def另外放」「2.都開吧」；「這種peek_clock,peek_now_time放一起，就是小工具的感覺。」（math 也收進來：「好」）。

## 通用四包（agent-fsm 預設開；eca-claude 四包都不掛——使用者 11-11「然後eca通常都有自己的基礎工具如read/write/ls，那對它們更順手，也不用給」、11-12「可以先定這樣，然後trash也拿掉。」，[thinking 11-12 eca-file-tools](../../thinking/2026-11/12/eca-file-tools.md)）

| 包 | 檔 | 工具 |
|---|---|---|
| 1 看 | [look.json](look.json) | read、ls、view、stat、grep（照內容搜，像 `grep -rn`）、glob（照檔名樣式找檔）——11-11 使用者「啊，grep/glob得做」 |
| 2 改 | [change.json](change.json) | write、edit、copy、move、mkdir |
| 3 刪 | [delete.json](delete.json) | trash（丟進工作區 `.trash/`，可搬回）、remove（真的刪） |
| 4 殼 | [shell.json](shell.json) | shell（bash 一行指令）、run_python |

## json 兩包（使用者 11-12「建議做成一個aos_json工具……做兩套」、兩套選「A」，[thinking 11-12 json-tools](../../thinking/2026-11/12/json-tools/README.md)）

| 包 | 檔 | 工具 |
|---|---|---|
| json（簡單組） | [json.json](json.json) | json_get、json_ls、json_search、json_len、json_set、json_add、json_del，一次多格的 json_multi_get、json_multi_set——路徑一整串 `檔#/指標`、值照字面、`$ref`／`$env` 當普通物件；agent-fsm、eca-claude 兩個範本都掛 |
| jsonx（複雜組） | [jsonx.json](jsonx.json) | jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del，一次多格的 jsonx_multi_get、jsonx_multi_set——多 `follow`、`resolve`、`text`、`from`、`check`；**範本都不掛**，要的定義在自己 `tools.json` 的 `$override` 多一行 |

十七支的程式都在 [`lib/aos_json.py`](../aos_json.py)（multi 四支在 [`lib/aos_json_multi.py`](../aos_json_multi.py)），各夾只是殼；圖紙 [01-規劃](../../thinking/2026-11/12/json-tools/01-規劃.md)。

## index 包（使用者 11-12「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」，[thinking 11-12 index-tools](../../thinking/2026-11/12/index-tools/README.md)）

| 包 | 檔 | 工具 |
|---|---|---|
| index | [index.json](index.json) | index_view（透過 index 看節點：`path` 看天然那份、`index` 看指定的那份、兩個都給＝疊著看、同名鍵以指定那份為準；只看不改，改 index 用 json 包）——agent-fsm、eca-claude 兩個範本都掛，reviewer 不掛 |

程式在 [`lib/aos_index.py`](../aos_index.py)，「index 放哪」只寫在它的 `spot()`。天然那份有兩處（[metainfo](../../thinking/2026-11/12/metainfo/README.md)，使用者「index_view也要認_metainfo。」）：`_metainfo` 裡的 `index` 為底、疊上獨立的 `_index.json`／`_index`，同名項整項以獨立那份為準；只有獨立那份時就只看那份（[N-69](../../docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md)）。

## 其他八包（兩個範本都預設開）

| 包 | 檔 | 工具 |
|---|---|---|
| 小工具 | [gadgets.json](gadgets.json) | peek_clock（daemon 時鐘第幾 cycle）、peek_now_time（UTC 時間）、math（算一個式子）——不改任何東西、隨手看一下；do_task（在自己的 history 做一段任務、結束時換成總結；使用者 11-11「放進某一包」→「小工具那包」、「eca 不給 do_task」＝eca 範本 `tools.json` 寫 `"do_task": null`，[fork-and-do-task](../../thinking/2026-11/11/fork-and-do-task/README.md)） |
| 事件 | [events.json](events.json) | clock_register（時鐘定期寄信）、self_hook（自己身上發生事時叫的勾子） |
| 待辦 | [todo.json](todo.json) | todo（eca 不掛：使用者 11-11「todo也不用」；自己的待辦清單：ls、set、add、mark；存自己的小格 `tools/todo/todo.json`，不自動帶進 prompt、腦自己 ls；使用者「todo/goal也一起做吧」、T1「不帶，腦自己查」，[new-tools 04](../../thinking/2026-11/11/new-tools/04-施工結果.md)） |
| 自我管理 | [self.json](self.json) | self_tools、self_llm、self_system、self_state、self_ctl、self_history |
| 子 agent | [subagent.json](subagent.json) | subagent（自己生的）、agents_ctl（daemon 上任何一隻）、fork（把當下的自己連對話複製一份給一個 goal、只拿回短結論；使用者 11-11「把fork單獨拉出來做為工具」「eca不給fork。」「subagent相關的工具都還是別給eca吧」＝eca 範本整包不掛） |
| 定義 | [def.json](def.json) | agent_def、tools_def（從 Python 骨架做新工具、檢查工具；使用者 11-10「3.對」） |
| 信箱 | [mailbox.json](mailbox.json) | mailbox_peek、mailbox_read、mailbox_send |
| 目標 | [goal.json](goal.json) | goal（eca 不掛：使用者 11-11「eca基本都有goal，所以goal不用給eca」；一支分動作 get、set、done、pause、resume；自己停下來〔答話不叫工具〕又沒信時，身體丟一則 `[aos] goal: …` 提醒，連續十次沒進展就暫停；使用者「todo/goal也一起做吧」、裁「一支 goal 分動作」，[goal 02](../../thinking/2026-11/11/goal/02-裁定與施工結果.md)） |

## 怎麼用、怎麼關

每份就是一般的工具清單（`{"tools": {名: {"path": …}}}`，路徑寫 `{"$env": "AOS_HOME", "$path": "/lib/…"}`，整夾 `cp -r` 出去仍通）。範本的 `tools.json` 用 `"$override": [包, 包, …]` 疊起來，自己只剩必要的格（例 eca 範本的 `"do_task": null`）。

- **關掉一包**：從範本（或 agent 自己覆蓋層）的 `$override` 串拿掉那一項；其他包不受影響。
- **關掉一支**：`aos-agent tools rm 名`（在覆蓋層寫 `"名": null`）。
- **看某支從哪包來**：`aos-agent tools ls -l` 的 FROM 欄＝寫那個 `path` 的檔，就是 `lib/packs/包.json`。

工具本身不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。
