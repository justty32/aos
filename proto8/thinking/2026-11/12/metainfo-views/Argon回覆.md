# metainfo-views 送 Argon 的提示與回覆原文（11-12 晚）

← [metainfo-views](../metainfo-views.md)

照 [aos-teams/05](../../../../../wf/workflows/dispatch/aos-teams/05-同機session與Argon.md) 用 `agy`（Gemini 4 Argon High、plan 模式）送出；下面兩段原樣照抄、沒改寫（是 Argon 的意見，不是使用者的）。

## 送去的提示

```text
你是 Argon，aos 專案的共同設計者（不只審稿，也提案）。請用繁體中文、白話、短。不要工具、不要讀檔，所需內容都在下面。輸出分兩段：(A) 審查——我的整理哪裡錯、漏、邊緣狀況沒想到；(B) 提案——你自己的看法與整理法。大方向是使用者的：不要拿另一套大方向取代他的，方向題只擺選項與後果。限 900 字內。

# 背景（aos：「資料夾＝程式」的 AI agent 體系）
- 節點＝資料夾或 json 物件。函數（工具、agent 定義）是一個夾，`_entry` 是入口。
- `_metainfo.json`（或 json 物件裡的 `_metainfo` 鍵）＝函數的那排屬性，設計者寫、放在定義旁邊。現有 80 份，用到的鍵：`summary`、九軸宣告（`resource`、`side_effect`、`idempotent`、`deterministic`、`interrupt`、`parallel`）、`cost`（估的 token／次數／時間）、`timeout_ms`（到了就殺，act 格與 aos-mcp 照它執行）、`arbitrary_exec`、`sandbox`（沙箱設定）、`comfort`（AI 用起來順不順，含按評分者分的 `ai_by`）。今天新開口子：`tooldef`（給腦看的工具說明＋參數 schema）與 `index` 也可以寫在裡面。
- 既有條文 N-68：`cost` 是「函數設計者宣稱、估的」；agent 跑的時候「自報」的估值分開記；實測寫在另一本帳 `observed.jsonl`（他見），不回寫 `_metainfo`；排程時被評為不準的宣稱改用實測中位數。
- aos-mcp 把 `side_effect`／`idempotent` 轉成 MCP 的 readOnlyHint／idempotentHint；shell 帳看 `arbitrary_exec` 與有沒有 `sandbox`。
- 每隻 agent 有自己的工具登記檔 `tools.json`，可 `$override` 定義那份（只記差異、後面贏），登記格現在可帶 `path`、`env`、`env_file`，不帶 tooldef／metainfo。

# 今天使用者為 index 定的那套（原話）
- 「yyy這個節點的值客觀上可能是任何json value…而description，就是讓agent能在主觀上對yyy這個節點(含其值)有所理解」
- 「description和index是可以合起來的…統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。…天然位置…在沒有指定位置的時候，agent如果想要了解某個節點的狀況，就會去看其上方節點的index。」
- 「放在天然位置的index，其實會是所謂的客觀index，而agent自己存的則是主觀。」
- 「我們就是訂下index是這樣，客觀index是這樣，agent自己要記錄自己的主觀的東西，就自己想想要放哪，我們不規定。…index…主要用途，一個是agent可能會有自己的看法(cache)(或是agent們的通用看法，天然位置)，另一個是當節點下的某些東西太龐大了，所以用index給他做一個簡介。」
- 「_index.json/_index本身是agent想要看到的對於該節點的，自己的視角(天然位置的話就是適用於各agent的通用視角)。如果想要真正客觀，那就乖乖用shell ls或是aos json ls。…或許可以這樣說，_metainfo就是一個天然的，蒐集那些同節點下散落的(aos體系中的)各種_*」
- 「改通用視角這塊就是有權限就能改，不用明講，風險自己承擔。看的時候可以自己指定要用啥index，沒指定的話就預設用通用視角。」「指定的那一份有的，會覆蓋掉天然那份。」
- index 過時怎麼辦：未定。

# 今天對 `_metainfo` 已裁的
- 「_metainfo…只活在概念與規範中，我們目前是不做單一程式去處理的…其他工具要不要支援，就看他們自己」
- 裡外都認：先讀 `_metainfo` 裡的 `tooldef`／`index`，再讀獨立的 `_tooldef`／`_index`，合併，「外面獨立出來的會覆蓋掉_metainfo內的」。
- 「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」（但讀 timeout／cost 的 `lib/metainfo.read` 遇壞檔現在報 FileBad 擋下，待裁：維持還是也略過。）
- 「description 寫進 _metainfo <- 先不寫入。只有{}的_metainfo.json也算agent定義。」

# 這題（使用者 11-12 晚原話）
「然後是metainfo這東西，就是說，還是今天thinking中所說的，客觀，通用觀點，主觀那套index/description，metainfo其實也是一樣，去想想。」

# 我（fable 隊長）的初步整理
1. 三層：客觀＝東西本身（index：`ls`／`json_ls`；函數：實際怎麼跑＝程式本身＋實測帳 observed）。通用觀點＝天然位置那份，大家共用、有權限就能改、沒指定就看它（index：上一層的 `_index`；函數：定義旁邊那份 `_metainfo.json`，設計者寫）。主觀＝某個 agent／讀者自己的看法，放哪不規定、看的時候自己指定、指定的蓋過天然的（函數：agent 自報估值、呼叫者自己想等多久、評分者的 comfort）。
   ——所以 `_metainfo` 整份本來就不是客觀，是「宣稱」；N-68 的「設計者宣稱／agent 自報／他見」其實早就是這三層。套得很順。
2. 不順的只有一類欄位：`timeout_ms`、`sandbox`（以及被拿去決定要不要問人的 `side_effect`）不是「描述」而是「被程式照著執行的規則」。主觀覆蓋它們有安全與預算後果：自己把 timeout 寫長＝卡死不被殺；把 cost 自報寫小＝騙過額度閘門；把 sandbox 拿掉＝出沙箱；把 side_effect 寫 false＝騙過批准。但注意：今天已裁「改通用那份有權限就能改、風險自負」，所以就算不准主觀覆蓋，有寫權限的 agent 改定義旁那份一樣做得到——真正的防線是檔案權限，不是這條規則。
3. 誰贏：現有三條——同一節點內「獨立檔贏 `_metainfo` 裡的」；跨層「讀者指定的贏天然的」；N-68「排程時實測贏不準的宣稱」。前兩條可排成一線（`_metainfo` 裡 < 獨立檔 < 讀者指定），第三條是客觀贏觀點，方向不同但不衝突。
4. `_index` 與 `_metainfo`：方向不同——`_metainfo` 是節點講自己（放在節點裡），index 是上一層講孩子（放在上一層）。index 一項的值是物件（「以後不只會有純文字description」），所以看得到三種整理法：
   甲「只換說法」：現況不動，條文補一段三層讀法；主觀 metainfo 不規定、沒有程式讀。
   乙「index 的一項＝別人對那個節點的 metainfo」：`_index.json: {"mul": {"description": "…", "timeout_ms": 2000}}`；上一層替「裝不下 `_metainfo` 的節點」（可執行檔、陣列、別人的 json）講；agent 的主觀 metainfo 就是它自己那份 index 裡的那一項，不用新格式。要不要讀看各工具。
   丙「主觀寫進 agent 自己的工具登記檔」：`tools.json` 登記格多帶 `metainfo`／`tooldef` 差異，沿用現成的 `$override` 後面贏。
5. 壞掉：觀點類（index、description、summary）壞了略過；執行類（timeout、sandbox）壞了該不該擋，是那題待裁的另一種說法——「觀點壞了略過、規則壞了擋下」或「全都只是參考、壞了用預設」。
6. fork／subagent／封存：通用那份跟著定義夾走；主觀那份「不規定放哪」，放 agent 自己夾裡就跟著 fork 抄走，但鍵裡指到的路徑若是絕對路徑會指回舊樹；subagent 不繼承父的主觀。
7. `{}` 也算定義：`_metainfo.json` 在不在是客觀記號，內容才是觀點；agent 在普通夾放一份只為寫 summary 的 `_metainfo.json` 會被當成定義。

請審查並提案。特別想聽：執行類欄位准不准主觀覆蓋（選項與後果）、乙丙哪個代價小、我漏掉的邊緣狀況。
```

