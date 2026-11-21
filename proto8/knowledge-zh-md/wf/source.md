# `knowledge/wf/source.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/wf/source.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

這一庫的內容從哪裡來、哪些沒帶進來。併入的經過與之後每一塊的搬遷紀錄在 aos repo 的 `proto8/thinking/2026-11/13/workflows-into-aos.md`。第 3、4 塊太大，拆在 `source/block-3.json`、`source/block-4.json`，`blocks` 裡原位放 `$ref`。

---

**`#/commit_ids`**

模板 repo 在 2026-11-13 push 前改寫過還沒公開的歷史（把內容裡的帳號名換掉；最後的檔案樹與改寫前逐位元相同），commit 編號全變，舊編號已經拿不到。下面各塊的 `commit` 都是改寫後的新編號。當初搬的時候記的舊編號：第 1 塊 7db19654b2bf0a21c8a940cdab9d442d7ae509d0（現在是 019c91240c1fad9a9d6c870f7493bdf2361c9d56）；第 2 塊 7db5ccc0260aa2c5f0bcb6a931ca5e6960edccb3（現在是 584f3f59f6539cfe3e0d761ba68300c7aa4c4014）、「自 45a27d6 起沒再改」的 45a27d68d02325d5000cf475a363560f5d8775f2（現在是 905c096e61fb603fc114303d6e95e68b23bd58dc）。完整對照在 aos repo 的 `proto8/thinking/2026-11/13/workflows-into-aos.md`。

---

**`#/blocks`**（陣列，4 項）

---

**`#/blocks/0`**（物件，5 個鍵：`block`、`what`、`from`、`carried`、`not_carried`）

**`#/blocks/0/block`**：`1`

**`#/blocks/0/what`**：組織原則

---

**`#/blocks/0/from`**（物件，4 個鍵：`repo`、`commit`、`date`、`paths`）

**`#/blocks/0/from/repo`**：workflows 模板 repo（使用者 2026-11-13：「workflows repo仍在，只是幾乎不再更新」）

**`#/blocks/0/from/commit`**：019c91240c1fad9a9d6c870f7493bdf2361c9d56

**`#/blocks/0/from/date`**：2026-11-13

---

**`#/blocks/0/from/paths`**（原文是字串陣列，5 行）

- wf/knowledge/structure.json
- wf/knowledge/structure/layers.json
- wf/knowledge/structure/nodes.json
- wf/knowledge/structure/tidying.json
- wf/knowledge/structure/repo.json

---

**`#/blocks/0/carried`**（陣列，10 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/blocks/0/carried/i`）

| i | `here` | `from` | `changed` |
|---|---|---|---|
| 0 | wf/layers.json#/layers | structure/layers.json#/layers | 「怎麼看 index」那句拿掉（docs/01 已有）；指到來源 repo 其他檔的路徑改成文字 |
| 1 | wf/layers.json#/skills_vs_memory | structure/layers.json#/skills_vs_memory | 只改路徑寫法 |
| 2 | wf/layers.json#/private_index | structure/layers.json#/index_convention | 只留私有 index；公共 index 指到 docs/01；`source`／`title`／`date` 額外鍵那條沒帶 |
| 3 | wf/layers.json#/logs | structure/layers.json#/logs | 拿掉講來源 repo 自己現況的那段與指到還沒搬的節點的路徑 |
| 4 | wf/nodes.json#/names | structure/nodes.json#/names | `_description`／`_index`／名字用字／統一路徑的定義指到 docs/01、02；只留 wf 多出來的約定 |
| 5 | wf/nodes.json#/workflow_form | structure/nodes.json#/workflow_form | 固定鍵直接列出，不再指到範本節點 |
| 6 | wf/nodes.json#/growth | structure/nodes.json#/growth | 只改路徑寫法 |
| 7 | wf/tidying.json#/split | structure/tidying.json#/split 與 #/data_files | json 與資料夾的數字指到 docs/01、02；8 KB 改成使用者 11-13 的說法（推薦、只限 .md、只限拆檔工作流） |
| 8 | wf/tidying.json#/split_method | structure/tidying.json#/split_method | 數字拿掉 |
| 9 | wf/tidying.json#/archive | structure/tidying.json#/archive | 沒改 |

---

**`#/blocks/0/not_carried`**（陣列，9 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/blocks/0/not_carried/i`）

