# `$ref` 與 index 路徑改成「`#` 左邊一律檔案系統、右邊一律 json 內部」（線址，11-13 晚，家機）：盤點、新規則表、代定、施工紀錄；Python 與 C++ 都接上、`$at` 刪掉，C++ 執行檔待停樹換。

← [11-13 日索引](README.md) ・ 被廢掉的舊規則：[ref-index-unify](../12/ref-index-unify.md)「定案」、[index-link](../12/index-link.md)、[ref-hash](../12/ref-hash.md)

## 使用者原話（11-13 晚，逐字）

> 「是這樣的，$ref和index路徑這塊，我發現我們錯了，他應該是以#作爲json內部尋址的標示，比如#/aaa，就是根obj的aaa，而#./bbb，就是當前所在的obj的bbb，#../ccc，就是當前所在obj的上一層的ccc。而如果是普通的./zzz.json，那就是當前所在資料夾下的zzz.json，而../xxx.json就是上一層。yyy.json#/kkk，就是當前資料夾下的yyy.json中的kkk這個key。然後yyy.json#./, yyy.json#../都是不允許的。純#aaa和yyy.json#aaa...可以。」

頂層確認三點（1 `#aaa` 等於哪個；2 沒有 `#` 的一律是檔案系統路徑；3 只寫 `#/` 或 `#` 代表整份）後：

> 「1.還是報錯吧，#aaa,yyy.json#aaa都報錯。2.對。3.對」

第一則末句「純#aaa和yyy.json#aaa...可以」被第二則第 1 點改成報錯。

看完這份（盤點＋代定 D1～D9，當時停在件數 gate）後，頂層轉使用者裁定：

> 「都OK。但是$ref這塊，幫我把$at刪掉。然後$ref和index路徑的規則要相同。」

＝放行（含 C++）；D1、D2、D8 照代定；D7 改成**刪掉 `$at`**（不留相容、不留提示）；`$ref` 與 index 路徑同一套規則、同一支解析函式（Python `aos_refpath.spot` 與 C++ `aos::ref_spot` 跑同一張 `lib/tests/ref_path_cases.json`）。

### 「所在物件」兩邊怎麼統一（代定 D10，取代 D1、D2 的寫法）

一句話：**所在物件＝這個路徑字串決定的那個值，它的上一層物件**；`{"$ref": …}` 整個物件算一個值（它就是要被換掉的那一格）。

| 寫在哪 | 那個值 | 所在物件 |
|---|---|---|
| `{"a": {"b": {"$ref": "#./x"}}}` | `/a/b`（指示詞整個） | `/a` → `#./x`＝`/a/x` |
| `$ref` 陣列裡的一個元素 | 同上（陣列是 `$ref` 的值，不算一層） | 同上 |
| 整份檔就是一個指示詞 | 根 | 沒有 → `#./`、`#../` 報錯 |
| 檔內 `FILE#/P/_index` 是字串 | `/P/_index` | `/P`（＝它描述的節點，同 D2） |
| 某項的 `index` 欄 `…/_index/KEY/index` | 那個字串 | `…/_index/KEY`（那一項）；指節點 `P` 底下要寫 `#../../sub/_index` |
| 資料夾 `DIR/_index.json` 某項的 `index` 欄 | `/KEY/index` | `/KEY` |

D1 本來就是這條；D2 原本「各項的 `index` 欄從節點算」跟它差兩層，為了「規則要相同」改成照字面從那一項算（`index_view` 與 `index_check` 已照這條）。實際資料裡沒有任何一項用 `#./`、`#../`，沒有東西要跟著改。

## 新規則（定案）

`#` 左邊一律檔案系統、右邊一律 json 內部。

