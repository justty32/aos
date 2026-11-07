知識庫到全庫規模的頂層設計：節點的身份是原文檔的路徑，英文名由程式從拼音算出來後凍結，一個節點對同一個目標只連一條，白話另開一個庫並記住依據哪一版原文，版本、歷史與撤銷全交給 git。

← [2026-11-07](../README.md)｜簡報 [01-簡報](01-簡報.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

本檔是 opus 隊長的補全：以 fable 的 02 為底稿，核對了條文引用，補上 fable 漏掉的衝突，也回應了另一帳號抽查（[arknights-kb-audit](../arknights-kb-audit/README.md)）挖到的命名與連結問題，並跟同批的 [evolve-design](../evolve-design/README.md)、[tool-evolve](../tool-evolve/README.md) 對齊。使用者出門到 16:30，說不要問他，方向題當時寫「已裁（11-07 傍晚）」，11-07 傍晚使用者已全部裁定（見「使用者裁定」節）；隊長替他做的小決定另列在「代定」一節，每條都可以翻案。

## 白話總結

這個知識庫將來會有五千多個節點。每個節點像一個小資料夾，裡面照抄一份原文、按行切成段落。現在只做了三個地點，跑得通；可是一放大，就有五個地方會卡住：名字會撞、原文會改、連結會太多、查東西沒有目錄、給人看的東西沒地方放。下面一段講一件事。

**節點靠什麼認人：靠原文檔的路徑，不靠名字。** 「夕」同時有人物、幹員兩份檔，用名字當鑰匙就分不清。改用 `lore/characters/夕.md` 這種路徑當身份證，路徑裡本來就帶著類別，不會撞。英文名只是方便打字的門牌號碼。

**英文名由程式算，不再問模型。** 中文名轉成拼音當門牌，第一次算出來就寫進名字表，從此不改。抽查發現現在的英文名有三種寫法混著用；改成程式算，就只剩一種寫法。不帶聲調的拼音一定會撞，例如黎和礫都是 `li`。撞了就依序加 `-2`、`-3`，誰先登記誰拿沒有後綴的那個，登記後同樣不改。門牌只是給機器用的，人看的是節點標題裡的中文名，所以 `li-2` 不好看也沒關係。

**一個實體只會有一張身份證。** 抽查發現「煮傘居士」在名字表裡有自己的門牌，在別名表裡又被當成夕。新規矩把這個漏洞從根上堵住：只有語料裡有自己那份檔的東西，才能進名字表拿門牌；其他名字（煮傘居士、陳暉潔）只能當某個人的「別名」，不能自成一人。

**原文改了怎麼辦：每個節點記下自己抄的是語料哪一個版本。** 語料是一個 git 倉庫，每一版都有編號。節點把當時的編號寫進去，之後要知道哪些節點過期，只要比對兩個版本之間哪些檔改過，全是腳本做，不花 token。過期的節點重抄一次，連結靠「名字」在新段落裡重新找位置，找不到的才交回模型重判。

**tag 只放程式能從語料結構抽出來的東西。** 例如類別、目錄裡的分組，以後再加事件的「分類」欄、幹員的出身地，都是加一條抽取規則，不讓模型自己發明。查 tag 的方式跟同批 evolve-design 對齊：aos 的 `memory find` 加一個「只找帶這個 tag 的節點」的選項。要同時滿足好幾個 tag，或要查「誰提到了夕」，再用這條線自己的小工具。

**連結要省著用：對同一個目標只連一條，而且只連有自己檔案的東西。** 婆山鎮原本 16 條連結，其中 9 條都指向夕，因為提到一次就連一次。現在改成一個目標一條，只記第一次出現在哪一段。目標也只限人物、幹員、地點、事件、勢力這五類有正式檔案的實體。抽查發現的「博士」漏連，是因為找名字的程式先挑了一個證據層的長檔名「博士甦醒」，接著把它丟掉，卻沒有回頭試裡面較短的「博士」。只拿五類當候選，這個毛病就不會再出現。

**給人看的白話另開一個庫。** 原文庫是唯一的真相，白話庫是模型寫的摘要。每篇白話最後一行寫明「根據原文庫哪個節點、哪一版寫的」，原文一改，它就被標成過期。建庫的 agent 看不到白話庫，所以白話不會倒流進真相。問答 agent 兩個庫都看：先翻白話，拿不準再翻原文，每句話仍要附原文出處。白話不必一次全寫，有人問到哪篇才寫哪篇。

**git 管所有的「誰改的、什麼時候、改了什麼、要不要退回」。** 語料是一個 git，知識庫是另一個 git，節點用版本編號指向語料。一個節點一個 commit，隊長審核就是看差異，模型判錯了就退回那一個 commit。節點裡不另外記誰改、何時，要查就用 git。aos 本體只改一處：`memory find` 加認 tag，這件事 evolve-design 已經排好了。

## 一、設計

### 1.0 各層管什麼（C-52）

| 層 | 管什麼 | 不管什麼 |
|---|---|---|
| aos 本體 `memory`／`memory_write` | 資料夾樹、讀寫、`節點#/指標` 讀、全文 find、多庫捷徑；**加 `find` 的選填 `tag`**（照 evolve-design 第 10 步，讀 memory 自己公開的 `_tags.json` 約定） | 不認連結、別名、名字表、語料版本、git |
| arknights 線的定義（試驗場 `defs/`） | `kb_slug`、`kb_store`、`kb_mentions`、`kb_link`、`kb_tag`、`kb_lint2`、`kb_sync`、`kb_find`、`kb_plain`、`linker`、`plainer`、`qa_ak`、`kb_search`；名字表、tag 抽取規則、連結規則、白話庫 | 不碰 aos 工具內部；節點裡不記誰改、何時 |
| 隊長（之後換審視 agent） | 在輪次邊界跑 `kb_sync --status`、挑過期的重做、提新的 tag facet、審 git diff、revert 錯判 | 不手改節點內容；審視 agent 怎麼長交給 evolve-design |
| 人 | 蓋過英文名、核准新 tag facet、讀白話庫 | — |

### 1.1 節點：身份、命名、別名、版本

**概念**：節點的身份是語料檔的路徑（`source.json` 的 `from`），永遠唯一。slug（英文門牌）是從身份機械推出來的 ASCII 名字，第一次推出就凍結。原文的版本是語料 repo 的 commit（`rev`）。

**名字表**：每個類別一個檔，`ak/index/names/<class>.json`，鑰匙是 lore 路徑。

```json
{
  "summary": "lore path -> frozen slug and learned aliases. Tool-owned; use kb_search.",
  "entries": {
    "lore/characters/夕.md": {"slug": "xi", "by": "pinyin", "aliases": {"煮傘居士": "llm:sol"}},
    "lore/characters/黎.md": {"slug": "li", "by": "pinyin"},
    "lore/characters/礫.md": {"slug": "li-2", "by": "pinyin"},
    "lore/operators/凱爾希.md": {"slug": "kaltsit", "by": "human"}
  }
}
```

- **拼法只有一條**（代定 1）：漢字逐字轉無聲調拼音、音節直接連寫不加連字號；原本就是拉丁字母的部分轉小寫照留（`Ace` → `ace`）；其他字元（`／`、`·`、`「」`、空白）一律變成一個 `-`，頭尾的 `-` 去掉。例：婆山鎮 → `poshanzhen`，塔拉／深池 → `tala-shenchi`。抽查 4-2 的三種寫法（`poshan-zhen`、`hua-zhong-ren`、`rhodes-island`）因此只剩一種。人工蓋過的（`by: "human"`）是有意的例外，表裡看得出來。
- **同音**（回應抽查 4-3）：同一類別裡撞名就依序加 `-2`、`-3`。誰拿沒有後綴的那個看登記順序：整批初始化時照 lore 路徑的 Unicode 排序登記；之後新增的拿下一個空號。登記後不改，所以結果穩定，也可以重現。不同類別不會撞，因為節點路徑裡有類別（`ak/characters/xi` 與 `ak/operators/xi` 是兩個門牌）。不改用帶聲調的拼音：同聲調的同音字一樣會撞，到頭來還是要後綴，多一套規則沒有好處。
- **凍結**：表裡有的就不再算。fable 原稿每條都帶 `frozen: true`，這裡拿掉，因為「在表裡」就等於凍結（C-56 做減法）。人要蓋過，直接改那一條、`by` 改成 `human`；如果舊 slug 已經被別的節點的連結引用，`kb_slug` 拒絕修改，並印出是哪些節點在引用。
- **別名與雙身份**（回應抽查 4-1）：名字表的鑰匙**只能是 lore 裡實際存在的檔**。沒有自己那份檔的名字（煮傘居士、陳暉潔）只能出現在某一條的 `aliases` 裡，不能自成一條。`kb_lint2` 驗兩件事：每條鑰匙對應的檔存在；同一個別名不能同時是另一條的檔名主幹（stem），否則報 `NameAliasConflict`，這條試驗場 B4 已經做了。同一個別名對到多個身份時兩邊都留，比對時標成模稜兩可，交給 linker 判。namer 整支退役，於是「替表外名字另取門牌」這條路就不存在了。
- **同一個名字跨類**（92 個，例如夕在 characters、operators、character_deep_dive 都有檔）：連結目標只限五類。同一個名字在五類裡出現不只一份時，依固定的優先序取第一份：characters → places → factions → events → operators（代定 2）。理由：幹員檔是遊戲單位的檔案，人物檔才是那個人本身；地點與勢力同名時（卡茲戴爾、哥倫比亞），地點詞條通常是主題頁。linker 可以用別名把個別情況蓋過去，例如寫進 factions 那條的 `aliases`。
- **候選名字只取五類**：candidates＝五類檔的 stem＋名字表別名＋原文裡現成的 Markdown 連結目標。evidence 子檔的結構性檔名（「基本資訊」出現 159 次、「博士甦醒」）不進候選。**比對時先篩類別、再挑最長**；遇到被濾掉的長命中，要退回去試較短的名字，不能整段跳過（回應抽查 2-1）。候選只取五類以後這種情形本來就不會發生，保留這條是防將來有人又放寬候選範圍。

**`source.json` 加 `rev`**：

```json
{"from": "lore/places/婆山鎮.md", "rev": "5d9beddc5ee4f7b8572bc180166469fbeb341227",
 "sha256": "7472…bfa1", "paras": ["### 婆山鎮（畫中天地）", "", "實為十二代理人之一「夕」…", "", "詳見：…"]}
```

- 內容取自 `git -C <語料 clone> show <rev>:<from>`。`from` 相對於語料 repo 根，而不是相對於 `lore/`。用的是試驗場自己的 clone（`ws/corpus/arknights`），使用者的語料 repo 照舊唯讀（arknights-kb 代定 2）。工作樹裡 146 個還沒 commit 的草稿不進庫。
- `rev` 寫完整的 40 碼（代定 3）。短碼在倉庫長大後可能變得有歧義，而這個值會被長期引用。
- lint 規則 1 改成「`'\n'.join(paras)` 逐 byte 等於 `git show rev:from`」。lint 只管節點內部一致，原文有沒有新版是 `kb_sync` 的事。

**更新（`kb_sync`）**：

- `kb_sync --status [rev]`（預設是 clone 的 HEAD）：對每個節點，看 `from` 有沒有出現在 `git diff --name-status <node.rev> <rev>` 裡；白話庫則比每篇的 `source@` 與現在 `source.json` 的 sha256。最後印出過期清單，不花 token。
- `kb_sync <class>/<slug> [rev]`：重存原文 → 每條連結用 `name` 在新的 `paras` 裡找第一次出現的位置並改寫 `in`，找不到就設成 `null` → 重算 tag → lint（`in: null` 會被擋）→ 只把 `null` 那幾條送 linker 重判，並附上舊判定當提示 → commit `Sync places/poshanzhen to lore@<rev 前 12 碼>`。
- 什麼時候跑：在輪次邊界由隊長（之後是審視 agent）跑，不做自動監聽（方向題 4）。

**索引檔**（名字表、`ak/index/tags.json`）是工具擁有的資料，由工具寫，不經 `memory_write`。照 C-71「沒有庫、子庫之分」，它們在 memory 眼裡仍是節點，agent 讀得到。只是 `ak/index/README.md` 會寫一句「這裡是工具資料，請用 `kb_search`／`kb_find`」，每個索引檔也帶 `summary` 鍵，`memory ls` 會印出這一句。fable 原稿用的是 `description`，但 memory 只認 `title`／`summary`（`memory_fs.py` 的 `title_summary`），所以改成 `summary`（代定 4）。索引檔一條一行、鑰匙排序，git diff 一眼就看得出改了哪筆。

### 1.2 tag

**概念**：tag 的形狀是 `facet:value` 字串（facet 是 tag 的種類，像「類別」「分組」），全部由語料結構機械抽出。一種 facet 就是 `kb_tag` 裡的一條抽取規則。tag 檔是可以重算的快取，lint 規則 7 本來就要求它等於重算結果。模型不產 tag，語意上的分類是白話層或問答的事。

**放哪、怎麼查**（跟 evolve-design 對齊，見衝突 7）：

- 節點是資料夾，所以 tag 放在節點資料夾裡的 `_tags.json`：`{"tags": ["class:places", "group:炎國／歲"]}`。這是 evolve-design 定的 memory 約定。`_` 開頭照 R11 是「aos 認的固定檔」，memory 列子節點時不列 `_` 開頭的檔（`memory_fs.py` 第 147 行），所以每個節點下面不會多出一個叫 `tags` 的雜訊子節點。fable 原稿用的是 `tags.json`，這裡改掉（代定 5）。
- 單一 tag：`memory find {"tag": "group:炎國／歲"}`，由 aos 本體提供，也就是 evolve-design 第 10 步。
- 多個 tag 交集、按 tag 計數：用這條線的 `kb_tag --index` 產生 `ak/index/tags.json`（facet → value → 節點數），再用 `kb_find --tag A --tag B` 取交集。
- agent 怎麼知道有哪些 facet：根 `ak/README.md`（ELI5，會進 system prompt）只列 facet 名稱與一句用法；facet 底下有哪些值，在 `index/tags.json`，要用時才讀。

**現有 facet**：`class`（lore 第一層目錄）、`group`（同目錄 INDEX 的分組小標）。**候選**：`category`（events 的「分類」欄）、`origin`／`race`（operators 的「檔案」欄）。新增 facet 要改程式一處並全庫重算，由隊長提、人核准。

### 1.3 連結的節制

**概念**：連結表示「這段原文提到了哪個實體」，不是記錄每個字出現在哪裡。

1. **一個目標一條**，記第一次出現的那一段。試驗場 B4 已經按目標分組（三地 5／12／15 個目標、16／19／24 處），這裡再收掉多處位置，只留第一段（代定 6）。原因：連結的讀者只需要「從這裡走到誰」；要全部位置，在段落裡找名字就有，而且 `kb_sync` 重新定位只剩一個數字要對。
2. **只連五類實體**：目標必須是 `ak/<五類>/<slug>`，不連 evidence、不連自己、不連章節名。表外的提及（「近衛局」→龍門近衛局、「大炎」→炎國）由 linker 回 `alias_of`，寫進名字表的別名，之後就由規則命中。對不上任何身份的不連。
3. **三種來源，兩種成本**：原文裡現成的 Markdown 連結、以及唯一且不是單字的名字命中，記 `by: rule`，不花 token；單字名、多個候選、模型補上的，記 `by: llm:<級>`。`by` 一律是字串（抽查 2-4）。
4. **`to` 一律寫節點路徑**，不再分 pending／ok：slug 由程式算得出來，節點還沒建也能先指過去。目標存不存在，讀的時候看檔案系統就知道，不另存欄位。讀的人如果撞到 `NodeMissing`，可以用名字表把 slug 反查回 lore 路徑去讀原文。`retarget` 這一步刪掉。
5. **位置只到段落**：`in` 寫 `source#/paras/N`，字元區間 `at` 拿掉。B3 有一次模型給的區間要靠腳本校正，抽查 2-2 的「陳暉潔」區間只蓋到「陳」，而區間本身沒有讀者。lint 規則改成「`name` 出現在第 `in` 段」。
6. **反向連結不另存，要用時現查**：`kb_find --to ak/characters/xi` 就是在全庫的 links.json 裡 grep；agent 自己用 `memory find "ak/characters/xi"` 也行。

```json
{"links": [
  {"name": "夕", "in": "source#/paras/2", "to": "ak/characters/xi", "by": "llm:terra"},
  {"name": "畫中人", "in": "source#/paras/2", "to": "ak/events/huazhongren", "by": "rule"}
]}
```

這和 evolve-design 的規矩一句「要讓工具沿著走的才做連結；只是提到，寫名字就好」的關係見衝突 8。

### 1.4 給人看的那層

**概念**：原文庫 `ak` 是唯一的真相。白話庫 `ak_plain` 是從它衍生出來的，路徑一對一對應，每篇記下自己依據的原文快照；內容只能從 `ak` 流向 `ak_plain`，不能倒流。問答 agent 給的是「當場做、可以跨節點的白話」，白話庫放的是「事先做好、一個節點一篇的白話」。兩者不脫節靠同一條規則：出處都只能引用 `ak/...#/paras/N` 或 `lore/...`。

- 白話庫是另一個 memory 根：`ak_plain/<class>/<slug>.md`。第 1 行和原文庫同一個標題，第 2 行是一句摘要（`memory ls` 會印），最後一行 `source: ak/<class>/<slug>/source@<sha256 前 12 碼>`。
- 由 `plainer` agent（terra 級以下）讀一個節點的 `source.json`，回一篇白話文字；**寫檔的是 `kb_plain` 腳本，不是 plainer**（代定 7）。kb_plain 驗首行與末行格式後寫入並 commit。這樣 plainer 的記憶根只有 `ak`，看不到白話庫，也沒有寫入工具。
- 過期由 `kb_sync --status` 順帶列出。過期的那篇重寫或刪掉，不修補。白話庫不做語意 lint，靠抽查與 git revert。
- 掛法用現有的多庫方案 A：建庫的 agent（linker、plainer）記憶根只掛 `ak` 一條捷徑；`qa_ak` 的記憶根掛 `ak` 與 `ak_plain` 兩條。
- `qa_ak` 的查法：`kb_search`（名字表＋別名 → 節點路徑）→ 讀 `ak_plain` 那篇 → 不夠再讀 `ak/.../source#/paras/N` → 都沒有才 grep `lore/`。這一輪只建 8～10 個地點，所以大部分問題仍會落到最後一步，這是預期中的；06 原型本來就主要靠 grep lore。
- 寫幾篇：懶做，有人問到或人點名才寫（方向題 3）。

### 1.5 git 的角色

- **語料的版本**：節點的 `rev` 指向語料 clone 的 commit，只抄已 commit 的內容。知識庫不另外複製一份語料，靠 clone 加 `rev` 指過去。搬到另一台機器時（C-79、C-83），兩個 repo 一起 pull；`kb_sync --status` 第一件事就是確認每個 `rev` 在本機 clone 裡找得到，找不到就報 `RevMissing`（代號照 C-54，`…Missing`）。
- **知識庫的版本與歷史**：一個節點一個 commit（`Add …`、`Sync … to lore@…`、`Plain …`），名字表的變動跟節點放在同一個 commit。節點裡不記誰改、何時，要查就 `git log -- ak/places/poshanzhen`、`git blame links.json`。
- **審核與撤銷**：隊長審核就是看 diff；模型判錯就 `git revert` 那個 commit 再重跑。使用者裁定的「格式檢查過就 commit，事後抽查」就是這樣落實。
- **整體比對**：照 tool-evolve，整庫從零重跑一次後 `git status --porcelain` 是空的，就代表一字不差。`place_run --check` 與 `kb_sync` 都可以用這把尺。
- **誰碰 git**：只有腳本（`place_run --commit`、`kb_sync`、`kb_plain`）。agent 不碰；aos 工具不碰（已定）。
- **能不能重建**：整庫＝語料@rev＋名字表（含別名）＋links.json 裡 `by: llm:*` 的判定。其餘（paras、tag、索引、白話）都能重算。所以真正要保住的只有這三樣，而它們都在 git 裡。
- **先不做**：多隻建庫 agent 同時 commit 同一個 repo 會撞 `index.lock`。現在是一個接一個跑；之後要並行時，改成寫檔並行、最後由 `place_run` 統一 commit。

### 1.6 交給別題

- 新工具的 `_metainfo`、他者觀測、審視 agent 何時替隊長跑 `kb_sync`：交給 evolve-design。
- `kb_*` 能不能叫 `bash`、寫入路徑怎麼約束：交給 tool-evolve。
- 多隻 plainer／linker 並行時怎麼排程、本機模型一次只能載一個：交給 kernel-nest。

## 二、與既有條文的衝突

fable 列了六條。隊長核對後，第 1、2 條其實不算衝突（照條文原文就讀得通），第 3～6 條成立。另外補上四條（7～10）。

| # | 哪條 | 衝突在哪 | 各自後果 | 推薦 |
|---|---|---|---|---|
| 1 | knowledge-write 使用者裁定（11-05 夜「知識庫這塊都按照推薦」）第 4 題：「不記誰改的、何時（不記 `_meta`，要歷史就 `git init`）」 | fable 擔心 `rev`、`sha256`、白話篇的 `source@` 也算 metadata。核對原文後，那一題禁的範圍本來就只有「誰改、何時」。 | **不算衝突**。`rev` 指的是語料的版本，不是知識庫自己的歷史，沒有搶 git 的工作。 | 照原文讀，不必補條文。 |
| 2 | agent-knowledge「節點 ≤ 2 KB」（建議）、`memory_write` 8000 bytes 硬限；B2 審視定、B3 做的「別名分片 ≤ 8,000 bytes」 | 全庫的名字表一類就有幾十 KB | 照節點規矩分片：會有上百片，查一次要讀多片。不分片：`memory read` 預設在 8000 截斷（可以用 `max_bytes` 調大）。 | **不算衝突**。2 KB 是建議；8000 是 `memory_write` 的限制，索引檔不經它寫。索引一類一檔，撤銷 B3 的分片做法。 |
| 3 | B2 審視定、B3 做的「pending 指 `lore:` 原檔，建好節點後 `retarget` 掃全庫改指」 | slug 由程式算得出來，`to` 一律直接指節點路徑 | 留著：多一個狀態欄、多一次全庫掃描、lint 多兩條規則。改掉：slug 一旦被引用就不能改。 | 改掉（C-56 做減法）。不寫遷移，現有節點重建。 |
| 4 | C-42 註「頂層是簡介、index 目錄，盡量 ELI5」、想法 7「只給頂層簡介和目錄（可以的話盡量少）」 | `memory read ak/characters` 會列 686 行子節點，超過 8000 bytes 被截斷 | 接受截斷：無害。按首字分桶：路徑變長、連結變醜。給 `memory` 加「子節點超過 N 個只印計數」：本體多一個參數。 | 接受截斷，各類別 README 寫一句「N 個節點，請用 find 或 kb_search」。fable 把「盡量少」記在 C-42 名下，原話其實出自想法 7，結論不受影響。 |
| 5 | 現行 lint 規則 1「逐 byte 等於原檔」（比的是工作樹） | 原文一改 lint 就紅，可是那其實是「過期」不是「壞掉」 | 維持：語料一更新全庫都紅，分不出壞與舊。改成比 `git show rev:from`：lint 管一致、sync 管新舊。 | 改比 `rev`（C-52 各管一層）。 |
| 6 | B2 定的 `at` 字元區間、lint 驗區間 | 拿掉 `at` | 留著：每條多一組容易錯的數字。拿掉：要逐字高亮時得現算。 | 拿掉。fable 說「常錯」講得太重（實際是 B3 一次、抽查 2-2 一次），但結論成立。 |
| 7 | **同批 evolve-design**（README 已 commit）：`memory find` 加選填 `tag`，tag 放節點 JSON 的 `tags` 或資料夾節點的 `_tags.json` | fable 推薦 tag 不進本體，放 `tags.json` 讓 find 當全文字串找。兩份設計互相矛盾。 | 照 fable：本體零改動，但 `find "class:places"` 也會命中任何含這串字的內文，而且 tag 檔會變成每個節點下的子節點。照 evolve：本體加一個逐字比對的選項。fable 擔心這會碰到 C-52，但 `_tags.json` 是 memory **自己公開的約定**，不是去認上層的格式，符合 C-52 11-06 讀法（不認身份、可認公開介面）。 | **一致讀法**：tag 的存放照 evolve（`_tags.json`），單一 tag 的查詢照 evolve（`memory find {"tag"}`）；多 tag 交集與反查留在這條線的 `kb_find`。fable 的方向題 5 因此改推薦 B。 |
| 8 | **同批 evolve-design** 的規矩一句「要讓工具沿著走的才做連結；只是提到，寫名字就好」 | 這裡的 links.json 記的恰恰是「提到」 | 字面讀：連提及都不該記，問答與反查就沒有表可用。分層讀：evolve 那句講的是 aos 知識庫一般節點；links.json 是這條線工具擁有的「提及→身份」解析結果，`kb_sync`、`kb_find --to`、`kb_search` 都沿著它走。 | 分層讀：links.json 正是「要讓工具沿著走」的那種。連結值的寫法與 evolve 一致（`to` 是節點路徑、`in` 是 `節點#/指標`）。 |
| 9 | arknights-kb 代定 2「arknights repo 唯讀」 | fable 落地第 7 步要「在 lore 的測試分支插一段並 commit」 | 照做會寫到使用者的語料 repo。 | 改成在試驗場的 clone（`ws/corpus/arknights`）或它的臨時副本上做。`rev` 也指 clone。 |
| 10 | C-54 錯誤代號、程式輸出英文 | fable 沒有給新工具的錯誤代號 | 不給：gpt 施工時會各自發明。 | 代定 8：`SourceMissing`（rev 裡沒有這個檔）、`RevMissing`（clone 裡沒有這個 rev）、`SlugBad`（拼法不合）、`SlugReferenced`（人要改的 slug 已被引用）、`NameAliasConflict`（沿用 B4）。 |

查過、不算衝突的：`in`、`to` 只是 links.json 裡的資料，memory 不解析；讀段落走 `memory read ak/…/source#/paras/2`（P3 已支援，在 N-62 範圍內）。`kb_sync` 讀語料 clone 的 git，是在讀輸入資料的公開介面，不是偷看下層（C-52）。白話庫另開一個根、用捷徑掛載，就是多庫方案 A 原樣。JSON key 全小寫（C-54）。

## 三、方向題（11-07 傍晚已裁，五題都選推薦）

1. **slug 怎麼來**。A：拼音機械生成，人可在名字表蓋過；幹員可以從遊戲資料的 `appellation` 欄取官方英文名（例 `kaltsit`）。不花 token，節點建好前就能被指向。B：保留 namer 模型命名，名字較像人取的，但每個新實體多一次呼叫（約 1,700 token），`retarget` 也得留著。**推薦 A，已裁（11-07 傍晚）。** 幹員取官方英文名這一項要讀 `corpus/raw`，它不在語料 git 追蹤裡（不足 #7），所以幹員的英文名以讀到的那份資料為準，`by` 記 `human`，表示不是拼音規則算的。
2. **連結粒度**。A：一個目標一條，位置到段落。B：每次提到都一條，帶字元區間。**推薦 A，已裁（11-07 傍晚）**：「別濫用」首先是數量。
3. **白話庫怎麼建**。A：懶做，有人問到才寫。B：全做，約 5,000 篇 × 3,000 token ≈ 1,500 萬 token，語料一更新還要重寫一批。C：不建，只靠問答，每問一次就重花一次（每題約 1.6 萬 token），人也沒有可以直接翻的東西。**推薦 A，已裁（11-07 傍晚）**；等問答紀錄顯示哪些類別常被問，再對那類批次補做。
4. **語料更新後多久跟一次**。A：在輪次邊界跑 `kb_sync --status`，挑過期的重做。B：語料每次 commit 就自動 sync，成本難以預估（一批改 19 檔）。**推薦 A，已裁（11-07 傍晚）。**
5. **tag 要不要進 aos 本體**（照衝突 7 改寫）。A（fable 原推薦）：不進本體，tag 當全文字串找。B（evolve-design 已排）：`memory find` 加選填 `tag`，讀 memory 公開的 `_tags.json` 約定；多 tag 交集仍在這條線。**推薦 B，已裁（11-07 傍晚）**：兩份設計就此一致，本體只加一個逐字比對的選項，而這個選項別的知識庫也用得上。

## 使用者裁定（11-07 傍晚，40 題選項框）

使用者 11-07 傍晚在 40 題選項框裡裁定（回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)）；除特別註明，選的都是推薦。回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進，沒逐題寫備註的也一樣。

