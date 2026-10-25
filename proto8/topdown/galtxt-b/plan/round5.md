# galtxt-b 第 5 輪：樹中有樹——子樹的對外描述、貢獻、照樹走的優化器（只規劃；fable，2026-10-25）

← [galtxt-b](../README.md)｜前情：[round4](round4.md)（人評 §6、第 2 層 tune §4d、白名單 §4c、budget §7 **沿用**；§3 評級欄位與 §4 train 由本檔**改寫**）、[round3-collapse](round3-collapse.md)、[optimize](optimize.md)｜依據：`_metainfo` [M1～M10](../../../thinking/2026-10-24-metainfo.md)（M6 外層自報優先、kernel 第一版不往下彙總；M7 實測不回寫）、[fn-grow 六級](../../../thinking/2026-10-24-fn-grow.md)、C-52（上層不知道下層是什麼）、AGENTS「每層只指向下一層、不存下層細節」、C-55／STRUCTURE 四級成長、C-56

使用者 10-25 四句（頂層轉述；最後一句以它為準）：①「把目標限縮到單一性格，單一場景」；②「整棵樹的 _metainfo 收攏成一張表，不是一件好事，我想要的是一棵樹中有很多棵樹，嵌套再嵌套，這樣樹可以重複利用」；③「進行改進時，_metainfo 就是很好的依據。改進的時候可以只改進特定子樹。也就是根據各子樹的貢獻去做優化」；④「**限縮角色設定，限縮故事背景。盡可能控制各種變量，然後我預期子樹會很深層…，因爲最終目標是讓整棵樹都不依靠 LLM**」。

## 0. 一頁看懂

- **終點**：整棵樹不靠 LLM（galtxt「笨模型＋鷹架＋護欄」、固化階梯同一方向）。LLM 是起步的鷹架；訓練的主方向＝把用到腦的子樹一棵一棵換成純程式子樹（模板、規則、搜尋、表）而分數不掉；成果除了分數，還看整棵樹的腦用量往 0 走（§1b）。
- **範圍（控制變量）**：傲嬌（宮澤柚葉）一份精簡設定＋一個固定小場景全部寫死成資料；測試題只在**兩個開關**上變（§1）。評分往傲嬌的細項長：`反差`（嘴硬心軟）、`節奏`、`含蓄`、`承接`、`文筆`、`多樣性`。
- **子樹會很深、反向收攏不急**：純程式要扛原本 LLM 的事得拆很細（節拍→句式→填充→口癖插入…），只併真的空殼層（§1b、§2d）。
- **樹中有樹**：每個資料夾的 `_metainfo` 對外描述「整棵子樹」，分五區——**宣告**（作者寫）、**彙總** `rollup`（從直接子樹算上來）、**評級** `ratings`（跑出來的品質）、**貢獻** `contribution`（對整棵樹的分數與成本影響）、**腦依賴與固化進度** `uses_llm`＋`solid`（還靠不靠腦、蒸餾到哪）。上層只讀直接子樹的描述，不看孫子（§2）。
- **貢獻怎麼量**：每個可關的子樹在 `_metainfo` 宣告一個關閉開關（`ablation`），訓練場把它關掉跑同一組題，分數差＝貢獻、measure 的 token 佔比＝成本（§3）。像反向傳播的「責任分配」，但不是鏈式法則、是有限差分、一棵一次前向。
- **優化器照樹走**：讀根的直接子樹描述 → 挑最值得動的一棵（弱點×貢獻＋成本）→ 鑽到葉 → 提一條改動 → 只在那棵子樹裡 apply → verify → 重跑 → 只沿被改那條路往上重算（§4）。優化器自己也是一棵樹，tune（第 2 層）讀它的描述。
- **預算**：一個場景 4 變化 × 2 次＝8 次跑樹 ≈ 13.6 萬；加量一棵子樹的貢獻（4 次）≈ 5.5 萬；優化器 0.7 萬 → **一輪 ≈ 20～25 萬**（§6）。

## 1. 範圍：單一性格、單一場景、只動兩個開關

**全部寫死成資料**（`train/set/base.json`，也是 brief 的輸入；下面每格都是常數，訓練期間不動）：

| 格 | 值（固定） | 出處 |
|---|---|---|
| 人物設定（精簡成一張卡 `brief/tables/cast.json#/宮澤柚葉`，只留這幾條） | 類型：傲嬌（主）＋書卷（副）；**特質 3 條**：嘴硬心軟（先否認再讓步再補一句遮掩）、只對放心的人凶、愛書成癡；**口癖 3 條**：「——才、才不是為了你」「你這人真是的」「幫我拿一下（不是拜託是命令）」；**稱呼**：她叫他「你」「喂」→直呼「佐伯」，他叫她「宮澤」（階 2）；**小動作 2 條**：撥瀏海看窗外、生氣踮腳；**禁語**：身高／矮／豆粒；**NG**：直白說喜歡、臉紅冒煙、真的惡毒 | `corpus/人物/宮澤柚葉.md`、`固化/01` §1、`固化/02` |
| 主角 | 既有卡，不動 | — |
| 背景 | 河鹿堂・四月・放學後；百葉窗的條狀光；爺爺在櫃台；她蹲在二手書竹籃前 | 店誌 §三、§四 |
| 關係 | 階 2，同社（文藝社）不同班；本場不升階 | dossier |
| 事件 | 同時伸手拿同一本文庫本 → 她嘴硬把書讓給他（「才不是留給你的，只是拿不動」）→ 爺爺蓋梅花章 → 收尾 | `固化/01` 傲嬌範例句、店誌 §六 |
| 句數、旁白 | 6～9 句、旁白 ≤ 3 行 | — |
| `must_mention` | 「讓給／拿去」、「梅花章」 | — |

**只變的兩個開關**（`train/set/` 四題＝2×2）：

| 開關 | 值 | 影響什麼 |
|---|---|---|
| `intent` | `鉤`（收尾留下次的引子）／`靜`（收尾定格景） | 收尾拍（B7）與 director 的 D 軸 |
| `turn` | `嘴硬`（讓步時否認在前：「才不是…只是拿不動」）／`逞強`（讓步時藉口在前：「我拿不動而已。給你。」） | 反差拍（B5）的句法；評分細項 `反差` 看得出差別 |

題名：`鉤_嘴硬`、`鉤_逞強`、`靜_嘴硬`、`靜_逞強`。其他一切不變。benchmark 無正解（19 題沒有宮澤×河鹿堂）；critic 照傲嬌 rubric 打。害羞、文靜停掉（round4 §1 作廢；q01／q08 留 examples/ 當回歸測試）。round4 §8 A 段「加兩張人物卡」改成只加宮澤這張精簡卡；`samples.json` 加 Q16 的對白（宮澤柚葉、文化祭收攤，去掉正解）當語料錨。

