# 單一路徑尋址與 aos index：現況、舊話、差距、缺點

蒐集日 11-24，只讀 repo。標記：【讀到】＝親眼看到檔案內容或跑了唯讀工具；【推測】＝我的推論；【沒找到】＝查過沒有。
路徑除非特別說，都是相對 `/home/lorkhan/repo/aos/` 的。

## 一、現況

### 1.1 單一路徑是什麼

「單一路徑」＝ `FILE#/POINTER`，一整串字：`#` 左邊是檔案系統路徑，右邊是 JSON 內部的位置（RFC 6901 指標，用 `/` 接，`~1` 代表 `/`、`~0` 代表 `~`）。

- 【讀到】json_* 與 jsonx_* 每支工具的 `path` 就是這一整串；只給 FILE＝整份；`FILE#` 不收（`SpecBad`）；`FILE#/` 是空字串 key。`proto8/knowledge/aos/tools/json_get.md`「JSON tools: the path」一節（約第 22–28 行）。
- 【讀到】解析集中在兩支純標準庫的函式：`proto8/py/aos/refpath.py:25`（`spot()`，`$ref` 與 index 共用）；C++ 那邊是 `aos-directive` 的 `aos::ref_spot`，兩邊跑同一張對照表 `proto8/py/tests/ref_path_cases.json`（見 `refpath.py:8`）。
- 【讀到】`#` 之後的三種寫法（`refpath.py:34-39`）：`#/a/b` 從本檔根起算；`#./b` 從「寫著這串字的物件」起算；`#../c` 從上一層起算。`yyy.json#./x`、`#aaa`、`yyy.json#aaa` 一律報錯（`RefPathBad`，`refpath.py:56-64`）。
- 【讀到】`#` 左邊是檔案系統：`x.json`、`./x.json`、`../x.json`、`sub/`、絕對路徑都行（`refpath.py:36`）。
- 【讀到】知識庫入口 `proto8/knowledge/aos/_description.md` 第 22 行寫了「`aos/me.md#/What is in your stack` 是那標題底下的一節」，把這套寫法教給 agent；第 20 行規則 4「Paths are relative to your workspace unless a tool says otherwise」。

### 1.2 同一套寫法也能進 markdown

- 【讀到】json_get／json_ls／json_len／json_search／json_multi_get 讀 `.md`：`FILE.md#/標題`、`/標題/_`（自己的內文）、`/標題/0`（清單第幾項）、`/標題/鍵`（`鍵: 值` 清單）、`/標題/2/0`（表格列欄）、只有一個 ```json 區塊的標題就當 JSON 往下走。規則在 `proto8/knowledge/aos/tools/json_get.md`「JSON tools: reading markdown」，實作在 `proto8/py/aos/mdpath.py`（406 行；檔頭 `mdpath.py:3-9` 引了使用者 11-21 的原話）；C++ 對應 `aos-directive/src/md.cpp`。
- 【讀到】**只讀、不寫**：json 工具不寫 md，改 md 用 `edit`／`write`（`json_get.md` 同節）。
- 【讀到】`$ref` 也能指進 md（`aos-directive` README 第 9 行）。
- 我實測（用 aos_sub 的工具）：`json_ls proto8/knowledge/aos/me.md` 列出 4 個標題；`json_get …/me.md#/Who am I/_` 回 3629 字元那段（超過 max_bytes 就回 `[too big]`）。【讀到】

### 1.3 index 體系：格式規則

