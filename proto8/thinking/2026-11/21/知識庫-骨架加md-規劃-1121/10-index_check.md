# `index_check` 這次怎麼動：只放寬一條（`index` 欄可指到任何最後讀得出 index 格式的 `檔#/路徑`）、沒有新增；另列四條還會卡到 md 與二次導航的現有規則給使用者審

← [README](README.md)｜從 [02-工具與測試](02-工具與測試.md) 分出來｜原話在 [09](09-使用者原話-續二.md) 第 14～17 句

**為什麼今天 `"index": "xxx.index.json"` 會被擋**：這支是照他 11-12 自己那句寫的——「除了description之外，還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json」（[thinking 11-12 index-link](../../12/index-link.md)）。程式把「另一個 `_index` 或 `_index.json`」照字面做成檢查：指到的整份檔必須叫 `_index.json`，不然就得是某份檔裡的 `_index` 鍵。沒有別的理由。

**他問「不能找到某個 .json、那個 .json 就是符合 index 格式的 json object 嗎」：能。**

- `index_view`：**不用改**。它今天就收任何一份 json 當 index 表（`index` 參數給 `me.index.json`，整份是物件就照表印）；夾的 index 那一行後面印 `index: me.index.json` 也是今天就有的。
- `index_check`：放寬一條，約 15 行＋測試。

**唯一放寬的一條（他第 14～17 句合成一條通則）**：

| | `index` 欄可以指到 |
|---|---|
| 改前 | 只有三種：整份 `_index.json`；某份檔裡的 `_index` 鍵；`_metainfo` 的 index |
| 改後 | **任何一條 `檔#/路徑`，只要它最後指到一個 json 物件**。整份 `.json` 檔（最上層是物件）、上面三種，都是它的特例 |

- 指到的東西要在、讀得出來、是物件，否則 `LinkBad`（這句檢查今天就有，只是原本前面多擋了「必須是那三種位置」）。表裡每一項寫得對不對不預先查（他的「解析失敗再說」）。
- **指進 md 也算**（他第 17 句：「都算，指進md也可以。反正就是最終能符合index格式」）：路徑指到 md 裡「只有一個 json 區塊」的節、而且區塊是物件＝算；指到一節字典式清單（`名字: 一句話`）＝也算，當成 `{名字: {"description": 一句話}}`。所以 `"index": "me.md#/index"` 可以寫。代價：`index_check` 要借用 `mdpath` 讀 md（多約 10 行）。
- 程式上：`is_index_spot` 那個位置限制拿掉，改成「讀得到、是物件」；檔是 `.md` 時經 `mdpath` 讀。約 15 行＋測試。指到檔內 `_index` 鍵時原有的「它列的鍵要在那個物件裡」照查。

**這支現有規則裡還會卡到這次設計的（只列、不改，給他之後審）**：

| 現有規則 | 會卡到什麼 |
|---|---|
| `EntryMissing`：有 `_index.json` 的夾要列出夾裡每一個東西 | `_index.md`、`xxx.index.json` 放進去就要各列一行，夾的 index 會變長 |
| `EntryGone`：鍵寫成 `檔#/位置` 時，把那份檔當 json 讀、看位置在不在 | 鍵寫 `me.md#/某標題`（在夾的 index 裡直接描述 md 的一節）一定被報「不在」，因為它不會讀 md |
| `IndexBad`：每一項必須是 `{"description": "…"}` 物件 | 他最早寫的 `"xxx": "xxx.md"`（一項直接是字串）會被報形狀不對 |
| 整支只認 `_index.json` | 夾的 `_index.md` 它完全不看：不查、也不會因為有它而少報 `EntryMissing` |

這次轉換產出的知識庫不會踩到上面任何一條（不生 `_index.md`、`xxx.index.json`、不寫 `md#/標題` 的鍵），所以動工不用等他審。「哪些頁該是 md」的判準不寫成檢查（第 8 句）。