為什麼只兩個開關：變量越少，純程式子樹越容易扛——固定的設定全部進表（固化階梯第 1 級），開關只有 2×2 種組合，模板與規則枚舉得完；分數的差才能歸給「子樹改了」而不是「題目不同」。

## 1b. 固化：把靠腦的子樹一棵一棵換成純程式

### 1b-1. 現況：三個靠腦的節點

| 節點 | 做什麼 | 一次 token（實測） | 純程式能不能扛（在 §1 的固定範圍內） |
|---|---|---|---|
| `draft/tools/director` | 排 beat 表 | ≈ 3.4k | **能，立刻**：範圍固定後 beat 表只有 2×2 種（intent 決定 B7、turn 決定 B5 句法），一張 `plans.json` 枚舉完；round3／§3a 的 `plan_template()` 就是它 |
| `draft/tools/writer` | 照表寫句 | ≈ 10k（兩次） | **能，但要拆深**：節拍→句式→填充→口癖插入→組稿，每層一棵純程式子樹（1b-2）；句式與填充從 LLM 歷次產出蒸餾（1b-3） |
| `judge/tools/critic` | 含蓄、承接、文筆三維 | ≈ 3.6k | **部分**：五個維度已是程式（護欄、語域、反差、節奏、多樣性）；剩三維用「語料統計＋規則」逼近、人評當錨校正（1b-4） |

### 1b-2. writer 固化後的子樹（預期很深；只畫到第三層，再往下由實作時拆）

```
draft/tools/writer_solid/            純程式：beat 表 → 台詞；_metainfo.uses_llm: false
  _entry                             單子：python3 assemble.py（組稿）
  beats/                             每一拍一棵子樹：拍名 → 候選句式清單（照 base.json 的事件與開關）
    b0_open/   b1_meet/  b2_speak/  b3_topic/  b4_hand/  b5_turn/  b6_stamp/  b7_close/
      _entry                         單子：python3 pick.py（這一拍挑句式）
      phrases.json                   這一拍的句式庫（含 ${slot}、說話者、intent／turn 條件、prior）——從 LLM 產出蒸餾
      _metainfo
  slots/                             填充表：${道具}、${讓步語}、${否認語}、${口癖}（照人物卡）→ fill.py
  turn/                              反差拍的「否認→讓步→遮掩」三段組裝（傲嬌的核心；turn 開關在這裡分岔）
  tics/                              口癖與小動作插入器：一場 ≤ 2 個口癖、≤ 2 個小動作、不連續（預算來自定點 04）
  guard/                             組稿後自檢：直接叫 ../../../../lib/lint（捷徑）；不過就換下一個候選（搜尋，gen_v0 的 DFS＋下界剪枝的小版）
  _metainfo                          rollup：llm_tokens 0；ratings 跟 writer 比
```

`draft/_entry` 照 `_metainfo.ratings` 選路（§5 reroute）：`writer_solid` 的 `ratings["傲嬌"].val` 不低於 `writer` 時走它，否則走 writer。兩棵並存一段時間（A/B），這就是「固化而分數不掉」的驗證點。

### 1b-3. 「固化」這種改動（優化器白名單新的一種 `solidify`）

```json
{"kind": "solidify", "target": "draft/tools/writer", "into": "draft/tools/writer_solid",
 "distill": {"from": "runs/*/**/out/*/answer.txt（score.val ≥ ok 的稿）", "by": "beat（用 plan.json 對回每句屬於哪一拍）",
             "keep": "每拍每說話者 ≤ 8 句、去重、把人物卡裡的口癖與道具換成 ${slot}"},
 "why": "writer 佔 59% token、反差維度 0.55 是弱點、歷次產出已累積 ≥ 16 稿"}
```

程式（`train/apply` 的 `solidify` 分支，純程式、零 token）：① 收集訓練場裡分數 ≥ ok 的稿子，用同次的 `plan.json` 把每句對回拍；② 每拍每說話者抽句式：把道具名、口癖、對方稱呼換成 `${slot}`，去重、計 prior（出現次數、所在稿的分數）；③ 寫進 `writer_solid/beats/<拍>/phrases.json`；④ `writer_solid` 其餘程式是固定的殼（第一次由實作者寫，之後 solidify 只換表）；⑤ 不改呼叫方（reroute 另一條改動、由 ratings 決定）。蒸餾的是**我們自己 LLM 的產出**（不是 corpus 逐字），版權線沒問題；corpus 的句子仍只當 few-shot 與規則來源（idea 礦脈 §4.3 的版權設計線）。

優化器什麼時候提 `solidify`：被挑的子樹 `uses_llm: true`、`solid.stage` 是 `scaffold`、訓練場累積的合格稿 ≥ 16（`solid.distill_ready`，record 算）；同一棵的 `solidify` 之後一輪的 `effect` 決定留不留——分數不掉（`val_delta ≥ −σ`）就 reroute 過去、writer 標 `solid.stage: "replaced"`（留著當對照與備援，不刪）。

### 1b-4. 評分器要不要固化、怎麼校正

critic 也靠腦（3.6k／題、≈ 21% token）。固化它跟固化 writer 不一樣：**尺不能跟被量的東西一起學**，不然是 Goodhart。做法：

1. 程式維度先頂上：`反差`（lint `tsundere_turn`）、`節奏`、`護欄`、`語域`、`多樣性` 已是程式；`含蓄`、`承接`、`文筆` 做程式近似——`含蓄`＝禁語 A 類零命中＋情緒詞（喜歡／心跳／想你）零命中＋留白符號（……）≥ 1；`承接`＝每句跟前一句有共用名詞或指代（簡單重疊率）；`文筆`＝句長分布（短句比例）＋ 跟語料錨的 3-gram 相似度（Tier 1 語料統計，round4 §2b 沒做的那項，現在範圍小做得了）。
2. **LLM critic 降成抽樣尺**：每輪只對 k 稿裡的 1 稿問腦（token −50%），其餘用程式分；兩者的一致率（同 round4 `calibration`）連兩輪 ≥ 0.8 → critic 標 `solid.stage: "sampled"`；人評（6 筆）對程式分的一致率 ≥ 0.8 才算程式尺可信。
3. **critic 被改時全樹 `contribution` 標 stale**（§7 第 7 條）；程式尺的規則只能由人評校正表觸發改（round4 §9-5 不變）。
4. 終點：critic 只在人評那 6 筆上跑（當人的助手），執行期零 LLM。

### 1b-5. 結論要能答的四題（`rounds/<輪>.json.solid_report`，record 算）

