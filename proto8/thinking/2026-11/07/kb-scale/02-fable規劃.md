# fable 規劃：全庫規模的知識庫——節點身份＝原文路徑、名字機械生成、連結一目標一條、白話層另開一庫、版本與歷史全交給 git
← [README](README.md)｜簡報 [01-簡報](01-簡報.md)

## 一、白話總結

這份知識庫未來會有五千多個節點，每個節點就是一份「照抄原文、切成段落」的小檔案夾。現在的做法在兩個地點上跑得通，但有幾個地方一放大就會卡：名字會撞、原文會改、連結太多、查東西沒有索引、給人看的東西還沒地方放。下面是我的解法，一段講一件事。

**節點的身份證是原文的檔案路徑，不是英文名。** 現在用「類別＋中文名」當鑰匙，碰到「夕」同時是人物又是幹員就會混。改成直接拿 `lore/characters/夕.md` 這條路徑當鑰匙，路徑天生含類別，永遠不撞。英文名（slug）只是一個方便打字的綽號。

**英文綽號改成機器算出來，不再問模型。** 中文名用拼音轉成 `poshan-zhen` 這種樣子，同類別撞名就加 `-2`，第一次算出來就寫進名字表、永遠不改。這樣每個節點還沒建之前，大家就已經知道它會叫什麼，連結可以直接指過去，不必等它建好再回頭改——現在那個「回頭掃全庫改連結」的步驟整個省掉。想用官方英文名（幹員的 Kal'tsit 之類）的話，人可以在名字表裡手動蓋過。

**原文改了怎麼辦：每個節點記住自己抄的是語料的哪一個 git 版本。** 語料 repo 還在長，每批會改十幾個檔。節點抄的時候把當時的 commit 編號寫進去，之後「檢查有沒有過期」就是比兩個 commit 之間哪些檔改過，純腳本、零 token。過期的節點重抄一次，連結用「名字」在新段落裡重新找位置，找得到就自動更新，找不到的才送回去請模型重判。

**tag 只放機器能從語料結構抽出來的東西，像類別、目錄分組。** 現在的兩種 tag 就是這樣，以後加新的（例如事件的分類欄、幹員的出身地）也是加一條抽取規則，不是讓模型自由發揮。查 tag 不用新機制：tag 是字串，現有的 `memory find` 就是全文找字串，直接能用；要列很多筆時再用這條線自己的小工具查索引。

**連結要節制：一個節點對同一個目標只連一條，而且只連「有自己檔案的東西」。** 婆山鎮 5 段 16 條連結、其中 9 條都指夕，是因為每提一次就連一次。改成一個目標一條（記第一次出現在哪一段），而且只連人物、幹員、地點、事件、勢力這五類有正式檔案的實體，不連「基本資訊」這種章節名。反向連結（誰提到了夕）不另外存，要用時全文搜 `ak/characters/xi` 就是答案。

**給人看的白話層另開一個庫，長得跟原文庫一模一樣但內容是白話。** 原文庫是唯一真相；白話庫是模型寫的摘要，每篇最後一行寫明「根據原文庫哪個節點的哪個版本寫的」，原文一改它就會被標成過期。建庫的 agent 只掛原文庫、看不到白話庫，所以白話永遠不會污染真相。問答 agent 兩個庫都掛：先查白話庫快速回答，拿不準再翻原文。白話庫不必一次全做，誰被問到就做誰。

**git 是這一切的版本、歷史、審核與搬家工具，不再另外記任何「誰改、何時」。** 語料是一個 git、知識庫是另一個 git；節點靠 commit 編號指著語料；一個節點一個 commit，隊長審核就是看 diff，模型判錯了就 revert 那個 commit；要知道某條連結是誰在哪天判的，`git blame` 就有。aos 本體的 `memory` 工具完全不改。

要你拍板的只有幾題，列在第四節；其餘是在你定的路上補細節。

## 二、設計

### 2.0 分層一句話（C-52）

