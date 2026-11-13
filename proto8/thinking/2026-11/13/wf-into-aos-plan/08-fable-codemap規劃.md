# 08 fable code map 規劃（Q14「code map 要搬」）：手寫地圖成 `wf/knowledge/code-map.json`、逐檔表成 `wf/knowledge/code-map/proto8/<頂層夾>.json`、生成器合成 `index_gen.py` 一支；後附隊長細化

← [回入口](../wf-into-aos-plan.md)｜上一份：[07-codemap備料](07-codemap備料.md)｜下一份：無

> 以下到「隊長細化」之前是 fable 交稿原樣（11-13 晚，只讀 [07 備料](07-codemap備料.md)），只拿掉它自己的標題行與最後的「相關檔案」交件說明。它的 Q1～Q5 是本檔自己的題號，跟 [05](05-待裁與衝突.md) 的 Q1～Q14 不同；下面細化與入口檔都改叫 **C1～C5**。

依據只有 `07-codemap備料.md`；備料沒有的事實一律標「待驗」。沒寫檔、沒 commit、沒跑指令。

## 0. 一句話結論

- 手寫地圖變成 `wf/knowledge/code-map.json`，也就是通用版本來就規定的那個位置，把骨架填滿。
- 逐檔表變成 `wf/knowledge/code-map/proto8/<頂層夾>.json`，照資料夾樹巢狀，葉子是檔頭那一句話。
- 生成入口合成一支：`index_gen.py --apply` 一次寫出就地的 `_index.json` 和逐檔表。`codemap_gen.py` 只留「讀檔頭一句」的函式，不再寫 md 冊。
- 門檻 15 不動。大夾靠就地 `_index.json` 導航，「每個檔都查得到」靠逐檔表全列。兩者同一次生成、同一個來源，不會互相打架。

## 1. 目標形狀

### 1.1 放哪、怎麼切

| 東西 | 現在 | 之後 | 誰寫 |
|---|---|---|---|
| 手寫地圖 | `wf/workflows/common/code-map.md`（4.9K） | `wf/knowledge/code-map.json`（一檔，約 5K） | 人手寫 |
| 逐檔表 | `wf/workflows/common/code-map/proto8/*.md`（31 冊、252K） | `wf/knowledge/code-map/proto8/<頂層夾>.json`，一個頂層夾一檔 | 生成，不手改 |
| impls 依賴表 | impls 冊開頭的 md 表 | `impls.json` 的 `deps` 鍵 | 生成 |
| 就地 `_index.json` | 超過 15 個的夾才有（33 份、791 格） | 不變 | 生成 |

- **不併進程式區的 `_index.json`。** 要每個夾都列，就得把程式區門檻降到 0，這違反「index 範圍按 11-12 門檻」，還會在別線正在改的 `lib`、`py`、`cmd`、`impls` 裡多出一堆生成檔。
- **先不切檔。** 一個頂層夾一檔，沒有 `lib-2`、`impls-9` 這種編號冊。
  - 8 KB 上限使用者已裁「只限 md」。
  - json 用 `json_get 檔#/tree/某夾` 只拿一段，檔大不影響讀。
  - 不切就沒有 `$ref` 跳轉、沒有「多一個檔就換冊」的大 diff。
  - 冊數約等於頂層夾數（估 10 上下，待驗），不到 15，這個夾自己不需要 `_index.json`。
  - 之後嫌大再切：按第二層夾各一檔，原位留 `{"$ref": "impls/aos-json.json"}`。這只動生成器。
- **不讓逐檔表跳去就地 index。** 「大夾只留一個指標」會讓搜一個詞要跨兩棵樹。兩邊都是生成物，重複無害。

### 1.2 逐檔表長怎樣

`wf/knowledge/code-map/proto8/lib.json`（示意，句子是假的）：

