# external-mcp：接外部 MCP server 的圖紙（11-12，只規劃、沒施工）——eca 由 CLI 自己接、fsm 經 aos 匯入成包，三題待使用者裁

← [2026-11-12](../README.md)｜[thinking](../../../README.md)｜前一版：[11-11 new-tools 03](../../11/new-tools/03-mcp-client.md)（M1～M8 已裁，照用）｜[01 盤點](01-盤點.md)｜[02 設計](02-設計.md)｜[03 施工切法](03-施工切法.md)｜[04 邊緣狀況](04-邊緣狀況.md)

> 狀態：圖紙第一版。沒改程式、條文、範本；沒下載、沒安裝、沒跑真腦。**等使用者裁下面三題，與一句開工。**

## 要你裁的三題

<a id="題一"></a>
### 題一：eca 要接哪幾台外部 server，定義裡寫在哪

背景：11-11 M8 你裁「每台伺服器自己選」（經 aos 轉接，或交給 claude／codex 自己接）。當時頂層的解讀是「包檔裡標記」。11-12 你說「eca本身就能接mcp」。

| 選項 | 長相 | 後果 |
|---|---|---|
| **a（推薦）** `cli.json` 加一個鍵 `mcp_servers`，列 server 檔 | `"mcp_servers": ["mcp/time.json"]`。寫在 `cli.json`＝CLI 自己接；疊進 `tools.json`＝經 aos。寫在哪就走哪條，包檔裡不放標記 | 多一個鍵、一支小指令 `aos-mcp-launch`，半天～1 天。claude 與 codex 同一種寫法；金鑰照 M3 走 env 檔、哪裡都不落地；之後 fsm 用同一份 server 檔 |
| b 不加鍵，文件教人把 CLI 自己的旗標寫進 `flags` | `"flags": [… "--mcp-config", "{\"mcpServers\": …}", "--allowedTools", "mcp__time"]` | 不用寫程式，驗過就能用。claude 與 codex 兩種寫法；金鑰只能明文寫進 `cli.json` 或放進 agent 的環境，兩個都會漏；跟 fsm 那條的包檔是兩份互不相干的設定 |
| c 包檔裡放一欄標記，cli_session 自己順著 `tools.json` 的 `$override` 找 | 包檔 `"mcp_server": {…, "eca": "native"}` | 宣告只在 `tools.json` 一處。cli_session 得學會登記檔的疊法（現在只有 aos-tools 懂）；只想原生掛的也要先有 `tools.json` |

<a id="題二"></a>
### 題二：CLI 自己接的那條凍結不了工具說明

衝突：11-11 M7 你裁「可選。默認用凍結的。」——外部 server 的工具說明匯入時凍結，人看過差異才更新。CLI 自己接時，claude／codex 每次開場直接問 server，aos 插不進去，server 改了說明腦就看到新的。

| 選項 | 後果 |
|---|---|
| **a（推薦）** 接受：CLI 自己接＝不凍結；要凍結的那台改走經 aos | 文件寫明這個差別。server 檔的 `only` 可以把工具「名字」鎖住（多出來的工具進不來），說明文字仍跟著 server 變 |
| b CLI 自己接的也要先匯入，開場只放行匯入時那幾支 | 名字鎖住，說明文字一樣擋不住；每台都得先匯入，要等 fsm 那條的程式做完，公司這幾步不能先上 |
| c eca 也一律經 aos，不做 CLI 自己接 | 凍結完整。有狀態的 server 不能用、每次呼叫都重起 server；跟「eca本身就能接mcp」相反 |

<a id="題三"></a>
### 題三：定義裡列了的外部 server，工具要不要整台免核准

衝突：11-11 你裁的是「只對 aos 那組工具關掉核准…codex 自帶的工具照舊要核准。」外部 server 不在那句話裡。eca 平常是非互動在跑，沒有人可以按核准：沒放行的工具 claude 直接拒、codex 卡住或拒。