- 【讀到】三種天然位置，且「index 放哪」只寫在一個函式：`proto8/py/aos/index.py:31-35`（`spot()`）。資料夾 `DIR` → `DIR/_index.json`（外加 `DIR/_metainfo.json#/index`）；整份 JSON `FILE` → `FILE#/_index`；JSON 內物件 → `FILE#/PTR/_index`。兩處都有時 `_metainfo` 裡的為底、`_index` 疊上去（同鍵 `_index` 贏）（`index.py:7`；`proto8/knowledge/aos/tools/index_view.md` 第一個項目）。
- 【讀到】md 的天然位置：資料夾沒有 `_index.json` 才看 `_index.md`；一份 md 或其中一節，在標題 `_index`（沒有才 `index`）底下的清單（`index.py:15`、`index.py:149-157`；`index_view.md`「Markdown」項）。
- 【讀到】一項的形狀：`{"description": "…"}`、純字串（＝description）、`{"$ref": 路徑}`；description 可以是字串陣列（一行一個元素）；一項可再帶 `index: 路徑` 指到另一份 index，`index_view` 只顯示不往下讀（`index_view.md` 同段；`proto8/knowledge/docs/03-md頁與尋址.md`「index 的寫法」）。
- 【讀到】index 是「視角不是事實」：不查節點在不在、不附型別大小、不往上找、鍵照字面（`proto8/py/docs/02-索引-base與索引-aos.md` 的 index_view 列；`index_view.md` 開頭）。不必列全（`proto8/knowledge/docs/03-md頁與尋址.md`「不必列出夾裡每一個東西」）。
- 【讀到】description 的另一個位置 `_description`：md 的 `# _description` 節（優先）或 `# description` 節，取內文第一行（`wf/tools/index_gen.py` 檔頭第 25–28 行）；知識庫各夾有 `_description.md`（例 `proto8/knowledge/aos/_description.md`，也就是入口）。我數到 git 追蹤的 `_description` 檔約 32 份（含 `knowledge-zh-md` 的映照）。
- 【讀到】description 規定「用英文、一句話」（`proto8/knowledge/README.md` 「想知道某個節點是什麼」項）；`wf/` 這側的 index 內容是繁中。

### 1.4 誰生成、誰讀、誰查

- 生成：【讀到】`wf/tools/index_gen.py`（檔頭 1–40 行）從各檔檔頭一句話、README、`_tooldef.json` 等**整份重生**程式區與文件區的 `_index.json`（也生 code map）。門檻：夾裡直接的東西超過 15 個才放（`wf/tools/index_gen.json` 的 `more_than: 15`）。使用者的 `wf/user` 不放；`proto8/knowledge` 不在範圍，**手寫維護**。鐵律 3 規定各線不自己跑、由 commit-request 排隊跑（`AGENTS.md:40`）。
- 讀：【讀到】`index_view` 工具（`proto8/py/aos/index.py`，388 行，Python）；AGENTS.md 第 11–12 行要求先看知識庫與 `wf/` 都走 `index_view`。使用者專屬區、`wf/inbox` 沒 index。
- 查：【讀到】`wf/tools/index_check.py`，11-21 整支重寫、只剩四種檢查（`IndexBad`／`EntryGone`／`LinkBad`／`LinkMissing`），已**不要求列全**（`proto8/thinking/2026-11/21/知識庫-骨架加md-規劃-1121/10-index_check.md`）。`wf/workflows/common/user.md` 第 12 行：index_check「不是必跑」。
- 另一個讀的人：【讀到】`aos-directive`（`$ref` 與 index 的 `index` 欄共用同一套路徑規則；`refpath.py` 檔頭）。

### 1.5 覆蓋率（我用 `git ls-files -z` 數的）

- 【讀到】git 追蹤的資料夾 959 個；含 `_index.json` 的 66 個；直接子項超過 15 的夾 72 個；其中**沒有 `_index.json` 的只剩 6 個**：`proto8/knowledge-zh-md/aos`、`…/aos/cli`、`…/aos/tools`、`…/wf/workflows`（這四個有 `_index.md`，所以算有）、`proto8/py/packs`（設定檔明列不放）、`wf/inbox/done`（設定檔明列不放）。
- 【讀到】超過 15 項才放，所以其餘約 890 個資料夾（≤15 項）**刻意沒有** index（`index_gen.json` 的門檻；`proto8/knowledge/README.md`：「如果夠小，……直接讀就是了」）。
- 【讀到】`_index.md` 當資料夾 index 只有 4 份，全在 `knowledge-zh-md/`；md 頁自己的 `# _index` 標題我沒統計（【沒找到】數字）。
- 【推測】依門檻看，「大夾」覆蓋接近全，但「每個資料夾都有」遠遠不到——這是設計，不是漏。

