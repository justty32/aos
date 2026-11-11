# fork-and-do-task：do_task 拆成兩支——fork（整份複製自己）與 do_task（save／load 摺疊 history）（11-11）

← [2026-11-11](../README.md)｜[thinking](../../../README.md)｜前一版 [do-task-rename](../do-task-rename.md)

## 使用者原話

「啊，關於剛剛那個do_task，Hmmm，我有些想法。就是說，他有兩種實現方式，一種是fork，也就是自身的各種東西複製一份，然後等他跑好後留下結論，這其實有點像subagent的變體。另一種是save/load，也就是從在呼叫do_task那時候留下一個紀錄點，等做完task後使用self_history修改history，將進行這段task的過程中的history做總結，然後退回load那邊」

## 裁定（頂層用選項框問的；引號內是他自己寫的或選的選項文字）

| 題 | 裁定 |
|---|---|
| 兩種做法怎麼安排 | 「把fork單獨拉出來做為工具。do_task改成save/load模式。」 |
| fork 複製到什麼程度 | 「一律連對話複製」 |
| eca 體的 do_task | 「eca 不給 do_task」（eca 範本不掛這支；要派工用 fork 或 subagent） |
| 總結由誰寫 | 「do_task有兩個子指令，一個是開始，一個是結束。結束的時候要附上總結」 |
| 現在 do_task「用別的定義開一次性小幫手」的能力 | 「拿掉這個能力」（需要時自己用 subagent 組） |
| eca 體的 fork（稍後追加，使用者原話） | 「eca不給fork。」——fork 只給 fsm 體：eca 範本不掛、eca 體叫到報 `BodyUnsupported` 並指向 `subagent`；先前查到的 claude `--resume X --fork-session`、codex `codex exec fork X` 做法與已寫的 eca 程式拿掉、不留；真腦驗 fork 改成回家測（fsm 接真腦） |

同時取消：稍早 [backlog-rulings](../backlog-rulings.md) 第 3 項「帶過去」做了一版沒進 main——fork 一律整份複製，已涵蓋。

## 分份

| 份 | 內容 |
|---|---|
| [01 fork](01-fork.md) | 新工具 fork 的施工結果、代定、待裁 |
| [02 do_task](02-do_task.md) | do_task 改成 save／load 的施工結果、代定、待裁 |

## 整合（線 K 隊長）

- fork 進 subagent 包（`lib/packs/subagent.json`）；do_task 留在 gadgets 包；eca 範本 `tools.json` 寫 `"do_task": null`、`"fork": null`（do_task 施工員待裁 1 的推薦 ①）。兩範本：agent-fsm 41 支、eca-claude 39 支。
- 知識庫：`aos/agents.json` 加 fork、拿掉 do_task；do_task 的節點搬到 `aos/me/do_task.json`（它改的是自己的對話）；packs.json、agents/_index.json 跟著改；出廠庫 knowledge_check 0 錯誤。
- C-52 例外 ⑤ 的工具名單加 `fork`（11-11 再註）；NORMS 附錄 4 加 `tools/do_task/tasks.json`（持久、新檔不用重建）。
- 試驗場（`~/code/playground`）還是 13:06 那版：要重刷才有 grep／glob／todo／goal／fork 與新 do_task，劇本 `fake-demo-today` 的 do_task 那步要改（[playground README](../playground/README.md) 已加註）。

## 新持久檔分類（11-11 稍後，線 K）

使用者：「三個都進 git」——`goal.json`、`tools/todo/todo.json`、`tools/do_task/tasks.json`。（do_task 期間別人的訊息那題的裁定在 [02 末節](02-do_task.md#11-11-稍後使用者裁定do-2任務期間別人送進來的訊息)。）

- 分類表 [two-machines/gitignore_classes.json](../../10/two-machines/gitignore_classes.json) 加 G096 `stacks/**/goal.json`、G097 `stacks/**/tools/todo/todo.json`、G098 `stacks/**/tools/do_task/tasks.json`，三列都 `carry`／進。todo 登記成別的名字＝別的小格，不在這列（照「不認得的要報」，自己補一列）。
- [stack.gitignore](../../../../cmd/aos-agent/stack.gitignore) 本來就沒擋（沒改規則，只在開頭「都要留」那句加這三個）；[gitignore 指南](../../../../cmd/aos-agent/docs/05-gitignore指南.md)的表加一列帶走。NORMS 附錄 4 這三列原本就寫「進」，沒改。
- `extras/gitignore-check` 的實跑加一段讓三個檔真的長出來：worker 範本多登記 `todo`、`do_task`，假腦劇本 `tasks`（when 接法）叫 `do_task start` → `todo add` → 答一句；接著 `aos-agent goal set` 再 `goal pause`（不讓假腦被提醒一直叫）；do_task 只 start、不 end（任務開著，`tasks.json` 留著）。實跑 `ALL CHECKS PASSED`，shutdown 的 find 快照有三個檔；不加三列時這三條路徑 classify 是 None（＝unknown）。
- 連帶查的（沒改，列給隊長）：hook 狀態 `hooks/mail_notify/notified.json`、`hooks/<名>/on_clock.json` 三處一致（G092 不進、`**/hooks/`、附錄 4 不進）；fork 的分身 stack 是一般 agent stack，照既有各列；`tools/fork/observed/` 照 G033／G034 不進。**不一致**：`tools/fork/children/<分身名>/state` 分類表與附錄 4 都沒列（長出來＝unknown）；`subagents.json`（`tools/subagent/` 記帳與 stack 配額兩份）附錄 4 寫進、分類表只有改名前的 G063 `children.json`（長出來＝unknown）。
- 沒驗到：do_task `end`（與 self_history）的結果行把 `history_removed.jsonl` 的絕對路徑寫進 `history.jsonl`；分類表把 history 列為進，gitignore-check 的敏感內容檢查遇到應該會判外洩（推的，實跑只做了 start）。
