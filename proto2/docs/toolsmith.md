# toolsmith 工具包

toolsmith 讓 agent 把常打的 shell 指令變成自己的工具。

所有東西只放在自己的 home。
不會改出廠內建的工具包。

## 工具清單

### tool_add

新增一個 shell 工具。

要給四樣：`name`、`description`、`parameters`、`command`。
簡單工具可以不給 `parameters`，會自動補成沒有參數的 object。

`command` 是一句 shell。
呼叫工具時，參數 JSON 會從 stdin 傳進去。
工作目錄是 agent 的世界資料夾。

也可以只給 `pack`。
它會在 `<home>/packs/<名字>.py` 建一份空骨架，並把這包打開。
骨架有 `PROMPT`、`TOOLS` 和 `run`。

同名自製工具不會直接蓋掉。
先用 `tool_remove`，再重加。

### tool_list

列出目前的工具。

每條有名字、來自哪一包、用途。
自製 shell 工具還會列出 `command`。

造工具前先看一次，免得重複。

### tool_remove

給 `name`，移除一個自製 shell 工具。

包裡的工具不能單獨移除。
這時會告訴你它來自哪一包。

給 `pack`，會關掉整包。
自己的 pack 骨架檔仍會留著。

### tool_try

給 `name` 和選填的 `args`。

它會在當格直接跑一次自製 shell 工具。
回傳 `exit`、`stdout`、`stderr`。

## 什麼時候用

同一串 shell 常手打，就把它做成工具。

先 `tool_list`。
再 `tool_add`。
加完立刻 `tool_try`。
確定能跑，下一格再正式呼叫它。

需要幾個工具共用 Python 程式時，才開 pack 骨架。

## 設定

在 `<home>/tools.json` 的 `packs` 加上 `toolsmith`。

自製 shell 工具存在同一檔的 `tools`。
自己的 Python 包存在 `<home>/packs/`。

每一格開頭才會重讀工具清單。
所以新增和移除都在下一格正式生效。
`tool_try` 不用等，當格就能試。

## 坑

- shell 工具沒有沙箱，也沒有逾時。
- 指令可以刪檔、連網，也能走出世界資料夾。
- `parameters` 只是告訴模型怎麼填。真正收到的是 stdin 裡的一包 JSON。
- 同時有兩格改 `tools.json`，可能互相蓋掉。
- 自製工具跟包裡工具同名時，包裡的會贏。
- 工具輸出很長時會截短。
