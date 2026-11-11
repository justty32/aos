# 03 MCP client：讓 aos agent 用別人的 MCP 伺服器（設計稿，未施工）

← [new-tools](README.md)｜上一份：[02 todo](02-todo.md)

## 一句話結論

推薦**「一台伺服器＝一個包檔、每支外部工具＝一支 aos 工具」**：人用一支新指令 `aos-mcp-import` 連一次外部伺服器、把它的工具清單**凍結**寫成一份包檔（`mcp/github.json`，跟 `lib/packs/*.json` 同形狀，伺服器怎麼起也寫在同一份裡），agent 的 `tools.json` 在 `$override` 疊上它就有了。每支外部工具的 `_entry` 是同一支轉接程式 `mcp_tool`：**每次呼叫起一次伺服器**（stdio）→ initialize → tools/call → 收掉。這樣 aos-tools、brain、act、aos-mcp、self_tools、hook 一個字都不用改，**eca 經 aos-mcp 自動也拿得到**（claude／codex → aos-mcp → aos-tools → 外部伺服器）。第一步只做 stdio、只有人能匯入；HTTP、`sync` 比對差異、常駐伺服器排在後面。

## 現況

- 只有反方向：`cmd/aos-mcp` 把 aos-tools 登記的工具當 MCP 伺服器給 eca（claude／codex）用。aos 這邊沒有 MCP client。
- 工具登記只有三種（資料夾、JSON 檔或 `檔.json#/指標`、可執行檔），**一格＝一支**。`aos-tools ls --json` 是 brain（每格）、aos-mcp（每次 tools/list 與每次 call 後）共同的工具來源。
- 兩範本 35 支、tooldef 約 12.5k tokens——外部伺服器一掛幾十支（GitHub 官方伺服器 20 幾支以上），**工具表的 token 是最直接的「配額」**（aos 沒有「最多幾支工具」的配額；`max_children` 管的是子 agent）。

## 參考市面

| 市面 | 做法 | 取 | 不取、為什麼 |
|---|---|---|---|
| Claude Code | `.mcp.json`／`--mcp-config` 的 `{"mcpServers": {名: {command, args, env} 或 {type: "http", url, headers}}}`；工具名 `mcp__伺服器__工具`；session 期間伺服器常駐；`env`／`headers` 支援 `${VAR}` 展開；權限用 `--allowedTools` 逐支或整台 | 設定的形狀（使用者可以從現成設定抄）；「整台伺服器一個前綴」的命名 | 常駐（aos 的工具是函數、行程歸 daemon 管，第一步不做）；`${VAR}` 從環境展開（使用者怕濫用環境變數，金鑰改走 env 檔，待裁 M3） |
| Codex | `~/.codex/config.toml` 的 `[mcp_servers.名]`、`command`／`args`／`env`；核准模式可整台設；不帶父行程環境（這次 11-11 才踩到） | 「整台一個核准開關」的想法 | 全域設定檔（aos 一律跟著 agent 定義或明給的檔走） |
| OpenHands | 設定檔裡列 stdio／SSE 伺服器，工具展開進 agent 的工具表 | 展開成一般工具 | — |
| 一般 MCP client SDK | 長連線 session、`tools/list_changed` 通知即時更新 | 協定本身（initialize／tools/list／tools/call、isError、content 種類） | 即時更新清單：外部伺服器可以偷換工具說明（「rug pull」），凍結＋人看過差異再更新比較安全 |

## 工具怎麼出現在工具表（三條路）

| | 甲 匯入成包（推薦） | 乙 通用兩支 | 丙 aos-tools 新種類「伺服器」 |
|---|---|---|---|
| 長相 | 每支外部工具＝`github_create_issue` 這樣一支 aos 工具 | `mcp_ls {server}` 列、`mcp_call {server, tool, arguments}` 叫 | 登記格寫 `{"mcp": {…}}`，aos-tools ls 當場問伺服器、展開成多支 |
| 改 aos-tools／brain／aos-mcp | 不改（用既有的 `檔.json#/指標` 種類） | 不改 | 改 aos-tools 核心（1159 行）、`ls -l`、`rm`、快取 |
| tooldef 快取 | 用不到（JSON 種類每次讀檔，不跑 `--tooldef`） | 用不到 | 一定要快取（不然每格問腦前都要起一次伺服器）＝新快取格式 |
| self_tools | `ls` 看得到每支、`rm` 可逐支關；整台關＝從 `$override` 拿掉那個包 | 只看到兩支；關某支外部工具做不到 | 逐支 rm 要先展開再疊，語意要重想 |
| 工具小格 | 每支一格，只有真的寫（存圖片）才建 | 全擠 `tools/mcp_call/` | 每支一格 |
| token | 匯入幾支就多幾支（要能挑，待裁 M6） | 固定兩支（最省） | 同甲，但伺服器加工具會自己變多 |
| 腦好不好用 | 跟原生工具一樣；參數有 schema | 先 ls 再 call，arguments 沒 schema 檢查；小模型常配錯；摘要後要重 ls | 同甲 |
| 說明被偷換 | 凍結，`sync` 才更新 | 每次 ls 都是伺服器當下說的 | 跟著伺服器變 |

