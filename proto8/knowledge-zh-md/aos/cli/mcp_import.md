# `knowledge/aos/cli/mcp_import.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/mcp_import.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/mcp_import.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/External MCP tools frozen into aos`**

# 凍結進 aos 的外部 MCP 工具

用 aos-mcp-import 連一次外部 MCP 伺服器，把它的工具凍結進伺服器檔；之後定義的 tools.json 像工具包一樣疊上那個檔。兩種身體（agent-fsm、eca）的腦都把它們當一般 aos 工具呼叫。eca agent 也可以改讓它的 CLI 自己連那個伺服器（`aos/cli/eca.md#/External MCP servers (claude and codex)`）。每個伺服器挑一種方式。

**`#/Where an external tool comes from`**

# 外部工具從哪裡來

說明以 `[MCP server NAME]` 開頭的工具，就是外部工具。它的名字是 `<server>_<tool>`（小寫；其他字元變成 `_`，連續的 `_` 併成一個；最多 64 個字元，否則 `NameBad`）；經過 aos-mcp 時是 `mcp__aos__<server>_<tool>`。

- 它住在 aos-mcp-import 填好的伺服器檔裡：`mcp_tools` 每個工具一筆凍結的項目，`tools` 登記它們，定義的 tools.json 把這個檔列在 `"$override"`。
- 每次呼叫都會啟動伺服器（stdio）或開一個新的 session（http），呼叫工具一次，然後關掉。呼叫之間什麼都不留，所以需要登入或要開著瀏覽器的伺服器，用這種方式行不通。
- 說明和參數是匯入當時的版本。
- 它是一般的 aos 工具：`before_tool`／`after_tool` hook 看得到它，`self_tools {"op": "rm", "name": "time_get_current_time"}` 可以關掉其中一個。
- 輸出：文字照順序，超過 2000 行或 50KB 就截斷；圖片和音訊存在你的 stack 裡：`[image saved: $AOS_STACK/tools/<tool name>/image-xxxx.png (image/png, 12345 bytes)]`；那裡的 `$AOS_STACK` 是你自己的 stack。

**`#/Importing a server`**

# 匯入一個伺服器

先寫伺服器檔（`description` + `mcp_server`，跟 eca 讀的是同一個檔），然後：

```sh
aos-mcp-import --only get_current_time mcp/time.json
# imported 1 of 2 tools from time -> mcp/time.json
# add it to tools.json "$override": "mcp/time.json"
```

再改定義的 tools.json：`{"$override": ["<the packs it had>", "mcp/time.json"], "tools": {}}`。匯入不會改 tools.json。

- `--only A,B`／`--except C,D` 會寫進 `mcp_server.only`／`except`。兩個都沒給 = 用檔案自己的 `only`／`except`，再沒有就是全部工具（超過 20 個會警告）。旗標跟檔案不一致，或兩個旗標都給 = `ArgumentsBad`。
- 兩個工具變成同一個名字 = `NameBad`；用 `--except` 拿掉一個。
- stdio 伺服器永遠在伺服器檔所在的資料夾啟動（匯入、sync 和每次呼叫都是）：`command` 和 `args` 裡的相對路徑從那裡算。它拿到呼叫的人的完整環境，API 金鑰也包括在內。
- 伺服器名（`mcp_server.name`）要符合 `[a-z][a-z0-9_]{0,31}`，而且不能是 `aos`，否則 `PackBad`。每個凍結的工具拿到 `timeout_ms` 60000；要改就逐個工具手動改。
- `--timeout-s N`：啟動伺服器、以及工具清單每一頁的時限（預設 30）。
- 先把檔案放好，再把它列進 `"$override"`：檔案不見 = `PathMissing`，整個登記表都讀不了。還沒匯入的檔案不會加任何工具。
- 已經匯入過的檔案 = `PackExists`；用 sync。

**`#/Refreshing the frozen tools`**

# 更新凍結的工具

```sh
aos-mcp-import sync mcp/time.json        # prints the differences, writes nothing
aos-mcp-import sync --yes mcp/time.json  # writes them
```

