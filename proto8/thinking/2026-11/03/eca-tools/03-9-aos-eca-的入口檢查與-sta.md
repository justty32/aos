← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 9. aos-eca 的入口檢查與 `state`、10. demo、11. 不動的｜上一份 [02-3-工作區與-stack-怎麼給-aos](02-3-工作區與-stack-怎麼給-aos.md)｜下一份 [04-要使用者看的](04-要使用者看的.md)

### 9. aos-eca 的入口檢查與 `state`

- `add`／`open` 新建：跑一次 `cli_session.load_cfg`＋登記檔在不在（§ 8 的 `CfgBad`／`ToolsMissing`），**不送信**。不叫 aos-tools ls（那是 aos-mcp 的事）。（11-04 已改：`aos-agent add` 不驗 cli.json／tools，只讀 `interfaces.json`，見 [11-04 aos-agent 子命令](../../04/aos-agent/01-子命令.md)）
- `state`／`status` 多印一行「工具箱 <登記檔絕對路徑>」或「工具箱 （沒有）」；`ls` 不動。

### 10. demo

- `demo/eca-claude`、`demo/eca-codex` 各附一份手寫 **`tools.json`**：`{"tools": {"clock": {"path": "../../lib/base/clock"}}}`（相對路徑從登記檔所在資料夾算；登記檔裡寫 `..` 不受 P-25「格裡零個 `..`」管）。`cli.json` 不寫 `tools`（走預設）。（11-04 已改：`demo/eca-codex` 刪掉，c25fc582）
- 跑 demo 要 `extras/ai_tools/bin`（aos-mcp）與 `proto8/bin`（aos-tools）在 PATH 上。

### 11. 不動的

- `lib/agent/claude`、`codex` 兩個工具的 `cli.json` 不加 `tools`（要接自己加）。
- `cli.json` 用 `json.load` 讀、不解 `$env`／`$ref`（跟 N-45 的既有差異，本題不改）。
- `eca.json`（aos-eca-turn 寫的名片）不多記登記檔。（11-04 已改：aos-eca-turn 不再寫 `eca.json`，見 [11-04 aos-agent 步 7](../../04/aos-agent/05-實作步驟/02-步6～7.md)）
- aos-mcp、aos-tools 零改動。
