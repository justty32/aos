# 03 函數屬性 `_metainfo` 與「九軸」

只蒐集事實與差距。標記：【讀到】＝我在檔案裡看到；【推測】＝我推的；【沒找到】。
路徑縮寫：P＝`/home/lorkhan/repo/aos/proto8`，U＝`/home/lorkhan/repo/aos/wf/user/advice`。

## 一、現況

### 1. `_metainfo` 是什麼、放哪、什麼格式

- `_metainfo` 是函數旁邊的一份描述：資料夾裡跟 `_entry` 並列的 `_metainfo.json`，或 JSON 物件裡的 `_metainfo` 鍵（含 `檔.json#/指標` 那個物件）。【讀到】`P/docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md:7-9`、`P/py/aos/metainfo.py:49-76`。
- 格式就是一個 JSON 物件，沒有 schema、沒有必填，全選填，不認得的鍵忽略。【讀到】N-69 同檔第 9 行「內容」；`P/py/aos/metainfo.py:1-5`（「Metadata is a point of view, not a rule」）。
- 壞了＝當沒寫：回 None，加一句英文 note，不擋。【讀到】`P/py/aos/metainfo.py:39-46`。
- 數值格可以寫純數、`{"val":…}`、`{"cal":"公式"}`；`cal` 只認四則加 min/max。【讀到】`P/py/aos/metainfo.py:92-166`。`lua`／`py`／`aos` 求值器：只在條文裡預留，程式沒實作。【讀到】`P/py/aos/metainfo.py:163-165`（不認得的求值器回 None）、N-68（`10-N-68.md` 末段「現在只實作 `cal`」）。

### 2. 「九軸」是哪九個

**repo 裡沒有一份「九軸」的正式清單。** 有兩份來源，列法不同：

甲、使用者 10-11 口述（2.9）舉的六個例子，原文說「例如」，不是九個：【讀到】`P/thinking/2026-10/11/restart/02-河堤後段.md:5-12`
1. 有沒有副作用
2. 冪等性
3. 要不要碰外部檔案
4. 是不是持續性的
5. 有沒有 entry
6. 確定還是不確定（跑 LLM 就是不確定）

乙、同檔第 13 行括弧、與 `P/thinking/2026-10/13/json-path/02-metainfo.md:14` 列的九個名字（轉述自 repo 外的 `~/repo/ai_core/docs/kb/kb-ss/doc_05_axes_metadata.md`，「套到 aos 見 proto7 axes-astra」）：
1. I/O 型態　2. 生命週期　3. 跨呼叫狀態　4. 資源特性　5. 可中斷性　6. 執行保證　7. 組合模式　8. 環境模式　9. 確定性

- 這九個只有名字，**每軸的意思 repo 內沒有定義**。原文在 repo 外；proto7 axes-astra 在 repo 內找不到（`find` 與 grep 都只命中引用它的句子）。【讀到／沒找到】
- 甲乙兩份對不上：甲的「有沒有 entry」，10-13 當時自己寫「對不上九軸哪一軸，沒追」（`json-path/02-metainfo.md:24`）。【讀到】
- 條文：C-13「每個計算任務都有固定的基礎特性（九軸）；其中確定性是任務自己的屬性」、C-14「基礎特性之外，人可以任意附加特性」。【讀到】`P/docs/CONCEPTS/04-kernel.md:9-10`。名詞表只寫「副作用、冪等、碰外部檔案、持續性、有無 entry、確定性……」（`P/docs/CONCEPTS/附錄1-名詞/01-aos到agent.md:30`）。