### 甲的包檔長相（`aos-mcp-import` 寫出來的）

```json
{"description": "Pack mcp github: 5 of 26 tools of the MCP server github, imported 2026-11-11T08:00:00.000Z by aos-mcp-import.",
 "mcp_server": {"name": "github", "transport": "stdio",
                "command": "uvx", "args": ["some-github-mcp-server"],
                "env_file": "/home/me/.config/aos/github.env",
                "imported_at": "2026-11-11T08:00:00.000Z", "protocol_version": "2025-06-18"},
 "mcp_tools": {
   "create_issue": {
     "_entry": ["python3", {"$env": "AOS_HOME", "$path": "/lib/base/mcp_tool/_entry"}, "--pack", "github.json", "--tool", "create_issue"],
     "_tooldef": {"description": "[MCP server github] Create a new issue in a repository.", "parameters": {"type": "object", "properties": {…}}},
     "_metainfo": {"summary": "create_issue on the MCP server github", "resource": ["net"], "side_effect": true, "timeout_ms": 60000}}},
 "tools": {"github_create_issue": {"path": "github.json#/mcp_tools/create_issue"}}}
```

- 頂層 `tools` 讓它本身就是一個包，`$override` 疊得上；`mcp_server`、`mcp_tools` 是 aos-tools 不認的鍵（要驗 aos-tools 照放過，現在只擋 `add`／`rm`）。
- `_entry` 在 cwd＝包檔資料夾跑，`--pack github.json` 就找得到自己；整夾 `cp -r` 帶走仍通（同 packs 的 `$env AOS_HOME` 寫法）。
- **設定＝包檔本身**：伺服器怎麼起只寫在這裡一份，不另讀別的設定、不靠環境變數找。

## 伺服器行程的生命週期

| | 每次呼叫起一個（推薦第一步） | 常駐 |
|---|---|---|
| 怎麼跑 | `mcp_tool` 起伺服器（自成一群）→ initialize → notifications/initialized → tools/call → 關 stdin、等 2 秒、TERM 整群、再 KILL | daemon 管一個 proc 抱著 stdio，工具寄信給它轉 |
| 誰關 | 叫它的那支 `mcp_tool` 自己（規則 5：被 TERM 先收那一群） | daemon（照它管 proc 的方式），agent 停了誰收要另定 |
| 好處 | 純函數、沒有孤兒、不碰 pid；跟現在所有工具一樣 | 快、伺服器的狀態留著（瀏覽器分頁、登入） |
| 壞處 | 每次多付伺服器啟動時間（uvx 冷啟動可到數秒；第一次還要下載）；**有狀態的伺服器不能用**（開瀏覽器、下一次叫就是新的） | 要新的 proc 種類、信件協議、健康檢查，工作量大一個量級 |
| HTTP 伺服器 | 每次 POST initialize 拿 `Mcp-Session-Id`、call、DELETE；同樣無狀態 | 可以留 session id |

stdio 與 HTTP：第一步只做 stdio（本機起的伺服器最多、純標準庫好寫好測）；HTTP（Streamable HTTP：POST JSON-RPC、回應可能是 JSON 或 SSE）第二步做，純標準庫 `urllib` 做得到，約多 150 行。舊的 HTTP+SSE 雙端點傳輸不做。

## 安全面