- **ks-1**（節點的英文門牌，要由程式算，還是讓模型取名？）：選 A「拼音機械生成，人可在名字表蓋過；幹員可以從遊戲資料的 appellation 欄取官方英文名（例 kaltsit）」。
- **ks-2**（同一個節點提到同一個對象，要連幾條？）：選 A「一個目標一條，位置到段落」。
- **ks-3**（給人看的白話庫，要一次寫完嗎？）：選 A「懶做，有人問到才寫」。
- **ks-4**（原始語料改了，知識庫多久跟一次？）：選 A「在輪次邊界跑 kb_sync --status，挑過期的重做」。
- **ks-5**（找標籤要交給 aos 的 memory find 嗎？）：選 B「memory find 加選填 tag，讀 memory 公開的 _tags.json 約定；多 tag 交集仍在這條線」。

## 四、代定（使用者不在時隊長定，每條可翻案）

1. **slug 拼法**：整詞無聲調拼音連寫；拉丁字母轉小寫照留；其他字元變 `-`。為什麼：抽查 4-2 有三種寫法，必須收成一種，連寫最簡單。翻案：要音節之間加連字號，就改 `kb_slug` 一處後全庫重建。
2. **同名跨五類的優先序**：characters → places → factions → events → operators。為什麼：固定順序才是確定性的，個別例外靠別名蓋過。翻案：改順序或改成一律交給 linker 判。
3. **`rev` 寫完整 40 碼。** 為什麼：會被長期引用，短碼將來可能有歧義。翻案：只要改成短碼就好。
4. **索引檔用 `summary` 鍵**（不用 `description`）。為什麼：`memory ls` 只認 `title`／`summary`。
5. **tag 檔叫 `_tags.json`**（不叫 `tags.json`）。為什麼：與 evolve-design 一致，也不會在每個節點下多一個子節點。
6. **連結只留第一處所在的段**，B4 的多處位置收掉。翻案：要保留全部段號，`in` 改成陣列即可。
7. **plainer 只回文字，由 `kb_plain` 寫檔。** 為什麼：建庫的 agent 不需要寫入工具，也不必看到白話庫。
8. **新的錯誤代號**：`SourceMissing`、`RevMissing`、`SlugBad`、`SlugReferenced`、沿用 `NameAliasConflict`。
9. **名字表不帶 `frozen` 欄**：在表裡就是凍結；`by` 標 `pinyin`／`human`。
10. **namer 退役**，B2 的 `names.tsv` 改成按類別分檔的 JSON。不寫遷移，現有三個地點節點刪掉重建。