```json
{
 "description": "proto8/lib 逐檔表。生成物，別手改；來源＝各檔檔頭一句話",
 "generated_by": "wf/tools/index_gen.py",
 "tree": {
  "aos_index.py": "讀 _index.json、算 index 路徑",
  "aos_refpath.py": "$ref 與 index 路徑的共用解析器",
  "agent": {
   "run.py": "高層工具的進入點",
   "tests": {
    "test_run.py": "run 的定向測試"
   }
  }
 }
}
```

`impls.json` 多一個鍵：`"deps": {"aos-json": ["aos-util"], "aos-llm": ["aos-post", "aos-util"]}`。

形狀規則：

| 規則 | 理由 |
|---|---|
| 字串＝檔，物件＝夾 | 不需要額外欄位 |
| 真樹包在 `tree` 底下 | `description`、`deps` 這些鍵不會撞到真檔名（`_entry` 就是真檔名） |
| 照樹巢狀，不用「整條路徑當鍵」 | 路徑當鍵會有 `/`，json 內部尋址要寫 `~1`；巢狀就是 `lib.json#/tree/agent/run.py` |
| 一格一行、鍵排序、不轉義中文 | `rg` 好搜、diff 小、合併衝突少 |
| 一句話是空的就寫 `""`，照舊只 warning | 現有 43 條不擋路 |
| 工具夾三個契約檔照舊併成一列 | 鍵名沿用現在 md 那一列的寫法（待驗：現在寫成什麼） |
| proto8 直接底下的檔放 `proto8.json` | 不必另發明名字 |

掃描範圍、排除清單、每種檔怎麼取一句話全部照現在，這次不改。

### 1.3 手寫地圖長怎樣

`wf/knowledge/code-map.json`（示意）：

```json
{
 "description": "aos 的 code map：先讀這份，再查逐檔表",
 "one_minute": {
  "lib": {"description": "共用 Python 程式庫", "per_file": {"$ref": "code-map/proto8/lib.json"}},
  "impls": {"description": "C++ 各執行檔；依賴鏈見 impls.json 的 deps", "per_file": {"$ref": "code-map/proto8/impls.json"}}
 },
 "headline_rule": "每個檔的檔頭一句話是逐檔表的唯一來源；各語言寫在哪…",
 "lookup": {
  "改 $ref 路徑規則": ["lib/aos_refpath.py", "impls/aos-directive/src/ref.cpp"]
 },
 "truth_order": ["第一優先…", "第二…", "第三…"]
}
```

- `one_minute` 的鍵就是 proto8 頂層夾名。生成器檢查時順便比對：頂層夾有、這裡沒有，就 warning。這樣手寫清單不會悄悄落後。
- `truth_order` 用陣列，因為順序就是內容，而且只整批讀。`lookup` 用鍵，因為會被單獨引用。
- `per_file` 用 `$ref`。待驗：`json_get` 讀整份時會不會把 `$ref` 全部展開。會的話改成純字串路徑。

### 1.4 跟通用版、骨架的關係

| 檔 | 角色 | 這次怎麼動 |
|---|---|---|
| `proto8/knowledge/wf/knowledge/code-map-rules.json`（通用版） | 講規矩：真相層優先序的原則、維護鏈 | 加一小段「逐檔表（選用）：可從檔頭一句話生成，放 `code-map/`，生成不手改」 |
| `wf/skeletons/code-map.json`（骨架） | 空表格 | 加選用鍵 `per_file`、`headline_rule`（待驗：骨架現有哪些鍵，名字要對齊） |
| `wf/knowledge/code-map.json`（本專案） | 填好的那一份 | 新寫，內容從 `code-map.md` 逐段搬 |

生成器本身先不做成通用版，等有第二個專案要用再說。

## 2. 兩支生成器

### 2.1 合一：一個入口、一個讀法