| 問 | 怎麼答（表的欄） |
|---|---|
| 哪些子樹已固化（0 token） | `uses_llm: false` 且 `rollup.llm_tokens.val == 0` 的子樹清單；本輪新固化的標 ★ |
| 哪些還靠腦、為什麼 | `uses_llm: true` 的子樹：`solid.stage`（scaffold／distilling／sampled／replaced）、`solid.blocker`（record 填：合格稿不足 n／分數掉 x／沒有程式近似） |
| 固化前後分數 | 每棵 `solid.before`／`solid.after`（`ratings` 快照：換路那一輪與前一輪） |
| 下一步最該固化哪棵 | 照 §4a 的挑選公式，但 `cost` 用 `llm_tokens` 份額、且只在 `uses_llm: true` 的裡面挑；輸出前三名與理由 |

整棵樹的腦用量：根 `rollup.llm_tokens.val` 每輪一個點，`rounds/*.json` 串起來就是「往 0 走」的曲線——這是跟分數並列的成果。

**評分細項（傲嬌版，照 round4 §2a 的級別長）**：`score.json.dims`：

| 維度 | 誰算 | 怎麼算 |
|---|---|---|
| `護欄` | lint（Tier 0） | 同前 |
| `語域` | lint（Tier 1） | 同前＋`topic_taboo` |
| **`反差`** | lint 新規則 `tsundere_turn`（程式）＋ critic | 程式：她至少一句含否認詞（才不是／別誤會／哼／隨便你）且同句或下一句有讓步（給你／拿去／也不是不行／…吧）＝1，有否認沒讓步＝0.5，都沒有＝0；critic 給 0～1「否認與讓步之間有沒有洩底動作」；取平均 |
| `節奏` | 程式 | 她的台詞平均 ≤ 18 字且含 ≥ 1 個「！」或破折號＝1；超過 28 字＝0；線性 |
| `含蓄`、`承接`、`文筆` | critic | 0～1 各一格（round4 §8 第 2 項） |
| `多樣性` | 程式 | 同題 k 稿 3-gram 重疊（round4 §2b） |

`val`（good／ok／bad）＝加權（`train/score/weights.json`：反差 0.3、含蓄 0.2、語域 0.15、護欄 0.15、文筆 0.1、承接 0.1；多樣性不進 val、另列）。

## 2. 子樹的對外描述：`_metainfo` 五區

### 2a. 格式

```json
{"summary": "…", "time_ms": {"val": 16000, "max": 600000}, "resource": ["llm", "cpu"], "llm_calls": {"val": 2, "max": 5},
 "…九軸與既有宣告 key…": "作者寫的，只有作者改（M6：外層作者自報優先；kernel 讀的是這一區）",

 "tree_id": "galtxt-b",                                   ← 只在根：這棵樹的名字（貢獻的 toward 用它）
 "subtrees": ["tools/director", "tools/plan_lint", "tools/writer"],   ← 直接子樹（相對路徑；捷徑也列、以 via 標）

 "rollup": {                                              ← 彙總：record 從直接子樹的 rollup（葉＝宣告）算上來；不碰宣告區
   "counter_nodes": 7, "counter_llm_nodes": 2,
   "time_ms": {"val": 15049, "max": 600000}, "llm_calls": {"val": 3, "max": 5}, "llm_tokens": {"val": 13839, "max": 15000},
   "resource": ["llm", "cpu"], "deterministic": false, "side_effect": true,
   "measured": {"counter_samples": 8, "time_ms": {"p50": 14200, "max": 19800}, "llm_tokens": {"p50": 13600, "max": 15900}},
   "rolled_at": "2026-10-26T…", "round": 1},

 "ratings": {"傲嬌": {"val": "ok", "反差": 0.55, "含蓄": 0.7, "節奏": 0.8, "文筆": 0.75, "承接": 0.8, "多樣性": 0.6,
                      "counter_samples": 8, "rated_at": "…", "round": 1},
             "human": {"傲嬌": {"val": "bad", "tags": ["太直球"], "counter_samples": 2}}},

 "contribution": {"galtxt-b": {                          ← 以 toward（根的 tree_id）為 key：搬去別棵樹不會誤用
   "method": "ablation", "off": "fallback", "counter_samples": 4, "measured_at": "…", "round": 1, "stale": false,
   "dims": {"反差": -0.30, "含蓄": -0.05, "節奏": 0.0, "文筆": -0.10, "承接": -0.15, "多樣性": +0.05},
   "val_delta": -0.6,
   "cost": {"share_tokens": 0.20, "share_time": 0.38}}},
 "ablation": {"env": "GALTXT_OFF_DIRECTOR", "off": "fallback", "note": "關掉＝draft 用模板 beat 表（純程式），不叫 director"},
 "responsible_for": ["反差", "承接"],                      ← 作者宣告：這棵子樹管哪些細項（零成本的先驗；貢獻量到後以量的為準）

 "uses_llm": true,                                        ← 宣告：這棵子樹（含底下）還靠不靠腦（record 用 rollup.llm_tokens 核對、不一致記 declared_gap）
 "solid": {"stage": "scaffold",                           ← 固化進度（record 寫）：scaffold（純腦鷹架）／distilling（已有蒸餾表、A/B 中）／sampled（只抽樣問腦）／replaced（已被純程式子樹取代、留作對照）／solid（純程式）
           "replacement": null,                           ← 取代它的純程式子樹（例 "../writer_solid"）
           "distill_ready": {"counter_samples": 12, "need": 16},
           "before": null, "after": null,                 ← 換路那一輪與前一輪的 ratings 快照
           "blocker": "合格稿 12 < 16"}
}
```

五區的規矩：

| 區 | key | 誰寫 | 什麼時候更新 | 搬走／被捷徑引用時 |
|---|---|---|---|---|
| 宣告 | 既有 M3 通用 key、`tree_id`、`subtrees`、`ablation`、`responsible_for` | 作者（人或生成樹的程式） | 改結構時 | 跟著資料夾走（同一個檔） |
| 彙總 | `rollup` | `train/record`（除錯用另有 `plan/metainfo_rollup.py`，只算不寫） | 只沿被改路徑往上重算（2c） | 跟著走；新父親讀到它就不用往下看 |
| 評級 | `ratings` | `train/record`（自動）、`human/import`（人） | 每輪，產出台詞的那條路（根、draft、writer）；其他節點不寫 | 跟著走：評級是「這棵子樹在某風格的表現」，換棵樹仍是它的表現（給的輸入形狀一樣時） |
| 貢獻 | `contribution[toward]` | `train/measure`（§3） | 量過才有；子樹被改後標 `stale` 直到重量 | 跟著走但**以 toward 分開**：新樹的 `tree_id` 不同＝沒量過，要重量 |
| 腦依賴與固化進度 | `uses_llm`（宣告）、`solid`（record 寫） | 作者／`train/record` | `uses_llm` 改結構時；`solid` 每輪（合格稿數、換路前後的快照、blocker） | 跟著走：`uses_llm` 是它自己的事實；`solid.replacement` 是相對路徑，搬走沒有那棵就標 `blocker: "replacement missing"` |

