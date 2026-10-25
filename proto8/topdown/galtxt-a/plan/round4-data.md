# round4 補充：設定全部拆成格（fable，2026-10-25）

← [round4.md](round4.md)（主規劃，不重寫）｜實作偏離記 [round4-impl-notes.md](round4-impl-notes.md)｜依據：[C-72 JSON＝單檔的檔案系統](../../../docs/CONCEPTS/01-設計理念.md)、[fn-grow 六級](../../../thinking/2026-10-24-fn-grow.md)、[round2 收攏判準 § 1](round2-collapse.md)

使用者 10-25：「場景條件，背景故事，人物設定，都可以用結構化來表示，也就是json，拆的愈散，後續愈方便。」

一句話：`data/` 裡每個「一條特質、一個口癖、一個稱呼、一個地點事實、一個事件節拍、一句模板」各自一格，格有穩定 id；程式節點查格、控制變量只動一格、規則與梯度指到格。散文只在最後一步渲染（給腦的 brief、給評審的 rubric）。只拆**宮澤柚葉×文化祭收攤教室**這個收窄範圍，晴子、佐伯、河鹿堂不動。

## 1. 盤點：哪些還是散文／大段

| 檔 | 散文或無 id 的大段 | 誰在吃它 |
|---|---|---|
| `data/cast.json` 柚葉 | `voice` 三條特質是陣列、無 id；`catchphrase` 是一條用「／」串起的字串（`compose.py` 用 `split("／")` 拆——程式在拆散文）；`habits` 三條各混兩個動作（「別過臉、耳根發紅」）；`markers`、`never` 無 id；`source` 一段 120 字。口癖「哼／真是的」散在五處：`cast.catchphrase`、`cast.markers`、`styles.傲嬌.habits`、`voice/_entry DEFAULT_TICS`、`templates.deny/cover` | brief、compose、voice |
| `data/places.json` 教室 | `details` 四句各混兩件事（建物＋聲音）；「彩帶從天花板垂落」是**事件狀態**不是地點；`fixed` 關鍵詞無結構 | brief（只給腦）、judge `details[:3]` |
| `data/styles.json` 傲嬌 | `narration` 一段散文混三個洩底動作＋兩個幫忙動作；`deny/yield/cover/reveal/ooc/endings/habits/ng` 八張表是陣列、無 id；`note` 散文；「嘴硬心軟」跟 cast.voice 重複 | brief → `rules.contrast` → lint |
| `data/address.json` | 六階每階的字面是散文（「姓氏＋君（男用君）／姓氏＋同學」）；`registers.how` 散文；本範圍只用 rank 2 | brief（只取 `register`） |
| `data/forbidden.json` | A～D 四陣列無 id、D 類沒有「為什麼錯」欄；`note` 散文 | brief → lint |
| `data/bench/Q16.json` | `setting`、`speaker_note` 兩段散文（第二份人物卡＋第二份場景）；`points` (a)(b)(c) 三段散文沒對到 `dims.json` 的維度；`guard.must` 無 id | brief（抄 `speaker_note`、`setting` 給腦）、pick |
| `data/templates.json` | 每個槽的候選句是裸字串：distill 追加時 § 5.6 要標的 `distilled_epoch`／`teacher` 沒地方放；`by_detail.ribbon` 用名字對題目的 `detail`，沒指到任何格；`source` 300 字 | compose |
| `data/dims.json`、`hints.json`、`lint_switches.json` | 已是表；`source` 都是百字散文；維度沒說「哪些格定義它」；hints 無 id | pick、write、brief |
| `plan/examples/cls-*.json` | `event` 一句散文（實際是 場景＋道具＋嘴上說的＋手上做的 四格）；`detail: "ribbon"` 是名字、指不到格；`intent: "餘溫"` 字串 | brief 照抄給腦 |
| `grader/system.v2.txt` | 「像柚葉」那行內嵌人物描述（傲嬌、文藝社、嘴硬心軟、逞強是保護色）＝**第三份柚葉卡**，跟 cast 不同步 | 評審 |
| `writer/tools/beat`、`voice`、`brain.py tsun()` | `DEFAULT`、`DEFAULT_TICS`、`GENERIC` 硬寫在程式裡 | 工具退路 |

