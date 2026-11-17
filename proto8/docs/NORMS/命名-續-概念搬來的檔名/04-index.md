← [回入口 命名-續-概念搬來的檔名](../命名-續-概念搬來的檔名.md)｜段落：index `_index`／`_index.json`、尋址、出廠知識庫｜上一份：[03-agent的固定名](03-agent的固定名.md)｜下一份：—

## index 的名字與格式：`_index`、`_index.json`

- 描述節點的 index：json 物件裡是 `_index` 鍵，資料夾裡是 `_index.json`；格式 `{名: {"description": …}}`，值用物件，以後不只放 description。
- 一項裡除了 `description`、`index` 還想放什麼都可以，後果自負；`index_view` 只讀這兩格，其他鍵不讀、不檢查、不印。
- 陣列與別人的 json 檔塞不進 `_index` 鍵：寫在外面、鍵寫路徑。
- 記憶庫用 JSON 時節點＝`.json` 檔與裡面的 key、表＝`_index`，形狀見 [json-memory](../../../thinking/2026-11/10/json-memory/README.md)；用 JSON 是推薦，別的格式不禁止（C-42）。
- index 也可以寫進 `_metainfo`（見 [01 `_metainfo`](01-入口-metainfo-介面-血緣.md#_metainfo節點描述自己的抽屜)、[N-69](../10-基礎設施-定義與工作區/11-N-69.md)）。

（無條號，從 [C-88](../../CONCEPTS/05-agent/04-C-88-記憶與index.md)、[C-42](../../CONCEPTS/05-agent/01-續-C-42/02-知識庫與生子.md) 搬來；[thinking index](../../../thinking/2026-11/12/index.md)。）原話：使用者「description和index是可以合起來的，或者說，本來就該合起來，統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。」；11-12 晚「_index的obj內要不要再多塞東西...可以，想塞啥塞啥，出事了自己負責。」；寫在外面：「2,3的確如此」；JSON 是推薦：使用者 11-13「推薦都用json，我們做的東西也盡量以json為主。這是推薦，不遵守也沒差」，再選「rd-C42:B」（[裁定落地-1113](../../../thinking/2026-11/13/裁定落地-1113.md)）。

## index 指到下一份 index、路徑寫法

- 每項除了 description 還可以放 `index`，json 物件裡的 `_index` 鍵也可以是字串；兩者都必須是路徑、指向另一份 `_index`／`_index.json`，工具只顯示、不跟著往下走。
- 路徑寫法跟 `$ref` 同一套：`#` 左邊是檔案系統路徑，從這份 json 檔所在的資料夾算（`_index.json` 從它的資料夾）；右邊是這份 json 內部（見 N-45）。檔內 `_index` 字串的所在物件＝裝著它的那個物件；某一項的 `index` 欄的所在物件＝那一項（`_index/KEY`）。物件裡可以直接寫 `w.json#/…`。
- `#/` 開頭＝從這份 index 所在的那個 json 檔的根算，跟寫得多深無關；資料夾的 `_index.json` 裡寫 `#/x`，本檔就是那份 `_index.json`。`#./b` 從所在物件算、`#../c` 從上一層算（可連用）；`#` 與 `#/` 是整份；`#aaa`、`y.json#./b` 壞（`IndexBad`，項目裡壞的只在那一行標 `bad (…)`）。
- `#` 右邊照 JSON Pointer 寫（`~1`、`~0`）；`_metainfo` 裡的 index 與腦明講的主觀 index 照同一套，本檔＝那份 index 所在位置 `#` 前面那段。
- 這條同像只管 index 的路徑；`$ref` 的相對檔名仍從寫著它的檔所在的資料夾算（N-45）。

（無條號，從 [C-88](../../CONCEPTS/05-agent/04-C-88-記憶與index.md) 搬來；規範旁：[N-45](../06-基礎設施-命令列與指示詞.md)；[index-link](../../../thinking/2026-11/12/index-link.md)、[ref-path-rules](../../../thinking/2026-11/13/ref-path-rules.md)。）原話：使用者 11-12 晚「json object內的_index這個key，現在他的值是只能json obj，我希望能支援字串，同樣也是路徑，必須指向另一個_index, _index.json。　　不跟着往下走。路徑相對...以_index, _index.json的位置爲準。」；11-13 晚「$ref和index路徑的規則要相同」；`#/` 開頭「也跟進吧」、資料夾的 `_index.json`「算數。」；`$ref` 相對檔名「3.甲」。

## 一條路徑尋址：`aaa.json#/xxx/yyy`

- 檔案系統與 json 用同一條路徑，`aaa.json#/xxx/yyy`＝aaa.json 節點下 xxx 底下的 yyy；檔案系統的根是 `/`，json 檔的根是 `#/`。
- 寫法照 RFC 6901（N-45）：整份檔寫 `aaa.json`，`aaa.json#/` 是名字為空字串的 key；`aaa.json#` 不收（`#` 後一定接 `/`，[N-62](../10-基礎設施-定義與工作區/05-N-61～N-62.md)）。

（無條號，從 [C-88](../../CONCEPTS/05-agent/04-C-88-記憶與index.md) 搬來；規範旁：N-45、N-62。）原話四：「我們用一條路徑來統一檔案系統與json的尋址，如aaa.json#/xxx/yyy，檔案系統的根目錄是/，.json檔案的根(也就是整份檔案)則是#/。」；使用者「原來$ref用的是標準寫法。那我們還是按照標準寫法好了。」

## 出廠的知識庫 `proto8/knowledge/`

- 出廠的 `proto8/knowledge/` 是一般的資料夾＋json，agent 怎麼知道它在哪不管；沒有 knowledge 工具。

（無條號，從 [C-88](../../CONCEPTS/05-agent/04-C-88-記憶與index.md) 搬來。）原話：「knowledge沒用了，可以拿掉。」「4.不管。」（[knowledge-removal](../../../thinking/2026-11/12/knowledge-removal.md)）