**上層只讀直接子樹的描述**：`subtrees` 列的那幾個資料夾各自的 `_metainfo`，讀 `rollup`、`ratings`、`contribution[自己的 tree_id]`；**不讀孫子**。孫子的事在子樹自己的 `rollup` 裡已經算進去了（AGENTS「每層只指向下一層」）。

### 2b. 跟 M1～M10 的關係與衝突

| 條 | 說什麼 | 這裡怎麼接 | 衝突？ |
|---|---|---|---|
| M1 三處同名 | 資料夾／JSON 物件／單子 | 五區都跟著 `_metainfo` 的位置走：葉子縮成單子時 `ratings`、`contribution` 進單子的 `_metainfo` key，`rollup` 刪（葉＝宣告即彙總） | 無 |
| M2 沿路第一份 | 找到第一份就停 | 讀子樹描述時也是：只開 `subtrees` 列的那一層 | 無 |
| M3 通用 key 全選填 | — | 五區新 key 都選填；沒 `rollup`＝沒算過，讀的人退回宣告 | 無 |
| **M6** 外層作者自報優先、kernel 第一版不往下彙總 | kernel 讀宣告、不自己加總 | kernel 照舊讀宣告區（不動）；**彙總放另一個 key `rollup`**，由訓練場算、給優化器與表看。宣告與 rollup 不一致時：kernel 信宣告，優化器信 rollup | **擦邊**：同一份檔兩個「這棵子樹多貴」的數字。處理：record 在 rollup 旁寫 `declared_gap`（宣告 val ÷ rollup val），差 > 2 倍的列進 `plan/metainfo_table.md` 的「宣告失準」給人回填宣告（M7 不自動回寫）。列 §7 第 1 條 |
| **M7** 實測不回寫 | kernel 量到的不回寫 | round4 §3c 已收窄：實測不回寫**宣告 key**；`rollup.measured`、`ratings`、`contribution` 是另外的 key、由 record／measure 寫 | 同 round4 §9-1，等使用者點頭 |
| M8 寫壞當沒寫 | — | 五區任一壞＝那一區當沒寫、record 記一筆、照跑 | 無 |
| M9 不加版本 | — | 五區不加 `ver`；要改意思換 key 名 | 無 |
| M10 跟 tool.json 分開 | 模型不看 `_metainfo` | **優化器是例外**：它的工作就是讀 `_metainfo`——但它讀的是「樹的描述」不是「工具說明」，而且只在訓練場、不在 galtxt-b 執行期的 prompt 裡 | 擦邊，列 §7 第 2 條 |

### 2c. 彙總怎麼算、何時重算

`rollup`（record 做；演算法放 `train/record/rollup.py`，`plan/metainfo_rollup.py` 只是同一支的唯讀殼）：

- **葉**（沒 `subtrees`）：`rollup` ＝ 宣告的 `time_ms`／`llm_*`／`resource`／`deterministic`／`side_effect` 原樣抄（沒宣告的就缺）＋ `measured`（這輪 measure.json 裡對得上這個節點的數字）。
- **非葉**：`counter_nodes`＝1＋Σ子；`llm_calls`、`llm_tokens`、`time_ms` 的 `val`＝Σ子的 rollup val（**乘上這一格一輪叫子樹的次數**：`calls` 裡可以寫 `{"path": "tools/writer", "counter_per_run": {"val": 1, "max": 3}}`，沒寫＝1），`max`＝Σ子 max × 次數 max；`resource`＝聯集；`deterministic`＝全 true 才 true；`side_effect`＝有一個 true 就 true（跟 10-24 metainfo 02 §4 的彙總法一致）。自己宣告的 `time_ms` 若比 Σ子大（黏合格自己的開銷）取大的。
- **捷徑子樹**：`subtrees` 列 `{"path": "tools/lint", "via": "link"}`，讀目標的 `rollup`，次數照 `calls`。
- **只沿被改路徑往上重算**：apply 改了子樹 S → record 從 S 的葉開始重算 S，再 parent(S)、…、根；兄弟不動（它們的 rollup 沒變）。每次重算寫 `rolled_at`、`round`。
- **評級**往上：根與 draft 的 `ratings` ＝ writer 的（產出台詞的那條路同一份數字，因為評的是整篇台詞）；不做平均。

### 2d. 重複利用、跟 fn-grow 與反向收攏怎麼接

- **搬去別棵樹**（`cp -a` 整個子資料夾）：宣告、rollup、ratings 跟著走；`contribution` 的 key 是舊 tree_id，新樹的優化器讀不到自己的 → 當沒量過（會先排一次量貢獻），舊的留著給人看。
- **被捷徑引用**（lib 那種）：同一份 `_metainfo`、兩個父親；`ratings` 共享（它描述這個函數自己）；`contribution` 兩棵樹各一個 key，互不干擾。
- **fn-grow 往上長**（檔→資料夾）：`_metainfo` 從單子 key 搬成資料夾檔（aos-grow 現在會把它刪掉——round3 §5 已列為缺；aos-fold 的 `_metainfo 跟著走` 規則反向也適用）。
- **反向收攏不急**（使用者：子樹會很深）：固化出來的 `writer_solid/beats/b5_turn/` 這種一層只有 `_entry`＋`phrases.json`＋`_metainfo` 的小資料夾**不算空殼**——它有自己的表、自己的評級、會被單獨量貢獻（關掉一拍的句式庫＝那一拍退回預設句）。只併真的空殼：只有 `_metainfo` 而沒有任何自己內容的容器層、或 `subtrees` 只有一項且那一項沒有獨立評級的。
- **反向收攏往下縮**（round3）：5→4 資料夾留著＝五區不動；→ 單子＝五區進單子的 `_metainfo`、`rollup` 刪；**併中間層**（子樹上提）＝被併掉那層的 `rollup` 消失、它的子樹改列進新父親的 `subtrees`，這些子樹的 `contribution` 標 `stale: true`（結構變了、量過的差值未必還對），沿新路徑重算 rollup。`plan/aos-fold` 的規格補這幾條（§5 工作清單）。

## 3. 貢獻怎麼量

### 3a. 做法：宣告一個關閉開關，關掉跑同一組題

每個「可以關掉而樹還跑得完」的子樹，在 `_metainfo.ablation` 宣告一個環境變數與關掉的方式；叫它的黏合格認這個變數（寫什麼就做什麼，C-56：開關是明寫的宣告，不是暗規則）。本樹可關的四棵：