| 項目 | 現在 | 之後 |
|---|---|---|
| 指令 | `codemap_gen.py --apply` 和 `index_gen.py --apply` 各跑一次 | 只跑 `index_gen.py --apply` |
| 讀檔頭一句 | 認法在 codemap_gen，index_gen「照它的認法」 | 不變，`codemap_gen.py` 留作被 import 的函式庫（待驗：現在是 import 還是抄一份；抄的話這次收成一份） |
| 寫 md 冊 | codemap_gen | 取消 |
| 寫逐檔表 json | 沒有 | index_gen，同一次掃描順手寫 |
| 寫就地 `_index.json` | index_gen | 不變 |
| 檢查模式 | 各自退 1 | 一支退 1；逐檔表對不上仍印 `CodemapStale` |
| `codemap_gen.py` 命令列 | 生成器 | 過渡期當薄殼，直接呼叫 index_gen，印一行「已改名」；之後刪 |

- 入口選 index_gen 的理由：它已有範圍設定檔 `index_gen.json`、手寫一句話檔、檢查器 `index_check.py`。逐檔表本質上就是一張不受門檻限制的全量 index。
- 留薄殼的理由：別線正照鐵律 3 的舊指令在跑，薄殼讓他們不用同步改。

### 2.2 門檻 15 與「每個檔都要查得到」

| 需求 | 靠什麼 | 門檻 |
|---|---|---|
| 站在某個大夾裡，想知道這裡有什麼 | 就地 `_index.json`，用 `index_view` | 超過 15 才有（不動） |
| 任何一個檔，一定查得到一句話 | 逐檔表，全列 | 沒有門檻 |
| 兩邊會不會說不一樣 | 同一個來源、同一次執行、同一個檢查 | 不會 |

小夾（15 個以內）沒有就地 index，直接 `ls` 加逐檔表就夠，不需要補。

## 3. 鐵律 3 與維護鏈條文

**鐵律 3（AGENTS.md）改成：**

> commit 前跑 `python3 wf/tools/index_gen.py --apply`。它一次重生程式區的 `_index.json` 與 `wf/knowledge/code-map/` 逐檔表。生成物跟程式同一個 commit；生成物不手改。

**維護鏈（`common/conventions/02`）逐句改：**

| 舊 | 新 |
|---|---|
| 修改前先讀地圖→生成冊 | 修改前先讀 `wf/knowledge/code-map.json`，再用 `json_get` 查 `code-map/proto8/<頂層夾>.json#/tree/<夾>` |
| 檔頭一句話是來源 | 不變 |
| commit 前跑 `codemap_gen.py --apply` | commit 前跑 `index_gen.py --apply`（一支） |
| 生成冊不手改 | `wf/knowledge/code-map/` 底下不手改；`code-map.json` 是手寫的，頂層夾增減時要跟著改 |
| 原始碼不加「對應 code map」註釋 | 不變 |

- AGENTS.md「碰原始碼前」的指標，從 `code-map.md` 改指 `wf/knowledge/code-map.json`。
- `conventions/02` 本身也在「規矩轉 json 節點」的範圍內。本線只改這幾句，整檔轉 json 交給那條線。

## 4. 人與 agent 怎麼讀

| 想做的事 | 用什麼 | 夠不夠 |
|---|---|---|
| 一分鐘看懂 | `json_get wf/knowledge/code-map.json#/one_minute` | 夠 |
| 看某個夾有哪些檔 | `json_get …/lib.json#/tree/agent`，或 `json_ls --depth` | 夠（待驗：`json_ls` 會不會印出值；不印就用 `json_get`） |
| 哪個檔負責某件事 | `json_search`；或 `rg 詞 wf/knowledge/code-map/`（一格一行） | 夠（待驗：`json_search` 能不能一次搜整個夾） |
| 大夾導航 | `index_view` 看就地 `_index.json` | 夠，沒變 |
| 看 diff | 現有 `json_text` textconv | 夠 |
| 人直接打開檔 | 縮排 json，一格一行 | 可讀 |

- 結論：現有工具夠，不做新輔助。
- 已知的小不便：`rg` 命中那行只有檔名、沒有完整路徑。`json_search` 回的位置有路徑；真有人喊痛，再加一支印「路徑 TAB 一句」的小工具。
- `index_view` 不能直接看逐檔表，因為它只認 `{名: {description}}`。這是故意的取捨：換來能用 `#/tree/夾/檔` 尋址。

