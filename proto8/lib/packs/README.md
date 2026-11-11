# packs — 工具分包，每包一份工具清單

使用者 11-10 深夜：「最基礎的就是read/ls/view/stat要有。然後是普通的編輯如write/edit/copy/move/mkdir，再來是trash/remove，最後是shell。就是說，這是一包一包的」；「1.預設開到第四包，想要安全就自行限制」。agent 工具的分法：「clock_register,self_hook兩個分一組，self_tools/llm/state/ctl/history一組。agents一組。mailbox_*一組，memory_*一組。peek_clock一組。」「agent_def另外放」「2.都開吧」；「這種peek_clock,peek_now_time放一起，就是小工具的感覺。」（math 也收進來：「好」）。

## 通用四包（兩個範本都預設開；eca-claude 11-10 深夜「1.算了，把各種東西也一起掛回eca。」掛回）

| 包 | 檔 | 工具 |
|---|---|---|
| 1 看 | [look.json](look.json) | read、ls、view、stat、json_read、grep（照內容搜，像 `grep -rn`）、glob（照檔名樣式找檔）——11-11 使用者「啊，grep/glob得做」 |
| 2 改 | [change.json](change.json) | write、edit、copy、move、mkdir、json_write |
| 3 刪 | [delete.json](delete.json) | trash（丟進工作區 `.trash/`，可搬回）、remove（真的刪） |
| 4 殼 | [shell.json](shell.json) | shell（bash 一行指令）、run_python |

## 其他八包（兩個範本都預設開）

| 包 | 檔 | 工具 |
|---|---|---|
| 小工具 | [gadgets.json](gadgets.json) | peek_clock（daemon 時鐘第幾 cycle）、peek_now_time（UTC 時間）、math（算一個式子）——不改任何東西、隨手看一下；do_task（派一件小事給用完即走的子 agent、只拿回短結論；11-11 使用者「放進某一包」→「小工具那包」） |
| 事件 | [events.json](events.json) | clock_register（時鐘定期寄信）、self_hook（自己身上發生事時叫的勾子） |
| 自我管理 | [self.json](self.json) | self_tools、self_llm、self_system、self_state、self_ctl、self_history |
| 子 agent | [subagent.json](subagent.json) | subagent（自己生的）、agents_ctl（daemon 上任何一隻） |
| 定義 | [def.json](def.json) | agent_def、tools_def（從 Python 骨架做新工具、檢查工具；11-10 深夜使用者「3.對」） |
| 信箱 | [mailbox.json](mailbox.json) | mailbox_peek、mailbox_read、mailbox_send |
| 記憶 | [knowledge.json](knowledge.json) | knowledge_read、knowledge_write——只寫路徑；用哪個庫由疊這包的那份 `tools.json` 在同名格補 `env`（`AOS_KNOWLEDGE`）。範本只替 knowledge_read 補（出廠庫）；knowledge_write 11-11 起不給庫（使用者「不給預設，要自己透過旗標指定或環境變數設定，或是工具呼叫內給。如果都沒有，那就報錯。」），腦在呼叫裡給 `root` 或人另配 |
| 目標 | [goal.json](goal.json) | goal（一支分動作 get、set、done、pause、resume；自己停下來〔答話不叫工具〕又沒信時，身體丟一則 `[aos] goal: …` 提醒，連續十次沒進展就暫停；11-11 使用者「todo/goal也一起做吧」、裁「一支 goal 分動作」，[goal 02](../../thinking/2026-11/11/goal/02-裁定與施工結果.md)） |

## 怎麼用、怎麼關

每份就是一般的工具清單（`{"tools": {名: {"path": …}}}`，路徑寫 `{"$env": "AOS_HOME", "$path": "/lib/…"}`，整夾 `cp -r` 出去仍通）。範本的 `tools.json` 用 `"$override": [包, 包, …]` 疊起來，自己只剩必要的 `env` 格（現在只有 knowledge_read 那格）。

- **關掉一包**：從範本（或 agent 自己覆蓋層）的 `$override` 串拿掉那一項；其他包不受影響。
- **關掉一支**：`aos-agent tools rm 名`（在覆蓋層寫 `"名": null`）。
- **看某支從哪包來**：`aos-agent tools ls -l` 的 FROM 欄＝寫那個 `path` 的檔，就是 `lib/packs/包.json`。

工具本身不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。