| 選項 | 後果 |
|---|---|
| **a（推薦）** 列了＝整台放行（claude 進白名單、codex 只對那幾台免核准） | 寫進定義就是點頭。server 之後自己多出來的工具也會被放行；想收緊的人在 server 檔寫 `only` |
| b 一定要寫 `only` 點名工具才放行，沒寫的那台不掛並印 warning | 每一支都是人點過名的。第一次用要先查那台有哪些工具再回來寫 |

兩個選項都不加任何全權限繞過的旗標，CLI 自帶工具的核准與沙盒不動。

## 一段白話

外部 MCP server 是別人寫好的工具箱。一台 server 寫成一份 server 檔，講怎麼起它、要哪幾支、金鑰檔在哪。

- **eca（claude／codex）**：CLI 本來就會接 MCP，所以讓它自己接。定義的 `cli.json` 列出 server 檔，cli_session 起 CLI 前把它翻成 CLI 認得的設定，跟 aos 自己那台並排。工具由 CLI 自己列、自己叫，aos 不包一層。
- **fsm（aos 自己的迴圈）**：沒有現成的 client，照 11-11 已裁的做——人跑一次 `aos-mcp-import` 把那台的工具凍結進 server 檔，每支外部工具變成一支普通的 aos 工具，叫一次起一台 server、叫完收掉。eca 想要 hook 攔得到、說明凍結，也可以走這條。
- **金鑰**：只放你自己的 env 檔，server 檔只記位置；起 server 的那一刻才讀，不進定義、設定檔、命令列、stack、紀錄。

小例子：

