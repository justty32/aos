# proto8/lib — aos agent 的函式庫（腦可以叫的工具，收成一份、被引用）

**lib - agent 跑的時候會呼叫的外部函數，收成一份標準版，掛捷徑引用、不複製**

← [proto8](../README.md)｜設計、盤點、代定與遷移清單：[thinking 2026-10-24 工具＝函式庫](../thinking/2026-10-24-tool-lib.md)｜慣例：[P-41、P-25](../CONVENTION/02-題目stack停錯腦.md)、[P-33](../CONVENTION/06-巢狀.md)｜特性：[`_metainfo`](../thinking/2026-10-24-metainfo.md)｜範例 agent：[demo/agent-liv](../demo/README.md)｜測試：`proto8/tests/test_lib.py`

使用者 10-24：「我們在做工具集，這其實挺像是在做函式庫。因爲agent是函數，我們給他的工具就是他在內部自己跑的時候會呼叫的外部函數。既然是這樣，那我們就要把抽象做好，把函數庫做好」——agent 是函數（一個資料夾，C-46、C-68），它 `tools/<名>/` 裡的東西是它內部呼叫的外部函數（C-42、C-61）。這裡把那些外部函數收成一份。

## 分層（每層只依賴下層）

```
demo/agent-*/              最上層：agent 本身（也是函數）
  tools/<名> ─捷徑─▶ lib/<層>/<名>/        引用，不複製（見下「怎麼引用」）
lib/agent/                 高層：裡面是一整隻 agent 的工具（pyfix、小念頭 thought、claude／codex）   ［還沒收，候選見遷移清單］
lib/aos/                   中層：動 aos 自己東西的工具（記憶 heap、寄信、say／listen、spawn／ask／status）［還沒收］
lib/base/                  底層原語：檔案、資料夾、JSON、行程（bash）——只靠 Linux 與 Python 標準庫、只碰 $AOS_WS（10-24 收了 7 個）
impls/                     基礎層與標準庫（C-74）：aos-exec 把工具叫起來，loop／fsm 跑 agent
```

層名只是資料夾名，不進工具名；還沒有工具的層不先建空資料夾（STRUCTURE：不預先建空檔）。

## 一個工具長什麼樣（契約）

一個工具＝一個資料夾程式（C-61、N-50），裡面固定三個檔：

| 檔 | 給誰看 | 內容 |
|---|---|---|
| `_entry` | aos-exec | 可執行檔（python3 純標準庫，或 sh）；第一行 shebang，第二行 `# <名> - 一句話`（C-54 R1） |
| `tool.json` | 模型 | `{"description", "parameters"}`（P-41，OpenAI function 物件去掉 name；工具名＝資料夾名） |
| `_metainfo` | kernel 與人 | JSON，通用 key 照 [`_metainfo` 規劃](../thinking/2026-10-24-metainfo/01-位置與格式.md)：`summary`、`time_ms`、`resource`、`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`；模型看不到（M10） |

規則（`tests/test_lib.py` 檢查形狀、每條都有案例）：

1. **參數**：stdin 一份 JSON 物件（模型的 `arguments` 原樣，P-41）；空 stdin 當 `{}`。key 全小寫底線、單位放字尾（`timeout_s`、`max_bytes`，C-54）；選填的寫預設值在 `tool.json` 的說明裡。
2. **結果**：stdout 整段就是結果（P-41）。文字工具印文字；結構工具（`ls`、`json_*`）印一行 JSON。工具不讀、不轉述自己起的程式的 stderr 以外的東西（C-52）。
3. **錯**：一律 stderr 一行 `工具名: 代號 原因`、退 1（P-21），**同一行也印在 stdout**——stdout 是給腦看的，腦才知道錯在哪。代號照 C-54 四種結尾（`ArgumentsBad`、`WsMissing`、`PathBad`、`FileMissing`、`FileBad`、`ReadFailed`、`WriteFailed`、`MkdirFailed`、`TextMissing`、`TextBad`、`PointerBad`、`PointerMissing`、`CommandFailed`、`LaunchFailed`）。**參數給錯對工具來說也是錯、照樣退 1**；停下等人還是把那行回給腦，是叫它的 agent 自己的決定（agent-dan 停、agent-pip 回給腦），工具不替它決定（C-52、C-53 入口檢查）。被跑的指令自己退非 0 **不是**工具的錯（那是結果，尾巴寫結束碼）。
4. **沙盒＝`$AOS_WS`**：路徑一律從工作區算，解開 `..` 與捷徑後必須還在裡面（`PathBad`）；沒設或不是資料夾＝`WsMissing`。要動別的資料夾，是叫它的人 `aos-exec --ws 那裡 tools/<名>`（C-66 指標＝`AOS_WS`），工具不另收根的參數或環境變數。`bash` 擋不住指令本身跑出去，說明裡寫明。
5. **逾時**：會跑東西的工具一定有逾時（`timeout_s`，預設與上限寫在 `tool.json`），到時整群先 TERM 再 KILL、算 `CommandFailed`；工具自己被外面 TERM（act 格逾時）時先收掉自己起的那一群再走，不留孤兒（P-36）。
6. **寫檔**：先寫 `.` 開頭的暫存檔再改名（N-05）、留住原檔權限；幾處一起改的全有或全無。
7. **上限與漸進展開**：讀最多 2000 行或 50KB、列最多 500 項、JSON 檔最多 4MB；超過就截，並在結果裡說怎麼接著拿（`offset`、`next_offset`、`pointer` 往下一層）。
8. **stack**：工具的 stack＝呼叫者給的小格 `$AOS_STACK/<名>/`（P-17）；base 層是純函數、不用 stack，要跨呼叫留東西的工具（中層以上）才寫那裡。
9. **自成一格**：一個工具資料夾裡的東西只靠自己，不 `import` 隔壁或上層的檔——搬到哪、被捷徑掛到哪都跑得動（C-61「兩份一起搬也不斷」）。同樣的十幾行開頭（讀 stdin、查工作區、報錯）每個工具各留一份；長到第三份一樣的大段再抽成共用庫（STRUCTURE 膨脹即拆）。
10. **命名**：工具名＝資料夾名，一個動詞（`read`、`ls`）或「主題_動詞」（`json_read`、`json_edit`，C-54 主題在前）；縮寫照 [abbr.json](../CONCEPTS/abbr.json)；錯誤代號主詞在前。