## 五、落地順序（交給 gpt 照圖施工，每步一個 commit、每步一句完成條件）

全部在試驗場 `~/code/playground-ak/` 做；只有第 6 步在 aos repo，而且它就是 evolve-design 的第 10 步，不重複施工。程式輸出、索引檔的 `summary`、commit 訊息一律英文。

1. **`kb_slug`**：輸入 lore 路徑，查 `ak/index/names/<class>.json`，沒有就照代定 1 拼出來；同類撞名加 `-2`、`-3`，寫回表裡（`by: pinyin`）；初始化時按路徑的 Unicode 排序登記。完成條件：五類 1,373 個檔全跑一遍，得到 1,373 個在各自類別內不重複的 slug；模型呼叫 0 次；黎／礫、吽／紅、令／澪各自分到無後綴與 `-2`；重跑結果逐 byte 相同。
2. **名字表的 lint**：鑰匙對應的檔存在；別名不能等於別條鑰匙的檔名主幹（`NameAliasConflict`）。完成條件：手動把「煮傘居士」加成一條獨立鑰匙時被擋下。
3. **`kb_store` 加 `rev`**：從 `git -C ws/corpus/arknights show <rev>:<from>` 取內容，預設 rev 是 clone 的 HEAD，存完整 40 碼；rev 裡沒有這個檔就報 `SourceMissing`。完成條件：婆山鎮的 `source.json` 帶 `rev`，`paras` 與 `git show` 的輸出逐 byte 相同。
4. **`kb_mentions` 收窄候選並修遮蔽問題**：候選＝五類檔名主幹＋名字表別名＋原文 Markdown 連結目標；先篩類別再挑最長，被濾掉的長命中要退回去試短名字；同名跨類照代定 2 的優先序；輸出按目標分組，列出第一次出現的段。完成條件：切爾諾伯格出現「博士」第 2 段的那一處（抽查 2-1 的 [20,22]）；婆山鎮的候選裡沒有任何 evidence 的檔名主幹。
5. **`kb_link` 改寫**：欄位只剩 `name,in,to,by`，`by` 一律字串；一個目標一條；`to` 由 `kb_slug` 算；`alias_of` 寫回名字表的 `aliases`；刪掉 `retarget`、`state`、`at`。完成條件：婆山鎮 links.json ≤ 8 條，lint 通過，程式裡搜不到 `retarget`、`state`、`at`。
6. **（aos repo，就是 evolve-design 第 10 步）`memory find` 認 `tag`**：完成條件照 evolve-design。
7. **`kb_tag` 寫 `_tags.json`，以及 `--index` 和 `kb_find`**：`--index` 產生 `ak/index/tags.json`；`kb_find` 支援多個 `--tag` 取交集，以及 `--to <節點路徑>` 反查。完成條件：`memory find {"tag":"class:places"}` 與 `kb_find --tag class:places` 都列出三個地點；`kb_find --to ak/characters/xi` 列出婆山鎮；索引重跑逐 byte 相同。
8. **`kb_lint2` 改規則**：規則 1 比 `git show rev:from`；連結規則改成 `name` 出現在第 `in` 段（`in: null` 算失敗）；刪掉 pending 與 state 相關的兩條；改成驗 `to` 合 `ak/<五類>/<slug>` 格式；tag 驗 `_tags.json` 等於重算結果。fable 原稿這一步的規則編號前後不一致，以這裡為準。完成條件：三個節點通過；把副本的一段原文改掉後不通過，並指出是哪一條規則。
9. **`kb_sync`**：`--status [rev]` 列出過期的節點與白話篇；`<class>/<slug> [rev]` 依 1.1 節重存、重新定位、重算、lint、commit。完成條件：在 clone 的**臨時副本**裡，於婆山鎮檔第 2 段前插一段並 commit，sync 後每條連結的 `in` 自動加一且 lint 通過；再把「夕」全刪，sync 後那條變成 `in: null`，lint 指出它。
10. **`place_run` 接線**：S1 改叫 `kb_slug`，S4 用新的 `kb_link`，刪掉 namer；`--check` 照新規則重建並比對（`git status --porcelain` 為空）。完成條件：三個地點從零重建，每個地點 ≤ 1 次 LLM 呼叫，`--check` 通過，`steps.json` 記到每一步的 token 與秒數。
11. **根、類別與索引的 README**：`ak/README.md` 十行以內，寫這是什麼、五類、facet 名、三句用法；每個類別 README 一行「N nodes, use find or kb_search」；`ak/index/README.md` 一行說明這裡是工具資料。完成條件：`memory read ak` 的輸出 ≤ 1,500 bytes，`memory ls ak/index` 印得出各索引檔的 `summary`。
12. **`ak_plain`、`plainer`、`kb_plain`**：完成條件：婆山鎮白話篇存在，末行的 sha 與 `source.json` 相符；改動 `source.json` 後，`kb_sync --status` 把它列為過期。
13. **問答掛載**：`qa_ak` 的記憶根改成掛 `ak`、`ak_plain` 兩條捷徑的資料夾；`kb_search` 改讀名字表（含別名）→ 節點路徑，查不到再退回 grep lore。完成條件：凍結的 10 題重跑一次，報表列出每題的 token、答對與否、出處對不對，並標出哪幾題命中了 `ak_plain`。

第 1～5 步是一組，做完就修好了抽查的四個問題（博士漏連、雙身份、三種拼法、同音）。第 6～9 步各自獨立。第 10 步依賴第 1～9 步。第 12～13 步可以放到地點做完之後再做。
