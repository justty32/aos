# index 指到下一份 index：每項可放 `index`、檔內 `_index` 可以是路徑字串，相對路徑照 json 與檔案系統同像去算（11-12 晚，家機；已施工）

← [11-12 日索引](README.md) ・ 前情：[index](index.md)（格式、天然位置、未定）、[index-tools](index-tools/README.md)（`index_view`）、[json-tools](json-tools/README.md)（路徑寫法 N-45 `檔#/位置`）

## 使用者原文

> 「對了，我這邊有新的想法：index這邊，現在的_index.json格式是這樣：{xxx:{description:...}, yyy:{...}}，我希望能添加{xxx:{descritipon: ..., index:...}}，就是後面那個obj裏面，除了description之外，還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json。」

> 「還有，json object內的_index這個key，現在他的值是只能json obj，我希望能支援字串，同樣也是路徑，必須指向另一個_index, _index.json。　　不跟着往下走。路徑相對...以_index, _index.json的位置爲準。」

看到「一份表裡兩種起點」（下面舊 L1 造成的出入）後：

> 「這個要用json與檔案系統的同像性去想。如果是在json物件內的，某key的_index，那他就從這個json物件開始算(把這個json物件當成資料夾)。然後如果這個json物件是這個.json檔案的根，那他就等同於這個檔案。」

頂層攤了剩的三題（1. 物件裡能不能直接寫別的檔：甲 維持、要先 `..` 走出去／乙 放寬成看到 `#` 就當檔名；2. C-51「資料夾與 JSON 互通只當工具與思考方式，不進規範」要不要加註：甲 不動／乙 加一句；3. `$ref` 要不要也改成同像：甲 不動、仍從檔所在資料夾算／乙 也改），使用者（11-12 晚）：

> 「1. 甲。2.甲。3.甲，話說ref應該支援#/開頭吧」

（後半句「ref應該支援#/開頭」另做，見 [ref-hash](ref-hash.md)。）

使用者接著問「還是ref有支援$at？」；頂層答 `$at` 10-23 已刪、`$ref` 要帶檔名才收 `#/`，並問 index 路徑要不要跟進收 `#/` 開頭（`#/x`＝從本檔的根算起），使用者：

> 「也跟進吧」

頂層再問資料夾的 `_index.json` 裡寫 `#/x` 算不算數（照字面「本檔」就是那份 `_index.json` 自己），使用者：

> 「算數。然後$ref支援./, ../嗎」

## 決定

- index 的每一項 `{description: …}` 可以再放 `index`（選填）：值必須是字串、必須是路徑，指向另一份 `_index`（檔內）或 `_index.json`。
- JSON 物件裡的 `_index` 鍵，值除了物件也可以是字串：同樣是路徑、指向另一份 `_index`／`_index.json`。
- **不跟著往下走**：兩種路徑工具都只顯示、不自動展開。
- **路徑相對誰＝以那份 `_index`／`_index.json` 所在的位置為準**（index 未定題「路徑相對誰」對這兩種路徑有了答案）。
- **`#/` 開頭也收**（使用者「也跟進吧」）＝這份 index 實際所在的那個 json 檔的根算起的絕對位置，跟寫得多深、起點容器都無關（同 N-45 `{"$ref": "#/a/b"}`，[ref-hash](ref-hash.md)）；資料夾的 `_index.json` 裡寫 `#/x`，本檔＝那份 `_index.json` 自己（使用者「算數。」）。物件裡直接寫 `w.json#/…` 仍不收（第 1 題甲）；只有 `#`、`#` 後不是 `/` 照舊不收。
- **用 json 與檔案系統的同像性去算**：json 物件裡的 `_index`，從這個物件開始算（把物件當成資料夾）；這個物件是檔案的根，就等同於這個檔案。`_index.json` 從它所在的資料夾算（同一條：從裝著它的容器算）。原本的代定 L1（檔內 `_index` 讀成該檔所在的資料夾）**使用者翻案、作廢**。

## 結論（做了什麼）

