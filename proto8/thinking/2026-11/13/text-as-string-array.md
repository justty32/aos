# 一段文字可以寫成字串、也可以寫成字串陣列：工具與說明跟上（11-13，線天施工）

← [11-13 README](README.md)｜調度者：頂層 session `repo-aos`｜施工：線天（fable）

## 使用者的話（逐字）

背景：wf-agent 把它的 `wf/` 轉成 json 時遇到「多行文字是一個 json 字串、在檔案裡是一整行，改一個字 git diff 整段換掉」。頂層的建議是「內容拆細為主＋git 比對時展開成文字；行陣列（長文字存成一行一個元素的陣列）先留著」。wf-agent 另外指出資料夾的 `_description.json` 整檔只能是一個字串、沒得拆。

- 「你的建議不錯...我也沒啥想法，跟wf-agent討論一下，總之能做先做」
- 「我會覺得陣列這塊，是可選的。就是說AI可以隨便寫，也可以按照推薦用字串陣列。我們也提供小程式(好像也不用)，讓AI把一個字串展開成字串物件」
- （施工中，調度者轉來）「aos-json get --str不用支援這個」

## 讀法（調度者回給使用者的）

- 一段文字**寫成一個字串或寫成字串陣列都可以**，由寫的人（AI）自己選；多行長文字**推薦**用字串陣列（一行一個元素），不強制；體系的工具兩種都要讀得懂。
- 「把一個字串展開成字串陣列的小程式」他自己說「好像也不用」——不做。
- `aos-json get --str` 不支援字串陣列——不做，維持現況。

## 規則（程式裡的認法，三處同一條）

值是**字串** → 照用。值是**陣列、至少一個元素、每個元素都是字串** → 等於用換行接起來的一段。其他形狀（空陣列、含非字串元素、巢狀陣列、數字…）→ 不是一段文字，照各工具原本「不是字串」的那條路走。

## 改了什麼

| 檔 | 改動 |
|---|---|
| `proto8/lib/aos_index.py` | 新函式 `text()`（上面那條規則）；`line()` 取 `description` 改經它。字串陣列的 description 接起來後照原本「字串裡帶換行」的印法：換行、TAB 換成空白，一項仍是一行。空陣列、含非字串元素：照舊只印鍵。 |
| `wf/tools/index_check.py` | 新函式 `text()`；`check_table()` 的 description 合法條件改成「字串或字串陣列、接起來去掉空白後不是空的」。空陣列、`[""]`、含非字串元素、巢狀陣列、數字、null、空字串都報 `IndexBad … has no description`（句子沒變）。 |
| `wf/tools/index_gen.py` | 新函式 `lines()`；`json_desc()`：物件的 `_description` 是字串陣列時照樣取那段 md 的標題；`description`／`summary`／`$comment`／`title` 是字串陣列時取第一行有字的；檔名是 `_description.json` 時整份（字串或字串陣列）當一段 md 取標題。`desc_of()`：夾的一句話來源在 README.md／INDEX.md／_tooldef.json／_metainfo.json 之後加 `_description.json`。 |
| `proto8/lib/tests/test_index_view.py` | 新例 `test_description_lines`。 |
| `wf/tools/tests/test_index_tools.py` | 新例 `test_text_as_lines`、`test_check_description_lines`。 |
| `proto8/knowledge/docs/02`、`docs/01`、`README.md` | 「一段文字」可以是字串或字串陣列、推薦與理由、出處；「要穩定的名字就用物件、不用陣列」補一句分清楚是講給節點取名。 |
| `proto8/knowledge/aos/tools/index_view.json` | 補「description 可以是字串或字串陣列」與空陣列／含非字串元素時只印鍵（都實測過）。 |

實測（暫存夾，清過環境）：

```text
$ cat kb/_index.json
{"a.json": {"description": ["Rules for mail.", "Read before sending."]}, "b.json": {"description": "One string\nwith a newline"}, "c.json": {"description": []}}
$ index_view {"path":"kb"}
[index] kb/_index.json, 3 entries
a.json	Rules for mail. Read before sending.
b.json	One string with a newline
c.json
```

現有 repo 的 index：`index_gen.py`（檢查）25 份 580 項 0 不一致；`index_check.py` 28 份 662 項 0 problems（改前改後相同；加這份結果檔後 thinking/2026-11/13 的 `_index.json` 重生一列）。