## 2. 新結構

### 2.1 格與 id

- **一格**＝一個能被**單獨命中**（lint 標記）、**單獨引用**（模板槽、rubric）、**單獨改動**（控制變量、distill 追加）的事實。形狀最小 `{"text": "…"}`，可選 `marker`（lint 比對的字面，沒有＝同 `text`）、`src`（corpus 節號，短）、`tags`、`by`（`author`／`distill@e3 teacher=writer@agent`）、`since`、`retired`。
- **id＝JSON key 路徑**（C-72）：`cast.yuzu.tic.03` ↔ `data/cast/yuzu.json#/tic/03`。規則：第一段＝`data/` 下的資料夾，第二段＝檔名（不帶 `.json`），其餘＝JSON pointer。檔長成資料夾（`cast/yuzu/tic.json#/03`）時解析器先試資料夾再補 `.json`（同 aos-exec N-61 找名字的順序），**id 不變**——跟 fn-grow「呼叫方從第 2 級起只寫名字」同一條。
- 序號兩位、只增不重用（刪了標 `retired: true` 留著，不然舊 grad 的引用懸空）；具名的用英文短 key（`ribbon`、`r2`），中文留在 `text`。
- `source` 一檔寫一次在檔內 `_metainfo`（§ 6），格只放 `src: "固化/01§1"`。

### 2.2 檔（每個檔＝一個實體；格是檔內路徑）

```
data/
├─ cast.json        舊三卡留；「宮澤柚葉」那格改成 {"$ref": "cast/yuzu.json"}（brief 解一層，同 _metainfo 的 $ref 慣例）
├─ cast/yuzu.json   trait.01～03 特質｜tic.01～05 口癖（marker 給 lint markers、voice tics）｜gesture.01～05 小動作
│                   （別過臉／耳根發紅／瀏海往耳後撥／眼神飄向窗外／踮腳；reveal: true 的 marker 併進 rules.contrast.reveal）
│                   ng.01～03｜calls_lead.r0～r4（r2: {"01": "你", "02": "喂"}）｜called_by_lead.r0～r4｜short、display、type: "style.tsun"
├─ places.json      舊；「教室」改 {"$ref": "place/classroom.json"}
├─ place/classroom.json   fact.01～05 永久事實（木造本館／走廊地板會響／上下滑窗關不緊／夕陽斜進／黑板）各帶 keyword；
│                   不放文化祭的任何東西（那是場景狀態）
├─ scene/closeup.json     ★場景條件＝背景故事：place "place.classroom"、cast、when {season, time}、rank 2、intent、
│                   mood.01～03（疲累後的滿足／淡淡的失落／餘溫，從 Q16 setting 拆）｜state.01～03（攤位拆完／彩帶垂落／喧鬧退去）｜
│                   prop.ribbon／poster／lights｜detail.ribbon {prop, say, do, role: "train"}、poster {…, role: "train"}、
│                   lights {…, role: "verify", held_out: true}——say＝嘴上、do＝手上，正是反差的兩半
├─ styles.json      舊；`types.傲嬌` 改 {"$ref": "style/tsun.json"}；`ng_marks` 不動
├─ style/tsun.json  deny.01～05｜yield.01～07｜cover.01～04｜reveal.01～06（通用洩底字：紅／小聲／手卻／沒走／偷瞄／描）｜
│                   ooc.01～05｜ending.01～04｜ng.01～03｜order.01 {"text": "先否認再讓步", "rule": ["deny", "yield"]}（反差的定義本身是一格）
├─ templates.json   槽候選改成格：generic.open.01 {"text", "uses": ["scene.closeup.state.03"]}、
│                   by_detail.ribbon.deny.02 {"text", "uses": ["scene.closeup.prop.ribbon"], "by": "author"}；id 前綴 `tpl.`
├─ templates.distilled.json   ★distill 唯一寫的檔（人寫的 templates.json 訓練中 bytes 不變）；格多 for: "scene.closeup.detail.poster"、teacher、since
├─ bench/Q16.json   context／guard／answer 不動；setting、speaker_note 刪、改 scene: "scene.closeup"、speaker: "cast.yuzu"；
│                   points 改 point.a {"text", "dims": ["承接", "反差"]}、b {…, ["語域", "像柚葉"]}、c {…, ["護欄"]}；guard.must 加 id（must.01、02）
├─ dims.json        每維多 cells：反差 ["style.tsun.order.01", "style.tsun.deny.*", "style.tsun.yield.*"]、
│                   洩底 ["cast.yuzu.gesture.*[reveal]", "style.tsun.reveal.*"]、語域 ["cast.yuzu.calls_lead.r2.*", "cast.yuzu.tic.*", "styles.ng_marks"]、
│                   像柚葉 ["cast.yuzu.trait.*"]（評審 rubric 從這些渲染）、文筆／承接 []（腦量、沒有格）
├─ lint_switches.json、hints.json   值改格（switch.contrast_order {"on": true}、hint.01 {"text": "借景"}）；形狀不然不變
└─ forbidden.json、address.json、samples.json、route.json、bench/Q01.json   不動（§ 4 預測拆了沒用）
```