- 條文：[N-69](../../../docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md) 裡 `index` 的形狀改成 `{名: {"description": …, "index": …}}` 並註明檔內 `_index` 可以是路徑字串；格式細節照 N-69 的指向寫在 [knowledge/docs/01](../../../knowledge/docs/01-樹長怎樣與多庫.md)（一條）、[02](../../../knowledge/docs/02-寫入與節點怎麼寫.md)（一句）、[knowledge/README](../../../knowledge/README.md)（一條）。
- 程式：`lib/aos_index.py` 新增 `home()`（一份 index 的位置 → 裝著它的容器）與 `link()`（從容器一段一段走，相對路徑只在這兩個函數）、`checked()`；項目多一欄 `TAB index: 路徑`；檔內 `_index`（或明講的 `index` 參數指到的那格）是路徑字串時印 `[index link] 位置 points to 路徑 (not followed; to read it: {"index": "路徑"})`，有別層的表時照列、標頭補一句 `(位置 points to 路徑, not followed)`。tooldef、`knowledge/aos/tools/index_view.json`、lib/docs/02 跟上。
- 算法（`link()`）：起點＝容器；在物件裡名字＝往下一個 key、`..`＝外層物件，根物件（＝這個檔）的 `..`＝檔案所在的資料夾；在檔案系統裡照資料夾走；`#/指標` 只能接在檔案系統那邊。印出來是 N-45 完整寫法、可直接當 `index` 參數。

| 寫在哪 | 字面 | 算出來 |
|---|---|---|
| `kb/_index.json` 的一項 | `sub/_index.json` | `kb/sub/_index.json` |
| `kb/_index.json` 的一項 | `data.json#/_index` | `kb/data.json#/_index` |
| `kb/v.json` 根物件的 `_index` | `a/_index` | `kb/v.json#/a/_index` |
| `kb/v.json` 根物件的 `_index` | `../w.json#/_index` | `kb/w.json#/_index` |
| `kb/v.json#/o/p/_index` | `../r/_index` | `kb/v.json#/o/r/_index` |
| `kb/v.json#/o/p/_index` | `../../../x.json#/_index` | `kb/x.json#/_index` |
| `kb/v.json#/o/p/_index` | `#/a/_index` | `kb/v.json#/a/_index`（本檔的根，不從 `/o/p` 算） |
| `kb/_index.json` 的一項 | `#/x` | `kb/_index.json#/x` |
| `kb/_metainfo.json#/index` 的一項 | `#/m/_index` | `kb/_metainfo.json#/m/_index` |
| 主觀 index `kb/v.json#/views` 的一項 | `#/a/_index` | `kb/v.json#/a/_index` |
| 任何地方 | `#`、`#a` | 不是路徑（同 L3） |
| `kb/v.json` 根物件的 `_index` | `w.json#/_index` | 不是路徑（物件裡又寫 `#`）：項目標 `index: bad (…)`；`_index` 本身這樣寫＝`IndexBad` |

- 出廠內容：`knowledge/aos/_index.json` 的 `cli`、`tools`、`packs.json` 三格加 `index`（`cli/_index.json`、`tools/_index.json`、`packs.json#/_index`）。
- 測試：`lib/tests/test_index_view.py` 加 2 支（項目的 `index` 欄、`_index` 是字串）；`#/` 開頭再加 1 支（`test_hash_root`，13 支全過）。
- `#/` 開頭（後來加）：只改 `link()`——字面以 `#/` 開頭就回「`where` 的 `#` 前面那段＋字面」，`home()` 不動；項目寫壞時的提示多一句 `#/a/_index counts from the root of this file`；tooldef、`knowledge/aos/tools/index_view.json`、knowledge/docs/01 各補一句。
- 要重建什麼：沒有；舊的 index 照樣讀得懂（`index` 是選填）。

```
{"path": "knowledge/aos", "key": "cli"}
[index] knowledge/aos/_index.json, 20 entries
cli	Use these shell commands to manage agents, tools and daemon procs.	index: knowledge/aos/cli/_index.json

{"path": "doc.json"}            （doc.json 是 {"_index": "sub/_index", ...}）
[index link] doc.json#/_index points to doc.json#/sub/_index (not followed; to read it: {"index": "doc.json#/sub/_index"})
```

## 代定（可翻）

