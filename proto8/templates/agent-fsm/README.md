Run an aos agent with loop and FSM cells.

用 `cp -r $AOS_HOME/templates/agent-fsm <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`），再修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

wait 格等腦回信不設期限：寄出後每滿 10 分鐘在 stderr 印一行 `agent-fsm: warning: no reply from the brain for N minutes to letter <名>: <原因>; still waiting`、照樣等（原因＝信在 kernel 的哪一格：`requests/new/` 還在排隊沒開始、`cur/` kernel 正在跑〔附那封的 `stderr.txt` 路徑〕、或 `AOS_LLM_KERNEL` 沒設／不是資料夾；kernel 沒在跑由同一拍 `aos-llm recv` 那行說，11-10 晚 two-machines B10）（提醒到第幾次記在 stack 的 `think/wait_warned.txt`）。

**通用工具四包全開**（11-10 tool-packs，使用者「1.預設開到第四包，想要安全就自行限制」）：`tools.json` 的 `"$override"` 疊上 [lib/packs](../../lib/packs/README.md) 的四份清單——1 看（read、ls、view、stat、json_read）、2 改（write、edit、copy、move、mkdir、json_write）、3 刪（trash、remove）、4 殼（shell、run_python）——再加範本自己那批（wall_clock、self_*、mailbox_*、clock_register、agents_*、agent_def、memory、memory_write）。這些檔案工具不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。`aos-tools --file tools.json ls -l` 的 FROM 欄看得出每支來自哪一包。**要收緊**：整包關＝從定義 `tools.json` 的 `$override` 那串拿掉那一包（例只留 look 就是唯讀）；只關這一隻的某幾支＝`aos-agent tools rm shell`、`aos-agent tools rm run_python`（一次一支，寫進這隻自己那份、`"名": null`，定義不動）；`aos-agent tools reset` 回定義。

`interfaces.json` 宣告身體、工具與腦設定的位置；知識庫由 `tools.json` 裡 `memory` 那格的 `env.AOS_MEMORY` 指定。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。
