# 2026-11-03 eca 接 aos 工具：`cli.json` 指登記檔、cli_session 自己接 aos-mcp，工作區與 stack 跟著實例走

← [thinking README](../../README.md)｜月份表 [2026-11](../README.md)｜前情：[10-28 aos-tools](../../2026-10/28/aos-tools/README.md)（一份登記檔、aos-mcp 包在 aos-tools 上）、[11-02 playground-cathy](../02/playground-cathy.md)（bob 串 aos-mcp 的 `mcp.json`；aos-mcp 改給登記檔）、[11-02 stack-tools](../02/stack-tools.md)（小格 `tools/<名>/`、`--enable-logs`）、[10-30 eca](../../2026-10/30/eca/README.md)（eca＝平級 agent、`cli.json`；[10 固定名字判準](../../2026-10/30/eca/10-10-31-使用者原文-turn-的定義檔只認固.md#10-31-使用者原則固定名字可以但限縮範圍判準)）、[11-03 procs](procs.md)（每隻 eca 的 stack＝daemon 表上那一列）｜條文：[P-15、P-43](../../../docs/CONVENTION/02-題目stack停錯腦.md)、[N-50、N-55、N-59](../../../docs/NORMS/10-基礎設施-定義與工作區.md)、[C-51、C-52、C-54、C-56](../../../docs/CONCEPTS/01-設計理念.md)｜程式：[cli_session](../../../lib/agent/cli_session.py)、[aos-eca-turn](../../../bin/aos-eca-turn)、[aos-eca](../../../extras/eca/README.md)、[aos-mcp](../../../extras/ai_tools/README.md)、[aos-tools](../../../bin/README.md)

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、原則推不出答案的衝突與方向題（[user/03](../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**11-03 已實作**（方向題 1 使用者選 (a)；實作時代定見[檔末](#實作時代定11-03實作者照原則定的可翻案)）。

## 使用者原文

- 11-03，講試驗場（逐字）：「要玩playground...怎麼可以沒有aos-mcp, aos-tools接入！」
- 11-03，頂層問「eca 要用 aos 工具只能把 `--mcp-config /絕對/mcp.json --allowedTools …` 寫死進 cli.json 的 flags、mcp.json 又寫死 `--ws /絕對/ws`，同一份工具箱不能讓不同工作區的 eca 共用；要不要給 eca 一個正式的工具登記檔接法」，使用者（逐字）：「要，派人規劃」
- 本題照用的既有原文：10-27「aos-mcp 是一個小包裝，跑在 aos-tools 上」；10-28「每個agent資料夾一份」（登記檔）；10-31「固定，是可以的，但建議線限縮範圍，比如只有一個檔案固定，剩下的，則都由這個檔案指定。要再靈活一些，可以用上環境變數或argv指定」；11-02「兩邊的json格式是一樣的嗎？是同一份嗎？是的話，那就全部改回預設tools.json。」；11-02「默認不留」（aos-mcp 的呼叫紀錄）。

## 今天的樣子（查清的，不是規劃）

- eca 資料夾頂層一份 `cli.json`（`kind`、`flags`、`print_flags`、`timeout_ms`），`flags` 原樣交給 claude／codex（非互動與畫面兩條路都是，[cli_session](../../../lib/agent/cli_session.py) `print_claude`／`start`）。要接 aos 工具只能自己寫 `--mcp-config /絕對/mcp.json --allowedTools mcp__aos__clock,…` 進 `flags`，mcp.json 再寫死 `aos-mcp --ws /絕對/ws --enable-logs /絕對/tools.json`。
- 試驗場實測：flags 本來就原樣交給 claude，aos-mcp 的呼叫紀錄落在那隻 eca 自己的 stack（`procs/<名>/aos-mcp-logs.jsonl`）。
- aos-mcp：`aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] [--enable-logs [--logs-path FILE]] [REGISTRY...]`，一份都沒給＝啟動 cwd 的 `./tools.json`；工作區 `--ws` ＞ `$AOS_WS`、stack `--stack` ＞ `$AOS_STACK` ＞ `$WS/.stack/`；每次叫工具 `AOS_WS=WS AOS_STACK=<stack>/tools/<名>/ aos-tools --file REG call 名`。
- 每隻 eca 的工作區與 stack 在哪：`aos-eca-turn` 從 `$AOS_WS`／`$AOS_STACK` 拿（daemon 起子 loop 時給；stack＝daemon 表上那一列的 `stack`）；`aos-eca open` 從表上拿 `ws`、`stack`，寫進 CLI 小格的 `ws.txt`，`open_cell` 再讀回。

## 決定（11-03，使用者）

1. 要做：給 eca 一個正式的「工具登記檔」接法，由 aos-eca／aos-eca-turn／cli_session 自己接上 aos-mcp，工作區與 stack 跟著那隻 eca 實例走（「要，派人規劃」）。
2. 方向題 1 選 (a)：`cli.json` 沒寫 `tools` 就找 eca 資料夾裡預設的 `tools.json`，寫了就用指的那份（見[方向題 1](#方向題-1預設要不要自動接-eca-資料夾裡的-toolsjson)）。

## 規劃（fable，照原則定的細節，可翻案）

一句話：**eca 資料夾裡放一份 aos-tools 的登記檔（預設 `tools.json`，`cli.json` 的 `tools` 可改指），cli_session 每次起 CLI 時自己把 `aos-mcp --ws <這隻的工作區> --stack <這隻的 stack> <登記檔絕對路徑>` 包成 MCP 設定交給 claude／codex；設定檔寫在 CLI 小格裡，定義資料夾一個字都不寫。**

### 1. 登記檔放哪、怎麼指

- **登記檔＝aos-tools 的那份**（格式 `{"tools": {名: {"path": …}}}`，用 `aos-tools --file … add` 登記，或手寫相對路徑），**放在 eca 資料夾裡**，跟 `cli.json` 同一層。｜10-28「每個 agent 資料夾一份」；eca 是平級的另一隻 agent（P-43）。工具箱屬於**定義**，跟 `flags`、模型、權限一樣：同一份定義掛到幾個工作區就共用同一箱；要不同的工具箱＝複製一份 eca 資料夾改它（跟今天 README「要別的模型、權限就複製一份改 cli.json」同一句）。
- **怎麼指**：`cli.json` 多一個選填 key **`tools`**＝登記檔路徑（字串；相對路徑**從 cli.json 所在的資料夾算**，同 N-45 `$ref`、aos-tools 手寫相對路徑的規則）。**沒寫 `tools`＝看 eca 資料夾裡有沒有 `tools.json`**：有就用、沒有＝不接工具（今天的行為）。｜aos-tools、aos-mcp 的預設都是 `./tools.json`（11-02「全部改回預設tools.json」），這裡同一個名字；`tools` key 就是 aos-tools 的 `--file`（10-28 結論 1「固定名字＋`--file` 覆寫」）。這一點跟 10-31 判準有拉扯，見[方向題 1](#方向題-1預設要不要自動接-eca-資料夾裡的-toolsjson)。
- 不用 `add` 旗標、不用環境變數指：`add --tools F` 會讓同一份定義的兩個實例工具箱不同，daemon `start` 再起時又只記得 add 的設定，多一條要記的路；環境變數 aos 只訂六個（C-69／N-57），不加。
- `tools` 的值只收字串（一份登記檔）；要多份就在那份裡 `{"tools": {"$ref": ["base.json", "mine.json"]}}`（10-28 結論 2），不在 cli.json 開陣列。寫成別的型別＝`CfgBad`。

### 2. MCP 設定由誰、何時產生、放哪

- **誰**：`lib/agent/cli_session.py`——它是唯一拼 claude／codex argv 的地方（`print_claude`、`print_codex`、`start`），所以非互動、畫面、`--one` 工具形、`lib/agent/claude`／`codex` 工具四條路一次全接上（C-56 一處寫）。aos-eca-turn、aos-eca 不碰 argv。
- **何時**：每次起 CLI 之前（`print_claude`／`print_codex` 每一次、`start` 開畫面那一次）重寫一次，N-05 先寫 `.` 暫存再改名。每次重寫是因為 ws／stack 不會變、但登記檔路徵可能被改（定義改了下次起就用新的，跟 aos-mcp「每次 tools/list 重讀」同一個精神）。
- **放哪**：claude 的寫在 **CLI 小格** `<stack>/<kind>/mcp.json`（`cell.file("mcp.json")`；eca 平級形的小格是 `$AOS_STACK/claude/`，工具形就是 `$AOS_STACK` 本身）。小格在 stack 裡，**定義資料夾不被寫**（P-15）。內容：

  ```json
  {"mcpServers": {"aos": {"command": "aos-mcp",
    "args": ["--ws", "<這隻的工作區>", "--stack", "<這隻的 stack>", "<tools_flags…>", "<登記檔絕對路徑>"]}}}
  ```

  codex 不寫檔（§ 5）。
- **`command` 寫 `aos-mcp`、靠 PATH 找**，不寫死絕對路徑。｜N-50／N-59「aos 的指令由呼叫者放進 PATH、aos 的程式不動 PATH」；aos-eca-turn 已經要 aos-post 在 PATH 上、aos-mcp 自己要 aos-tools／aos-exec 在 PATH 上，同一條規矩（試驗場代定 6 也是這樣）。daemon 的 PATH 要有 `extras/ai_tools/bin`——eca README「daemon 的 PATH」那條已知限制多寫一句。
- 伺服器名字固定 `aos`（工具就叫 `mcp__aos__<登記名>`，跟試驗場、ai_tools README 的掛法一致）。

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
| 4 條文與說明 | [P-43](../../../docs/CONVENTION/02-題目stack停錯腦.md) 加「11-03 註：`cli.json` 選填 `tools`（預設同層 `tools.json`）、`tools_flags`；MCP 設定由 cli_session 寫在小格、定義不被寫（P-15）」；[ai_tools README aos-mcp 掛法](../../../extras/ai_tools/README.md) 補「eca 不用手寫 `--mcp-config`，見 extras/eca」；[lib/README](../../../lib/README.md) cli_session 那列；[bin/README](../../../bin/README.md) aos-eca-turn 代號；code map [09-lib](../../../../wf/workflows/common/code-map/proto8/09-lib.md)、[17-eca](../../../../wf/workflows/common/code-map/proto8/06-周邊工具.md)、[06-周邊工具-3](../../../../wf/workflows/common/code-map/proto8/06-周邊工具.md)、[13-demo](../../../../wf/workflows/common/code-map/proto8/13-demo.md)（鐵律 3） | `/wf-lint` broken=0 | 可以；放最後、寫「已落地」 |
| 5 收尾 | 本檔補「實作時代定」；試驗場（不在 git）bob-cathy 的 `mcp.json` 不動（那是 aos agent 那條路）；eca 那隻改成不寫 `--mcp-config`、放 `tools.json`；日誌一行 | 試驗場真 claude 一題叫到工具 | 併入 4 |

## 要使用者看的

### 衝突：沒有

對過 P-15（設定寫小格、定義不寫）、C-52（cli_session 不讀登記檔內容、aos-mcp 不知道誰叫它）、C-56（一處寫、不為每個旗標造 key）、N-50／N-59（PATH 由呼叫者放）、C-69（不加環境變數）、10-28 aos-tools 的決定 6／8（經 aos-mcp 吃、每個 agent 資料夾一份）、11-02 的三件（`tools/<名>/`、預設 `tools.json`、預設不記），都對得上。

### 方向題 1：預設要不要自動接 eca 資料夾裡的 `tools.json`

**使用者 11-03 答（逐字）**：「如果cli.json沒有指定，那就去找默認的tools.json」——**決定：選 (a)**。**結論**：`cli.json` 沒寫 `tools`＝用 eca 資料夾裡的 `tools.json`（有才接、沒有＝不接工具）；寫了 `tools`＝用指的那份。下面是當時擺的選項。


- **背景**：aos-tools 與 aos-mcp 沒給檔名時都讀 `./tools.json`（你 11-02 說格式一樣就全部改回預設 `tools.json`），aos agent 範本也是放一份 `tools.json` 就自動吃。但你 10-31 又說固定名字要限縮——「只有一個檔案固定，剩下的由這個檔案指定」；eca 那個固定的檔是 `cli.json`。
- **(a) 自動接（fable 選的，上面照這個寫）**：eca 資料夾裡有 `tools.json` 就接、`cli.json` 的 `tools` 可改指別的檔。跟 aos agent、aos-tools、aos-mcp 三處同一個習慣：放一份 `tools.json` 就有工具。代價：多一個固定名字；資料夾裡剛好躺著一份 `tools.json` 就會被接上（要不接得改名或刪掉）。
- **(b) 只認 `cli.json` 的 `tools`**：不寫就不接，資料夾裡有 `tools.json` 也不看。固定名字只有 `cli.json` 一個，完全照 10-31；代價：eca 跟其他三處不一樣，demo 的 `cli.json` 要多寫一行。
- 例子：你把 `demo/eca-claude` 複製成 `~/eca/mine/`、丟一份 `tools.json` 進去——(a) add 之後 claude 就叫得到 clock；(b) 還要在 `cli.json` 加 `"tools": "tools.json"`。

### 方向題 2：codex 那條路只實測、不另設計

- **背景**：codex 的 MCP 設定靠 `-c mcp_servers.aos.…` 命令列覆寫，不用寫檔，形狀最乾淨；但這裡沒有真 codex 可試，`-c` 收不收 TOML 陣列、`codex exec` 起不起 MCP，要到 WSL 上跑一次才知道。
- **(a) 照上面做、實測不過才退回 `CODEX_HOME`（fable 選的）**；**(b) 一開始就寫 `config.toml` 到小格、`CODEX_HOME` 指過去**（一定能跑，但會把 codex 的其他全域設定一起換掉，你的 `~/.codex` 登入、模型設定都看不到）。
- 不用你答，寫在這裡是讓你知道 codex 那半有一個實測關卡（步驟 0）。

## 實作時代定（11-03，實作者照原則定的，可翻案）

- **預設 `tools.json` 不在＝不接工具，不是錯**；`ToolsMissing` 只在 `tools` 寫了、指的不是檔時（`load_cfg` 就報），或 `load_cfg` 之後、起 CLI 之前登記檔被刪（`mcp_argv` 再查一次）。`tools` 是空字串＝`CfgBad`。
- 登記檔絕對路徑記在 `load_cfg` 回的 cfg 的 `registry`（`cli.json` 裡自己寫的同名 key 會被蓋掉，不另讀）。
- **工具形的 stack＝工具小格本身**：`call_main`（lib/agent/claude、codex、`aos-eca-turn --one`）與 agent-fay 的 `attach` 都把那格給 aos-mcp 的 `--stack`，它叫的工具在 `<那格>/tools/<名>/`（規劃 § 3「工具形是 `$AOS_STACK`（工具小格）」照這樣讀）。
- **`stack.txt` 一律寫**（不管接沒接工具，跟 `tool.txt`／`ws.txt` 一起）；`open_cell` 只在接了工具時要它，舊小格沒有 `stack.txt`、也沒接工具照常開。
- **argv 的位置**：claude 非互動接在 `flags`＋`print_flags` 之後、`--resume`／`--session-id` 之前；畫面接在 `flags` 之後、`--settings` 之前。codex 非互動接在 `flags`＋`print_flags` 之後、`--skip-git-repo-check` 之前；畫面接在 `flags` 之後、`notify` 之前。
- `mcp.json` 用小格的 `Cell.write`（N-05 先寫暫存再改名）、一行 JSON；寫不了＝`WriteFailed`（只有 claude 會碰到）。
- **`aos-eca state` 的「工具箱」那行**：cli.json 讀不懂、`tools` 指的不在時把 cli_session 的那一行寫在括號裡，`state` 照樣退 0（`add` 才擋）。`add` 的檢查錯誤行開頭是 `aos-eca:`（cli_session 的 `PROG` 本來就換成這支）。
- **測試的 PATH**：`tests/aos_bins.py` 的 `BINS` 尾端加 `extras/ai_tools/bin`（aos-mcp），所有測試的 `path_with` 都有它；`aos-mcp` 不在 PATH 的案自己把那一段拿掉。
- codex 實測時發現：WSL 的 `~/.codex/config.toml` 預設模型 `gpt-6.1-sol` 這個帳號不能用（`model_not_found`），實測加了 `-m gpt-5.6-luna`；`demo/eca-codex` 的 `cli.json` 沒寫模型、照用使用者自己的 codex 設定，沒改。
- **真 CLI 實跑過（11-03，WSL 暫存資料夾、自己起的 daemon，沒碰試驗場）**：claude（haiku）掛 daemon、`aos-eca add` → `aos-say`／`aos-listen` 叫到 clock，小格 `claude/mcp.json` 的 `--ws`＝工作區、`--stack`＝daemon 表上那一列，`aos-mcp-logs.jsonl` 與 `tools/clock/` 落在那隻的 stack，`--allowedTools mcp__aos`（整個伺服器）`-p` 下不用逐個列也放行；`state` 印工具箱；`rm` 一起刪掉。codex 經 `aos-eca-turn`（射後不理）也叫到 clock。
- 試驗場（`~/code/playground`，不在 git）這次沒改：使用者正在裡面玩。要改的是 `agents/eca_kit`——`cli.json` 的 `flags` 拿掉 `--mcp-config …/kit/mcp.json` 與 `--allowedTools …`，放一份 `tools.json`（kit 的 clock、add，絕對路徑），要紀錄就加 `"tools_flags": ["--enable-logs"]`；README「掛在 daemon 上的 eca 也能叫 aos 工具」那節改成這個寫法。WSL 的 `~/repo/simple_tools/aos` 要先 `git pull` 到本次 commit。