## 5. 搬遷步驟

每步一個 commit，可單獨進 main、可單獨 revert。先做第 0 步把待驗補齊，這步唯讀、不 commit。

| 步 | 做什麼 | 可觀察的驗收 | revert 影響 |
|---|---|---|---|
| 1 | index_gen 多寫逐檔表 json；md 冊照舊由 codemap_gen 生成。先寫測試再寫程式 | 見下方四條 | 只少掉新 json，舊路照走 |
| 2 | 寫 `wf/knowledge/code-map.json`；`code-map.md` 縮成三行轉址；AGENTS.md「碰原始碼前」改指 json | 每段 `json_get` 讀得出；`index_check` 0 problems；舊 md 每段內容在 json 裡都找得到 | 回到 md 地圖 |
| 3 | 換指令：鐵律 3 與維護鏈改字；`codemap_gen.py` 命令列變薄殼 | 新舊兩個指令跑完工作樹一樣；檢查模式兩個都退 0 | 條文回舊字，指令照舊能跑 |
| 4 | 刪 md 生成冊整夾（含 README 與那份 `_index.json`）、刪寫 md 的程式；修掉連到冊的連結 | repo 內搜 `code-map/proto8/` 的 md 連結 0 筆；`index_check` 0 problems；測試全綠 | 回到 json、md 並存，等於第 3 步的狀態 |
| 5 | 通用版 `code-map-rules.json` 加一段、骨架加選用鍵 | 兩檔讀得出；知識庫測試綠 | 無副作用 |
| 6 | 收尾：批次改 `code-map.md` 的連入連結、刪轉址檔、刪薄殼（等 Q3、Q5 裁） | 搜 `code-map.md`、`codemap_gen` 都 0 筆 | 轉址檔與薄殼回來 |

第 1 步的四條驗收：

- json 的葉子數等於 md 冊的列數（同一次掃描）。
- 每個被掃到的檔在 json 裡恰好出現一次。
- 連跑兩次 `--apply`，第二次沒有 diff。
- 改一個檔頭後跑檢查，退 1 並印 `CodemapStale`。

**連入的 md 連結怎麼處理：**

- 連 `code-map.md` 的（不少，待驗確切數）：第 2 步留轉址檔，連結全部不斷。那些連入的 md 多半本來就排隊要轉 json 節點，等它們轉的時候順手改，不為了改連結另開一輪。第 6 步清掉剩下的。
- 連到生成冊某一冊的（估很少，待驗）：第 4 步同一個 commit 改指對應的 json 檔。
- `conventions.md` 的 34 個連入不在本題範圍，不動。

## 6. 要裁的題、邊緣狀況、撞到的 aos 問題

### 6.1 要使用者裁

| 題 | 選項 | 後果 | 推薦 |
|---|---|---|---|
| Q1 逐檔表放哪 | 甲：集中在 `wf/knowledge/code-map/`，全列 | 一棵樹搜得完；跟就地 index 有重複，但都是生成的 | **甲** |
| | 乙：程式區門檻降到 0，每夾一份 `_index.json`，不要集中冊 | 違反門檻裁定；程式區多出很多生成檔，別線常撞 | |
| | 丙：集中冊遇到已有 index 的夾只留指標 | 沒有重複；查一個詞要跨兩棵樹 | |
| Q2 要不要切檔 | 甲：不切，一個頂層夾一檔 | 檔少、diff 穩；impls 那檔可能幾十 K，要用 `json_get` 讀 | **甲** |
| | 乙：一律切到第二層夾（每個 impl 一檔） | 每檔小；檔數多，要多一份 `_index.json` 和 `$ref` | |
| Q3 生成器 | 甲：合成 `index_gen.py` 一支，舊指令留薄殼一陣子 | 鐵律 3 變一行；別線不用同步改 | **甲** |
| | 乙：兩支都留，codemap_gen 改寫 json | 改動最小；每次 commit 還是跑兩支 | |
| | 丙：合一且立刻刪舊指令 | 最乾淨；別線下一次 commit 會撞牆 | |
| Q4 通用版 | 甲：通用版與骨架加一段「逐檔表選用」，生成器不通用化 | 別的專案知道有這招，但要自己接 | **甲** |
| | 乙：完全不動通用版 | 通用版跟本專案做法對不上 | |
| | 丙：生成器也做成通用工具 | 現在沒人要，白做 | |
| Q5 `code-map.md` 轉址檔留多久 | 甲：留到連入的 md 各自轉 json 時順手改完 | 不另開一輪改連結；轉址檔多活一陣 | **甲** |
| | 乙：第 2 步就一次改完所有連入 | 立刻乾淨；一個 commit 動幾十個檔，容易跟別線衝突 | |