1. **外部 description 是不可信文字**：會原樣進模型的 tools 陣列（提示注入的入口）。做三件事：開頭一律加 `[MCP server 名] `、長度截到 1024 字元（參數說明各 300）、**匯入時凍結**——伺服器之後偷改說明，aos 這邊看不到，直到人跑 `sync`、看了差異才換（待裁 M7）。外部 schema 裡的 `$ref`／`$defs`：aos 的 JSON 讀法會把 `$ref` 當指示詞去解（`aos-tools` 的 `has_directive`），**匯入時一律就地展開本地 `$ref`、拿掉 `$defs`／`$schema`／`$id`**，展不開的那一段換成 `{}` 並印 warning——包檔裡不留任何 JSON Schema 的 `$` 鍵（`$` 是 aos 的寫法，不讓外部格式混進來）。
2. **工具結果也是不可信文字**：照現在的工具一樣交給腦，不另處理（跟 shell 的輸出同等級）；只限長度（同 read：2000 行或 50KB，從頭留）。
3. **金鑰**：不寫進包檔、不寫進 stack、不印。推薦 `env_file` 只記位置（同 `aos-tools --env-file`、`llm_http --key-env` 的精神：值留在使用者自己的檔），每次呼叫才讀、合進伺服器的環境；HTTP 的 `headers` 可以寫 `${NAME}`，只從那份 env 檔展開（待裁 M3）。
4. **誰能加伺服器**：加伺服器＝讓某個指令在這台機器上跑，等於 `shell`。第一步只有人能匯入（`aos-mcp-import` 是人的指令、寫的是定義資料夾或人指定的地方）；腦要自己加是第二步的題（待裁 M5）。
5. **要不要逐次核准**：不另做核准機制。人匯入那一步就是核准；要逐次問人，用既有的 `before_tool` hook（可攔、可改 arguments），不在 `mcp_tool` 裡另寫一套。`_metainfo.side_effect` 照 annotations 的 `readOnlyHint` 反過來填（沒寫＝當有副作用），給 hook 與人參考。
6. **沙箱**：包在 aos-sandbox 裡跑時，`mcp_tool` 要的 `mcp_client.py`、`tool_io.py` 綁唯讀，伺服器的執行檔與網路照沙箱設定；不另做。

## eca 那邊

- **走 aos 轉接（推薦，第一步就有）**：外部工具已經是 aos 工具，eca 的 aos-mcp 照樣列給 claude／codex，名字是 `mcp__aos__github_create_issue`；hook、self_tools、記帳都一致，什麼都不用改。代價：多兩層行程、每次冷起伺服器。
- **原生掛（之後可加）**：cli_session 把包檔裡的 `mcp_server` 直接寫進 claude 的 `mcp.json`／codex 的 `-c mcp_servers.名`——CLI 自己常駐那台伺服器，有狀態的伺服器（瀏覽器）只有這條能用；但繞過 aos 的 hook、self_tools、核准設定要另外對（claude `--allowedTools mcp__github`、codex 核准模式），fsm 與 eca 行為分岔。列成待裁 M8。

## 介面草稿

### `aos-mcp-import`（人的指令，`cmd/aos-mcp-import/bin/`）

```
aos-mcp-import [--out FILE] [--only A,B] [--except C] [--env-file FILE] [--timeout-s N] NAME -- COMMAND [ARGS...]
aos-mcp-import [--out FILE] … NAME --url URL [--header K:V]...          （第二步）
aos-mcp-import sync FILE [--yes]                                        （第二步：重問伺服器、印差異、--yes 才寫）
```

- 連一次、列工具、寫包檔（預設 `./mcp/NAME.json`；檔已在＝`PackExists`，要換用 `sync`）；印 `imported N of M tools from NAME -> FILE`，最後一行教怎麼疊：`add it to tools.json "$override": "mcp/NAME.json"`（不替人改 tools.json，代定 D6）。
- 錯：`ArgumentsBad`、`FlagUnknown`、`PackExists`、`ServerFailed`、`ServerBad`、`ToolUnknown`（`--only` 裡有伺服器沒有的）、`NameBad`（轉出來的工具名撞名或不合）、`WriteFailed`。

### `mcp_tool`（每支外部工具共用的 `_entry`，`lib/base/mcp_tool/`）