| 寫法（寫在 `kb/m.json`，所在物件 `/o/p`） | 指到 | 對照表列 |
|---|---|---|
| `x.json`、`./zzz.json`、`../xxx.json`、`sub/x.json`、`sub/`、絕對路徑 | 檔案系統，從這份 json 檔所在的資料夾算：`kb/x.json`、`kb/zzz.json`、`xxx.json`… | 1～8 |
| `q/_index`（沒有 `#`） | `kb/q/_index`（檔案系統，不再往物件裡走） | 6 |
| `#/a/b` | 本檔根起算（RFC 6901）：`kb/m.json#/a/b`；`..` 不特別、是 key 名 | 9～13 |
| `#./b`、`#.`、`#./` | 所在物件起算：`kb/m.json#/o/p/b`、`/o/p` 整個 | 14～18 |
| `#../c`、`#../../c`、`#..`、`#../` | 所在物件上一層起算，可連用：`/o/c`、`/c`、`/o` | 19～24 |
| `#../` 超出根 | 報錯 | 25、26 |
| `#`、`#/` | 本檔整份 | 27、28 |
| `yyy.json#/kkk`、`yyy.json#`、`yyy.json#/` | `kb/yyy.json` 的 `/kkk`、整份、整份 | 29～32 |
| `yyy.json#./…`、`yyy.json#../…` | 報錯 | 33～36 |
| `#aaa`、`yyy.json#aaa`（`#` 後不是 `/`、`./`、`../`） | 報錯 | 37～40 |
| 空字串、不是字串 | 報錯 | 41 |
| 不知道是哪份檔卻寫 `#…`、不知道所在物件卻寫 `#./`／`#../` | 算不出來（另一種錯，呼叫者自己決定怎麼處理） | 42、43 |

對照表 = [`lib/tests/ref_path_cases.json`](../../../lib/tests/ref_path_cases.json)（44 列，每列一個 `rule` 欄寫它是上表哪一條）。

## 舊規則廢掉哪些

proto8 一律當沒有舊版（使用者 11-05）：不寫遷移、不做舊格式相容、不留舊名提示。

- [ref-index-unify](../12/ref-index-unify.md)「定案」表與代定 U1～U5：`#/` 後的 `..` 往外一層、走出根物件到檔所在資料夾（`#/../other.json`、`#/a/../b`＝`#/b`、`x.json#/../y.json`、走出檔後再認一次 `#`）。
- [index-link](../12/index-link.md)：index 路徑「從裝著那份 index 的容器算、json 物件當資料夾走（名字＝下一層 key、`..`＝外層物件、根物件再 `..` 出檔）」「物件裡直接寫 `w.json#/…` 不收」。
- [ref-hash](../12/ref-hash.md) R5：`#/`＝名字是空字串的那個 key（現在 `#/`＝整份）；「`#` 後不是 `/`＝原封不動不報錯」（D15 的那一半；現在報錯）；`x.json#` 不收（現在＝整份）。
- 只動 `$ref`／index 的路徑字串。json 工具與入口的「位置」（`檔#/指標`，N-62，`aos-json`、`json_get`、`index_view` 的 `path` 參數）不在這次範圍：那是「位置」不是「寫在 json 裡的相對路徑」，照舊第一個 `#` 切、`#` 後要 `/`（見代定 D6）。

## 盤點

四隻 sonnet 唯讀盤點（Python 程式、C++、測試、資料與條文），下面是匯總。

### 程式：自己解析的（真正要改的）

