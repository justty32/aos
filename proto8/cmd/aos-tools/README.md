# aos-tools — 一個 agent 資料夾一份工具註冊檔

← [cmd](../README.md)

`bin/aos-tools`（Python）管 tools.json：登記這隻 agent 能叫哪些工具、`call` 叫它們。`add` 成功印一行 `added NAME -> 絕對路徑 (寫進的檔: 存的原樣值)`（原樣值是 JSON，指示詞就印那段）、`rm` 每拿掉一個印一行 `removed NAME (寫進的檔)`；`aos-tools --help` 印頂層、`aos-tools 子命令 --help` 印那個子命令的英文說明。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)；覆蓋層見 [aos-agent docs/03](../aos-agent/docs/03-tools覆蓋層.md)。

**命令列小修**（11-10 [aos-tools-cli](../../thinking/2026-11/10/aos-tools-cli/README.md) 步 1）：`--file F` 子命令前後都收（前後都給且指到不同檔＝`ArgumentsBad`）；旗標要寫在 XXX／NAME 前面，寫在後面＝`ArgumentsBad flags go before XXX: --name`；沒給 `--file` 而 `./tools.json` 不在時，`ls`／`get`／`call`／`rm` 先印 `aos-tools: warning: ./tools.json not found; no tools (use --file F)`；`ls -l`（`--long`）一行多三欄 `FROM`（`檔#/tools/名`，覆蓋層的是 `檔#/add/名`）、`STORED`（存的原樣值，JSON）、`ENV`（只印變數名，沒有＝`-`），跟 `--json` 同給＝`ArgumentsBad`；`call NAME ARGS_JSON` 把 ARGS_JSON 原樣（不驗）當工具的 stdin，沒給照舊讀 stdin；登記檔的指示詞解不開時，訊息說出是哪個工具（`tool 名 (檔#/tools/名)`）。測試 `tests/test_cli.py`。

**可執行檔的定義快取在 stack**（11-10 步 2，使用者 Q2「快取搬到 stack 裡」）：`$AOS_STACK/tooldef_cache.json`，`{絕對路徑: {"stamp": "mtime奈秒-大小", "tooldef": …}}`；stamp 相符就用、不符重跑 `--tooldef` 並寫回（暫存檔＋改名）；檔壞＝當沒有、整份重寫；`AOS_STACK` 沒設或不是資料夾＝不快取、不寫也不建任何檔。登記檔不再存快取，登記格 `cache` 只收 `false`（`add --no-cache` 寫的，那支不讀不寫快取檔）；物件＝`RegistryBad`。[`stack.gitignore`](../aos-agent/stack.gitignore) 擋 `**/tooldef_cache.json`。測試 `tests/test_cache.py`。**要重建什麼**：對可執行檔 `add` 過的登記檔，刪掉各工具的 `cache` 那格（`aos-json del 檔#/tools/名/cache`）或重新登記。

`add XXX` 的相對路徑從當下 cwd 算，成功行的 PATH 一律印絕對路徑。**存法保留使用者的寫法**（11-10 午 TC，使用者「使用者自己準備。要用相對位置、絕對位置、環境變數指定都可」）：給絕對＝存絕對；給相對＝存成相對「寫進的那份檔」（有 `--overlay O` 是 O，否則登記檔）所在資料夾的相對；`--path-json JSON`＝原樣存（字串或指示詞，例 `--path-json '{"$env":"AOS_PROTO8","$path":"/lib/base/bash"}'`；add 當下解一次只為了驗與取名，解出的值不寫回，之後每次用到才解）。`aos-agent tools add` 照使用者給的寫法轉交（同一個 cwd）。**登記檔與覆蓋層都解指示詞**（`path`、`env` 兩格都收，同一套 `aos-json get --follow --resolve`）；路徑指不到＝`PathMissing`，訊息帶工具名、解出的路徑與它來自哪份檔的哪一格（`檔#/tools/名/path`／`檔#/add/名/path`）。讀取時，相對路徑從記錄它的登記檔或覆蓋層所在資料夾算。資料夾工具只認 `_tooldef.json` 與選填的 `_metainfo.json`；不帶副檔名的檔不讀，JSON 檔裡的 `_tooldef`／`_metainfo` key 照舊。

三種工具（資料夾、JSON、可執行檔）都經 `aos-exec`、arguments 原樣從 stdin 進。`call` 統一把父 `AOS_STACK` 換成 `tools/<登記名>/` 小格；呼叫者只傳自己的 stack，登記格 env 不能蓋掉小格。父沒設時交 aos-exec 給預設。

`add` 可用可重複的 `--envs K=V` 補 hub 變數（存進登記格 `env`，值照打的存——不放金鑰）；`--env-file FILE` **只記位置**（11-10 步 3，使用者 Q1）：存進登記格 `env_file`，寫法同 XXX，內容不進登記檔；add 當下檔在就讀一次只為驗格式與 hub 提醒、不在＝warning 照登記；每次 `call` 才讀，檔裡的 `${…}` 照那次呼叫的環境展開，不在＝`PathMissing` 不跑（N4「報錯不跑」）。call 時後面的贏：工具自己的 `.env`（只補沒設的）＜ 呼叫者環境 ＜ `env_file` ＜ `env` ＜ `AOS_STACK` 小格。`ls -l` 的 ENV 欄印 `env` 的名字與 `@"存的 env_file"`，不印值。測試 `tests/test_env_file.py`。不用重建：以前用 `--env-file` 登記的值仍在 `env` 裡照樣生效，要拿掉就重新登記。`--override` 整項重寫。工具定義 `env` 列的名稱若當下環境與這次設定都沒有，印一行 warning，仍登記、退 0。`ls --json` 保留完整 tooldef；brain／aos-mcp 給模型時只取 description／parameters，不傳 hub 值。