各行：`+ NAME`（新的）、`- NAME`（不見了；它的登記項目也跟著拿掉）、`~ NAME: description changed` 或 `parameters changed`，後面接一行 `before:` 和一行 `after:`。沒有差異 = `no changes`。有差異但沒給 `--yes`，最後一行是 `run again with --yes to write`；給了 `--yes`，最後一行是 `synced N of M tools from SERVER -> FILE`。`--timeout-s` 跟匯入時一樣。只比對說明和參數。你手動改過的 `timeout_ms` 會保留。sync 用檔案的 `only`／`except`：改了它們之後，跑 `sync --yes`。從沒匯入過的檔案 = `PackBad`。匯入後改名或用別的名字複製的檔案也是 `PackBad`：它的工具仍然跑當初匯入時的那個檔，所以拿掉它的 `mcp_import`、`mcp_tools` 和 `tools` 鍵，重新匯入（同名搬到別的資料夾沒問題）。

**`#/Through aos or by the CLI itself`**

# 經過 aos，還是讓 CLI 自己來

| | 經過 aos（aos-mcp-import + tools.json） | eca CLI 自己（cli.json `mcp_servers`） |
|---|---|---|
| 說明 | 匯入時凍結；用 sync 更新 | 即時，CLI 啟動時讀 |
| hook | `before_tool`／`after_tool` 看得到呼叫 | aos 看不到 |
| 關掉一個工具 | `self_tools rm`、`aos-agent tools` | 伺服器檔裡的 `only`／`except` |
| 伺服器程序 | 每次呼叫一個新的 | CLI 跑著時一個 |
| 身體 | agent-fsm 和 eca | 只有 eca |

同一個伺服器兩種都用，腦會看到同一個工具有兩個名字（`mcp__time__x` 和 `mcp__aos__time_x`）：挑一個。經過 aos 時，http 只收 Bearer token；`bearer_token_env` 需要 `env_file`（沒有就 `PackBad`）。`env_file` 現在用跟 aos-tools env 檔一樣的 dotenv 子集：`${X}` 展開、行內 `#` 註解、引號要嚴格成對；`A=x # note` 讀成 `x`，接著 `B=${A}y` 讀成 `xy`。env 檔保持 `chmod 600`，放在定義和工作區之外。在 proxy 後面時，本機的 http 伺服器要設 `NO_PROXY=<host>`。

**`#/Codes from external MCP tools`**

# 外部 MCP 工具的代號

第一個字說是誰失敗：`mcp_tool`（一次呼叫）或 `aos-mcp-import`。

- `ServerFailed`：伺服器沒開始講話、死掉、啟動時逾時，或回了錯誤（後面接它的訊息）。重試一次。
- `ArgumentsBad`：伺服器拒絕了參數（JSON-RPC -32602）。工具已經不在時，伺服器也會這樣回：如果參數看起來沒錯，就由人去跑 `aos-mcp-import sync`。
- `ServerBad`：伺服器的回覆違反 MCP 協定。回報它；不要重試。
- `ServerRejected`：http 401 或 403：token 錯了或沒有權限。由人修 env 檔；不要重試。
- `CallFailed`：工具跑了，並說它失敗；它自己的文字在最前面。讀它，修你的參數，或回報。
- `CommandMissing`：伺服器程式啟動不了。`CommandFailed`：呼叫超過 `timeout_ms`。
- `ToolUnknown`：名字不在伺服器檔裡（`mcp_tool`），或 `--only` 指名了伺服器沒有的工具（匯入）。
- `NameBad`：伺服器名或工具名組不出合法的工具名。
- 另外：`WriteFailed`（伺服器檔寫不進去）、`FlagUnknown`（不認得的旗標）、`StackMissing`（`mcp_tool` 沒有 `$AOS_STACK`）。
- `PackExists`：檔案已經匯入過；用 sync。
- `PackBad`、`PackMissing`、`DotenvBad`、`PathMissing`：伺服器檔或它的 env 檔壞掉或不見（`PathMissing`：找不到 `env_file` 或 `ca_file`）；由人去修。

更多旗標：跑 `aos-mcp-import --help`。
