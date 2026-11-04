← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 3. 工作區與 stack 怎麼給 aos-mcp、4. allowedTools 怎麼來、5. codex 怎麼接、6. 畫面那條路（open／tmux）、7. log 與 aos-mcp 的其他旗標、8. 錯誤代號｜上一份 [01-使用者原文](01-使用者原文.md)｜下一份 [03-9-aos-eca-的入口檢查與-sta](03-9-aos-eca-的入口檢查與-sta.md)

### 3. 工作區與 stack 怎麼給 aos-mcp

- **寫在 args 裡，不靠環境變數繼承**：`--ws <ws> --stack <stack>`（三條路的環境不一致，寫進 args 三條路一樣）。
- **值從哪來**：ws＝`ask`／`start` 拿到的 `ws`；stack＝**那隻的 stack**——平級形是 `$AOS_STACK`（daemon 表上那一列的 `stack`）、工具形是 `$AOS_STACK`（工具小格）、`open` 是表上的 `stack`。cli_session 的 `ask` 多收一個 `stack` 參數；`note_cell` 多寫一個 **`stack.txt`**（跟 `tool.txt`、`ws.txt` 同一組，`open_cell` 叫回畫面時讀），沒有 `stack.txt` 又要接工具＝`CellBad`。
- 結果：aos-mcp 每次叫工具的小格在 `<這隻的 stack>/tools/<名>/`（P-17）、呼叫紀錄（開了的話）在 `<這隻的 stack>/aos-mcp-logs.jsonl`，刪 stack 時一起走。工具形多疊一層（`…/tools/claude/tools/clock/`，P-38「stack 樹＝呼叫樹」）。

### 4. allowedTools 怎麼來

- **一律 `--allowedTools mcp__aos`**（整個伺服器放行），不展開成一個個工具名。
- **白名單＝登記檔本身**：要收窄＝換一份小一點的登記檔，不另開 key。`flags` 裡自己寫的 `--allowedTools` 照舊原樣交給 claude。
- 畫面那條路也給（§ 6）。

### 5. codex 怎麼接

- 命令列用 **`-c` 覆寫**，不寫檔：

  ```
  codex … -c mcp_servers.aos.command="aos-mcp" -c mcp_servers.aos.args=["--ws","<ws>","--stack","<stack>",…,"<登記檔>"]
  ```

  值用 `json.dumps` 產（JSON 字串與字串陣列同時是合法的 TOML）。
- codex 沒有 `allowedTools`；工具放不放行看它自己的 `approval_policy`。
- 11-03 在 WSL 真 codex（codex-cli 0.153.4）實測通，不用 `CODEX_HOME` 退路。

### 6. 畫面那條路（open／tmux）

- `start()` 拼 argv 時跟非互動同一段：claude 加 `--mcp-config <小格>/mcp.json --allowedTools mcp__aos`，codex 加兩個 `-c`。ws、stack 從小格的 `ws.txt`、`stack.txt` 來（`open_cell`）。
- `aos-eca open` 多傳表上的 `stack`。
- 人在畫面上叫 aos 工具＝同一個 aos-mcp、同一個 stack；呼叫紀錄跟非互動那次寫同一個檔。

### 7. log 與 aos-mcp 的其他旗標

- **預設不記**（11-02「默認不留」）：不自動加 `--enable-logs`。
- `cli.json` 多一個選填 **`tools_flags`**＝字串陣列，**原樣**插在 aos-mcp 的 args 裡（`--ws`／`--stack` 之後、登記檔之前）。要記呼叫紀錄就寫 `["--enable-logs"]`，要改逾時寫 `["--timeout-s", "120"]`。給了 `tools_flags` 卻沒有登記檔＝`CfgBad`。
- `--logs-path` 相對路徑從 aos-mcp 啟動 cwd（＝工作區）算，會寫進工作區；要給絕對路徑或不給。

### 8. 錯誤代號

| 情形 | 代號 |
|---|---|
| `tools` 不是字串、`tools_flags` 不是字串陣列、有 `tools_flags` 沒登記檔 | `CfgBad` |
| 登記檔不是檔（`tools` 指的、或預設 `tools.json` 消失了） | **`ToolsMissing`** |
| `aos-mcp` 不在 PATH 上（起 CLI 前 `shutil.which`） | `CliMissing`（訊息「aos-mcp 不在 PATH 上」） |
| 小格的 `mcp.json` 寫不了 | **`WriteFailed`** |
| 畫面叫回時小格沒 `stack.txt` | `CellBad` |

登記檔**壞掉**（aos-tools 讀不懂、工具缺 `_tooldef`）**不在這層查**：那是 aos-mcp 起來時的 `ToolsBad`。
