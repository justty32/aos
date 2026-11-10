# aos-tools — 一個 agent 資料夾一份工具註冊檔

← [cmd](../README.md)

`bin/aos-tools`（Python）管 tools.json：登記這隻 agent 能叫哪些工具、`call` 叫它們。`add` 成功印一行 `added NAME -> PATH`、`rm` 每拿掉一個印一行 `removed NAME`；`aos-tools --help` 印頂層、`aos-tools 子命令 --help` 印那個子命令的英文說明。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)；覆蓋層見 [aos-agent docs/03](../aos-agent/docs/03-tools覆蓋層.md)。

`add XXX` 的相對路徑從當下 cwd 算，成功行的 PATH 一律印絕對路徑。未用 `--overlay` 時，登記檔也存絕對路徑；有 `--overlay O` 時只寫 O，一律存相對 O 所在資料夾的路徑：XXX 在那資料夾裡＝照字串算相對；在這份 repo 的 `proto8/` 裡（realpath 比對，repo 從 aos-tools 自己的 realpath 推）＝存 `.aos-proto8/<proto8 裡的路徑>`，並在 O 的資料夾建錨點捷徑 `.aos-proto8` → 這台的 `proto8/`（不進 git：stack 的 `.gitignore` 照 stack.gitignore 的 `**/.*` 已擋；換機 pull 後 `templates/copy-out --relink <根>` 重指）；其他外面的＝相對（同包搬才對）。未用 `--overlay` 時照舊存絕對，只有登記檔那資料夾已有錨點（copy-out 抄的 agent）、XXX 又在 repo 裡時存 `.aos-proto8/…`。存的字串不含這台的家目錄或 repo 位置（11-10 坑-92，使用者「盡量支援相對路徑」「會頻繁遷移，透過github」；原本指到 repo 的 lib 會存成 `../../../home/…`）。錨點缺了或指錯＝`PathMissing …`，訊息尾提示 relink。讀取時，相對路徑從記錄它的登記檔或覆蓋層所在資料夾算。資料夾工具只認 `_tooldef.json` 與選填的 `_metainfo.json`；不帶副檔名的檔不讀，JSON 檔裡的 `_tooldef`／`_metainfo` key 照舊。

三種工具（資料夾、JSON、可執行檔）都經 `aos-exec`、arguments 原樣從 stdin 進。`call` 統一把父 `AOS_STACK` 換成 `tools/<登記名>/` 小格；呼叫者只傳自己的 stack，登記格 env 不能蓋掉小格。父沒設時交 aos-exec 給預設。

`add` 可用 `--env-file FILE` 加可重複的 `--envs K=V` 補 hub 變數：檔案先、envs 後，存入登記格的 `env`。檔案相對 add 當下 cwd，存當下內容、call 不重讀；檔裡的 `${…}` 照命令列那樣，在 add 當下展開（命令列的 `--envs K=${HOME}/x` 由 shell 當場展開，檔案由 aos-tools 照同樣時點展開；檔裡沒大括號的 `$NAME` 照字面存，同 `.env` 格式；使用者 11-06「用${HOME}/...，本來就是在命令行這個階段展開」，[env-portability](../../thinking/2026-11/06/env-portability/README.md#使用者裁定11-06選項框)）；`--override` 整項重寫。工具定義 `env` 列的名稱若當下環境與這次設定都沒有，印一行 warning，仍登記、退 0。`ls --json` 保留完整 tooldef；brain／aos-mcp 給模型時只取 description／parameters，不傳 hub 值。
