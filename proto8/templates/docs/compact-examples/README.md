compact 前後 hook 的範例 handler（compact 第 5 刀，11-25）：給人抄、範本一支都不掛；restore_todo、restore_goal 壓完把待辦與目標補回對話，handoff_summary 不叫模型、拿 handoff.md 最後一節當摘要。

# compact-examples：壓縮前後的 hook 範例

← [agent-fsm 說明「壓縮前後的 hook」](../02-agent-fsm.md#壓縮前後的-hook)｜[eca-claude 說明「壓縮前後的 hook 點」](../01-eca-claude.md)

使用者 11-21：「compact這塊，反正各agent有需要的，可以自訂自己的compact程式和流程」；11-25 對 compact 第 5 刀（範例 handler）說「做」。所以這裡是**給人抄的範例**：範本（agent-fsm、eca-claude）預設一支都不掛，要用就掛到自己那隻上。預設把 todo 補回對話會碰到 11-11 T1「不帶，腦自己查」（[06-衝突 第 2 條](../../../thinking/2026-11/21/compact-改進規劃-1121/06-衝突.md)），所以不預設；各家自己的 agent 掛是那隻自己的事。

| 檔 | 掛哪一點 | 做什麼 | 哪種身體 |
|---|---|---|---|
| [restore_todo](restore_todo) | `before_compact` | 交 `restore`：壓完在摘要後面接一則「你的待辦清單」（讀 `<stack>/tools/todo/todo.json`，todo 工具自己那格；沒有清單＝不改） | agent-fsm、eca-claude |
| [restore_goal](restore_goal) | `before_compact` | 交 `restore`：goal 是 active 或 paused 時再說一次目標（讀 `<stack>/goal.json`） | agent-fsm、eca-claude |
| [handoff_summary](handoff_summary) | `before_compact` | 交 `summary`：不叫模型，`<stack>/handoff.md` 最後一節（`## ` 開頭的標題拿掉）就是摘要；沒有那份或最後一節是空的＝不改，照常叫腦 | 只有 agent-fsm（eca 的摘要是 Claude Code 自己寫的，`before_compact` 沒有 `summary` 這個鍵） |

兩支 restore 都**接在前面 hook 交的 `restore` 後面**，不整段換掉，所以可以一起掛；hook 照名字排、後一個看得到前一個改的值（agent-fsm），eca 那邊每個拿同一份事件、後蓋前，兩支一起掛時只有名字排後面的那支算數。`restore` 掛在 `before_compact` 而不是 `after_compact`，是因為 eca-claude 只在 `before_compact` 收（Claude Code 的 SessionStart 比 PostCompact 早跑）；agent-fsm 兩點都收，同一支兩邊都能用。

## 怎麼掛

抄一份到自己的地方（例：定義夾旁邊的 `hooks/`），再掛到那一隻上（寫進它 stack 裡自己那份被勾清單，定義不動）：

```sh
cp $AOS_HOME/templates/docs/compact-examples/restore_todo ~/my-hooks/
aos-agent -t ann hook add --event before_compact -n restore_todo ~/my-hooks/restore_todo
aos-agent -t ann hook ls                       # 看掛上了沒
aos-agent -t ann hook rm restore_todo          # 拿掉
```

agent 自己掛用 `self_hook`（`{"op": "add", "name": "restore_todo", "event": "before_compact", "path": "<絕對路徑>"}`；要選掛 events 包）。不抄、直接指這裡也行（`--path-json '{"$env": "AOS_HOME", "$path": "/templates/docs/compact-examples/restore_todo"}'`），但 repo 更新時這幾支會跟著變。

要每一隻都帶，就把那一格寫進定義的 `hookeds.json`（`{"restore_todo": {"event": "before_compact", "handler": "…"}}`），那是你自己的定義、不是範本。

## 自己寫一支

事件從 stdin 來，是一個 JSON 物件：共通的 `event`、`hook`、`stack`（這隻 agent 的 stack，絕對路徑），加上那一點的欄位（表在 [02-agent-fsm「壓縮前後的 hook」](../02-agent-fsm.md#壓縮前後的-hook)）。退 0、stdout 印一個物件＝改那幾個鍵；什麼都不印＝不改；`before_compact` 退 10＝攔下（stdout 是理由）。壞了（退別的、逾時、stdout 不是物件）只是一行 warning，壓縮照常做，所以範例讀不到檔就安靜地退 0。

測試：[tests/agent-fsm/test_compact_examples.py](../../tests/agent-fsm/test_compact_examples.py) 用真的 idle、brain、wait 格與假腦，跑一次 `/compact` 驗三支。
