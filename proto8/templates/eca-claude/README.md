Run Claude Code as an aos agent: one turn per queue batch, answers appended to history.

用 `cp -r $AOS_HOME/templates/eca-claude <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`；要真的 `claude` 指令在 PATH 上），再修改 `cli.json`（怎麼叫 CLI）、`llm.json`（`model`）與 `tools.json`，即可建立另一隻外部 coding agent；各檔的用途、實例＝定義 × 工作區、畫面與完整用法見 [eca-claude 說明](../docs/01-eca-claude.md)。

`_entry` 起 `aos-loop`，`loop.json` 每格叫 `aos-eca-turn`：從 stack 的 `queue/` 認領一批、交給 claude CLI，回答接進 `history.jsonl`；queue 空就退 0、隔 300 毫秒再來。`screen/` 是給 `aos-agent open／close／watch` 的畫面子介面。

**不掛通用工具四包**（11-10 tool-packs，使用者「對於eca，其實那些基礎工具就不用了」）：claude 自帶讀寫檔與 bash，`tools.json` 只有範本自己那批（wall_clock、self_*、mailbox_*、clock_register、agents_*、agent_def、memory、memory_write），經 aos-mcp 給 claude。要加回某一包，在定義 `tools.json` 頂層寫 `"$override": [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}]`（四包見 [lib/packs](../../lib/packs/README.md)：look、change、delete、shell，可寫多份）；只加一支用 `aos-agent tools add $AOS_HOME/lib/base/read`。

`interfaces.json` 宣告畫面、工具、腦設定、history 與 hook 的位置；知識庫由 `tools.json` 裡 `memory` 那格的 `env.AOS_MEMORY` 指定。`_metainfo.json` 宣告估時 `cost.time_ms`（一輪約一分鐘，粗估）與 `llm` 資源，未設定逾時（一輪的上限在 `cli.json` 的 `timeout_ms` 與 `loop.json` 的 `timeout_ms`）。
