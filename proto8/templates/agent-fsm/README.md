Run an aos agent with loop and FSM cells.

用 `cp -r $AOS_HOME/templates/agent-fsm <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`），再修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

wait 格等腦回信不設期限：寄出後每滿 10 分鐘在 stderr 印一行 `agent-fsm: warning: no reply from the brain for N minutes to letter <名>: <原因>; still waiting`、照樣等（原因＝信在 kernel 的哪一格：`requests/new/` 還在排隊沒開始、`cur/` kernel 正在跑〔附那封的 `stderr.txt` 路徑〕、或 `AOS_LLM_KERNEL` 沒設／不是資料夾；kernel 沒在跑由同一拍 `aos-llm recv` 那行說，11-10 晚 two-machines B10）（提醒到第幾次記在 stack 的 `think/wait_warned.txt`）。

**通用工具四包全開**（11-10 tool-packs，使用者「1.預設開到第四包，想要安全就自行限制」）：`tools.json` 的 `"$override"` 疊上 [lib/packs](../../lib/packs/README.md) 的四份清單——1 看（read、ls、view、stat、json_read）、2 改（write、edit、copy、move、mkdir、json_write）、3 刪（trash、remove）、4 殼（shell、run_python）——再加七包 agent 工具（兩個範本都開）：小工具 gadgets（peek_clock、peek_now_time、math、thought）、事件 events（clock_register、self_hook）、自我管理 self（self_tools、self_llm、self_system、self_state、self_ctl、self_history）、子 agent subagent（subagent、agents_ctl）、定義 def（agent_def、tools_def）、信箱 mailbox（mailbox_*）、知識 knowledge（knowledge_read、knowledge_write），共 36 支（11-11 self 包加 self_system、gadgets 包加 thought）。`tools.json` 自己只剩 `knowledge_read` 那格的 `env`。這些檔案工具不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。`aos-tools --file tools.json ls -l` 的 FROM 欄看得出每支來自哪一包。**要收緊**：整包關＝從定義 `tools.json` 的 `$override` 那串拿掉那一包（例四包只留 look 就是唯讀；拿掉 subagent 就不能生子 agent），其他包不受影響；只關這一隻的某幾支＝`aos-agent tools rm shell`、`aos-agent tools rm run_python`（一次一支，寫進這隻自己那份、`"名": null`，定義不動）；`aos-agent tools reset` 回定義。

`interfaces.json` 宣告身體、工具與腦設定的位置；讀的知識庫由 `tools.json` 裡 `knowledge_read` 那格的 `env.AOS_KNOWLEDGE` 指定，寫的 `knowledge_write` 不給庫（見下段）。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。

**知識庫指 `knowledge/` 這一層**（11-10 深夜 tool-packs，使用者「指knowledge/」）：`tools.json` 的 `knowledge_read` 那格 `env.AOS_KNOWLEDGE` 是 `{"$env": "AOS_HOME", "$path": "/knowledge"}`。所以腦開場拿到的根是 `knowledge/`（它列 `aos/`、叫腦先讀 `aos/`）。原本 `knowledge_write` 那格也指這裡（agent 寫了就改到 repo 的 `knowledge/`）；**11-11 拿掉**（使用者「不給預設，要自己透過旗標指定或環境變數設定，或是工具呼叫內給。如果都沒有，那就報錯。」）：要寫，腦在呼叫裡給 `root`（相對從工作區算），或人照下面替 `knowledge_write` 配 `AOS_KNOWLEDGE`；都沒有＝`KnowledgeMissing`。工具本身沒有預設位置（沒指定＝`KnowledgeMissing`，開場安靜不帶根）。要改指自己的資料夾：
- 改定義：把那格的 `"AOS_KNOWLEDGE"` 換成 `"/home/me/kb"`、相對路徑（從 `$AOS_DAEMON` 算）或 `{"$env": "MY_KNOWLEDGE"}`；要給寫的庫，同樣補一格 `"knowledge_write": {"env": {"AOS_KNOWLEDGE": "/home/me/kb"}}`（別指出廠的 `knowledge/`）；
- 只改跑著的那隻：`aos-agent --daemon D tools --target NAME add --replace -n knowledge_read --envs AOS_KNOWLEDGE=/home/me/kb "$AOS_HOME/lib/agent/knowledge_read"`（給 `knowledge_write` 配寫的庫同樣一次）；
- 拿掉這格的 `env`、改在 daemon 或定義的 `.env` 寫 `AOS_KNOWLEDGE=…`（登記格的 `env` 蓋過 `.env`，所以要先拿掉）。

**hook 預設**（11-11 [clock-hook](../../thinking/2026-11/11/clock-hook/README.md)）：`loop.json` 的 `on_start`／`on_stop` 叫 `lib/agent/hook_fire` 發 `after_start`／`after_stop`；`hooks.json` 帶一格 `timer`（`on_clock`、每 300000 ms、handler `lib/agent/hook_noop` 什麼都不做；每次起來、睡醒會先跑一次，之後每 5 分鐘），history 不多任何一則。要定時叫醒腦＝同名換成往 `queue/` 寄信的 handler；不要＝`aos-agent hook -t 名 rm timer`。用法 [aos-agent docs/06](../../cmd/aos-agent/docs/06-hook.md)。
