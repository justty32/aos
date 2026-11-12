# 07 fsm 施工單：「fsm 經 aos 用外部 MCP」切成九步，每步半天以內、各自一個 commit、各自有驗法；做完步 2 就看得到 `aos-tools call` 叫到一支外部工具，步 8 才需要 fsm 真腦

← [external-mcp](README.md)｜[02 設計](02-設計.md#fsm-身經-aos照-11-11-的-03內容不重抄延後)｜[03 施工切法](03-施工切法.md)｜[06 施工結果](06-施工結果.md)｜原設計：[11-11 new-tools 03](../../11/new-tools/03-mcp-client.md)（M1～M8 已裁）

> 狀態：只有圖紙，沒改程式、條文、範本。11-12 傍晚公司出的，**家機照這份派工**。
> 使用者原話：「fsm來得及做嗎？」（頂層答來不及、提議把施工切法再切細一層讓他回家能直接派工）、「派」。下午另有：「外部 MCP 開工吧，做不完就push上去，我回家繼續做」。

## 結論

- 九步，共約 27 小時（三天半一個人；步 3、4、6、9 可以跟別步同時做，兩個寫手約兩天）。
- **步 1＋步 2（約 6 小時）做完**：手寫一份包檔，`aos-tools call` 就叫得到外部 stdio server 的工具。之後才疊匯入（步 4、5）、http（步 6）、sync（步 7）、fsm 真腦（步 8）、文件（步 9）。
- aos-tools、brain、act、aos-mcp、cli_session **都不動**（外部工具用的是既有的 `檔.json#/指標` 登記種類）。只有步 8 驗出 codex 底下缺環境變數時，才可能補 `cli_session.MCP_ENV`。
- 今天 eca 那半的東西直接沿用：server 檔格式與讀法（`lib/mcp_server_file.py` 的 `load`、`stdio_launch`、`read_env_file`、`bearer_value`）、假 http server（`extras/fake-mcp-http`）、「第二台 aos-mcp 當外部 stdio server」的驗法。不另起一套金鑰／CA 做法。

## 要你裁的（一題，不擋開工——推薦的 a 就是步 6 先做的）

**11-12 已裁 a（只收 Bearer）**：使用者「那就a。fable代定就先這樣，感覺都OK，以後出問題再來解決」。

**題一：經 aos 那條的 http，金鑰只收 Bearer，還是也收任意標頭**（02 寫過「開工前另出題」的那題）

- **a 只收 Bearer（推薦）**：沿用今天的 `bearer_token_env`＋`env_file`，`mcp_tool` 送 `Authorization: Bearer <值>`。server 檔格式一個字不改，同一份檔 eca、fsm 兩條路都能用。後果：要 `X-API-Key` 這類自訂標頭的 server 這條路接不了（eca 原生掛那條今天也一樣接不了）。
- **b 也收任意標頭**：server 檔加 `headers: {"X-API-Key": "${NAME}"}`，只從 env 檔展開（11-11 03 的原稿）。後果：`mcp_server_file.KEYS` 要加鍵、eca 兩身（codex `-c`、claude `headersHelper`）也要跟著翻，不然同一份檔兩條路行為不同；多約半天。

## 步驟表

| 步 | 做什麼 | 大小 | 相依 | 可同時做 | 哪裡驗 | 派誰 |
|---|---|---|---|---|---|---|
| 1 | `lib/mcp_client.py`：MCP client 的 stdio 半邊＋假 stdio server | 3h | — | — | 公司／家都可，單元測試 | gpt 寫手（照圖） |
| 2 | `lib/base/mcp_tool/`：共用 `_entry`，文字結果與基本錯誤；手寫包檔 → **`aos-tools call` 叫到外部工具** | 3h | 1 | — | 單元＋第二台 aos-mcp 實跑 | opus 隊長 |
| 3 | `mcp_tool` 補完：圖片存檔、截斷、逾時整群收、TERM 收 server | 3h | 2 | 可跟 4、5、6 | 單元測試（假 server 的怪工具） | gpt 寫手 |
| 4 | `lib/mcp_freeze.py`：把一支外部工具凍結成包裡一格的純函式（名字、`$ref` 展開、前綴、截斷、`_metainfo`） | 2.5h | — | 可跟 1、2、3 | 單元測試（純函式，不起行程） | gpt 寫手 |
| 5 | `cmd/aos-mcp-import`：連一次、把工具凍結進 server 檔 | 4h | 1、4 | 可跟 3、6 | 單元＋第二台 aos-mcp：匯入 → `aos-tools ls` → `call` | opus 隊長 |
| 6 | http transport：`mcp_client.py` 加 http 半邊（Bearer、`ca_file`） | 4h | 1 | 可跟 3、5 | 單元＋`extras/fake-mcp-http` 實跑 | gpt 寫手 |
| 7 | `aos-mcp-import sync FILE [--yes]`：重問、印差異、`--yes` 才寫 | 3h | 5 | 可跟 8 | 單元測試（假 server 換說明） | gpt 寫手 |
| 8 | 真腦驗收：fsm 真腦叫外部工具；eca 經 aos-mcp 看到 `mcp__aos__…`；hook 攔得到；金鑰不落地 | 3h | 2、5（http 要 6） | 可跟 7、9 | **家機**（要 proxy 與真腦） | opus 隊長自己跑 |
| 9 | 說明與登記：cmd README、`cmd/docs/01`、`lib/docs/02`、knowledge、`install.sh`、templates/docs 補一段 | 2h | 5 | 可跟 7、8 | wf-lint、codemap | opus 隊長 |

gpt 系只照這份圖寫碼、不參與設計；圖上沒寫到的地方先問隊長，不自己定。

## 介面定死（各步共用）

### 包檔（＝server 檔，匯入後長這樣）

```json
{"description": "MCP server time (stdio, no key).",
 "mcp_server": {"name": "time", "transport": "stdio", "command": "uvx", "args": ["mcp-server-time"]},
 "mcp_import": {"imported_at": "2026-11-13T08:00:00.000Z", "protocol_version": "2025-06-18", "server_tools": 2},
 "mcp_tools": {
   "get_current_time": {
     "_entry": ["python3", {"$env": "AOS_HOME", "$path": "/lib/base/mcp_tool/_entry"}, "--pack", "time.json", "--tool", "get_current_time"],
     "_tooldef": {"description": "[MCP server time] Get current time in a timezone.", "parameters": {"type": "object", "properties": {}}},
     "_metainfo": {"summary": "get_current_time on the MCP server time", "resource": [], "side_effect": true, "timeout_ms": 60000}}},
 "tools": {"time_get_current_time": {"path": "time.json#/mcp_tools/get_current_time"}}}
```

- `mcp_server`：今天的格式，一個字不改（`mcp_server_file.load` 照驗）。http 的就是 `transport: "http"`、`url`、`bearer_token_env`、`env_file`、`ca_file`。
- `mcp_import`（新的頂層鍵，匯入寫的）：`imported_at`、`protocol_version`、`server_tools`（server 當時總共幾支）。
- `mcp_tools`：鍵是**外部原名**；每格有 `_entry`、`_tooldef`（獨立鍵，X20／N-69）、`_metainfo`。
- `tools`：登記名 → `"<檔名>#/mcp_tools/<原名>"`（原名裡的 `~`、`/` 照 JSON 指標跳脫成 `~0`、`~1`）。`path` 與 `--pack` 都只寫**檔名**（相對於包檔自己的資料夾），整夾 `cp -r` 帶走仍通。
- `_entry` 怎麼指回 server 檔：`--pack <檔名>`，aos-exec 在包檔的資料夾跑，所以找得到自己；`mcp_tool` 用 `mcp_server_file.load(那份檔)` 讀怎麼連。
- 疊法：定義的 `tools.json` 寫 `{"$override": [<原本的包…>, "mcp/time.json"], "tools": {}}`。匯入不替人改 `tools.json`，只印要加哪一行（D6）。

### 名字規則（沿用 02／11-11）

- server 名：`[a-z][a-z0-9_]*`、最多 32 字、不准叫 `aos`（`mcp_server_file.NAME_RE`）。
- 登記名＝`<server 名>_<工具名>`：轉小寫、非 `[a-z0-9_]` 換 `_`、連續 `_` 併一個；超過 64 字或包內撞名＝`NameBad`。
- eca 經 aos 看到的是 `mcp__aos__time_get_current_time`。

### 錯誤代號

- 既有的照用：`ArgumentsBad`、`FlagUnknown`、`PackMissing`、`PackBad`、`PathMissing`、`DotenvBad`、`CommandMissing`（起不來，今天 `aos-mcp-launch` 用的就是這個）、`CommandFailed`（逾時，同 shell）、`WriteFailed`。
- 11-11 D7 已列、這次才真的出現的：`PackExists`、`ServerFailed`、`ServerBad`、`ServerRejected`（http 401／403）、`ToolUnknown`、`CallFailed`、`NameBad`。
- 句子裡不帶金鑰的值，只講變數名與檔的位置（同今天）。

## 各步細節

### 步 1：`lib/mcp_client.py`（stdio 半邊）

- **新增** `lib/mcp_client.py`、`lib/tests/test_mcp_client.py`、`lib/tests/fake_mcp_stdio.py`（標準庫假 server）。不改既有檔。
- 介面：
  - `open_stdio(argv, env, cwd, init_timeout_s=30) -> Session`：`subprocess.Popen(…, start_new_session=True)`（自成一群）；送 `initialize`（`protocolVersion: "2025-06-18"`，不宣告 sampling／elicitation／roots）、收回應、送 `notifications/initialized`。
  - `Session.protocol_version`、`Session.list_tools() -> [dict]`（照 `nextCursor` 翻頁）、`Session.call_tool(name, arguments, timeout_s) -> dict`（原樣回 `result`）、`Session.close()`（關 stdin、等 2 秒、TERM 整群、再 2 秒 KILL）。
  - `open_session(server_file) -> Session`：`mcp_server_file.load` 看 transport；stdio＝`argv, env = mcp_server_file.stdio_launch(server_file)` 再 `open_stdio(argv, env, cwd=os.environ.get("AOS_WS") or os.getcwd())`；http＝這步先丟 `PackBad`「http is not supported yet」，步 6 換掉。
  - 錯一律丟 `tool_io.Error`：起不來＝`CommandMissing`；initialize 逾時、server 中途死、回 JSON-RPC error＝`ServerFailed`（帶它的 message；`-32602`＝`ArgumentsBad`）；不是 JSON-RPC、少欄位、連續 100 行非 JSON、單一回應超過 16MB＝`ServerBad`；呼叫逾時＝`CommandFailed`。
  - server 反過來問（`sampling/createMessage` 等）＝回 `-32601`；`notifications/*` 忽略；initialize 前的非 JSON 行跳過。server 的 stderr 直接繼承（透到工具的 stderr）。
- 協定寫法可參考 `cmd/aos-mcp/bin/aos-mcp` 的 `handle`（反方向同一套訊息）。
- 假 server `fake_mcp_stdio.py`：工具 `echo`、`fail`（`isError`）、`image`（回一張小 png）、`sleep`、`big`（回 200KB）、`refschema`（schema 有 `$ref`／`$defs`）、`show_env`（回指定變數在不在，不回值）；用環境變數切怪行為：`FAKE_MODE=init_fail｜die｜garbage｜ask_sampling｜two_pages｜changed_desc`。
- 驗：單元測試——握手、兩頁 `tools/list`、`call echo`、每個 `FAKE_MODE`、`close()` 後行程群不在。不用真腦、不用網路。

### 步 2：`lib/base/mcp_tool/`（最小版）→ 看得到 `aos-tools call`

- **新增** `lib/base/mcp_tool/_entry`（python，可執行）、`_metainfo.json`（含 `tooldef`，只給 `--help`；不登記給腦）、`tests/test_mcp_tool.py`、`tests/fixtures/demo.json`（手寫包檔，形狀照上面）。
- usage：`mcp_tool --pack FILE --tool NAME`，arguments 從 stdin 原樣讀（一個 JSON 物件，空＝`{}`；不用 `tool_io.arguments()` 驗）。
- 流程：`mcp_server_file.load(FILE)`（錯＝原代號）→ 檔裡 `mcp_tools` 沒有 NAME＝`ToolUnknown` → `mcp_client.open_session(FILE)` → `call_tool(NAME, arguments, timeout_s)` → 印結果 → `close()`。`timeout_s` 取那格 `_metainfo.timeout_ms`（沒有＝60 秒）。
- 這步的輸出：`content` 裡 `type: "text"` 的依序接起來印；`isError: true`＝內容照印、最後一行 `mcp_tool: error: CallFailed the server reported an error`、退 1。其他 content 種類先印一行 `[<type> content not shown]`（步 3 補）。
- 先驗兩件事（寫進測試）：(1) aos-tools 讀包檔對 `mcp_server`／`mcp_import`／`mcp_tools` 三個頂層鍵放行（讀碼看 `read_layer` 只擋 `add`／`rm`，應該過）；(2) `tools` 裡相對的 `demo.json#/mcp_tools/x` 從包檔資料夾算、`_entry` 的 cwd 是包檔資料夾。任一不成立＝停下來回報，不自己改 aos-tools。
- 驗：
  - 單元：`aos-tools --file <疊了 fixtures/demo.json 的 tools.json> ls --json` 看得到 `demo_echo`；`aos-tools call demo_echo` 拿到回聲；`fail` 退 1 帶 `CallFailed`；`--tool nope`＝`ToolUnknown`。
  - 實跑：把第二台 aos-mcp 寫成 stdio server 檔（照 [06](06-施工結果.md) 步 4 的 `demo`、`test_cli_external_mcp` 裡的寫法），手寫一格 `peek_now_time`，`aos-tools call demo_peek_now_time` 拿到時間。不用真腦。

### 步 3：`mcp_tool` 補完

- **修改** `lib/base/mcp_tool/_entry`、`tests/test_mcp_tool.py`。
- `image`／`audio`：存進自己的小格（`tool_io` 現有的小格位置函式，寫才建），印 `[image saved: <路徑> (image/png, 12345 bytes)]`；`resource_link` 印 URI；嵌入 `resource` 有 text 就印；只有 `structuredContent`＝印成一行 JSON。
- 輸出超過 2000 行或 50KB＝從頭留、尾巴一行說截了多少（同 read）。
- 逾時＝整群收、`CommandFailed`；自己收到 TERM＝先 `close()` 那一群再走（規則 5）。
- 驗：假 server 的 `image`、`big`、`sleep`、`FAKE_MODE=die`；測完 `pgrep -f fake_mcp_stdio` 沒東西；`show_env` 驗 env 檔的變數進了 server、且值不在 stdout／stderr。

### 步 4：`lib/mcp_freeze.py`（純函式）

- **新增** `lib/mcp_freeze.py`、`lib/tests/test_mcp_freeze.py`。不起行程、不讀檔。
- `registry_name(server, tool) -> str`（上面的名字規則；不合＝`Error("NameBad")`）。
- `clean_schema(schema, warn) -> dict`：本地 `$ref`（`#/…`）就地展開（深度 10、遇環停），拿掉 `$defs`／`$schema`／`$id` 等所有 `$` 開頭的鍵；展不開的那段換 `{}` 並 `warn`；頂層不是 object＝包成 `{"type": "object", "properties": {}}` 並 `warn`；參數的 `description` 截 300 字。**結果裡不留任何 `$` 鍵**（`$` 是 aos 指示詞）。
- `freeze_tool(server_name, pack_basename, tool, transport) -> (登記名, mcp_tools 那一格)`：`_tooldef.description`＝`"[MCP server <名>] "`＋原文、總長截 1024；`parameters`＝`clean_schema(inputSchema)`；`_metainfo`＝`summary`、`side_effect`（`readOnlyHint` 反過來，沒寫＝true）、`idempotent`（`idempotentHint`）、`resource`（`openWorldHint` 或 http＝`["net"]`）、`timeout_ms: 60000`；`_entry` 照上面形狀。
- `diff_tools(old_mcp_tools, new_mcp_tools) -> [行]`（步 7 用：`+ 名`、`- 名`、`~ 名: description／parameters changed` 加前後各一行）。
- 驗：單元測試，例子直接用 `fake_mcp_stdio.py` 的工具表（複製成常數，兩步才不互等）。

### 步 5：`cmd/aos-mcp-import`

- **新增** `cmd/aos-mcp-import/bin/aos-mcp-import`、`README.md`、`tests/test_import.py`；**修改** `install.sh`（加捷徑，一行）。
- usage：`aos-mcp-import [--only A,B | --except C,D] [--timeout-s N] SERVER_FILE`
- SERVER_FILE 是人先寫好的 server 檔（只有 `description`＋`mcp_server`，跟 eca 那條同一份）。流程：`load` → 檔裡已有 `mcp_tools`＝`PackExists`（訊息教用 `sync`）→ `open_session` → `list_tools` → 照 `only`／`except` 挑 → 每支 `freeze_tool` → 原子寫回同一份檔（加 `mcp_import`、`mcp_tools`、`tools`；`description` 與 `mcp_server` 其他鍵不動）→ `close()`。
- `--only`／`--except` 給了＝寫進 `mcp_server.only`／`except`（檔裡已有且不同＝`ArgumentsBad`，請人先改檔）；兩個都沒有＝全收，超過 20 支印 warning。`only` 裡有 server 沒有的名字＝`ToolUnknown`。
- stdout 兩行：`imported N of M tools from <名> -> <檔>`、`add it to tools.json "$override": "<檔>"`。
- 錯：`ArgumentsBad`、`FlagUnknown`、`PackMissing`、`PackBad`、`PathMissing`、`DotenvBad`、`PackExists`、`CommandMissing`、`ServerFailed`、`ServerBad`、`ToolUnknown`、`NameBad`、`WriteFailed`。任何錯＝檔不動。
- 驗：
  - 單元（假 stdio server）：全收、`--only`、`--except`、撞名、`PackExists`、失敗時檔的位元組沒變、匯入後 `mcp_server_file.load` 仍讀得過（eca 那條照樣能用同一份檔）。
  - 實跑：第二台 aos-mcp 的 server 檔 → `aos-mcp-import` → `aos-tools ls` 看到 `demo_*` → `aos-tools call demo_peek_now_time`。不用真腦。

### 步 6：http transport

- **修改** `lib/mcp_client.py`（加 `open_http`、`open_session` 的 http 分支）、`lib/tests/test_mcp_client.py`。`mcp_tool`、`aos-mcp-import` 不用改（都走 `open_session`）。
- `open_http(url, bearer=None, ca_file=None, init_timeout_s=30) -> Session`（同一組方法）：純標準庫 `urllib`；每個請求 `POST url`，標頭 `Content-Type: application/json`、`Accept: application/json, text/event-stream`、有 bearer 加 `Authorization: Bearer <值>`；`initialize` 回的 `Mcp-Session-Id` 之後每個請求都帶；回應是 JSON 就直接解，是 SSE 就讀到對應 `id` 的那一則；`close()` 送 `DELETE`（失敗不管）。`ca_file`＝`ssl.create_default_context(cafile=…)`。
- `open_session` 的 http 分支：`bearer = mcp_server_file.bearer_value(server)`（今天的函式：從 `env_file` 只拿那一個變數）；寫了 `bearer_token_env` 卻沒寫 `env_file`＝`PackBad`（見代定 F4）。值只放進請求標頭，不進環境、不進任何輸出。
- 錯：401／403＝`ServerRejected`；連不上、TLS 失敗、其他 4xx／5xx＝`ServerFailed`（帶狀態碼或原因，不帶標頭）。
- 驗：
  - 單元：測試裡起 `extras/fake-mcp-http/server.py`（憑證與假 token 當場產，照它 README）：握手、`list_tools`、`call echo`；token 錯＝`ServerRejected`；不給 `ca_file`＝`ServerFailed`；server 的 log 有 `auth ok`。
  - 實跑：寫一份 http server 檔 → `aos-mcp-import` → `aos-tools call teamsite_echo`、`teamsite_list_threads`；假 token `grep -rlaF` 掃包檔、stack、所有 cmdline＝0（同 06 的掃法）。不用真腦。
- 家機有 proxy：`urllib` 會讀 `http_proxy`／`https_proxy`；假 server 在 127.0.0.1，測試裡自己設 `NO_PROXY=127.0.0.1`。

### 步 7：`aos-mcp-import sync`

- **修改** `cmd/aos-mcp-import/bin/aos-mcp-import`、`tests/test_import.py`、README。
- usage：`aos-mcp-import sync [--yes] [--timeout-s N] SERVER_FILE`
- 檔裡沒有 `mcp_tools`＝`PackBad`（教先跑匯入）。重連、照檔裡的 `only`／`except` 重新凍結、`mcp_freeze.diff_tools` 印差異；沒差＝印 `no changes`、退 0、不寫；有差沒 `--yes`＝印差異＋`run again with --yes to write`、退 0、不寫；有 `--yes`＝原子寫回（更新 `mcp_import`）。人手改過的 `timeout_ms` 保留（其他欄位照 server 的）。
- 驗：假 server `FAKE_MODE=changed_desc`——不加 `--yes` 檔不變且差異有印；加了才變；server 少一支＝`- 名`、`tools` 跟著拿掉。

### 步 8：真腦驗收（家機）

- 不新增程式；結果寫成 `08-fsm施工結果.md`（照 06 的寫法）。
- 驗：
  1. fsm 真腦（範本 fsm 定義，`tools.json` 疊上第二台 aos-mcp 匯入的包）：叫它「現在幾點」，live 看到它叫了 `demo_peek_now_time` 並拿到結果。
  2. http 那份（假 http server）同樣一輪，server log `auth ok`。
  3. eca 經 aos：claude 身、codex 身各一輪，看到 `mcp__aos__demo_peek_now_time` 並叫得到；**codex 底下**確認 `mcp_tool` 起得了 server（`PATH`、`HOME`、`AOS_HOME`；缺＝補 `cli_session.MCP_ENV`，這是唯一可能動既有程式的地方，另一個 commit）。
  4. `before_tool` hook 攔得到這支外部工具；`self_tools rm` 能關掉單一支。
  5. 金鑰不落地：假 token 掃定義、stack、`live.jsonl`、所有 cmdline＝0。
  6. （要你點頭才做）真的別人寫的 `uvx mcp-server-time`：要下載。
- 步 1～7 都不用真腦：直接 `aos-tools call` 或假腦（`llm_fake`）就能驗。

### 步 9：說明與登記

- **修改** `cmd/README.md`、`cmd/docs/01`、`lib/docs/02` 索引、knowledge（外部工具怎麼來的、錯誤代號怎麼讀、`cli/` 加 `mcp_import` 節點）、templates/docs/01「接外部 MCP server」補「經 aos」一段（寫明兩條路差別：凍結、hook 攔得到 vs. CLI 自己接）、`cmd/aos-eca` README 一句。codemap、wf-lint。

## 跟 11-11 原設計對不上的地方（都解得開，編成代定；每條可翻案）

**F1～F12：11-12 使用者：先這樣，出問題再解決**（「那就a。fable代定就先這樣，感覺都OK，以後出問題再來解決」；頂層另轉述給他的 F4、F9 也在這句裡）。

- **F1 匯入的對象是「人先寫好的 server 檔」**，不是 `NAME -- COMMAND`。11-11 的 usage 是 `aos-mcp-import NAME -- COMMAND…`（匯入當場生一份檔）；今天 server 檔已經是手寫的、eca 也讀同一份（X2），所以匯入只收 `SERVER_FILE`。`NAME -- COMMAND` 那個「順手生檔」的寫法不做（要的話之後加一支小子命令）。
- **F2 匯入時間等資訊放新的頂層鍵 `mcp_import`**，不放 `mcp_server` 裡。11-11 把 `imported_at`、`protocol_version` 寫在 `mcp_server` 底下；今天的 `mcp_server_file.load` 對 `mcp_server` 裡不認的鍵一律 `PackBad`（eca 那條就會把這台跳過）。放頂層＝`load` 不看、不用改今天的程式。
- **F3 `mcp_tool` 不自己組怎麼起 server**：stdio 用今天的 `mcp_server_file.stdio_launch`（回 argv 與環境，`env`＜`env_file` 整份進 server 環境——跟 `aos-mcp-launch` 同一個函式，只是這裡要留著管線所以自己 `Popen`、不 exec）。
- **F4 經 aos 的 http：寫了 `bearer_token_env` 就一定要寫 `env_file`**，沒寫＝`PackBad`。今天 E2 讓 codex「沒寫 `env_file` 就用行程本來繼承的變數」；但 M3 你裁的是「env 檔，只記位置」，而且工具的環境是 aos-exec 給的、金鑰不該放在 agent 環境（X12）。所以這條路不學 E2。同一份檔在 eca 能用、在 fsm 被擋，訊息會講清楚要補 `env_file`。
- **F5 起不來的代號用 `CommandMissing`**（今天 `aos-mcp-launch` 已經這樣用），不用 11-11／X19 寫的 `LaunchFailed`——同一件事不要兩個名字。
- **F6 env 檔的讀法用今天的 `mcp_server_file.read_env_file`**（E3：`KEY=VALUE`、`export`、`#`、成對引號），不是 11-11 寫的 `aos-tools --env-file` 那個解析器（那個會做 `${VAR}` 展開）。兩條路讀同一份檔要同一個讀法。
- **F7 `description` 匯入時不改寫**。11-11 的包檔 `description` 是匯入產生的句子（`5 of 26 tools…`）；現在那句是人寫的，數字改放 `mcp_import.server_tools`。
- **F8 `only`／`except` 以檔裡的為準**（X9 的延伸）：匯入與 sync 都讀檔；人之後改了檔裡的 `only`，要跑 `sync --yes` 才生效（凍結的那批不會自己變）。`mcp_tool` 只認 `mcp_tools` 裡有的。
- **F9 M7「可選。默認用凍結的。」這次只做默認那半**（凍結＋sync）。「每台可選每次重問」要 aos-tools 在列工具時去問 server，等於動 aos-tools 核心與快取，不在這九步裡；要做另出小圖。
- **F10 M5「不限制，有權限就能用。」**：`aos-mcp-import` 是一支普通指令，有 shell 的腦自己就能跑、再用 `self_tools` 疊上；這次不另做給腦用的 `mcp_import` 工具。
- **F11 http 只做 Streamable HTTP、金鑰只做 Bearer**（題一的 a；你選 b 就加半天）。舊的 HTTP+SSE 雙端點不做（同 11-11）。
- **F12 server 的 cwd＝`$AOS_WS`**（沒有就用當下的 cwd）：照 11-11 邊緣 11；eca 原生掛那條 CLI 也是在工作區起 server，兩條路一致。

## 邊緣狀況（有答案的）

1. **包檔不在，卻疊在 `$override`**：aos-tools 現況是 `PathMissing`、整份登記讀不了（`read_bases`），不是略過。不改它；文件寫「先放好 server 檔再疊」。檔在但不是 JSON＝`RegistryBad`，同樣整份停。
2. **包檔在、某一格壞了**（`_tooldef` 被手改壞）：aos-tools 今天的「一條登記壞了只略過那支、印 warning」（tool-path-broken、P-41）直接適用。
3. **server 檔還沒匯入就疊上去**：沒有 `tools` 鍵＝那一層是空的，不報錯、沒有工具；不特別處理。
4. **工具原名有 `/`、`~`、`.`、大寫**：`mcp_tools` 的鍵與 `--tool` 用原名；指標跳脫 `~0`／`~1`；登記名照規則轉。兩支轉完同名＝`NameBad`（用 `except` 排掉一支）。
5. **同一份檔 eca 原生掛與經 aos 同時用**：可以；腦會同時看到 `mcp__time__x` 與 `mcp__aos__time_x`，是寫定義的人的選擇（M8「每台伺服器自己選」），文件寫一句「一台選一條」。
6. **平行叫同一支**：各起一台（stdio）／各開一個 session（http），互不干擾。
7. **有狀態的 server**（瀏覽器、登入）：這條路不能用（每次都是新的），文件寫明走 eca 原生掛，或等常駐 proc。
8. **server 那邊工具不見了**：凍結的照舊列；叫到＝`ServerFailed`，訊息尾巴加 `(run aos-mcp-import sync)`。
9. **冷啟動慢**（`uvx` 第一次下載）：initialize 逾時 30 秒、每支 `timeout_ms` 60 秒可手改；匯入那次順便暖好。
10. **沙箱裡**：`mcp_tool` 需要讀 `lib/mcp_client.py`、`lib/mcp_server_file.py`、`lib/tool_io.py`、包檔、env 檔、`ca_file`；網路與 server 執行檔照沙箱設定。不另做。
11. **匯入寫到一半被砍**：原子寫（暫存檔＋rename），檔不會半份。
12. **`env_file` 權限太鬆**：不檢查（今天 eca 那條也不查），文件建議 `chmod 600`。
13. **http server 回 SSE 且夾著通知**：只認 `id` 對得上的那一則，其他丟掉。
14. **家機 proxy 擋到區網 http server**：`urllib` 照環境走 proxy；不通先設 `NO_PROXY=<主機>`（同 06 的家機注意）。

## 家機開工前

- `git pull`、重跑 `proto8/install.sh`（步 5 之後多一支 `aos-mcp-import`）。
- 步 1、4 可以先同時派出去；步 2 等步 1；之後照表。
- 每步做完：該步的測試＋`lib`、`cmd/aos-tools`、`cmd/aos-mcp` 既有測試照過，才 commit。

## 不在這次範圍（另開設計）

常駐 proc（M4 後半「專門的常駐aos proc…將request丟給他」）、M7 的「每次重問」那半、給腦用的 `mcp_import` 工具、任意標頭（題一 b）、舊式 HTTP+SSE。