### 1.6 親身走一遍

用 aos_sub 的唯讀工具：

- `index_view wf` → 17 項，一行一項「名 TAB 一句話」，有 index 的夾多一欄 `index: …`。順。【讀到】
- `index_view …/knowledge/aos/packs.md` → 讀的是 md 內部 `#/_index`（`[index] …/packs.md#/_index, 18 entries`），分頁尾巴 `[more] …`。【讀到】
- `index_view …/knowledge/aos/me.md` → `[no index]`，退 0，提示改用 `ls`／`json_ls`。【讀到】

### 1.7 「同一套路徑」實際覆蓋的範圍

統一的：
- json_get／ls／len／search／multi_get／set／add／del／multi_*（含 jsonx_* 共 18 支，`proto8/py/tools/base/*`、`tools/aos/jsonx_*`；每支 `_tooldef.json` 都寫 `FILE#/POINTER`），`index_view`（`path`、`index` 欄），`$ref`（`aos-directive`），`aos-json` 命令列。【讀到】
- 這些的 `.md` 讀取、index 的 `index` 欄、`$ref` 共用 `refpath.spot()`。【讀到】

**沒統一的**（逐條，見第三節差距）：

1. 檔案工具與 json 工具是兩套分工：`read`／`ls`／`stat`／`grep`／`glob` 只吃檔案系統路徑；`json_*` 看到資料夾報 `FileBad … is a directory`（我實測 `json_get`、`json_ls` 對 `proto8/knowledge/aos` 都是）。
2. `view` 工具把路徑與指標**分成兩個參數**（`path` ＋ `pointer`），不收 `FILE#/POINTER`（`proto8/py/tools/base/view/_tooldef.json:4`、`_entry:3-5,60`）。
3. `read` 的路徑說明是「relative to your workspace, or absolute」，不認 `#`（`proto8/py/tools/base/read/_tooldef.json:3`）；其他檔案工具同。
4. 「相對路徑從哪算」有三套：json／檔案工具從 `$AOS_WS` 算（`py/docs/02-索引-base與索引-aos.md` json_get 列、`_description.md` 規則 4）；`$ref` 與 index 裡寫的路徑從「裝著它的那份 JSON 所在的資料夾」算（`refpath.py:48-49`、`proto8/knowledge/README.md` index 段）；`#./`、`#../` 從「寫著它的物件」算（`refpath.py:10-11`）。
5. `index_view` 的「key 接回路徑」兩種寫法：資料夾 `DIR/KEY`，JSON 內 `FILE#/KEY` 或 `FILE#/POINTER/KEY`（`index_view.md` 第二項）；key 本身含 `/` 要寫 `~1`（同檔末段 `data.json#~1items~10` 例）。
6. 工具的其他「路徑」參數不是這種格式：`watch` 的 `metric` 是「JSON pointer into measure.cost」（`/token/in`，無檔名）（`proto8/py/tools/aos/watch/_tooldef.json`）；其餘 aos 工具如 `promote`、`defs` 吃絕對檔案路徑（`watch` 的 `watch` 寫 "Absolute path"）。
7. 指示詞 `$env` 不是路徑尋址，是環境變數；`AOS_CF`／`AOS_CO`（正在跑的那份檔與檔內位置）是 aos-exec 注入的環境變數，`AOS_CO` 是「不帶 `#` 的指標」（`proto8/thinking/2026-11/21/md與json尋址-1121/01-現況-aos今天的尋址.md` 第 4 種；【沒找到】我沒去 C++ 原始碼確認現行是否仍如此）。
8. md 的**人用錨點**（`x.md#某標題錨`，GitHub 把標題轉小寫、空白變 `-`）與 aos 的 md 路徑（`x.md#/標題`）長得像但規則不同；repo 裡到處是前者的連結（同上 01-現況 第 8 種；`wf/` 有 `check_anchors` 工具）。【讀到】
9. mailbox 的 keep 參數說「from your workspace」但絕對路徑照收、`#` 只有 json 工具當分界（`wf/advices/02-範本工具知識庫.md:37`，是 agent 寫的意見，我沒去驗）。