- argv `--pack FILE --tool NAME`，arguments 從 stdin **原樣**轉給伺服器（不用 `tool_io.arguments()` 驗：外部 schema 可能有 tool_io 不懂的寫法，驗交給伺服器）。
- 結果：`content` 裡的 text 依序接起來；`image`／`audio` 存進自己的小格（`$AOS_STACK/` 底下，寫才建）、印 `[image saved: <路徑> (image/png, 12345 bytes)]`；`resource_link` 印 URI；嵌入的 `resource` 有 text 就印；只有 `structuredContent` 沒 text＝印成一行 JSON。超過 2000 行或 50KB 從頭留、尾巴說截了多少。
- `isError: true`＝把內容照印，最後一行 `<名>: error: CallFailed the server reported an error`、退 1（act／aos-mcp 本來就把 stdout 交給腦）。
- 伺服器的 stderr 原樣透到工具 stderr（R10）；act 失敗時附最後 2KB。
- 伺服器反過來問的（`sampling/createMessage`、`elicitation/create`、`roots/list`）：不宣告這些能力，真的來了回 JSON-RPC `-32601`；`notifications/*`（progress、log）忽略。
- 錯誤代號：`PackMissing`／`PackBad`（包檔不在、壞了）、`ToolUnknown`（包裡沒有這支）、`LaunchFailed`（指令起不來，例 `uvx` 不在 PATH）、`ServerFailed`（initialize 失敗、伺服器中途死掉、回 JSON-RPC 錯誤；原因帶伺服器的 message）、`ServerBad`（回的不是 JSON-RPC、少欄位）、`ServerRejected`（HTTP 401／403，第二步）、`ArgumentsBad`（伺服器回 `-32602` 參數不對，原因帶它的 message）、`CallFailed`（`isError`）、`CommandFailed`（逾時，整群收掉；同 shell）、`DotenvBad`（env 檔壞了）。

### `lib/mcp_client.py`（共用模組）

協定本身：JSON-RPC 2.0、換行分隔的 stdio、initialize 送 `protocolVersion: "2025-06-18"`、收伺服器回的版本（認得 `2024-11-05`／`2025-03-26`／`2025-06-18`，不認得＝warning 照試）、`tools/list` 翻頁（`nextCursor`）、`tools/call`、整群收行程。`aos-mcp-import` 與 `mcp_tool` 都用它；放 `lib/` 最上層（同 `tool_io.py`），`cmd` 依賴 `lib` 合規矩。

### 名字轉換

外部名 `create-issue`、`createIssue`、`fs.read` → `github_create_issue`、`github_createissue`…：伺服器名＋`_`＋工具名，轉小寫、非 `[a-z0-9_]` 換 `_`、連續 `_` 併一個、超過 64 字元＝`NameBad`（OpenAI 函數名上限）；撞名＝`NameBad`，用 `--only`／`--except` 或換伺服器名。包內 `mcp_tools` 的鍵留**外部原名**（`_entry` 的 `--tool` 也是原名），只有登記名轉。

## 分階段

| 階段 | 內容 | 能做到 | 粗估 |
|---|---|---|---|
| **1 最小可用** | `lib/mcp_client.py`（stdio）、`lib/base/mcp_tool/`、`cmd/aos-mcp-import`（只 stdio、`--only`／`--except`、`--env-file`）、`$ref` 展開、text／image 結果、假伺服器測試、知識節點、cmd README | fsm 與 eca 都能用無狀態的本機伺服器（`mcp-server-time`、`mcp-server-fetch`、檔案類） | **2～3 天** |
| 2 | HTTP 傳輸、`sync`（差異＋`--yes`）、`headers` 從 env 檔展開、（看 M5）腦用的 `mcp_import` 工具 | 遠端伺服器、更新外部工具 | 1.5～2 天 |
| 3 | 常駐（daemon proc 抱 stdio）或 eca 原生掛（M8 乙） | 有狀態的伺服器（瀏覽器、資料庫連線） | 3 天以上，另開設計 |

## 實作路線（階段 1）

- **新增**：`lib/mcp_client.py`、`lib/base/mcp_tool/`（`_entry`、`_tooldef.json`〔給 `--help`；不登記給腦〕、`_metainfo.json`、`tests/`）、`cmd/aos-mcp-import/`（`bin/`、`README.md`、`tests/`）、知識節點（外部工具怎麼來的、錯誤代號怎麼讀）。
- **要動的既有檔**：`install.sh`（捷徑）、`cmd/README.md` 與 `cmd/docs/01`、`lib/docs/02` 索引、`knowledge`、codemap；**不動** aos-tools、aos-mcp、brain、act、cli_session、packs（MCP 包是使用者自己的，不進 `lib/packs`）。施工前先驗一件事：aos-tools 讀包檔時對 `mcp_server`／`mcp_tools` 兩個不認得的頂層鍵是否放行（不放行就改成兩份檔：`github.json` 放伺服器與工具、`github.pack.json` 放 `tools`）。
- **依賴**：只有 Python 標準庫；伺服器本身靠使用者裝（這台 WSL 有 `uvx`、沒有 `node`／`npx`）。
- **測試**：`tests/fake_mcp_server.py`（標準庫寫的 stdio 伺服器：兩支工具、一支回 isError、一支回圖、一支睡到逾時、一支 `$ref` schema、可選擇 initialize 失敗／中途死掉／回壞 JSON／反問 sampling）；測匯入（全收、`--only`、撞名、`$ref` 展開、說明加前綴與截斷）、`aos-tools ls --json` 看得到、`aos-tools call` 叫得到、逾時整群收掉沒孤兒、TERM 時收掉伺服器、env 檔合進伺服器環境且不出現在任何輸出；整合測試用假腦叫一支外部工具。真伺服器（`uvx mcp-server-time`）在這台實跑一次、寫進驗收。
- **工作量**：client 約 300 行、mcp_tool 150、import 250、測試 400；**2～3 天**。

