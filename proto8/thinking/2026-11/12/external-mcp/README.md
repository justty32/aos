# external-mcp：接外部 MCP server（11-12）——eca 由 CLI 自己接，11-12 下午施工做完五步（codex／claude 兩身、http 與 stdio、範本與說明）；fsm 經 aos 匯入成包延後

← [2026-11-12](../README.md)｜[thinking](../../../README.md)｜前一版：[11-11 new-tools 03](../../11/new-tools/03-mcp-client.md)（M1～M8 已裁，照用）｜[01 盤點](01-盤點.md)｜[02 設計](02-設計.md)｜[03 施工切法](03-施工切法.md)｜[04 邊緣狀況](04-邊緣狀況.md)｜[05 http＋bearer 試接](05-http-bearer試接.md)｜[06 施工結果](06-施工結果.md)

> **11-12 下午施工**（使用者「外部 MCP 開工吧，做不完就push上去，我回家繼續做」）：03 的五步都做完、各一個 commit，見 [06 施工結果](06-施工結果.md)（續行點、代定 E1～E7、搬一隻現有 Codex agent 的照抄步驟）。沒做：fsm 那條。
>
> 狀態（施工前）：圖紙**第二版**（11-12 下午照 [05](05-http-bearer試接.md#對圖紙的調整建議) 的實測改過 02、03、04），**三題已裁（使用者 11-12「都按照推薦。」）**。沒改程式、條文、範本；沒下載、沒安裝。**還沒施工，等使用者說開工**（他 11-12 上午說的是「等假日在家再來稿」；五步都只碰 eca、公司可做）。
>
> 11-12 下午 http＋bearer＋自簽憑證試接 [05](05-http-bearer試接.md)（使用者「好，先驗」）：假 http MCP＋codex luna 經 aos 叫得到、三個 `-c` 寫進 `cli.json` 的 flags 就行；token 用定義的 sh `_entry` 讀 env 檔給＝哪裡都不留，`ctl add --envs` 給＝明文進 stack 的 exec.json；codex 有 `enabled_tools`、沙盒管不到 MCP 連線。
>
> **第二版改了什麼**：server 檔多收 `transport: "http"`（`url`、`bearer_token_env`、`env_file`、`ca_file`）；施工順序重排成先 codex 身＋http server；X5、X7、X9、X12、X17、X18 改寫；[04](04-邊緣狀況.md) 第 5 項作廢、加 23～26。

## 各檔一句話

| 檔 | 一句話 |
|---|---|
| [01 盤點](01-盤點.md) | aos 現在跟 MCP 有關的一切、兩支 CLI 怎麼接外部 server、使用者講過定過的（上午寫的，沒改；裡面標「沒查到」的 codex 逐支開關與沙盒兩項，05 已實測） |
| [02 設計](02-設計.md) | 一台 server 一份 server 檔（stdio 或 http）；寫進 `cli.json` 就是 CLI 自己接，疊進 `tools.json` 就是經 aos 接 |
| [03 施工切法](03-施工切法.md) | 五步、每步各自能獨立合併：codex 身＋http → `--envs` 文件警告 → claude 身 → stdio＋`aos-mcp-launch` → 範本與說明；fsm 延後 |
| [04 邊緣狀況](04-邊緣狀況.md) | 原生掛這條的 26 項（第 5 項作廢） |
| [05 http＋bearer 試接](05-http-bearer試接.md) | 11-12 下午實測：接得上；token 怎麼給才不漏；對圖紙的調整建議（第二版的依據） |
| [06 施工結果](06-施工結果.md) | 11-12 下午施工：五步各一個 commit、怎麼驗的、代定 E1～E7、沒做的、家機注意、搬一隻現有 Codex agent 的照抄步驟 |
| [07 fsm 施工單](07-fsm施工單.md) | fsm 經 aos 那條切成九步（每步半天內、各一個 commit、各有驗法；步 2 做完就看得到 `aos-tools call` 叫到外部工具，步 8 才要真腦）；題一 11-12 已裁 a（只收 Bearer）、代定 F1～F12 使用者「先這樣」（「那就a。fable代定就先這樣，感覺都OK，以後出問題再來解決」）；家機照它派工 |

## 已裁的三題（使用者 11-12：「都按照推薦。」）

<a id="題一"></a>
### 題一：eca 要接哪幾台外部 server，定義裡寫在哪 → `cli.json` 加 `mcp_servers` 鍵

`cli.json` 加一個選填鍵 `mcp_servers`，列 server 檔（例 `"mcp_servers": ["mcp/time.json"]`）。寫在 `cli.json`＝CLI 自己接；疊進 `tools.json`＝經 aos。寫在哪就走哪條，包檔裡不放標記。這是 11-11 M8「每台伺服器自己選」的落地。連帶做一支小指令 `aos-mcp-launch`（第二版：只給 stdio 的 server 用）；claude 與 codex 同一種寫法；金鑰照 M3 走 env 檔。

<a id="題二"></a>
### 題二：CLI 自己接的那條凍結不了工具說明 → 接受，要凍結的那台走經 aos

**這是 11-11 M7「可選。默認用凍結的。」在「CLI 自己接」那條路上的例外**：claude／codex 每次開場直接問 server，aos 插不進去，server 改了說明腦就看到新的。M7 在經 aos 那條照舊（匯入時凍結、人看過差異才更新）。文件要寫明這個差別；server 檔的 `only` 可以把工具名字鎖住（多出來的工具進不來），說明文字仍跟著 server 變。

<a id="題三"></a>
### 題三：定義裡列了的外部 server，工具要不要整台免核准 → 列了＝整台放行

寫進定義就是點頭：claude 把那台加進白名單（`--allowedTools mcp__名`），codex 只對列出來的那幾台設免核准。這把 11-11「只對 aos 那組工具關掉核准…codex 自帶的工具照舊要核准。」的免核准擴到定義裡列出的外部 server；codex 自帶工具的核准與沙盒照舊不動。server 之後自己多出來的工具也會被放行，想收緊的人在 server 檔寫 `only`。不加任何全權限繞過的旗標。

## 一段白話

外部 MCP server 是別人寫好的工具箱。一台 server 寫成一份 server 檔，講怎麼連它（stdio＝怎麼起；http＝網址）、要哪幾支、金鑰檔在哪。

- **eca（claude／codex）**：CLI 本來就會接 MCP，所以讓它自己接。定義的 `cli.json` 列出 server 檔，cli_session 起 CLI 前把它翻成 CLI 認得的設定，跟 aos 自己那台並排。工具由 CLI 自己列、自己叫，aos 不包一層。
- **fsm（aos 自己的迴圈）**：沒有現成的 client，照 11-11 已裁的做——人跑一次 `aos-mcp-import` 把那台的工具凍結進 server 檔，每支外部工具變成一支普通的 aos 工具，叫一次起一台 server、叫完收掉。eca 想要 hook 攔得到、說明凍結，也可以走這條。這條延後。
- **金鑰**：只放你自己的 env 檔，server 檔只記位置，不進定義、設定檔、命令列、stack、紀錄。stdio＝起 server 的那一刻才讀、只進 server 的環境；http＝起 CLI 的那一刻才讀、只進 CLI 那支行程的環境（codex 再用 `shell_environment_policy.exclude` 不給腦的 shell）。

小例子：

```json
mcp/teamsite.json {"description": "MCP server teamsite (http, bearer token, private CA).",
                   "mcp_server": {"name": "teamsite", "transport": "http",
                                  "url": "https://teamsite.example:8443/mcp",
                                  "bearer_token_env": "TEAMSITE_TOKEN",
                                  "env_file": "/home/me/.config/cody/teamsite.env",
                                  "ca_file": "/home/me/.config/cody/ca-bundle.pem"}}

eca 的 cli.json   {"kind": "codex", "flags": […], "mcp_servers": ["mcp/teamsite.json"], …}
                  → 腦看到 mcp__teamsite__list_threads

mcp/time.json   {"description": "MCP server time (stdio, no key).",
                 "mcp_server": {"name": "time", "transport": "stdio", "command": "uvx", "args": ["mcp-server-time"]}}

eca 的 cli.json   {"kind": "claude", "flags": […], "mcp_servers": ["mcp/time.json"], …}
                  → 腦看到 mcp__time__get_current_time

fsm 的 tools.json {"$override": [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}, "mcp/time.json"], "tools": {}}
                  （先跑過 aos-mcp-import）→ 腦看到 time_get_current_time
```

## 使用者原話

- 11-11：「那就1,2,5！」；M1～M8 的裁定與「mcp這塊先到這邊就好，不急著做。」見 [01](01-盤點.md#使用者講過定過的逐字)。
- 11-12 上午：「不用。eca本身就能接mcp，等假日在家再來稿」
- 11-12 下午：「外部MCP，可以開始規劃」
- 11-12 下午（看過圖紙的三題後）：「都按照推薦。」
- 11-12 下午（頂層提用假的 http MCP 搭一隻 Codex 身試接）：「好，先驗」→ [05](05-http-bearer試接.md)

## 施工切法（細節在 [03](03-施工切法.md)；每步各自能獨立合併，都在公司可做）

| 步 | 內容 | 多大 |
|---|---|---|
| 1 | codex 身＋http server：`cli.json` 的 `mcp_servers` 鍵、`lib/mcp_server_file.py`、cli_session 翻成 `-c mcp_servers.<名>.*`、讀 `env_file` 只放進 codex 行程環境、自動補 `shell_environment_policy.exclude`、`ca_file` 設兩個憑證變數、畫面那條路也帶、壞的 server 檔 warning 跳過 | 半天～1 天 |
| 2 | `aos-agent ctl add --envs` 明文落地：只做文件警告 | 很小 |
| 3 | claude 身：`mcp.json` 跟 aos 那台並排、`--strict-mcp-config` 照留、`--allowedTools mcp__<名>` | 半天 |
| 4 | stdio server＋`aos-mcp-launch`（兩身）；驗證用再起一台 aos-mcp 當外部 server（不用下載、不用金鑰） | 半天～1 天 |
| 5 | 範本與說明、定義檢查 | 半天 |
| 延後 | fsm 那條：匯入成包、client、`mcp_tool`、`sync`、經 aos 的 http、常駐 proc（細切見 [07](07-fsm施工單.md)） | 照 11-11 的 03 |

## 代定（照原則與既有裁定定的，每條可翻案）

- **X1** eca 以 CLI 自己接為主、排在最前面做；fsm 只走經 aos。依據：11-12「eca本身就能接mcp」、11-11 晚「eca通常都有自己的基礎工具…更順手」。11-11 的 03 把原生掛排在階段 3，順序改了。
- **X2** server 檔就是 M2 的包檔；可以先只有 `mcp_server` 一段，匯入＝把工具凍結進同一份檔（檔裡已有 `mcp_tools` 才算 `PackExists`）。
- **X3** `cli.json` 的鍵叫 `mcp_servers`，值是路徑陣列，相對路徑與指示詞的規則同現有的 `tools` 鍵。
- **X4** server 名只收 `[a-z][a-z0-9_]*`、最多 32 字，不准叫 `aos`。
- **X5**（第二版改）CLI 自己接的 **stdio** server 一律經 `aos-mcp-launch` 起（它 exec 成 server，不多留一層行程），不分有沒有金鑰；指令放 `cmd/aos-mcp-launch/`。**http server 沒有可以 exec 的行程，不經 launcher，由 cli_session 自己備 CLI 行程的環境。** 原文：「CLI 自己接的 server 一律經 `aos-mcp-launch` 起…不分有沒有金鑰」。
- **X6** 讀 server 檔的程式只寫一份 `lib/mcp_server_file.py`，cli_session、`aos-mcp-launch`、之後的 `mcp_tool` 與 `aos-mcp-import` 共用。
- **X7**（第二版補 http）stdio server 的環境：收到的 ＜ `env_file` ＜ `env`。http：只從 `env_file` 拿 `bearer_token_env` 講的那一個變數，放進 CLI 行程的環境；沒寫 `env_file`＝用 CLI 本來就繼承到的。`env_file`／`ca_file` 寫了但檔不在＝`PathMissing`、那台不接。
- **X8** `mcp_servers` 裡某一台壞了（檔不在、形狀不對、重名、叫 `aos`）＝warning 跳過那台，其他照接。依據 11-12「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」，以及同日 aos-tools 已照同一個意思改成一條登記壞了略過那支、印 warning（[tool-path-broken](../tool-path-broken.md)）；跟 cli_session 現在「`tools` 指的檔不在＝`ToolsMissing` 直接停」的做法不同調，那條不動。
- **X9**（第二版改）`only`／`except` 記在 server 檔（M6）；claude 翻成 `--allowedTools`／`--disallowedTools`；codex 的 `only` 直接翻成 `mcp_servers.<名>.enabled_tools`（05 實測有效）；**`except` 翻成 `disabled_tools`——沒實測，代定**，步 1 開工先驗，沒效＝寫了 `except` 的那台在 codex 底下不掛並 warning，不默默整台放行。原文：「codex 查不到逐支的欄位＝寫了 `only`／`except` 的那台不掛並 warning」。
- **X10** 範本的 `--strict-mcp-config` 照留；codex 不預設加 `--ignore-user-config`。
- **X11** CLI 自己接的外部工具不算 aos 工具：不進 `aos-tools ls`、`before_tool`／`after_tool` 攔不到、`self_tools` 不管。
- **X12**（第二版改）不洗 server 拿到的環境。**stdio**：金鑰不放 agent 的環境，`aos-mcp-launch` 起 server 那一刻才讀進 server 的環境。**http**：bearer 只能放 CLI 行程的環境（CLI 的 bearer 設定只認自己的環境），cli_session 起 CLI 那一刻才讀、只給那支行程；codex 靠 `shell_environment_policy.exclude` 不給腦的 shell，cli_session 自動補。原文：「不洗 server 拿到的環境；金鑰不放 agent 的環境。」
- **X13** fsm 不做常駐的 MCP 連線；有狀態的 server 等 M4 後半「專門的常駐aos proc」。
- **X14** 腦自己加減「CLI 自己接」的 server 這一輪不做；M5 由經 aos 那條滿足。
- **X15** 不為外部 server 另做沙箱；邊界用 Linux 權限與 aos-sandbox，選哪台 server 的風險歸寫定義的人。
- **X16** 範本預設不掛任何外部 server（沿 03 的 D9）。
- **X17**（第二版改）http 的 **codex 這半提前到步 1**（05 實測不改程式就跑得通）；claude 那半在步 3，bearer 與憑證怎麼給開工先驗；經 aos 那條的 http 與「金鑰放標頭」跟 fsm 一起延後、開工前另出題。原文：「HTTP（兩條路）與「金鑰放標頭」排在步 4，開工前另出題。」
- **X18**（第二版改）步 1 的驗證對象＝假 http MCP server（標準庫，沿 05 那支）；步 4（stdio）的驗證對象＝第二台 aos-mcp；真的別人寫的＝`uvx mcp-server-time`，下載要你點頭。
- **X19** 錯誤代號沿用 03 的 `PackMissing`、`PackBad`、`LaunchFailed` 與現有的 `PathMissing`、`DotenvBad`、`CliMissing`，不新增。
- **X20** 匯入寫的工具定義用獨立的 `_tooldef` 鍵（N-69 現行讀法）。
- **X21**（第二版新增，跟著 http 形狀來的）http server 檔的欄位名：`url`、`bearer_token_env`（變數名）、`env_file`、`ca_file`（選填）；`ca_file` 同時設 `SSL_CERT_FILE` 與 `CODEX_CA_CERTIFICATE`；鍵寫錯種類＝server 檔壞；兩台的 `ca_file` 不同＝第一台算數、後面那台 warning 跳過。
- **X22**（第二版新增）`aos-agent ctl add --envs` 明文落地這一輪只做文件警告，不改程式（05 的 P1）。

## 未決

- 什麼時候開工（五步公司都能做；你 11-12 上午說的是「等假日在家再來稿」）。
- 還沒驗的，排在各步的「開工先驗」（[03](03-施工切法.md)）：codex 的 `disabled_tools` 有沒有效、`flags` 自己也寫 `exclude` 時誰算數（步 1）；claude 的 http 設定形狀、bearer 怎麼給才不落地又不進腦的 Bash、`ca_file` 對 claude 設哪個變數、server 沒起來的事件欄位（步 3）；codex 的沙盒管不管 stdio server（步 4）。[01](01-盤點.md) 標「沒查到」的六項裡，codex 逐支開關與沙盒（http）兩項 05 已實測。

## 建議 Argon 審的重點

今天沒找 Argon 審。要審的話看這幾處：

1. **題一（已裁）**：`cli.json` 加鍵、「寫在哪就走哪條」，有沒有變成暗規則；跟 M8「每台伺服器自己選」的原話合不合。
2. **金鑰真的不落地嗎**：stdio 經 `aos-mcp-launch`、http 經 cli_session 放進 CLI 行程環境——claude 把環境傳給 server 與 Bash、codex 的 `-c` 出現在命令列、`live.jsonl`、小格 `mcp.json`，逐處對一次（[02 金鑰](02-設計.md#金鑰與環境變數)）。
3. **X8**：壞的 server 檔 warning 跳過，跟 KISS「寫什麼就做什麼，不靜靜吞掉」與 cli_session 現有的 `ToolsMissing` 做法有沒有打架。
4. **X9 與題三（已裁整台放行）**：codex 的 `except`（`disabled_tools`）驗不過時「不掛」對不對；整台免核准有沒有哪個旗標組合實際上變成全放行。
5. **X5**：stdio 一律經 launcher 是不是多此一舉（沒有金鑰的 server 直接把 `command` 交給 CLI 更簡單）。
6. **02 對 11-11 的 03 改的四處**，有沒有碰到已裁的 M1～M7。
7. **[04](04-邊緣狀況.md) 第 12 項**：非互動每輪重起 server，使用者期待的「eca本身就能接mcp」包不包含跨輪記住狀態。