| i | `what` | `why` |
|---|---|---|
| 0 | structure/nodes.json#/node_shape（節點怎麼寫） | 一段文字＝字串或字串陣列、檔案與 `$ref` 的寫法 docs/02、docs/01 已有；「字串陣列是清單還是多行文字」的判斷規則使用者 11-13 裁不定；「同質記錄一律寫物件陣列」與 docs/02「別人會用路徑指到的放成物件的鍵」說法不同，沒裁；檔案格式（縮排 1 格等）docs 沒有對應條文，沒裁 |
| 1 | structure/layers.json#/md_for_humans（內容一律走 json、只留四個 md） | aos 這邊「哪些檔留 md」還在等使用者裁（C-42 放寬、內容走 json、導航留 md 三句哪句為準）；另外它指到來源 repo 的 `wf-view` |
| 2 | 「路由線三層不管幾項一律建 index」 | 使用者 11-13 裁 docs/01 不補這條例外 |
| 3 | 「程式碼單檔 > 300 行、給人看的 md > 300 行」 | 與使用者 10-09「原型開發階段不設核心行數上限」說法不同，沒裁 |
| 4 | index description「維持一句字串（index_view 還不認陣列形）」 | 過時：docs/01 已寫字串陣列也認 |
| 5 | 「index_check.py 會驗引用走不走得到」與 `wf-view.py` | 使用者 11-13：「檢查工具，wf/的那邊就完全不留」 |
| 6 | index 條目的 `source`（kernel／flavor／project）、筆記的 `title`／`date` 額外鍵 | `source` 是給模板升級對照用的，來源 repo 幾乎不再更新；額外鍵本身 docs/01 已允許 |
| 7 | structure/tidying.json#/data_files（`wf-table/1`、tabledb、> 1 KB 抽資料檔） | 綁來源 repo 的 md 形態與它的工具，等搬到那一塊再說 |
| 8 | structure/repo.json（repo 佈局、試點註記） | 講的是來源 repo 自己 |

---

**`#/blocks/1`**（物件，6 個鍵：`block`、`what`、`from`、`carried`、`not_carried`、`added_here`）

**`#/blocks/1/block`**：`2`

**`#/blocks/1/what`**：工作流節點的骨架、tidy 一組

---

**`#/blocks/1/from`**（物件，5 個鍵：`repo`、`commit`、`note`、`date`、`paths`）

**`#/blocks/1/from/repo`**：workflows 模板 repo

**`#/blocks/1/from/commit`**：584f3f59f6539cfe3e0d761ba68300c7aa4c4014

**`#/blocks/1/from/note`**：這幾份自 905c096e61fb603fc114303d6e95e68b23bd58dc 起沒再改

**`#/blocks/1/from/date`**：2026-11-13

---

**`#/blocks/1/from/paths`**（原文是字串陣列，8 行）

- wf/knowledge/workflow-template.json
- wf/workflows/tidy.json
- wf/workflows/tidy/principles.json
- wf/workflows/tidy/content-trim.json
- wf/workflows/tidy/_description.json
- wf/workflows/tidy-manager-brief.json
- wf/knowledge/content-trim.json
- wf/knowledge/gotchas.json（tidy_ 開頭四段）

---