## 沒改的

- **`aos-json get --str`（C++）不做**（使用者「aos-json get --str不用支援這個」）：只認字串；值是字串陣列時報 `aos-json: error: TargetBad … is not a string (it is array)`、退 1。要拿字串陣列就用 `get`（不帶 `--str`）或 `json_get`，拿到的是陣列。
- 「把字串展開成字串陣列的小程式」不做（使用者「好像也不用」）。
- 知識庫現有節點的 `_description` 都是一個字串，沒有改寫成陣列（可選、不強制）。

## 讀取點清單（grep `_description`、`"description"`：proto8 的 lib、cmd、py、templates、kernel，wf/tools，impls 的 C／C++）

**改了的**

- `proto8/lib/aos_index.py` `line()`：index 那一格的 `description`。
- `wf/tools/index_check.py` `check_table()`：同上，形狀檢查。
- `wf/tools/index_gen.py` `json_desc()`、`desc_of()`：`_description` 鍵、`_description.json` 整份、json 檔頭的 description 一族。

**不用改的**

- `json_get`／`json_ls`／`json_search`（`lib/aos_json.py`）：一般的 JSON 工具，不分「一段文字」；實測 `json_get` 原樣印陣列、`json_ls` 照常列鍵、`json_search`（`contains`）命中陣列裡的那一行並印 `…/description/0`。`json_set`／`jsonx_*` 是調度者查實的，這次沒重測。
- `aos_index.py` 其他地方（`checked`／`dig`／`soft`／`link`）：管的是 index 表的形狀與 `index` 路徑，不是一段文字。
- `_description`（節點正文）：aos 的 lib、cmd、py、templates、kernel 與 impls 的 C／C++ **沒有任何程式讀它**（grep 零筆），只有腦用 json 工具讀；唯一當字串取的是 `wf/tools/index_gen.py`（已改）。`index_view` 不顯示資料夾的 `_description`（它只讀 index），沒有要改的路徑。

**只列、沒改的**

- `wf/tools/codemap_gen.py` `json_desc()`（不在領地）：json 檔頭的 `description`／`summary`／`$comment`／`title` 只認字串——寫成字串陣列時那一項落到「設定（鍵：…）」；整份是字串陣列的 json 檔被當成 argv 檔（「argv：\`…\`」）。影響的是 code map 生成冊的那一句；`index_gen` 對 `_description.json` 與 description 一族已在自己這邊先認，不會走到這裡。json 檔頭那句是「一句話」，本來就不該多行，寫成一個字串就沒事。
- 給機器讀的 description，**不在這題範圍、必須是字串**：工具定義 `_tooldef.json`／`_metainfo.json` 的 `description` 與各參數的 `description`（`lib/tool_spec.py` 會驗非空字串；`lib/tool_io.py`、`lib/mcp_freeze.py`、`lib/agent/tools_def/_entry`、`templates/agent-fsm/brain.py` 照字串用）；`_entry` 這類設定檔頭的 `description`、`py/aos_clock_register.py` 的定時信檔、`lib/mcp_server_file.py` 的 server 檔。這些是格式定義，不是知識內容。
- `aos-json get --str`：見上，不做。

## 代定

1. 陣列要「至少一個元素、全是字串」才算一段文字；空陣列不算（`index_view` 只印鍵、`index_check` 報 `IndexBad`）。接起來全是空白的（`[""]`）`index_check` 也報。
2. `index_view` 印字串陣列的 description 時，行與行之間是一個空白（跟字串裡的 `\n` 同一條路）。
3. `index_gen` 對字串陣列的 description 一族取**第一行有字的**；`_description` 取那段 md 的第一個標題（跟字串時同一支 `md_desc`）。
4. `index_gen` 新增兩個來源：`_description.json` 這個檔自己的一句話＝它那段 md 的標題（以前整份是字串時取不到、會報 `DescMissing`）；夾沒有 README.md／INDEX.md／_tooldef.json／_metainfo.json 時取它的 `_description.json`。現有 25 份 index 沒有因此變動。
5. 三處各寫一支小函式（`aos_index.text`、`index_check.text`、`index_gen.lines`），沒有抽共用：`wf/tools` 是純標準庫、不 import `proto8/lib`。
