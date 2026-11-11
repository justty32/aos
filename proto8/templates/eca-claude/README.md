Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.

用 `cp -r $AOS_HOME/templates/eca-claude <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`；要真的 `claude` 指令在 PATH 上），再修改 `cli.json`（怎麼叫 CLI）、`llm.json`（`model`）與 `tools.json`，即可建立另一隻外部 coding agent；各檔的用途、實例＝定義 × 工作區、畫面與完整用法見 [eca-claude 說明](../docs/01-eca-claude.md)。

`_entry` 起 `aos-loop`，`loop.json` 每格叫 `aos-eca-turn`：從 stack 的 `queue/` 認領一批、交給 claude CLI，回答接進 `history.jsonl`；queue 空就退 0、隔 300 毫秒再來。`screen/` 是給 `aos-agent open／close／watch` 的畫面子介面。

**十一包全開，跟 agent-fsm 一樣**（11-10 深夜使用者「1.算了，把各種東西也一起掛回eca。」，翻掉稍早的「對於eca，其實那些基礎工具就不用了」——tools_def 驗收時 haiku 沒有改檔工具、做不出新工具）：`tools.json` 的 `"$override"` 疊通用四包 look、change、delete、shell，再加七包 agent 工具（[lib/packs](../../lib/packs/README.md)：gadgets〔peek_clock、peek_now_time、math〕、events、self、children、def、mailbox、knowledge），共 35 支（11-11 self 包加 self_system），自己只剩記憶兩格的 `env`，經 aos-mcp 給 claude（工具名 `mcp__aos__read`…）。關一包＝從那串拿掉那一項；只關一支用 `aos-agent tools rm shell`。

`interfaces.json` 宣告畫面、工具、腦設定、history 與 hook 的位置；知識庫由 `tools.json` 裡 `knowledge_read`、`knowledge_write` 兩格的 `env.AOS_KNOWLEDGE` 指定（見下段）。`_metainfo.json` 宣告估時 `cost.time_ms`（一輪約一分鐘，粗估）與 `llm` 資源，未設定逾時（一輪的上限在 `cli.json` 的 `timeout_ms` 與 `loop.json` 的 `timeout_ms`）。

**知識庫指 `knowledge/` 這一層**（11-10 深夜 tool-packs，使用者「指knowledge/」）：`tools.json` 的 `knowledge_read`、`knowledge_write` 兩格 `env.AOS_KNOWLEDGE` 都是 `{"$env": "AOS_HOME", "$path": "/knowledge"}`。所以腦開場拿到的根是 `knowledge/`（它列 `aos/`、叫腦先讀 `aos/`），**agent 用 `knowledge_write` 寫了就改到 repo 裡的 `knowledge/`**——這是使用者指定的預設。工具本身沒有預設位置（沒指定＝`KnowledgeMissing`，開場安靜不帶根）。要改指自己的資料夾：
- 改定義：把兩格的 `"AOS_KNOWLEDGE"` 換成 `"/home/me/kb"`、相對路徑（從 `$AOS_DAEMON` 算）或 `{"$env": "MY_KNOWLEDGE"}`；
- 只改跑著的那隻：`aos-agent --daemon D tools --target NAME add --replace -n knowledge_read --envs AOS_KNOWLEDGE=/home/me/kb "$AOS_HOME/lib/agent/knowledge_read"`（`knowledge_write` 同樣一次）；
- 拿掉這格的 `env`、改在 daemon 或定義的 `.env` 寫 `AOS_KNOWLEDGE=…`（登記格的 `env` 蓋過 `.env`，所以要先拿掉）。
