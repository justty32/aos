# memory — 唯讀查記憶庫（資料夾＋.json 的一棵 JSON 樹）

圖紙：[thinking 11-10 json-memory](../../../thinking/2026-11/10/json-memory/README.md) 的 [02 格式規則](../../../thinking/2026-11/10/json-memory/02-格式規則.md)、[03 工具](../../../thinking/2026-11/10/json-memory/03-工具.md)。寫入是隔壁的 [memory_write](../memory_write/)；兩支共用 [`memory_fs.py`](../memory_fs.py)。

## 路徑

統一路徑＝`資料夾/檔.json#/JSON Pointer`（RFC 6901：`~1`＝`/`、`~0`＝`~`），檔名帶副檔名。相對從庫根算；空字串或 `/`＝根；其他 `/` 開頭＝檔案系統絕對路徑（讀不限範圍）。**read／ls／find 印出的每條路徑都能直接貼回 `path`**：庫裡的印相對、庫外的印絕對、資料夾後面加 `/`。

## 表（_index）

- 資料夾的表＝它的 `_index.json`，整個檔就是表；JSON 物件的表＝它的 `_index` key。
- 表的 key＝從表的基準走的相對路徑：資料夾表從那個資料夾算（`rules.json`、`cli/`、`../x.json#/k`）；物件表從那個物件算，`/` 分段、key 裡的 `/` 寫 `~1`、`..` 往上一層（跳出檔的根＝回到檔所在的資料夾）、`#` 只能接在檔名後、`/` 開頭＝絕對路徑。
- 格是物件：`_description`（字串）＝說明、`tags`（字串陣列）＝find 的標籤；帶 `$env`（可加 `$path`）＝這格實際指到解出來的路徑（相對就從表的基準算），變數沒設＝那行後面附 `[DirectiveBad …]`，不算錯。
- `"."` 格＝這個地方自己：它的 `_description` 是 read 時印在表前面的簡介。
- 真的在、但表沒列的（`.`、`_` 開頭的不算）列在 `not in index:`。

## 動作

- `read`：資料夾或有 `_index` 的物件＝簡介＋`children:`＋`not in index:`；字串＝原文；其他 JSON（物件沒 `_index`、陣列、數字…）＝縮排 JSON，內容裡的 `$ref`／`$env` 交給 aos-json `--resolve` 解；非 `.json` 檔＝UTF-8 原文，不是 UTF-8＝`binary file, N bytes`。
- `ls`：只印表（資料夾、物件、陣列；陣列沒有表，元素都在 `not in index:`）；對字串等＝`TargetBad`。
- `find`：`query`（不分大小寫）比對名字（最後一段）、說明、字串與文字檔內容；`tag` 比對表那格（或 `"."` 格）的 `tags`；兩個都給要同時符合；範圍＝`path` 底下的樹＋表指到外面的格；不解內容裡的 `$ref`；記走過的（實體路徑, 指標）防繞圈，`$env` 格只跳一次；最多 20 筆。命中在內文（不在印出來的名字或說明裡）＝那行後面附 `[match: 命中那一行]`（最多 160 字、以命中為中心切；11-10 S3：小模型照它挑對節點、常常不用再 read）。
- 輸出超過 `max_bytes`（預設 8000）截斷、附 `[truncated: N more bytes]`。

## 實作

單點讀走 PATH 上的 `aos-json get --follow`（值裡有指示詞再加 `--resolve`）；表讀原文（`$env` 格才留得住）。aos-json 失敗＝它最後一行的代號照圖紙 03 換（`FileMissing`／`PointerMissing`→`NodeMissing`、`SpecBad`→`PathBad`、`FollowMissing`→`TargetBad`，其餘同名），原因照接；PATH 上沒有＝`LaunchFailed`。find 直接用 Python 讀 JSON。

`NodeMissing` 的提示：路徑少了 `.json`（`me/self_tools`、`rules`）而補上會在＝附 `(did you mean me.json#/self_tools? …)`；路上有檔＝提示 `file.json#/key` 寫法；`/` 開頭而拿掉就在庫裡＝提示拿掉 `/`。寫入那支另教「先開資料夾／先開檔」，見 [memory_write](../memory_write/writing.py)。

錯誤代號：`ArgumentsBad`、`OpUnknown`、`PathBad`、`MemoryMissing`、`CfgBad`、`NodeMissing`（附上一層有哪些）、`TargetBad`、`FileBad`、`DirectiveBad`、`ReadFailed`、`LaunchFailed`。
