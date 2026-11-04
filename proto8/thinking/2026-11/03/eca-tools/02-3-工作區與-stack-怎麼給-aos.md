← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 3. 工作區與 stack 怎麼給 aos-mcp、4. allowedTools 怎麼來、5. codex 怎麼接、6. 畫面那條路（open／tmux）、7. log 與 aos-mcp 的其他旗標、8. 錯誤代號｜上一份 [01-使用者原文](01-使用者原文.md)｜下一份 [03-9-aos-eca-的入口檢查與-sta](03-9-aos-eca-的入口檢查與-sta.md)

### 3. 工作區與 stack 怎麼給 aos-mcp

- **寫在 args 裡，不靠環境變數繼承**：`--ws <ws> --stack <stack>`。｜環境變數在三條路不一致：平級形 claude 的環境有 `AOS_WS`／`AOS_STACK`（daemon→loop→aos-eca-turn 一路傳下來），但 `aos-eca open` 開畫面是人的 shell 起的、沒有這兩個；`--one` 工具形的 `AOS_STACK` 又是工具小格。寫進 args 三條路一樣（寫什麼就做什麼）。
- **值從哪來**：ws＝今天 `ask`／`start` 已經拿到的 `ws`；stack＝**那隻的 stack**——平級形是 `$AOS_STACK`（daemon 表上那一列的 `stack`）、工具形是 `$AOS_STACK`（工具小格）、`open` 是表上的 `stack`。cli_session 的 `ask` 多收一個 `stack` 參數；`note_cell` 多寫一個 **`stack.txt`**（跟 `tool.txt`、`ws.txt` 同一組，`open_cell` 叫回畫面時讀），沒有 `stack.txt` 又要接工具＝`CellBad`（同 `tool.txt`／`ws.txt` 缺的處理）。
- 結果：aos-mcp 每次叫工具的小格在 `<這隻的 stack>/tools/<名>/`（P-17）、呼叫紀錄（開了的話）在 `<這隻的 stack>/aos-mcp-logs.jsonl`——跟試驗場實測一樣，而且 `aos-eca rm` 刪 stack 時一起走。工具形多疊一層（`…/tools/claude/tools/clock/`），正是 P-38「stack 樹＝呼叫樹」。

### 4. allowedTools 怎麼來

- **一律 `--allowedTools mcp__aos`**（整個伺服器放行；Claude Code 認 `mcp__<server>` 這種寫法），不展開成一個個工具名。｜cli_session 不必知道登記檔裡有哪些工具（C-52：aos-mcp 才讀登記檔）；登記檔變了不用改 argv。
- **白名單＝登記檔本身**：這隻能叫哪些工具，就是 aos-tools 登記的那幾個（aos-tools 的定義「登記這隻 agent 能叫哪些工具」）。要收窄＝換一份小一點的登記檔，不另開 key。`flags` 裡自己寫的 `--allowedTools` 照舊原樣交給 claude（claude 自己合併）。
- 畫面那條路也給（§ 6）：人接進去用 aos 工具時不再被逐個問。

### 5. codex 怎麼接

- codex 的 MCP 設定在 `config.toml` 的 `[mcp_servers.<名>]`（`command`、`args`、`env`），命令列用 **`-c` 覆寫**（`--config key=value`，值照 TOML 解；`codex exec` 與互動都收）。所以不寫檔：

  ```
  codex … -c mcp_servers.aos.command="aos-mcp" -c mcp_servers.aos.args=["--ws","<ws>","--stack","<stack>",…,"<登記檔>"]
  ```

  值用 `json.dumps` 產：JSON 字串與字串陣列同時是合法的 TOML 基本字串與陣列。
