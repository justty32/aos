# aos-tools — 一個 agent 資料夾一份工具註冊檔

← [cmd](../README.md)

`bin/aos-tools`（Python）管 tools.json：登記這隻 agent 能叫哪些工具、`call` 叫它們。`add` 成功印一行 `added NAME -> PATH`、`rm` 每拿掉一個印一行 `removed NAME`；`aos-tools --help` 印頂層、`aos-tools 子命令 --help` 印那個子命令的英文說明。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)；覆蓋層見 [aos-agent docs/03](../aos-agent/docs/03-tools覆蓋層.md)。

`add XXX` 的相對路徑從當下 cwd 算，成功行的 PATH 一律印絕對路徑。**存法保留使用者的寫法**（11-10 午 TC，使用者「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」；取代坑-92 的自動經錨點）：給絕對＝存絕對；給相對＝存成相對「寫進的那份檔」（有 `--overlay O` 是 O，否則登記檔）所在資料夾的相對；`--path-json JSON`＝原樣存（字串或指示詞，例 `--path-json '{"$env":"AOS_PROTO8","$path":"/lib/base/bash"}'`；add 當下解一次只為了驗與取名，解出的值不寫回，之後每次用到才解）；`--anchor`（使用者明講才做）＝XXX 在這份 repo 的 `proto8/` 裡時存 `.aos-proto8/<proto8 裡的路徑>`，那資料夾沒錨點、或錨點指不到 proto8 就建一條指這台 `proto8/` 的捷徑（已指得到一份 proto8 的、使用者自己放的相對錨點不改寫；不進 git：stack 的 `.gitignore` 照 stack.gitignore 的 `**/.*` 已擋）。`aos-agent tools add` 照使用者給的寫法轉交（同一個 cwd）。**登記檔與覆蓋層都解指示詞**（`path`、`env` 兩格都收，同一套 `aos-json get --follow --resolve`）；路徑指不到＝`PathMissing`，訊息帶工具名、解出的路徑與它來自哪份檔的哪一格（`檔#/tools/名/path`／`檔#/add/名/path`）；錨點路徑缺了另提示 relink。讀取時，相對路徑從記錄它的登記檔或覆蓋層所在資料夾算。資料夾工具只認 `_tooldef.json` 與選填的 `_metainfo.json`；不帶副檔名的檔不讀，JSON 檔裡的 `_tooldef`／`_metainfo` key 照舊。

三種工具（資料夾、JSON、可執行檔）都經 `aos-exec`、arguments 原樣從 stdin 進。`call` 統一把父 `AOS_STACK` 換成 `tools/<登記名>/` 小格；呼叫者只傳自己的 stack，登記格 env 不能蓋掉小格。父沒設時交 aos-exec 給預設。

`add` 可用 `--env-file FILE` 加可重複的 `--envs K=V` 補 hub 變數：檔案先、envs 後，存入登記格的 `env`。檔案相對 add 當下 cwd，存當下內容、call 不重讀；檔裡的 `${…}` 照命令列那樣，在 add 當下展開（命令列的 `--envs K=${HOME}/x` 由 shell 當場展開，檔案由 aos-tools 照同樣時點展開；檔裡沒大括號的 `$NAME` 照字面存，同 `.env` 格式；使用者 11-06「用${HOME}/...，本來就是在命令行這個階段展開」，[env-portability](../../thinking/2026-11/06/env-portability/README.md#使用者裁定11-06選項框)）；`--override` 整項重寫。工具定義 `env` 列的名稱若當下環境與這次設定都沒有，印一行 warning，仍登記、退 0。`ls --json` 保留完整 tooldef；brain／aos-mcp 給模型時只取 description／parameters，不傳 hub 值。