## 二、以前說過什麼（逐字）

### 2.1 起點：11-10、11-12

- 11-10（引在 `proto8/knowledge/README.md` 開頭、與 `proto8/thinking/2026-11/21/md與json尋址-1121/00-使用者原話.md`）：
  > 「json本身就是節點樹。然後json跟檔案系統又有同像性，可以用xxx/xxx.json#/xxx/xxx，這個單一路徑取得東西。所以資料夾，配合各.json檔案。其實就是一個好東西了。」
- 11-12，原話二（`proto8/thinking/2026-11/12/index.md`）：
  > 「就是說，整個檔案系統+json，本來就可以作為agent的memory了，有需要啥就去讀啥，天然的分層。缺的是啥？」
  使用者自答：「description, index」。
- 11-12，原話四（同檔，單一路徑的定義，與 description 最早的樣子）：
  > 「我們用一條路徑來統一檔案系統與json的尋址，如aaa.json#/xxx/yyy，檔案系統的根目錄是/，.json檔案的根(也就是整份檔案)則是#/。而aaa.json#/xxx/yyy可以視為一棵樹上的aaa.json節點下的xxx節點...他底下的yyy節點，我們透過這個路徑去取得yyy這個節點的值。……而description，就是讓agent能在主觀上對yyy這個節點(含其值)有所理解」
- 11-12，原話五（同檔，index 是透鏡）：
  > 「而index的用途，我用白話說，就是一個透鏡，agent可以透過他看到自己想看到的東西」
- 11-12，原話六（同檔，description 與 index 合一）：
  > 「description和index是可以合起來的，或者說，本來就該合起來，統一叫_index.json/_index，也就是agent自己對這個節點的理解。格式就是{xxx:{description:...}, yyy:{...}}。當然，這個_index.json/_index有其天然位置，這個天然的意思是，在沒有指定位置的時候，agent如果想要了解某個節點的狀況，就會去看其上方節點的index。」
- 11-12，原話八（同檔，何時才需要 index）：
  > 「當節點下的某些東西太龐大了，所以用index給他做一個簡介。……如果夠小，那其實也不用做看法了，直接讀就是了。」
- 11-12 晚（引在 `proto8/knowledge/README.md`）：
  > 「客觀那個你不管怎麼描述無法描述全，所以能被我們記錄下來的，非私有的，全都是通用視角(公用視角)(自己公開給別人的聲稱)。」
- 11-12，原話十（同檔，縮小 index 工具範圍）：
  > 「index工具那塊，主要做視角就好，修改這塊應該不用做，因為他就是json，直接用json工具就好」

### 2.2 路徑規則：11-13 晚

`proto8/thinking/2026-11/13/ref-path-rules.md`（亦見 `refpath.py` 檔頭）：
> 「$ref和index路徑這塊，我發現我們錯了，他應該是以#作爲json內部尋址的標示，比如#/aaa，就是根obj的aaa，而#./bbb，就是當前所在的obj的bbb，#../ccc，就是當前所在obj的上一層的ccc。而如果是普通的./zzz.json，那就是當前所在資料夾下的zzz.json，而../xxx.json就是上一層。yyy.json#/kkk，就是當前資料夾下的yyy.json中的kkk這個key。然後yyy.json#./, yyy.json#../都是不允許的。」

之後的裁定（同檔）：「都OK。但是$ref這塊，幫我把$at刪掉。然後$ref和index路徑的規則要相同。」

### 2.3 md 尋址：11-21