## 邊緣狀況

1. **冷啟動慢**：`uvx`／`npx` 第一次會下載，可能超過 initialize 逾時（代定 30 秒）。`aos-mcp-import` 那次順便暖好；`_metainfo.timeout_ms` 預設 60 秒，可在包檔裡手改。
2. **伺服器 initialize 前往 stdout 印雜訊**（不守協定的）：非 JSON 行跳過、印 warning；連續 100 行都不是＝`ServerBad`。
3. **伺服器不結束**（關 stdin 也不走）：2 秒後 TERM 整群、再 2 秒 KILL；孫行程靠自成一群收。
4. **伺服器起了子行程又脫群**（`setsid`）：收不到，跟 shell 一樣管不了，文件寫明。
5. **同一支外部工具被平行叫**（eca 的 claude 會平行）：每次各起一台，互不干擾；伺服器自己的檔案鎖由它負責。
6. **伺服器端工具清單變了**：凍結的包照舊；叫到已經不在的工具＝伺服器回錯 → `ServerFailed`，訊息提示 `sync`。
7. **schema 寫法 tool_io 不懂**（`oneOf`、`patternProperties`、`$ref`）：不驗、原樣（展開後）給模型；只有 `$ref` 會撞 aos 指示詞，匯入時處理。
8. **schema 頂層不是 object**（少數伺服器）：包成 `{"type": "object", "properties": {}}` 並 warning。
9. **工具名撞 aos 原生工具**：只有完全同名才算撞（伺服器取名 `self`、外部工具叫 `tools`＝`self_tools`，就撞了）。包內撞名＝匯入時 `NameBad`；跟別包同名＝疊進 `$override` 時後面蓋前面（aos-tools 既有規則），匯入時看不到這層，README 提醒「伺服器名別取 aos 包名（self、mailbox、knowledge…）」。
10. **codex 起 aos-mcp 不帶環境**（11-11 踩過）：`cli_session.MCP_ENV` 只明寫 `AOS_*` 那幾個；`PATH`、`HOME` 是 codex 自己預設帶的（aos-mcp 就是靠 `PATH` 找到的），但 `uvx` 在 `~/.local/bin`、伺服器要 `HOME` 找快取，施工時在 codex 底下實跑一次確認；缺什麼再補進 `MCP_ENV`（這是唯一可能要動 cli_session 的地方）。env 檔的值不經這條，`mcp_tool` 每次自己讀。
11. **伺服器要 `HOME`、cwd**：cwd 代定＝`$AOS_WS`；環境＝工具拿到的環境（aos-exec 給的）＋env 檔。
12. **結果有圖片但腦不吃圖**：存檔印路徑；fsm 現在的 history 是純文字，之後要送圖另議。
13. **巨大結果**（一次回 10MB）：讀到 50KB 之後的直接丟、尾巴說明；JSON-RPC 單行太長仍要讀完才能解析——單一回應超過 16MB＝`ServerBad`。
14. **包檔被人手改壞**：`PackBad`，訊息帶哪一格；`aos-tools ls` 那層先報（它讀 `_tooldef`）。
15. **定義資料夾不被寫（P-15）**：包檔是人匯入時寫的，跑起來只讀；圖片存工具小格。
16. **同一個包疊進好幾隻 agent**：共用一份檔，各自的小格分開；`sync` 會同時影響所有疊它的 agent（文件寫明）。

## 代定