題目 `cls-*.json`：`event` 改成**可省**，寫 `"scene": "closeup", "detail": "ribbon"`；brief 用固定句型從 `scene.closeup.detail.ribbon` 的 `say`／`do` 渲染出跟現在一字相同的 `event`（有寫 `event` 就照抄＝人的覆寫）。`intent` 從 `scene.closeup.intent` 來。

### 2.3 誰長成資料夾、誰留單檔（判準）

- **留單檔**（第 2 級）：一個實體一檔，格是 key 路徑。預計 `cast/yuzu.json` ≈ 3 KB、`scene/closeup.json` ≈ 2 KB、`style/tsun.json` ≈ 2.5 KB，都遠低於 B-3 的 8 KB／300 行。
- **長成資料夾**（第 3～4 級）的觸發，照 round2 § 1 N-1 與 fn-grow 第 3 級：(a) **兩個寫者要各自 diff**——人寫的與 distill 寫的分檔，所以 `templates.json`＋`templates.distilled.json` 並列；再多一個場景或合計 > 8 KB 才長成 `templates/closeup.json`＋`closeup.distilled.json`；(b) 有非 JSON 伴隨檔（要附 corpus 原文摘錄 `.md`）；(c) 要靠檔案權限隔離——`bench/Q16.json` 的正解日後若要用檔案層擋住寫手（C-64 借 Linux 權限）就拆成 `bench/Q16/{prompt.json, answer.json}`，**這圈不做**（隔離已由測試掃 stack 守住）；(d) 檔 > 8 KB 或 > 300 行。
- **不拆成資料夾的理由**：`data/` 已有 `fs_needs: [git_tracked, isolation]`，格層沒有新的檔案系統需求；一格一檔會讓 brief 開 30 個檔、metatable 多 30 行，違 KISS（C-56）。

## 3. 消費者怎麼改