| 層 | 管什麼 | 不管什麼 |
|---|---|---|
| aos 本體 `memory`／`memory_write` | 資料夾樹、讀寫、`節點#/指標` 讀、全文 find、多庫捷徑 | 不認 tag、連結、別名、索引、git（**本規劃對 aos 本體零改動**） |
| arknights 線的定義（playground `defs/`） | `kb_slug`、`kb_store`、`kb_mentions`、`kb_link`、`kb_tag`、`kb_lint2`、`kb_sync`、`kb_find`、`kb_search`、`linker`、`plainer`、`qa_ak`；名字表、tag 抽取規則、連結規則、白話庫 | 不碰 aos 工具內部；不在節點裡記誰改何時 |
| 隊長／審視 agent | 跑 `kb_sync --status`、決定哪批過期要重抄、新增 tag 抽取規則、審 git diff、revert 錯判 | 不手改節點內容（審視 agent 本身的設計交給 evolve-design） |
| 人 | 蓋過英文名、核准新 tag 類目、讀白話庫 | — |

### 2.1 節點結構：身份、命名、別名、版本

**概念**：節點的身份＝語料檔路徑（`from`），永遠唯一。slug 只是 ASCII 把手，由身份機械導出、第一次導出即凍結。原文的版本＝語料 repo 的 commit（`rev`）。

**機制**

- 名字表按類別一檔：`ak/index/names/<class>.json`，鑰匙是 lore 路徑，值是 slug 與學到的別名。`kb_slug <lore路徑>` 查表；查不到就拼音生成（`[a-z0-9]+(-[a-z0-9]+)*`），同類別撞名依序加 `-2`、`-3`，寫回表後凍結。人要蓋過就直接改表（例如幹員改用官方英文名），改前該 slug 若已被連結引用，工具拒改（表裡有 `frozen` 就是這個意思）。幹員類可選從遊戲資料的 `appellation` 欄取官方英文名（見方向題 1）。
- 別名併進名字表（不另設分片檔），由 `linker` 回的 `alias_of` 寫入，值記判定者。同一別名對到多個目標時兩邊都留，比對時標為模稜。
- 候選名字來源：**只有頂層五類**（characters／operators／places／events／factions）的檔名與別名；evidence 子檔（`基本資訊`×159 這類結構名）不當候選。這一條直接把目前 2,732 個候選砍到約 1,400。
- `source.json` 加 `rev`：抄的是 `git -C lore show <rev>:<from>` 的內容，不抄工作樹（146 個未追蹤草稿一律不進庫）。`sha256` 照舊。
- lint 規則 1 改為「`'\n'.join(paras)` 逐 byte 等於 `git show rev:from`」——lint 只管節點內部一致，不管語料有沒有新版；新舊是 `kb_sync` 的事。
- 索引檔是工具的資料，不是給 agent 讀的節點：不受 2 KB 建議約束，不經 `memory_write` 寫入（所以 8000 bytes 硬限不適用），一條一行、鑰匙排序，讓 git diff 一眼看得出改了哪筆。`ak/index/README.md` 一行告訴 agent「這裡是工具資料，請用 `kb_find`／`kb_search`」。

**JSON 範例**

`ak/index/names/characters.json`
```json
{
  "description": "lore path -> frozen slug and learned aliases. Tool-owned (kb_slug, kb_link). One entry per line.",
  "entries": {
    "lore/characters/夕.md": {"slug": "xi", "frozen": true, "aliases": {"煮傘居士": "llm:sol"}},
    "lore/characters/陳.md": {"slug": "chen", "frozen": true},
    "lore/characters/晨.md": {"slug": "chen-2", "frozen": true}
  }
}
```

`ak/places/poshan-zhen/source.json`
```json
{
  "from": "lore/places/婆山鎮.md",
  "rev": "5d9bedd",
  "sha256": "7472…bfa1",
  "paras": ["### 婆山鎮（畫中天地）", "", "實為十二代理人之一「夕」…", "", "詳見：[…](../evidence/places/婆山鎮_畫中天地.md)"]
}
```

**版本與更新（`kb_sync`）**

