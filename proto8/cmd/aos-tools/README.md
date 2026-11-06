# aos-tools — 一個 agent 資料夾一份工具註冊檔

← [cmd](../README.md)

`bin/aos-tools`（Python）管 tools.json：登記這隻 agent 能叫哪些工具、`call` 叫它們。`add` 成功印一行 `added NAME -> PATH`、`rm` 每拿掉一個印一行 `removed NAME`；`aos-tools --help` 印頂層、`aos-tools 子命令 --help` 印那個子命令的英文說明。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)；覆蓋層見 [aos-agent docs/03](../aos-agent/docs/03-tools覆蓋層.md)。

`add XXX` 的相對路徑從當下 cwd 算，成功行的 PATH 一律印絕對路徑。未用 `--overlay` 時，登記檔也存絕對路徑；有 `--overlay O` 時只寫 O，存相對 O 所在資料夾的路徑（字串計算、不解捷徑）。讀取時，相對路徑從記錄它的登記檔或覆蓋層所在資料夾算。資料夾工具只認 `_tooldef.json` 與選填的 `_metainfo.json`；不帶副檔名的檔不讀，JSON 檔裡的 `_tooldef`／`_metainfo` key 照舊。

三種工具（資料夾、JSON、可執行檔）都經 `aos-exec`、arguments 原樣從 stdin 進。`call` 統一把父 `AOS_STACK` 換成 `tools/<登記名>/` 小格；呼叫者只傳自己的 stack，登記格 env 不能蓋掉小格。父沒設時交 aos-exec 給預設。

`add` 可用 `--env-file FILE` 加可重複的 `--envs K=V` 補 hub 變數：檔案先、envs 後，存入登記格的 `env`。檔案相對 add 當下 cwd，存當下內容、call 不重讀；`--override` 整項重寫。工具定義 `env` 列的名稱若當下環境與這次設定都沒有，印一行 warning，仍登記、退 0。`ls --json` 保留完整 tooldef；brain／aos-mcp 給模型時只取 description／parameters，不傳 hub 值。