| 檔:行 | 現在 | 新規則下 |
|---|---|---|
| `lib/aos_index.py:46-56` `home()`、`:59-115` `link()` | index 路徑：物件當資料夾走、`#` 後 `..` 出檔；C++ `ref_spot` 的 Python 雙胞胎 | 改叫 `aos_refpath.spot`，`home()` 只剩「所在物件」 |
| `lib/aos_index.py:232` | 壞掉時的提示句舉 `sub/_index`、`../a.json#/_index` | 改舉 `#./sub/_index`、`../a.json#/_index` |
| `lib/aos/kernel_llm/packs.py:86-92` `_endpoints()` | 自己 `partition("#")`、`pointer.strip("/")`，`#aaa` 會被放過 | 改叫共用函式 |
| `cmd/aos-grow/bin/aos-grow:205-217` | 搬函式時改寫 `$ref`：空檔名補成來源檔名 | `#./`、`#../` 不能補檔名（會變成報錯的 `檔#./`），要換成 `檔#/絕對指標` |
| `wf/tools/index_check.py:157-163` | 自己切 `#`、`#` 後要 `/` | 照共用函式（`#`、`#/` 合法、`#./`、`#../`） |
| `py/daemon_ctl/table.py:47-52` | daemon state 分檔 `{"$ref": [分檔…]}` 直接 `os.path.join` 開 | 寫出來的永遠是不帶 `#` 的檔名，合新規則，不用改 |
| C++ `impls/aos-directive/src/ref.cpp:111-168` `aos::ref_spot` | `$ref` 的主算法 | 重寫成上表；需要「所在物件」→ `RefBase` 加位置 |
| C++ `aos-directive/src/resolve.cpp` `walk`／`shallow`／`absolute`、`internal.hpp` `base_of`、`ref.cpp` `merge` 的 `dir_of` | 遞迴只帶 `RefBase{dir, file}`，不知道自己在檔裡哪個位置 | 遞迴時一路補 key／index |
| C++ `aos-daemon/src/daemon/procs.cpp:17-57` `abs_refs` | 自己切 `#`，只認 `#/` | 搬進小格前把 `#./`、`#../` 換成 `絕對檔#/絕對指標` |
| C++ `aos-json/src/follow/kind.cpp:18`、`cmd/ref.cpp:36-85` `rebase`、`cmd/check.cpp:88-90` | 用 `ref_spot` 做語法檢查；`ref --move` 自己切 `#` 重算檔名；check 訊息說「原封不動」 | 跟著改 |
| C++ 子樹交給 aos-directive、位置會丟的 4 處：`aos-daemon/src/daemon/adopt.cpp:174`、`aos-exec/src/env/dotenv.cpp:237`（`classify.cpp:128` 給的 `.env`）、`aos-json/src/cmd/read.cpp:36`、`peek.cpp:126` | 只給資料夾＋檔 | 各補一行位置 |
| C++ `impls/aos-directive/src/ref.cpp:171-209` `ref_step`（`$at`） | `$at` 的 `..` 往外、走出根到資料夾 | 使用者沒提，**待裁**（D7） |

C++ 合計約 10～12 個檔、約 20 處（sonnet 估）。

### 程式：只把字串交給 C++ 的（間接）

`lib/directive_value.py:15-62`、`cmd/aos-agent/aos_agent/tools.py:125,146`、`py/aos_clock_register.py:133-139`、`lib/mcp_server_file.py:238`、`lib/hook_run.py:115`：都把一格包成 `{"v": 值}` 交給 `aos-directive --file 檔`。新規則下 `#./`、`#../` 會從這個包裝物件算、不是那一格真正所在的物件——**要改成連位置一起給**（`aos-directive` 多一個旗標，跟 C++ 一起做）。只寫 `#/…` 與檔名的照舊對。

### 不相關（看過、不動）

`lib/mcp_freeze.py`（JSON Schema 的 `$ref`）、`lib/aos_json.py` `Target`、`lib/tool_spec.py:186`、`lib/metainfo.py:55`、`py/daemon_ctl/entry.py:96`、`cmd/aos-tools`、`cmd/aos-mcp-import`、`cmd/aos-agent` 的 `檔#/指標` 位置——都是「位置」（N-62），不是寫在 json 裡的相對路徑。`wf/tools/index_gen.py:209` 寫出的 `index` 欄是不帶 `#` 的 `sub/_index.json`，合新規則。

### 測試

| 檔 | 要改 | 說明 |
|---|---|---|
| `lib/tests/test_index_link.py` | 全檔重寫（約 8 處） | 換成吃新對照表 |
| `lib/tests/test_index_view.py` | 約 20 處 | 物件內相對（`a/_index`、`../r/_index`）改 `#./`、`#../`；「物件裡寫 `w.json#/_index` 是壞的」三條反轉成合法；`#`、`#/` 變整份；提示句 5 處 |
| `impls/aos-directive/tests/ref_spot_cases.json` | 換成 `lib/tests/ref_path_cases.json` | 舊 25 列約一半意思變了 |
| `impls/aos-directive/tests/test_ref_spot.py` | 約 14 處 | `#/../x` 全改；`$at` 出檔 4 處看 D7 |
| `impls/aos-directive/tests/test_ref_hash.py`、`aos-json/tests/test_ref_hash.py` | 各 1 支（`#`、`#a` 原封不動 → 整份／報錯） | |
| `impls/aos-json/tests/test_ref_at.py` | 約 6 處 | |
| 其他 impls 的 `test_ref_hash.py`、其餘測試 | 0 | 只用 `#/a/b`、`x.json#/a` |