- `kb_sync --status [rev]`（預設 lore HEAD）：對每個節點比 `node.rev..rev` 之間 `from` 是否在 `git diff --name-status` 裡；印出過期清單。零 token。
- `kb_sync <class>/<slug> [rev]`：重跑 S2 存檔 → 對 links.json 每條用 `name` 在新 `paras` 找第一次出現、改寫 `in`；找不到的把 `in` 設 `null`（lint 會擋，`kb_link` 只把這些送 linker 重判，並附上舊判定當提示）→ S5 重算 tag → S6 lint → commit `Sync places/poshan-zhen to lore@<rev>`。
- 白話庫的過期判定同一支工具順便做（見 2.4）。
- 什麼時候跑：隊長或審視 agent 在輪次邊界跑，不做自動監聽（方向題 4）。

**誰負責**：`kb_slug`／`kb_store`／`kb_sync` 腳本；`linker` 只處理模稜與重判；人蓋名字；aos 本體不參與。

### 2.2 tag 體系

**概念**：tag＝`facet:value` 字串，全部由語料結構機械抽出；一種 facet＝`kb_tag` 裡一條抽取規則；tags.json 是可重算的快取（lint 規則 7 已經這樣定）。模型不產 tag，語意分類是白話層或問答的事，不是 tag 的事。

**機制**

- facet 白名單寫在 `kb_tag` 的程式裡，每個 facet 標明抽取來源。現有：`class`（lore 第一層目錄）、`group`（同目錄 INDEX 分組小標）。候選新 facet：`category`（events 的「分類」欄）、`origin`／`race`（operators 的「檔案」欄）。新增 facet＝改程式一處＋全庫重算，由隊長提、人核准。
- 怎麼查：
  - 零新機制的路：tag 是字串，`memory find "group:炎國／歲"` 就會命中所有帶這個 tag 的 `tags.json`。限制是 20 筆截斷、無排名。
  - 多筆、多條件的路：`kb_tag --index` 掃全庫 tags.json 生 `ak/index/tags.json`（facet → value → 計數）；`kb_find --tag class:places --tag group:炎國／歲` 取交集印節點路徑。
- agent 怎麼知道有哪些 tag：根 `ak/README.md`（ELI5，進 system prompt）只列 facet 名與一句用法；值的清單在 `index/tags.json`，要用才讀。

`ak/places/poshan-zhen/tags.json`
```json
{"tags": ["class:places", "group:炎國／歲"]}
```

`ak/index/tags.json`
```json
{
  "description": "facet -> value -> node count. Rebuilt by kb_tag --index.",
  "facets": {
    "class": {"places": 41, "characters": 686},
    "group": {"炎國／歲": 12}
  }
}
```

**誰負責**：`kb_tag` 抽與建索引；`kb_find` 查；隊長提新 facet；人核准；aos `memory` 不認 tag（方向題 5）。

### 2.3 連結的節制規則

**概念**：連結是「這段原文提到了哪個實體」，不是「每個字出現在哪」。一個節點對一個目標一條；目標只能是有自己檔案的頂層實體；反向連結不存、現查。

**規則（寫進 `kb_link` 與 lint）**

1. **一目標一條**：同一節點指向同一 `to` 只留第一次出現那段。婆山鎮 16 條會收成約 7 條。
2. **只連頂層五類實體**：目標必須是 `ak/<五類之一>/<slug>`；不連 evidence 子檔、不連自己、不連章節名。
3. **三種來源、兩種成本**：原文裡現成的 Markdown 連結（`[山](安東尼.md)`）→ `by: rule`，零 token；唯一且非單字的名字命中 → `by: rule`；單字名、多候選、模型補的 → `by: llm:<級>`。
4. **`to` 一律是節點路徑**，不分 pending／ok：slug 機械可得，節點還沒建也先指過去；「存不存在」是讀的時候查檔案系統，不存欄位。`retarget` 全庫掃描刪除。
5. **位置只到段落**：`in` 用 `source#/paras/N`；字元區間 `at` 拿掉（B3 已證明模型給的區間常錯、腳本要校正，而它沒有任何讀者）。lint 規則 3 改成「`name` 出現在第 `in` 段」。
6. **反向連結現查**：`kb_find --to ak/characters/xi` 等於 grep 全庫 links.json；agent 自己用 `memory find "ak/characters/xi"` 也行。