| 子樹 | 開關 | 關掉＝ | 誰實作 |
|---|---|---|---|
| `draft/tools/director` | `GALTXT_OFF_DIRECTOR=1` | `fallback`：draft 用 `beats.json` 填模板 beat 表（optimize.md 第 1 名那支純程式，順便做了） | draft/_entry |
| `draft/tools/writer` 的自檢（`tools/lint` 那條捷徑） | `GALTXT_OFF_SELF_LINT=1` | `skip`：brain 不把 lint 放進 tools（writer 仍寫稿） | writer/brain.py |
| `check`（打回重寫） | `GALTXT_OFF_REDRAFT=1` | `skip`：check 照跑但 `final` 一律 true（第一稿定稿） | check/_entry |
| `brief/tables/samples.json`（語料錨 few-shot） | `GALTXT_OFF_SAMPLES=1` | `skip`：brief.samples 空 | brief/_entry |

不可關的：`brief` 本體（沒稿紙樹跑不動）、`judge/critic`（它是尺，關了沒分數——它的「貢獻」只有成本）、`lib/lint`（判準）、`idle`／`deliver`（流程）。這些的 `contribution` 只填 `cost`，`dims` 寫 `null`、`method: "none"`。

`train/measure` 格（新，純程式）：對指定的子樹 S，把 `ablation.env` 設成 1，跑 set 四題各 1 次（k_abl＝1；4 次 ≈ 5.5 萬 token），算每維平均 → `contribution[tree_id].dims[d]`＝（有 S 時的平均）−（關掉 S 的平均）；`val_delta` 同；`cost.share_tokens`＝measure.json 裡 S 那隻 agent 的 token ÷ 整題 token（director、writer 直接有；自檢＝writer 第 2 次問腦的 token；打回重寫＝第 2 稿起的 token；samples＝稿紙裡那段的字數估）。寫進 S 的 `_metainfo.contribution`，`stale: false`。

**一輪量幾棵**：round 0 量優化器第一步會挑的前兩名（照 `responsible_for` 先驗與成本挑）；之後每輪只重量被改的那一棵（4 次），有餘額再量一棵沒量過的。四棵全量完要兩輪。

### 3b. 會不準在哪（誠實寫）

1. **只量邊際、不量交互**：關掉 director 時 writer 還在、關掉自檢時 check 還會打回——量到的是「其他都在時少了它」的差，兩棵一起關不等於兩個差相加。
2. **關掉的方式決定數字**：director 關掉是「換成模板」還是「不給表」，差值不同；`off: fallback|skip` 寫在宣告裡，讀的人要看。
3. **雜訊**：k_abl＝1、4 題，一維的差 < 0.15 不要信（round4 §8 第 0 項先量 σ；傲嬌題 critic 的「含蓄」可能比文靜題抖）。`contribution` 帶 `counter_samples`，優化器的挑選公式對樣本少的打折（§4）。
4. **critic 看整篇**：它給的「反差 0.7」分不出是 director 排的拍好還是 writer 寫得好；只有關掉一棵才分得出——所以這套量法本來就是給 critic 這種整體評分器配的。
5. **成本份額是準的**（measure.json 直接有）；分數貢獻是估的。優化器用成本份額當「省錢」的依據可信、用分數貢獻當「哪棵該改」只是排序線索。
6. **結構改了舊數字就不算數**：標 `stale`，不自動延用。

### 3c. 跟神經網路的反向傳播：像與不像

| | 反向傳播 | 這裡 |
|---|---|---|
| 目的 | 把整體損失的責任分到每個參數 | 把整體分數的責任分到每棵子樹 ——**像** |
| 局部量 | 損失對參數的偏導（鏈式法則一層層傳） | 子樹開／關的分數差（有限差分、在子樹邊界量一次）——**不像**：沒有鏈式法則，不往子樹裡面再傳；director 的貢獻不會再拆成「它的 prompt 哪一句」 |
| 一次要幾次前向 | 一次反向≈一次前向的代價，所有參數一起得到 | **每棵子樹一次前向**（N 棵＝N 次），所以只量少數幾棵、而且要挑 ——這是成本上最大的不像 |
| 更新 | 參數沿梯度走一小步，連續 | 優化器（腦）讀貢獻後**改檔**（離散、大步、可能改壞）；verify 擋壞的、分數掉就退回 ——不像 |
| 哪裡責任分得到 | 任何可微的節點 | 只有「能關」的子樹；判準、流程格分不到（責任為 0 不代表不重要） |
| 相像的直覺 | 梯度大的參數先動 | 貢獻大又弱的子樹先改；成本份額高又貢獻小的子樹先縮 |
| 累積 | 動量、Adam 記梯度歷史 | `ratings.moves`（第 2 層 tune）記每類改動的效果 ——像，但粒度是「改動種類」不是「參數」 |

一句話：像的是「先算責任再改」這個骨架；不像的是沒有可微鏈、每量一棵要跑一次、改動是腦寫的離散編輯。

## 4. 優化器照樹走

### 4a. 一步（取代 round4 §4b 第 5 點）

```
1 讀根 _metainfo：tree_id、subtrees、ratings（整棵樹本輪的細項）、rollup
2 對根的每個直接子樹 S 算分：
     weak(S)   = Σ_d  (1 − ratings[d]) × max(0, −contribution[S].dims[d])     ← 弱的維度 × 這棵子樹對它的正貢獻
     cost(S)   = contribution[S].cost.share_tokens                             ← 腦用量份額（固化的主訊號）
     trust(S)  = min(1, counter_samples / 4)                                  ← 樣本少打折
     solid(S)  = 1 if S.uses_llm and S.solid.stage in (scaffold, distilling) else 0
     score(S)  = trust × weak + λ_cost × cost + λ_solid × solid × cost          λ 在 pick_rule.json：預設 cost 0.3、solid 0.5（終點是零 LLM，所以靠腦又貴的先挑）
     沒量過貢獻的 S：score = 先驗（responsible_for 命中弱維度＝0.5）× 0.5，並在提案裡附一條「量貢獻」動作
     凍結的（judge/critic、lib/lint、idle、deliver、train 自己）：跳過
3 挑 score 最高的 S；若 S 有 subtrees → 用 S 當根再做一次 2（只讀 S 的直接子樹）；沒有 → 停在 S
   停的條件：S 是葉，或 S 的子樹都沒量過貢獻（那就提「量 S 的子樹貢獻」而不是改）
4 腦上場（這時才問腦）：給它 根→S 這條路上每層的描述（≤ 3 層 × ≤ 6 個子樹 ≈ 1.5k token）、S 的檔案清單、本輪成果與上一輪改動效果、白名單（限 S 底下的路徑；多一種 `solidify`，§1b-3）、它自己的 ratings.moves（哪類改動在哪棵子樹有效）→ 回 1 條改動（round4 §4c 的形）
   S 靠腦且 solid.distill_ready 夠了 → 提案若不是 solidify，優化器要在 why 說明為什麼先改別的（tune 會數「有得固化卻不固化」的次數）
5 apply：路徑必須在 S 底下（白名單再加一條「在被挑的子樹內」）；改前拍 S 的快照
6 verify（round4）：壞了退回 S 的快照、標 reverted
7 跑 set（8 次）→ score → record：ratings 更新；rollup 只沿 S→…→根 重算；S 的 contribution 標 stale
8 measure：重量 S（4 次）→ contribution 更新、stale 清掉；有餘額再量一棵沒量過的
9 changes/<輪>.json：{"subtree": S, "path_from_root": [...], "move": …, "effect": {delta dims, delta tokens}}
```