- L1（作廢）檔內 `_index` 的「位置」讀成該檔所在的資料夾：**使用者翻案**（「這個要用json與檔案系統的同像性去想……」），改照上面「決定」。
- **L2 印出來的是接好的路徑**（工作區相對，N-45 `檔#/指標` 完整寫法，可以直接當 `index` 參數），不印原字面；絕對路徑照用、不整理；`#` 後的指標照字面。
- **L3 「是路徑」只查寫法**：非空字串、有檔名、有 `#` 時後面一定是 `/`（`x.json#` 不收，同 json 工具）；不查指到的東西在不在、名字是不是 `_index`／`_index.json`（工具本來就不查被描述的節點，I2、I6；也讓 `_metainfo.json#/index`、自己的主觀 index 能被指）。
- **L4 壞的只標那一行**：項目的 `index` 不是字串或不是路徑＝那一行印 `index: bad (…)`，其他項照常、退 0（「一處壞掉不該擋住其他好的」）。檔內 `_index` 既不是物件也不是合法路徑字串＝照舊 `IndexBad`（整份 index 壞了，跟原本不是物件同一條）。
- **L5 只做使用者說的兩處**：資料夾的 `_index.json` 整份是字串仍是 `IndexBad`；`_metainfo` 裡的 `index` 是字串照舊當壞的略過。
- **L6 輸出欄位**：第三欄 `index: 路徑`（I13「之後加欄就接在 TAB 後面」）；沒有 description 時第二欄空著（`鍵<TAB><TAB>index: 路徑`）。

- **L7 往外走與進檔**（同像推的；「物件裡不能直接寫 `w.json#/…`、要先 `..` 走出去」**使用者已裁維持**：「1. 甲。」）：根物件＝這個檔，它的 `..`＝檔案所在的資料夾；從物件裡要指到別的檔，先 `..` 走出檔再寫 `檔#/指標`。物件裡的名字一律當 key，不看磁碟上有沒有同名檔；檔案系統那邊的名字一律當資料夾／檔名，進 json 要明寫 `#`（`x.json/a/_index` 是資料夾路徑、不是 `x.json#/a/_index`）。
- **L8 物件裡的段照字面當 JSON Pointer 的 token**：key 裡有 `/` 寫 `~1`、`~` 寫 `~0`（同 json 工具）；空段與 `.` 略過。
- **L9（作廢）`#/…` 開頭（沒寫檔名）仍不收**：**使用者翻案**（「也跟進吧」），改照上面「決定」收 `#/` 開頭。
- **L11 本檔＝`where` 的 `#` 前面那段**：所有住處同一條——`DIR/_index.json` 是它自己（使用者已裁「算數。」）、`DIR/_metainfo.json#/index` 是 `DIR/_metainfo.json`、`FILE#/P/_index` 與 `FILE#/P/_metainfo/index` 是 `FILE`、主觀 index `me.json#/views` 是 `me.json`。
- **L12 `#/`（空指標）也收**：算出 `檔#/`，同 N-45 完整寫法 `x.json#/`。
- **L10 其他住處同一條「從裝著它的容器算」**：容器＝這份表描述的那個節點。`_metainfo` 裡的 index（`DIR/_metainfo.json#/index`、`FILE#/P/_metainfo/index`）＝跟獨立的 `_index.json`／`_index` 同一個容器（`DIR`、`FILE#/P`）；腦明講的主觀 index（`index` 參數，如 `me.json#/views`）＝表所在的上一層（`me.json#/views` → 根物件＝`me.json`；整份 `me/v.json` → 資料夾 `me`）。

## 有出入、給使用者看的

- **已解：一份表裡兩種起點**（舊 L1 時，檔內 `_index` 的鍵相對物件、`index` 路徑卻相對檔案所在資料夾）。改照同像算之後，鍵和 `index` 路徑都從裝著那份 index 的物件起算。剩一點：主觀 index 的鍵相對誰仍是「寫它的 agent 自己知道」（I3），路徑卻照 L10 從表的上一層算，兩者不一定是同一個節點。
- **C-51 寫「資料夾與 JSON 互通只當工具與思考方式，不進規範」**：這次照使用者的話把同像寫進了 index 路徑的算法（knowledge/docs/01；N-69 只說形狀）。**使用者已裁不加註**（「2.甲。」），C-51 不動。
- **跟 N-45 `$ref` 不同**（**使用者已裁 `$ref` 算法不動**：「3.甲」，相對檔名仍從檔所在的資料夾算）：`$ref` 的相對檔名「從寫著它的那份檔所在的資料夾算」，不管它寫在檔內多深；index 的路徑寫在檔內物件時從那個物件算。兩者是不同的東西（`$ref` 是指示詞、index 路徑只顯示），沒有改 N-45。`#/` 開頭現在兩邊同義（都是「本檔的根」），只有相對路徑的算法不一樣。寫法上照 N-45 分得出 `/` 與 `#/`（使用者 11-11「其根就是#/，而檔案系統是/，兩者不同」），同像的只有「怎麼算相對」，兩句對得起來。跟工具參數「相對工作區」也不同，所以 `index_view` 印的是已接好的路徑。
