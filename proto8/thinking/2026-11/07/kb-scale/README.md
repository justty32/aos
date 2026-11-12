知識庫到全庫規模的頂層設計：節點的身份是原文檔的路徑，英文名由程式從拼音算出來後凍結，一個節點對同一個目標只連一條，白話另開一個庫並記住依據哪一版原文，版本、歷史與撤銷全交給 git。

← [2026-11-07](../README.md)

以 fable 的 02 為底稿、opus 隊長補全；跟同批 [evolve-design](../evolve-design/README.md)、[tool-evolve](../tool-evolve/README.md) 對齊，也回應 [arknights-kb-audit](../arknights-kb-audit/README.md) 挖到的命名與連結問題。五題方向題使用者 11-07 傍晚都選推薦（見「使用者裁定」）；「代定」是隊長替他做的小決定，每條可翻案。

## 使用者裁定（11-07 傍晚，40 題選項框）

回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)；回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進。

- **ks-1**（節點的英文門牌，要由程式算，還是讓模型取名？）：選 A「拼音機械生成，人可在名字表蓋過；幹員可以從遊戲資料的 appellation 欄取官方英文名（例 kaltsit）」。幹員官方英文名讀的 `corpus/raw` 不在語料 git 追蹤裡，`by` 記 `human`。
- **ks-2**（同一個節點提到同一個對象，要連幾條？）：選 A「一個目標一條，位置到段落」。
- **ks-3**（給人看的白話庫，要一次寫完嗎？）：選 A「懶做，有人問到才寫」；等問答紀錄顯示哪些類別常被問，再對那類批次補做。
- **ks-4**（原始語料改了，知識庫多久跟一次？）：選 A「在輪次邊界跑 kb_sync --status，挑過期的重做」，不做自動監聽。
- **ks-5**（找標籤要交給 aos 的 memory find 嗎？）：選 B「memory find 加選填 tag，讀 memory 公開的 _tags.json 約定；多 tag 交集仍在這條線」。

## 設計（結論）

### 各層管什麼（C-52）

| 層 | 管什麼 | 不管什麼 |
|---|---|---|
| aos 本體 `memory`／`memory_write` | 資料夾樹、讀寫、`節點#/指標` 讀、全文 find、多庫捷徑；`find` 的選填 `tag`（讀 memory 自己公開的 `_tags.json` 約定） | 不認連結、別名、名字表、語料版本、git |
| arknights 線的定義（試驗場 `defs/`） | `kb_slug`、`kb_store`、`kb_mentions`、`kb_link`、`kb_tag`、`kb_lint2`、`kb_sync`、`kb_find`、`kb_plain`、`linker`、`plainer`、`qa_ak`、`kb_search`；名字表、tag 抽取規則、連結規則、白話庫 | 不碰 aos 工具內部；節點裡不記誰改、何時 |
| 隊長（之後換審視 agent） | 輪次邊界跑 `kb_sync --status`、挑過期的重做、提新 tag facet、審 git diff、revert 錯判 | 不手改節點內容 |
| 人 | 蓋過英文名、核准新 tag facet、讀白話庫 | — |

### 節點：身份、命名、別名、版本

- **身份**＝語料檔路徑（`source.json` 的 `from`，相對語料 repo 根），永遠唯一。**slug**＝從身份機械推出的 ASCII 門牌，第一次推出就凍結。原文版本＝語料 repo 的 commit（`rev`）。
- **名字表**：每類一檔 `ak/index/names/<class>.json`，鑰匙是 lore 路徑，值 `{"slug", "by": "pinyin"|"human", "aliases"?}`；在表裡就是凍結，不帶 `frozen` 欄。人要蓋過就改那條、`by` 改 `human`；舊 slug 已被別的節點連結引用時 `kb_slug` 拒絕，印出引用者。
- **拼法**（代定 1）：漢字逐字轉無聲調拼音、音節連寫不加連字號；拉丁字母轉小寫照留（`Ace` → `ace`）；其他字元（`／`、`·`、`「」`、空白）一律變一個 `-`，頭尾 `-` 去掉。例：婆山鎮 → `poshanzhen`，塔拉／深池 → `tala-shenchi`。
- **同音**：同類撞名依序加 `-2`、`-3`；整批初始化照 lore 路徑 Unicode 排序登記，之後新增拿下一個空號；登記後不改。不同類不會撞（`ak/characters/xi` 與 `ak/operators/xi`）。不改用帶聲調拼音。
- **別名**：名字表鑰匙只能是 lore 裡實際存在的檔；沒有自己那份檔的名字（煮傘居士、陳暉潔）只能進某條的 `aliases`。`kb_lint2` 驗鑰匙檔存在、別名不等於別條鑰匙的檔名主幹（否則 `NameAliasConflict`）。同一別名對到多個身份時兩邊都留、標模稜兩可、交 linker 判。namer 退役。
- **同名跨五類**優先序（代定 2）：characters → places → factions → events → operators；個別情況用別名蓋過。
- **候選名字只取五類**：五類檔 stem＋名字表別名＋原文現成 Markdown 連結目標；evidence 子檔的結構性檔名不進候選。比對先篩類別、再挑最長；被濾掉的長命中要退回試較短的名字。
- **`source.json` 加 `rev`**（完整 40 碼，代定 3）：內容取自 `git -C <語料 clone> show <rev>:<from>`，用試驗場自己的 clone（`ws/corpus/arknights`），使用者語料 repo 唯讀；未 commit 的草稿不進庫。lint 規則 1＝`'\n'.join(paras)` 逐 byte 等於 `git show rev:from`；原文有沒有新版是 `kb_sync` 的事。
- **`kb_sync`**：`--status [rev]` 看每個節點的 `from` 有沒有在 `git diff --name-status <node.rev> <rev>` 裡、白話篇比 `source@` 與現在的 sha256，印過期清單、不花 token；`kb_sync <class>/<slug> [rev]` 重存原文 → 每條連結用 `name` 在新 `paras` 找第一次出現改寫 `in`、找不到設 `null` → 重算 tag → lint → 只把 `null` 的送 linker 重判（附舊判定）→ commit。
- **索引檔**（名字表、`ak/index/tags.json`）由工具寫、不經 `memory_write`；帶 `summary` 鍵（代定 4，memory 只認 `title`／`summary`）；一條一行、鑰匙排序。`ak/index/README.md` 寫一句「這裡是工具資料，請用 `kb_search`／`kb_find`」。