## 怎麼引用（不複製）

agent 的 `tools/` 裡放**一條相對捷徑指到庫裡那個工具**，一個工具一條：

```sh
cd proto8/demo/agent-liv/tools && ln -s ../../../lib/base/read read
```

- agent 的程式**一個字不用改**：act 照舊 `aos-exec tools/read`（P-25、P-33，地址零個 `..`）；aos-exec 走進捷徑指到的真資料夾（cwd、`AOS_CF`、`AOS_CD` 都是庫裡的位置，N-57、N-59），brain 照舊從 `tools/*/tool.json` 組 tools 陣列。agent 不知道、也不必知道這個工具是庫的（C-52）。
- **要哪些掛哪些**，自己的工具（真資料夾）跟庫的並存在同一個 `tools/`；同名時自己的贏（一個名字只能有一個東西），這就是覆寫。
- **版本＝git**：庫改了，掛著的 agent 下次跑就是新的；要釘住某一版就複製那個資料夾進自己的 `tools/`（複製＝覆寫＝自己維護）。
- 不選的幾條（比較在 [thinking](../thinking/2026-10-24-tool-lib.md)）：整個 `tools/` 一條捷徑（10-24 agent-pip 的寫法：不能挑、不能混自己的）；`tools.json` 清單（要改範本的 brain、act 兩支）；`_entry` 寫字串轉向（`tool.json` 還是得複製一份）；PATH（C-61 已否決）。
- 代價：只有 Linux 有捷徑（使用者 10-19「先只考慮在linux上」）；repo 外的 agent 要寫絕對路徑；複製 agent 資料夾時要保留捷徑（`cp -a`，不要 `cp -r`／跟著捷徑複製，不然就變成複本）。

## 索引：base（10-24）

| 工具 | 一句話 | 參數 | 回什麼 | 來源 |
|---|---|---|---|---|
| [read](base/read/) | 讀工作區裡一個文字檔，太長從頭截 | `path`、`offset`、`limit` | 內容（不加行號）；被截時尾巴寫從第幾行接著讀 | demo/pi-tools/read |
| [write](base/write/) | 整份寫進一個檔（建或蓋）、上層資料夾自動建 | `path`、`content` | 一行：寫了幾 bytes | demo/pi-tools/write |
| [edit](base/edit/) | 幾處照字面替換，一處不合整個不改 | `path`、`edits[{old_text, new_text}]` | 一行：換了幾處 | demo/pi-tools/edit |
| [bash](base/bash/) | 在工作區用 bash 跑一行指令 | `command`、`timeout_s`（30／300） | stdout＋stderr 合在一起、尾巴寫結束碼；留最後 2000 行／50KB | demo/pi-tools/bash（`timeout` 改名 `timeout_s`） |
| [ls](base/ls/) | 列一個資料夾的子項，一次一頁 | `path`、`offset`、`limit`（100／500）、`hidden` | JSON：`items[{name, type, size, mtime}]`、`next_offset` | 新寫（demo/file-tools/ls 是加料版） |
| [json_read](base/json_read/) | 看一份 JSON 檔的某個位置，大的摺起來 | `path`、`pointer`、`depth`（1／10） | JSON：`value`，物件摺成 `{type, keys}`、陣列 `{type, len}` | 新寫（impls/aos-json 的 peek 是 C++ 版） |
| [json_edit](base/json_edit/) | 照指標改幾個位置，一處不合整份不寫 | `path`、`set{指標: 值}`、`del[指標]` | JSON：改了幾個、頂層 key | 新寫（同 demo/file-tools/json_edit 的形；aos-json 的 set／del 是 C++ 版） |

每個工具的細節看它 `_entry` 開頭的幾行說明與 `tool.json`。

## 範例：demo/agent-liv

agent-dan 的複本（只改錯誤訊息開頭與假腦），`tools/` 裡七條捷徑掛上面七個，加一個自己的 `clock/`（真資料夾，示範並存）；`_metainfo` 寫這隻 agent 的特性。假腦叫一次 `ls`、拿 `total` 答題，證明捷徑掛進來的工具經 aos-exec 跑得動、小格落在 `$AOS_STACK/ls/`。跑法同 agent-dan：`aos-exec --ws <工作區> proto8/demo/agent-liv`（PATH 放好 impls 三支；設 `AOS_BRAIN_URL` 才用真腦）。

## 測試

`python3 -m unittest discover -s proto8/tests -p test_lib.py`：形狀檢查跑過 `lib/` 底下每個工具（三個檔、NAME 行、`tool.json` 與 `_metainfo` 的形、壞 stdin 的錯誤行格式與 stdout 同一行），七個工具各自的行為（截斷、全有或全無、逾時整群停、路徑出不去、沒 `AOS_WS`），agent-liv 經捷徑用庫的工具跑完一題。