### 資料、範本、條文

**實際寫出來的路徑值：0 處要改。** 出廠知識庫與 `lib/_index.json`、`proto8/_index.json` 的 13 個 `$ref`（`me/self_tools.json`、`tidy/principles.json#/principles`…）與 10 個 `index` 欄（`cli/_index.json`、`packs.json#/_index`…）全是不帶 `#` 的檔名或 `檔#/指標`，新舊規則同一個意思；`$at` 0 個；`_index` 是字串的 0 個；範本、`cmd/*` 的 json 0 個；沒有任何 `#/..`。

**講規則的文字要改（只算 `$ref`／index；D6 把 json 工具 `path` 的 13 個 `_tooldef.json` 排除）：**

| 類 | 檔:行 |
|---|---|
| 知識庫與工具說明（json 裡的說明字串） | `knowledge/aos/tools/index_view.json:2`、`lib/base/index_view/_tooldef.json:2`、`knowledge/aos/cli/parts/directive.json:1`、`lib/tests/_index.json:21` |
| N-45 | `docs/NORMS/06-基礎設施-命令列與指示詞.md:11,14,16,19,23`（`:17` `$at` 看 D7） |
| N-62 | `docs/NORMS/10-基礎設施-定義與工作區/05-N-61～N-62.md:10`（`$ref` 與 index 那半句） |
| 條號表、命名、慣例 | `docs/NORMS/附錄1-條號表.md:42`、`docs/NORMS/命名.md:5`、`docs/CONVENTION.md:15` |
| C-88 | `docs/CONCEPTS/05-agent/04-C-88-記憶與index.md:14,15,16`（`:7` 是 json 工具位置，D6 不動） |
| knowledge 文件 | `knowledge/docs/01-樹長怎樣與多庫.md:23,25`、`knowledge/docs/02-寫入與節點怎麼寫.md:6`、`knowledge/README.md:15` |
| lib 文件 | `lib/docs/02-索引-base與索引-aos.md:29` |
| aos-directive | `impls/aos-directive/README.md:5`、`docs/01-用法等.md:14,15,22,26,27,87` |
| aos-json | `impls/aos-json/docs/02-給腦用的兩個工具等.md:15` |
| 「`$ref` 的 `#` 後不是 `/`＝換不了」的錯誤條文 | `impls/docs/03-錯誤.md:21`、`impls/aos-loop/docs/03-元素等.md:35`、`impls/aos-fsm/docs/02-元素等.md:26`、`cmd/aos-sandbox/README.md:42`（逐條看是講 `$ref` 還是講位置，講位置的照 D6 不動） |

合計約 22 個檔、約 35 處。另有 json 工具位置的條文（`json_get.json:3,4`、`lib/docs/02:18`、`aos-llm-kernel/docs/01:26`、`aos-json/docs/01:6`、aos-exec 入口 `docs/01:31`、`05:14`、N-60）照 D6 不動；N-69:20 index 鍵寫 `list/0` 是「鍵」不是路徑，不動。

## 改法