**實際寫在檔案裡的鍵**（跟上面兩份都不是一一對應）：【讀到】`P/py/aos/tool_spec.py:24-27`、N-69。
| 鍵 | 值 | 對應到九軸名單的哪一軸（我的對照，【推測】） |
|---|---|---|
| `side_effect` | 布林 | 甲 1 |
| `idempotent` | 布林 | 甲 2 |
| `deterministic` | 布林 | 甲 6／乙 9 |
| `interrupt` | `safe`／`unsafe`／`resumable` | 乙 5 可中斷性 |
| `parallel` | 布林 | 沒有明確對應（可能是乙 7 組合模式，不確定） |
| `resource` | 字串或陣列（`cpu`／`llm`／`disk`／`net`…） | 乙 4 資源特性（10-13 說九軸「也包括資源特性」，另算） |
| `arbitrary_exec` | 布林 | 非九軸：11-07 定為 C-14 附加特性（`wf/inbox/done/20261107T1539-aos-b0-DONE.md:30` 「C-13 九軸不動、『能跑任何東西』當 C-14 附加特性」） |
乙的「I/O 型態」「生命週期」「跨呼叫狀態」「組合模式」「環境模式」**沒有對應的鍵**；10-24 明文「先不列通用 key，要用的人自己加」。【讀到】`P/thinking/2026-10/24/metainfo/01-位置與格式.md:64`。

其他鍵：`summary`、`cost`（`token{in,out,cached}`、`counter_calls`、`time_ms`）、`timeout_ms`、`sandbox`、`tooldef`、`index`、`comfort`、`lineage`（後兩者條文有）。【讀到】N-68、N-69。

### 3. 現在填了多少、填了哪些軸

數字來自我對 `P/py`、`P/templates`、`P/frontend` 下 `_metainfo.json` 的實數（`P/lib/` 是 `install.py` 抄出來的副本、被 git 忽略，不重複算）：【讀到，我跑 find＋json 計數】
- 共 **95 份**：`py/tools/base` 32、`py/tools/agent` 30、`py/tools/aos` 21、`templates` 10（agents 8、tools 2）、`frontend/aide-def` 1、`py/aos/apps/sandbox/examples/shell-boxed` 1。
- 鍵出現次數：`summary` 95、`resource` 92、`side_effect` 86、`deterministic` 85、`idempotent` 84、`interrupt` 84、`parallel` 84、`cost` 81、`timeout_ms` 71、`arbitrary_exec` 35、`sandbox` 1、`tooldef` 1。`comfort`、`index`、`lineage` 0。
- 沒有九軸鍵（只有 summary 等）的 8 份全是 agent 範本（`templates/agents/*` 6 份、`start-*/agents/ann` 2 份）。工具（base／agent／aos）基本都填了六個軸鍵。
- 範例：`P/py/tools/aos/jsonx_get/_metainfo.json`（全填、`parallel:true`、`timeout_ms:3000`）；`P/py/tools/agent/fork/_metainfo.json`（`side_effect:true`、`deterministic:false`、`interrupt:"unsafe"`、`timeout_ms:0`）。
- 空的 `_metainfo.json` 0 份。
- 有人寫 `_metainfo` 的另一個來源：新工具由 `tools_def`／`tool_spec.metainfo()` 產，沒給的補保守預設（`resource:cpu`、`side_effect:false`、`idempotent:true`、`deterministic:true`、`interrupt:safe`、`parallel:true`…）。【讀到】`P/py/aos/tool_spec.py:24-27,110-121`。【推測】這表示不少檔的值可能是預設補上、不是設計者逐項判斷的；我沒逐檔查。

### 4. 誰讀它、有沒有程式照它做事