`proto8/thinking/2026-11/21/md與json尋址-1121/00-使用者原話.md` 與 `…/知識庫-骨架加md-規劃-1121/00-使用者原話.md`：
> 「啊，幫我派線調查一個可能性，就是說，有沒有辦法讓AI主要生成markdown，然後一個工具可以讓.md檔適應json尋址？這樣人類方便看，aos index也方便查找。」
> 「尋址這塊，感覺也可以用這套#/xxx的方式去尋markdown」
> 「不是，#/xxx尋址md，不要在那邊加東西，就用md現有的格式，比如#這種topic，大概尋一下就好，我知道一定會有地方尋不到，但這樣就夠了。」
> 「仍然以.md爲主體，然後index做導航骨架」（引在 `proto8/knowledge/docs/03-md頁與尋址.md`）
> 「誰說index格式要列出所有東西了？……這個規則刪掉」（同上，index 的寫法一節）
> 「index_check感覺是毒瘤，實作的時候拜託整個重寫。」（`…/10-index_check.md`）
> 「以後我覺得可以是新寫的就預設寫.md，然後再去用index json做骨架，當然，具體要用.md還是.json都可以」（`AGENTS.md:43`）

### 2.4 與 Plan 9 的關係

- 【讀到】使用者 11-05（`proto8/thinking/2026-11/05/no-pid/README.md:13`）：「aos體系脫胎於plan9，也就是純粹的unix哲學。……盡量將各類東西暴露爲檔案。」
- 【讀到】`proto8/thinking/2026-11/18/linux-as-hw-1118/03-別人怎麼做.md:42`（agent 寫的）：「C-30『空間可以擴到外部設備，像 Plan 9』、C-37『空間照 Plan 9』早就定了」；講的是**空間／權限**，不是 description 與 index。
- 【沒找到】我 grep 過 thinking、docs、wf/user，沒有任何一處把 aos index 與 Plan 9 namespace 拿來比、或說「不太一樣因為我們多了 description」。你這次的說法在文件裡沒有對應前例。

## 三、差距（使用者這次說的 vs 現況）

使用者這次的話：「json和檔案系統的單一路徑尋址……降低agent的認知負擔，……延伸出了aos index體系，……我們還添加description等，這是讓agent眼中的世界更加單純，讓他觀察起來更加舒服。」

大方向現況對得上（單一路徑、index、description 都存在）。對不上的地方：

1. **「單一路徑」只在 JSON 工具那一族統一，檔案工具沒有**。`read`／`ls`／`stat`／`view`／`grep`／`glob` 都不吃 `FILE#/POINTER`；`view` 甚至把指標拆成獨立參數（證據：`view/_tooldef.json:4`、`read/_tooldef.json:3`）。agent 要記「看資料夾用 ls、看 JSON 內部用 json_ls、看 index 用 index_view」。
2. **資料夾本身不是 json 工具的節點**：`json_get`／`json_ls` 對資料夾報 `FileBad … is a directory`（我實測）。使用者 11-12 說「檔案系統的根目錄是/，.json 檔案的根是 #/」，意思像是兩者同一棵樹；現在要換工具才走得過資料夾。index_view 是唯一一支橫跨資料夾與 JSON 內部的工具（`index.py:33-35`）。
3. **「description」在現況裡其實有三個名字／位置**：index 項的 `description` 鍵；md 的 `# _description` 與 `# description` 節；`_description.md`／`_description.json` 檔（夾的正文，`index_gen` 檔頭 25–31）。使用者 11-12 原話「description和index是可以合起來的……統一叫_index」，現況的樣子是：`_index` 裡有一格叫 description，另外還有獨立的 `_description` 正文。兩者功能不同（一句話 vs 整頁正文），但名字相近。【讀到】
4. **「讓 agent 眼中的世界更單純」vs 相對路徑三套起點**（見 1.7 第 4 條）。這是認知負擔的一個實際來源。
5. **index 的覆蓋是「大夾才放」**，不是每個節點都有 description。使用者話裡「添加 description 等」像是全面的；現況（也是使用者 11-12 自己訂的）只對太大的夾補（`proto8/knowledge/README.md`：「只給太大的補」）。小夾沒 index，agent 看不到一句話介紹。
6. **index 是人／生成器維護，沒有保證新鮮**：`proto8/knowledge` 手寫（`index_gen.json` 不涵蓋）；`index_check` 不是必跑（`user.md:12`）、也不再查「漏列」（`10-index_check.md` 第 1 條）。所以「description 對不對」沒有任何自動守門。
7. **與 Plan 9 的比較**：使用者這次說「和 plan 9 namespace 不太一樣」。文件裡沒有現成的對照（見 2.4）；而 Plan 9 的名字空間在 aos 裡出現的位置是**沙箱／權限**（`linux-as-hw-1118/03:42`），不是路徑尋址。這句話需要使用者自己的定義，我沒有可以引用的根據。
8. **md 尋址是 11-21 才加的、只讀不寫**。「單一路徑」對 JSON 可讀可寫，對 md 只能讀（`json_get.md` 同節）。【讀到】