| 誰 | 改法 |
|---|---|
| `brief.py` | 新增 `cells.py`（根下伴隨檔，標準庫）：`resolve(id) → (path, pointer, value)`、`load_ref(obj)` 解一層 `$ref`、`expand("cast.yuzu.gesture.*[reveal]")`。brief 照舊組 `brief.json`／`rules.json`，但每個值從格取：`catchphrase` → `tic.*.text` 串成現在的字串（給腦的格式不變）；`habits` → `gesture.*.text`；`place.details` → `fact.*.text`＋`scene.state.*.text`；`event` 渲染；`speaker_note` 從 `trait`＋`tic` 渲染一句。`rules.contrast` 多 **`cells` 對照表** `{"才不是": "style.tsun.deny.01", "耳根": "cast.yuzu.gesture.02", …}`（marker → id），`brief.json` 多 `cells_used: [id…]`。晴子、佐伯走舊路徑、產物 bytes 不變。 |
| `tools/lint` | 讀 `rules.contrast.cells`；輸出多 `hits: {"反差": [id…], "洩底": [id…], "語域": [id…]}`（命中的格；沒對照表＝`[]`）。分數算法不變。 |
| `pick.py` → `rate.py` | `score.json` 每份多 `hits`（照抄 lint）；`rate.py` 彙成 `ratings.json.style:傲嬌.cell_hits {id: 次數}`——這是「哪一格在起作用」的計數，判斷器與人看。 |
| `judge.py`、`grader/system.txt` | rubric 的「像柚葉」行改成佔位 `{traits}`，judge 從 `dims.json.像柚葉.cells` 解出 `trait.*.text` 渲染進 task（system.txt 只留評分尺度）；cast 改一字、rubric 跟著變，第三份卡消失。 |
| `writer/compose.py` | 槽候選是格：`pick()` 回 `(text, id)`；`fmt` 多 `{prop}`＝`scene.detail[detail].prop` 的 text；`tics` 從 `cast.yuzu.tic.*`（不再 split 字串）。`templates.distilled.json` 合進 `by_detail`（同槽追加在人寫的後面）。`hard.jsonl` 行多 `cells: ["scene.closeup.detail.poster"]`（缺的那格）與 `cells_hit`（lint 回的）。 |
| `writer/tools/beat`、`voice` | 仍是純函數、不讀檔（契約不變）；`DEFAULT`／`DEFAULT_TICS` 留著當退路並註明「退路，不是資料」；compose 一律把 `tics` 傳進去，退路只在 compose 都壞時才會用到。日後 `tools/deny/` 等子工具抽出時，它們查的就是 `style.tsun.deny.*`。 |
| `train/optimize` `distill` | 新模板只寫 `templates.distilled.json`：`by_detail.poster.deny.01 {"text", "for": "scene.closeup.detail.poster", "teacher": "writer@agent", "since": 3}`；`hard.jsonl` 那行 `resolved_epoch`＋`resolved_cells: [新格 id…]`。`switch` 動作改 `switch.contrast_order.on`。 |
| `grad.json` | `steps[].diff` 多 `cells: {"+": [id…], "-": [id…]}`（`cell_hits` 前後比：從沒命中變有命中／反過來）；`steps[]` 多 `changed_cells: [id…]`（這一步動作改了哪幾格：distill 追加的、switch 翻的；extract／stage 是 `[]`）。`sum` 多 `cells_touched` 計數。這樣 `_metainfo`／梯度能說「這次改動跟哪一格有關」。 |
| `human/questions.json` | 不改；人評樣本 `why_picked` 可帶 `cells_hit`（讓人看「程式說它命中了洩底格 gesture.02，像不像」）。 |

## 4. 拆到什麼粒度算夠；預測

**停止條件（三問，全否就不拆、留陣列）**：(1) 有沒有程式節點會只讀這一格？(2) 控制變量時會不會只動這一格？(3) 梯度、難例、規則會不會只指到這一格？「耳根發紅」拆成「耳根」「發紅」三問全否（lint 用 marker「耳根」已經夠）→ 停。一個檔 20～40 格是這圈的量級；超過 80 格先懷疑拆過頭。

| 預測有用（之後對照 `cell_hits`／`grad.cells`／`hard.cells` 有沒有引用） | 預測拆了沒用（這圈不拆；若實測有人引用再拆） |
|---|---|
| `tic.*`（lint markers、voice tics、模板三處共用一源）｜`gesture.*[reveal]`（洩底維度直接命中它）｜`deny/yield/cover.*`（反差命中、beat 三槽、distill 切出來的歸類）｜`scene.detail.*`（題目開關、難例缺的那格、templates `for`）｜`tpl.*` 每句（distill 標 teacher；人評「像套公式」能指到句）｜`dims.*.cells`（rubric 渲染、梯度歸因）｜`Q16.point.*.dims`（正解要點對到維度，判斷器硬規則可引用） | `forbidden` 逐條（lint 只要清單；沒有節點改單一禁詞）｜`address` 其他五階、`registers.how`｜晴子、佐伯、河鹿堂卡｜`place.fact.*`（沒人量它；只給腦）｜`hint.*`（三個值、整組切換）｜`scene.mood.*`（只有腦看）｜`samples` |