N-69 自己的結論：「kernel 現在不讀」「aos-exec、inst 與指示詞都不讀」。【讀到】N-69 第 7 行（「誰讀、讀了做什麼」）。我 grep 的結果相符：【讀到】
| 讀者 | 讀什麼 | 做什麼 | 證據 |
|---|---|---|---|
| act 格（agent-fsm） | `timeout_ms` | 到了就殺工具 | `P/py/aos/apps/agent_fsm/act.py:150-151` |
| aos-mcp | `timeout_ms` | 逾時殺 | `P/py/aos/apps/mcp/main.py:207-208` |
| aos-mcp | `parallel:false` | 同名工具呼叫排隊 | `P/py/aos/apps/mcp/serve.py:5` |
| aos-mcp | `side_effect`／`idempotent`／`resource` | 換成 MCP 的 readOnlyHint／idempotentHint／openWorldHint（只是提示） | `P/py/aos/apps/mcp/main.py:149-158` |
| shell_report | `arbitrary_exec`、`sandbox` | 報告 shell 帳是 open 還是 boxed | `P/py/tools/aos/shell_report/report.py:75-76` |
| aos-sandbox | `_metainfo.json#/sandbox` | 套沙箱 | `P/py/aos/apps/sandbox/main.py:4` |
| metainfo_check | `cost` | 跟實測比，回 close／off／unclaimed，只報告不寫檔 | `P/py/tools/aos/metainfo_check/README.md:1-15` |
| index_view | `_metainfo.index` | 當天然 index 的底 | `P/py/aos/index.py:32-35,195-252` |
| aos-tools | `tooldef`、整份 metainfo | 與 `_tooldef` 淺合併、`get`／`ls` 帶出 | `P/py/aos/apps/tools/tooldef.py:30,175-206` |
| defs／agent_def check | `summary` | 定義夾要有非空 summary | `P/py/tools/aos/defs/catalog.py:217-219` |
- 因此「真的被程式拿去做事」的軸鍵：`parallel`、`timeout_ms`、`sandbox`、`arbitrary_exec`（有執行或報告效果）；`side_effect`／`idempotent`／`resource` 只轉成 MCP 提示；`deterministic`、`interrupt`、`cost.token` 等我沒找到任何執行端的讀者（`cost.time_ms`、`cost.token.in` 只被 metainfo_check 讀）。【讀到；`deterministic`／`interrupt` 的 grep 在 py、cpp 裡除了寫入端無命中】
- C++ 端（`P/cpp`）grep `metainfo` 無命中。排程（llm kernel、daemon）不讀。【讀到】
- 排程、權限、驗證：沒有任何一處用九軸做排程；`parallel:false` 只在 aos-mcp 層做同名排隊。【讀到】

### 5. 「動態的、相對於檔案屬性」

- 概念上：檔案有 `ls -l` 那排屬性，函數沒有；`_metainfo` 就是函數的那排屬性。【讀到】`P/thinking/2026-10/13/json-path/02-metainfo.md:14`、N-69 第 7 行。
- 實作上：`_metainfo` 是**靜態的 JSON 檔**，設計者寫、跑的時候誰都不改、實測不回寫（量到的寫在量的人自己那邊 `observed.jsonl`）。【讀到】N-69「實測不回寫」。所以「動態」目前只落在概念，檔案本身不隨執行變。【推測：這點與使用者 11-24 說的「動態」有張力，下面差距節再列】

## 二、以前說過什麼（逐字）