1. **共用解析函式**：Python 一份 `lib/aos_refpath.py` 的 `spot(字串, 檔, 所在物件, 資料夾)` → `(檔案系統路徑, token 串或 None)`；寫法不合丟 `RefPathBad`、算不出來丟 `RefPathUnknown`（都是 `ValueError`），呼叫者換成自己的既有代號（`$ref`＝`DirectiveBad`、index＝`IndexBad`）。C++ 一份重寫 `aos::ref_spot`，簽章多帶位置。兩邊跑同一張 `lib/tests/ref_path_cases.json`（取代 `impls/aos-directive/tests/ref_spot_cases.json`）。**已做（commit d980a950b）。** 舊表 `impls/aos-directive/tests/ref_spot_cases.json` 刪掉。
2. **index（Python）**：`aos_index.link()` 改叫 `spot()`，`home()` 只回所在物件；`wf/tools/index_check.py` 改 import 同一支；改 `test_index_link.py`、`test_index_view.py`、`index_view` 的 `_tooldef.json` 與知識庫 `tools/index_view.json`。
3. **`$ref`（C++）**：照上面盤點改 `ref_spot`、`RefBase` 帶位置、`abs_refs`、aos-json 三處、丟位置的 4 處；`aos-directive` 加旗標讓 Python 給位置；`directive_value.py` 等 5 處 Python 給位置；`packs.py`、`aos-grow` 改叫共用函式。build 在 repo 外，活樹執行檔待停樹換。
4. **資料、條文**：N-45、N-62 半句、knowledge `cli/parts/directive.json`、`knowledge/docs/01` 等照新表改寫，例子換掉。

## 代定（可翻）

- **D1 `$ref` 的「所在物件」＝裝著 `{"$ref": …}` 那一格的物件**（不是指示詞物件自己）。`{"defs": …, "a": {"$ref": "#./defs"}}` 的 `a` 指到 `/defs`。理由：指示詞物件整個會被換掉，從它自己算的 `#./x` 只能指到 `$ref` 的兄弟 key，沒用處；檔案系統那邊 `./zzz.json` 也是從「裝著這份檔的資料夾」算。整份檔就是一個指示詞時沒有所在物件，`#./`、`#../` 報錯。
- **D2 index 的「所在物件」＝那份 index 描述的節點**（同舊 `home()`）：`FILE#/P/_index` 與 `FILE#/P/_metainfo/index` 裡寫的都從 `/P` 算；資料夾的 `_index.json`、`_metainfo.json#/index` 從那份檔的根算。各項的 `index` 欄也從節點算（不從 `_index/KEY` 那一格算）——這樣 `"index": "#./sub/_index"` 指的是節點 `P` 底下的 `sub`。
- **D3 `#./`、`#../` 後面的段照字面**：開頭那串 `.`、`..` 之後才是 token，中間的 `..` 是 key 名（`#../c/../d`＝`/o/c/../d`）。`#/` 後面全照 RFC 6901，`..` 也是 key 名。
- **D4 `#.`、`#..`（不帶尾 `/`）也收**，同 `#./`、`#../`；`#.x`、`#...` 報錯。
- **D5 `#/`＝整份**，所以名字是空字串的根 key 寫不到（`#//x` 是 `""` 底下的 `x`，照 RFC 仍寫得到下一層）。
- **D6 json 工具與入口的「位置」不跟**：`json_get` 等的 `path`、`aos-json` 的引數、`entries` 宣告都是 `檔#/指標`（N-62），照舊 `x.json#` 不收、`x.json#/` 是空字串 key。使用者這次說的是 `$ref` 與 index 路徑。
- ~~D7 `$at` 不動~~ → 使用者裁定**刪掉 `$at`**（見上方「使用者裁定」），不留相容、不留提示。
- **D8 不知道是哪份檔（stdin、信）時 `#/…`**：維持原封不動（C++ 現狀），`#aaa` 這種寫法錯則一律報錯（不看知不知道檔）。
- **D9 錯誤代號沿用**：`$ref`＝`DirectiveBad`、index＝`IndexBad`（項目裡壞的照舊只在那一行標 `bad (…)`），不新增代號。

## 施工紀錄（放行後）