優化器一步只改一棵、其他凍結——這就是使用者說的「只改進特定子樹、根據各子樹的貢獻」。一輪一步（round4 的 `max_rounds` 照用）。

### 4b. 優化器自己也是一棵樹

`train/optimize/tools/optimizer/` 的 `_metainfo`：宣告區照 round4 §10；`subtrees` 列它自己的部件——`system.txt`（策略段＋經驗段）、`pick_rule.json`（4a 的公式與權重）、`whitelist.json`——這三個不是資料夾程式、是資料檔，在 `subtrees` 裡以 `{"path": "pick_rule.json", "kind": "data"}` 列（樹中有樹不限於資料夾，C-72 JSON 也是樹）；`ratings.moves`（round4 §4d，現在多一層：`moves[kind][subtree]`）；`contribution`：它對訓練場的貢獻＝它提的改動平均帶來的 `val_delta`（record 算，toward＝`train`）。

**第 2 層 tune**（round4 §4d 沿用）讀的就是這份描述：`moves[kind][subtree]` 的 `delta_mean`、`counter_samples`，照規則在 `system.txt` 經驗段加「在 `draft/tools/writer` 上 `edit_prompt` 平均 +0.4、優先」「`fold` 常弄壞、先不要」；另一條新規則：某棵子樹被改 2 次都沒進步 → 在 `pick_rule.json` 給它 `penalty: 0.5`（下次少挑它）。tune 零 token。

## 5. 給實作者的 B 段

（A 段＝round4 §8 的 0～3 項，照本檔 §1 改：只加宮澤一張精簡卡、`set/base.json`＋四題只動兩個開關、score dims 傲嬌版、lint 加 `tsundere_turn` 與 `topic_taboo`、critic 加三個 0～1 維度。）

**B0 第一個實際目標：把 director 固化成純程式、分數不掉；接著 writer 蒸餾一棵 `writer_solid`。**
1. `draft/tools/plan_template/`（純程式子樹，`uses_llm: false`）：讀 `base.json`＋兩個開關，從 `plans.json`（2×2 四張表，實作者照 §1b-1 手寫、plan_lint 全過）出 beat 表；`draft/_entry` 照 `ratings` 選路（§4：`plan_template` 的 `ratings["傲嬌"].val` 不低於 `director` 就走它，否則 director）；`GALTXT_OFF_DIRECTOR` 的 fallback 就指到它。驗收：同一組題（8 次）director vs plan_template 的 `val_delta ≥ −σ`、`反差`／`承接` 不掉超過 0.1 → record 把 director 標 `solid.stage: "replaced"`、根的 `rollup.llm_tokens` 掉約 20%。
2. `writer_solid/` 的殼（§1b-2：assemble、beats/<8 拍>/pick、slots、turn、tics、guard）第一版由實作者寫，`phrases.json` 先手寫每拍 2～3 句當種子；`train/apply` 的 `solidify` 分支（§1b-3 的 ①～④）之後只換表。驗收：假腦下 `writer_solid` 對四題各出一稿、lint 全過、`反差`（程式算）≥ 0.5；真腦累積 ≥ 16 合格稿後跑一次 solidify，`phrases.json` 每拍 ≥ 4 句、A/B 8 次 `val_delta ≥ −σ`。
3. critic 抽樣尺（§1b-4 第 2 點）：`judge/_entry` 讀 `round.json.k`，k 稿只對 1 稿問腦、其餘用程式維度；程式近似的三維（含蓄、承接、文筆）進 `lib/lint`？——**不**，判準不改；放新的純函數 `lib/score_dims/`（給 judge 叫），lint 仍只管護欄與語域。驗收：程式分 vs critic 分一致率算進 `calibration.json`。

**B1 描述五區**
1. 每個函數資料夾的 `_metainfo` 加 `subtrees`（作者寫；捷徑標 `via`）；根加 `tree_id: "galtxt-b"`；四棵可關的加 `ablation`；各子樹加 `responsible_for`（§1 表的對應：brief→語域、護欄；director→反差、承接；writer→文筆、含蓄、節奏、多樣性；check→護欄、語域；samples→文筆）。
2. `train/record/rollup.py`（2c 演算法）＋ `plan/metainfo_rollup.py --root tree/ [--path S]`（唯讀：印某節點的 rollup 與它沿路的子樹描述；除錯用）。record 只沿被改路徑重算；round 0 全算一次。
3. `human/import` 照 round4 不變（寫 `ratings.human`）。

**B2 開關與貢獻**
4. 四個 `GALTXT_OFF_*` 開關各在對應黏合格／brain 實作（§3a 表）；director 的 fallback＝`draft/_entry` 裡一支 `plan_template()`（純程式：B0 定場、B1 事件、B2 開口、B3×2、B4 讓渡（放第二組 must）、B5 反差、B6 蓋章、B7 收尾；通過 plan_lint 才算）。
5. `train/measure/`（格、純程式）：§3a；`train/fsm.json` 改成 `idle → init → run → score → record → measure → pick → optimize → apply → verify → tune → idle`（measure 在 record 後：先知道誰 stale、誰沒量過）。
6. `train/budget.json` 多 `max_ablations_per_round: 2`。

**B3 優化器照樹走**
7. `train/optimize/_entry`：4a 的 1～3 用程式做（挑子樹不問腦），`pick_rule.json` 放公式權重；只把 4 需要的描述送給 optimizer；5 的白名單多「必須在 S 底下」。
8. optimizer 的 `_metainfo` 照 4b；tune 加「子樹連兩次沒進步就 penalty」。
9. `changes/<輪>.json` 多 `subtree`、`path_from_root`。

**B4 aos-fold 補規格**（round3 §5 原型）：`_metainfo` 五區跟著走——縮成單子時 `ratings`／`contribution` 進單子 key、`rollup` 刪；併層時子樹的 `contribution` 標 `stale`、`subtrees` 改列；`verify` 多比五區形狀。