### 6.2 我代定的（不同意再說）

- 一句話空的照舊只 warning，不升成錯誤。
- 檢查失敗的訊息名字 `CodemapStale` 不改。
- 掃描範圍與排除清單不改，只是把寫死在 codemap_gen 裡的排除清單搬進 `index_gen.json` 一個 `codemap` 段，讓範圍設定只在一處。
- 逐檔表不放夾的一句話，只放檔的。夾的一句話在就地 index 與手寫地圖。

### 6.3 邊緣狀況

- 檔名含 `~`：json 內部尋址要寫 `~0`。極少見，不處理，測試留一則記錄行為。
- 夾裡有真檔叫 `description` 或 `deps`：已用 `tree` 包住，不會撞。
- 新增一個 proto8 頂層夾：生成器自動多一檔；手寫地圖沒跟上會 warning。
- 頂層夾被整個刪掉：`--apply` 要把對應的 json 也刪掉，檢查模式要報「多出來的冊」。
- 兩條線同時改程式：生成檔會合併衝突，解法照舊，合併後重跑 `--apply`。
- 別線還在跑舊指令：薄殼接住，結果一樣。
- 逐檔表自己會不會被掃進逐檔表：掃的是 `git ls-files proto8`，`wf/` 應在外面（待驗：`wf/` 確實不在 `proto8/` 底下）。
- `wf/knowledge/` 在不在 index_gen 的範圍、是不是手寫 index（待驗）：是手寫的話，第 1、2 步要手動補 `code-map.json` 與 `code-map/` 兩格。
- 通用版改了以後，活樹上的知識庫副本要等停樹才重抄，跟 11-13 其他線同樣處理。
- 第 1 到第 3 步之間 md 冊與 json 並存：兩邊同一次掃描生成，不會不一致，但 commit 會多帶一份 diff，所以這段要盡快走完。

### 6.4 撞到的 aos 問題（一行一條）

- `index` 欄只能指另一份 index，所以逐檔表掛不進 index 樹，手寫地圖只能用 `$ref` 指過去。
- `index_view` 只認扁平的 `{名: {description}}`，巢狀樹看不了，逐檔表只能靠 `json_get`、`json_ls`。
- json 內部尋址遇到鍵裡有 `/` 要寫 `~1`，「整條路徑當鍵」這種最好搜的形狀因此不好用。
- 門檻 15 讓 index 樹單獨回答不了「每個檔都查得到」，才需要第二份全量表。
- 沒有「搜整個夾的 json」的確定做法（待驗 `json_search`），目前退回 `rg`。
- 讀整份 json 時 `$ref` 會不會被整包展開不明（待驗），這會影響手寫地圖能不能放 `$ref`。
- 同一個「檔頭一句話」的範圍設定分在兩處：`index_gen.json` 和 codemap_gen 寫死的排除清單。
- 43 個 knowledge json 沒有 `description` 鍵，逐檔表裡會是空字串。
- AGENTS.md 把工具指令寫死在鐵律裡，工具一改名所有線都受影響，所以才需要薄殼過渡。
- 通用版知識庫只有「手寫領域表」，沒有「生成逐檔表」這個概念，本專案做法跑在通用版前面。