`ak/places/poshan-zhen/links.json`
```json
{
  "links": [
    {"name": "夕", "in": "source#/paras/2", "to": "ak/characters/xi", "by": "llm:terra"},
    {"name": "畫中人", "in": "source#/paras/2", "to": "ak/events/huazhongren", "by": "rule"},
    {"name": "煮傘居士", "in": null, "to": "ak/characters/xi", "by": "llm:sol"}
  ]
}
```
（第三條是 sync 後找不到位置的樣子：`in: null`，lint 擋下、`kb_link` 送 linker 重判。）

**誰負責**：`kb_mentions` 出候選（含原文 Markdown 連結）、`kb_link` 寫檔與去重、`linker` 判模稜；aos 本體不解析連結。

### 2.4 「給人看」那層：白話庫與問答 agent

**概念**：原文庫 `ak` 是唯一真相。白話庫 `ak_plain` 是衍生品，路徑一對一鏡射，每篇記自己依據的原文快照；只許從 `ak` 流向 `ak_plain`，不許回流。問答 agent 是「現做的、跨節點的白話」；白話庫是「做好放著的、單節點的白話」。兩者靠同一條規則不脫節：都只能引用 `ak/...#/paras/N`。

**機制**

- 白話庫是另一個 memory 根：`ak_plain/<class>/<slug>.md`，第 1 行同原文庫標題，第 2 行一句摘要（`memory ls` 會印這句），最後一行 `source: ak/<class>/<slug>/source@<sha256 前 12 碼>`。
- `plainer` agent（低級模型即可）讀一個節點的 `source.json` 寫一篇；由 `kb_plain <class>/<slug>` 腳本起它、檢查最後一行格式、commit。不當 place_run 的固定步驟，誰被問到才做（方向題 3）。
- 過期：`kb_sync --status` 順帶比 `ak_plain` 每篇的 `source@` 與現在 `source.json` 的 sha256，不符就列為過期；過期的重做或刪掉，不修補。
- 掛法用現有多庫方案 A：建庫的 agent（linker、plainer）的記憶根只有一條捷徑 `ak`；`qa_ak` 的記憶根有 `ak` 與 `ak_plain` 兩條捷徑。
- `qa_ak` 的查法順序：`kb_search`（名字表＋別名 → 節點路徑）→ 讀 `ak_plain` 該篇 → 不夠再讀 `ak/.../source#/paras/N` → 都沒有才 grep `lore/`。每個論點仍附 `ak/...#/paras/N` 出處。
- 不做白話庫的 lint（沒法機械驗語意）；靠抽查與 git revert。

`ak_plain/places/poshan-zhen.md`
```
# 婆山鎮 (poshan-zhen)
炎國一座被「夕」畫進畫裡的小鎮，畫中人事件的舞台。
（白話正文……）
source: ak/places/poshan-zhen/source@7472a1b2c3d4
```

**誰負責**：`plainer` 寫、`kb_plain` 起與驗格式、`kb_sync` 標過期、`qa_ak` 讀；人讀白話庫；隊長抽查。

### 2.5 git 的角色