- codex 沒有 `allowedTools`；工具放不放行看它自己的 `approval_policy`（demo 已寫 `never`）。
- **11-03 實測過、通**（codex-cli 0.153.4，WSL）：`codex exec -c mcp_servers.aos.command="aos-mcp" -c 'mcp_servers.aos.args=[…json.dumps…]'` 起了 aos-mcp、叫到 clock（`--json` 有 `mcp_tool_call` 事件、`approval_policy="never"` 下不用核可），呼叫紀錄落在 `--stack` 給的資料夾；退路 `CODEX_HOME` 沒用上。
- （規劃時原文）**做得到，但要實測**（實作時第一件事，在 WSL 真 codex 上）：`-c` 收 TOML 陣列、`codex exec` 會起 MCP 伺服器。實測不過就退回寫一份 `config.toml` 到小格、用 `CODEX_HOME` 指過去——這會把 codex 的其他設定一起換掉，所以只當退路、要寫進 README。
- codex 的 `-c` 既有 `flags` 已經在用（demo/eca-codex），同一種寫法。

### 6. 畫面那條路（open／tmux）

- `start()` 拼 argv 時跟非互動同一段：claude 加 `--mcp-config <小格>/mcp.json --allowedTools mcp__aos`，codex 加兩個 `-c`。ws、stack 從小格的 `ws.txt`、`stack.txt` 來（`open_cell`）。
- `aos-eca open` 今天已經 `note_cell(cell, template, ws)`，多傳表上的 `stack`；agent-fay 的 `attach_main` 也多傳（它的 stack＝`$AOS_STACK` 或 `<ws>/.stack`，小格 `tools/<名>/`）。
- 人在畫面上叫 aos 工具＝同一個 aos-mcp、同一個 stack；呼叫紀錄（開了的話）跟非互動那次寫同一個檔。

### 7. log 與 aos-mcp 的其他旗標

- **預設不記**（11-02「默認不留」）：不自動加 `--enable-logs`。
- `cli.json` 多一個選填 **`tools_flags`**＝字串陣列，**原樣**插在 aos-mcp 的 args 裡（`--ws`／`--stack` 之後、登記檔之前）。要記呼叫紀錄就寫 `["--enable-logs"]`（落在 `<stack>/aos-mcp-logs.jsonl`），要改逾時寫 `["--timeout-s", "120"]`。｜跟 `flags`／`print_flags` 同一種「原樣交給」的形（C-54 主題放前面：`tools`、`tools_flags`）；不替 aos-mcp 的每個旗標各造一個 key（C-56）。給了 `tools_flags` 卻沒有登記檔（沒 `tools`、也沒 `tools.json`）＝`CfgBad`（寫什麼就做什麼，不靜靜吞掉）。
- `--logs-path` 相對路徑是從 aos-mcp 啟動 cwd（＝claude 的 cwd＝工作區）算的，會寫進工作區；README 提醒要給絕對路徑或不給。

### 8. 錯誤代號

cli_session 這層（照 lib 契約：工具形 stderr／stdout 各一行、aos-eca-turn 換成丟例外）：

| 情形 | 代號 |
|---|---|
| `tools` 不是字串、`tools_flags` 不是字串陣列、有 `tools_flags` 沒登記檔 | `CfgBad`（既有） |
| 登記檔不是檔（`tools` 指的、或預設 `tools.json` 消失了） | **`ToolsMissing`**（新；對應 aos-mcp 的 `ToolMissing`，這裡少的是整份登記檔） |
| `aos-mcp` 不在 PATH 上（起 CLI 前 `shutil.which`） | `CliMissing`（既有，訊息「aos-mcp 不在 PATH 上」；代號少一個） |
| 小格的 `mcp.json` 寫不了 | **`WriteFailed`**（aos-eca-turn 已有這個字） |
| 畫面叫回時小格沒 `stack.txt` | `CellBad`（既有） |

登記檔**壞掉**（aos-tools ls 讀不懂、工具缺 `_tooldef`）**不在這層查**：那是 aos-mcp 起來時的 `ToolsBad`，claude 會說 MCP 伺服器連不上、`aos-eca watch` 看得到（C-52、C-53 入口默認正常）。