## 四、已知的缺點與沒解的問題

來源都是 repo 裡寫著的；不是我的建議。

1. **index 三題等使用者**（`wf/progress.json:110`）：「同一節點多處 index 聽誰的、過時、專屬工具長怎樣」。注：該句之後 index_check 重寫，「題目要重看」。【讀到】
2. **md 標題就是路徑**：改標題字，別頁的 `某頁.md#/舊標題` 就尋不到；靠 `proto8/py/tests/test_knowledge_paths.py` 掃整個知識庫、與改前 grep（`proto8/knowledge/docs/03-md頁與尋址.md`「寫 md 頁的人要知道的」）。同名標題只尋得到第一個；`_` 是保留名。
3. **md 尋址不到的地方使用者已接受**：「我知道一定會有地方尋不到，但這樣就夠了」（見 2.3）。
4. **index 不是事實**：沒列的不代表沒有；`index_view` 不查節點存不存在（`index_view.md` 開頭）。使用者 11-12：「沒列到的就不管」。
5. **`$ref`／`$env` 物件在 json_get 不展開**，要用 `jsonx_*`（`json_get.md`；`py/docs/02-…` 兩族工具）。同一條路徑在 json_ 族與 jsonx_ 族回不同結果。【讀到】
6. **兩份實作要保持同步**：Python（`refpath.py`、`mdpath.py`）與 C++（`aos::ref_spot`、`md.cpp`）靠共用測試表 `ref_path_cases.json`、`md_path_cases.json` 對齊（`refpath.py:8`、`mdpath.py:9`）。C++ 要重編才生效；11-13 的紀錄寫過「C++ 執行檔待停樹換」（`ref-path-rules.md` 標題）。現況是否已換，【沒找到】我沒驗。
7. **index_view 的幾個尚未對齊項**：`10-index_check.md` 末段列了「`index_view` 要跟著改」（純字串 description、`$ref` 解開、`_index.md`、md 的 `# index`）；我讀 `index.py`，`_index.md` 與 md 的 `# index` 已有（`index.py:15,149-157,242`），**純字串、`$ref` 項已有支援**（`index.py:264-333` 有 `is_ref`／`deref`）；【推測】該清單大致已做完，但我沒逐項跑。
8. **知識庫一份中文映照版另存**（`proto8/knowledge-zh-md/`，使用者 11-21 要求；搬出 `knowledge/` 是因為 grep 會重複出現），有自己的 `_index.md`；與英文原版靠人維護同步。【讀到】
9. **「index 放 `_metainfo` 裡」**：口子開了（`index.py:195-205`）但使用者 11-12 說「現在先不用做，這是後續想法」，現況 `knowledge` 都放外面（`proto8/knowledge/README.md`）。【讀到】
10. **觀察**（不是結論）：使用者這次的話是「降低 agent 的認知負擔」；現況裡讓 agent 多記事的點是第三節 1、2、4 項。agent 自己也回報過類似的字樣不一致（`wf/advices/02-範本工具知識庫.md:37`）。