- **語料版本**：節點的 `rev` 指語料 repo 的 commit；只抄已 commit 的內容。知識庫不複製語料，靠 `lore` 捷徑＋`rev` 指過去；搬家（C-83）時兩個 repo 一起 pull，`kb_sync --status` 第一件事就是確認 `rev` 在本機 lore 裡找得到。
- **知識庫版本與歷史**：一節點一 commit（`Add places/poshan-zhen`、`Sync places/poshan-zhen to lore@<rev>`、`Plain places/poshan-zhen`），名字表與節點同一個 commit。節點裡不記誰改、何時（照 knowledge-write 裁題 4）；要問就 `git log -- ak/places/poshan-zhen`、`git blame links.json`。
- **審核與撤銷**：隊長審核＝看 diff；模型判錯＝`git revert` 那個 commit，再重跑。這就是「事後抽查」的具體形式。
- **誰碰 git**：只有腳本（`place_run --commit`、`kb_sync`、`kb_plain`）；agent 一律不碰（已是現狀）。aos 本體工具不碰 git（已定）。
- **可重建性**：整庫＝語料@rev ＋ 名字表（含別名）＋ links.json 裡的 `by: llm:*` 判定。其餘（paras、tags、索引、白話）全可重算。所以備份的重點是這三樣，它們都在 git 裡。
- **先不做**：多隻建庫 agent 同時 commit 同一個 repo 會撞 `index.lock`；現在串行，之後要並行時改成「寫檔並行、最後由 place_run 一次 commit」。多建庫 agent 的排程交給 kernel-nest。

### 2.6 碰到別題的地方

- 新工具（`kb_slug`、`kb_sync`、`kb_find`、`kb_plain`、`plainer`）的 `_metainfo` 與他者觀測：交給 evolve-design。
- 審視 agent 怎麼長、什麼時候由它替隊長跑 `kb_sync`：交給 evolve-design。
- `kb_*` 工具能不能叫 `bash`、寫入路徑約束：交給 tool-evolve。
- 多隻 plainer／linker 並行時的排程、本機模型一次只載一個：交給 kernel-nest。

## 三、與既有條文的衝突

| # | 哪條 | 衝突在哪 | 各自後果 | 推薦 |
|---|---|---|---|---|
| 1 | knowledge-write 裁題 4「知識庫不做 metadata，要歷史放 git」 | `source.json` 的 `rev`／`sha256`、白話篇的 `source@sha` 行，形式上是「關於內容的資料」 | 嚴格讀：這些也不准放，過期判定就只能逐 byte 重比全庫（慢、且白話篇無從判過期）。寬鬆讀：它們是「指向原文哪個版本」的內容指標，不是「誰改何時」 | 採寬鬆讀，條文補一句：**禁的是編輯者與時間，不禁內容來源與版本指標**。`rev` 是語料的 commit、不是知識庫自己的歷史，沒有搶 git 的工作 |
| 2 | AK/01「節點文 ≤ 2 KB」、`memory_write` 8000 bytes 硬限；隊長 B3 代定「別名分片 ≤ 8,000 bytes」 | 名字表全庫一類會到幾十 KB | 照節點規矩分片：全庫上百片、每次查要讀多片、git diff 散在多檔。不分片：`memory read` 讀它會截斷在 8000 | 索引檔**不是節點**：工具擁有、工具寫、agent 不直接讀。一類一檔、一條一行。aos 的限制只約束經 `memory_write` 寫的東西，這裡不經過它，無衝突；撤銷 B3 分片代定 |
| 3 | 隊長 B3 代定①「pending 連結指 `lore:` 原檔，建節點後 `retarget` 掃全庫改指」 | 本規劃讓 slug 機械可得，`to` 一律直接指節點路徑 | 留 pending/ok 兩態與 retarget：多一個狀態欄、多一個全庫掃描步驟、lint 多兩條規則。改掉：少三樣東西，代價是 slug 一旦被引用就不能改（名字表 `frozen`） | 改掉，C-56 做減法。不寫遷移，現有 2 節點重跑 |
| 4 | C-42 註「頂層簡介／index 盡量少」、根 README 每回合進 system prompt | `read ak/characters` 會列 686 行子節點、超過 8000 bytes 被截斷 | 接受截斷：agent 偶爾看到 `[truncated]`，無害。分桶（`ak/characters/a/…`）：路徑變醜、連結變長。改 aos `memory` 加「子節點超過 N 個只印計數」：aos 本體多一個參數 | 接受截斷，各類別 README 寫一句「N 個節點，請用 find 或 kb_search」。aos 不改；真的痛再談通用參數 |
| 5 | lint 規則 1「逐 byte 等於原檔」（現行比工作樹） | 原文一改 lint 就紅，但那其實是「過期」不是「壞」 | 維持：語料一更新全庫 lint 紅，分不出壞與舊。改比 `git show rev:from`：lint 只管內部一致，過期另查 | 改比 `rev`。lint＝一致性，sync＝新鮮度，各管一層（C-52、C-53） |
| 6 | 隊長 B2 定的 `at` 字元區間、lint 規則 3 驗區間 | 本規劃拿掉 `at` | 留：每條連結多一組易錯數字、B3 已需腳本校正、沒有讀者。拿掉：失去字級定位，白話層要高亮時得現算 | 拿掉；要高亮時 `name` 在段裡找即可 |