### tag

- 形狀 `facet:value`，全部由語料結構機械抽出；一種 facet＝`kb_tag` 一條抽取規則；tag 檔是可重算的快取；模型不產 tag。
- 放節點資料夾的 `_tags.json`（代定 5）：`{"tags": ["class:places", "group:炎國／歲"]}`。
- 單一 tag：`memory find {"tag": ...}`（aos 本體）。多 tag 交集、計數：`kb_tag --index` 產 `ak/index/tags.json`，`kb_find --tag A --tag B`。根 `ak/README.md` 只列 facet 名與一句用法。
- 現有 facet：`class`、`group`；候選：`category`、`origin`／`race`。新增 facet 改程式一處並全庫重算，由隊長提、人核准。

### 連結的節制

1. 一個目標一條，記第一次出現的段（代定 6）。
2. 只連五類實體：`to` 必須是 `ak/<五類>/<slug>`。表外提及由 linker 回 `alias_of` 寫進名字表別名；對不上任何身份的不連。
3. `by`：現成 Markdown 連結與唯一且非單字的名字命中記 `rule`；單字名、多候選、模型補的記 `llm:<級>`；一律字串。
4. `to` 一律寫節點路徑，不分 pending／ok；目標存不存在讀時看檔案系統；`retarget` 刪掉。
5. 位置只到段落：`in` 寫 `source#/paras/N`，不記字元區間 `at`；lint 驗 `name` 出現在第 `in` 段。
6. 反向連結不另存：`kb_find --to ak/characters/xi` 或 `memory find`。
7. links.json 是工具沿著走的「提及→身份」解析結果，正是 evolve-design「要讓工具沿著走的才做連結」那種。

```json
{"links": [{"name": "夕", "in": "source#/paras/2", "to": "ak/characters/xi", "by": "llm:terra"}]}
```

### 給人看的那層

- 原文庫 `ak` 是唯一真相；白話庫 `ak_plain/<class>/<slug>.md` 是衍生的，內容只從 `ak` 流向 `ak_plain`。第 1 行同原文庫標題、第 2 行一句摘要、末行 `source: ak/<class>/<slug>/source@<sha256 前 12 碼>`。
- `plainer`（terra 級以下）只回文字，`kb_plain` 驗首末行後寫檔並 commit（代定 7）；建庫的 agent 記憶根只掛 `ak`，看不到白話庫。
- 過期由 `kb_sync --status` 列出，重寫或刪掉，不修補；白話庫不做語意 lint，靠抽查與 git revert。
- `qa_ak` 記憶根掛 `ak` 與 `ak_plain` 兩條捷徑；查法 `kb_search` → `ak_plain` → `ak/.../source#/paras/N` → grep `lore/`；出處只能引 `ak/...#/paras/N` 或 `lore/...`。

### git 的角色

- 節點的 `rev` 指語料 clone 的 commit；搬機器時兩個 repo 一起 pull；`kb_sync --status` 先確認每個 `rev` 在本機 clone 找得到，否則 `RevMissing`。
- 知識庫一個節點一個 commit（名字表變動同 commit）；節點裡不記誰改、何時，查 `git log`／`git blame`。審核看 diff、錯判 `git revert` 再重跑。
- 整體比對：整庫從零重跑後 `git status --porcelain` 為空＝一字不差。
- 只有腳本（`place_run --commit`、`kb_sync`、`kb_plain`）碰 git；agent、aos 工具不碰。
- 要保住的只有語料@rev＋名字表（含別名）＋`by: llm:*` 的連結判定，其餘可重算。
- 先不做：多隻建庫 agent 並行 commit（要並行時改成寫檔並行、`place_run` 統一 commit）。

### 錯誤代號（代定 8）

`SourceMissing`、`RevMissing`、`SlugBad`、`SlugReferenced`、沿用 `NameAliasConflict`。

### 與既有條文的讀法

- knowledge-write 第 4 題「不記誰改、何時」：`rev` 是語料版本，不算衝突。
- 名字表大於 8 KB：索引檔不經 `memory_write`，一類一檔，不分片（撤銷 B3 的分片）。
- `memory read ak/characters` 超過 8000 bytes 被截斷：接受，各類別 README 寫一句「N 個節點，請用 find 或 kb_search」。
- 改 lint 規則 1 比 `rev`、拿掉 `at`、`to` 直指節點（不寫遷移，現有節點重建）。
- 語料 repo 唯讀：要改語料的測試在試驗場 clone 的臨時副本上做。

## 落地狀況

- 已做：命名、名字表、連結形狀、五類優先序、`rev` 與 lint 規則 1 由 arknights 第二輪 B6 照做（[代定清單](../arknights-kb/代定清單.md) 25～27）；`memory find` 認單一 tag 在 impl-plan 批 1。
- 未做（代定 27 排後；之後的 thinking 沒有施工紀錄）：`kb_sync`、`kb_tag --index`／`kb_find`、各類 README、白話庫（`ak_plain`／`plainer`／`kb_plain`）、`qa_ak` 改掛兩庫。