- **index（commit cbadd29a2）**：`lib/aos_index.py` 的 `link()` 叫 `aos_refpath.spot`、`home()` 刪；`wf/tools/index_check.py` 叫同一支；`test_index_link.py` 跑共用表。改 `aos_index.py` 時曾有幾秒存著語法錯的版本（活樹當時若 import 會壞），隨即修好。
- **`$ref`（C++，本 commit）**：`aos::ref_spot` 重寫（`impls/aos-directive/src/ref.cpp`），`RefBase` 帶位置（`at` token 串＋`placed`）、`in(key)`／`in(i)` 往下走；`ref_step`／`ref_at_of`／`$at` 全刪；`aos-directive` 加 `--at POINTER`（要 `--file`，給 stdin 那份在檔裡的位置）。連帶 aos-json（`follow/kind.cpp`、`follow.hpp`、`locate.cpp`、`cmd/check.cpp`、`ref.cpp`、`read.cpp`、`peek.cpp`；`ref --move` 搬走時：指在搬走那格裡面的 `#./`、`#../` 照舊，指在外面的改成 `#/絕對`）、aos-daemon（`procs.cpp` 的 `abs_refs` 帶位置、`#…` 換成「絕對檔#/絕對指標」）、aos-exec（`find/classify.cpp` 的 `.env` 位置）。測試：`aos-directive/tests/test_ref_spot.py` 跑共用表 44 列＋9 支、`test_ref_hash.py` 改；`aos-json/tests/test_ref_at.py` 刪、新 `test_ref_rel.py`（5 支）。**build 只在 repo 外（~/code/ref-1113），活樹執行檔沒換，待停樹換**；換之前活樹的 C++ 還是舊規則。
- **Python 其他**：`lib/aos/kernel_llm/packs.py` 的 `_endpoints()` 改叫 `aos_refpath.spot`（原本自己切 `#`、`#aaa` 會放過）；`cmd/aos-grow/bin/aos-grow` 搬單子時只寫 `#` 的 `$ref` 照新規則算指到哪：指在搬走那格裡面＝`#./`、`#../` 照舊、`#/` 換新位置，指在外面＝`原檔#/絕對指標`（原本一律補檔名，`#./` 補上變成新規則的錯寫法）。
- **`$at` 移除清單**：實際資料（知識庫、範本、設定）用到 `$at` 的 0 處。程式與測試：`impls/aos-directive/{include/aos/directive.hpp, src/main.cpp, src/ref.cpp, tests/test_ref_spot.py}`、`impls/aos-json/{src/follow/follow.hpp, kind.cpp, locate.cpp, tests/test_ref_at.py（整支刪）}`。說明與條文：`docs/NORMS/06`（N-45）、`docs/NORMS/_index.json`、`docs/NORMS/附錄1`、`docs/CONCEPTS/01-設計理念/01-C-01～C-48.md`、`impls/aos-directive/{README.md, docs/01}`、`impls/aos-json/docs/02`、`knowledge/aos/cli/parts/directive.json`、`knowledge/docs/01`。`docs/NORMS/附錄2-各批出處/04-各批原話.md` 是歷史原話，不改。`archive/` 不動。

## 沒做的

- **C++ 執行檔待停樹換**（見上）。
- **活樹知識庫要重抄**：這次改了 `knowledge/` 裡的節點與說明（`aos/cli/parts/directive.json`、`aos/tools/index_view.json`、`docs/01`、`docs/02`、`README.md`），`~/aos-home` 那份是複本，沒動。
- **Python 把一格包成 `{"v": 值}` 交給 aos-directive 的 5 處沒給位置**（`lib/directive_value.py`、`cmd/aos-agent/aos_agent/tools.py`、`py/aos_clock_register.py`、`lib/mcp_server_file.py`、`lib/hook_run.py`）：新 aos-directive 有 `--at`，但活樹的舊執行檔不認這個旗標，現在接上會讓活樹全壞；所以這幾處寫 `#./`、`#../` 目前原封不動（D8 的「不知道位置」）。停樹換完執行檔後再接。
- `adopt.cpp` 只給資料夾、不知道位置，`#./` 原封不動，沒改。
- 保守沒改的說明（判為講「位置」N-62 不是 `$ref`）：`impls/docs/03-錯誤.md:21`、`aos-loop/docs/03`、`aos-fsm/docs/02`、`cmd/aos-sandbox/README.md:44`。
