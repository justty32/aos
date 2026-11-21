# `index_check` 這次怎麼動：刪一條（要列出所有東西）、放寬三條（`index` 指到哪、`檔.md#/位置` 的鍵、一項可以是純字串）、多認一處（沒有 `_index.json` 才看 `_index.md`）

← [README](README.md)｜原話在 [09](09-使用者原話-續二.md) 第 14～17 句、[11](11-使用者原話-續三.md) 第 18 句

這支程式（`wf/tools/index_check.py`）查 `_index.json` 跟實際的樹對不對得上。使用者嫌它拖後腿，第 18 句逐條裁了。下面五條是這支**全部**的改動。動工後他又說「index_check感覺是毒瘤，實作的時候拜託整個重寫。」（第 20 句）：所以不是在舊程式上改這五條，而是整支重寫，新版只查四種（`IndexBad`、`EntryGone`、`LinkBad`、`LinkMissing`），內容就是下表「改後」那一欄加上「沒動的」；舊版其餘的一律不帶。交件時另附「新版一共查哪幾條」與「舊版有、新版沒帶的」兩張清單（[12](12-施工紀錄.md)）。

## 逐條改前改後

| # | 規則（代號） | 改前 | 改後 | 他哪一句 |
|---|---|---|---|---|
| 1 | 在但沒列（`EntryMissing`） | 有 `_index.json` 的夾，夾裡每一個東西都要列，漏一個報一個 | **整條刪掉**。index 是視角，可以只列一部分 | 第 18 句「這個規則刪掉」 |
| 2 | 列了但不在（`EntryGone`）裡的 `檔#/位置` 鍵 | 把那份檔當 json 讀；檔是 md 就一定報「不在」 | 檔是 `.md` 時照 md 的尋址規則讀，讀得到就算在 | 第 18 句「xxx.md#/yyy，他也可以當json讀啊」 |
| 3 | 一項的形狀（`IndexBad`） | 每一項必須是物件、帶非空的 `description` | 也可以是**純字串**，那個字串就是 description；也可以是 `{"$ref": …}`（指到別處，不查形狀） | 第 18 句「也可以是純字串……得自己用$ref指向別的地方」 |
| 4 | `index` 欄指到哪（`LinkBad`） | 只能三種：整份 `_index.json`、檔內 `_index` 鍵、`_metainfo` 的 index | 任何一條 `檔#/路徑`，最後讀出來符合 index 格式就行；指進 md 也算（只有 json 區塊的節、字典式清單） | 第 14～17 句 |
| 5 | 夾的 index 是哪一份 | 只認 `_index.json` | 沒有 `_index.json` 才看 `_index.md`（當成字典式清單讀，照同一套查） | 第 18 句 |

沒動的：`EntryGone` 的其他部分（列的檔或夾不在）、`LinkMissing`（子夾自己有 `_index.json`、上一層那一項沒帶 `index`）、`archive/` 不查、警告與結束碼。

第 4 條裡照舊的部分：指到的東西要在、讀得出來、是物件，否則 `LinkBad`；表裡每一項寫得對不對不預先查（他的「解析失敗再說」）。

## 刪掉第 1 條會連帶動到什麼（盤點）

- **`index_gen` 不受影響**：它不靠 `index_check` 補項。程式區的 `_index.json` 是它自己掃磁碟整份重生的，「有沒有漏列」由它自己的比對管（排隊每次交件都跑）。
- **兩個旗標變成沒事做**：`--view`（不查在但沒列）與 `--fs`（在但沒列照磁碟算）只為這條規則存在。預定兩個都拿掉；repo 裡除了這支自己的測試，沒有別處呼叫時帶這兩個旗標（`grep` 過 `wf/`、`proto8/py`、`templates`、`AGENTS.md`）。
- **測試**：`wf/tools/tests/test_index_tools.py`（2 處）、`test_index_check_edges.py`（3 處，另有 6 個呼叫帶 `--fs`／`--view`）要跟著改。
- **寫著「要列出每一個東西」的說明**：`proto8/knowledge/README.md`、`knowledge/docs/01`、`docs/02`（「資料夾的 `_index.json` 要列出夾裡每一個東西」）、`index_check.py` 檔頭。知識庫這三份本來就在這次要改的清單裡，一起改成「可以只列一部分」。
- **後果**：以後知識庫加了一頁、忘了在 `_index.json` 加一項，不會有任何檢查提醒；agent 用 `index_view` 看不到那一頁，要 `ls` 才看得到。
- 順帶：先前擔心的「`_index.md`、`xxx.index.json` 放進夾要各列一行」隨這條一起消失。

## 當初為什麼 `"index": "xxx.index.json"` 會被擋

第 4 條的改前是照他 11-12 那句寫的：「除了description之外，還可以放index，值必須是字串，必須是路徑，指向另一個_index或_index.json」（[thinking 11-12 index-link](../../12/index-link.md)）。程式把「另一個 `_index` 或 `_index.json`」照字面做成檢查，沒有別的理由。

## `index_view` 要跟著改的（不是 `index_check`，放這裡一起看）

- 一項是純字串：今天只印鍵、字不見；改成把字串當 description 印。
- 一項或它的 description 是 `{"$ref": …}`：讀 index 時把 `$ref` 解開再印（這條線對「自己用 `$ref` 指向別的地方」的讀法）。
- 夾沒有 `_index.json` 時讀 `_index.md`；md 頁讀自己的 `# index`。
- `index` 參數給任何一份 json 物件：今天就能讀，不用改。

合計 `index_check` 約 40 行（刪的比加的多）、`index_view` 約 80 行，各加測試。