- 使用者 10-13（語音）：「檔案空間上的屬性就是檔案、資料夾屬性，那些不用說；時間上的屬性，Linux 本身也有 PID 那些，也是通用屬性。`_metainfo` 更進一步，是在九軸（九個 axis）上的。」；「九個軸是我們在這套體系上提出的概念，用來實施我們的想法，就是後續自我改進的概念。」；「剛剛說的屬性**只有定義**；要不要跑，是那個程式自己的決定，**怎麼決定是它內部的演算法，隨便**。」— `P/thinking/2026-10/13/kernel-agent/01-使用者原文.md:38,46,50`（句子在檔內，行號為近似，逐字以檔為準）
- 使用者 10-13：「我會希望添加一個 _metainfo key，在 inst 格式中。先前有提到說所謂的函數九軸，我們可以在這裡定義。也包括資源特性啥的。」— `P/thinking/2026-10/13/json-path/02-metainfo.md:7`
- 使用者 10-24：「一個函數是用_entry去跑。其特性我想要將其寫到_metainfo，裏面可以存放該函數要跑多久，要喫多少資源這種東西。相關的.json格式也要規劃。然後kernel也可以透過這個，來做參考」— 引自 N-69（`P/docs/NORMS/10-基礎設施-定義與工作區/11-N-69.md:7`）
- 使用者 10-25（由上而下拆資料夾）：「當然，不要忘記_metainfo這東西，每個資料夾都可以在這東西內放入對自己功能的描述，具體可以參考九軸，比如需要使用到agent/LLM的功能，不只有不確定性，也需要消耗token/endpoint資源等，這東西很重要，這是後續對整個資料夾樹進行優化的參考。」「metainfo很重要。裏面除了九軸之外，還可以儲存任意資訊，以galtxt爲例子，可以說這個資料夾函數，在"傲嬌"一方面的臺詞生成上，有good評級。」— `P/thinking/2026-10/25/top-down/01-使用者原文-10-25-逐字.md:6,9`
- 使用者 11-06（「動態對靜態」的出處）：「這個函數屬性，他是相對於檔案屬性的，一個是動態一個是靜態。真要細說的話，那其實可以是維度上的區別，檔案屬性，就好比物體的長寬高，很容易理解，而函數屬性，則描述了時間軸上的區別，乃至於世界線上的區別(機率)。」「屬性這東西，除了客觀也還有主觀。…函數九軸的參照物則是現實公理基礎。」「比如一個用agent產出galgame臺詞的函數，對於我這個臭宅男來說，這個函數的臺詞傲嬌程度就是0.4。並且也不一定要是值，甚至可以是一個字串或json物件，比如"缺乏靈活性"、{"pretty":12, "good":true}。」— `/home/lorkhan/repo/aos/wf/user/advice/20261106.md:49-51`
- 使用者 11-07（evo-A）：「函數九軸是基礎特性，我們是建議不管多簡單或多笨…」（後文被截；全文在 `P/thinking/2026-11/07/kb-ideas/README.md:52`）；同段「不是所有函數設計者都會寫這種估值，所以不能假定永遠都有metainfo，而且我們也不該強迫。」
- 使用者 11-12：「_metainfo這東西，他就是只活在概念與規範中，我們目前是不做單一程式去處理的，我們就是定下來，啊其他工具要不要支援，就看他們自己」「我們就是開了metainfo這個口子，要用不用都可以」（引自 `P/thinking/2026-11/14/aos-brainstorm/01b-蒐集-metainfo-index-與三處佔比.md` §1，原檔 `P/thinking/2026-11/12/metainfo/README.md`）；「當然，全都是觀點，全都是參考用，出事了自行負責。」（N-69）；「_metainfo不算index，_metainfo他是描述自身節點的一個子節點，可以塞任何東西來描述自身…」（N-69）。
- 使用者 11-24 晚（目前這輪）：「在 `_entry` 的基礎上，延伸出函數屬性。這是動態的，相對於檔案屬性。」「最基礎的就是九軸，但也可以隨意設置，也就是 `_metainfo`。」— `U/20261124.md:25-26`（整理版；原話在同檔下半，使用者原文「在此基礎上，延伸出函數屬性，這是動態的，相對於檔案屬性，最基礎的就是九軸，但也可以隨意設置，也就是_metainfo」）
- 「動態／靜態」區分：**有寫過**，在 11-06（上面那條）與 11-14 proc 心智模型發想（`P/thinking/2026-11/14/proc-mental-model/01-opus點子.md:106-118`：「九軸是束的統計量」；盲點「屬性分『定義上的』和『跑出來的』兩種」；是 agent 的發想，使用者標明沒定稿，`README.md:10`）。

### 「從單一資料夾長出子資料夾」「生長型神經網路」以前有沒有寫過