```json
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

## 施工切法（細節在 [03](03-施工切法.md)）

| 步 | 內容 | 多大 | 哪裡做 |
|---|---|---|---|
| 0 | 不改程式：`flags` 直接寫 CLI 的 MCP 旗標，真腦叫一次外部工具；驗掉盤點裡「沒查到」的幾項。對象＝再起一台 aos-mcp 當外部 server（不用下載、不用金鑰） | 1～2 小時 | 公司 |
| 1 | `cli.json` 的 `mcp_servers`、`aos-mcp-launch`、共用模組、測試、文件 | 半天～1 天 | 公司 |
| 2 | 收尾：server 沒起來印 warning、codex 的逐支開關、定義檢查 | 半天 | 公司 |
| 3 | fsm 那條階段 1：client、`mcp_tool`、`aos-mcp-import` | 2～3 天 | fsm 真腦回家驗 |
| 4 | `sync`、可選每次重問、給腦用的匯入、HTTP | 1.5～2 天 | 回家 |
| 5 | 常駐的 server proc | 另開設計 | — |

## 代定（照原則與既有裁定定的，每條可翻案）

- **X1** eca 以 CLI 自己接為主、排在最前面做；fsm 只走經 aos。依據：11-12「eca本身就能接mcp」、11-11 晚「eca通常都有自己的基礎工具…更順手」。11-11 的 03 把原生掛排在階段 3，順序改了。
- **X2** server 檔就是 M2 的包檔；可以先只有 `mcp_server` 一段，匯入＝把工具凍結進同一份檔（檔裡已有 `mcp_tools` 才算 `PackExists`）。
- **X3** `cli.json` 的鍵叫 `mcp_servers`，值是路徑陣列，相對路徑與指示詞的規則同現有的 `tools` 鍵。
- **X4** server 名只收 `[a-z][a-z0-9_]*`、最多 32 字，不准叫 `aos`。
- **X5** CLI 自己接的 server 一律經 `aos-mcp-launch` 起（它 exec 成 server，不多留一層行程），不分有沒有金鑰；指令放 `cmd/aos-mcp-launch/`。
- **X6** 讀 server 檔的程式只寫一份 `lib/mcp_server_file.py`，cli_session、`aos-mcp-launch`、之後的 `mcp_tool` 與 `aos-mcp-import` 共用。
- **X7** server 的環境：收到的 ＜ `env_file` ＜ `env`；`env_file` 寫了但檔不在＝`PathMissing`、不起。
- **X8** `mcp_servers` 裡某一台壞了（檔不在、形狀不對、重名、叫 `aos`）＝warning 跳過那台，其他照接。依據 11-12「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」，以及同日 aos-tools 已照同一個意思改成一條登記壞了略過那支、印 warning（[tool-path-broken](../tool-path-broken.md)）；跟 cli_session 現在「`tools` 指的檔不在＝`ToolsMissing` 直接停」的做法不同調，那條不動。
- **X9** `only`／`except` 記在 server 檔（M6）；claude 翻成 `--allowedTools`／`--disallowedTools`；codex 查不到逐支的欄位＝寫了 `only`／`except` 的那台不掛並 warning，不默默整台放行。
- **X10** 範本的 `--strict-mcp-config` 照留；codex 不預設加 `--ignore-user-config`。
- **X11** CLI 自己接的外部工具不算 aos 工具：不進 `aos-tools ls`、`before_tool`／`after_tool` 攔不到、`self_tools` 不管。
- **X12** 不洗 server 拿到的環境；金鑰不放 agent 的環境。
- **X13** fsm 不做常駐的 MCP 連線；有狀態的 server 等 M4 後半「專門的常駐aos proc」。
- **X14** 腦自己加減「CLI 自己接」的 server 這一輪不做；M5 由經 aos 那條滿足。
- **X15** 不為外部 server 另做沙箱；邊界用 Linux 權限與 aos-sandbox，選哪台 server 的風險歸寫定義的人。
- **X16** 範本預設不掛任何外部 server（沿 03 的 D9）。
- **X17** HTTP（兩條路）與「金鑰放標頭」排在步 4，開工前另出題。
- **X18** 步 0 的驗證對象＝第二台 aos-mcp；真的別人寫的＝`uvx mcp-server-time`，下載要你點頭。
- **X19** 錯誤代號沿用 03 的 `PackMissing`、`PackBad`、`LaunchFailed` 與現有的 `PathMissing`、`DotenvBad`、`CliMissing`，不新增。
- **X20** 匯入寫的工具定義用獨立的 `_tooldef` 鍵（N-69 現行讀法）。

## 未決

- 上面三題。
- 什麼時候開工（步 0～2 公司能做；你 11-12 上午說的是「等假日在家再來稿」）。
- [01](01-盤點.md) 標「沒查到」的六項，步 0 驗。

## 建議 Argon 審的重點

今天沒找 Argon 審。要審的話看這幾處：

1. **題一的 a**：`cli.json` 加鍵、「寫在哪就走哪條」，有沒有變成暗規則；跟 M8「每台伺服器自己選」的原話合不合。
2. **`aos-mcp-launch`**：金鑰真的不落地嗎——claude 把環境傳給 server 與 Bash、codex 的 `-c` 出現在命令列、`live.jsonl`、小格 `mcp.json`，逐處對一次（[02 金鑰](02-設計.md#金鑰與環境變數)）。
3. **X8**：壞的 server 檔 warning 跳過，跟 KISS「寫什麼就做什麼，不靜靜吞掉」與 cli_session 現有的 `ToolsMissing` 做法有沒有打架。
4. **X9 與題三**：codex 查不到逐支開關時「不掛」對不對；整台免核准有沒有哪個旗標組合實際上變成全放行。
5. **X5**：一律經 launcher 是不是多此一舉（沒有金鑰的 server 直接把 `command` 交給 CLI 更簡單）。
6. **02 對 11-11 的 03 改的四處**，有沒有碰到已裁的 M1～M7。
7. **[04](04-邊緣狀況.md) 第 12 項**：非互動每輪重起 server，使用者期待的「eca本身就能接mcp」包不包含跨輪記住狀態。
