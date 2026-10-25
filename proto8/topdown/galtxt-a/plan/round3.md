# galtxt-a 第三輪：從極小版往外長一圈——評級 → 選路，包進一個最小訓練迴圈（fable，2026-10-25）

← 收攏方案 [round2-collapse.md](round2-collapse.md)（本輪以它 § 3「後」那棵樹為底）｜盤點 [round2-optimize.md](round2-optimize.md)｜實測 [round1-measure.md](round1-measure.md)｜經驗 [lessons.md](lessons.md)｜依據：[`_metainfo` 10-24](../../../thinking/2026-10-24-metainfo.md)（M7、[01 § 5 `$ref` 陣列](../../../thinking/2026-10-24-metainfo/01-位置與格式.md#5-版本演進)）、[LLM kernel 10-24](../../../thinking/2026-10-24-llm-kernel.md)、[self-improve 10-24](../../../thinking/2026-10-24-self-improve.md)、[aos-kernel-llm](../../../impls/aos-kernel-llm/README.md)／[aos-gate](../../../impls/aos-gate/README.md)／[aos-daemon](../../../impls/aos-daemon/README.md)、[CONCEPTS 04-kernel](../../../CONCEPTS/04-kernel.md)（C-11、C-14、C-47）、[fn-grow 10-24](../../../thinking/2026-10-24-fn-grow.md)、[wf/STRUCTURE](../../../../wf/STRUCTURE.md)（膨脹即拆、四級）、C-55（值的雙形）

給實作者照做。只寫規劃、不改程式。**實作者此刻正在照 round2-collapse 收攏，本輪一律以收攏後的樹為準**（`writer/`、`grader/`、`tools/lint/`、五格內嵌單子＋伴隨腳本、`data/cast.json` 等三張單檔表）。

使用者 10-25 三句（逐字）：
1. 「metainfo很重要。裏面除了九軸之外，還可以儲存任意資訊，以galtxt爲例子，可以說這個資料夾函數，在"傲嬌"一方面的臺詞生成上，有good評級。」
2. 「並且kernel/daemon，有需要的話也可以自己嘗試做。」
3. 「除此之外，我還想到了一個類比：神經網路的訓練方式就是拿一些東西給他跑，跑幾次，記錄這些成果，然後把這些成果丟給另一個函數讓他優化神經網路。我們這其實也可以用類似方式做優化，並且我們這其實算是"長出來"的神經網路」

規劃中途隊長又轉來四句（逐字；§ 14～§ 16 回應）：
4. 「那個用於優化神經網路的函數，我們也可以用這套aos體系做，並且那個也可以是神經網路」
5. 「這樣我們就有兩套神經網路。然後可以繼續疊加，也就是優化"用於優化神經網路的神經網路"的神經網路。」
6. 「並且不要只有單值分數，我們的分數可以是結構性的，就像我剛剛說的，傲嬌方面的臺詞評級是good。並且這套東西還可以繼續細化，也就是按照STRUCUTE.md那樣，單值good變成"多樣性":0.7, "文筆":0.9」
7. 「好了，我相信fable神力，去吧。可以的話，我覺得使用者觀感也可以納入考量。這個評級會是你弄出網頁artifact，讓我勾選和填寫評論而得到的。」「當然，考慮到我時間不多，這套方法最好少用」

加上早先的「先從極小需求開始」——所以這一圈只長**一條主軸**：評級（②）→ 選路（③ 的唯一動作），其餘（腦改 prompt、併／拆節點）列成下一圈的候選，不做。4～7 句用最小的形式接進同一條鏈：評分從一開始就是**結構**（§ 14），優化函數是**有自己 `_metainfo` 與評級的資料夾**（§ 15），人評是**旁檔＋匯入程式**、只拿來校正（§ 16）；三樣都不多花腦呼叫。

---

## 0. 一句話

多一種風格（傲嬌：宮澤柚葉）、多一個寫手變體（`writer-sol/`，只換模型）；跑完的 `score.json` 由純程式算成各寫手的風格評級（`ratings.json`，結構化、`_metainfo` 用 `$ref` 併進來）；`write.py` 照 `data/route.json` 把題目交給該風格評級較好的寫手；`train/` 一個小 loop 把「跑 → 評級 → 換路 → 驗證（退步就回滾）」串成兩個 epoch，token 上限寫死；優化函數 `train/optimize/` 自己也有評級（每次換路讓驗證分升降多少）；人評從 `human/samples.json`（≤ 6 筆）出去、`human/ratings.json` 回來、匯入成各寫手的 `human.json`。

---

## 1. 長哪一圈

| 長什麼 | 選哪個 | 理由 |
|---|---|---|
| 第二種風格 | **傲嬌／宮澤柚葉**（corpus/人物/宮澤柚葉.md；固化/01 § 1 代表角） | 跟森下晴子（文靜／書卷）語域差最遠：句尾「才、才不是」「哼」vs「…呢」「……」；lint 的 Tier 1 `VoiceMissing` 靠語域標記，所以兩種風格能被**純程式**分出來。評測有現成題：**Q16｜收攤的餘韻**（04_秋_文化祭.md，說話者宮澤柚葉，難度中）。Q06 也是傲嬌但說話者吉岡春菜（沒有人物卡），不挑。 |
| 第二個寫手變體 | **`writer-sol/`：跟 `writer/` 同 prompt、同程式，只有 `.env` 換成 `chatgpt-gpt-6-sol-low`** | 一次只動一個參數族（模型），評級才解釋得了差在哪；prompt 版本留給下一圈的「腦改 prompt」。變體必須是**資料夾**：使用者說的評級是掛在「資料夾函數」上的，要被評的東西得有自己的 `_metainfo`（§ 4）。 |
| 一題訓練場景 | 自造 `scene-yuzuha.json`：河鹿堂、主角＋宮澤柚葉、事件「買太多書提不動，把書包塞給主角」（人物卡「擅長／不擅長」那段）、rank 2 | 地點卡已有（她常泡河鹿堂、集梅花章），只加人物卡；訓練題自造、驗證題用 benchmark（§ 8.6 不讓訓練集＝驗證集）。 |

**不長的**：第三種風格、第三個寫手、腦改 prompt、評審變體、平行（O-1）、寫手單次問腦（O-2）。每樣都會讓「評級差異來自哪裡」多一個變因；這圈要先證明「評級→選路」這條鏈離線走得通、真腦跑兩輪不爆預算。

---

## 2. 評級：怎麼產生、放哪、誰寫、怎麼更新

### 2.1 寫法

評級檔 `writer/ratings.json`、`writer-sol/ratings.json`（跟 `_metainfo` 並列；git 追蹤）：

```json
{"source": "train/rate.py 從訓練 stack 的 epochs/*/runs/*/ws/out/*/score.json 算；門檻寫死在 rate.py；人不手改這份（要改路線改 data/route.json）",
 "scale": {"min": 0, "max": 5, "what": "Tier 1（語域 0～2）＋ Tier 2（評審 0～3）；只算過了 Tier 0 的草稿；dims 一律 0～1"},
 "style:傲嬌":      {"val": "good", "score_avg": 4.17, "score_min": 4, "counter_samples": 6, "counter_runs": 2,
                     "dims": {"語域": 0.83, "語意": 0.67, "多樣性": 0.71, "護欄": 1.0},
                     "rated_at": "2026-10-25T12:00:00Z", "rated_by": "train/rate.py epoch 2 @ ~/code/try/galtxt-a/train/ws/.stack"},
 "style:文靜／書卷": {"val": "good", "score_avg": 4.0,  "score_min": 4, "counter_samples": 6, "counter_runs": 2,
                     "dims": {"語域": 1.0, "語意": 0.67, "多樣性": 0.62, "護欄": 1.0},
                     "rated_at": "…", "rated_by": "…"}}
```

每個風格的值照 C-55 的雙形：原值（`good`）在 `val`，其餘是長出來的（§ 14 說它怎麼從一個字長到這個樣子、再往下長要怎麼拆）。

`_metainfo` 只多一個 key，指過去（M1 § 5「`$ref` 共用」；相對檔名從 `_metainfo` 所在資料夾算）：

```json
 "ratings": {"$ref": "ratings.json"}
```

讀的人解開 `$ref` 就看到「這個資料夾函數在傲嬌上 good」——使用者要的那句話；磁碟上 `_metainfo` 這個檔一個字沒被程式改過。

| 欄位 | 定什麼 | 自由格式 vs 通用 key |
|---|---|---|
| `ratings` 容器、每格的 `val`／`score_avg`／`counter_samples`／`dims`／`rated_at`／`rated_by` | 容器名與這六個 key **建議當通用 key**（metatable、日後的判官 kernel、上層優化器才能不認樹就讀） | 通用 |
| 軸名 `style:傲嬌` | `<軸>:<值>` 一個字串；軸與值由各樹自定（這棵樹的軸＝人物卡的 `type`；優化函數的軸是 `action:route`，§ 15） | 自由（只約定冒號分隔） |
| `val` 的值 | 固定四個：`good`／`ok`／`bad`／`none`（樣本不足） | 通用 |
| `dims` | 子維度，值一律 0～1；維度名各樹自定、名字就是量它的程式（§ 14） | 容器通用、維度名自由 |
| `scale` | 分數的尺度與意思，給跨樹讀者換算 | 通用（選填） |
| 門檻 | 寫死在 `rate.py`：`score_avg ≥ 4.0`＝good、`≥ 3.0`＝ok、其餘 bad；`counter_samples < 3`＝none | 這棵樹自己的 |

C-54：計數 `counter_*`、時間點 `rated_at`、上限沒有（門檻是常數不是上限）。`score_min` 留著是因為評審分辨力低（optimize O-6：Q01 三份同分），平均看不出「偶爾寫砸」。

### 2.2 誰寫、怎麼更新

- **只有 `train/rate.py` 寫** `*/ratings.json`（純程式，標準庫）。輸入：這次訓練 stack 底下所有 `score.json`（每份草稿一筆樣本：`writer`、`style`、`total`、`pass`、Tier 1／Tier 2 各自的分）。輸出：每個寫手一份，**以風格為單位整格覆蓋**；這次訓練沒跑到的風格留舊格（`rated_at` 看得出舊）。
- 樣本只取**這一個訓練 stack**（不跨訓練累積）：跨訓練要比就比 git 歷史；不做 EMA（小）。
- 人要改路線**改 `data/route.json`**（§ 3），不手改 `ratings.json`——評級是量出來的，手改就分不出誰說的。人的觀感走另一條路：`human.json`（§ 16），另一個檔、另一支程式寫，跟自動評級不混在一個檔裡。
- 一開始就要有檔（不然 `_metainfo` 的 `$ref` 懸空＝閘門會 `DirectiveBad`）：兩份初始 `ratings.json` 只有 `source`、`scale`，沒有任何 `style:*`（＝全部 none）；`human.json` 同理。

### 2.3 跟 M7 的衝突（**這條要帶給使用者看**）

M7（10-24 照建議定）：實測「寫在 kernel 自己的 `$AOS_STACK`，**絕不回寫**使用者的 `_metainfo`（那是作者的契約，kernel 改了就分不出誰說的）」。使用者 10-25 要的評級「最好由實跑＋評分得來」，而且「寫在 metainfo 裡」——字面上正好對撞：評級是實測，M7 說實測不進 `_metainfo`。

| 解法 | 做法 | 後果 |
|---|---|---|
| A（本輪選這個）**評級寫旁檔、`_metainfo` 用 `$ref` 併進來** | `ratings.json` 由評級程式寫；`_metainfo` 只多 `"ratings": {"$ref": "ratings.json"}`（作者寫的一行） | 守住 M7 的字面（`_metainfo` 檔程式不碰）與精神（`rated_by` 說得出誰量的）；讀者解開 `$ref` 就是使用者要的「metainfo 裡有評級」。代價：不解指示詞的讀者（現在的 metatable、測試）看到的是 `$ref` 不是評級——metatable 要補 10 行解 `$ref`（§ 4.3）。 |
| B 認定評級是「作者的宣告」、直接寫進 `_metainfo` | `rate.py` 當作者的代筆，改 `_metainfo` 的 `ratings` key | 違反 M7 字面；而且一個檔裡混了手寫的 `time_ms` 與程式寫的 `ratings`，diff 時分不出哪行是人改的；metatable 不用改。 |
| C 評級只放訓練 stack（照 M7 原話）、樹上不留 | `route.json` 由訓練寫，評級留在 stack | 使用者要的「這個資料夾在傲嬌上 good」從樹上看不到；換台機器、換 stack 就沒了。 |

**M7 的對象其實是 kernel**（一個讀者不該改它讀的東西）；這裡寫評級的是這棵樹**自己的開發期工具**（`train/`，`role: dev`，`writes` 明寫 `tree:`），是作者那一方的程式。所以 A 不是鑽漏洞，而是把 M7 說清楚一點——建議帶給使用者的一句：**「`_metainfo` 檔本身只有作者寫；量出來的東西（實測、評級、人評）放旁檔、由樹自己的工具寫、`_metainfo` 用 `$ref` 併進來」**，要的話落成 M7 的補句。翻案判準：解 `$ref` 的讀者寫不出來（> 50 行）或閘門因懸空 `$ref` 常寄不出信 → 改 B。

---

## 3. 選路：誰讀評級

### 3.1 現成的夠不夠

| 現成 | 它做什麼 | 選路要的 | 夠不夠 |
|---|---|---|---|
| aos-kernel-llm＋aos-gate | 把「問腦」單子丟信箱、照 level／deadline／`time_ms` 排隊、`slots` 併發、每窗 `max_calls`／`max_tokens` 額度、`served.jsonl` 記 elapsed 與宣告 | 「這題交給**哪一個**寫手」 | **不夠也不該**：kernel 管的是「哪封信先跑、跑不跑」（C-11 排序＝誰先拿資源），不是「叫哪個函數」。選實作是**呼叫方**的事（C-52：呼叫者只看得到它叫的 X）。而且現在一次一題、`slots` 1，沒有爭奪，沒東西可排。 |
| aos-daemon | 顧一群 loop、小格、ctl 增減 | 常駐、定期重評 | **不需要**：訓練是一個 loop 跑兩個 epoch 就停；沒有第二個常駐的東西要顧。 |
| `galtxt-a/kernel/` 自己做 | 讀 `_metainfo` 評級／成本挑實作 | — | **不做**：它能多的只有「讀評級挑寫手」，那正是 `write.py` 讀一張表就能做的事；做成 kernel 反而要信箱、閘門、兩隻 agent 改 think 格。 |

**決定：選路＝純程式，分兩半**——(a) `data/route.json` 一張表（寫什麼就做什麼，C-56；可 diff、可回滾、人可改）；(b) `write.py` 讀表選寫手。評級→表 的那一步是 `train/optimize/`（§ 8、§ 15）。這樣「參數」（表）與「前向」（write.py）分開，訓練迴圈改的是表，不是程式。

什麼時候才該做 kernel／daemon（給下一圈的觸發條件）：
- 做 O-1 平行（兩個寫手同時跑）而腦 endpoint 有併發上限 → 兩隻 agent 的 think 格改走 aos-gate（照 demo/kernel-llm 的 agent-ivy 五行），kernel `slots`＝併發、`budget.window: "all"`＋每次訓練新 stack＝訓練預算由 kernel 擋在**每次問腦之前**（現在 train 自己算，只能在格與格之間擋，最多超一題 ≈ 28k）。
- 要「每天重評一次」→ 一個 aos-loop 設 `interval_ms` 拍 `train/`，或 daemon 顧它；現在沒有這個需求。

### 3.2 表

`data/route.json`：

```json
{"source": "train/optimize 從 writer*/ratings.json 算（同 val 比 score_avg，再平手留原值）；人可改，但下一次 optimize 會再算一次——要固定某題的寫手，在題目 JSON 寫 writer",
 "default": "writer",
 "by_style": {"傲嬌": "writer-sol"},
 "routed_at": "2026-10-25T12:00:00Z",
 "routed_by": "train/optimize epoch 1"}
```

- 值＝根底下的資料夾名（要有 `_entry`）；`by_style` 的 key＝風格（人物卡 `type`）。
- 初始版：`default: "writer"`、`by_style: {}`、`routed_by: "author"`——極小版行為不變。

### 3.3 `brief.py`、`write.py`、`pick.py` 的改動（小）

| 誰 | 改什麼 |
|---|---|
| `brief.py` | `brief.json` 多 `style`（fill：說話者的 `type`；scene：第一個不是主角的卡司的 `type`）與選填 `writer`（題目 JSON 有寫就照抄＝題目級覆寫）。換題清東西那條多清 `stack:route.json`。 |
| `write.py` | 讀 `data/route.json`＋`brief.json`：`brief.writer` > `by_style[style]` > `default`；目標資料夾沒有 `_entry`＝`RouteBad` 退 1。選好先寫 `stack:route.json` `{"writer", "style", "by": "question"\|"by_style"\|"default"}`（**狀態 key**：重跑接著做時照這份、不重選；它在就不重讀表）；小格改開在 `stack:<writer>/runs/NNN/`。 |
| `pick.py` | `score.json` 多 `writer`、`style`（從 `stack:route.json`）；每份草稿多 `dims`（§ 14：語域、語意、護欄三個從已有的分換算；多樣性是整題一個數）——評級程式只靠 `score.json`，不翻 trace、不重算。 |

`_metainfo` 跟著改：`write` 格 `reads` 加 `data:route.json`、`writes` 加 `stack:route.json`、加 `state_key: "stack:route.json"`；`pick` 格 `reads` 加 `stack:route.json`；根 `reads` 加 `data:route.json`。

---

## 4. 樹的變化

### 4.1 前後

**前**（round2-collapse § 3「後」，13 個資料夾）→ **後**（19 個資料夾；真資料夾最深 2 不變）：

```
galtxt-a/
├─ _entry _metainfo loop.json fsm.json README.md
├─ brief.py write.py check.py judge.py pick.py          （三支小改，§ 3.3）
├─ idle/
├─ tools/lint/
├─ writer/                  _entry _metainfo(+ratings、human_ratings $ref) .env fsm.json loop.json brain.py(+假腦技能表) act.py system.txt  ratings.json★ human.json★
│  ├─ idle → ../idle
│  └─ tools/lint → ../../tools/lint
├─ writer-sol/★             _entry _metainfo .env(sol-low) ratings.json human.json
│  ├─ brain.py → ../writer/brain.py   act.py → ../writer/act.py   fsm.json → ../writer/fsm.json
│  ├─ loop.json → ../writer/loop.json system.txt → ../writer/system.txt
│  ├─ idle → ../idle
│  └─ tools/lint → ../../tools/lint
├─ grader/
├─ data/                    _metainfo address.json forbidden.json styles.json(+傲嬌) cast.json(+宮澤柚葉) places.json(+教室) samples.json(+柚葉)  route.json★
│  └─ bench/                _metainfo Q01.json Q16.json★
├─ train/★                  _entry _metainfo loop.json fsm.json verify.py train.py rate.py set.json budget.json
│  └─ optimize/★            _entry(=optimize.py) _metainfo(+ratings $ref) ratings.json policy.json   ← 優化函數：自己有評級（§ 15）
├─ human/★                  _metainfo samples.json questions.json ratings.json(網頁寫) calibration.json          ← 人評（§ 16）
│  └─ import/★              _entry _metainfo                                                      ← ratings.json → 各寫手 human.json
├─ meta/                    _metainfo table-round1.md table-round2.md table-round3.md
│  └─ metatable/            _entry(+ratings 欄、解 $ref) _metainfo
└─ plan/                    … round3.md★
   └─ examples/             Q01.json scene.json  scene-yuzuha.json★ Q16.json★
```

★＝新。`writer-sol/` 的 `_entry` 是 `exec aos-loop loop.json`（跟 writer 一樣，自己一份、不是捷徑——aos-exec 走捷徑進資料夾看 `_entry`，`_entry` 本身可以是捷徑，但 `.env` 必須是真檔，所以乾脆入口也真檔，兩行）。`fsm.json` 捷徑：aos-fsm 跑內嵌單子時 cwd＝fsm.json 所在資料夾——捷徑的 realpath 在 `writer/`，**要查** aos-fsm 用的是 `AOS_CF` 的字面路徑還是 realpath；若是 realpath，`writer-sol/fsm.json` 改成真檔（內容一字不差）。這是實作者第一個要驗的點。

### 4.2 新節點的 `_metainfo`

`writer-sol/_metainfo`（數字用實測：寫手每次 3.2～6.6 s、6.6k～7.1k token）：

```json
{"summary": "寫手變體：跟 writer 同一套 prompt 與程式（捷徑），只有 .env 換模型；在哪種風格上寫得好看 ratings.json、人怎麼看看 human.json",
 "kind": "agent", "grow_level": 5, "variant_of": "writer",
 "time_ms": {"val": 5000, "max": 720000},
 "resource": ["llm", "cpu"],
 "llm_calls": {"val": 2, "max": 4}, "llm_tokens": {"val": 7000, "max": 50000},
 "llm_model": "chatgpt-gpt-6-sol-low（.env）", "llm_endpoint": "AOS_BRAIN_URL；沒設＝假腦（技能表：沒有弱項）",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": true,
 "lock": [{"$env": "AOS_WS", "$prefix": "ws:"}],
 "reads": ["ws:new/*.json", "ws:rules.json（經 lint）"],
 "writes": ["ws:out/<題名>", "ws:done/<題名>.json", "stack:history.jsonl", "stack:usage.jsonl", "stack:state.txt", "stack:current.txt", "stack:trace.jsonl", "cell:lint/"],
 "fs_needs": ["own_stack", "mount"], "callers": 1,
 "ratings": {"$ref": "ratings.json"},
 "human_ratings": {"$ref": "human.json"}}
```

`writer/_metainfo`：只加 `"ratings": {"$ref": "ratings.json"}`、`"human_ratings": {"$ref": "human.json"}` 與 `"llm_endpoint"` 補一句「假腦技能表：傲嬌弱」；其餘不動（M7：不拿實測回填宣告；要回填是作者另一次決定）。

`train/_metainfo`：

```json
{"summary": "最小訓練迴圈：verify（驗證題照路由跑、跟上一個 epoch 比、退步就回滾、把差值記成 optimize 的評級）→ train（訓練題 × 每個寫手強制跑）→ rate（score.json → 各寫手 ratings.json；第一個 epoch 挑人評樣本）→ optimize（資料夾：ratings → data/route.json）；會改自己這棵樹的幾種檔",
 "kind": "program", "grow_level": 5, "role": "dev",
 "time_ms": {"val": 300000, "max": 1800000},
 "resource": ["llm", "cpu", "disk"],
 "llm_calls": {"val": 126, "max": 150}, "llm_tokens": {"val": 380000, "max": 450000},
 "llm_model": "沿用各寫手、評審的 .env", "llm_endpoint": "AOS_BRAIN_URL；沒設＝假腦，整條離線可跑",
 "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "resumable", "parallel": false,
 "lock": ["tree:galtxt-a"],
 "reads": ["tree:set.json", "tree:budget.json", "tree:../plan/examples/*.json", "tree:../data/route.json", "tree:../writer*/ratings.json", "tree:../writer*/human.json", "tree:optimize/ratings.json", "stack:epochs/*", "stack:epoch.txt"],
 "writes": ["tree:../data/route.json", "tree:../writer*/ratings.json", "tree:optimize/ratings.json", "tree:../human/samples.json", "stack:epochs/NNN/{runs/,verify.json,usage.json,params/}", "stack:verify.jsonl", "stack:epoch.txt"],
 "state_key": "stack:epoch.txt",
 "fs_needs": ["own_stack", "git_tracked"], "callers": 0}
```

新前綴 **`tree:`**＝寫進自己的原始碼樹（會自我修改的函數）。`lock: tree:galtxt-a`＝同一棵樹同時只能有一個訓練在跑（兩個會互相蓋 `route.json`）。`llm_*` 的 val 是 § 10 算出來的（2 epoch），`max` 就是 `budget.json` 的上限——這格的 `max` 終於是「資源上限」不是逾時上界（optimize O-7 拆開的那兩種意思，這裡分別落在 `llm_tokens.max` 與 `time_ms.max`）。

`train/fsm.json` 四格的 `_metainfo`（表列；verify／train／rate 是內嵌單子，`grow_level 0`、`fs_needs []`、`callers 1`、`kind: program`）：

| 格 | summary | time_ms | resource | llm_calls（每 epoch） | side_effect | deterministic |
|---|---|---|---|---|---|---|
| verify | 驗證題各一題照路由跑根（`aos-exec --ws 小格/ws ..`）、算分、跟上一個 epoch 比、把差值記進 `optimize/ratings.json`（§ 15）；退步＝回滾 `data/route.json` 退 10；到 `max_epochs` 退 10；預算到頂退 2 | 60000／600000 | llm,cpu | 18 | true（可能回寫 route.json；寫 optimize 的評級） | false |
| train | `set.json` 的訓練題 × `writers` 每個強制跑一次（題目 JSON 加 `writer`） | 120000／1200000 | llm,cpu | 36 | false（只寫 stack） | false |
| rate | 收 stack 的 score.json → `writer*/ratings.json`（含 dims）；第一個 epoch 挑人評樣本 → `human/samples.json`（§ 16） | 100／10000 | cpu,disk | — | true（`tree:`） | true |
| optimize | `"exec": "optimize"`（資料夾，§ 15）：`writer*/ratings.json`＋`human.json`＋自己的 `ratings.json`／`policy.json` → `data/route.json`，印 diff；先拍 `params/` 快照 | 50／10000 | cpu,disk | — | true（`tree:`） | true |

optimize 這格不是內嵌單子而是 `"exec": "optimize"`（資料夾），因為它要有自己的 `_metainfo`＋評級檔（N-2 伴隨檔 ≥ 2，§ 4.4）。`train/optimize/_metainfo`、`human/_metainfo`、`human/import/_metainfo` 在 § 15、§ 16。

資料表：`data/_metainfo.children` 加 `"route.json": "路由表 {default, by_style}——只有 write.py 讀、只有 train/optimize 寫"`；`data/bench/_metainfo` 不動（Q16 多一檔）。

### 4.3 metatable 跟著長一點

- 讀 `_metainfo` 時，頂層 key 的值是 `{"$ref": "檔"}` 就從該資料夾讀那個檔併進來（只做一層、只做頂層；讀不到＝那格印 `壞ref`、不退 1）。約 10 行，不叫 aos-directive（metatable 是標準庫 Python、要離線）。
- 多一欄 `ratings`：印成 `傲嬌:good(4.2/6) 文靜／書卷:good(4.0/6)`（`val(score_avg/counter_samples)`；`dims` 太寬不印、`--json` 原樣帶）；`human_ratings` 有東西就在同欄尾巴加 `[人:ok/3]`。
- 多一欄 `role`（optimize O-10 提的）：彙總時 `role: dev` 的另算，不然 `train` 的 126 次腦呼叫會把「整棵樹典型值」撐爆。
- 彙總加一行「有評級的節點」。收一次 `meta/table-round3.md`。

### 4.4 新節點過 round2 判準

| 節點 | 判準 | 結論 |
|---|---|---|
| `writer-sol/` | N-1 `own_stack`、N-2 伴隨檔 ≥ 2（`.env`、`ratings.json`、`human.json`、`_metainfo`）、N-3 resumable | 留；而且 B-4 去重已經做在裡面（五個檔是捷徑） |
| `train/` | N-1 `own_stack`、`git_tracked`（寫回樹）；N-2 伴隨檔 6 個；N-3 resumable（`epoch.txt`） | 留 |
| `train/` verify、train、rate 三格 | 從第 0 級（內嵌單子＋伴隨腳本）開始，**不開資料夾**——開了就是 B-2 馬上要縮的東西 | 合判準 |
| `train/optimize/` | N-2 伴隨檔 ≥ 2（`_metainfo`、`ratings.json`、`policy.json`）；它要被評級，所以必須是有 `_metainfo` 的資料夾（同 writer-sol 的理由） | 留（第 4 級） |
| `human/` | N-1 `git_tracked`、要單檔 diff（`samples.json` 程式寫、`ratings.json` 網頁寫、`questions.json` 人寫——三個寫的人不同）；`human/import/` 是像 `meta/metatable` 的開發期工具（`callers 0`、人手叫），要能 `aos-exec` 就得是資料夾 | 留 |
| `data/route.json`、`data/bench/Q16.json`、`*/ratings.json`、`*/human.json`、`optimize/policy.json` | N-1 要單檔 diff（人／程式各自改）、`git_tracked` | 留單檔，不併進別的表 |
| `plan/examples/scene-yuzuha.json`、`Q16.json` | 同 round2 的 `plan/examples`（要被 `cp` 單獨拿） | 留 |
| 沒長出的 | 沒有新 `tools/` 容器、沒有新 glue 資料夾、沒有第四份 idle | — |

`train/` 的 `set.json`、`budget.json` 兩張表合計 < 1 KB，不開資料夾（B-3 反向：太小不該長）。`human/` 四張表也都 < 2 KB，留在一層。

---

## 5. 資料要補的（從 corpus 固化，每張帶 `source`）

| 表 | 加什麼 | 來源 |
|---|---|---|
| `data/cast.json` | `宮澤柚葉`：`type: "傲嬌"`、`voice`（嘴硬心軟、先否認再讓步、音量翻倍）、`catchphrase: "——才、才不是為了你"`、`likes`（宮澤賢治、太宰、河鹿堂的梅花章、吃辣）、`habits`（撥瀏海看窗外、踮腳、指尖描字）、`markers: ["才不是", "才沒", "哼", "真是的", "隨便你", "笨蛋"]`、`never`（直白說喜歡、真的惡毒、臉紅冒煙／跺腳）、`calls_lead: {"0": ["同學"], "1": ["你", "主角同學"], "2": ["你", "喂"], "3": ["悠同學"], "4": ["悠"]}`、`called_by_lead: {"0": ["宮澤"], "1": ["宮澤"], "2": ["宮澤", "喂"], "3": ["宮澤"], "4": ["柚葉"]}` | corpus/人物/宮澤柚葉.md、固化/01 § 1、固化/02 § 一（主角沒姓氏＝「你／喂」對應同階） |
| `data/styles.json` | `types.傲嬌`：`endings`（才、才不是那樣！／別、別誤會了／…又沒有說不行／隨便你啦）、`habits`（哼／真是的／所以說啊／…算了）、`narration`（耳朵臉頰泛紅、別過頭、嘴上兇動作卻幫忙）、`ng`（直白說喜歡、真的惡毒、臉紅冒煙／跺腳） | 固化/01 § 1 |
| `data/places.json` | `教室`（Q16 要；文化祭閉幕後的黃昏教室）：`details` 從校內地圖抄 3～5 條、`fixed` | 世界/日和高中詳誌/01_校內地圖與建築.md |
| `data/samples.json` | `宮澤柚葉`：固化/01 的合格範例一句（「這本你拿著。……才不是特地留給你的，只是我拿不動而已。」）；**不抄 Q16 正解** | 固化/01 § 1 |
| `data/bench/Q16.json` | 照 Q01 的欄位：`speaker: 宮澤柚葉`、`place: 教室`、`cast: ["佐伯悠", "宮澤柚葉"]`、`season: 十月`、`time: 黃昏`、`intent: 餘溫`、`rank: 2`、`context`（六行、第五行挖空）、`guard.must: [["才不是", "才沒", "哼"], ["不是不能", "也不是不", "還算", "偶爾"]]`、`bonus: ["彩帶", "明年", "鬧一場"]`、`points`、`answer`、`answer_min` | 評測/04_秋_文化祭.md Q16 |
| `plan/examples/scene-yuzuha.json` | `{"mode": "scene", "place": "河鹿堂", "cast": ["佐伯悠", "宮澤柚葉"], "event": "柚葉買了一疊書提不動，把書包塞給主角、理由每次不同；主角照單全收", "season": "十月", "time": "放學後", "intent": "鬥嘴", "rank": 2, "min_lines": 5, "max_lines": 10, "drafts": 3}` | 人物卡「擅長／不擅長」 |
| `plan/examples/Q16.json` | `{"mode": "fill", "bench": "Q16", "drafts": 3}` | — |

要查的：`forbidden.json` 的 A／B／C 不能含「笨蛋」「哼」「！」（傲嬌必用）；`ng_marks` 只擋「！！」雙驚嘆，單個不擋——對。`max_line_chars` 60 夠（Q16 正解 36 字）。

---

## 6. 假腦：整條離線可測

兩隻寫手共用一支 `brain.py`，假腦要能**分出變體**，不然評級永遠平手、選路永遠不動、測試驗不到鏈。做法：`fake()` 加一張**技能表**（劇本，不是品質證據，同 self-improve 的假腦劇本）：

```python
WEAK = {("", "傲嬌")}        # 假腦技能表：(模型標籤, 風格) 在表裡＝這個假寫手寫這種風格會寫砸：女角那句句尾加 NG 標記「～～」
tag = "sol" if "sol" in (os.environ.get("AOS_BRAIN_MODEL") or "") else ""
```

- 女角 `type` 從題目 JSON 的 cast 讀（brief 已帶 `type`）。`AOS_BRAIN_MODEL` 來自各變體 `.env`（`--dotenv-override`），假腦看得到。測試要反過來時用環境變數 `GALTXT_FAKE_WEAK=sol:傲嬌`（只有假腦讀）。
- 效果：`writer`（luna）寫傲嬌 → lint `NgMark` → Tier 1 1；`writer-sol` 寫傲嬌 → 「～～」沒加、`samples` 那句帶「才不是」→ Tier 1 2；兩個寫晴子都 2。假評審固定 2。所以總分：writer×晴子 4、writer×柚葉 3、sol×晴子 4、sol×柚葉 4。
- **極小版的假輸出一個字不變**（luna × 文靜不在表裡）：round2 的收攏證明照舊成立；既有測試的 `picked`、`total` 不動。
- 評審假腦不改（固定 2）；評級差異全靠 Tier 1，這是純程式、確定性。

---

## 7. 評估流程與次數

| 階段 | 跑什麼 | 題-次 | 樣本（草稿） |
|---|---|---|---|
| verify（epoch 0，基線） | Q01、Q16 照初始 route（都給 writer） | 2 | 6 |
| train（每 epoch） | `scene.json`、`scene-yuzuha.json` × {writer, writer-sol} 強制 | 4 | 12（每個（寫手, 風格）格 3 份） |
| rate → optimize | 純程式 | 0 | — |
| verify（epoch 1、2） | Q01、Q16 照新 route | 2 × 2 | 12 |

兩個 epoch 合計 **14 題-次**、每格評級 6 份樣本（2 epoch × 3 份）。`counter_samples < 3` 就 `none`，所以一個 epoch 就能出第一版評級；第二個 epoch 是為了看換路後驗證分有沒有真的變好。

---

## 8. 訓練迴圈的形狀

### 8.1 誰跑

`train/`：`_entry` → `aos-loop loop.json`（`max: 8`＝2 epoch × 4 格的保險，正常由 verify 退 10 收工）→ `fsm.json`：`start: verify`，`verify → train → rate → optimize → verify`。跑法：

```sh
mkdir -p ~/code/try/galtxt-a/train/ws
AOS_BRAIN_URL=http://localhost:4000/v1 aos-exec --ws ~/code/try/galtxt-a/train/ws proto8/topdown/galtxt-a/train   # 真腦
aos-exec --ws ws proto8/topdown/galtxt-a/train                                                                     # 假腦（測試用）
```

不用 self-improve 的殼（它改的是「暫時複本上的一個函數」、判準是例子或檢查程式、改進者是腦）；這裡被改的是**自己這棵樹的幾張表**、判準是跑整棵樹算分、優化是純程式。但抄它三件：每 epoch 拍快照、從最好的那版往下改、預算三種在格與格之間檢查。

### 8.2 ① 跑：`train.py`

- 讀 `set.json`：`{"source": "訓練題自造（plan/examples）、驗證題 benchmark（data/bench）", "train": ["scene.json", "scene-yuzuha.json"], "verify": ["Q01.json", "Q16.json"], "writers": ["writer", "writer-sol"]}`。
- 每個（題, 寫手）開小格 `stack:epochs/NNN/runs/<題名>-<寫手>/{ws,stack}`，題目複製進 `ws/new/`、JSON 加 `"writer": <寫手>`（題目級覆寫，§ 3.3），`aos-exec --ws 小格/ws ..`（根；cwd＝`train/`，`..` 就是 galtxt-a）。已有 `ws/out/<題名>/score.json` 的小格跳過（被殺重跑接著做）。
- 每跑完一題把寫手、評審小格的 `usage.jsonl` 加總進 `epochs/NNN/usage.json`（`counter_calls`、`counter_tokens`），**格與格之間**看 `budget.json`，到頂＝stderr `train: BudgetSpent …` 退 2。

### 8.3 ② 記成果：`rate.py`（寫到哪＝§ 2，面對 M7＝§ 2.3）

- 收 `epochs/*/runs/*/ws/out/*/score.json`（訓練題的；驗證題的不算進評級——驗證集不能拿來調參數）：每份 `pass` 的草稿一筆 `(writer, style, total, dims)`。
- 算每個寫手每個風格的 `score_avg`、`score_min`、`counter_samples`、`counter_runs`、`dims` 平均；門檻 → `val`；整格覆蓋寫進 `<writer>/ratings.json`（N-05 先寫 `.ratings.json` 再改名）。
- 第一個 epoch 跑完順手挑人評樣本寫 `human/samples.json`（§ 16.2）。
- 同時把 `epochs/NNN/usage.json` 的 token、時間一起印成一行摘要（`train: epoch 1 rated writer{傲嬌:ok 文靜／書卷:good} writer-sol{…} tokens 112000`）。
- 成果也進 `_metainfo`？**只有評級**（經 `$ref`）；token、時間的實測仍只留 stack（M7 原話）。要回填宣告是作者另一次決定，不自動。

### 8.4 ③ 優化函數：`train/optimize/`

- **輸入只看**：`writer*/ratings.json` 與 `human.json`（經 `_metainfo` 的 `$ref` 找，所以它讀的是「`_metainfo` 裡的評級」）、現在的 `data/route.json`、`set.json` 的 `writers`、自己的 `ratings.json`／`policy.json`（§ 15）。不看 trace、不看草稿。
- **輸出**：新的 `data/route.json`。規則（純程式、確定性）：每個風格挑 `val` 最高的寫手（good > ok > bad > none）；同 val 比 `score_avg`；再平手**留原值**（不震盪）；全部 none → 不列（走 `default`）；人評 `val: bad`（≥ 3 筆）的寫手在那個風格上**不選**（人評唯一的直接用法，§ 16）。`routed_by: "train/optimize epoch N"`。
- **能 diff、能回滾**：寫之前先把現在的 `data/route.json` 與各份 `ratings.json` 拷進 `stack:epochs/NNN/params/`；stdout 印舊→新的 diff（一行一風格）。樹是 git 追蹤的，使用者層的 diff／回滾就是 `git diff`／`git checkout -- data/route.json writer*/ratings.json`；迴圈內的回滾由 verify 做（8.5）。
- 這一圈**只有這一種動作**（換路）。下一圈的候選動作，各自是一支函數、各動一個參數族：`optimize-prompt/`（腦：讀評級最差那格的 `dims` 與草稿、評審理由，改那個寫手的 `system.txt` 一版，走 self-improve 的 improver，工具只開 `edit`、路徑只准 `writer*/system.txt`）、`optimize-model/`（純程式：改 `.env` 模型名，候選表寫死）、`optimize-shape/`（併／拆節點＝round2-collapse § 5 的 `meta/collapse`，純程式）。一次迴圈只跑一種動作，不然驗證分變了不知道是誰的功勞。

### 8.5 ④ 比較前後：`verify.py`

- 驗證題固定＝`set.json.verify`（benchmark 挖空題 Q01、Q16），照**當下的** `data/route.json` 跑（不強制寫手）。
- 分數（`epochs/NNN/verify.json`）：`score_mean`＝兩題**所有**過護欄草稿的 `total` 平均（6 份，不只挑中的那份——樣本太少，用全部）；同一份檔也放結構分 `dims`（§ 14 四個維度在驗證題上的平均）；另記 `picked_total_sum`、`guard_hit` 幾題、`bigram_overlap` 平均、token、時間（只記不比）。
- 比較：跟上一個 epoch 的 `verify.json` 比 `score_mean`；**漲 ≥ `budget.json.min_gain`（0.25）才算進步**。第一次（epoch 0）沒得比，只記。比完把差值寫成優化函數的一筆成果（`train/optimize/ratings.json`，§ 15）。
- 退步（跌 > 0）→ 把 `epochs/<上一個>/params/route.json` 拷回 `data/route.json`、stderr 一行 `train: Regressed epoch N 回滾到 N-1`、退 10（收工，不是錯：N-43 預料到的結果）；`epoch ≥ max_epochs` → 退 10；否則 `epoch.txt`＋1、退 0 往 train 走。進步也不「存最好版」——最好版就是現在樹上的那份（跟 self-improve 不同：參數在樹上、不是在 stack 的複本）。

### 8.6 訓練集 ≠ 驗證集、樣本太少

| 問題 | 做法 |
|---|---|
| 訓練集＝驗證集 | 訓練題只用自造場景（scene 模式，沒有正解），驗證只用 benchmark 挖空題（fill，正解只有 pick 讀）；`rate.py` 不吃驗證題的 score.json；`optimize` 看不到 verify.json。 |
| 一題只 3 份、評審分辨力低（Q01 三份同分） | 評級用 6 份（2 epoch）；驗證用 6 份草稿的平均不用 2 份挑中的；`min_gain` 0.25 ＝ 6 份裡至少一份多 1 分半才算動了；`score_min` 記下來看穩不穩。 |
| 風格只有兩種、各一題 | 評級軸名是 `type`，不是題名；同型角色之後加題就直接進同一格。 |
| 假腦跟真腦 | 假腦只證鏈（評級→換路→驗證分↑→不回滾）走得通；真腦跑兩輪只看數字、不當結論（lessons § 4）。 |

---

## 9. 類比：哪裡貼合、哪裡不貼合

| 神經網路 | 這棵樹 | 貼合度 |
|---|---|---|
| 參數 θ | `data/route.json`（離散、幾個格）、各寫手 `system.txt`、`.env` 模型名、`write.py` 的 `HINTS`、評審 rubric | 貼：都是「改了行為就變、不用改程式」的東西；差：離散、少、彼此不連續。 |
| 前向 | 一題走 brief → write → check → judge → pick | 貼。 |
| 損失 | −（Tier 1＋Tier 2）在驗證題上的平均（`score_mean`） | 半貼：評審是不可微的判官（腦），同輸入不同分（deterministic false）。 |
| 梯度 | **沒有**。最接近的是「每個（寫手, 風格）格各跑一次、看分數」＝逐臂試的 bandit／座標搜尋，不是對參數求導 | 不貼。所以優化器只能是 argmax、不能是 step。 |
| 學習率 | `min_gain`（多少才算動）、同分留原值（慣性）、§ 15 的 `min_gap`（回滾過就要更大的差距才換） | 勉強：是「要不要跳」不是「跳多遠」。 |
| epoch | 訓練題全跑一遍＋評級＋換路＋驗證 | 貼。 |
| mini-batch | 一題-次 | 貼（batch size 1）。 |
| 過擬合 | 路線／prompt 對著兩個自造場景調，benchmark 分沒漲 | 貼：verify 用不同題、退步回滾就是早停。 |
| 反向傳播／credit assignment | 沒有：分數算在整棵樹上，哪一格該負責不知道。這圈靠結構硬切（評級按「寫手×風格」記，因為 write 格是唯一換得了實作的格） | 不貼；是最大的缺口。 |
| 神經元／層 | 格／資料夾；`_metainfo`＝每個神經元自帶的說明與量測（NN 沒有這個） | 樹多出來的東西。 |
| MoE 的 gate | `route.json`＝硬的、學出來的 gate（by_style） | 貼。 |
| 「長出來的」 | 加寫手變體＝加一個 head；round2 收攏＝剪枝；fn-grow 六級＝一個函數從 inline 長到子網路；train 的 `optimize-shape`＝NAS | 貼到「結構搜尋」那一支，不是 SGD 那一支。 |
| 每次前向的成本 | 27k token、15～24 s／題 | 不貼：貴三到六個數量級，所以 epoch 只能 2、優化器必須樣本效率高（少臂、argmax）。 |

結論一句：這不是梯度下降，是**在一棵會長的結構上做少臂 bandit**；`_metainfo` 的評級就是每個臂的估計值，`route.json` 是 policy。結構化的 `dims`（§ 14）讓它往梯度靠一步：知道「傲嬌的語域差」就動管語域的那個參數，而不是整個換掉。

---

## 10. 預算（寫死）

實測（round1-measure）：一題 ≈ 27k token（寫手 3 × 7k ＋ 評審 3 × 2.4k）、9 次腦、15～24 s。

| | 題-次 | 腦呼叫 | token | 時間 |
|---|---|---|---|---|
| verify ×3（epoch 0、1、2） | 6 | 54 | ≈ 165k | ≈ 2 min |
| train ×2 | 8 | 72 | ≈ 220k | ≈ 2.5 min |
| 合計（2 epoch） | 14 | 126 | ≈ 385k | ≈ 5 min（逐個跑） |

`train/budget.json`（上限一律 `max_*`；格與格之間檢查，最多超一題 ≈ 28k）：

```json
{"max_epochs": 2, "max_calls": 150, "max_tokens": 450000, "max_elapsed_ms": 1200000, "min_gain": 0.25}
```

到頂＝`BudgetSpent` 退 2、樹上的 `route.json` 留在最後一次 optimize 的結果（verify 沒跑到就沒驗證、stderr 說清楚）。做了 O-2（寫手一次腦）後整條減半，上限不改。§ 14～§ 16 加的東西都是純程式，**不多花一次腦**；人評花的是使用者的時間（§ 16.4 算過：一輪 6 筆、約 5 分鐘）。

---

## 11. 測試要驗什麼（加進 `proto8/tests/test_topdown_galtxt_a.py`；全部假腦）

1. **樹**：`writer-sol/` 有 `_entry`（+x）、`.env` 的模型名 ≠ `writer/.env` 的；`brain.py`／`act.py`／`fsm.json`／`loop.json`／`system.txt` 是相對捷徑指到 `../writer/*`；`idle`、`tools/lint` 捷徑同 writer。兩份 `_metainfo.ratings` 都是 `{"$ref": "ratings.json"}`、`human_ratings` 指 `human.json`；四份檔都是物件、有 `source`，每個 `style:*` 格的 `val` ∈ {good, ok, bad, none}、`dims` 的值都在 0～1。`data/route.json` 的 `default` 與 `by_style` 每個值都是根下有 `_entry` 的資料夾。
2. **選路**：放 `scene-yuzuha.json` → `brief.json.style == "傲嬌"`；`route.json` 暫改 `by_style: {"傲嬌": "writer-sol"}`（測試用暫時工作區拷一份樹，或用題目級 `writer` 覆寫）→ 小格在 `stack/writer-sol/runs/001/`、`score.json.writer == "writer-sol"`、`stack/route.json.by == "by_style"`；題目寫 `"writer": "writer"` 時覆寫贏（`by == "question"`）；`route.json` 指到不存在的資料夾 → stderr `galtxt-a write: RouteBad`、退 1、`state.txt` 是 `write`。
3. **換題清狀態**：兩題連放（晴子題、柚葉題）→ 第二題的 `stack/route.json` 是柚葉的、寫手小格各自分開。
4. **Q16 離線**：`answer.txt` 一行、以「宮澤柚葉：「」開頭、must 兩組都中；`bigram_overlap`、`guard_hit` 在；所有 history.jsonl 找不到正解句（隔離）。
5. **假腦技能表**：`writer` 跑柚葉題 → 三份草稿 `tier1` 都是 1、`tier1_notes` 含 `NgMark`；`writer-sol` 跑同題 → `tier1` 2；`writer` 跑晴子題輸出跟 round2 證明用的一字不差（既有 `test_scene`、`test_fill_q01` 斷言不動）。`score.json` 每份有 `dims`（護欄 1.0、語域 0.5／1.0、語意 0.67）、整題有 `多樣性`。
6. **`rate.py` 單元**：暫存資料夾放手寫的 `score.json` 若干 → `ratings.json` 的 `val` 照門檻（4.0 good／3.0 ok／其餘 bad／< 3 份 none）、`counter_samples` 對、`dims` 是各份平均、別的風格舊格留著、`rated_at` 是 ISO 時間；同輸入跑兩次除了 `rated_at` 全同；驗證題的 score.json 放進去**不被算**。
7. **`optimize` 單元**：兩份評級 → `route.json` 每風格挑最高；同 val 比 `score_avg`；再平手留原值；全 none 不列；某寫手 `human.json` 那風格 `val: bad`（3 筆）就不選它；自己的 `ratings.json` 記了回滾（§ 15）時要 `min_gap` 才換；寫之前 `params/` 有快照；stdout 有 diff 行；`--dry-run` 不寫。
8. **整條訓練（假腦，`max_epochs: 1`）**：`aos-exec --ws ws train` 結束碼 0；`epochs/000/verify.json`、`epochs/001/verify.json` 在、後者 `score_mean` ≥ 前者；`writer/ratings.json` 有 `style:傲嬌` ok、`style:文靜／書卷` good，`writer-sol/ratings.json` 有 `style:傲嬌` good；`data/route.json.by_style.傲嬌 == "writer-sol"`；`train/optimize/ratings.json` 的 `action:route` 有一筆 `delta` > 0、`counter_applied` 1；`human/samples.json` ≤ 6 筆、欄位齊、每筆 `lines` ≤ 10 行、`produced_by` 是存在的資料夾；`verify.jsonl` 兩行；trace 的 state 序列 verify、train、rate、optimize、verify。
9. **回滾**：把 `epochs/000/params/route.json` 做成「傲嬌 → writer-sol」、再把假腦技能表反過來（`GALTXT_FAKE_WEAK=sol:傲嬌`）跑 verify 格 → `data/route.json` 被拷回、stderr `train: Regressed`、退 10、`optimize/ratings.json` 的 `counter_regressed` 1。
10. **預算**：`budget.json` 暫改 `max_calls: 3` → 停在 train 格、stderr `train: BudgetSpent`、退 2；`route.json` 沒變。
11. **M7 守住**：訓練跑完，`writer/_metainfo`、`writer-sol/_metainfo`、`train/optimize/_metainfo`、`fsm.json` 的 bytes 跟跑前一樣；只有 `ratings.json`、`human/samples.json`、`data/route.json` 變。
12. **人評匯入**（§ 16，假評級）：手寫 `human/ratings.json` 三筆（兩筆指同一個 `produced_by`）→ `aos-exec human/import` 退 0 → 對應 `human.json` 的 `style:*` 格 `counter_ratings` 對、`val` 是多數決、`tags` 計數對、`dims` 平均對；`human/calibration.json` 列出人評與自動 `val` 不一致的格；`id` 對不到 `samples.json` ＝ stderr `import: SampleUnknown`、那筆跳過、退 0；`ratings.json` 不是陣列＝`RatingsBad` 退 1；重跑一次結果不變（整格覆蓋）。
13. **metatable**：`--json` 的 writer 列有 `ratings`（解開 `$ref`）、`role` 欄；`train` 列 `role == "dev"`；彙總的「頂層宣告」不含 dev。`_metainfo` 一致性加：`train.llm_calls.max ≥ len(train)×len(writers)×根.llm_calls.val`、`train.time_ms.max ≥ Σ 四格 timeout_ms × loop.max`（P-36）。
14. **真腦**（連不上就 skip）：Q16 跑通、一行、`guard_hit`；不斷言分數。訓練的真腦跑不進測試（5 分鐘、385k token）——手跑一次記進 `plan/round3-measure.md`。

---

## 12. 做的順序（每步能回頭；人評樣本在第一個 epoch 就出來，頂層先做網頁）

1. 資料（§ 5）＋ `Q16.json`、`scene-yuzuha.json`；假腦跑 Q16 通（測試 4）。
2. `brief.py` 的 `style`／`writer`、`write.py` 讀表、`pick.py` 記 `writer`／`dims`；初始 `route.json`（`by_style: {}`）；既有測試全綠（極小版行為不變）。
3. `writer-sol/`＋兩份初始 `ratings.json`、`human.json`＋兩份 `_metainfo` 的 `$ref`；驗 aos-fsm 吃不吃捷徑的 fsm.json（§ 4.1）。
4. 假腦技能表（測試 5）。
5. `human/questions.json`、`samples.json` 的格式先定、交頂層（§ 16.1，**這步不等後面**，頂層可以先拿假資料做網頁）。
6. `train/` 三支＋ `optimize/`＋ `set.json`、`budget.json`、`_metainfo`；單元測試 6、7，再整條 8～11。第一次假腦整條跑完就有一份真格式的 `human/samples.json`。
7. `human/import/`（測試 12）。
8. metatable 的 `$ref`、`ratings`、`role`；`meta/table-round3.md`。
9. 真腦手跑一次訓練（2 epoch）→ `plan/round3-measure.md`：評級實際長什麼樣、route 有沒有換、驗證分前後、token 實花 vs 385k、`optimize/ratings.json` 那一筆；`human/samples.json` 換成真腦的 6 筆交頂層。README 的樹與「怎麼跑」補 train 與 human。

---

## 13. 未決、要使用者拍的

1. **M7 補句**（§ 2.3）：「`_metainfo` 檔只有作者寫；量出來的放旁檔、由樹自己的工具寫、`_metainfo` 用 `$ref` 併進來」——要不要落成條文。
2. 評級門檻（4.0／3.0／3 份）是我定的；真腦評審分辨力低、可能全 good——那就靠 `score_avg` 平手判，是否可接受，還是要先做評審變體（更嚴的 rubric）。
3. 變體只換模型、不換 prompt（§ 1）——若使用者更想看「prompt 版本」當變體，`writer-sol/` 改成 `system.txt` 真檔、`.env` 捷徑，其餘不變。
4. `tree:` 前綴與 `role: dev`、`variant_of`、`state_key` 這幾個自加 key 要不要進通用表（optimize § 2.4 已提過兩個）。
5. 塔疊到第幾層（§ 15.3 建議：這圈停在第 2 層，而且第 2 層只准單調保守規則）。
6. 人評每輪 6 筆、只在訓練的第一個 epoch 之後要一次（§ 16.4）——夠不夠少。

---

## 14. 結構化評分：從一個 `good` 長到 `dims`，再往下怎麼拆

使用者第 6 句。照 C-55（純值不夠用就長成物件、原值放 `val`）與 STRUCTURE 的「膨脹即拆、四級」套在**三處**：寫手的 `ratings.json`（§ 2.1）、`score.json`（評分節點 pick 的輸出）、優化函數的 `ratings.json`（§ 15）。三處同一套長法：

| 級 | 長相 | 什麼時候到這級 | 誰決定 |
|---|---|---|---|
| 1 純值 | `"style:傲嬌": "good"` | 只有一個訊號（總分門檻） | — |
| 2 物件 | `{"val": "good", "score_avg", "score_min", "counter_samples", "rated_at", "rated_by"}` | 要帶證據（幾份、多少分、誰量的）——**這圈從第 2 級起跳**，因為沒證據的 good 沒人敢拿來換路 | 純程式（形狀固定） |
| 3 子維度 | 加 `"dims": {"語域": 0.83, "語意": 0.67, "多樣性": 0.71, "護欄": 1.0}` | 有兩個以上**各自有量法**的訊號；這圈現成就有四個，所以一併做 | 加一個維度＝加一支量它的程式（lint 規則、評審 rubric 的一行、一支純程式），**那是腦／人的決定**；形狀由純程式長 |
| 4 拆檔 | `ratings.json` 的 `style:*` 格超過 1 KB 或某個維度自己要長子維度（例 `語意 → {承接, 留白, 口氣}`）→ `ratings/<風格>.json` 一檔一風格，`ratings.json` 變成 `{"$ref": [...]}`（M1 § 5）或只留索引 | STRUCTURE 觸發 A-4（條列區塊 > 1 KB）；metatable 可以算、印「該拆」 | 純程式判、人拍板搬（同 round2 的收攏） |

這圈的四個維度（全部純程式、從 `score.json` 已有的分換算、0～1）：

| 維度 | 算法 | 來源 |
|---|---|---|
| `語域` | Tier 1 ÷ 2（每份），平均 | lint（稱呼、口氣標記、NG 標記） |
| `語意` | Tier 2 ÷ 3（每份），平均 | 評審 |
| `護欄` | 過 Tier 0 的份數 ÷ 總份數 | lint |
| `多樣性` | 1 − 同一題各份草稿兩兩字元二元組重疊率的平均（整題一個數；pick 已有 `bigrams()`） | pick 算，純程式 |

使用者舉的「文筆」沒做：它要評審 rubric 多出一個分（腦的改動＋token），列為下一圈第一個候選維度；「多樣性」做了。`pick.py` 把每份的 `dims` 與整題的 `多樣性` 寫進 `score.json`（第 3 級），`rate.py` 只平均、不重算——評分節點的結構在評分節點長，評級程式只收。

**優化函數怎麼讀結構**（往梯度靠的那一步）：`val` 決定「要不要換」（這圈的唯一動作），`dims` 決定「下一圈該動哪個參數族」——寫成一張對照表放 `train/optimize/policy.json`（§ 15）：`語域` 差 → prompt／brief 的標記（`optimize-prompt`）；`語意` 差 → 換模型或路線（`optimize-model`／換路）；`多樣性` 差 → `write.py` 的 `HINTS`；`護欄` 差 → lint 規則或 brief。這圈 optimize 只在 stdout 印「最差維度 → 建議動作」，不動手；下一圈每個動作各自是一支函數。

**上層優化器的成果也是結構嗎**：是，同一套長法（§ 15.1 的 `action:route` 格從第 2 級起、`dims` 是「升了多少、回滾過幾次、每千 token 的增益」）；再上一層一樣。結構的**形狀**規則對每一層都一樣，只有軸名與維度名不同——這就是「同一套 STRUCTURE 規則」能疊的原因。

---

## 15. 優化函數也是一棵樹、也有評級；塔要疊幾層

使用者第 4、5 句。

### 15.1 `train/optimize/`：有自己 `_metainfo` 與評級的資料夾

```
train/optimize/
├─ _entry        → optimize.py 的內容（python3 腳本；§ 8.4 的規則）
├─ _metainfo     kind program、role dev、grow_level 4、ratings $ref、policy $ref
├─ ratings.json  它自己的評級：每種動作一格（這圈只有 action:route）
└─ policy.json   它自己的參數：{"min_gap": 0, "dims_to_action": {...}}
```

`optimize/_metainfo`：

```json
{"summary": "優化函數（第 2 層）：讀各寫手 _metainfo 裡的評級（含人評）、改 data/route.json；自己每次改動讓驗證分升降多少記在 ratings.json，回滾過就把 policy 的 min_gap 調大一級",
 "kind": "program", "grow_level": 4, "role": "dev",
 "time_ms": {"val": 50, "max": 10000}, "resource": ["cpu", "disk"],
 "side_effect": true, "idempotent": true, "deterministic": true, "interrupt": "safe", "parallel": false,
 "reads": ["tree:../../writer*/ratings.json", "tree:../../writer*/human.json", "tree:../../data/route.json", "tree:../set.json", "tree:ratings.json", "tree:policy.json"],
 "writes": ["tree:../../data/route.json", "tree:policy.json", "stack:params/"],
 "fs_needs": ["git_tracked"], "callers": 1,
 "ratings": {"$ref": "ratings.json"},
 "policy": {"$ref": "policy.json"}}
```

`optimize/ratings.json`（**由 `verify.py` 寫**——評第 2 層的程式是第 1 層驗證的那支，因為只有它知道改動前後的分；optimize 不自評）：

```json
{"source": "train/verify.py：每次 optimize 改了 route.json、下一個 epoch 的 verify 算出 score_mean 的差，就記一筆；門檻：delta_avg ≥ min_gain＝good、≥ 0＝ok、< 0＝bad、沒改過＝none",
 "scale": {"min": -5, "max": 5, "what": "驗證題 score_mean 的前後差；dims 一律 0～1"},
 "action:route": {"val": "good", "delta_avg": 0.5, "counter_applied": 1, "counter_improved": 1, "counter_regressed": 0,
                  "dims": {"命中": 1.0, "穩定": 1.0, "效率": 0.6},
                  "rated_at": "…", "rated_by": "train/verify.py epoch 1 @ …"}}
```

`dims`：`命中`＝改動後進步的比例、`穩定`＝1 − 回滾比例、`效率`＝每 100k token 換到的分（上限 1）。「沒改（平手留原值）」不算一次 `counter_applied`，不然永遠不動的優化器會被評成 good（§ 15.3 的壞法 a）。

`optimize/policy.json`（第 2 層的「參數」）：

```json
{"source": "optimize 自己讀、自己改一個 key（min_gap）；其餘人寫",
 "min_gap": 0,
 "dims_to_action": {"語域": "optimize-prompt", "語意": "optimize-model", "多樣性": "hints", "護欄": "rules"}}
```

**最小的「讓它讀紀錄調整自己一次」**：optimize 開跑先讀自己的 `ratings.json`；`action:route` 的 `counter_regressed` > `counter_improved` 就把 `policy.min_gap` 從 0 升成 1（意思：以後同 val 不換，要差一個等級才換）；反過來連兩次 improved 就降回 0。這就是第 2 層讀第 2 層自己的成果調第 2 層的參數——**一棵樹自己收住**，不開第 3 層資料夾。規則單調、只有兩個值，所以不會學壞（§ 15.3）。

### 15.2 每層的成果是什麼、要跑幾次下層、成本怎麼乘

| 層 | 誰 | 一筆成果 | 要跑幾次下一層才有一筆 | 一筆的成本（實測推） | 訊號 vs 雜訊 |
|---|---|---|---|---|---|
| 1 台詞樹 | `galtxt-a/` | 一題的分數（結構：`dims`） | — | 1 題-次 ≈ 27k token、20 s | 評審 σ ≈ 0.5 分（Q01 三份同分、scene 4／4／5），單筆就能分 good／bad，分不出 4.0 與 4.3 |
| 2 優化函數 | `train/optimize/` | 一次改動帶來的驗證分差 Δ | 1 epoch＝4 訓練＋2 驗證＝**6 題-次** | ≈ 165k token、2 min | Δ 的雜訊 ≈ σ/√6 × √2 ≈ 0.3；`min_gain` 0.25 剛好在雜訊邊上——所以 2 epoch 只能看出「大致對了」，不能當數字 |
| 3 優化優化函數的 | （沒做） | 一次 policy 改動帶來的「Δ 的變化」（例：回滾率降、每 token 增益升） | 1 次完整訓練＝2～3 epoch＝**14 題-次** | ≈ 385k token、5 min | 一筆雜訊 ≈ 0.3 × √2 ≈ 0.4，要看出 policy 好壞至少 5 筆＝5 次訓練 ≈ 2M token、25 min；而且每筆都在同兩題驗證題上量，早就過擬合 |
| N | — | 第 N−1 層改動帶來的第 N−1 層成果變化 | 每往上一層 ×（題數 × epoch）≈ **×6～14** | 指數長 | 雜訊每層 ×√2 疊上去、樣本每層 ÷6～14：第 3 層起訊號淹沒 |

**結論**：成本每層乘 6～14、樣本每層除 6～14、雜訊每層乘 √2——第 3 層一筆成果要 385k token，而且 5 筆才勉強不是雜訊。這圈**停在第 2 層**，第 2 層的「學」只准單調保守規則（`min_gap` 兩個值），不准從自己的 1～2 筆成果裡學連續值。

### 15.3 同一棵優化樹優化自己（自我參照）能不能收住塔、會壞在哪

能收住：§ 15.1 的「optimize 讀自己的 `ratings.json` 改自己的 `policy.json`」就是把第 3 層的工作塞回第 2 層做，塔到此為止——因為成果（Δ）由第 1 層的 verify 算、不是它自己算，所以不是「自己給自己打分」。會壞在：

| 壞法 | 怎麼發生 | 這圈怎麼擋 |
|---|---|---|
| a. 退化成「什麼都不做最安全」 | 不換路就不會回滾，`穩定` 永遠 1.0、`val` good | 平手留原值不算 `counter_applied`；沒改過＝`none`；`效率` 維度記每 token 增益，不動＝0 |
| b. 自己給自己打分 | optimize 改 policy、又由 optimize 評 policy | 成果只由 `verify.py`（第 1 層的驗證）寫；optimize 對自己的 `ratings.json` 只讀 |
| c. 驗證題被每一層共用 | 第 1、2 層都看 Q01／Q16 的分；第 2 層調 `min_gap` 也是對著它們 | 承認：題只有兩題，這圈不分第二份驗證集；下一圈加題時第 2 層用不同的題（例：Q08、Q13） |
| d. 改自己的規則而不是參數 | 讓腦改 `optimize.py` 本身＝self-improve 的「函數自己改自己」；改壞了連回滾都靠它自己 | 不做：policy 只有 JSON 參數；程式由人／git 管 |
| e. 震盪 | `min_gap` 0 ↔ 1 來回 | 升要一次回滾、降要連兩次進步（不對稱） |
| f. 信用分配 | 分變了是換路的功勞還是評審抖動？ | 承認分不出；`counter_applied` 多了再看平均，1～2 筆只當紀錄 |

---

## 16. 人評：使用者觀感怎麼進來（少用、只校正）

使用者第 7 句＋「時間不多、最好少用」。網頁由頂層做（兩隊共用）；我們交三樣、一支匯入程式，人評**不是主訊號**，是拿來校正自動評分器的。

### 16.1 交給網頁的（格式隊長定的，照抄；多的 key 讀者忽略 C-48）

`human/samples.json`（陣列，**最多 6 筆**、台詞短）：

```json
[{"id": "a-q16-sol-2", "team": "a", "round": 1,
  "scene": {"cast": ["主角", "宮澤柚葉"], "place": "教室", "event": "文化祭收攤、彩帶垂落的黃昏", "style": "傲嬌", "intent": "餘溫"},
  "lines": ["宮澤柚葉：「……哼，才、才沒有開心。不過……偶爾這樣鬧一場，也不是不能接受啦。」"],
  "produced_by": "writer-sol",
  "auto_scores": {"val": "good", "total": 4, "dims": {"語域": 1.0, "語意": 0.67, "護欄": 1.0, "多樣性": 0.71}, "reason": "承接自然"},
  "brain": "real",
  "why_picked": "tie"}]
```

`human/questions.json`：

```json
{"source": "想問使用者的；tags 是勾選、dims 是 0～1 的滑桿或三段",
 "tags": ["像這個角色", "太白", "太油", "接不上前文", "稱呼不對", "有留白", "想看下去"],
 "dims": ["多樣性", "文筆", "像不像"]}
```

`tags` 對應自動評分抓得到／抓不到的東西各一半：「稱呼不對」「太油」lint 抓得到（校正 lint）、「像這個角色」「想看下去」只有人知道（校正評審）。`dims` 的「文筆」「像不像」是自動評分**沒有**的維度——人評先量，日後要不要做成自動維度看人評有沒有分辨力。

網頁回來的 `human/ratings.json`：每筆 `{"id", "overall": "good|ok|bad", "tags": [...], "dims": {...}, "comment", "rated_at"}`。

### 16.2 怎麼挑那 6 筆（主動學習，純程式，在 `rate.py` 第一個 epoch 之後做）

候選＝這個 epoch 所有過護欄的草稿（訓練題＋驗證題都可，因為人評不拿來調參數、不怕汙染驗證集）。每筆算一個「不確定度」，取前 6、再套限制：

| 挑法 | 分數 | 為什麼 |
|---|---|---|
| 自動評分自己打架 | `|語域 − 語意|` 大（lint 說像、評審說不像，或反過來） | 最能校正：兩個自動評分器至少錯一個 |
| 平手 | 同題同分、靠編號挑的（Q01 三份同分） | 自動評分分不出的，人分得出就是新維度的證據 |
| 剛好在門檻上 | `total` 落在 3～4 之間（good／ok 的邊界） | 門檻（§ 2.1）是我定的，人評校正門檻 |
| 覆蓋 | 每個（寫手, 風格）格 ≥ 1、≤ 2 筆 | 不然 6 筆全是傲嬌 |
| 短 | 挖空題（1 行）優先；場景題只收 ≤ 8 行的 | 使用者時間 |

挑到的寫 `why_picked`（`disagree`／`tie`／`threshold`／`cover`）。只在**第一個 epoch** 之後寫（頂層最早能拿到），之後的 epoch 不覆蓋（`samples.json` 在就不動；要重挑刪掉它）。真腦跑完換成真腦的 6 筆（假腦的 6 筆只給頂層做網頁用，`brain: "fake"`）。

### 16.3 匯入：`human/import/`（資料夾程式，人手叫，`callers 0`）

```sh
aos-exec proto8/topdown/galtxt-a/human/import        # 讀 human/ratings.json → 寫各寫手的 human.json、human/calibration.json
```

- 照 `id` 對回 `samples.json` 拿 `produced_by` 與 `scene.style`；對不到＝stderr `import: SampleUnknown <id>`、跳過、退 0（預料到的：網頁可能帶舊樣本）；`ratings.json` 不是陣列或缺 `id`／`overall`＝`RatingsBad` 退 1。
- 寫 `<produced_by>/human.json`（M7 同款：旁檔、`_metainfo.human_ratings` 用 `$ref`；**跟自動評級分開兩個檔**，兩支程式各寫各的、不互蓋）：

```json
{"source": "human/import 從 human/ratings.json 併；每格整格覆蓋；人評是校正用，optimize 只在 val: bad 且 counter_ratings ≥ 3 時當否決",
 "style:傲嬌": {"val": "ok", "counter_ratings": 3, "overall": {"good": 1, "ok": 2, "bad": 0},
                "tags": {"像這個角色": 2, "太白": 1},
                "dims": {"多樣性": 0.5, "文筆": 0.7, "像不像": 0.8},
                "comments": ["第二句有點像晴子"],
                "rated_at": "…", "rated_by": "human/import @ human/ratings.json 3 筆"}}
```

`val`＝`overall` 多數決（平手取較差的，人嚴一點）；`< 3` 筆＝`none`。結構照 § 14 同一套長法（第 2 級起、`dims` 第 3 級）。
- 同時寫 `human/calibration.json`：每個（寫手, 風格）格並排 `auto.val` vs `human.val`、`auto.dims` vs `human.dims` 共有的維度、不一致的列出來，加一行判讀（純程式規則：人 bad 而 auto good ＝「評審太鬆」；人 good 而 auto bad ＝「lint 太嚴（看 tags 哪條）」）。這份是給人看的校正報告，也是下一圈改門檻／rubric 的依據；**這圈不自動改門檻**。
- `human/import/_metainfo`：`kind program`、`role dev`、`grow_level 3`、`time_ms 50／10000`、`resource disk`、`side_effect true`、`idempotent true`、`deterministic true`、`reads` [`tree:../ratings.json`, `tree:../samples.json`, `tree:../../writer*/ratings.json`]、`writes` [`tree:../../writer*/human.json`, `tree:../calibration.json`]、`fs_needs [git_tracked]`、`callers 0`。`human/_metainfo`：`kind data`、`fs_needs [git_tracked]`、`children` 四張表各一句。

### 16.4 多少人評才夠、放在迴圈哪裡

- **一輪 6 筆、每筆 ≤ 1 分鐘**（勾 2～3 個 tag、拉 3 個滑桿、一句話選填）≈ 5 分鐘；一次訓練只要一輪（第一個 epoch 之後）。使用者「最好少用」→ 真腦訓練跑一次要一輪，之後**只在自動評級換了路線、或 `calibration.json` 出現不一致時**才再要一輪。
- 夠做什麼：6 筆分到 4 個（寫手, 風格）格，每格 1～2 筆——**只夠抓「自動評分明顯錯」**（人 bad／auto good 這種），不夠給每格一個可信的 `val`（要 ≥ 3 筆才非 none，所以第一輪多半全 none、只有 calibration 有用）。兩三輪（12～18 筆）後每格 ≥ 3，`human.val` 才開始進 optimize 的否決規則。
- 不夠也沒關係：人評的位置是**校正器**（看自動評分哪裡跟人不一致），不是訊號——訊號仍是自動評級（§ 2）。所以人評晚到、沒到，迴圈照跑。
- 迴圈裡的位置：`rate`（第一個 epoch）挑樣本 → 樹外（頂層網頁、使用者）→ `human/import`（人手叫）→ 下一次 `optimize` 讀得到 `human.json`。人評不在 fsm 的格裡（等人＝`resource: human`，C-28 間接抽象化：寄出去、人在系統外做、收回來）。