**實測對照**（步驟 9 真腦 4 epoch 後、寫進 round4-measure.md）：列每格被 `cell_hits`／`grad.cells`／`hard.cells`／`tpl.uses` 引用的次數；0 次的格下一輪**併回陣列**（fn-grow「降級也成立」）；預測錯的兩邊都記進 lessons。

## 5. 插在哪一步；測試

**位置：步驟 3b**——步驟 3（寫手三階，正在做）完成、測試 5、6、8 綠之後，步驟 4 rollup 之前。理由：步驟 4 起 `grad.json`／`hard.jsonl`／`distill` 都要寫格 id，先有格再長旁檔，不然回頭改三處；步驟 3 的 compose 現在用名字對 `by_detail`，改成格只是把裸字串包成物件，傷口最小。3b 分兩半先後 commit：**3b-α 資料與 brief**（§ 2 的檔、`cells.py`、brief 渲染；產物等價）→ **3b-β 消費者**（lint hits、pick/rate、judge rubric、compose、hard 行）。

§ 10 增的測試（`Round4T`，假腦；每個要證明能變紅一次）：

- **3b-1 格解析**：`cells.resolve("cast.yuzu.tic.03")` 回 `data/cast/yuzu.json`＋`/tic/03`＋`{"text": "才沒"}`；`expand("cast.yuzu.gesture.*[reveal]")` 只回 `reveal: true` 的；不存在 → `CellMissing`；在 `tree_copy` 把 `cast/yuzu.json` 拆成 `cast/yuzu/` 資料夾（`tic.json` 等）→ 同一 id 解到同值、brief 產物 bytes 相同（長成資料夾 id 不變）。
- **3b-2 等價**：Q01、scene（晴子）改前後 `brief.json`、`rules.json` bytes 一字不變；Q16、cls-ribbon 的 `rules.contrast.{deny,yield,cover,reveal,ooc}` 改前後**集合**相同、`total` 相同（既有 `test_fill_q16`、`test_fake_skill_table` 不動照綠）；`cast.json` 裡找不到「哼」以外第二份口癖字面（去重）。
- **3b-3 lint hits**：「哼，才沒有。不過……也不是不能接受」→ `hits.反差 == ["style.tsun.deny.03", "style.tsun.yield.01"]`（照 id 序）、`反差 1.0`；旁白「（宮澤柚葉別過臉，耳根有點紅。）」→ `hits.洩底` 含 `cast.yuzu.gesture.02`；每個 hit 都 `resolve` 得到且其 `marker` 在輸入裡；沒 `cells` 表 → `hits` 全 `[]`、分數不變。
- **3b-4 event 渲染**：`cls-ribbon.json` 去掉 `event`、留 `scene`＋`detail` → `brief.event` 等於原 `event` 字串；兩者都寫 → 照抄 `event`；`detail` 不在 `scene.detail` → brief 退 1 `DetailMissing`（題目壞；跟 compose 的 `TemplateMissing` 難例不同——那是模板缺、題目對）。
- **3b-5 rubric 渲染**：judge 的 task 含 `trait.01～03` 三條字面；`tree_copy` 改 `trait.01.text` → task 跟著變、`system.txt` bytes 不變、假腦分數不變；`grader/system.txt` 裡不再出現「嘴硬心軟」。
- **3b-6 模板格**：`templates.json`＋`distilled` 每格有 `text`、`uses` 全部 `resolve` 得到；program 階跑 cls-ribbon → `answer.txt` 含 `scene.closeup.prop.ribbon.text`；跑 cls-poster → `hard.jsonl` 行 `cells == ["scene.closeup.detail.poster"]`、`cells_hit` 非空；Q16 正解字串不在 `data/` 任何格的 `text`（既有掃 stack 的斷言照舊，多掃 `data/templates*.json`）。
- **3b-7 score → ratings**：`score.json` 每份有 `hits`；`rate.py` 後 `ratings.json.style:傲嬌.cell_hits` 的計數＝手算；`dims.json` 每維 `cells` 全部 `expand` 得到（`文筆`／`承接` 為 `[]`）；`moved_by` 既有斷言不變。
- **3b-8 `_metainfo` 與 M7**：`data/_metainfo.children` 列出 § 2.2 每個新檔；每個格檔 `_metainfo.counter_cells`＝程式數出來的格數；`metatable` 表行數不因格增加（格層不成行）；步驟 4 起的 M7 清單加「人寫的格檔（`cast/`、`place/`、`scene/`、`style/`、`templates.json`）訓練前後 bytes 不變，只有 `templates.distilled.json`、`lint_switches.json` 變」。