## 隊長細化（opus，11-13 晚 22:00，家機，唯讀查）

**fable 待驗查到的**：

| 待驗 | 結果 | 影響 |
|---|---|---|
| `wf/knowledge/`、`wf/skeletons/` 在不在 | **repo 裡都不存在**（那是通用版的工作區路徑，本 repo 還沒建過） | 步 2 是第一次建 `wf/knowledge/`；它要在 `index_gen.json` 的範圍或 `hand_indexes` 登記，步 1 同 commit 決定。骨架那條（fable §1.4 第二列）改成只動通用版 `proto8/knowledge/wf/` 底下的骨架，本 repo 不建 `wf/skeletons/` |
| codemap_gen 是被 import 還是抄一份 | `index_gen.py` 已 `import codemap_gen` 共用 `clean`／`json_desc`／`text_desc` | 合一只差「寫出端」：index_gen 多寫逐檔表、codemap_gen 去掉寫 md 冊。比 fable 估的小 |
| 頂層夾幾個 | 生成冊現有 11 種：cases、cmd、extras、feedback、impls、kernel、knowledge、lib、py、root、templates | 11 檔 <15，`code-map/proto8/` 不需要自己的 `_index.json`；`root.md` 那冊照 fable 叫 `proto8.json` |
| 連 `code-map.md` 的檔數 | 71 個（不含 archive、session_logs、thinking） | 支持 C5 甲：留轉址檔，各檔轉 json 時順手改 |
| 連到生成冊某一冊的 md | 15 個：`wf/workflows/common/code-map.md`、`common/conventions/02`，另外 **13 個在 `proto8/impls/*`（12 個 docs、README）與 `proto8/extras/README.md`** | **新衝突**：impls 是線址、線修正在改的範圍，本線不碰。fable 的步 4（刪 md 冊、同 commit 改連結）要等那兩線停手，或把那 13 檔的改字交給它們；步 1～3 不受影響 |
| `json_search` 能不能搜整夾、`json_get` 讀整份會不會展開 `$ref`、`json_ls` 印不印值 | 沒查（要叫 aos 工具實跑，留給步 0） | 步 0 唯讀實跑三樣；`$ref` 會展開就照 fable 改純字串路徑 |

**跟 fable 不同的地方**：只有上表兩處——骨架只動通用版那份；步 4 的連結改字分兩半（wf 的本線改、impls／extras 的交給別線或等停手）。其餘照 fable。

**對到檔名的施工順序**（接在 [04](04-施工分段與驗收.md) 段 5「code map 另成一串」）：

1. 步 0（唯讀）：實跑 `json_search`、`json_get`（含 `$ref`）、`json_ls --depth` 各一次，結果補進本節。
2. 步 1：改 `wf/tools/index_gen.py`、`index_gen.json`（加 `codemap` 段、把 codemap_gen 寫死的排除清單搬過來）、`codemap_gen.py`（只留認法函式）；新產物 `wf/knowledge/code-map/proto8/*.json`（11 檔）。驗收照 fable 四條。
3. 步 2：新 `wf/knowledge/code-map.json`（從 `code-map.md` 逐段搬）；`code-map.md` 縮成轉址；`AGENTS.md`「碰原始碼前」改指 json。
4. 步 3：鐵律 3 改字、`common/conventions/02` 那幾句改字、`codemap_gen.py` 命令列變薄殼。
5. 步 4：刪 `wf/workflows/common/code-map/` 整夾；wf 這邊兩個連入本線改，impls／extras 的 13 個另約。
6. 步 5、6 照 fable。

**要使用者裁的**：C1～C5，fable 推薦全是甲，隊長同意，沒有要另加的題。另有一件要協調、不是要裁的：步 4 碰到 impls／extras 的 13 個連入，等線址、線修收工再做。