- D1 指令名 `aos-mcp-import`（C-54 R13 `aos-<領域>-<功能>`）；轉接程式 `mcp_tool`、模組 `mcp_client.py`。備選：`aos-agent mcp add`（掛在 aos-agent 底下，直接改這隻的 tools.json）。
- D2 包檔預設寫 `./mcp/NAME.json`，`--out` 可改；同一個檔同時是設定與包。
- D3 外部描述加 `[MCP server 名] ` 前綴、描述上限 1024 字元、參數說明 300。
- D4 initialize 逾時 30 秒、每支 `timeout_ms` 預設 60000、關閉寬限 2 秒。
- D5 `$ref` 就地展開（只本地 `#/…`，深度 10、遇環停），其他 `$` 開頭的 schema 鍵拿掉。
- D6 匯入不替人改 `tools.json`，只印要加哪一行。
- D7 新代號：`PackMissing`、`PackBad`、`PackExists`、`ServerFailed`、`ServerBad`、`ServerRejected`、`ToolUnknown`、`CallFailed`、`NameBad`（全落在 C-54 六種結尾）。
- D8 annotations → `_metainfo`：`readOnlyHint` → `side_effect`（反，沒寫＝true）、`idempotentHint` → `idempotent`、`openWorldHint` 或 HTTP → `resource` 含 `net`（同 aos-mcp 反方向的對應）。
- D9 MCP 包不進 `lib/packs`、範本不預設掛任何外部伺服器。

## 待裁

**M1 外部工具怎麼進工具表**
- 甲 匯入成包，每支一支 aos 工具（推薦）：不改 aos 核心、eca 自動有；匯入幾支就多幾支 token。
- 乙 通用 `mcp_ls`＋`mcp_call` 兩支：最省 token、最快做完；小模型要先列再叫、參數沒 schema。
- 丙 aos-tools 加「伺服器」種類、當場展開：最即時；改 aos-tools 核心、要新快取、說明會被伺服器偷換。

**M2 伺服器怎麼起的設定放哪**
- 甲 寫在包檔裡（匯入時寫，推薦）：一份檔走天下、可 `cp -r`；改設定＝改包檔或重匯入。
- 乙 另一份 `mcp.json`（Claude 格式）放定義資料夾、執行時讀：能直接抄 Claude 設定；多一份檔、多一個宣告。
- 丙 使用者層 `~/.aos/mcp.json` 共用：一台機器設一次；agent 帶到別台就斷。

**M3 金鑰放哪**
- 甲 env 檔只記位置（`--env-file`，推薦）：不靠環境變數、值不進任何 aos 檔；要多管一個檔。
- 乙 `${VAR}` 從呼叫者環境展開（Claude 寫法）：抄設定最方便；就是使用者怕的環境變數依賴，codex 底下還會掉。
- 丙 兩種都收：彈性最大；兩條路要各測、各寫文件。

**M4 伺服器行程**
- 甲 先做每次呼叫起一台，有狀態的之後另議（推薦）：純函數、沒孤兒、2～3 天；瀏覽器類不能用。
- 乙 一開始就做 daemon 常駐：什麼伺服器都能用；工作量大一個量級、要新 proc 種類。
- 丙 只做每次起，永遠不做常駐：最單純；有狀態的伺服器永遠只能靠 eca 原生掛。

**M5 誰能加伺服器**
- 甲 只有人（`aos-mcp-import`，推薦第一步）：加伺服器＝能跑任意指令，留在人手上。
- 乙 腦也能（給腦一支 `mcp_import`，同 tools_def＋self_tools 的精神）：agent 能自己長能力；它本來就有 shell，風險其實已經在。
- 丙 腦提、人核准（寄信給人、人回才匯入）：最安全；要新的核准流程。

**M6 一台伺服器的工具全收還是挑**
- 甲 預設全收、`--only`／`--except` 可挑、超過 20 支印 warning（推薦）：上手快；大伺服器會吃掉幾千 tokens。
- 乙 一定要 `--only` 列名字：工具表最乾淨；第一次用要先知道有哪些（import 加 `--list` 先看）。
- 丙 全收、不給挑：最簡單；GitHub 那種一掛就爆。

**M7 外部工具說明怎麼更新**
- 甲 凍結，人跑 `sync` 看差異、`--yes` 才換（推薦）：伺服器偷改說明進不來；要記得 sync。
- 乙 每次叫都重問、說明跟著伺服器變：永遠最新；提示注入可以悄悄進來，而且每格多起一次伺服器。

**M8 eca 怎麼用外部伺服器**
- 甲 走 aos 轉接（第一步自動就有，推薦）：hook、self_tools 一致；多兩層、每次冷起。
- 乙 cli_session 原生掛給 claude／codex：快、有狀態的能用；繞過 aos 的 hook 與核准，fsm／eca 分岔。
- 丙 包檔裡標一個欄位，每台伺服器自己選甲或乙：兩全；兩條路都要維護。
