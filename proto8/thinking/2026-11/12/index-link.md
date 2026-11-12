# index 指到下一份 index：每項可放 `index`、檔內 `_index` 可以是路徑字串（11-12 晚，家機；已施工）

← [11-12 日索引](README.md) ・ 前情：[index](index.md)（格式、天然位置、未定）、[index-tools](index-tools/README.md)（`index_view`）、[json-tools](json-tools/README.md)（路徑寫法 N-45 `檔#/位置`）

## 使用者原文

> 「對了，我這邊有新的想法：index這邊，現在的_index.json格式是這樣：{xxx:{description:...}, yyy:{...}}，我希望能添加{xxx:{descritipon: ..., index:...}}，就是後面那個obj裏面，除了description之外，還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json。」

> 「還有，json object內的_index這個key，現在他的值是只能json obj，我希望能支援字串，同樣也是路徑，必須指向另一個_index, _index.json。　　不跟着往下走。路徑相對...以_index, _index.json的位置爲準。」

## 決定

- index 的每一項 `{description: …}` 可以再放 `index`（選填）：值必須是字串、必須是路徑，指向另一份 `_index`（檔內）或 `_index.json`。
- JSON 物件裡的 `_index` 鍵，值除了物件也可以是字串：同樣是路徑、指向另一份 `_index`／`_index.json`。
- **不跟著往下走**：兩種路徑工具都只顯示、不自動展開。
- **路徑相對誰＝以那份 `_index`／`_index.json` 所在的位置為準**（index 未定題「路徑相對誰」對這兩種路徑有了答案）。

## 結論（做了什麼）

- 條文：[N-69](../../../docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md) 裡 `index` 的形狀改成 `{名: {"description": …, "index": …}}` 並註明檔內 `_index` 可以是路徑字串；格式細節照 N-69 的指向寫在 [knowledge/docs/01](../../../knowledge/docs/01-樹長怎樣與多庫.md)（一條）、[02](../../../knowledge/docs/02-寫入與節點怎麼寫.md)（一句）、[knowledge/README](../../../knowledge/README.md)（一條）。
- 程式：`lib/aos_index.py` 新增 `link()`（相對路徑怎麼接只寫這裡）與 `checked()`；項目多一欄 `TAB index: 路徑`；檔內 `_index`（或明講的 `index` 參數指到的那格）是路徑字串時印 `[index link] 位置 points to 路徑 (not followed; to read it: {"index": "路徑"})`，有別層的表時照列、標頭補一句 `(位置 points to 路徑, not followed)`。tooldef、`knowledge/aos/tools/index_view.json`、lib/docs/02 跟上。
- 出廠內容：`knowledge/aos/_index.json` 的 `cli`、`tools`、`packs.json` 三格加 `index`（`cli/_index.json`、`tools/_index.json`、`packs.json#/_index`）。
- 測試：`lib/tests/test_index_view.py` 加 2 支（項目的 `index` 欄、`_index` 是字串）。
- 要重建什麼：沒有；舊的 index 照樣讀得懂（`index` 是選填）。

```
{"path": "knowledge/aos", "key": "cli"}
[index] knowledge/aos/_index.json, 20 entries
cli	Use these shell commands to manage agents, tools and daemon procs.	index: knowledge/aos/cli/_index.json

{"path": "doc.json"}            （doc.json 是 {"_index": "sub/_index.json", ...}）
[index link] doc.json#/_index points to sub/_index.json (not followed; to read it: {"index": "sub/_index.json"})
```

## 代定（可翻）

- **L1 檔內 `_index` 的「位置」讀成該檔所在的資料夾**（不是檔內那個物件）：`a/b.json` 裡任何深度的 `_index` 寫 `x/_index.json` ＝ `a/x/_index.json`。翻案改 `link()`。
- **L2 印出來的是接好的路徑**（工作區相對，跟 `[index]` 行同一種寫法，可以直接當 `index` 參數），不印原字面；絕對路徑照用；只接 `#` 前的檔名，`#` 後的指標照字面。
- **L3 「是路徑」只查寫法**：非空字串、有檔名、有 `#` 時後面一定是 `/`（`x.json#` 不收，同 json 工具）；不查指到的東西在不在、名字是不是 `_index`／`_index.json`（工具本來就不查被描述的節點，I2、I6；也讓 `_metainfo.json#/index`、自己的主觀 index 能被指）。
- **L4 壞的只標那一行**：項目的 `index` 不是字串或不是路徑＝那一行印 `index: bad (…)`，其他項照常、退 0（「一處壞掉不該擋住其他好的」）。檔內 `_index` 既不是物件也不是合法路徑字串＝照舊 `IndexBad`（整份 index 壞了，跟原本不是物件同一條）。
- **L5 只做使用者說的兩處**：資料夾的 `_index.json` 整份是字串仍是 `IndexBad`；`_metainfo` 裡的 `index` 是字串照舊當壞的略過。
- **L6 輸出欄位**：第三欄 `index: 路徑`（I13「之後加欄就接在 TAB 後面」）；沒有 description 時第二欄空著（`鍵<TAB><TAB>index: 路徑`）。

## 有出入、給使用者看的

- **index 的鍵相對誰（圖紙 I3）**：鍵相對「這份 index 所描述的節點」。資料夾的 `_index.json` 兩者一樣（都是那個夾）；但檔內 `cfg.json#/a/_index` 的鍵（如 `tags/0`）相對物件 `cfg.json#/a`，同一份表裡的 `index` 路徑卻相對 `cfg.json` 所在的資料夾——一份表裡兩種起點。照指示沒有擴大，鍵照舊。
- 新規則跟 [N-45](../../../docs/NORMS/06-基礎設施-命令列與指示詞.md) 的 `$ref`「相對檔名從寫著它的那份檔所在的資料夾算」一致；跟工具參數「相對工作區」不同，所以 `index_view` 印的是已接好的路徑。