既有測試影響：`test_fill_q01`／`test_scene`／晴子的 `total` 不變（3b-2 直接驗）；`test_fill_q16` 正解隔離掃 stack 照舊（`cells_used` 只有 id 與設定字面，不含正解）；`test_tree_shape`／`test_metainfo_consistent` 的檔清單與 `reads` 加 `data:cast/yuzu.json` 等；`test_hard_cases` 加 `cells` 斷言；`test_tool_contract` 不動（beat／voice 契約沒變）。真腦（測試 22）只多看 task JSON 有沒有 `cells_used`，不斷言分數。

## 6. 對 `_metainfo` 的影響

- **格檔自己的描述放檔內 `_metainfo` key**（C-72：JSON 當資料夾，`js["_metainfo"]` 就是那個資料夾的 `_metainfo`）：`{"summary", "kind": "data", "source"（整檔只此一處）, "counter_cells", "cells": {"trait": 3, "tic": 5, "gesture": 5, "ng": 3, "calls_lead": 7}, "writers": ["author"]｜["train/optimize distill"], "readers": ["brief", "compose"]}`。`cells.py` 解析 id 時跳過 `_metainfo` key。
- **`data/_metainfo`**：`children` 多 § 2.2 的檔各一行（跟現在 `cast.json` 一行一樣的粒度）、`counter_cells` 總數；`writes` 多 `templates.distilled.json`（它是 `data/` 裡唯一有程式寫者的檔，`fs_needs` 補 `shared_write`——round2 § 1 說要人寫出來的那條）。
- **metatable、rollup 不看格層**。樹中有樹的原則（round4 § 3.3）是只看直接子樹；`data/` 是葉子樹，格是它的內部。rollup 根的 `children.data` 一行 `{kind: data, counter_cells, counter_distilled}` 夠了。格層只出現在三個地方：`ratings.cell_hits`、`grad.cells`／`changed_cells`、`hard.cells`——都是「跟哪一格有關」的指針，不是表。
- **要看格就用工具**：`meta/cells/_entry`（純程式、標準庫，第 3 級）：`cells ls [前綴]`、`cells get <id>`、`cells where <id>`（grep 整棵樹的 `uses`／`cells`／`cell_hits`／`hard.jsonl`，印誰引用它）——步驟 8 工具收尾一起做；metatable `--suggest` 不加格的候選。
- `_metainfo` 通用表要不要收 `counter_cells`／`cells`：這圈不進通用表，跟 round4 § 13 第 6 條一起等使用者拍。

## 7. 預算與風險

- 工：3b-α 半天（手拆 ≈ 120 格、`cells.py` ≈ 80 行、brief ≈ 40 行）；3b-β 半天（lint、pick/rate、judge、compose 各 15～40 行、測試 8 個）。不花腦 token。
- 風險：(a) 拆時字面改動讓 lint 命中集合變 → 3b-2 的集合斷言抓；(b) 格 id 進了 `brief.json` 被真腦看到＝多餘 token——`cells_used` 放 `rules.json` 那側或 write.py 送腦前刪掉，擇一記 impl-notes；(c) distill 切句歸到哪個 `deny.*` 格需要字面比對，比不到就新開格、`by: distill`，不硬塞。