## Argon 回覆原文

```text
### (A) 審查：錯、漏、邊緣狀況

1. **錯把檔案權限當防線（第2點）**：多數 agent 對公用工具夾「唯讀」、對自己的主觀檔「可寫」。若准許用主觀檔蓋掉 `sandbox`／`side_effect`，唯讀 agent 不必改公用檔就能自己脫沙箱、跳過批准。檔案權限擋不住「拿主觀設定當執法依據」的洞。
2. **錯把 `observed` 當絕對客觀（第1點）**：客觀本體只有 `_entry` 實作與當下執行；`observed.jsonl` 是「過去的統計（他見）」。一旦工具改版或輸入規模大變，舊實測一樣會過時，跟 index 過時是同一件事。
3. **漏分「讀者」與「執法者」**：看 index 時，讀者就是 agent 自己；但跑函數時，有「大腦（讀 `tooldef`／`comfort` 選工具）」與「執法者 `act`／`aos-mcp`（看 `sandbox`／`timeout` 管執行）」。大腦讀主觀沒事，執法者若聽呼叫者自備的主觀規則就會破功。
4. **漏排「父講子 vs 子講自己」的優先序（第3、4點）**：若採乙案，父夾 `A/_index.json` 的 `{"B": {...}}` 與子夾 `A/B/_metainfo.json` 都是天然位置，撞鍵時誰贏？
5. **漏想的邊緣狀況**：
   - **收納盒與定義記號打架（第7點）**：既說 `_metainfo` 收納同節點的 `_*`（含 `index`），又說「有 `{}` 的 `_metainfo.json` 就算定義」——那普通資料夾把 `_index` 收進 `_metainfo.json` 就會被誤認成函數／agent。
   - **`comfort.ai_by` 的定位**：它是塞在通用檔裡的主觀集合，三層拉開後留不留？
   - **覆蓋粒度**：主觀蓋 `sandbox`／`tooldef` 若只做淺合併或整塊洗掉，改半套參數會弄壞結構。

---

### (B) 提案：整理法與選項

1. **三層與優先序整理**：
   - **客觀**：節點與 `_entry` 本體。**通用**：節點內 `_metainfo`（自述）＋父節點 `_index`（他述）。**主觀／他見**：agent 自存看法與 `observed` 實測帳。
   - **同節點優先序**：`父天然 _index[子] < 子 _metainfo 內鍵 < 子獨立 _xxx < 指定的主觀`（子自述比父簡介貼身，除非父是替裝不下 `_metainfo` 的節點代講）。

2. **方向題一：執行類欄位（`timeout`、`sandbox`、`side_effect`）准不准主觀覆蓋？**
   - **選項1（不准）**：`act`／`aos-mcp` 只認定義旁的通用檔；主觀只給大腦看。**後果**：最單純，但呼叫方連「這次只想等 3 秒」都不能靠它收緊。
   - **選項2（單向收緊）**：主觀只能比通用更嚴（`timeout` 取小、`sandbox` 不准拔、`side_effect` 只能 false 改 true）。**後果**：安全且能自設護欄，但 `metainfo.read` 要寫比大小規則。
   - **選項3（全准，但由父／宿主指定）**：只有發起呼叫的宿主能指定讀哪份主觀檔，被跑者無權指定。**後果**：概念最統一，但執行介面要多傳視角參數。

3. **方向題二：乙 vs 丙與壞檔處理**
   - **選乙（掛在 `_index`）、不選丙（`tools.json`）**：`tools.json` 只能記已掛載工具，管不到未掛載工具、動態發現的節點或外部執行檔；`_index` 本來就是「對某節點的主觀理解」，把 `summary`、`comfort`、`cost` 當作 `description` 的同級鍵放進去，零新格式、也不用新查找規則（各工具要讀再讀，保住甲案的低成本）。
   - **壞檔分流**：觀點類（`index_view`）壞了略過；執法類（`act` 讀 `timeout`／`sandbox`）壞了維持 `FileBad` 擋下，否則沙箱壞檔就變裸奔。
   - **定義判準**：改看有無 `_entry`（或特定鍵），別光看 `_metainfo.json` 存不存在，普通夾才能安心用 `_metainfo` 收納 `index`。
```