查過不衝突、順手記下免得再查：`in: source#/paras/N` 與 `to: ak/…` 都是 links.json 的資料，`memory` 不解析；要讀段落走 `memory read ak/…/source#/paras/2`（P3 已支援），不會拿去 ls／find（N-62 範圍內）。`kb_sync` 讀語料 repo 的 git 是讀輸入資料的公開介面，不是偷看下層（C-52 11-06 讀法）。JSON key 全小寫（C-54）。白話庫另開根＋捷徑掛載＝多庫方案 A 原樣。

## 四、方向題

**1. slug 怎麼來**
- A 拼音機械生成＋名字表人工蓋過（幹員可從遊戲資料 `appellation` 取官方英文名）：零 token、建節點前就能指；缺點是沿用拼音不算嚴格「英文」，幹員若不取官方名會長成 `kaierxi`。
- B 保留 `namer` 模型命名：名字比較像人取的；每個新實體一次 luna 呼叫（約 1,700 token），且節點建好前無法確定 slug，`retarget` 必須留。
- **推薦 A**。已凍結的 40 個地點名本來就是拼音，你已看過；幹員那 400 個用官方英文名。

**2. 連結粒度**
- A 一目標一條，位置到段落：婆山鎮 16→約 7 條，lint 少兩條規則，sync 重定位簡單。
- B 每次提到一條，含字元區間：保留全部出現位置，可做高亮；量是 A 的兩三倍，模型給的區間要校正。
- **推薦 A**。「別濫用」首先是數量。

**3. 白話庫怎麼建**
- A 懶做：誰被問到（或人點名）才寫；庫長得慢，但 token 只花在有人要看的節點上。
- B 全做：節點建好就跟著寫一篇；5,000 篇×約 3,000 token≈1,500 萬 token，且語料一更新就有一批過期要重寫。
- C 不建白話庫、只靠問答 agent：零維護；但同一個節點每問一次重花一次（每題 1.6 萬 token），人沒有可以直接翻的東西。
- **推薦 A**，用 terra 級以下的模型寫；等問答命中率顯示哪些類別常被問，再對那類批次補做。

**4. 語料更新了，知識庫多久跟一次**
- A 輪次邊界由隊長（之後審視 agent）跑 `kb_sync --status`、挑過期的重做：可控、重判集中、便宜。
- B 每次語料 commit 自動 sync：永遠最新；但語料一批改 19 檔，每批都會觸發一批 linker 重判，成本不可預期。
- **推薦 A**。語料主要在長人物，知識庫這一輪只做 8～10 個地點，過期量很小。

**5. tag／索引要不要進 aos 本體的 `memory`**
- A 不進：tag 只是 `tags.json` 裡的字串，`memory find` 現成能查；多條件交集走這條線的 `kb_find`。aos 零改動。
- B `memory find` 加 `--tag` 或多關鍵字 AND：所有庫都受惠；但 `memory` 得知道「tag 長什麼樣、放在哪個檔」，碰 C-52；且要動 aos 本體。
- **推薦 A**。等第二條線也要 tag 時再談通用化，那時才知道通用的樣子。

## 五、落地小步（交 gpt 照圖施工，每步一句完成條件）

每步各自一個 commit；不寫舊版相容，現有兩節點刪掉重建。所有程式輸出、索引檔 `description`、commit 訊息英文。