- **「神經網路」「生長型」只出現在 11-24 這份**：我在 `P/docs`、`P/thinking`、`P/knowledge`、`wf/user`、`wf/org`、`wf/workflows` grep「神經網路／生長式／生長型／neural／NEAT」，除了 `U/20261124.md:30` 與其引用外沒命中。【讀到／沒找到】
- 最接近的舊東西，**說法相近、但意思不是同一件事**：
  1. **C-55「函數成長」**：函數也照布局成長那套長，六級：0 內嵌 → 1 同檔另一個鍵 → 2 單檔 → 3 資料夾只有入口 → 4 資料夾加伴隨檔（含 `_metainfo.json`）→ 5 資料夾裡有自己的 loop／fsm、各格是子函數、各自再從第 0 級長。使用者 10-24：「當一個函數太過膨大，或是其特性達到某個點之後，就會將其弄成資料夾，底下是子函數」。— `P/docs/CONCEPTS/01-設計理念/05-續-C-55-函數成長.md:7-8`。原型工具 `aos-grow`（`up --to file|dir`、`down`，`P/py/aos/apps/grow/README.md`），使用者 10-24 說是「嘗試」。【讀到】長的觸發是「太大／被多處叫／有 ≥2 步驟」等訊號，由人或工具判斷、不是學出來的。
  2. **能力三階段**：① `_entry` 跑得動 ② 補 `_metainfo.json` ③ 補 `_tooldef.json`。— 同檔 `:12`。
  3. **10-25 由上而下**：使用者「由人類或LLM，依據該程式的目標，將其切分成幾大塊，然後每大塊就是一個資料夾，在頂層寫一些小程式將其黏合，之後逐步往下，深入每個資料夾再次這樣拆」— `P/thinking/2026-10/25/top-down/01-使用者原文-10-25-逐字.md:6`。這是**先切大塊再往下拆**，方向跟 11-24 的「從單一資料夾逐步長出子資料夾」相近但不是同一句；是否同一條路，我不判斷。
  4. **`wf/STRUCTURE.md` 的「膨脹即拆、四級成長」**：是 **wf 文件**（工作流 md 檔）太大就拆成資料夾，四級是 單檔 → 同名子資料夾 → … 的文件結構整理（`/home/lorkhan/repo/aos/wf/STRUCTURE/03-成長軌跡與統一形式.md:3`、`02-結構整理原則.md`）。**與 `_metainfo` 無關，也不是 11-24 說的「生長」**；只在 C-55 開頭被指為「檔案那邊仍以 STRUCTURE 為唯一出處」，C-55 把同一套規則套到函數上（`05-布局成長與檔案權限.md:5`：「資料夾／檔案與 JSON 物件有同像性（C-51），所以長大的規則同一套」）。所以 STRUCTURE 四級＝C-55 檔案那一半的出處，C-55 六級＝函數那一半；兩者共用「長大就拆」的規則，與 11-24 的「類似生長型神經網路」是否同一條路【沒找到使用者說它們是同一條】。
  5. `P/thinking/2026-10/24/janet-compile.md:29`「長出的子資料夾用相對名字」是編譯 janet 時的邊角，非本題。

## 三、差距（一條一條）

