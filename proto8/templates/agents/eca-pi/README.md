Run the pi coding agent as an aos agent: one pi --mode rpc run per queue batch (letters that come meanwhile are steered in), answers appended to history; aos-agent open shows pi's own screen.

用 `cp -r $AOS_HOME/templates/agents/eca-pi <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`，抄到哪都能跑，這台要有 `AOS_HOME`），再掛進樹：`aos-agent -d .stack ctl add --auto-restart -w <工作區> <目的資料夾>`。完整用法、實測紀錄與限制見 [eca-pi 說明](../../docs/03-eca-pi.md)；跟 claude 那份的共同部分（實例＝定義 × 工作區、hook、goal、slash 的大原則）見 [eca-claude 說明](../../docs/01-eca-claude.md)。

**這份範本跟 `eca-claude` 差在哪**（使用者 11-18：「1.做成第三種。2.甲。3.先全開。」「6.開」，傍晚「pi coding agent要做畫面」「接著做乙丙吧」）：

- `cli.json` 是 `{"kind": "pi", "flags": [], "timeout_ms": 0}`：aos 每批信起一次 `pi --mode rpc --no-approve --session-dir $AOS_STACK/pi/pi-sessions --session-id <id>`，題目送一則 `prompt`；同一個 id 下一輪接著講。**回答途中又來的信**一封一則 `steer` 送進去（pi 在下一次叫模型之前讀到），回答是每段接起來；不要就在 `cli.json` 寫 `"live_mail": false`（上限 `live_mail_cap` 同 claude）。`--mode`、`--session*`、`--approve`／`--no-approve` 這些是 aos 自己加的，`flags` 裡寫了＝`CfgBad`。
- **畫面**：`screen/` 跟 eca-claude 同一份，`aos-agent open` 在 tmux 裡起互動的 `pi`（同一個對話資料夾、同一個 id，`--tui-mode regular`），多帶一支 aos 的 pi 外掛：每講完一輪通知 aos（`turns.jsonl`）、畫面開著時 aos 的信經它送進對話。`Ctrl-]` 跳出、畫面留著；`aos-agent close` 關。`hookeds.json` 帶 `screen_linger_start`／`screen_linger_stop`（停下後 `screen_close_after_s` 秒關畫面，預設 600，同 eca-claude）。
- **要 `pi` 與 `node` 都在 PATH 上**：pi 的啟動檔是 `#!/usr/bin/env node`。用 nvm 裝 node 的機器，非互動殼常常找不到 node（退 127）；在樹的 `env.sh` 加一行 `export PATH="$HOME/.nvm/versions/node/<版本>/bin:$HOME/.local/bin:$PATH"`，見說明的「要先有的東西」。開畫面的那個殼也要有這兩個。用的是使用者自己裝的那份 pi（11-18 使用者「算了，不要釘版吧，太麻煩了」）。
- **模型**：`llm.json` 是 `{}`＝pi 自己的預設（`pi` 裡 `/login` 登 ChatGPT 訂閱時選的；使用者 11-18「我是打算拿它來代替codex」）。要指定就寫 `{"model": "供應商/id"}`（`pi --list-models` 列得出來）；思考程度寫 `reasoning_effort`（補成 `--thinking`，`off`～`max`）。改走 litellm proxy 之類的 OpenAI 相容端點，寫法在說明裡。
- 沒有 `compact_hook`（那是 Claude Code 的 hook）。
- **工具**：`tools.json` 跟 eca-claude 同一份（五包、18 支；11-22 跟 eca-claude 一起拿掉 events、def、jsonx 三包，要用時 `self_tools add` 加回）。pi 沒有「這次用這份 MCP 設定」的旗標，aos 每輪在小格寫一支一行的外掛 `pi-aos-mcp.mjs`（只呼叫 `pi.registerMcpServer("aos", …)`），用 `-e` 帶進去（使用者 11-18「每輪生一行外掛，目前就先這樣」）；工具名 `mcp__aos__peek_now_time`…。檔案與指令交給 pi 自己的 read、bash、edit、write。
- **權限全開**（使用者「3.先全開」）：pi 從不問、沒有沙盒，bash 與寫檔用你這個帳號的權限照做。aos 只加 `--no-approve`（工作區 `.pi/` 裡的設定、MCP 檔、外掛一律不載）。aos 的 `before_tool` hook 只看得到 aos 的工具。
- **`hookeds.json`**（被勾清單）帶 `screen_linger_start`、`screen_linger_stop`、`timer`、`mail_notify` 四格。沒放 `context_wrap`：pi 的事件沒有 context 視窗大小，要用就把 eca-claude 那格抄過來、`config` 加 `"window": <模型的視窗 token 數>`（預設要不要放，使用者還沒裁）。`brain_notify` 只認 claude 的失敗代號，也沒放。
- **slash**：`/compact [指示]` 另起一次 `pi --mode rpc` 壓縮同一段對話、history 換成摘要（畫面開著＝打進畫面）；`/clear` 開新對話（畫面開著＝打 pi 的 `/new`）；`/goal`、`/usage` 回一句不支援。

`_entry` 起 `aos-loop`，`loop.json` 每格叫 `aos-eca-turn`（同 eca-claude）。`interfaces.json` 宣告畫面、工具、腦設定、history、hook 與 system 的位置。`_metainfo.json` 宣告估時 `cost.time_ms`（一輪約一分鐘，粗估）與 `llm` 資源；一輪的上限在 `cli.json` 與 `loop.json` 的 `timeout_ms`，兩個都是 0＝不限時。