**`#/blocks/1/carried`**（陣列，7 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/blocks/1/carried/i`）

| i | `here` | `from` | `changed` |
|---|---|---|---|
| 0 | wf/knowledge/workflow-template.json | wf/knowledge/workflow-template.json | `fields` 從物件陣列改成以鍵名為鍵的物件；拿掉 `source` 標法與指到 node_shape 的句子；「同質記錄寫物件陣列」那半句沒帶 |
| 1 | wf/workflows/tidy.json | wf/workflows/tidy.json | 驗收改寫：index 檢查與連結檢查寫成「工作區有工具就跑」；8 KB、300 行、4096 bytes 的硬線拿掉，改成「超過門檻而不拆的寫理由」；盤點指令拿掉來源 repo 的工具路徑；`steps` 改成一行一個元素的編號清單；指到來源 repo 專案記憶的路徑拿掉 |
| 2 | wf/workflows/tidy/principles.json | wf/workflows/tidy/principles.json | 第 4 條的門檻與工具清單改成指到 `wf/tidying.json#/split`；加編號 |
| 3 | wf/workflows/tidy/content-trim.json | wf/workflows/tidy/content-trim.json | 巢狀陣列攤平成一行一個元素；拿掉 index_check 與來源 repo 的 commit 規矩路徑 |
| 4 | wf/workflows/tidy-manager-brief.json | wf/workflows/tidy-manager-brief.json | 驗收那步改成指到 tidy 的 done_when；巢狀陣列攤平；拿掉資料檔契約與 commit 規矩的路徑 |
| 5 | wf/knowledge/content-trim.json | wf/knowledge/content-trim.json | 適用範圍裡來源 repo 的檔名改成通稱；日誌指到 `wf/layers.json#/logs` |
| 6 | wf/knowledge/gotchas.json | wf/knowledge/gotchas.json 的 tidy_archive_move、tidy_split_datafile、tidy_dispatch、tidy_env | 工具名改成通稱；tidy_split_datafile 只帶三條、改名 tidy_split |

---

**`#/blocks/1/not_carried`**（陣列，7 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/blocks/1/not_carried/i`）

| i | `what` | `why` |
|---|---|---|
| 0 | tidy 驗收裡的 `index_check.py … RefBad／IndexWanted`、`wf-lint.sh --strict`、`--self` | 使用者 11-13：「檢查工具，wf/的那邊就完全不留」；aos 的 index 檢查不查節點內容引用（使用者 11-13 對那批題「都按照推薦」） |
| 1 | `.md` > 8192 位元組 → 0、README ≤ 300 行／入口 ≤ 100 行、名冊 ≤ 8192、SESSION-LOG ≤ 4096 位元組 | 8 KB 使用者 11-13 定為推薦值、只限拆檔工作流、只限 .md；行數與 4096 沒有使用者的話支持，沒裁 |
| 2 | A／B 拆法的契約 `data-files.json`、`tabledb.py`、`find_big_lists.py`、`fix_moved_links.py` 的路徑 | 綁來源 repo 的工具與 `wf-table/1`；節點裡改成「工作區有這種工具就用」 |
| 3 | gotchas 的三條：`link_columns`、入口壓在 8192 邊緣、用空行躲 BIGLIST | 綁 `wf-table/1` 與來源 repo 的 lint |
| 4 | gotchas 的 `threshold`、`common` 兩段 | 不在這一塊；等搬 gotchas 工作流那塊再看 |
| 5 | 「push 先問」與指到 `conventions.json#/git` 的句子 | 那是來源 repo 自己的專案記憶；要不要成為通用規則在等使用者裁 |
| 6 | not_when 的「只是骨架版本升級…照上游變動記錄手動套」 | 講的是模板的版本升級，來源 repo 幾乎不再更新 |

---

**`#/blocks/1/added_here`**（陣列，1 項；每項是同一組鍵的小物件，排成表：第 i 列＝`#/blocks/1/added_here/i`）

| i | `here` | `from` | `why` |
|---|---|---|---|
| 0 | wf/workflows/tidy/principles.json 第 6 條（收斂優先於拆檔） | aos repo 自己的 `wf/workflows/tidy/README.md` 第 6 條，模板沒有 | 使用者 2026-11-13 收工待裁頁 W16 選「補進去，知識庫變六條」 |

**`#/blocks/2`**：→ `$ref` `source/block-3.json`（映照版：[source/block-3.md](source/block-3.md)）

**`#/blocks/3`**：→ `$ref` `source/block-4.json`（映照版：[source/block-4.md](source/block-4.md)）