1. **「九軸」沒有定稿的清單。** 兩份名單（六個舉例；九個名字）對不上，十個實際鍵又跟兩份都不齊。證據：二-2 節三份對照；10-13「對不上九軸哪一軸，沒追」。九軸原文與 proto7 axes-astra 不在這個 repo。
2. **九軸有一半只有名字、沒有鍵。** I/O 型態、生命週期、跨呼叫狀態、組合模式、環境模式無通用鍵，10-24 明文「先不列通用 key」。（`01-位置與格式.md:64`）
3. **「動態」與「檔案是靜態 JSON」有落差。** 使用者 11-06、11-24 說函數屬性是動態的、描述時間軸與機率；現行 `_metainfo` 是設計者寫死的一份檔，實測不回寫（N-69）。`observed.jsonl` 與 `metainfo_check` 是分開的「宣稱 vs 實測」兩份。11-14 proc 發想把這叫「定義上的／跑出來的」兩種，未定稿。
4. **使用者說的「也可以隨意設置」已支援，但「主觀屬性」沒有位置。** 11-06 的「傲嬌程度 0.4」類；N-69 只說「主觀的metainfo的位置也不規定」，沒有程式去找。`comfort` 條文有、95 份檔 0 份有寫。
5. **幾乎沒有程式照九軸做事。** 見一-4：排程、kernel 都不讀；真正有效果的只有 `timeout_ms`、`parallel`、`sandbox`、`arbitrary_exec`。`deterministic`、`interrupt` 沒有任何讀者。使用者 10-25 說的「後續對整個資料夾樹進行優化的參考」——找不到對應的優化程式。【沒找到】
6. **C-13 說「每個計算任務都有九軸」，實作上「不強迫寫」。** 條文 N-68「metainfo 不強迫」；agent 範本 8 份沒有任何軸鍵。這是使用者自己裁的（evo-A），列出來只因與 C-13 的「固定」字面不同。
7. **函數 `_metainfo` 與生長的接點只有一句。** C-55 說長成資料夾後「讀資料夾的人只看資料夾裡那份描述檔」、`_entry` 單子裡的 `_metainfo` 鍵「沒有人讀」（N-69）。沒有找到「父函數的屬性由子函數彙總」的實作，只有概念（`P/thinking/2026-10/15/kernel-intercept.md:18` 提到「由子葉彙總」，使用者 11-06 也說「函數屬性自然由子函數決定」）。【沒找到實作】
8. **「生長型神經網路」式的開發模式（11-24）：repo 內無對應設計。** 最近的是 C-55 六級、`aos-grow` 原型（一次只做一件：把一個函數往上長一級或縮回），以及 10-25 由上而下拆。沒有「從單一資料夾自動／逐步長出子資料夾」的流程、判準或工具。【沒找到】使用者 11-24 明說「目前暫時不多說」。

## 四、已知的缺點與沒解的問題

- **值的可信度**：`_metainfo` 全是「宣稱」，N-69 明講不是保證、不是安全邊界；寫錯後果自負。大量檔案的值可能是預設補的（推測，未逐檔驗）。
- **主觀 vs 客觀、誰是參照物**：使用者 11-06 提了概念（九軸參照「現實公理基礎」；主觀要有參照物），repo 內沒有落成規範。
- **函數設計者估值 vs agent 自報**：evo-A 裁「平常只報告；拿估值排程時不準的定義改用他見的中位數」（N-68），中位數機制只在 `metainfo_check` 報告，未接到排程（排程不讀 metainfo）。
- **待裁／待定的錯誤路徑評估**：C-53「kernel 評估納入錯誤路徑」，量法、寫在哪（`_metainfo`？）、拿來做什麼都沒定。`P/docs/NORMS/08-待定/01-待定之一.md:8`。
- **11-12 metainfo-views 的邊角**：agent 在普通資料夾放有 `summary` 的 `_metainfo.json`，在 defs 根下會被當成定義；各工具認不認「指定另一份」不會一致；執行類格（`timeout_ms`、`sandbox`）壞了算不算「觀點壞了」曾列待裁（`P/thinking/2026-11/12/metainfo-views.md` 結論三）。
- **`lua`／`py`／`aos` 公式求值器**：條文預留，程式只做 `cal`。
- **`arbitrary_exec` 的歸類**：它被當 C-14 附加特性、不動九軸，但 35 份檔都填、且被 shell_report 實際用，是現有鍵裡「被執行端讀」最重的一個；它不在九軸名單裡。
- **已有的舊數字不一致**：11-12 文寫「80 份」、11-14 文寫「86 份」，我今天數是 95（見一-3）；各是不同時間、不同範圍。

## 觀察（不是建議）

- 使用者的三個詞在 repo 裡各有一處對應：「函數屬性」＝`_metainfo`、「九軸」＝C-13 與六個鍵、「生長」＝C-55 六級＋aos-grow；但沒有哪份文件把三者放在同一張圖裡講。
- 「九軸」這個詞在條文、名詞表、使用者話裡出現很多次，卻是 repo 裡定義最薄的一個詞（只有名字清單、無逐軸說明）。
