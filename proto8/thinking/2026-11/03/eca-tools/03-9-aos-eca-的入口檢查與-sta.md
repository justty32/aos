← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 9. aos-eca 的入口檢查與 `state`、10. demo、11. 不動的；實作步驟表（不實作；給隊長）｜上一份 [02-3-工作區與-stack-怎麼給-aos](02-3-工作區與-stack-怎麼給-aos.md)｜下一份 [04-要使用者看的](04-要使用者看的.md)

### 9. aos-eca 的入口檢查與 `state`

- `add`／`open` 新建：今天只看 `cli.json` 在不在（`EcaBad`）。改成跑一次 `cli_session.load_cfg`＋登記檔在不在（§ 8 的 `CfgBad`／`ToolsMissing`，代號照用），**不送信**——不然錯要等 daemon 起子 loop、aos-eca-turn 退 1、proc 下表才看得到。不叫 aos-tools ls（那是 aos-mcp 的事）。
- `state`／`status` 多印一行「工具箱 <登記檔絕對路徑>」或「工具箱 （沒有）」；`ls` 不動。

### 10. demo

- `demo/eca-claude`、`demo/eca-codex` 各附一份手寫 **`tools.json`**：`{"tools": {"clock": {"path": "../../lib/base/clock"}}}`（相對路徑從登記檔所在資料夾算、搬家不斷；登記檔裡寫 `..` 不受 P-25「格裡零個 `..`」管，那條管的是格叫工具的地址）。`cli.json` 不寫 `tools`（走預設）。
- 跑 demo 要 `extras/ai_tools/bin`（aos-mcp）與 `proto8/bin`（aos-tools）在 PATH 上；`demo/README` 外部 coding agent 範本那段、`tests/aos_bins.path_with` 補。
- 測試用的假 claude／codex（`test_fay.FAKE_CLAUDE`）不會起 MCP，只記 argv；`mcp.json` 的內容由測試讀小格驗。

### 11. 不動的

- `lib/agent/claude`、`codex` 兩個工具的 `cli.json` 不加 `tools`（它們是給 aos agent 當工具的；要接自己加）。
- `cli.json` 今天用 `json.load` 讀、不解 `$env`／`$ref`（N-45 說 aos 讀的 JSON 都解；這是既有差異，本題不改、不擴大）。
- `eca.json`（aos-eca-turn 寫的名片）不多記登記檔；要看用 `aos-eca state`。
- aos-mcp、aos-tools 零改動。

## 實作步驟表（不實作；給隊長）

驗證統一：proto8 unittest 全套（11-03 基準 635 OK／13 skip）＋ repo 根 `cmake --build --preset default && ctest --preset default` 全綠（鐵律 1）；WSL 真 codex 實測 § 5。順序 0 → 1 → 2 → 3 → 4 → 5；0 先做，結果決定 § 5 用哪條。

| 步 | 改哪些檔 | 測試 | 分開 commit？ |
|---|---|---|---|
| 0 codex 實測 | 不改檔：WSL 真 codex `codex exec -c mcp_servers.aos.command="aos-mcp" -c 'mcp_servers.aos.args=["--ws",…]' -` 叫到 clock；不過就改走 `CODEX_HOME` 退路、本檔補一行 | 手動 | 不 commit |
| 1 cli_session | `lib/agent/cli_session.py`：`load_cfg` 收 `tools`／`tools_flags`、算登記檔絕對路徑（§ 1）；新 `mcp_argv(cfg, cell, kind, ws, stack)`（寫小格 `mcp.json`／組 codex `-c`，§ 2、§ 5；`which aos-mcp`）；`print_claude`／`print_codex`／`start` 接上；`ask`、`note_cell`、`open_cell`、`call_main`、`attach_main` 多 `stack`（`stack.txt`）；檔頭說明小格多 `mcp.json`、`stack.txt`。`bin/aos-eca-turn`：`ask(..., stack)`、檔頭代號表加 `ToolsMissing` | `tests/test_fay.py`（工具形：cli.json 有 `tools` → argv 有 `--mcp-config <小格>/mcp.json --allowedTools mcp__aos`、檔內 `--ws`／`--stack` 是工具小格；codex 兩個 `-c`；沒 `tools`／沒 `tools.json`＝argv 跟今天一樣；`ToolsMissing`、`CfgBad`、`aos-mcp` 不在 PATH＝`CliMissing`；attach 開畫面 argv 有、沒 tmux skip）、`tests/test_eca_turn.py`（平級形：`--stack` 是 `$AOS_STACK`、`--ws` 是 `$AOS_WS`；`tools_flags` 原樣插在中間；預設 `tools.json` 自動接） | 可以，單獨一個 |
| 2 aos-eca | `extras/eca/bin/aos-eca`：`eca_dir` 後 `load_cfg`＋登記檔檢查（§ 9）、`cmd_open` 的 `note_cell` 多 stack、`cmd_state` 多一行；`extras/eca/README.md`：cli.json 段加 `tools`／`tools_flags`、「對它說話」例子加一句 `aos-tools --file proto8/demo/eca-claude/tools.json ls`、已知限制補 daemon PATH 要有 aos-mcp、`--logs-path` 相對路徑的坑 | `tests/test_eca_cmd.py`（add 登記檔不在＝`ToolsMissing` 不送信、表上沒有；add 好的 eca → 子 loop 跑過後小格 `claude/mcp.json` 的 `--stack` 等於 `aos-daemon-ctl where --stack` 印的；`state` 印工具箱） | 可以，單獨一個 |
| 3 demo | `demo/eca-claude/tools.json`、`demo/eca-codex/tools.json`（§ 10）；`demo/README.md` 範本段；`tests/aos_bins.py` `path_with` 加 `extras/ai_tools/bin` | `tests/test_eca.py`（範本形狀：`tools.json` 在、`aos-tools --file 它 ls` 列出 clock；射後不理那案的小格有 `mcp.json`）、`tests/test_demo.py` 若跑到 | 可以，單獨一個 |
| 4 條文與說明 | [P-43](../../../../docs/CONVENTION/02-題目stack停錯腦.md) 加「11-03 註：`cli.json` 選填 `tools`（預設同層 `tools.json`）、`tools_flags`；MCP 設定由 cli_session 寫在小格、定義不被寫（P-15）」；[ai_tools README aos-mcp 掛法](../../../../extras/ai_tools/README.md) 補「eca 不用手寫 `--mcp-config`，見 extras/eca」；[lib/README](../../../../lib/README.md) cli_session 那列；[bin/README](../../../../bin/README.md) aos-eca-turn 代號；code map [09-lib](../../../../../wf/workflows/common/code-map/proto8/09-lib.md)、[17-eca](../../../../../wf/workflows/common/code-map/proto8/06-周邊工具.md)、[06-周邊工具-3](../../../../../wf/workflows/common/code-map/proto8/06-周邊工具.md)、[13-demo](../../../../../wf/workflows/common/code-map/proto8/13-demo.md)（鐵律 3） | `/wf-lint` broken=0 | 可以；放最後、寫「已落地」 |
| 5 收尾 | 本檔補「實作時代定」；試驗場（不在 git）bob-cathy 的 `mcp.json` 不動（那是 aos agent 那條路）；eca 那隻改成不寫 `--mcp-config`、放 `tools.json`；日誌一行 | 試驗場真 claude 一題叫到工具 | 併入 4 |