1. **`kb_slug`**：輸入 lore 路徑，查 `ak/index/names/<class>.json`，無則拼音生成、同類撞名加 `-2`、寫回並 `frozen: true`。完成條件：對頂層五類全部 1,373 個檔跑一遍得 1,373 個不重複 slug、0 次模型呼叫、重跑結果逐 byte 相同。
2. **`kb_store` 加 `rev`**：改讀 `git -C lore show <rev>:<from>`，預設 rev＝lore HEAD；檔案在該 rev 不存在則報 `SourceMissing`。完成條件：婆山鎮 `source.json` 含 `rev`，且 `paras` 與 `git show` 輸出逐 byte相同。
3. **`kb_lint2` 改規則**：規則 1 比 `git show rev:from`；規則 3 改為 `name` 出現在第 `in` 段（`in: null` 算失敗）；刪規則 4、5；規則 5 改為 `to` 必須合 `ak/<五類>/<slug>` 格式。完成條件：兩節點通過；手改一段原文的副本不通過並指出哪條規則。
4. **`kb_mentions` 收窄候選**：候選＝頂層五類 stem＋名字表別名＋原文 Markdown 連結目標；輸出按目標分組、每組列出現段落。完成條件：婆山鎮候選不含任何 evidence stem，「夕」為一組且列出 9 處。
5. **`kb_link` 改寫**：欄位只剩 `name,in,to,by`；一目標一條取首現；`to` 由 `kb_slug` 算；`alias_of` 寫回名字表 `aliases`；刪 `retarget` 與 pending 邏輯。完成條件：婆山鎮 links.json ≤ 8 條、lint 通過、程式裡找不到 `retarget` 與 `state`。
6. **`kb_tag --index` 與 `kb_find`**：前者掃全庫 tags.json 生 `ak/index/tags.json`；後者支援多個 `--tag` 交集與 `--to <節點路徑>` 反查，印節點路徑一行一個。完成條件：`kb_find --tag class:places` 印出兩個節點；`kb_find --to ak/characters/xi` 印出婆山鎮；索引重跑逐 byte 相同。
7. **`kb_sync`**：`--status [rev]` 列過期節點與過期白話篇；`<class>/<slug> [rev]` 重存、按 `name` 重定位 `in`、找不到設 `null`、重算 tag、lint、commit `Sync … to lore@<rev>`。完成條件：在 lore 的測試分支於婆山鎮檔第 2 段前插一段並 commit，sync 後所有連結 `in` 自動加一、lint 通過；再把「夕」字全刪，sync 後對應連結 `in: null` 且 lint 指出。
8. **`place_run` 接線**：S1 改叫 `kb_slug`、S4 用新 `kb_link`、刪 namer 相關步驟；`--check` 照新規則重建比對。完成條件：兩個地點從零重建各 1 次 LLM 呼叫以內、`--check` 通過、`steps.json` 記到每步 token 與秒。
9. **根與類別 README**：`ak/README.md` 十行內寫這是什麼、五類、facet 名、三句用法（find 找名字、`kb_find` 找 tag、`source#/paras/N` 讀原文）；`ak/<class>/README.md` 一行「N nodes, use find」。完成條件：`memory read ak` 輸出 ≤ 1,500 bytes。
10. **`ak_plain` 與 `plainer`／`kb_plain`**：`plainer` 定義（terra 級）讀 `source.json` 寫白話篇；`kb_plain <class>/<slug>` 起它、驗首行與末行格式、commit `Plain …`。完成條件：婆山鎮白話篇存在且末行 sha 與 `source.json` 相符；改動 `source.json` 後 `kb_sync --status` 把它列為過期。
11. **問答掛載**：`qa_ak` 記憶根改為含 `ak`、`ak_plain` 兩條捷徑的資料夾；`kb_search` 改讀名字表（含別名）→ 節點路徑，再回退 lore grep。完成條件：凍結的 10 題重跑一次，報表列出每題 token、答對與出處正確，並標出哪幾題命中 `ak_plain`。
12. **索引檔 README**：`ak/index/README.md` 一行說明工具資料、請用 `kb_find`／`kb_search`。完成條件：`memory ls ak/index` 顯示該句。
