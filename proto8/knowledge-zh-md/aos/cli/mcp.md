# `knowledge/aos/cli/mcp.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/mcp.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/mcp.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/aos tools for an external agent`**

# 給外部 agent 用的 aos 工具

用 aos-mcp 透過 stdio，把 aos-tools 登記表（registry）裡的工具當作 MCP 工具提供出去（JSON-RPC：initialize、ping、tools/list、tools/call）。eca agent 會自動拿到它；只有你自己的 MCP client 才需要手動設定。

**`#/Serving a registry`**

# 提供一份登記表

```sh
aos-tools --file tools.json add $AOS_HOME/lib/tools/base/read
aos-mcp --ws /abs/ws tools.json
```

在你的 MCP client 裡把這行指令註冊成一個 stdio server；aos-tools 和 aos-exec 必須在它的 PATH 上。工作區 = `--ws` > `$AOS_WS`（沒有或不是資料夾 = `WsMissing`）；stack = `--stack` > `$AOS_STACK` > `WS/.stack/`。旗標可以放在登記表前面或後面。沒給登記表 = `./tools.json`；不是檔案 = `ToolMissing`；兩份登記表有同名的工具 = `ToolsBad`。`--own FILE` 只要那份 agent 自己的登記表存在就用它；這時只提供那一份，列出的登記表都不管。FILE 是空的 = `ArgumentsBad`。`--hooks DEF` 會執行 agent 定義夾 DEF 的 before_tool／after_tool hook（不是資料夾 = `ArgumentsBad`）。更多旗標：執行 `aos-mcp --help`。

**`#/What a call does`**

# 一次呼叫做了什麼

每一個 tools/call 會執行 `aos-tools --file REGISTRY call NAME`，參數從 stdin 給；stdout 就是結果文字。結束碼不是零 = `isError: true`，並且第二段文字帶著工具 stderr 的最後 2048 位元組：

```text
read: error: FileMissing no.txt
[aos] tool: read stderr (last 2048 bytes at most):
read: error: FileMissing no.txt
```

逾時 = 工具 `_metainfo` 裡的 `timeout_ms`，沒有就用 `--timeout-s`（預設 60；壞掉的 `timeout_ms` 當作沒寫，並印出一個警告）；兩者設 0 都 = 不限時。時間到時，整個行程群組會收到 TERM，2 秒後再收到 KILL，結果是 `CommandFailed`。結束碼不是零而 stdout 是空的，也是 `CommandFailed`，文字會這樣寫，例如 `read exited 1 with empty stdout`。工具清單每次呼叫都會重讀；當某次呼叫改了它（self_tools add），後面會跟著一個 `notifications/tools/list_changed`，所以新工具在同一個回合就能用。`--enable-logs` 每次呼叫寫一行到 `<stack>/aos-mcp-logs.jsonl`（`--logs-path FILE` 寫到別處；只給 `--logs-path` = `ArgumentsBad`）。