**驗收與測試**（`test_topdown_galtxt_b_train.py` 加）：
- `rollup`：手組三層小樹（根→a→a/b，b 是葉、a 叫 b 兩次），算出 `llm_calls.val`＝2×b、`counter_nodes`＝3、`deterministic` 全 true 才 true；改 a/b 後只重算 a、根，兄弟 c 的 `rolled_at` 不變；捷徑子樹用目標的 rollup；宣告區 hash 不變（record 一字不碰）。
- `contribution`：假腦下關掉 director（fallback）跑 set → `contribution["galtxt-b"]` 有 `dims`、`cost`、`counter_samples`＝4；假腦分數固定所以 `dims` 全 0——再用 `GALTXT_FAKE_SCORE_DROP=反差:0.3` 讓假 critic 在 OFF 時少給，斷言 `dims.反差 ≈ +0.3`（證明量法會動）；關不掉的（judge）`dims: null`、`cost` 有值；改了 S 後 `stale: true`，measure 後 `false`。
- `toward`：把 `tree_id` 改成別的名字，優化器把該子樹當沒量過（提「量貢獻」而不是改）。
- 優化器走樹：構造根三個子樹的描述（弱點×貢獻分別高／中／低），斷言挑最高；該子樹有子樹且都沒量過→提案是「量貢獻」；提案路徑不在 S 底下→apply rejected；一輪只有一條 applied。
- 開關：四個 `GALTXT_OFF_*` 各跑一題假腦退 0 且產出符合（director off→`plan.json` 的 `source: "template"`；self-lint off→writer history 沒 tool_calls；redraft off→`check.json.final` 第一稿 true；samples off→`brief.samples` 空）。
- lint 新規則 `tsundere_turn`、`topic_taboo` 各一紅一綠；`節奏` 計算一例。
- 真腦（連不上 skip）：round 0＋1 輪，`changes/1.json` 有 `subtree` 與 `effect`；`measure` 量了 ≤ 2 棵。
- 固化：`plan_template` 四題各出一張表且 plan_lint 全過；`draft/_entry` 在 `plan_template.ratings ≥ director` 時走模板（假腦下兩邊 ratings 相等→走模板，刻意把模板 ratings 調低→走 director）；`solidify` 對 runs/ 裡 16 份假稿蒸餾，`phrases.json` 每拍 ≥ 4 句、口癖與道具已換成 `${slot}`、沒有重複句；合格稿只有 10 份→提案被 rejected（`distill_ready` 不足）；`writer_solid` 對四題出稿、lint 全過、`反差`（程式）≥ 0.5、`rollup.llm_tokens.val == 0`；`solid_report` 列出 `uses_llm` 子樹與 blocker、根的 `rollup.llm_tokens` 曲線兩輪遞減（假腦：模板換掉 director 後 token 數字由 measure 證明掉了）；critic 抽樣：k＝2 只有 1 稿有 `llm.jsonl` 一行、另一稿的 dims 來自 `lib/score_dims`。
- 原 galtxt-b 樹 hash 不變、demo 三段照過、原 23 條照過。

## 6. token 預算（單一場景、一輪 ≤ 25 萬）

| 項 | 次 | token | 說明 |
|---|---|---|---|
| 基準／改後重跑 | 4 變化 × k＝2 ＝ 8 | ≈ 13.6 萬 | 每次 ≈ 1.7 萬（傲嬌句短、可能略少） |
| 量貢獻 | 每棵 4 變化 × 1 ＝ 4；一輪 ≤ 2 棵 | ≈ 5.5 萬／棵（關掉的那次本來就便宜） | round 0 量 2 棵＝11 萬；之後每輪重量被改那棵 1 棵＋餘額 1 棵 |
| 優化器 | 1 | ≈ 0.6 萬（描述 1.5k＋檔案 2k＋成果 1k＋輸出 0.5k） | 比 round4 的平表少（不送整棵表） |
| verify、tune、record | 0 | 0 | 純程式 |
| **一輪** | | **round 0 ≈ 24.6 萬；round ≥ 1 ≈ 19.7～25.2 萬** | `budget.json`：`max_rounds 2`、`max_tokens 600000`、`max_ablations_per_round 2` |
| 兩輪訓練（0＋1＋驗收重跑） | | ≈ 60 萬 | 省錢版 k＝1：一輪 ≈ 13 萬 |
| 固化之後 | | 每固化一棵就少一截：director 換模板 −20%、critic 抽樣 −10%、writer 換 writer_solid −59% → 終點一輪 ≈ 1～2 萬（只剩抽樣尺） | 這條曲線就是 §1b-5 的「腦用量往 0」 |

## 7. 跟原則衝突、要使用者定的（接 round4 §9 的十條）

1. **M6 vs `rollup`**：同一份 `_metainfo` 裡「宣告的 llm_tokens」與「彙總的 llm_tokens」可能差 2～3 倍（optimize.md §4 已量到）。我定：kernel 信宣告（M6 不動）、優化器與表信 rollup，差太多列給人回填宣告。另一條路是讓 record 直接回填宣告 val——違反 M7，不選；要使用者定。
2. **M10 模型不看 `_metainfo` vs 優化器就是讀它的腦**：我定優化器是例外（它在訓練場、讀的是樹的描述）；要不要在 M10 加一句「優化器例外」。
3. **「上層只看直接子樹」vs C-52「上層不該知道下層是什麼」**：讀直接子樹的 `_metainfo` 本來就是 M 01 §2 允許的「另外的機制」；但 `subtrees` 這個 key 讓父親「知道有哪些子樹」——我認為這是描述不是依賴（父親不因它改行為），擦邊，列出。
4. **`ablation` 開關是不是暗規則**：四個環境變數只在訓練場設、黏合格讀到就換路——C-56「寫什麼就做什麼」要求明寫：開關宣告在 `_metainfo.ablation`、黏合格說明列出。但「同一棵樹因為一個環境變數走不同路」有人會覺得是暗門；替代方案是改動白名單裡的 `set_param`（改 fsm.json 真的拿掉那格）再跑——更乾淨但每次量貢獻要改樹、拍快照、退回，慢 3 倍。我選環境變數，要使用者看。
5. **`responsible_for` 先驗由作者寫**：作者可能寫錯（我就是作者）；量到的貢獻跟先驗不合時以量的為準、record 在 `contribution` 旁記 `prior_mismatch: true`——要不要讓這個不合反過來改宣告（M7 又來了），不做。
6. **一輪只改一棵子樹**：使用者的意思；代價是一輪只學到一件事，兩輪只能試兩條改動。想快就要多輪＝多錢；或一輪改兩棵不相干的子樹（契約上它們的貢獻獨立）——我先照一棵，列出。
7. **貢獻跟 critic 綁死**：critic 改了（人評校正它的 prompt），所有 `contribution` 都該重量（尺變了）。record 在 critic 被改時把全樹 `contribution` 標 `stale`——預算會爆一輪；或接受舊數字——要使用者定。
8. **`tree_id` 新 key**：根的名字現在等於資料夾名，但搬走會變；用宣告的 `tree_id` 而不是路徑。C-54 命名：`tree_id`（主題在前）或 `id`（R3 固定格）——我選 `tree_id`，因為 `id` 在 daemon 子項已有別的意思。
9. **人評樣本 6 筆現在全是傲嬌**：round4 §6b「每風格至少一筆」改成「每個開關組合至少一筆」；校正只能校傲嬌這把尺——範圍縮了，人評的用處也縮了，照使用者的意思接受。
10. **尺也固化＝Goodhart**：critic 的三維換成程式近似後，優化器會對著程式尺優化（句長分布、留白符號數都能被「刷」）。我的擋法：程式尺的規則只能由人評校正表觸發改、LLM critic 留抽樣尺、人評是最後的錨——但 6 筆／輪的錨很細。要不要在尺固化後把人評提高到每輪 10 筆，使用者定（他說最好少用）。
11. **蒸餾表裡是 LLM 的原句**：`phrases.json` 收我們自己 LLM 產出的句子（換成 `${slot}`）。版權線上沒問題（不是 corpus 逐字），但「純程式子樹」裡裝的是腦寫過的話——使用者的「不依靠 LLM」指執行期不叫腦，建材期用腦炸候選正是固化 README 的終點形態（「LLM 移到編譯期」）；確認這個理解對不對。
12. **固化的子樹會很深、`_metainfo` 會很多**：writer_solid 一棵就 ≥ 14 個資料夾、各一份 `_metainfo`（五區）。record 只沿路徑重算所以成本可控，但「每個資料夾都要有 `_metainfo`」的手寫負擔上來了——第一版由實作者寫殼時一起生成（程式產 `_metainfo` 的宣告區），之後 solidify 換表不動它。要不要允許「生成樹的程式替子樹寫宣告區」（M6 的「作者」變成程式），列出。

## 8. 新／改的 `_metainfo`（實作者照抄的部分）

`train/measure/_metainfo`：

```json
{"summary": "量一棵子樹的貢獻：把它的 ablation 開關設 1，set 四題各跑 1 次，跟本輪基準比每維平均差＝contribution.dims，measure.json 的 token 佔比＝cost；寫進那棵子樹的 _metainfo.contribution[tree_id]、清 stale；一輪最多量 max_ablations_per_round 棵（被改的優先、沒量過的次之）",
 "time_ms": {"val": 70000, "max": 900000}, "resource": ["llm", "cpu"],
 "llm_calls": {"val": 14, "max": 40}, "llm_tokens": {"val": 55000, "max": 160000},
 "llm_endpoint": "http://localhost:4000/v1", "llm_model": "chatgpt-gpt-6-luna-low",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "reads": ["$AOS_WS/rounds/<輪>.json", "$AOS_WS/tree/**/_metainfo（ablation、contribution.stale）", "budget.json"],
 "writes": ["$AOS_WS/runs/<輪>/ablate_<子樹>/", "$AOS_WS/tree/<子樹>/_metainfo#/contribution", "$AOS_WS/rounds/<輪>.json#/ablations"],
 "grow_level": 3, "unit": "round", "writer_of": ["contribution"],
 "note": "llm_* 是一棵子樹 4 次跑樹的合計（關掉的那棵不算它的 token）；這一格自己不問腦"}
```

`train/_metainfo` 的 diff：`subtrees` 列十一格；`llm_calls` val 49 → 36（8 次×約 3.5＋量貢獻 14／2 棵＋優化器 1）、`llm_tokens` val 210000 → 230000、max 800000 → 600000；`summary` 加「量貢獻、照樹走、一輪只改一棵子樹」。

`train/optimize/_entry` 的 `_metainfo`：`summary` 改「程式照 pick_rule 從根往下挑一棵子樹（讀直接子樹描述，不掃表），把沿路描述與那棵的檔交給 tools/optimizer 要一條改動」；`reads` 把 `tree/**/_metainfo` 改成 `tree/_metainfo 與沿路各層 subtrees 的 _metainfo`；`llm_tokens` val 7000 → 6000。

`galtxt-b/_metainfo`（根）加：`"tree_id": "galtxt-b"`、`"subtrees": ["idle", "brief", "draft", "check", "judge", "deliver", {"path": "lib", "kind": "dir"}]`、`"rollup": {}`、`"contribution": {}`（根沒有貢獻，留空給表讀）。`draft/_metainfo` 加 `"subtrees": ["tools/director", {"path": "tools/plan_lint"}, "tools/writer"]`、`"responsible_for": ["反差", "承接"]`（由 director 來）；`draft/tools/director/_metainfo` 加 `ablation`（§3a）、`responsible_for: ["反差", "承接"]`；`draft/tools/writer/_metainfo` 加 `"subtrees": [{"path": "tools/lint", "via": "link"}]`、`responsible_for: ["文筆", "含蓄", "節奏", "多樣性"]`、`ablation`（自檢那條：`{"env": "GALTXT_OFF_SELF_LINT", "off": "skip", "scope": "tools/lint"}`）；`check/_metainfo` 加 `ablation`（`GALTXT_OFF_REDRAFT`）、`responsible_for: ["護欄", "語域"]`；`brief/_metainfo` 加 `"subtrees": [{"path": "tables", "kind": "data"}]`、`responsible_for: ["語域", "護欄", "文筆"]`、`ablation`（`GALTXT_OFF_SAMPLES`，`scope: "tables/samples.json"`）；`judge/_metainfo` 加 `"frozen": true`（判準，優化器不挑；`contribution` 只有 cost）。`lib/lint/_metainfo` 加 `"frozen": true`。

---

**結論一句**：終點是整棵樹不靠 LLM——範圍縮到一張精簡人物卡＋一個寫死的小場景、只動兩個開關；`_metainfo` 從「一張平表」變成「每棵子樹一份對外描述、五區（宣告／彙總／評級／貢獻／腦依賴與固化進度）、上層只讀直接子樹」；貢獻用「宣告的關閉開關＋關掉重跑」量（像反向傳播的責任分配、但是一棵一次前向的有限差分）；優化器一步只挑一棵子樹、靠腦又貴的先挑、能蒸餾就提 `solidify`、改一條、只沿那條路往上重算；第一個目標＝director 換模板、writer 蒸餾成深層純程式子樹、critic 降成抽樣尺；一輪 20～25 萬 token，每固化一棵少一截。
